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
SCENERY = re.compile(r"backdrop|vista|periph|skybox|sky_|cloud|horizon|mountain|water|ocean", re.I)


def _material_drawn(mat):
    """A material that is drawn as an ordinary opaque surface (not invisible, not a cut-out, decal or glass)."""
    if mat is None:
        return True
    s = getattr(mat, "sk8_material", None)
    if s is None:
        return True
    if getattr(s, "invisible", False):
        return False
    return str(getattr(s, "alpha", "opaque")) in ("opaque", "auto") and str(getattr(s, "domain", "surface")) == "surface"


def _world_tree(scene, depsgraph, want):
    """One BVH tree in world space from the faces `want(object, material)` accepts. Returns (tree, object name per face)."""
    verts, polys, owner = [], [], []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        me = obj.data
        mats = me.materials
        picked = [p for p in me.polygons if want(obj, mats[p.material_index] if p.material_index < len(mats) else None)]
        if not picked:
            continue
        base, mw = len(verts), obj.matrix_world
        verts += [mw @ v.co for v in me.vertices]
        for p in picked:
            polys.append(tuple(base + i for i in p.vertices))
            owner.append(obj.name)
    return (BVHTree.FromPolygons(verts, polys) if polys else None), owner


def seen_vs_solid(scene, depsgraph, radius=150.0, step=0.5, centre=None, tolerance=0.15):
    """Measures, piece by piece, how much of what is DRAWN has nothing SOLID within `tolerance` metres of it.
    Works for maps where the drawn mesh and the collision mesh are separate objects (most ports) and for maps where
    one mesh does both. Returns {object name: [sampled m2, unsupported m2, biggest gap m, first bad spot]}."""
    if centre is None:
        spawn = find_spawn(scene)
        centre = spawn.location.copy() if spawn else scene.cursor.location.copy()
    vis, vis_owner = _world_tree(scene, depsgraph, lambda o, m: not o.hide_render and _material_drawn(m))
    sol, _ = _world_tree(scene, depsgraph, lambda o, m: is_solid(o))
    out = {}
    if vis is None:
        return out
    top = max((o.matrix_world @ Vector(c)).z for o in scene.objects if o.type == "MESH" for c in o.bound_box) + 2.0

    def column(tree, x, y, limit=8):
        found, z = [], top
        for _ in range(limit):
            loc, nor, idx, _d = tree.ray_cast(Vector((x, y, z)), DOWN, 1000.0)
            if loc is None:
                break
            found.append((loc.z, nor.z, idx))
            z = loc.z - 0.02
        return found

    n, cell = int(radius / step), step * step
    for ix in range(-n, n + 1):
        for iy in range(-n, n + 1):
            if ix * ix + iy * iy > n * n:
                continue
            x, y = centre.x + ix * step, centre.y + iy * step
            seen = [h for h in column(vis, x, y) if abs(h[1]) > 0.35]         # floors and ramps, not walls
            if not seen:
                continue
            solid_z = [h[0] for h in column(sol, x, y)] if sol is not None else []
            for z, _nz, idx in seen:
                rec = out.setdefault(vis_owner[idx], [0.0, 0.0, 0.0, None])
                rec[0] += cell
                gap = min((abs(z - s) for s in solid_z), default=None)
                if gap is None or gap > tolerance:
                    rec[1] += cell
                    rec[2] = max(rec[2], gap if gap is not None else 999.0)
                    rec[3] = rec[3] or (x, y, z)
    return out


def check_seen_vs_solid(scene, depsgraph, radius=150.0, step=0.5, minimum_m2=1.5):
    """Drawn floors and ramps you would ride or fall straight through, because nothing solid sits where they are drawn."""
    table = seen_vs_solid(scene, depsgraph, radius, step)
    rows = [(rec[1], name, rec) for name, rec in table.items()
            if rec[1] >= minimum_m2 and not SCENERY.search(name) and not is_solid(scene.objects[name])]
    rows.sort(reverse=True)
    if not rows:
        return [finding("solid", "ok", "Every drawn floor and ramp within %.0f m has something solid where it is drawn." % radius)]
    out = [finding("solid", "problem", "%d drawn pieces are not solid where you see them (%.0f m2 in all). "
                                       "Use 'Make drawn pieces solid'." % (len(rows), sum(r[0] for r in rows)))]
    for bad, name, rec in rows[:40]:
        gap = "nothing solid under it at all" if rec[2] >= 999.0 else "solid is %.2f m away" % rec[2]
        out.append(finding("solid", "problem", "%s: %.0f of %.0f m2 not solid (%s)" % (name, bad, rec[0], gap), rec[3]))
    return out


