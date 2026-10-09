# Converters (coming)

This folder will hold the tools that bring a level from another game into Blender, ready for ReSkate Studio.
Nothing is here yet: the readers exist and have produced released maps, but they still have paths from the PC they
were written on, and they are being cleaned up before they go public.

## How a port works, whatever the game

1. **Unpack** the game's archive files to get the level's models, textures and collision.
2. **Read** each format into plain data: meshes, materials, object positions, rails, lights.
3. **Assemble** the level in Blender at real-world scale (skate. is in metres).
4. **Tag** it for ReSkate Studio: what is solid, what is a grind rail, where the player starts, lights.
5. **Check** it with Porterino, because a level built for an arcade game does not automatically ride well in skate.
6. **Compile** with ReSkate Studio.

Steps 1 and 2 are different for every game. Steps 3 to 6 are the same, and that shared part is what will be published
here first, with one reader as a worked example.

## Planned readers

| Game | Engine | State |
|---|---|---|
| Tony Hawk's Pro Skater 1+2 | Unreal 4 | working, used for released maps |
| Tony Hawk's American Wasteland | Neversoft | working, pilot level built |
| Old School RuneScape | own cache format | working for terrain and models |

## What will never be in this repository

- Game files, extracted assets or textures.
- Decryption keys.
- Any part of ReSkate Studio.

You need to own the game you convert from, and you supply its files yourself.
