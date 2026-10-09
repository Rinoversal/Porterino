# Parts library: browse a folder of ready-made pieces (ramps, rails, benches ...) and place them at the 3D cursor.
# Folder layout: every .blend / .fbx / .obj file is a piece, and the folders above it are its category, for example
#   Parts/Street/Benches/Metal bench/Metal bench.blend   ->  category "Street / Benches", piece "Metal bench"
# Pieces saved as .blend keep their ReSkate Studio settings (collision, grind curves, materials).
import os

import bpy
from mathutils import Vector

PIECE_TYPES = (".blend", ".fbx", ".obj")
_cache = {"folder": None, "pieces": {}}        # category -> [(name, path)]


def scan(folder):
    """{category: [(piece name, file path)]} for every piece under the folder."""
    pieces = {}
    folder = os.path.normpath(folder)
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d.lower() not in ("textures", "__pycache__") and not d.startswith("."))
        for name in sorted(files):
            stem, ext = os.path.splitext(name)
            if ext.lower() not in PIECE_TYPES:
                continue
            rel = os.path.relpath(root, folder)
            parts = [] if rel == "." else rel.split(os.sep)
            if parts and parts[-1].lower() == stem.lower():
                parts = parts[:-1]                         # a piece in a folder of its own name: the folder is not a category
            pieces.setdefault(" / ".join(parts) or "(top folder)", []).append((stem, os.path.join(root, name)))
    return pieces


def pieces_for(folder, refresh=False):
    folder = bpy.path.abspath(folder) if folder else ""
    if not folder or not os.path.isdir(folder):
        return {}
    if refresh or _cache["folder"] != folder:
        _cache["folder"], _cache["pieces"] = folder, scan(folder)
    return _cache["pieces"]


def place(context, path, location, snap=0.0):
    """Bring the piece at `path` into the scene with its origin at `location`. Returns the new objects."""
    scene = context.scene
    if snap > 0.0:
        location = Vector([round(v / snap) * snap for v in location])
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        new = [o for o in dst.objects if o is not None]
        for obj in new:
            if obj.name.lower().startswith(("spawn", "start", "playerstart")) or obj.type == "CAMERA":
                bpy.data.objects.remove(obj)
                continue
            scene.collection.objects.link(obj)
        new = [o for o in bpy.data.objects if o not in before]
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
    else:
        raise ValueError("Not a piece file: " + path)
    for obj in new:
        if obj.parent is None or obj.parent not in new:    # move the piece as a whole, children follow their parents
            obj.location = Vector(obj.location) + Vector(location)
    for obj in scene.objects:
        obj.select_set(obj in new)
    if new:
        context.view_layer.objects.active = new[0]
    return new
