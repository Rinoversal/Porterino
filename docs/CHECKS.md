# The map checks, one by one

Every check puts its findings in the **Results** box. A red triangle is a problem, a blue "i" is something to look
at, a tick means that check found nothing. The magnifier on a line moves the 3D cursor to the spot and centres the
view on it. The full text is also in Blender's Text Editor as **Porterino report**, so you can copy it.

The checks measure the mesh. They do not ride the map. Use them to find where to look, then ride it.

## Floor holes

**What it finds:** floor you can see that has nothing solid under it. In game you fall through the map there.
This usually happens when a floor piece has its collision set to "none", for example because it was treated as decoration.

**How to run it**

1. Set **Radius**. It searches a circle around the player start (an empty whose name starts with `spawn`, `start`
   or `playerstart`). If there is none it uses the 3D cursor.
2. Press **Floor holes**.

**Reading the result:** `18 m2 of drawn floor has nothing solid under it (floor_pit)` means a patch of that size, and
the name is the mesh you are looking at.

**How to fix it:** select that piece, and in ReSkate Studio's object settings set collision to triangle mesh. Or put
a simple invisible collision plane under it.

**It ignores on purpose:** pieces under 12 m2, and anything named like a tree, water, sky or backdrop.

## Seen but not solid

**What it finds:** floors and ramps that are drawn but have nothing solid where you see them. You ride onto the ramp
and go straight through it. This is common in ports, where the picture and the collision are two separate meshes and
the collision for some pieces did not come across.

**How to run it:** set **Radius**, press **Seen but not solid**.

**Reading the result:** `ramp_12: 14 of 14 m2 not solid (solid is 1.50 m away)` means the whole piece is drawn 1.5 m
away from the nearest collision. `nothing solid under it at all` means there is no collision below it anywhere.

**How to fix it:** press **Make drawn pieces solid**.

- A piece that is mostly unsupported (a quarter of it or more) becomes solid as a whole, from its own drawn mesh.
- A piece that is only partly unsupported, such as a deck whose edge hangs past its collision, keeps its collision
  as it is. Just its unsupported faces are copied into one invisible solid object called `col_seen_patch`, which
  shows as a wire outline in Blender.
- Backdrops, water and sky are left alone.

A few square metres can remain on very large faces where only a thin strip at the edge is unsupported.
Run the check again afterwards. Roofs and other high pieces become solid too, which is normally what you want.

**What it does not cover:** walls and fences. It only looks at surfaces you could stand on.

## Ramp lips

**What it finds:** a sharp step where the floor meets the bottom of a ramp, bank, quarter pipe, bowl or kicker.
In skate. a step of a few centimetres can catch the wheels and stop you dead.

**How to run it**

1. Leave **Selected only** off to check every piece whose name looks like a ramp (ramp, quarter, qp, bowl,
   kicker, bank, spine, pyramid, funbox, roll in, wedge, hip, vert, pool).
   Turn it on to check exactly the meshes you have selected, whatever they are called.
2. Press **Ramp lips**.

**Reading the result:** `QP_03: sharp step up to 6.1 cm at its foot (typical 2.5 cm, 14 places)`. The cursor goes to
the worst place.

**How to fix it:** bring the ramp's bottom edge down to the floor, or add a thin wedge that starts at floor height.
Aim for no step at all at an entrance.

**Honest note:** this check has found steps in our own maps, but we have not finished ride-testing which sizes you can
feel. Treat 3.5 cm and up as "ride this entrance first".

## Measure bowl / ramp

**What it finds:** whether a transition will send you up or throw you outward, and whether it is smooth enough.

**How to run it**

1. Select the bowl or ramp mesh (several pieces are fine).
2. Put the 3D cursor on the flat bottom: Shift + right-click on the floor of the bowl.
3. Press **Measure bowl / ramp**.

It walks outward from the cursor in 32 directions and measures every wall it climbs.

**Reading the result**

- **Height:** floor to lip.
- **Lip angle:** how steep the last part is. 90 is vertical. Under 75 it reports "you launch outward, not up".
- **Radius:** rough size of the curve.
- **Angle jumps N deg between two facets:** the curve is made of too few flat strips. Over 14 degrees it tells you
  to add segments.

**How to fix it:** add edge loops along the curve for kinks; make the top steeper or taller for a low lip angle.

**The three numbers under the button** are yours to change: **Lip at least** (default 75), **Facet turn at most**
(default 14) and **Look out to** (how far from the cursor it searches, default 12 m; raise it for a big bowl).

**Honest note:** 75 and 14 degrees are starting values, not laws. If a bowl rides well with other numbers, tell us.

## Check coping curve

**What it finds:** corners and long straight pieces along a grind curve, which make a grind jerk or drop.

**How to run it:** select the curve object and press **Check coping curve**.

**Reading the result:** number of points, the sharpest turn between two segments, and the longest segment. It suggests
staying under 10 degrees per point and 0.45 m per segment on a round bowl. Add points where it turns sharply.

## NPC routes

Needs ReSkate Studio's add-on. It reads the NPC routes in the scene and reports:

- **Closed pedestrian loop:** walkers appear and vanish beside the player. Use an open path.
- **Many spawn points on one route:** set the spacing near the route's length so one walker spawns.
- **Points not over solid ground:** NPCs spawn off the map or fall.
- **Passes within 12 m of the player start:** someone appears in your face on load.
- **More than 3 pedestrian routes:** costs frame rate on slower PCs.

### Add deck under routes (the fix for vehicles in mid-air)

