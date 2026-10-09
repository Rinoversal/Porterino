# Lighting a ReSkate map

Written from an in-game test with ReSkate Studio 2.11 (seven test panels side by side). A later Studio version may change this.

## The short version

- Real Blender lights work: Point, Spot and Area.
- Sun lights are skipped. The game's own sun and sky light the level.
- **Emission does not work.** A material with emission colour, emission strength or an emission texture shows up in
  game as its plain base colour. There is no warning.
- To make a sign, screen or panel look lit: give it a bright base colour and put an Area light about 30 cm in front
  of it. In game that blooms and reads as glowing.

## Two settings every light needs

They are custom properties on the light **object** (Object properties > Custom Properties):

| Property | Meaning | Typical |
|---|---|---|
| `sk8_light_range` | how far the light reaches, in metres | 6 to 60 (40 if missing) |
| `sk8_light_tod` | when it is on: add up the numbers below | 127 always, 88 evening and night |

Time of day numbers: morning 1, noon 2, afternoon 4, evening 8, night 16, weather day 32, weather night 64.

You do not have to type these. Select your lights and use the **Lighting helper** panel:

1. Set **Range**.
2. Set **On during** (Always for indoor lights, Evening and night for street lamps and signs).
3. Press **Apply to selected lights**.

## Making something glow

1. Select the sign or panel mesh (one or many).
2. Set **Power**. 300 W suits a 2 m panel.
3. Press **Add glow light to selected**.

It adds an Area light the size of the piece, 30 cm off its biggest face. If the light ended up behind the sign
(the face pointed the other way), rotate the light 180 degrees and move it to the front.

## Check lights

Press **Check lights**. It reports:

- lights with no range or no time of day set;
- lights or meshes that are **hidden from render** (the camera icon in the Outliner). Hidden-from-render things are
  left out of the compiled map entirely, collision included. This is the usual reason "my fence has no collision";
- materials that use emission, which will not glow;
- Sun lights, which are skipped.

## Baked lighting

Bounce lighting is baked when the map is compiled with **Bake lighting** ticked (Rebuild panel). Without it lamps
still light things directly, but the level looks flat. Tick **Enclosed level** for indoor or walled-in maps so the
skater is not a black silhouette. Baking is slower and needs more memory (a city-sized map needed about 9 GB), so
leave it off for quick test builds and turn it on for the build you release.

A Blender render is not the game: no game sky, no bake, no bloom. Judge lighting in game, at the time of day you care about.
