# Porterino checks: plain functions that measure a Blender scene and return lists of findings.
# No UI in this file, so the same code runs from the panel buttons and from the command line.
# A finding is a dict: {"check", "level" ("problem" | "look" | "ok"), "text", "location" (x, y, z) or None}.
import math
import re

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DOWN = Vector((0.0, 0.0, -1.0))

# Things that are never ground you ride on. Used so tree tops and backdrops are not reported as holes.
NOT_GROUND = re.compile(
    r"vista|periph|backdrop|skybox|sky_|cloud|water|ocean|river|lake|horizon|cliff|mountain|decal|graffiti|puddle|"
    r"stain|leaf|leaves|foliage|tree|oak|pine|palm|maple|birch|acacia|dogwood|elm|cedar|canopy|awning|bush|ivy|grass_atlas", re.I)
RAMP = re.compile(
    r"ramp|quarter|(^|_)qp(_|\d|$)|half_?pipe|bowl|kicker|launch|funbox|fun_box|pyramid|spine|bank|transition|"
    r"roll_?in|wedge|hip(_|\d|$)|vert(_|\d|$)|pool", re.I)
NOT_RAMP = re.compile(r"decal|graffiti|sign|fence|light|lamp|sticker|poster|vista|backdrop|water", re.I)


def is_solid(obj):
    """True when the object has collision in ReSkate Studio. Without Studio's add-on every mesh counts as solid."""
    settings = getattr(obj, "sk8_object", None)
    if settings is None:
        return True
    return str(getattr(settings, "collision_mode", "triangle_mesh")) != "none"


def finding(check, level, text, location=None):
    return {"check": check, "level": level, "text": text,
            "location": tuple(round(v, 3) for v in location) if location is not None else None}


def find_spawn(scene):
    for obj in scene.objects:
        if obj.name.lower().startswith(("spawn", "start", "playerstart")):
            return obj
    return None


def _hits_below(scene, depsgraph, x, y, top, depth, max_hits=10):
    """Every up-facing surface under (x, y), highest first: (z, object, normal_z)."""
    origin = Vector((x, y, top))
    left = depth
    hits = []
    for _ in range(max_hits):
        hit, loc, nor, _idx, obj, _mat = scene.ray_cast(depsgraph, origin, DOWN, distance=left)
        if not hit:
            break
        src = getattr(obj, "original", obj)
        if src.type == "MESH":
            hits.append((loc.z, src, nor.z))
        left -= (origin.z - loc.z) + 0.02
        origin = Vector((x, y, loc.z - 0.02))
        if left <= 0:
            break
    return hits


def ride_height(scene, depsgraph, x, y, top, depth=6.0):
    """Height of the surface the skater rides at (x, y): the first SOLID, up-facing surface from above."""
    for z, obj, nz in _hits_below(scene, depsgraph, x, y, top, depth, 8):
        if is_solid(obj):
            return z if nz > 0.35 else None
    return None