def fix_seen_vs_solid(scene, depsgraph, radius=150.0, step=0.5, minimum_m2=1.5, minimum_share=0.25, tolerance=0.15):
    """Gives collision to the drawn pieces check_seen_vs_solid reports. Scenery (backdrops, water, sky) is left alone.
    A piece that is mostly unsupported becomes solid as a whole, from its own drawn mesh. A piece that is only
    partly unsupported (an edge that hangs past its collision) keeps its collision as it is, and just its
    unsupported faces are copied into one invisible solid patch. Returns the objects changed or made."""
    table = seen_vs_solid(scene, depsgraph, radius, step, tolerance=tolerance)
    changed, partial = [], []
    for name, rec in table.items():
        obj = scene.objects.get(name)
        if obj is None or SCENERY.search(name) or is_solid(obj) or rec[1] < minimum_m2:
            continue
        if rec[1] >= minimum_share * rec[0]:
            settings = getattr(obj, "sk8_object", None)
            if settings is not None:
                settings.collision_mode = "triangle_mesh"
                changed.append(obj)
        else:
            partial.append(obj)
    if partial:
        patch = _patch_unsupported_faces(scene, depsgraph, partial, tolerance)
        if patch is not None:
            changed.append(patch)
    return changed


def _patch_unsupported_faces(scene, depsgraph, objects, tolerance):
    """One invisible solid mesh made of the up-facing faces of `objects` that have a spot with nothing solid within
    `tolerance` metres above or below it. Each face is sampled about every half metre, the same test the check uses."""
    solid_tree, _ = _world_tree(scene, depsgraph, lambda o, m: is_solid(o))
    lift = Vector((0.0, 0.0, tolerance))

    def supported(p):
        return solid_tree is not None and solid_tree.ray_cast(p + lift, DOWN, 2.0 * tolerance)[0] is not None

    def samples_of(corners):
        centre = sum(corners, Vector()) / len(corners)
        yield centre
        for a, b in zip(corners, corners[1:] + corners[:1]):          # a fan of triangles around the centre
            n = max(1, min(12, int(math.ceil(math.sqrt(((a - centre).cross(b - centre)).length * 0.5 / 0.25)))))
            for i in range(n + 1):
                for j in range(n + 1 - i):
                    u, v = i / n, j / n
                    p = centre + (a - centre) * u + (b - centre) * v
                    yield centre + (p - centre) * 0.97                  # just inside the edge, not on it

    verts, faces = [], []
    for obj in objects:
        me, mw = obj.data, obj.matrix_world
        rot = mw.to_3x3()
        world = None
        for poly in me.polygons:
            mat = me.materials[poly.material_index] if poly.material_index < len(me.materials) else None
            if not _material_drawn(mat) or abs((rot @ poly.normal).normalized().z) <= 0.35:
                continue
            if world is None:
                world = [mw @ v.co for v in me.vertices]
            corners = [world[i] for i in poly.vertices]
            if all(supported(p) for p in samples_of(corners)):
                continue                                   # something solid already sits under all of this face
            base = len(verts)
            verts += [tuple(c) for c in corners]
            faces.append(tuple(range(base, base + len(corners))))
    if not faces:
        return None
    me = bpy.data.meshes.new("Seen-not-solid patch")
    me.from_pydata(verts, [], faces)
    me.update()
    mat = bpy.data.materials.new("Invisible seen-not-solid patch")
    ms = getattr(mat, "sk8_material", None)
    if ms is not None:                                      # ReSkate Studio: invisible in game, still solid
        for name, value in (("invisible", True), ("cast_shadows", False), ("exclude_from_edge_generation", True),
                            ("exclude_from_grinding", True)):
            if hasattr(ms, name):
                setattr(ms, name, value)
    me.materials.append(mat)
    patch = bpy.data.objects.new("col_seen_patch", me)
    scene.collection.objects.link(patch)
    patch.display_type = "WIRE"                             # an outline in Blender, so it is clearly a helper
    so = getattr(patch, "sk8_object", None)
    if so is not None:
        so.collision_mode = "triangle_mesh"
    return patch


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
        if kind == "pedestrian":
            off = [p for p in pts if ride_height(scene, depsgraph, p.x, p.y, p.z + 1.5, 4.0) is None]
        else:                                               # vehicles sit on the route: more than 4 m of nothing is mid-air
            off = [p for p in pts if (lambda d: d is None or d > 4.0)(_drop_below(scene, depsgraph, p, 4.5))]
        problems = []
        if kind == "pedestrian" and closed:
            problems.append("closed loop: walkers appear and vanish beside the player; use an open path")
        if samples > 2:
            problems.append("about %d spawn points on %.0f m: set spacing near the route length for one" % (samples, length))
        if off and kind != "pedestrian":
            # a vehicle is placed on its route: with nothing solid under it, it starts in mid-air and drops
            drops = [d for d in (_drop_below(scene, depsgraph, p) for p in off) if d is not None]
            problems.append("%d of %d points have nothing solid under them%s: vehicles start in the air there. "
                            "Use 'Add deck under routes'" % (len(off), len(pts), (", up to %.0f m above the ground" % max(drops)) if drops else ""))
        elif off:
            problems.append("%d of %d points are not over solid ground" % (len(off), len(pts)))
        if sp is not None and min((p - sp).length for p in pts) < 12.0:
            problems.append("passes within 12 m of the player start")
        if problems:
            out.append(finding("routes", "problem", "%s (%s): %s" % (obj.name, kind, "; ".join(problems)), off[0] if off else pts[0]))
    if not seen_any:
        return [finding("routes", "ok", "No NPC routes in this scene (or ReSkate Studio's add-on is not enabled).")]
    if pedestrians > 3:
        out.append(finding("routes", "look", "%d pedestrian routes: more than 3 on one map costs frame rate on slower PCs." % pedestrians))
    return out or [finding("routes", "ok", "No route problems found.")]


