# Rebuild into the game

## Why there is no live editing

skate. does not read your .blend. ReSkate Studio compiles the .blend into the game's own map format, and the game
loads that compiled copy. So if you move a ramp in Blender and start the game, **you see the old map** until you
rebuild. Moving one object means: save, compile, install, load.

The **Rebuild and install** button does all of that in one click, in its own window, so Blender stays usable.

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
4. Press **Rebuild and install**.
5. A console window opens and shows the build. When it says `Installed to Mods\<name>`, the game starts if
   **Start the game after** is ticked. With **Go straight into the map** ticked it opens directly in your map,
   skipping the menu. Otherwise pick the map from the pause menu's custom maps.
6. If it says `BUILD FAILED`, the reason is in the lines above it. The window stays open so you can read it.

**"Path is too long":** Windows refuses file paths over about 260 characters, and the build repeats the map's name
inside the build folder. Use a short build folder such as `C:\RSBuild` and a short .blend name. Porterino checks this
before it starts and tells you.

## Quick test: selected only

The fastest way to try one ramp, bowl or rail without rebuilding the whole map.

1. Select the pieces you want to try. Include some floor to land on.
2. Put the 3D cursor where the skater should start (Shift + right-click on the floor).
3. Press **Quick test: selected only**.

It saves a copy of your file, strips the copy down to the selection in a separate Blender, builds that as its own
small map called `<your map> QT`, and opens the game in it. Your real map and your open file are not touched.
The test map shows up in the game's custom maps like any other; delete its folder from `Mods` when you are done.
Lighting is never baked for a quick test.

## Making the loop fast

The wait is almost all compile time, and compile time follows how much is in the file.

- **Leave Bake lighting off** while you are shaping things. Turn it on for the release build.
- **Test the piece, not the map.** Use **Quick test: selected only** (above) on the bowl or ramp you are tuning.
  A small selection compiles in seconds where a full map takes minutes.
- **Measure before you build.** The bowl and lip checks take seconds and catch the obvious problems, so fewer
  rebuilds are spent finding out a transition is too shallow.

## Before you share a map

Zip the map's folder from `Mods` and check that the file `.reskate-studio-patch` is in the zip. Some zip tools skip
files whose name starts with a dot, and without it the launcher shows the map as "Outdated" and will not load it.
