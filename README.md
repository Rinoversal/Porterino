# Porterino: the ReSkate Map Toolkit

A Blender add-on for people making custom maps for skate. with ReSkate Studio.

**TL;DR:** press a button in Blender and it tells you where your map will play badly (holes you fall through, lips at
the foot of ramps, bowls that throw you outward instead of up, pedestrians that pop in beside you, lights that will
not show up) and takes you to the exact spot. Another button saves, rebuilds and installs the map and starts the game.

No AI needed. No command line needed. If you do use an AI agent or scripts, the same checks run from the command line
(see [docs/FOR_AI.md](docs/FOR_AI.md)).

> Status: version 0.1, early. Each check says below how far it has been proven. Treat results as "look here", then ride it.

## What is in it

| Tool | What it does | How far it is proven |
|---|---|---|
| Find holes in the floor | Finds floor you can see but that has no collision under it | Found a real fall-through pit in a released map |
| Find lips at ramp entrances | Finds sharp steps (3.5 cm and up) where the floor meets a ramp | Finds steps in the mesh; which sizes you feel in game is still being ride-tested |
| Measure bowl / quarter pipe | Height, angle at the lip, radius and facet kinks all the way round | New, numbers are a starting point |
| Check coping / rim curve | Sharp turns and long straight segments along a grind curve | New |
| Check pedestrians and traffic | Routes that pop in next to the player, spawn off the map or cost frame rate | Rules come from tester complaints on released maps |
| Check lights | Lights with no range or time of day, hidden pieces that will not export, emission the game ignores | Emission result confirmed in game |
| Lighting helper | Sets range and time of day on lights; adds a glow light in front of a sign | Glow method confirmed in game |
| Scale the whole map | Scales everything and keeps lights and NPC routes matching | Used on released maps |
| Save, rebuild and install | One button: save, compile with ReSkate Studio, install, start the game | Same command our own maps are built with |

## Does it work for other games and engines?

Yes for the measuring tools. Holes, lips, bowl and coping checks, the emission and hidden-piece checks and the scale
tool read plain Blender geometry, so they run on any scene, whatever game it came from or is going to. Without ReSkate
Studio's add-on every mesh simply counts as solid. The numbers they flag (3.5 cm lips, 75 degree lips) are tuned for
how skate. plays; another game may want different ones.

Only three things are ReSkate-specific: the NPC route check, the two light properties the lighting helper writes, and
the rebuild button.

## What if ReSkate Studio updates?

The checks keep working: they measure geometry and do not depend on Studio. Porterino touches Studio in four places
only, all listed in [docs/STUDIO_UPDATES.md](docs/STUDIO_UPDATES.md) with how to tell if one changed and the one line to edit.

## What you need

- Blender 4.2 or newer.
- ReSkate Studio, with its Blender add-on enabled. Without it the checks still run, but they cannot see which pieces
  have collision switched off, and the rebuild button will not work.

## Install (2 minutes)

1. On this page click **Releases** (right-hand side) and download `porterino.zip`. Do not unzip it.
2. In Blender: **Edit > Preferences > Add-ons**, the small arrow at the top right, **Install from Disk**, pick `porterino.zip`.
3. Tick **Porterino: ReSkate Map Toolkit** in the list.
4. In the 3D view press **N**. There is a new tab called **Porterino**, next to ReSkate Studio's **Skate Map** tab.

(If you downloaded the source instead: run `python make_zip.py`, or zip the `porterino` folder yourself.)

## Use it

1. Open your map's .blend.
2. In the Porterino tab press **Run every map check**. On a big map this takes a few minutes; Blender waits while it works.
3. Read the **Results** box. Each line has a magnifier button: press it to jump to that spot.
4. Fix, press the check again, repeat.
5. Ride it. A check finds what the mesh says; only a ride proves how it feels.

Each tool is explained step by step, with what the numbers mean and how to fix what it finds, in:

- [docs/CHECKS.md](docs/CHECKS.md) – holes, lips, bowls, coping, NPC routes
- [docs/LIGHTING.md](docs/LIGHTING.md) – how lighting works in ReSkate maps and the lighting helper
- [docs/REBUILD.md](docs/REBUILD.md) – the rebuild button and how to make test loops fast
- [docs/FOR_AI.md](docs/FOR_AI.md) – running everything from the command line
- [converters/README.md](converters/README.md) – bringing levels over from other games (coming)

## What it cannot do

- It cannot edit a map while the game is running. skate. loads a compiled copy of your map, so a change in Blender
  shows up only after a rebuild. The rebuild button makes that one click, and [docs/REBUILD.md](docs/REBUILD.md) shows how to get the wait down.
- It does not fix things for you yet. It finds and measures.
- It contains no game files and no part of ReSkate Studio.

Made by Carterino.