def _drop_below(scene, depsgraph, p, depth=80.0):
    """Distance from p down to the first solid surface, or None when there is none."""
    for z, obj, _nz in _hits_below(scene, depsgraph, p.x, p.y, p.z + 0.5, depth, 12):
        if is_solid(obj):
            return p.z - z
    return None


def add_route_support(scene, depsgraph, routes=None, reach=4.0):
    """Lays an invisible solid deck under the stretches of vehicle routes that have nothing solid within `reach`
    metres below them (an elevated track drawn as thin rails, a gap in a road). Nothing is removed.
    Returns a list of (route name, points fixed, new object)."""
    made = []
    if routes is None:
        routes = [o for o in scene.objects if o.type == "CURVE" and getattr(o, "sk8_npc_route", None) is not None
                  and o.sk8_npc_route.enabled and str(o.sk8_npc_route.kind) != "pedestrian"]
    for obj in routes:
        if obj.type != "CURVE":
            continue
        pts, closed = [], False
        for spline in obj.data.splines:
            closed = closed or bool(spline.use_cyclic_u)
            src = spline.bezier_points if spline.type == "BEZIER" else spline.points
            pts += [obj.matrix_world @ Vector(p.co[:3]) for p in src]
        n = len(pts)
        if n < 2:
            continue
        bad = []
        for p in pts:
            d = _drop_below(scene, depsgraph, p, reach + 0.5)
            bad.append(d is None or d > reach)
        if not any(bad):
            continue
        route = getattr(obj, "sk8_npc_route", None)
        half = max(float(getattr(route, "width", 3.2) or 3.2), 3.2) / 2.0 + 0.6
        verts, faces = [], []
        for i in range(n):
            a = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
            b = pts[(i + 1) % n] if closed else pts[min(i + 1, n - 1)]
            t = b - a
            t.z = 0.0
            side = Vector((t.y, -t.x, 0.0)).normalized() if t.length > 1e-6 else Vector((1.0, 0.0, 0.0))
            low = Vector((0.0, 0.0, 0.03))
            verts += [tuple(pts[i] + side * half - low), tuple(pts[i] - side * half - low)]
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            if bad[i] or bad[j]:
                faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
        if not faces:
            continue
        me = bpy.data.meshes.new("Route support deck " + obj.name)
        me.from_pydata(verts, [], faces)
        me.update()
        if sum(p.normal.z for p in me.polygons) < 0.0:
            me.flip_normals()
        mat = bpy.data.materials.new("Invisible route support")
        ms = getattr(mat, "sk8_material", None)
        if ms is not None:                                  # ReSkate Studio: invisible in game, still solid
            for name, value in (("invisible", True), ("cast_shadows", False), ("exclude_from_edge_generation", True),
                                ("exclude_from_grinding", True)):
                if hasattr(ms, name):
                    setattr(ms, name, value)
        me.materials.append(mat)
        deck = bpy.data.objects.new("Route support " + obj.name, me)
        scene.collection.objects.link(deck)
        deck.display_type = "WIRE"                          # shows as an outline in Blender so it is clearly a helper
        so = getattr(deck, "sk8_object", None)
        if so is not None:
            so.collision_mode = "triangle_mesh"
        made.append((obj.name, sum(bad), deck))
    return made


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
SAFE_IMAGE_TYPES = (".png", ".dds")


