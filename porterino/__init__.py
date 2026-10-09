# Porterino: the ReSkate Map Toolkit. A Blender add-on that checks a map against how skate. plays
# (holes, ramp lips, bowl transitions, NPC routes, lights) and rebuilds it into the game with one button.
# Install: Edit > Preferences > Add-ons > Install from Disk > pick the porterino zip. Panel: 3D view, N key, "Porterino" tab.
bl_info = {
    "name": "Porterino: ReSkate Map Toolkit",
    "author": "Carterino",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar (N) > Porterino",
    "description": "Check a map against skate. physics and rebuild it into the game with one button",
    "category": "3D View",
}

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, StringProperty)

from . import checks, rebuild

ICONS = {"problem": "ERROR", "look": "INFO", "ok": "CHECKMARK"}


class PorterinoFinding(bpy.types.PropertyGroup):
    check: StringProperty()
    level: StringProperty()
    text: StringProperty()
    has_location: BoolProperty()
    location: FloatVectorProperty(size=3)


class PorterinoSettings(bpy.types.PropertyGroup):
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


class PORTERINO_OT_all(bpy.types.Operator):
    bl_idname = "porterino.check_all"
    bl_label = "Run all checks"
    bl_description = "Floor holes, ramp lips, NPC routes and lights. Large maps can take a few minutes"

    def execute(self, context):
        context.scene.porterino.findings.clear()
        for op in (bpy.ops.porterino.check_floor, bpy.ops.porterino.check_lips, bpy.ops.porterino.check_routes,
                   bpy.ops.porterino.check_lights):
            op()
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
            bake=s.bake_lighting, open_sky=s.open_sky, launch=s.launch_after, startup_command=s.map_asset)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Build started in its own window. Blender stays usable")
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
        col.separator()
        col.operator("porterino.check_lips", icon="IPO_EASE_IN")
        col.prop(s, "lip_minimum")
        col.prop(s, "lips_selected_only")
        col.separator()
        col.operator("porterino.check_routes", icon="OUTLINER_OB_ARMATURE")
        col.operator("porterino.check_lights", icon="LIGHT")


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
        col.prop(s, "map_asset")
        col.operator("porterino.rebuild", icon="FILE_REFRESH")
        col.label(text="Paths: Preferences > Add-ons > Porterino")


CLASSES = (PorterinoFinding, PorterinoSettings, PorterinoPreferences, PORTERINO_OT_floor, PORTERINO_OT_lips,
           PORTERINO_OT_transition, PORTERINO_OT_rim, PORTERINO_OT_routes, PORTERINO_OT_lights, PORTERINO_OT_all,
           PORTERINO_OT_goto, PORTERINO_OT_set_lights, PORTERINO_OT_glow, PORTERINO_OT_scale, PORTERINO_OT_rebuild,
           PORTERINO_PT_checks, PORTERINO_PT_shape, PORTERINO_PT_results, PORTERINO_PT_lights, PORTERINO_PT_scale,
           PORTERINO_PT_rebuild)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.porterino = bpy.props.PointerProperty(type=PorterinoSettings)


def unregister():
    del bpy.types.Scene.porterino
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