A bus, car or train is placed **on** its route. If part of the route has nothing solid directly under it, the
vehicle starts in the air there and drops. This happens most with elevated train tracks, which are drawn as two thin
rails and sleepers with gaps between them, and with road tiles that have a hole under a decal.

1. Run **NPC routes**. A route with this problem says `N of M points have nothing solid under them, up to X m above
   the ground`.
2. Press **Add deck under routes**. With nothing selected it fixes every vehicle route; select route curves first to
   fix only those.
3. It adds an invisible solid strip, a little wider than the route, under just the stretches with more than 4 m of
   nothing below them. Stretches closer to solid ground are left alone, so it never puts an invisible ceiling low over
   a place you can skate. In Blender
   it shows as a wire outline named `Route support ...`. Nothing is removed and the route is not moved.
4. Run **NPC routes** again to confirm.

In game the strip cannot be seen but is solid, so a skater who reaches an elevated track can stand between the rails.
If you would rather not have that, delete the strip and lower the route's weight or shorten the route instead.

## Check materials (a piece is untextured in game)

**What it finds:** pieces that look right in Blender and come out as one flat colour in game.

**Why it happens:** the map build reads one thing for a material's picture: the **Base Color** input of its
**Principled BSDF**. The picture reaches the game when an Image Texture node is wired straight into that input.
Downloaded models often are not built that way.

| It says | Meaning |
|---|---|
| has no Principled BSDF (it uses Diffuse BSDF ...) | an older or imported shader. The build reads only Principled |
| Base Color goes through a ... node before it reaches the picture | a colour adjustment, mix or node group sits in between. The build tries to bake it and uses a flat colour when it cannot |
| has a picture that is not connected to Base Color | the Image Texture node is there but not plugged in |
| has no UV map | nothing tells the game where the picture goes on the mesh |
| its Image Texture node has no picture chosen | the pink "missing" node |
| uses a Mapping node / places its picture by ... coordinates | the build uses the plain UV map, so size or position will differ in game |
| is linked from another .blend | the piece lives in a different file. Make it local |

**How to fix it:** press **Fix materials**. It

- wires the colour picture straight into Base Color (it picks the colour picture, not the normal or roughness map),
- builds a Principled BSDF for materials that have none and connects it,
- adds a UV map (Smart UV Project) to textured meshes that have none.

One Undo reverts all of it. A colour adjustment that sat between the picture and Base Color is bypassed, so the piece
may look a little different from before; if you want that adjustment kept, bake it into the picture file instead.
Then run **Fix textures** as well (next section), so the pictures themselves are in a format that always builds.

It cannot fix a material that has no picture at all, or a picture file that is missing.

## Check surface sounds (a piece makes the wrong sound)

Needs ReSkate Studio's add-on. In Studio every **object** and every **material** has a setting called
**Base Surface / Audio Donor**: wood, metal, concrete and so on. It decides the rolling and landing sound.

Two things catch people out:

- **The material's choice beats the object's.** If you set a ramp to wood in the object settings but its material came
  with concrete chosen (common on downloaded models), the ramp still sounds like concrete.
- **A piece nobody set uses the generic default**, so everything sounds the same.

**Check surface sounds** lists:

- pieces where a material overrides the object's choice (it names both),
- pieces with no surface chosen at all,
- pieces whose name says one thing (wood, metal, plastic ...) while the surface says another.

**How to fix it:** select the pieces, pick the surface in the dropdown, leave **Also set its materials** ticked and
press **Set surface on selected**. That sets the object and its materials together, so nothing overrides it.
A material shared with other pieces changes for them too; give a piece its own material first if that matters.

The dropdown shows the plain surfaces. Studio's own panel has more (variants with special behaviour) if you need one.

## Check textures ("image has no data")

**What it finds:** textures that will reach the build empty. The usual message is `Image '...' does not have any
image data` or `image has no pixels`, and it tends to come and go: the same file builds one day and not the next.

**Why it comes and goes:** ReSkate Studio 2.11 copies `.png` and `.dds` textures into the build as they are, which
always works. Every other type, JPEG included, is converted during the build, and that conversion fails whenever
Blender has not already loaded the picture into memory. So a JPEG that is fine in every other way can still fail.

**How to run it:** press **Check textures**. It lists, for every texture a material in the scene uses:

| It says | Meaning |
|---|---|
| is a .jpg file | works only by luck: save it as PNG |
| file not found | the path is broken (file moved, renamed, or on a drive that is not connected) |
| file is empty (0 bytes) | a failed download or copy |
| has a .jpg name but is not a readable JPEG | a web page or another format saved with the wrong name |
| is a CMYK JPEG | a print-format JPEG: re-save as RGB |
| made inside Blender and never saved | painted or generated in Blender, exists only in memory |

**How to fix it:** press **Fix textures**. Every texture Blender can read is saved as a PNG in a folder called
`porterino_textures` next to your .blend, and the materials are pointed at those files. Your original pictures are
not changed or deleted. Then save the .blend. Textures that cannot be read at all (missing, empty, not really an
image) stay on the list: re-link those by hand with **File > External Data > Find Missing Files**, or replace them.

Save the .blend first: the fix needs to know where to put the folder.

## Check lights

See [LIGHTING.md](LIGHTING.md).

## Scale map

Set **Factor** (0.8 = 80% of the size) and press **Scale map**. It scales about the world origin and also
adjusts light power, light ranges and NPC route widths so the map looks and behaves the same, just smaller or bigger.
Save a copy of the file first. One Undo reverts it.