def _jpeg_info(path):
    """(components, progressive) from a JPEG file's header, or None. 4 components = CMYK, which many tools cannot use."""
    try:
        with open(path, "rb") as f:
            data = f.read(1 << 20)
    except OSError:
        return None
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            return data[i + 9], marker == 0xC2
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def _used_images(scene):
    """{image: [material names]} for every image texture in a material that a mesh in the scene uses."""
    used = {}
    mats = {m for o in scene.objects if o.type == "MESH" for m in o.data.materials if m is not None}

    def walk(tree, mat, seen):
        if tree is None or tree in seen:
            return
        seen.add(tree)
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image is not None:
                used.setdefault(node.image, []).append(mat.name)
            elif node.bl_idname == "ShaderNodeGroup":
                walk(node.node_tree, mat, seen)
    for mat in mats:
        walk(mat.node_tree, mat, set())
    return used


def image_problem(img):
    """Why this image would reach the map compiler empty, or None when it is fine. Returns (level, text)."""
    import os
    if img.source in ("GENERATED",) or (not img.filepath and img.packed_file is None):
        if img.is_dirty or not img.filepath:
            return "problem", "made inside Blender and never saved to a file: it will be empty in the build"
    if img.source in ("MOVIE", "SEQUENCE", "TILED"):
        return "look", "is a %s image: only single still images are safe" % img.source.lower()
    path = bpy.path.abspath(img.filepath, library=img.library) if img.filepath else ""
    if img.packed_file is None and img.source == "FILE":
        if not path or not os.path.isfile(path):
            return "problem", "file not found: %s" % (img.filepath or "(no path)")
        if os.path.getsize(path) == 0:
            return "problem", "file is empty (0 bytes): %s" % os.path.basename(path)
        if path.lower().endswith((".jpg", ".jpeg", ".jpe")):
            info = _jpeg_info(path)
            if info is None:
                return "problem", "has a .jpg name but is not a readable JPEG file (renamed or damaged?)"
            if info[0] == 4:
                return "problem", "is a CMYK JPEG (a print format): re-save it as RGB"
    try:
        w, h = int(img.size[0]), int(img.size[1])       # asking for the size makes Blender load the file
    except Exception:
        w = h = 0
    if w <= 0 or h <= 0 or int(getattr(img, "channels", 0)) <= 0:
        return "problem", "Blender cannot read any pixels from it (unsupported or damaged file)"
    if not bpy.data.filepath and img.filepath.startswith("//"):
        return "look", "has a path relative to a .blend that is not saved yet"
    ext = os.path.splitext(path)[1].lower() if path else ""
    if img.packed_file is None and ext not in SAFE_IMAGE_TYPES:
        # ReSkate Studio 2.11 copies .png and .dds files into the build as they are. Every other type is converted
        # during the build, and that conversion fails ("does not have any image data") whenever Blender has not
        # already loaded the picture into memory, so the same file builds one day and not the next.
        return "look", "is a %s file: the build has to convert it, which fails at random. Save it as PNG" % (ext or "non-PNG")
    return None


def check_textures(scene):
    """Images that would arrive empty at the map compiler ('image has no data / no pixels')."""
    used = _used_images(scene)
    out, bad = [], 0
    for img, mats in sorted(used.items(), key=lambda t: t[0].name.lower()):
        problem = image_problem(img)
        if problem is None:
            continue
        bad += problem[0] == "problem"
        out.append(finding("textures", problem[0], "%s %s (used by %s)" % (
            img.name, problem[1], ", ".join(sorted(set(mats))[:3]) + ("..." if len(set(mats)) > 3 else ""))))
    jpgs = sum(1 for img in used if img.filepath.lower().endswith((".jpg", ".jpeg")))
    if not out:
        return [finding("textures", "ok", "%d textures in use, all readable PNG or DDS files." % len(used))]
    return [finding("textures", "problem" if bad else "look",
                    "%d of %d textures in use will not build as they are. 'Fix textures' repairs what it can." % (len(out), len(used)))] + out


