# Running Porterino from the command line (scripts and AI agents)

Everything the panel does is a plain function in `porterino/checks.py`. `run_checks.py` runs the map checks with no
Blender window:

```
blender --background "my_map.blend" --python run_checks.py -- --report report.txt --json report.json --studio-addon "<ReSkate Studio>\Native\Blender\sk8_map_export.py"
```

| Option | Meaning |
|---|---|
| `--report FILE` | findings as text |
| `--json FILE` | findings as JSON: `check`, `level` (`problem`, `look`, `ok`), `text`, `location` (x, y, z or null) |
| `--only floor,lips,routes,lights` | run some of the checks |
| `--radius 150` | floor-hole search radius in metres around the player start |
| `--studio-addon FILE` | Studio's `sk8_map_export.py`. Without it collision settings and NPC routes are not read |

Exit code 0 means no finding is marked `problem`; 1 means at least one is.

## Calling the functions yourself

```python
import bpy
from porterino import checks            # or load porterino/checks.py with importlib

scene, dg = bpy.context.scene, bpy.context.evaluated_depsgraph_get()
checks.check_floor_holes(scene, dg, radius=150.0)
checks.check_ramp_lips(scene, dg, objects=None, minimum_cm=3.5)      # objects=None finds ramps by name
checks.check_transition(dg, [bowl_object], centre_vector)            # centre on the flat bottom
checks.check_rim([curve_object])
checks.check_routes(scene, dg)
checks.check_lights(scene)
checks.set_light(light_object, 20.0, ("evening", "night", "weathernight"))
checks.add_glow_light(scene, sign_object, power=300.0)
checks.scale_map(scene, 0.8)
```

## Rules for an agent using this

- A finding is a place to look, not proof. Report it with its location and say it has not been ridden.
- The lip and transition thresholds (3.5 cm, 75 degrees, 14 degrees) are starting values. Do not "fix" geometry to
  satisfy them without the map's owner agreeing.
- Do not compile while the game is running, and keep the build folder outside the game folder.
- Never create or copy a `.reskate-studio-patch` file. It must come from the compile of that same map.
