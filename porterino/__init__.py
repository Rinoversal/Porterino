# Porterino: the ReSkate Map Toolkit. A Blender add-on that checks a map against how skate. plays
# (holes, ramp lips, bowl transitions, NPC routes, lights) and rebuilds it into the game with one button.
# Install: Edit > Preferences > Add-ons > Install from Disk > pick the porterino zip. Panel: 3D view, N key, "Porterino" tab.
bl_info = {
    "name": "Porterino: ReSkate Map Toolkit",
    "author": "Carterino",
    "version": (0, 4, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar (N) > Porterino",
    "description": "Check a map against skate. physics and rebuild it into the game with one button",
    "category": "3D View",
}

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, StringProperty)

from . import checks, library, rebuild

ICONS = {"problem": "ERROR", "look": "INFO", "ok": "CHECKMARK"}


class PorterinoFinding(bpy.types.PropertyGroup):
    check: StringProperty()
    level: StringProperty()
    text: StringProperty()
    has_location: BoolProperty()
    location: FloatVectorProperty(size=3)


_category_items = []          # Blender needs the strings of a dynamic dropdown kept alive


def _categories(self, context):
    global _category_items
    names = sorted(library.pieces_for(self.library_folder)) or ["(no pieces found)"]
    _category_items = [(n, n, "") for n in names]
    return _category_items


_surface_items = []


def _surfaces(self, context):
    global _surface_items
    rows = checks.surface_choices("Object") or [("none", "(ReSkate Studio add-on not enabled)")]
    _surface_items = [(i, label, "") for i, label in rows]
    return _surface_items


class PorterinoSettings(bpy.types.PropertyGroup):
    surface_choice: EnumProperty(name="Surface", items=_surfaces,
                                 description="The surface the selected pieces should sound and behave like")
    surface_materials: BoolProperty(name="Also set its materials", default=True,
                                    description="A material's own surface beats the object's. Leave this on so nothing overrides "
                                                "your choice. A material shared with other pieces changes for them too")
    library_folder: StringProperty(name="Parts folder", subtype="DIR_PATH",
                                   description="A folder of pieces (.blend, .fbx, .obj). Sub-folders become categories")
    library_category: EnumProperty(name="Category", items=_categories)
    library_snap: FloatProperty(name="Snap (m)", default=0.0, min=0.0, max=10.0,
                                description="Round the placing position to this step. 0 = no snapping")
    hole_radius: FloatProperty(name="Radius (m)", default=150.0, min=10.0, max=3000.0,
                               description="How far from the player start (or the 3D cursor) to look for holes")
    lip_minimum: FloatProperty(name="Report from (cm)", default=3.5, min=1.0, max=8.0,
                               description="Smallest sharp step to report at the foot of a ramp")
    lips_selected_only: BoolProperty(name="Selected only", default=False,
                                     description="Check the selected meshes instead of finding ramps by name")
    bowl_lip_angle: FloatProperty(name="Lip at least (deg)", default=75.0, min=20.0, max=90.0,
                                  description="Flag a wall whose top is shallower than this. 90 is vertical")
    bowl_kink: FloatProperty(name="Facet turn at most (deg)", default=14.0, min=2.0, max=45.0,
                             description="Flag a curve where the angle jumps more than this between two strips")
    bowl_reach: FloatProperty(name="Look out to (m)", default=12.0, min=2.0, max=60.0,
                              description="How far from the cursor to look for walls")
    scale_factor: FloatProperty(name="Factor", default=0.8, min=0.1, max=10.0,
                                description="0.8 makes the whole map 80% of its size")
    light_range: FloatProperty(name="Range (m)", default=20.0, min=1.0, max=200.0)
    light_when: EnumProperty(name="On during", items=[
        ("always", "Always", "Indoor lights"),
        ("dark", "Evening and night", "Street lamps and signs"),
        ("night", "Night only", "")], default="dark")
    glow_power: FloatProperty(name="Power (W)", default=300.0, min=1.0, max=5000.0)
    time_of_day: EnumProperty(name="Time of day", items=[(t, t.title(), "") for t in
                                                          ("morning", "noon", "afternoon", "evening", "night")], default="noon")
    bake_lighting: BoolProperty(name="Bake lighting (slower)", default=False,
                                description="Off for quick test builds, ON for the build you release")
    open_sky: BoolProperty(name="Enclosed level", default=False,
                           description="Indoor or walled-in level: stops the skater being a black silhouette")
    launch_after: BoolProperty(name="Start the game after", default=True)
    auto_load: BoolProperty(name="Go straight into the map", default=True,
                            description="After the build the game opens directly in this map, skipping the menu")
    map_asset: StringProperty(name="Load command", default="",
                              description="Optional. A console line run at startup, for example: load levels/game/my_map/my_map. "
                                          "Leave empty to pick the map from the pause menu")
    findings: CollectionProperty(type=PorterinoFinding)
    finding_index: IntProperty()


class PorterinoPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    game_folder: StringProperty(name="Game folder", subtype="DIR_PATH",
                                description="The folder that holds ReSkateLauncher.exe and the Mods folder")
    studio_cli: StringProperty(name="reskate_cli.exe", subtype="FILE_PATH",
                               description="Inside your ReSkate Studio folder")
    staging_folder: StringProperty(name="Build folder", subtype="DIR_PATH",
                                   description="Any empty folder OUTSIDE the game folder. Build files go here")

    def draw(self, _context):
        col = self.layout.column()
        col.label(text="Only needed for the Rebuild button. The checks work without these.")
        col.prop(self, "game_folder")
        col.prop(self, "studio_cli")
        col.prop(self, "staging_folder")


def show(context, results, replace_check=None):
    s = context.scene.porterino
    keep = [(f.check, f.level, f.text, f.has_location, tuple(f.location)) for f in s.findings
            if replace_check is not None and f.check != replace_check]
    s.findings.clear()
    rows = keep + [(r["check"], r["level"], r["text"], r["location"] is not None, r["location"] or (0, 0, 0)) for r in results]
    for check, level, text, has, loc in rows:
        f = s.findings.add()
        f.check, f.level, f.text, f.has_location, f.location = check, level, text, has, loc
    text = bpy.data.texts.get("Porterino report") or bpy.data.texts.new("Porterino report")
    text.clear()
    for check, level, line, has, loc in rows:
        where = "  at X %.1f  Y %.1f  Z %.1f" % tuple(loc) if has else ""
        text.write("[%s] %-10s %s%s\n" % ({"problem": "PROBLEM", "look": "LOOK", "ok": "OK"}[level], check, line, where))
    return sum(1 for r in results if r["level"] != "ok")


class PorterinoCheck:
    """Shared run wrapper: object mode, wait cursor, result count in the status bar."""
    bl_options = {"REGISTER"}
    check_name = ""

    def measure(self, context, depsgraph):
        raise NotImplementedError

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.window.cursor_set("WAIT")
        try:
            results = self.measure(context, context.evaluated_depsgraph_get())
        finally:
            context.window.cursor_set("DEFAULT")
        n = show(context, results, self.check_name)
        self.report({"WARNING"} if n else {"INFO"}, "%d thing(s) to look at" % n if n else "Nothing found")
        return {"FINISHED"}


