# Run the Porterino map checks without opening Blender's window (for scripts, batch builds and AI agents).
#
#   blender --background "my_map.blend" --python run_checks.py -- --report report.txt
#
# Options after the "--":
#   --report FILE     write the findings here as text (default: print only)
#   --json FILE       also write them as JSON
#   --only LIST       comma list of: floor,lips,routes,lights  (default: all four)
#   --radius M        floor-hole search radius from the player start (default 150)
#   --studio-addon F  path to ReSkate Studio's sk8_map_export.py, so collision / route settings in the file are read.
#                     Without it every mesh counts as solid and routes are skipped.
# Exit code: 0 = nothing marked PROBLEM, 1 = at least one PROBLEM.
import argparse
import importlib.util
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--report")
ap.add_argument("--json")
ap.add_argument("--only", default="floor,lips,routes,lights")
ap.add_argument("--radius", type=float, default=150.0)
ap.add_argument("--studio-addon")
args = ap.parse_args(argv)

if args.studio_addon and not hasattr(bpy.types.Object, "sk8_object"):
    spec = importlib.util.spec_from_file_location("sk8_map_export", args.studio_addon)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sk8_map_export"] = mod
    spec.loader.exec_module(mod)
    mod.register()
    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)        # reload so the file's Studio settings are attached

spec = importlib.util.spec_from_file_location("porterino_checks", os.path.join(HERE, "porterino", "checks.py"))
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()
wanted = [w.strip() for w in args.only.split(",") if w.strip()]
runs = {"floor": lambda: checks.check_floor_holes(scene, depsgraph, radius=args.radius),
        "lips": lambda: checks.check_ramp_lips(scene, depsgraph),
        "routes": lambda: checks.check_routes(scene, depsgraph),
        "lights": lambda: checks.check_lights(scene)}
results = []
for name in wanted:
    print("PORTERINO running", name, flush=True)
    results += runs[name]()

label = {"problem": "PROBLEM", "look": "LOOK", "ok": "OK"}
lines = ["Porterino report for " + os.path.basename(bpy.data.filepath), ""]
for r in results:
    where = "  at X %.1f  Y %.1f  Z %.1f" % r["location"] if r["location"] else ""
    lines.append("[%s] %-8s %s%s" % (label[r["level"]], r["check"], r["text"], where))
text = "\n".join(lines) + "\n"
print(text, flush=True)
if args.report:
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(text)
if args.json:
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
sys.exit(1 if any(r["level"] == "problem" for r in results) else 0)
