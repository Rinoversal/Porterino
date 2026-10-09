# Rebuild into the game

## Why there is no live editing

skate. does not read your .blend. ReSkate Studio compiles the .blend into the game's own map format, and the game
loads that compiled copy. So if you move a ramp in Blender and start the game, **you see the old map** until you
rebuild. Moving one object means: save, compile, install, load.

The **Save, rebuild and install** button does all of that in one click, in its own window, so Blender stays usable.

## Set it up once

**Edit > Preferences > Add-ons > Porterino**, fill in three paths:

| Field | What to pick |
|---|---|
| Game folder | the folder that has `ReSkateLauncher.exe` and `Mods` in it |
| reskate_cli.exe | inside your ReSkate Studio folder |
| Build folder | any empty folder that is **not** inside the game folder, for example `C:\ReSkateBuilds` |

## Use it

1. Save your .blend with the name you want the map to have in game. The file name is the map's title.
2. Close skate. if it is open. A map cannot be replaced while the game has it loaded.
3. In the **Rebuild into the game** panel pick the time of day, leave **Bake lighting** off for a test build.
4. Press **Save, rebuild and install**.
5. A console window opens and shows the build. When it says `Installed to Mods\<name>`, the game starts if
   **Start the game after** is ticked. Pick the map from the pause menu's custom maps.
6. If it says `BUILD FAILED`, the reason is in the lines above it. The window stays open so you can read it.

**Load command (optional):** a console line the game runs at startup, so it goes straight into your map, for example
`load levels/game/my_map/my_map;wait 30`. The exact asset name is shown in the build window's output. Leave it empty
if you are not sure.

## Making the loop fast

The wait is almost all compile time, and compile time follows how much is in the file.

- **Leave Bake lighting off** while you are shaping things. Turn it on for the release build.
- **Test the piece, not the map.** Copy the bowl or ramp you are tuning, plus a bit of floor and a player start, into
  a small .blend. That compiles in a fraction of the time. Paste it back when it rides right.
- **Measure before you build.** The bowl and lip checks take seconds and catch the obvious problems, so fewer
  rebuilds are spent finding out a transition is too shallow.

## Before you share a map

Zip the map's folder from `Mods` and check that the file `.reskate-studio-patch` is in the zip. Some zip tools skip
files whose name starts with a dot, and without it the launcher shows the map as "Outdated" and will not load it.
