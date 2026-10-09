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

**How to fix it:** press **Make drawn pieces solid**. Each reported piece gets collision from its own drawn mesh.
Backdrops, water and sky are left alone, and a piece is only changed when at least a quarter of it is unsupported.
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

## Check lights

See [LIGHTING.md](LIGHTING.md).

## Scale map

Set **Factor** (0.8 = 80% of the size) and press **Scale map**. It scales about the world origin and also
adjusts light power, light ranges and NPC route widths so the map looks and behaves the same, just smaller or bigger.
Save a copy of the file first. One Undo reverts it.
