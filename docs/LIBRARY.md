# Parts library

Place ready-made pieces (ramps, rails, benches, stair sets) into your map with one click, without leaving Blender.

Porterino does not come with any pieces. You point it at a folder of your own.

## Set up a parts folder

Any folder works. Every `.blend`, `.fbx` or `.obj` file in it is one piece, and the folders above the file become
its category:

```text
Parts/
  Street/
    Benches/
      Metal bench/
        Metal bench.blend        -> category "Street / Benches", piece "Metal bench"
        textures/                 (ignored by the library; keep the piece's pictures here)
  Park/
    Ramps/
      Kicker.blend               -> category "Park / Ramps", piece "Kicker"
  Loose box.obj                  -> category "(top folder)", piece "Loose box"
```

A piece may sit in a folder of its own name (like `Metal bench/Metal bench.blend`); that folder is not counted as a
category.

**Save pieces as `.blend` when you can.** A `.blend` piece keeps its ReSkate Studio settings: what is solid, grind
curves and materials. `.fbx` and `.obj` bring the shape only, so you set those up after placing.

Make each piece with its origin where you want to grab it (usually the middle of its base), Z up, in metres.

## Place pieces

1. Open the **Parts library** panel and pick your folder.
2. Choose a **Category**.
3. Put the 3D cursor where the piece should go (Shift + right-click).
4. Click the piece's name. It lands with its origin on the cursor and is left selected.
5. Press **G** to move it, **R** to rotate, **S** to scale, as with anything in Blender.

**Snap:** set a step in metres (1.0, 0.5 ...) and the placing position is rounded to it, so pieces line up on a grid.
Leave it at 0 for free placing.

**Refresh** (the round arrows next to the category) re-reads the folder after you add or remove files.

**Player start at cursor** puts the start point where the cursor is. A map needs exactly one; pressing it again moves
the one you have.

If a piece file contains its own start point or camera, those are left out when placing.

## Works with ReSkate Map Creator folders

[ReSkate Map Creator](https://github.com/jonigiuro/ReSkate-Map-Creator) by Joni Giuro is a separate, standalone editor
for people who would rather not work in Blender. It uses the same idea of an `Objects` folder whose sub-folders are
categories, so you can point Porterino's parts folder at the `Objects` folder you already have there.

Porterino contains none of that project's code and none of its assets. It is an independent Blender add-on.