def fix_textures(scene, folder_name="porterino_textures"):
    """Writes every readable texture in use as a PNG in a folder next to the .blend and points the materials at it,
    so the build no longer depends on JPEG variants, far-away folders or unsaved images.
    Returns (fixed, still_broken) where still_broken is a list of (image name, reason)."""
    import os
    if not bpy.data.filepath:
        return 0, [("(file)", "save the .blend first, so the textures have somewhere to live")]
    folder = os.path.join(os.path.dirname(bpy.data.filepath), folder_name)
    os.makedirs(folder, exist_ok=True)
    fixed, broken, taken = 0, [], set()
    for img in _used_images(scene):
        if img.source in ("MOVIE", "SEQUENCE", "TILED"):
            continue
        try:
            w, h = int(img.size[0]), int(img.size[1])
        except Exception:
            w = h = 0
        if w <= 0 or h <= 0:
            problem = image_problem(img)
            broken.append((img.name, problem[1] if problem else "no pixels"))
            continue
        stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in os.path.splitext(img.name)[0]) or "texture"
        name, k = stem, 1
        while name.lower() in taken:
            k += 1
            name = "%s_%d" % (stem, k)
        taken.add(name.lower())
        target = os.path.join(folder, name + ".png")
        current = bpy.path.abspath(img.filepath) if img.filepath else ""
        if (img.packed_file is None and img.source == "FILE" and not img.is_dirty and os.path.isfile(current)
                and os.path.splitext(current)[1].lower() in SAFE_IMAGE_TYPES):
            continue                                        # already a PNG or DDS file on disk: nothing to do
        try:
            _ = img.pixels[0]                               # make Blender load the picture before it is written out
            old_format = img.file_format
            img.file_format = "PNG"
            try:
                img.save(filepath=target, save_copy=True)   # writes the PNG, leaves this image pointing where it was
            finally:
                img.file_format = old_format
            if not os.path.isfile(target) or os.path.getsize(target) == 0:
                raise RuntimeError("no file was written")
        except Exception as ex:
            broken.append((img.name, "could not be written: %s" % str(ex).strip()))
            continue
        if img.packed_file is not None:
            img.unpack(method="REMOVE")
        img.source = "FILE"
        img.filepath = bpy.path.relpath(target)
        img.file_format = "PNG"
        img.reload()
        fixed += 1
    return fixed, broken


# ---------------------------------------------------------------------------------------------------------------
# Materials: why a piece builds without its texture.
# The map build reads ONE thing for a material's picture: the Base Color input of its Principled BSDF. A texture
# reaches the game when an Image Texture is wired straight into it. Anything in between is baked if the mesh has a
# UV map, and otherwise replaced by the plain colour of the socket. A material with no Principled BSDF, or a mesh
# with no UV map, comes out as one flat colour however good it looks in Blender.
DATA_MAP = re.compile(r"normal|nrm|_nor|_n\b|rough|rgh|metal|mtl|spec|gloss|_ao\b|occlusion|height|disp|bump|opacity|alpha|mask|emis|orm\b", re.I)


def _upstream(socket):
    """(node, output socket) feeding this input, looking through reroutes; (None, None) when nothing is linked."""
    for _ in range(64):
        if socket is None or not socket.is_linked:
            return None, None
        link = socket.links[0]
        if link.from_node.type != "REROUTE":
            return link.from_node, link.from_socket
        socket = link.from_node.inputs[0]
    return None, None


def _find_principled(mat):
    """The shader the build reads: the Principled BSDF reached from the Material Output, else any one in the tree."""
    tree = mat.node_tree
    if tree is None:
        return None
    outputs = sorted((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), key=lambda n: (not n.is_active_output, n.name))
    stack, seen = [], set()
    for out in outputs:
        surface = out.inputs.get("Surface")
        if surface is not None and surface.is_linked:
            stack += [link.from_node for link in surface.links]
    while stack:
        node = stack.pop(0)
        if node.name in seen:
            continue
        seen.add(node.name)
        if node.type == "BSDF_PRINCIPLED":
            return node
        for s in node.inputs:
            stack += [link.from_node for link in s.links]
    return next((n for n in sorted(tree.nodes, key=lambda n: n.name) if n.type == "BSDF_PRINCIPLED"), None)


def _image_behind(socket):
    """The nearest Image Texture node (with a picture) upstream of a socket, or None."""
    stack = [link.from_node for link in socket.links] if socket is not None and socket.is_linked else []
    seen = set()
    while stack and len(seen) < 300:
        node = stack.pop(0)
        if node.name in seen:
            continue
        seen.add(node.name)
        if node.type == "TEX_IMAGE" and node.image is not None:
            return node
        for s in node.inputs:
            stack += [link.from_node for link in s.links]
    return None


def _colour_image_node(tree):
    """The Image Texture in a material most likely to be its colour picture (not a normal, roughness or mask map)."""
    nodes = [n for n in tree.nodes if n.type == "TEX_IMAGE" and n.image is not None]
    if not nodes:
        return None

    def score(n):
        name = n.image.name + " " + n.name + " " + n.label
        data = bool(DATA_MAP.search(name)) or n.image.colorspace_settings.name.lower() in ("non-color", "raw")
        named = bool(re.search(r"diff|albedo|base|col|color|colour", name, re.I))
        return (data, not named, n.name)
    return sorted(nodes, key=score)[0]


