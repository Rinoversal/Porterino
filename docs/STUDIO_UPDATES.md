# When ReSkate Studio updates

Written against ReSkate Studio 2.11. Porterino contains no Studio code. It only reads a few names that Studio's
Blender add-on defines, and runs Studio's own compiler. If an update renames one of them, that one feature goes
quiet; nothing crashes and the geometry checks carry on.

| What Porterino uses | Where | If Studio changes it, you will see | Where to edit |
|---|---|---|---|
| Object collision setting `sk8_object.collision_mode` (value `none` = not solid) | hole and lip checks | pieces with collision off are treated as solid, so holes are missed | `is_solid` in `porterino/checks.py` |
| NPC route settings `sk8_npc_route` (`enabled`, `kind`, `spacing`, `width`) | route check, scale tool | "No NPC routes in this scene" on a map that has them | `check_routes` in `porterino/checks.py` |
| Light properties `sk8_light_range`, `sk8_light_tod` | light check, lighting helper | lights you set with the helper behave as if unset in game | `set_light` and `TIME_FLAGS` in `porterino/checks.py` |
| Compiler command `reskate_cli.exe compile-map` and its options | rebuild button | the build window shows an "unknown option" style error | the `cmd = [...]` line in `porterino/rebuild.py` |

## Things that may become wrong in a good way

- **Emission.** Studio 2.11 ignores emission, so the light check warns about it and the helper adds glow lights.
  If Studio gains real emissive materials, that warning is out of date: test one glowing panel in game, and if it
  glows, the warning can be removed from `check_lights`.

## After any Studio update

1. Rebuild one small map with the rebuild button and load it.
2. Run **Check pedestrians and traffic** on a map that has routes and confirm it still lists them.
3. Set one light with the lighting helper and confirm in game that it switches on at the time you chose.

If all three behave, nothing needs changing.