# ---------------------------------------------------------------------------------------------------------------
def check_floor_holes(scene, depsgraph, radius=150.0, step=None, centre=None, max_columns=160000):
    """Drawn floor with nothing solid under it: places where the player falls through the map."""
    if centre is None:
        spawn = find_spawn(scene)
        centre = spawn.location.copy() if spawn else scene.cursor.location.copy()
    if step is None:
        step = max(0.5, math.sqrt(math.pi * radius * radius / max_columns))
    meshes = [o for o in scene.objects if o.type == "MESH"]
    if not meshes:
        return [finding("floor", "ok", "No meshes in the scene.")]
    footprint = {o.name: sorted(o.dimensions)[1] * max(o.dimensions) for o in meshes}
    top = max(o.matrix_world.translation.z + max(o.dimensions) for o in meshes) + 5.0
    bad = {}
    n = int(radius / step)
    for ix in range(-n, n + 1):
        x = centre.x + ix * step
        for iy in range(-n, n + 1):
            if ix * ix + iy * iy > n * n:
                continue
            y = centre.y + iy * step
            hits = [h for h in _hits_below(scene, depsgraph, x, y, top, top + 400.0) if h[2] > 0.75]
            solid_z = [z for z, obj, _ in hits if is_solid(obj)]
            for z, obj, _ in hits:
                if is_solid(obj) or footprint.get(obj.name, 0.0) < 12.0:
                    continue
                if NOT_GROUND.search(obj.data.name) or NOT_GROUND.search(obj.name):
                    continue
                # solid a little above it means the piece is buried under real floor, which is harmless
                if not any(-0.5 <= z - s <= 1.2 for s in solid_z):
                    below = [z - s for s in solid_z if s < z]
                    bad[(ix, iy)] = (z, obj.data.name, min(below) if below else None)
                    break
    out, seen = [], set()
    for key in bad:
        if key in seen:
            continue
        group, stack = [], [key]
        while stack:
            q = stack.pop()
            if q in seen or q not in bad:
                continue
            seen.add(q)
            group.append(q)
            stack += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
        area = len(group) * step * step
        if area < 2.0:
            continue
        cx = centre.x + sum(q[0] for q in group) / len(group) * step
        cy = centre.y + sum(q[1] for q in group) / len(group) * step
        z, name, _drop = bad[group[0]]
        drops = [bad[q][2] for q in group]
        if any(d is None for d in drops):
            # no ground at all under part of it: the player leaves the map
            out.append((area + 1e6, finding("floor", "problem",
                                            "%.0f m2 of drawn floor has nothing solid under it: you fall out of the map (%s)" % (area, name),
                                            (cx, cy, z))))
        else:
            out.append((area, finding("floor", "look",
                                      "%.0f m2 of %s is not solid: you sink through it and land %.1f m lower" % (area, name, max(drops)),
                                      (cx, cy, z))))
    out.sort(key=lambda t: -t[0])
    if not out:
        return [finding("floor", "ok", "No holes found within %.0f m (grid %.2f m)." % (radius, step))]
    return [f for _, f in out[:40]]