def material_problem(mat):
    """Why this material would build as a flat colour, or None when its texture reaches the game.
    Returns (level, text, kind); kind names the repair fix_materials can make, or None."""
    tree = mat.node_tree
    if tree is None:
        return "problem", "has no node setup: the build cannot read a texture from it", None
    bsdf = _find_principled(mat)
    picture = _colour_image_node(tree)
    if bsdf is None:
        shaders = sorted({n.bl_label for n in tree.nodes if n.type.startswith("BSDF") or n.type in (
            "EMISSION", "MIX_SHADER", "ADD_SHADER", "GROUP", "EEVEE_SPECULAR")}) or ["no shader"]
        return ("problem", "has no Principled BSDF (it uses %s). The build reads only Principled, so it comes out as a "
                           "flat colour" % ", ".join(shaders[:3]), "no_principled" if picture else None)
    base = bsdf.inputs.get("Base Color")
    if base is None:
        return None
    node, _out = _upstream(base)
    if node is None:
        if picture is not None:
            return ("look", "has a picture (%s) that is not connected to Base Color, so it builds as a flat colour"
                    % picture.image.name, "unlinked")
        return None                                         # a plain colour on purpose
    if node.type == "TEX_IMAGE":
        if node.image is None:
            return "problem", "its Image Texture node has no picture chosen", None
        vnode, vout = _upstream(node.inputs.get("Vector"))
        if vnode is not None and vnode.type == "TEX_COORD" and vout is not None and vout.name != "UV":
            return ("look", "places its picture by '%s' coordinates. The build only uses the UV map, so it will sit "
                            "differently in game" % vout.name, None)
        if vnode is not None and vnode.type == "MAPPING":
            return ("look", "uses a Mapping node (scale, offset or rotation). The build uses the plain UV map, so the "
                            "picture may be a different size in game: apply the scale to the UVs instead", None)
        return None
    behind = _image_behind(base)
    what = ("the node group '%s'" % node.node_tree.name) if node.type == "GROUP" and node.node_tree else "a %s node" % node.bl_label
    if behind is not None:
        if node.type in ("MIX", "MIX_RGB") and str(getattr(node, "blend_type", "")) == "MULTIPLY":
            return None                                     # a picture multiplied by a colour is carried across
        return ("look", "Base Color goes through %s before it reaches the picture (%s). The build tries to bake that and "
                        "falls back to a flat colour when it cannot" % (what, behind.image.name), "indirect")
    if picture is not None:
        return ("look", "Base Color comes from %s; its picture (%s) sits where the build cannot follow"
                % (what, picture.image.name), "indirect")
    return ("look", "Base Color comes from %s with no picture behind it (a procedural colour). It is baked only when "
                    "the mesh has a UV map" % what, None)


def _material_users(scene):
    """{material: [objects]} for mesh objects in the scene."""
    users = {}
    for obj in scene.objects:
        if obj.type == "MESH":
            for mat in obj.data.materials:
                if mat is not None:
                    users.setdefault(mat, []).append(obj)
    return users


def check_materials(scene):
    """Pieces that will build as a flat colour: no UV map, no Principled BSDF, or a picture the build cannot follow."""
    out, bad = [], 0
    users = _material_users(scene)
    for mat, objs in sorted(users.items(), key=lambda t: t[0].name.lower()):
        problem = material_problem(mat)
        if problem is None:
            continue
        bad += problem[0] == "problem"
        names = sorted({o.name for o in objs})
        out.append(finding("materials", problem[0], "Material '%s' %s. Used by %s%s" % (
            mat.name, problem[1], ", ".join(names[:3]), "..." if len(names) > 3 else ""), objs[0].matrix_world.translation))
    for obj in scene.objects:
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        me = obj.data
        textured = [m for m in me.materials if m is not None and m.node_tree is not None and _colour_image_node(m.node_tree)]
        if textured and not me.uv_layers:
            bad += 1
            out.append(finding("materials", "problem", "%s has no UV map, so its picture cannot be placed and it builds as "
                                                       "one flat colour. 'Fix materials' gives it one" % obj.name,
                               obj.matrix_world.translation))
        if not [m for m in me.materials if m is not None]:
            out.append(finding("materials", "look", "%s has no material: it builds in plain grey" % obj.name,
                               obj.matrix_world.translation))
        if obj.library is not None or me.library is not None:
            out.append(finding("materials", "look", "%s is linked from another .blend. Make it local (Object > Relations > "
                                                    "Make Local > All) so it is built into the map" % obj.name,
                               obj.matrix_world.translation))
    if not out:
        return [finding("materials", "ok", "%d materials checked: every picture is wired where the build can read it." % len(users))]
    return [finding("materials", "problem" if bad else "look",
                    "%d thing(s) will build without their picture. 'Fix materials' repairs what it can." % len(out))] + out


