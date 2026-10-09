# Run by the quick-test build in a separate Blender: keeps only the listed objects in this copy of the map, puts the
# player start where the 3D cursor was, and saves.   blender --background copy.blend --python quick_strip.py -- keep.json
import json
import sys

import bpy

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
keep = set(job["keep"])
scene = bpy.context.scene
removed = 0
for obj in list(bpy.data.objects):
    if obj.name not in keep or obj.name.lower().startswith(("spawn", "start", "playerstart")):
        bpy.data.objects.remove(obj, do_unlink=True)
        removed += 1
start = bpy.data.objects.new("spawn", None)
start.empty_display_type = "SINGLE_ARROW"
start.location = (job["start"][0], job["start"][1], job["start"][2] + 0.05)
scene.collection.objects.link(start)
try:
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
except Exception:
    pass
bpy.ops.wm.save_mainfile()
print("Porterino quick test: kept %d object(s), removed %d" % (len(scene.objects) - 1, removed), flush=True)