class PORTERINO_OT_floor(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_floor"
    bl_label = "Floor holes"
    bl_description = "Drawn floor with nothing solid under it, where the player falls through the map"
    check_name = "floor"

    def measure(self, context, depsgraph):
        return checks.check_floor_holes(context.scene, depsgraph, radius=context.scene.porterino.hole_radius)


class PORTERINO_OT_solid(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_solid"
    bl_label = "Seen but not solid"
    bl_description = ("Drawn floors and ramps with nothing solid where you see them: you ride or fall straight through. "
                      "For maps whose collision is a separate mesh, such as most ports")
    check_name = "solid"

    def measure(self, context, depsgraph):
        return checks.check_seen_vs_solid(context.scene, depsgraph, radius=context.scene.porterino.hole_radius)


class PORTERINO_OT_fix_solid(bpy.types.Operator):
    bl_idname = "porterino.fix_solid"
    bl_label = "Make drawn pieces solid"
    bl_description = "Gives collision to the drawn pieces that 'Seen but not solid' reports, using the drawn mesh itself"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        changed = checks.fix_seen_vs_solid(context.scene, context.evaluated_depsgraph_get(),
                                           radius=context.scene.porterino.hole_radius)
        self.report({"INFO"}, "%d piece(s) made solid" % len(changed) if changed else "Nothing needed fixing")
        return {"FINISHED"}


class PORTERINO_OT_lips(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_lips"
    bl_label = "Ramp lips"
    bl_description = "Sharp steps where the floor meets the foot of a ramp, bank, bowl or kicker"
    check_name = "lips"

    def measure(self, context, depsgraph):
        s = context.scene.porterino
        objects = list(context.selected_objects) if s.lips_selected_only else None
        return checks.check_ramp_lips(context.scene, depsgraph, objects, s.lip_minimum)


class PORTERINO_OT_transition(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_transition"
    bl_label = "Measure bowl / ramp"
    bl_description = "Select the bowl or ramp, put the 3D cursor on its flat bottom, then press this"
    check_name = "transition"

    def measure(self, context, depsgraph):
        s = context.scene.porterino
        return checks.check_transition(depsgraph, list(context.selected_objects), context.scene.cursor.location.copy(),
                                       reach=s.bowl_reach, min_lip_deg=s.bowl_lip_angle, max_kink_deg=s.bowl_kink)


class PORTERINO_OT_rim(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_rim"
    bl_label = "Check coping curve"
    bl_description = "Select the coping or grind curve: reports sharp turns and long straight segments"
    check_name = "rim"

    def measure(self, context, depsgraph):
        return checks.check_rim(list(context.selected_objects))


class PORTERINO_OT_routes(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_routes"
    bl_label = "NPC routes"
    bl_description = "NPC routes that pop in beside the player, spawn off the map or cost frame rate"
    check_name = "routes"

    def measure(self, context, depsgraph):
        return checks.check_routes(context.scene, depsgraph)


class PORTERINO_OT_lights(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_lights"
    bl_label = "Check lights"
    bl_description = "Lights with no range or time of day, hidden pieces that will not export, emission that the game ignores"
    check_name = "lights"

    def measure(self, context, depsgraph):
        return checks.check_lights(context.scene)


class PORTERINO_OT_textures(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_textures"
    bl_label = "Check textures"
    bl_description = ("Textures that would reach the build empty ('image has no data'): missing files, empty or damaged "
                      "JPEGs, CMYK JPEGs, images made in Blender and never saved")
    check_name = "textures"

    def measure(self, context, depsgraph):
        return checks.check_textures(context.scene)


class PORTERINO_OT_fix_textures(bpy.types.Operator):
    bl_idname = "porterino.fix_textures"
    bl_label = "Fix textures"
    bl_description = ("Saves every readable texture as a PNG in a 'porterino_textures' folder next to the .blend and points "
                      "the materials at it. Your original files are not changed")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        fixed, broken = checks.fix_textures(context.scene)
        show(context, checks.check_textures(context.scene), "textures")
        if broken:
            self.report({"WARNING"}, "%d texture(s) saved as PNG; %d still need you: %s" % (
                fixed, len(broken), "; ".join("%s (%s)" % b for b in broken[:3])))
        else:
            self.report({"INFO"}, "%d texture(s) saved as PNG next to the .blend. Save the file to keep the change" % fixed)
        return {"FINISHED"}


class PORTERINO_OT_materials(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_materials"
    bl_label = "Check materials"
    bl_description = ("Pieces that will build as a flat colour: no UV map, no Principled BSDF, or a picture that is not "
                      "wired straight into Base Color")
    check_name = "materials"

    def measure(self, context, depsgraph):
        return checks.check_materials(context.scene)


class PORTERINO_OT_fix_materials(bpy.types.Operator):
    bl_idname = "porterino.fix_materials"
    bl_label = "Fix materials"
    bl_description = ("Wires each colour picture straight into Base Color, gives materials without a Principled BSDF one, "
                      "and adds a UV map to textured meshes that have none. One Undo reverts it")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        rewired, unwrapped, left = checks.fix_materials(context.scene, context)
        show(context, checks.check_materials(context.scene), "materials")
        text = "%d material(s) rewired, %d mesh(es) given a UV map" % (rewired, unwrapped)
        if left:
            self.report({"WARNING"}, text + "; %d still need you: %s" % (len(left), "; ".join("%s (%s)" % (n, r[:60]) for n, r in left[:2])))
        else:
            self.report({"INFO"}, text)
        return {"FINISHED"}


class PORTERINO_OT_surfaces(PorterinoCheck, bpy.types.Operator):
    bl_idname = "porterino.check_surfaces"
    bl_label = "Check surface sounds"
    bl_description = ("Solid pieces that will make the wrong sound: no surface chosen, or a material whose own surface "
                      "overrides the one set on the object")
    check_name = "surfaces"

    def measure(self, context, depsgraph):
        return checks.check_surfaces(context.scene)


class PORTERINO_OT_set_surface(bpy.types.Operator):
    bl_idname = "porterino.set_surface"
    bl_label = "Set surface on selected"
    bl_description = "Chooses this surface for the selected pieces and, if ticked, for their materials so nothing overrides it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.porterino
        if s.surface_choice in ("", "none"):
            self.report({"ERROR"}, "Enable ReSkate Studio's Blender add-on first: the surfaces come from it")
            return {"CANCELLED"}
        picked = [o for o in context.selected_objects if o.type == "MESH"]
        if not picked:
            self.report({"ERROR"}, "Select the pieces first")
            return {"CANCELLED"}
        n_obj, n_mat = checks.set_surface(picked, s.surface_choice, s.surface_materials)
        self.report({"INFO"}, "Surface set on %d piece(s) and %d material(s)" % (n_obj, n_mat))
        return {"FINISHED"}


class PORTERINO_OT_all(bpy.types.Operator):
    bl_idname = "porterino.check_all"
    bl_label = "Run all checks"
    bl_description = "Floor holes, ramp lips, NPC routes and lights. Large maps can take a few minutes"

    def execute(self, context):
        context.scene.porterino.findings.clear()
        for op in (bpy.ops.porterino.check_floor, bpy.ops.porterino.check_lips, bpy.ops.porterino.check_routes,
                   bpy.ops.porterino.check_lights, bpy.ops.porterino.check_textures, bpy.ops.porterino.check_materials,
                   bpy.ops.porterino.check_surfaces):
            op()
        return {"FINISHED"}


class PORTERINO_OT_route_support(bpy.types.Operator):
    bl_idname = "porterino.route_support"
    bl_label = "Add deck under routes"
    bl_description = ("Lays an invisible solid deck under the parts of bus, train and car routes that have nothing solid "
                      "under them, so vehicles do not start in mid-air. Uses the selected routes, or all of them if none is selected")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        chosen = [o for o in context.selected_objects if o.type == "CURVE"] or None
        made = checks.add_route_support(context.scene, context.evaluated_depsgraph_get(), chosen)
        if not made:
            self.report({"INFO"}, "Every vehicle route already has solid ground under it")
        else:
            self.report({"INFO"}, "; ".join("%s: %d points decked" % (name, n) for name, n, _ in made))
        return {"FINISHED"}


class PORTERINO_OT_goto(bpy.types.Operator):
    bl_idname = "porterino.goto"
    bl_label = "Go to this spot"
    bl_description = "Move the 3D cursor to the finding and frame the view on it"
    index: IntProperty()

    def execute(self, context):
        f = context.scene.porterino.findings[self.index]
        if not f.has_location:
            return {"CANCELLED"}
        context.scene.cursor.location = f.location
        if context.area and context.area.type == "VIEW_3D":
            bpy.ops.view3d.view_center_cursor()
        return {"FINISHED"}


WHEN = {"always": ("morning", "noon", "afternoon", "evening", "night", "weatherday", "weathernight"),
        "dark": ("evening", "night", "weathernight"), "night": ("night", "weathernight")}


class PORTERINO_OT_set_lights(bpy.types.Operator):
    bl_idname = "porterino.set_lights"
    bl_label = "Set selected lights"
    bl_description = "Write the range and the times of day onto every selected light"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.porterino
        lights = [o for o in context.selected_objects if o.type == "LIGHT"]
        for obj in lights:
            checks.set_light(obj, s.light_range, WHEN[s.light_when])
        self.report({"INFO"}, "%d light(s) set" % len(lights))
        return {"FINISHED"}


class PORTERINO_OT_glow(bpy.types.Operator):
    bl_idname = "porterino.add_glow"
    bl_label = "Add glow light"
    bl_description = "Puts an Area light just in front of each selected sign or panel. This is how to make something look lit: emission is ignored by the game"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.porterino
        made = [checks.add_glow_light(context.scene, o, s.glow_power, 0.3, WHEN[s.light_when])
                for o in context.selected_objects if o.type == "MESH"]
        self.report({"INFO"}, "%d glow light(s) added. If one sits behind its sign, rotate it 180 degrees" % len([m for m in made if m]))
        return {"FINISHED"}


class PORTERINO_OT_scale(bpy.types.Operator):
    bl_idname = "porterino.scale_map"
    bl_label = "Scale map"
    bl_description = "Scales every object about the world origin and keeps lights, ranges and NPC routes matching. Save a copy first"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        n = checks.scale_map(context.scene, context.scene.porterino.scale_factor)
        self.report({"INFO"}, "%d objects scaled by %.2f" % (n, context.scene.porterino.scale_factor))
        return {"FINISHED"}


class PORTERINO_OT_rebuild(bpy.types.Operator):
    bl_idname = "porterino.rebuild"
    bl_label = "Rebuild and install"
    bl_description = "Saves this file, compiles it with ReSkate Studio in a separate window and installs it into the game's Mods folder"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        s = context.scene.porterino
        if not bpy.data.filepath:
            self.report({"ERROR"}, "Save the .blend first. The file name becomes the map's name in game")
            return {"CANCELLED"}
        bpy.ops.wm.save_mainfile()
        error = rebuild.start(
            blend=bpy.data.filepath, blender_exe=bpy.app.binary_path,
            game_folder=bpy.path.abspath(prefs.game_folder), studio_cli=bpy.path.abspath(prefs.studio_cli),
            staging_folder=bpy.path.abspath(prefs.staging_folder), time_of_day=s.time_of_day,
            bake=s.bake_lighting, open_sky=s.open_sky, launch=s.launch_after, startup_command=s.map_asset,
            auto_load=s.auto_load)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Build started in its own window. Blender stays usable")
        return {"FINISHED"}


class PORTERINO_OT_quick_test(bpy.types.Operator):
    bl_idname = "porterino.quick_test"
    bl_label = "Quick test: selected only"
    bl_description = ("Builds ONLY the selected objects as a small separate test map and opens the game in it. The skater "
                      "starts at the 3D cursor. Much faster than rebuilding the whole map; your real map is not touched")

    def execute(self, context):
        import os
        prefs = context.preferences.addons[__package__].preferences
        s = context.scene.porterino
        picked = [o for o in context.selected_objects if o.type in ("MESH", "CURVE", "LIGHT", "EMPTY")]
        if not any(o.type == "MESH" for o in picked):
            self.report({"ERROR"}, "Select the pieces to test first (include some floor to land on)")
            return {"CANCELLED"}
        staging = bpy.path.abspath(prefs.staging_folder)
        if not staging:
            self.report({"ERROR"}, "Set a build folder in Preferences > Add-ons > Porterino")
            return {"CANCELLED"}
        base = os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else "Untitled"
        folder = os.path.join(staging, "_quick_tests")
        os.makedirs(folder, exist_ok=True)
        base = base[:24].strip() or "Map"                    # short name: the build repeats it inside long paths
        target = os.path.join(folder, base + " QT.blend")
        # Save a copy of this file (your open file and its name are not changed), then let the build window strip the
        # copy down to the selection in a separate Blender before compiling it.
        import json
        job = os.path.join(folder, base + " QT.json")
        try:
            with open(job, "w", encoding="utf-8") as f:
                json.dump({"keep": [o.name for o in picked], "start": list(context.scene.cursor.location)}, f)
            bpy.ops.wm.save_as_mainfile(filepath=target, copy=True, check_existing=False)
        except Exception as ex:
            self.report({"ERROR"}, "Could not write the test file: %s" % ex)
            return {"CANCELLED"}
        strip = [bpy.app.binary_path, "--background", target, "--python",
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "quick_strip.py"), "--", job]
        error = rebuild.start(
            blend=target, blender_exe=bpy.app.binary_path, game_folder=bpy.path.abspath(prefs.game_folder),
            studio_cli=bpy.path.abspath(prefs.studio_cli), staging_folder=staging, time_of_day=s.time_of_day,
            bake=False, open_sky=False, launch=s.launch_after, startup_command="", auto_load=True, before=[strip])
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Quick test of %d object(s) building in its own window. Skater starts at the 3D cursor" % len(picked))
        return {"FINISHED"}


class PORTERINO_OT_library_refresh(bpy.types.Operator):
    bl_idname = "porterino.library_refresh"
    bl_label = "Refresh"
    bl_description = "Read the parts folder again after adding or removing pieces"

    def execute(self, context):
        found = library.pieces_for(context.scene.porterino.library_folder, refresh=True)
        self.report({"INFO"}, "%d piece(s) in %d categor%s" % (sum(len(v) for v in found.values()), len(found),
                                                                "y" if len(found) == 1 else "ies"))
        return {"FINISHED"}


class PORTERINO_OT_place_piece(bpy.types.Operator):
    bl_idname = "porterino.place_piece"
    bl_label = "Place piece"
    bl_description = "Add this piece to the map at the 3D cursor"
    bl_options = {"REGISTER", "UNDO"}
    filepath: StringProperty()

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            new = library.place(context, self.filepath, context.scene.cursor.location.copy(), context.scene.porterino.library_snap)
        except Exception as ex:
            self.report({"ERROR"}, "Could not place it: %s" % ex)
            return {"CANCELLED"}
        self.report({"INFO"}, "Placed %d object(s) at the 3D cursor. Press G to move, R to rotate" % len(new))
        return {"FINISHED"}


class PORTERINO_OT_add_start(bpy.types.Operator):
    bl_idname = "porterino.add_start"
    bl_label = "Player start at cursor"
    bl_description = "Puts the player start (an empty named 'spawn') at the 3D cursor, or moves the one you already have"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        start = checks.find_spawn(context.scene)
        if start is None:
            start = bpy.data.objects.new("spawn", None)
            start.empty_display_type = "SINGLE_ARROW"
            context.scene.collection.objects.link(start)
        start.location = context.scene.cursor.location.copy()
        self.report({"INFO"}, "Player start is at the 3D cursor")
        return {"FINISHED"}


class PorterinoPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Porterino"


class PORTERINO_PT_checks(PorterinoPanel, bpy.types.Panel):
    bl_label = "Map checks"

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.operator("porterino.check_all", icon="PLAY")
        col.separator()
        col.operator("porterino.check_floor", icon="MESH_GRID")
        col.prop(s, "hole_radius")
        col.operator("porterino.check_solid", icon="MOD_PHYSICS")
        col.operator("porterino.fix_solid", icon="CHECKMARK")
        col.separator()
        col.operator("porterino.check_lips", icon="IPO_EASE_IN")
        col.prop(s, "lip_minimum")
        col.prop(s, "lips_selected_only")
        col.separator()
        col.operator("porterino.check_routes", icon="OUTLINER_OB_ARMATURE")
        col.operator("porterino.route_support", icon="MOD_SOLIDIFY")
        col.separator()
        col.operator("porterino.check_textures", icon="TEXTURE")
        col.operator("porterino.fix_textures", icon="FILE_IMAGE")
        col.operator("porterino.check_lights", icon="LIGHT")


class PORTERINO_PT_materials(PorterinoPanel, bpy.types.Panel):
    bl_label = "Materials and sounds"

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.label(text="Untextured in game?")
        col.operator("porterino.check_materials", icon="MATERIAL")
        col.operator("porterino.fix_materials", icon="NODE_MATERIAL")
        col.operator("porterino.check_textures", icon="TEXTURE")
        col.operator("porterino.fix_textures", icon="FILE_IMAGE")
        col.separator()
        col.label(text="Wrong sound?")
        col.operator("porterino.check_surfaces", icon="SPEAKER")
        col.prop(s, "surface_choice", text="")
        col.prop(s, "surface_materials")
        col.operator("porterino.set_surface", icon="CHECKMARK")


class PORTERINO_PT_library(PorterinoPanel, bpy.types.Panel):
    bl_label = "Parts library"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.prop(s, "library_folder", text="")
        found = library.pieces_for(s.library_folder)
        if not found:
            col.label(text="Pick a folder of pieces")
            col.label(text="(.blend, .fbx or .obj files)")
        else:
            row = col.row(align=True)
            row.prop(s, "library_category", text="")
            row.operator("porterino.library_refresh", text="", icon="FILE_REFRESH")
            col.prop(s, "library_snap")
            col.label(text="Click a piece: it lands on the cursor")
            for name, path in found.get(s.library_category, [])[:80]:
                col.operator("porterino.place_piece", text=name, icon="MESH_CUBE").filepath = path
        col.separator()
        col.operator("porterino.add_start", icon="EMPTY_SINGLE_ARROW")


class PORTERINO_PT_shape(PorterinoPanel, bpy.types.Panel):
    bl_label = "Bowl and ramp shape"

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.label(text="1. Select the bowl or ramp")
        col.label(text="2. 3D cursor on its flat bottom")
        col.operator("porterino.check_transition", icon="SPHERECURVE")
        col.prop(s, "bowl_lip_angle")
        col.prop(s, "bowl_kink")
        col.prop(s, "bowl_reach")
        col.separator()
        col.label(text="Select the coping curve:")
        col.operator("porterino.check_rim", icon="CURVE_BEZCIRCLE")


class PORTERINO_PT_results(PorterinoPanel, bpy.types.Panel):
    bl_label = "Results"

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        if not s.findings:
            col.label(text="Run a check. Results show here.")
            return
        for i, f in enumerate(s.findings):
            box = col.box()
            row = box.row()
            row.label(text=f.check.title(), icon=ICONS.get(f.level, "DOT"))
            if f.has_location:
                row.operator("porterino.goto", text="", icon="VIEWZOOM").index = i
            # sidebar labels do not wrap, so break long lines by hand
            words, line = f.text.split(" "), ""
            for w in words:
                if len(line) + len(w) > 38:
                    box.label(text=line)
                    line = w
                else:
                    line = (line + " " + w).strip()
            if line:
                box.label(text=line)
        col.label(text="Full text: Text Editor > Porterino report")


class PORTERINO_PT_lights(PorterinoPanel, bpy.types.Panel):
    bl_label = "Lighting helper"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.prop(s, "light_range")
        col.prop(s, "light_when")
        col.operator("porterino.set_lights", icon="LIGHT_POINT")
        col.separator()
        col.prop(s, "glow_power")
        col.operator("porterino.add_glow", icon="LIGHT_AREA")


class PORTERINO_PT_scale(PorterinoPanel, bpy.types.Panel):
    bl_label = "Scale"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(context.scene.porterino, "scale_factor")
        col.operator("porterino.scale_map", icon="FULLSCREEN_EXIT")


class PORTERINO_PT_rebuild(PorterinoPanel, bpy.types.Panel):
    bl_label = "Rebuild into the game"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.porterino
        col = self.layout.column(align=True)
        col.prop(s, "time_of_day")
        col.prop(s, "bake_lighting")
        col.prop(s, "open_sky")
        col.prop(s, "launch_after")
        col.prop(s, "auto_load")
        col.operator("porterino.rebuild", icon="FILE_REFRESH")
        col.separator()
        col.label(text="Select pieces, cursor = start:")
        col.operator("porterino.quick_test", icon="PLAY")
        col.label(text="Paths: Preferences > Add-ons > Porterino")


CLASSES = (PorterinoFinding, PorterinoSettings, PorterinoPreferences, PORTERINO_OT_floor, PORTERINO_OT_solid,
           PORTERINO_OT_fix_solid, PORTERINO_OT_lips,
           PORTERINO_OT_transition, PORTERINO_OT_rim, PORTERINO_OT_routes, PORTERINO_OT_lights, PORTERINO_OT_all,
           PORTERINO_OT_textures, PORTERINO_OT_fix_textures, PORTERINO_OT_materials, PORTERINO_OT_fix_materials,
           PORTERINO_OT_surfaces, PORTERINO_OT_set_surface, PORTERINO_OT_route_support, PORTERINO_OT_goto, PORTERINO_OT_set_lights, PORTERINO_OT_glow, PORTERINO_OT_scale, PORTERINO_OT_rebuild, PORTERINO_OT_quick_test,
           PORTERINO_OT_library_refresh, PORTERINO_OT_place_piece, PORTERINO_OT_add_start,
           PORTERINO_PT_checks, PORTERINO_PT_materials, PORTERINO_PT_library, PORTERINO_PT_shape, PORTERINO_PT_results, PORTERINO_PT_lights, PORTERINO_PT_scale,
           PORTERINO_PT_rebuild)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.porterino = bpy.props.PointerProperty(type=PorterinoSettings)


def unregister():
    del bpy.types.Scene.porterino
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