def fix_materials(scene, context=None):
    """Repairs what check_materials reports, where it safely can:
    wires the colour picture straight into Base Color, builds a Principled BSDF for materials that have none, and
    adds a UV map (Smart UV Project) to textured meshes that have none.
    Returns (materials rewired, meshes given UVs, [(name, reason)] left for a person)."""
    rewired, left = 0, []
    for mat in _material_users(scene):
        problem = material_problem(mat)
        if problem is None:
            continue
        kind = problem[2]
        tree = mat.node_tree
        if kind is None or tree is None:
            if problem[0] == "problem":
                left.append((mat.name, problem[1]))
            continue
        picture = _colour_image_node(tree)
        bsdf = _find_principled(mat)
        if kind == "no_principled":
            bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
            out = next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None) or \
                next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or tree.nodes.new("ShaderNodeOutputMaterial")
            bsdf.location = (out.location.x - 300, out.location.y)
            tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        elif kind == "indirect":
            picture = _image_behind(bsdf.inputs["Base Color"]) or picture
        if picture is None or bsdf is None:
            left.append((mat.name, problem[1]))
            continue
        tree.links.new(picture.outputs["Color"], bsdf.inputs["Base Color"])
        rewired += 1
    unwrapped = 0
    if context is not None:
        need = [o for o in scene.objects if o.type == "MESH" and o.data.polygons and not o.data.uv_layers and
                any(m is not None and m.node_tree is not None and _colour_image_node(m.node_tree) for m in o.data.materials)]
        done_meshes = set()
        for obj in need:
            if obj.data.name in done_meshes or obj.data.library is not None:
                continue
            done_meshes.add(obj.data.name)
            try:
                for o in context.view_layer.objects:
                    o.select_set(False)
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project()
                bpy.ops.object.mode_set(mode="OBJECT")
                unwrapped += 1
            except Exception as ex:
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception:
                    pass
                left.append((obj.name, "could not be given a UV map: %s" % str(ex).strip()[:80]))
    return rewired, unwrapped, left


# ---------------------------------------------------------------------------------------------------------------
# Surfaces: why a piece makes the wrong sound.
# In ReSkate Studio every object and every material has a "Base Surface / Audio Donor". The MATERIAL's choice wins
# over the object's, and a piece nobody set uses the generic default. So a plywood ramp sounds like concrete either
# because nothing was chosen, or because its material carries a choice that beats the one made on the object.
SURFACE_HINTS = (("Wood", r"wood|ply|plank|timber|lumber|pallet|crate|deck(?!al)"), ("Metal", r"metal|steel|iron|alumin|car\b|wreck|vehicle|pipe|rail|barrel|drum|dumpster"),
                 ("Plastic", r"plastic|bin\b|trash|garbage|rubbish|bag\b|cone|barrier"), ("Cardboard", r"cardboard|carton|box\b"),
                 ("Concrete", r"concrete|cement|curb|kerb|slab|pavement"), ("Asphalt", r"asphalt|tarmac|road"),
                 ("Brick", r"brick"), ("Glass", r"glass|window"), ("Grass", r"grass|lawn|hedge"), ("Earth", r"dirt|soil|mud|earth"),
                 ("Gravel", r"gravel"), ("Sand", r"sand\b"), ("Rubber", r"rubber|tyre|tire"))


def surface_choices(owner="Object"):
    """[(identifier, label)] of the surfaces ReSkate Studio offers, without the clothing ones; [] without its add-on."""
    group = getattr(bpy.types, owner).bl_rna.properties.get("sk8_object" if owner == "Object" else "sk8_material")
    prop = group.fixed_type.properties.get("collision_material") if group is not None else None
    if prop is None:
        return []
    rows, seen = [], set()
    for e in prop.enum_items:
        label = re.sub(r"^\d+\s*-\s*", "", e.name).strip()
        # keep the plain surfaces: not the clothing ones, and not the "X + Y behavior" variants
        if label in seen or " + " in label or re.match(r"Clothing|Footwear|Native material|Camera|Wipeout|Jump Pad", label) \
                or re.search(r"surface$", label):
            continue
        seen.add(label)
        rows.append((e.identifier, label))
    return sorted(rows, key=lambda r: (r[1] != "Default", r[1]))