# ---------------------------------------------------------------------------------------------------------------
def check_ramp_lips(scene, depsgraph, objects=None, minimum_cm=3.5):
    """Sharp steps where the floor meets the foot of a ramp, quarter pipe, bank, bowl or kicker.
    Pieces are found by name unless `objects` is given (for example the current selection)."""
    step_len, half, low, high = 0.02, 0.6, 0.015, 0.08
    if objects is None:
        objects = [o for o in scene.objects if o.type == "MESH" and RAMP.search(o.data.name + " " + o.name)
                   and not NOT_RAMP.search(o.data.name)]
    out, checked = [], 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        d = obj.dimensions
        if max(d.x, d.y) < 1.0 or d.z < 0.15 or max(d) > 80.0:
            continue
        box = [Vector(c) for c in obj.bound_box]
        lo = Vector((min(c[k] for c in box) for k in range(3)))
        hi = Vector((max(c[k] for c in box) for k in range(3)))
        mw = obj.matrix_world
        corners = [mw @ Vector((x, y, lo.z)) for x, y in ((lo.x, lo.y), (hi.x, lo.y), (hi.x, hi.y), (lo.x, hi.y))]
        centre = sum(corners, Vector()) / 4.0
        zfoot = min(c.z for c in corners)
        checked += 1
        lips = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            edge = b - a
            if edge.length < 0.8:
                continue
            outward = Vector((edge.y, -edge.x, 0.0)).normalized()
            if outward.dot((a + b) / 2 - centre) < 0:
                outward = -outward
            n = max(2, int(edge.length / 0.5))
            # an entrance is an edge where the piece is still low just inside it; sides and backs are steps by design
            inside = sorted(z for z in (ride_height(scene, depsgraph, (a + edge * (i / n)).x - outward.x * 0.3,
                                                    (a + edge * (i / n)).y - outward.y * 0.3, zfoot + 1.5)
                                        for i in range(1, n)) if z is not None)
            if not inside or inside[len(inside) // 2] - zfoot > 0.25:
                continue
            for i in range(1, n):
                p = a + edge * (i / n)
                ground = ride_height(scene, depsgraph, p.x + outward.x * 0.5, p.y + outward.y * 0.5, zfoot + 1.5)
                if ground is None or abs(ground - zfoot) > 0.35:
                    continue
                prev = None
                for k in range(int(-half / step_len), int(half / step_len) + 1):
                    q = p - outward * (k * step_len)
                    z = ride_height(scene, depsgraph, q.x, q.y, zfoot + 1.5)
                    if z is not None and prev is not None and low <= abs(z - prev) <= high:
                        # a wedge also rises a few cm over 2 cm of travel; it is a lip only if the rise is one sharp step
                        sharp, zp = 0.0, None
                        for j in range(9):
                            qq = p - outward * ((k - 1) * step_len + j * 0.0025)
                            zz = ride_height(scene, depsgraph, qq.x, qq.y, zfoot + 1.5)
                            if zz is not None and zp is not None:
                                sharp = max(sharp, abs(zz - zp))
                            zp = zz if zz is not None else zp
                        if 0.012 <= sharp <= 0.10:           # more than 10 cm is a ledge or kerb built on purpose
                            lips.append((sharp * 100.0, q.copy(), z))
                        break
                    prev = z if z is not None else prev
        if len(lips) >= 2:
            worst = max(lips, key=lambda t: t[0])
            if worst[0] >= minimum_cm:
                typical = sorted(t[0] for t in lips)[len(lips) // 2]
                out.append((worst[0], finding(
                    "lips", "look", "%s: sharp step up to %.1f cm at its foot (typical %.1f cm, %d places)" % (
                        obj.name, worst[0], typical, len(lips)), (worst[1].x, worst[1].y, worst[2]))))
    out.sort(key=lambda t: -t[0])
    if not out:
        return [finding("lips", "ok", "%d ramp pieces checked, no sharp step of %.1f cm or more at an entrance." % (checked, minimum_cm))]
    return [finding("lips", "look", "%d ramp pieces checked, %d have a sharp step at an entrance." % (checked, len(out)))] + \
           [f for _, f in out[:40]]


# ---------------------------------------------------------------------------------------------------------------
def check_transition(depsgraph, objects, centre, directions=32, reach=12.0, min_lip_deg=75.0, max_kink_deg=14.0):
    """Measures a bowl or quarter pipe from a point on its flat bottom (the 3D cursor), outward in every direction.
    Reports, per direction that climbs a wall: height, angle at the lip, the biggest change of angle between two
    facets, and a radius estimate. Uses only the given objects, so it works on a piece you are still modelling."""
    trees = []
    top = None
    for obj in objects:
        if obj.type != "MESH":
            continue
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = obj.matrix_world
        verts = [mw @ v.co for v in me.vertices]          # world space, so moved and rotated pieces measure right
        polys = [tuple(pl.vertices) for pl in me.polygons]
        ev.to_mesh_clear()
        if not polys:
            continue
        trees.append(BVHTree.FromPolygons(verts, polys))
        top = max([v.z for v in verts] + ([top] if top is not None else []))
    if not trees:
        return [finding("transition", "look", "Select the bowl or ramp mesh first.")]
    top += 1.0

    def sample(x, y):
        """Highest surface at (x, y): (z, normal) or None."""
        best = None
        for tree in trees:
            loc, nor, _i, _d = tree.ray_cast(Vector((x, y, top)), DOWN, 60.0)
            if loc is not None and (best is None or loc.z > best[0]):
                best = (loc.z, nor if nor.z >= 0 else -nor)
        return best

    hit0 = sample(centre.x, centre.y)
    z0 = hit0[0] if hit0 else centre.z     # a separate floor piece: the cursor's own height is the floor
    step = 0.01
    rows = []
    for i in range(directions):
        ang = 2.0 * math.pi * i / directions
        way = Vector((math.cos(ang), math.sin(ang), 0.0))
        prof = []                                          # (distance, z, slope in degrees, uphill direction)
        for k in range(int(reach / step)):
            hit = sample(centre.x + way.x * k * step, centre.y + way.y * k * step)
            if hit is None:
                if prof and prof[-1][1] > z0 + 0.03:
                    break                                  # ran off the wall
                continue                                   # still over the floor piece, before the wall starts
            z, nor = hit
            flat = Vector((-nor.x, -nor.y, 0.0))
            prof.append((k * step, z, math.degrees(math.acos(max(-1.0, min(1.0, nor.z)))),
                         flat.normalized() if flat.length > 1e-4 else None))
        wall = [p for p in prof if p[1] - z0 > 0.03]
        if len(wall) < 10:
            continue
        tall = max(p[1] for p in wall) - z0
        if tall < 0.4:
            continue
        # only measure where this direction runs up the wall; crossing it at a slant reads shallower than it is
        steep = [p for p in wall if p[3] is not None and p[2] > 10.0]
        if not steep or sum(1 for p in steep if p[3].dot(way) > 0.87) < 0.7 * len(steep):
            continue
        upper = [p for p in steep if p[1] - z0 >= 0.7 * tall] or steep
        lip_angle = max(p[2] for p in upper)
        end = max(wall, key=lambda p: p[1])
        # a truly vertical top cannot be seen from above: look for it sideways, just under the highest point found
        origin = Vector((centre.x, centre.y, end[1] + 0.05))
        for tree in trees:
            loc, nor, _i, _d = tree.ray_cast(origin, way, reach)
            if loc is not None and abs(nor.z) < 0.17:
                lip_angle = max(lip_angle, math.degrees(math.acos(abs(nor.z))))
                break
        facets = []
        for p in steep:
            if not facets or abs(p[2] - facets[-1]) > 0.5:
                facets.append(p[2])
        kink = max((abs(q - r) for q, r in zip(facets, facets[1:])), default=0.0)
        run = end[0] - wall[0][0]
        radius = (run * run + tall * tall) / (2.0 * tall)
        where = (centre.x + way.x * end[0], centre.y + way.y * end[0], end[1])
        rows.append((ang, tall, lip_angle, kink, radius, where))
    if not rows:
        return [finding("transition", "look", "No wall found within %.0f m of the cursor. Put the cursor on the flat bottom." % reach)]
    out = []
    lip_angles = [r[2] for r in rows]
    out.append(finding("transition", "ok", "%d of %d directions climb a wall. Height %.2f-%.2f m, lip angle %.0f-%.0f deg, radius about %.1f m." % (
        len(rows), directions, min(r[1] for r in rows), max(r[1] for r in rows), min(lip_angles), max(lip_angles),
        sorted(r[4] for r in rows)[len(rows) // 2])))
    for ang, tall, lip_angle, kink, radius, where in rows:
        notes = []
        if lip_angle < min_lip_deg:
            notes.append("top of the transition reaches only %.0f deg: you launch outward, not up" % lip_angle)
        if kink > max_kink_deg:
            notes.append("angle jumps %.0f deg between two facets: add segments" % kink)
        if notes:
            out.append(finding("transition", "look", "Direction %3.0f deg: %s (height %.2f m)" % (
                math.degrees(ang), "; ".join(notes), tall), where))
    if len(out) == 1:
        out.append(finding("transition", "ok", "Every wall reaches %.0f deg or more at the lip and no facet turns more than %.0f deg." % (
            min_lip_deg, max_kink_deg)))
    return out


def check_rim(objects, max_turn_deg=10.0, max_segment=0.45):
    """Kinks along a selected rim or coping line: works on a CURVE object or on the selected edge loop's vertices
    of a mesh in the order Blender stores them. Reports turns sharper than max_turn_deg and long straight segments."""
    out = []
    for obj in objects:
        loops = []
        if obj.type == "CURVE":
            for spline in obj.data.splines:
                pts = spline.bezier_points if spline.type == "BEZIER" else spline.points
                loops.append(([obj.matrix_world @ Vector(p.co[:3]) for p in pts], bool(spline.use_cyclic_u)))
        for pts, closed in loops:
            if len(pts) < 3:
                continue
            seq = pts + (pts[:2] if closed else [])
            worst_turn, worst_at, long_seg = 0.0, None, 0.0
            for a, b, c in zip(seq, seq[1:], seq[2:]):
                u, v = (b - a), (c - b)
                long_seg = max(long_seg, u.length)
                if u.length > 1e-6 and v.length > 1e-6:
                    turn = math.degrees(u.angle(v))
                    if turn > worst_turn:
                        worst_turn, worst_at = turn, b
            level = "look" if worst_turn > max_turn_deg or long_seg > max_segment else "ok"
            out.append(finding("rim", level, "%s: %d points, sharpest turn %.0f deg, longest segment %.2f m%s" % (
                obj.name, len(pts), worst_turn, long_seg,
                "" if level == "ok" else " (aim for under %.0f deg and %.2f m)" % (max_turn_deg, max_segment)), worst_at))
    if not out:
        out.append(finding("rim", "look", "Select the coping or rim as a curve object (Studio grind curve) and run again."))
    return out


# ---------------------------------------------------------------------------------------------------------------
def check_routes(scene, depsgraph):
    """Pedestrian and traffic routes: no pop-in beside the player, nothing spawning off the map."""
    spawn = find_spawn(scene)
    sp = spawn.location.copy() if spawn else None
    out, pedestrians, seen_any = [], 0, False
    for obj in scene.objects:
        route = getattr(obj, "sk8_npc_route", None)
        if obj.type != "CURVE" or route is None or not getattr(route, "enabled", False):
            continue
        seen_any = True
        pts, closed = [], False
        for spline in obj.data.splines:
            closed = closed or bool(spline.use_cyclic_u)
            src = spline.bezier_points if spline.type == "BEZIER" else spline.points
            pts += [obj.matrix_world @ Vector(p.co[:3]) for p in src]
        if len(pts) < 2:
            continue
        kind = str(route.kind)
        pedestrians += kind == "pedestrian"
        length = sum((a - b).length for a, b in zip(pts, pts[1:])) + ((pts[-1] - pts[0]).length if closed else 0.0)
        spacing = float(getattr(route, "spacing", 0.0) or 0.0)
        samples = max(1, int(round(length / spacing))) if spacing > 0 else 0
        off = [p for p in pts if ride_height(scene, depsgraph, p.x, p.y, p.z + 1.5, 4.0) is None]
        problems = []
        if kind == "pedestrian" and closed:
            problems.append("closed loop: walkers appear and vanish beside the player; use an open path")
        if samples > 2:
            problems.append("about %d spawn points on %.0f m: set spacing near the route length for one" % (samples, length))
        if off:
            problems.append("%d of %d points are not over solid ground" % (len(off), len(pts)))
        if sp is not None and min((p - sp).length for p in pts) < 12.0:
            problems.append("passes within 12 m of the player start")
        if problems:
            out.append(finding("routes", "problem", "%s (%s): %s" % (obj.name, kind, "; ".join(problems)), off[0] if off else pts[0]))
    if not seen_any:
        return [finding("routes", "ok", "No NPC routes in this scene (or ReSkate Studio's add-on is not enabled).")]
    if pedestrians > 3:
        out.append(finding("routes", "look", "%d pedestrian routes: more than 3 on one map costs frame rate on slower PCs." % pedestrians))
    return out or [finding("routes", "ok", "All routes are open, single-spawn, on solid ground and away from the start.")]


# ---------------------------------------------------------------------------------------------------------------
def check_lights(scene):
    """Light setup: range and time of day set, nothing hidden from render, and no emission that will be ignored."""
    out, lights = [], 0
    for obj in scene.objects:
        if obj.type != "LIGHT":
            continue
        lights += 1
        if obj.data.type == "SUN":
            out.append(finding("lights", "look", "%s is a Sun light: ReSkate uses the game's own sun, this one is skipped." % obj.name, obj.location))
            continue
        notes = []
        if obj.hide_render:
            notes.append("hidden from render, so it is NOT exported")
        if "sk8_light_range" not in obj:
            notes.append("no range set (Studio will use 40 m)")
        if "sk8_light_tod" not in obj:
            notes.append("no time of day set (on all the time)")
        if notes:
            out.append(finding("lights", "look", "%s: %s" % (obj.name, "; ".join(notes)), obj.location))
    emissive = []
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.node_tree is None or mat.users == 0:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeBsdfPrincipled":
                strength = node.inputs.get("Emission Strength")
                colour = node.inputs.get("Emission Color")
                lit = strength is not None and (strength.is_linked or strength.default_value > 0.0)
                coloured = colour is not None and (colour.is_linked or max(colour.default_value[:3]) > 0.0)
                if lit and coloured:
                    emissive.append(mat.name)
            elif node.bl_idname == "ShaderNodeEmission":
                emissive.append(mat.name)
    if emissive:
        names = sorted(set(emissive))
        out.append(finding("lights", "look", "%d material(s) use emission, which ReSkate Studio ignores (tested in game): %s. "
                                             "Use 'Add glow light' on the surface instead." % (len(names), ", ".join(names[:8]))))
    hidden = [o.name for o in scene.objects if o.type == "MESH" and o.hide_render]
    if hidden:
        out.append(finding("lights", "look", "%d mesh(es) are hidden from render and will be left out of the compiled map: %s" % (
            len(hidden), ", ".join(hidden[:8]))))
    return out or [finding("lights", "ok", "%d lights, all with range and time of day set; no emission materials; nothing hidden from render." % lights)]


# ---------------------------------------------------------------------------------------------------------------
TIME_FLAGS = {"morning": 1, "noon": 2, "afternoon": 4, "evening": 8, "night": 16, "weatherday": 32, "weathernight": 64}


def set_light(obj, range_m, times):
    obj["sk8_light_range"] = float(range_m)
    obj["sk8_light_tod"] = int(sum(TIME_FLAGS[t] for t in times))


def add_glow_light(scene, obj, power=300.0, offset=0.3, times=("evening", "night", "weathernight")):
    """A real Area light just in front of a flat piece, sized to it: the way to make a sign or panel look lit."""
    mesh = obj.data
    if not mesh.polygons:
        return None
    face = max(mesh.polygons, key=lambda p: p.area)
    centre = obj.matrix_world @ face.center
    normal = (obj.matrix_world.to_3x3() @ face.normal).normalized()
    data = bpy.data.lights.new(obj.name + " glow", "AREA")
    data.energy = power
    data.shape = "RECTANGLE"
    dims = sorted(obj.dimensions, reverse=True)
    data.size, data.size_y = max(dims[0] * 0.9, 0.1), max(dims[1] * 0.9, 0.1)
    light = bpy.data.objects.new(obj.name + " glow", data)
    scene.collection.objects.link(light)
    light.location = centre + normal * offset
    light.rotation_euler = normal.to_track_quat("Z", "Y").to_euler()      # the light's -Z points back at the surface
    set_light(light, max(4.0, dims[0] * 4.0), times)
    return light


def scale_map(scene, factor):
    """Scale the whole map about the world origin, keeping lights looking the same and markers their real size."""
    count = 0
    for obj in scene.objects:
        if obj.parent is not None:
            continue
        obj.location = Vector(obj.location) * factor
        volume = getattr(obj, "sk8_audio", None)
        keep_size = obj.type == "LIGHT" or (obj.type == "EMPTY" and not (volume is not None and getattr(volume, "enabled", False)))
        if not keep_size:
            obj.scale = Vector(obj.scale) * factor
        route = getattr(obj, "sk8_npc_route", None)
        if obj.type == "CURVE" and route is not None and getattr(route, "enabled", False):
            route.width = max(route.width * factor, 0.8)
            route.spacing = max(route.spacing * factor, 1.0)
        if "sk8_light_range" in obj:
            obj["sk8_light_range"] = float(obj["sk8_light_range"]) * factor
        count += 1
    for data in bpy.data.lights:
        data.energy *= factor * factor
        if getattr(data, "use_custom_distance", False):
            data.cutoff_distance *= factor
        if data.type == "AREA":
            data.size *= factor
            data.size_y *= factor
    return count