def _chosen_surface(owner, group):
    """The surface identifier explicitly chosen on an object or material, or None when it was never set."""
    settings = getattr(owner, group, None)
    if settings is None:
        return None
    try:
        return settings.collision_material if settings.is_property_set("collision_material") else None
    except Exception:
        return None


def check_surfaces(scene):
    """Solid pieces that will make the wrong sound: no surface chosen, a material that overrides the object's
    choice, or a name that says wood while the surface says something else."""
    all_labels = {}
    group = bpy.types.Object.bl_rna.properties.get("sk8_object")
    if group is not None and group.fixed_type.properties.get("collision_material") is not None:
        all_labels = {e.identifier: re.sub(r"^\d+\s*-\s*", "", e.name).strip()
                      for e in group.fixed_type.properties["collision_material"].enum_items}
    if not all_labels:
        return [finding("surfaces", "ok", "ReSkate Studio's add-on is not enabled, so surfaces cannot be read.")]
    out, unset = [], []
    for obj in scene.objects:
        if obj.type != "MESH" or not is_solid(obj) or not obj.data.polygons:
            continue
        on_object = _chosen_surface(obj, "sk8_object")
        mats = [m for m in obj.data.materials if m is not None]
        on_mats = {m.name: _chosen_surface(m, "sk8_material") for m in mats}
        if any(getattr(m.sk8_material, "invisible", False) for m in mats if hasattr(m, "sk8_material")) and len(mats) == 1:
            continue                                        # an invisible collider: its sound is whatever was set
        effective = [s or on_object for s in on_mats.values()] or [on_object]
        overriding = [(n, s) for n, s in on_mats.items() if s is not None and on_object is not None and s != on_object]
        if overriding:
            n, s = overriding[0]
            out.append(finding("surfaces", "problem", "%s is set to %s, but its material '%s' is set to %s and the material "
                                                      "wins. 'Set surface on selected' sets both" % (
                                                          obj.name, all_labels.get(on_object, on_object), n, all_labels.get(s, s)),
                               obj.matrix_world.translation))
            continue
        if all(s is None for s in effective):
            unset.append(obj)
            continue
        text = " ".join([obj.name, obj.data.name] + [m.name for m in mats])
        guess = next((label for label, pattern in SURFACE_HINTS if re.search(pattern, text, re.I)), None)
        have = {all_labels.get(s, "Default") for s in effective if s is not None}
        if guess and have and not any(guess.lower() in h.lower() for h in have):
            out.append(finding("surfaces", "look", "%s is named like %s but its surface is %s" % (
                obj.name, guess.lower(), ", ".join(sorted(have))), obj.matrix_world.translation))
    if unset:
        hinted = []
        for obj in unset:
            text = " ".join([obj.name, obj.data.name] + [m.name for m in obj.data.materials if m is not None])
            guess = next((label for label, pattern in SURFACE_HINTS if re.search(pattern, text, re.I)), None)
            if guess and guess not in ("Concrete",):
                hinted.append((obj, guess))
        out.insert(0, finding("surfaces", "look", "%d solid piece(s) have no surface chosen, so they all sound like the "
                                                  "generic default: %s%s" % (len(unset), ", ".join(o.name for o in unset[:6]),
                                                                             "..." if len(unset) > 6 else "")))
        for obj, guess in hinted[:30]:
            out.append(finding("surfaces", "look", "%s has no surface chosen and is named like %s" % (obj.name, guess.lower()),
                               obj.matrix_world.translation))
    return out or [finding("surfaces", "ok", "Every solid piece has a surface chosen and no material overrides its object.")]


def set_surface(objects, identifier, also_materials=True):
    """Chooses one surface for the given objects, and for their materials too so nothing overrides it.
    Returns (objects set, materials set). A material shared with other pieces changes for them as well."""
    n_obj, done = 0, set()
    for obj in objects:
        settings = getattr(obj, "sk8_object", None)
        if obj.type != "MESH" or settings is None:
            continue
        settings.collision_material = identifier
        n_obj += 1
        if also_materials:
            for mat in obj.data.materials:
                ms = getattr(mat, "sk8_material", None) if mat is not None else None
                if ms is not None and mat.name not in done:
                    ms.collision_material = identifier
                    done.add(mat.name)
    return n_obj, len(done)


# ---------------------------------------------------------------------------------------------------------------
TIME_FLAGS ={"morning": 1, "noon": 2, "afternoon": 4, "evening": 8, "night": 16, "weatherday": 32, "weathernight": 64}


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
    """Scale map about the world origin, keeping lights looking the same and markers their real size."""
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
