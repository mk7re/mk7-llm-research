# Course culling: the div file, the quadtree and clip objects

- Status: verified
- Asked: Let's start a new topic, I want to investigate how .div and culling works in the game. We know that div files
  are divided by meshes that correspond to the meshes in the course bcmdl, and then each mesh is divided in XZ areas that
  contain some amount of triangles, those triangles are selected by kmp areas and linked to checkpoints using the clip
  objects setting 1 and route. There are some open questions: are the div areas a tree? How is the generation algorithm
  exactly (a reimplementation is in kmpexpander but it's not accurate)? Why having big div areas break culling (as in
  the game seems to select the big area over smaller ones so geometry doesn't cull)? How do kmp objects and cpu drivers
  assign themselves to the div areas? Document the culling system answering those question, make a user friendly guide
  for custom track creators and try to fix the kmpexpander algorithm to match the game (provide result as patch over
  latest master https://github.com/PabloMK7/KMPExpander)
  - Follow-up (2026-10-29): add the scripts to the topic folder as a tool; keep the retail split. Explain how "behind
    the camera" culling works. (The KMPExpander requests of this and later follow-ups moved to the research on the
    KMPExpander culling preview on 2026-10-29.)
  - Follow-up (2026-11-14, document review): make the wording clear for custom track creators, so that they have basic
    context on how culling works without getting too technical: how the clip areas hide cells even in front of the
    camera, how the game hides everything behind the camera, the perm model, how to link areas to culling objects (with
    their object ID) and to checkpoints, how it affects the culling of objects and other karts, and how to use all this
    in KMPExpander and how it is drawn there. The overview explains how the game works, not the questions asked, and
    sums up clip objects and the camera in one sentence each. The div file format is in the glossary. Explain
    occlusion objects in depth.
- Base commit: db0fec51ce309b67fd45a710492ac344190bb565
- Images: `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95), `dlp` only as the source of names. `eur2` also run in
  Azahar (the installed game with its v1.2 update) on Mario Circuit and Wario Shipyard. The 40 retail `.div` and
  `.bcmdl` files are those of `rom:/Course/` of `eur2`.

## Contents

- [Overview](#overview): what culling does and how, for readers new to the topic and for custom course creators
  - [Words used in this document](#words-used-in-this-document)
  - [The grid](#the-grid)
  - [Which cells are hidden in a frame](#which-cells-are-hidden-in-a-frame)
  - [Clip objects: hiding cells in front of the camera](#clip-objects-hiding-cells-in-front-of-the-camera)
  - [The camera: hiding what is behind and beside it](#the-camera-hiding-what-is-behind-and-beside-it)
  - [Occlusion objects](#occlusion-objects)
  - [When a div area is drawn](#when-a-div-area-is-drawn)
  - [The `_perm` model: never culled](#the-_perm-model-never-culled)
  - [Objects, items and karts](#objects-items-and-karts)
  - [Why big div areas break culling](#why-big-div-areas-break-culling)
  - [How the retail div files were made](#how-the-retail-div-files-were-made)
  - [Seeing the culling in KMPExpander](#seeing-the-culling-in-kmpexpander)
  - [Guide for custom course creators](#guide-for-custom-course-creators)
- [Glossary](#glossary): the [div file format](#the-div-file-format); the classes, members and enums involved, with their
  offsets; the [functions](#functions) and [data](#data) tables with addresses
- [Findings](#findings): each claim with its evidence
  - [Sources and method](#sources-and-method)
  - [1. Loading the div file](#1-loading-the-div-file)
  - [2. Building the quadtree](#2-building-the-quadtree)
  - [3. Attaching the div areas to the tree](#3-attaching-the-div-areas-to-the-tree)
  - [4. Clip objects and the clip ID](#4-clip-objects-and-the-clip-id)
  - [5. Occlusion objects](#5-occlusion-objects)
  - [6. The update of each frame](#6-the-update-of-each-frame)
  - [7. Showing and hiding index streams](#7-showing-and-hiding-index-streams)
  - [8. Objects, items, coins and karts](#8-objects-items-coins-and-karts)
  - [9. How the retail div files were made](#9-how-the-retail-div-files-were-made)
  - [10. Culling of different divisions](#10-culling-of-different-divisions)
  - [11. The race camera](#11-the-race-camera)
  - [12. The model: course_culling.py](#12-the-model-course_cullingpy)
- [Confidence](#confidence): what is certain, what is likely, what is a guess
- [Open questions](#open-questions): what was not resolved

## Overview

Mario Kart 7 does not draw the parts of the course that cannot be seen from where the player is: this is called
culling. It works on a grid. When the course loads, the game lays a grid of 8 × 8 cells over the course, and every frame
it decides which cells are hidden ([Which cells are hidden in a frame](#which-cells-are-hidden-in-a-frame)). Two things
hide cells (a third, the occlusion object, is used by a single retail course):

- **Clip objects**, placed in the KMP, hide chosen parts of the course while the player is in chosen checkpoints, even
  right in front of the camera ([Clip objects](#clip-objects-hiding-cells-in-front-of-the-camera)).
- **The camera** hides what is behind it or outside its field of view to the sides
  ([The camera](#the-camera-hiding-what-is-behind-and-beside-it)).

The `.div` file tells the game where each piece of the course model lies: the model is split into small pieces, and the
file gives the rectangle each piece covers. A piece is drawn while at least one of the cells its rectangle touches is
not hidden ([When a div area is drawn](#when-a-div-area-is-drawn)). Objects, items, coins and karts, the CPUs included,
disappear when the cell they are in is hidden ([Objects, items and karts](#objects-items-and-karts)). The course's
second model, `<course>_perm`, is never culled ([The `_perm` model](#the-_perm-model-never-culled)).

Some details that follow from this:

- The div file is a flat list of rectangles; the game builds the grid, a quadtree, over the bounding box of all of
  them ([The grid](#the-grid)).
- Big div areas cull badly because a piece is drawn while **any** cell it touches is visible, and because the unit
  the game hides is the cell, an eighth of the course's width ([Why big div areas break
  culling](#why-big-div-areas-break-culling)).
- The retail div files were made by cutting each mesh along that same grid ([How the retail div files were
  made](#how-the-retail-div-files-were-made)).
- Objects and karts never use the div areas: each one uses the cell it is in.

KMPExpander 2.1 makes div files the retail way and shows all of this on the map
([Seeing the culling in KMPExpander](#seeing-the-culling-in-kmpexpander)), and the
[guide for custom course creators](#guide-for-custom-course-creators) sums up what to do.

### Words used in this document

- **Course model**: the model named after the course in `<course>.bcmdl` (for example `Gctr_MarioCircuit`). It is the
  only model that culling hides. The other model of that file, `<course>_perm`, is the **`_perm` model**.
- **Shape** and **mesh**: the course model's geometry is a list of shapes (vertex data and triangles); a mesh draws one
  shape with one material. The div file follows the order of the shapes.
- **Index stream**: one list of triangles of a shape. The game can switch each index stream on and off on its own; a
  shape split into 20 index streams can be drawn in parts. These are the "pieces" of the course model.
- **Div area**: the rectangle (on the XZ plane, the ground seen from above) that the div file gives for one index
  stream: the bounding box of the stream's vertices.
- **Cell**: a rectangular region of the grid. The grid is a quadtree: the whole course is the **root** cell, which is
  split into 4 cells, each of them into 4, and each of those into 4 again, which gives the 64 **leaf cells** of the
  8 × 8 grid. A leaf cell is one eighth of the course's width by one eighth of its depth. Hiding a cell hides every cell
  inside it. A cell is **visible** in a frame when it is not hidden.
- **Clip object**: a KMP object (GOBJ) with object ID 30 (0x1E, `clip`); KMPExpander's error checker calls them culling
  (clip) objects. Its setting 1 is its **clip ID**, and its route gives its clip quad.
- **Clip quad**: the quad made by the first four points of a clip object's route, seen from above. It is a route of the
  KMP (POTI), not an entry of its AREA section.
- **Clip ID** of a checkpoint: the byte at offset 0x14 of a CKPT entry (KMPExpander calls it ClipID). −1 (255 in the
  file) means none.
- **Culling target kart**: the kart whose camera is shown, normally the player's. Every cell is hidden or visible for
  its camera and its checkpoint, for everything on screen, the other karts included.
- **Occlusion object**: a KMP object with object ID 10 (`occlusion`), which hides cells from the camera's position
  ([Occlusion objects](#occlusion-objects)).

### The grid

The div file is a flat list of rectangles, one per index stream ([The div file format](#the-div-file-format)). The
game builds the grid from it when the course loads ([Finding 2](#2-building-the-quadtree)):

1. The game takes the bounding box of all the div areas. That rectangle becomes the root cell, and the tree is always
   three levels deep below it: 1 + 4 + 16 + 64 = 85 cells. The 64 leaf cells are an even 8 × 8 grid over it. On Mario
   Circuit the rectangle is 9292 × 9402 units, so a leaf cell is 1161 × 1175.
2. For each div area it notes **which of the 64 leaf cells its rectangle touches** (touching an edge counts)
   ([Finding 3](#3-attaching-the-div-areas-to-the-tree)). Only that list decides whether the div area is drawn.
3. It reads the clip objects and marks, in each cell, the clip IDs whose clip quad holds that cell entirely
   ([Clip objects](#clip-objects-hiding-cells-in-front-of-the-camera)).

The grid depends only on the bounding box of all the div areas: a single div area far from the rest makes the whole
grid, and every cell, bigger. A course without a `.div` file has no grid and is never culled
([Finding 1](#1-loading-the-div-file)).

### Which cells are hidden in a frame

Every frame, on a thread of its own, the game goes through the cells from the root down
([Finding 6](#6-the-update-of-each-frame)):

1. **Clip ID**: a cell marked with the clip ID of the checkpoint the culling target kart is in is hidden, with every
   cell inside it.
2. **Camera**: otherwise, a cell that lies entirely outside the camera's view, seen from above, is hidden with every cell
   inside it. The test uses the cell grown by a small margin (2.5% of a leaf cell on each side), so a cell that only
   just misses the view stays visible.
3. Otherwise the cell is visible, and the four cells inside it are tested the same way.
4. Then each occlusion object can hide more cells.

The root, the cell of the whole course, is never hidden by the clip ID or by the camera; only an occlusion object can
hide it. The result is the list of visible leaf cells.

### Clip objects: hiding cells in front of the camera

The camera's test cannot know that a wall or a hill blocks the view: it hides only what is behind or beside the camera
([The camera](#the-camera-hiding-what-is-behind-and-beside-it)). Clip objects tell the game, for each part of the
course, what cannot be seen from there. Three parts of the KMP work together ([Finding 4](#4-clip-objects-and-the-clip-id)):

1. A **route** of four points, the clip quad, drawn around the region to hide. The points go in order around the quad,
   which must be **convex**: the game takes the inside of each edge to be the side where the first other point lies.
   Their heights do not matter.
2. A **clip object** (object ID 30) that links that route (its route ID) to a clip ID (its setting 1), from 0 to 31.
3. **Checkpoints** with that clip ID. While the culling target kart is in one of them, the cells inside the clip quads
   of every clip object with that clip ID are hidden, wherever the camera looks.

How the game applies them:

- **Only whole cells are hidden.** At load time, every cell (except the root) that lies **entirely** inside a clip quad,
  all four of its corners, is marked with the clip object's clip ID, together with every cell inside it. A cell only
  partly inside is not marked; the smaller cells inside it that are entirely inside are. Each clip quad is tested on its
  own: a cell that is half in one clip quad and half in another with the same clip ID is not hidden. This is why the
  retail clip quads are huge, reaching thousands of units beyond the course.
- **The checkpoint that counts** is the one the game's latest checkpoint search found for the culling target kart; while
  the kart is outside every checkpoint, the last one found. So the clip ID changes as soon as the kart enters another
  checkpoint, and a misplaced checkpoint that the search finds (a "ghost" checkpoint, see the research on ghost
  checkpoints) can change it unexpectedly. A clip ID of −1 (255 in the file) hides nothing.
- **Clip IDs go from 0 to 31**: the marks are 32 bits. A checkpoint's clip ID of 32 or more hides nothing, and a clip
  object's clip ID from 32 to 255 marks nothing; a clip object's clip ID of 256 or more counts as its remainder after
  division by 256.
- **Only the first 32 clip objects of the GOBJ section are read.** Wario Shipyard has 40: its clip IDs 12, 13 and 14
  only have clip objects after the 32nd, and in game they mark no cell, so the checkpoints using them hide nothing.
- **Clip IDs and routes can be shared.** A checkpoint has a single clip ID, so every region that should be hidden from
  it needs a clip object with that clip ID; several clip objects may share a clip ID, and one route may serve several
  clip IDs. Mario Circuit's route 19 serves clip IDs 1 and 2, route 20 clip IDs 2, 3 and 4.

### The camera: hiding what is behind and beside it

The game does not cull by distance or height: it flattens the camera's view onto the ground (the XZ plane) and hides
the cells that lie entirely outside that flat shape ([Findings 6](#6-the-update-of-each-frame) and
[11](#11-the-race-camera)).

Seen from above, the shape is a wedge. It starts on a short line 1.5 units in front of the camera, across the direction
the camera looks, and opens to both sides at the camera's horizontal field of view: about 78 to 84 degrees for the race
camera, wider at top speed. It reaches 50000 units ahead, much farther than any course, so nothing is hidden for being
far away. When the camera looks down, as the race camera always does a little, the game cuts the lower part of the view
where it reaches the bottom of the course model (and the upper part at the top of the model when the camera looks up),
which changes the sides of the wedge a little ([The view region](#the-view-region)).

- **Behind the camera**: every cell that lies entirely behind the wedge's starting line, by more than the margin, is
  hidden.
- **Beside the camera**: every cell that lies entirely beyond one of the wedge's two sides is hidden.
- **Above and below**: height plays no part. Geometry above or below the camera is culled only by where it is on the
  ground.

Because a leaf cell is an eighth of the course wide, the cell the camera is in, and every cell the wedge's edges cross,
stay visible, together with every div area that touches them. In practice the camera hides the cells well behind it and
some cells far to the sides; what is ahead is left to the clip objects.

### Occlusion objects

An occlusion object (object ID 10, `occlusion`) stands for something solid that the camera cannot see through, such as
a big rock or a building. Like a clip object, it takes a quad from the first four points of its route; the quad should
cover the solid thing's footprint, seen from above. Unlike a clip object, it does not depend on checkpoints or clip IDs:
every frame, the game works out the "shadow" the quad casts away from the camera, as if the camera were a lamp, and
hides every cell that lies entirely in that shadow ([Finding 5](#5-occlusion-objects)).

The shadow is built in three steps:

1. The game takes the line from the camera to the centre of the quad (the average of its four points).
2. It picks the quad point furthest to the left of that line and the one furthest to the right: the two outer corners
   of the quad as the camera sees it, `L` and `R` below.
3. The shadow is everything between the line from the camera through `L` and the line from the camera through `R`,
   beyond the side of the quad that faces the camera. It contains the quad itself and has no far end: it reaches the
   edge of the course.

```
   \ . . . . . . . . . . . . . /
    \ . . . . . shadow . . . . /
     \ . . . . . . . . . . . /
      L-------- quad -------R
       \                   /
        \                 /
         \               /
          \             /
           \           /
              camera
```

What follows from this:

- **Only the view from above counts.** Heights are ignored, so the quad works like a wall of endless height: whatever
  is behind it from the camera's point of view is hidden, even a mountain tall enough to be seen over it, or the ground
  behind a low wall seen from a camera high above. An occlusion object only suits something taller than everything
  behind it, from every place the camera can be.
- **It works from every side.** The shadow always points away from the camera, so the same object hides the far side
  from wherever the camera is.
- **Whole cells only**, as with clip quads: a cell is hidden only when all of it, grown by the same small margin as in
  the camera test, is in the shadow. Next to the quad the shadow is about as wide as the quad, so it rarely holds a whole cell there; it widens
  with distance, so a narrow quad mostly hides cells far behind it.
- **It hides objects and karts too**, like any hidden cell ([Objects, items and karts](#objects-items-and-karts)).
- **The culling code reads only its route**: not its settings. At most 8 occlusion objects are read; the others are
  ignored.
- **KMPExpander does not show occlusion objects** in its preview
  ([Seeing the culling in KMPExpander](#seeing-the-culling-in-kmpexpander)).

Among the retail courses only Koopa Troopa Beach (`Gn64_KoopaTroopaBeach`) has one: GOBJ entry 21, with route 5, a long
and narrow quad about 4,600 to 5,200 units long and 850 to 900 wide. How it behaves in game was not tested.

### When a div area is drawn

A div area, and so its index stream, is drawn while at least one of the leaf cells it touches is visible
([Finding 7](#7-showing-and-hiding-index-streams)):

- **Showing is immediate, hiding is spread over 8 frames.** Hidden index streams are tested every frame; visible ones
  only one frame in eight (each frame tests a different eighth of them). The list of visible cells itself follows a
  change a frame or two late, since another thread computes it: in game, forcing a clip ID hid 19 index streams over 8
  to 12 frames.
- A mesh is skipped entirely once all its index streams are hidden.
- Each index stream is switched on its own: in game, with every leaf cell but the one under the start line hidden, the
  road around the kart stays while the far barriers, the buildings and Lakitu disappear.

### The `_perm` model: never culled

The course's `.bcmdl` holds a second model, `<course>_perm`, which the game draws with an actor of its own. Culling
never hides any of it, wherever the camera is: the div file describes only the course model, and only the course
model's index streams are shown and hidden ([Finding 1](#1-loading-the-div-file)). Since the grid comes from the div
areas, the `_perm` model does not make the grid bigger either ([Finding 2](#2-building-the-quadtree)).

### Objects, items and karts

Objects, items, coins and karts never look at div areas: each one is hidden with the cell it is in
([Finding 8](#8-objects-items-coins-and-karts); this comes from the code and was not tested in game):

- Each one takes a square around its position (its radius on each side), made a little smaller by the margin, and goes
  into the **smallest cell that holds the square entirely**. It is drawn while that cell is visible; some of them also
  test their own circle against the camera's view.
- Karts, the CPUs included, do this every frame with a radius of 20 units, so a kart nearly always sits in a leaf cell,
  and disappears when that leaf cell is hidden by a clip ID or by the camera. A clip quad that hides a stretch of track
  hides the karts driving there too.
- Objects take a radius from their model's bounding box, scale and rotation; moving objects change cell as they move.
  A big object, or one on the line between two cells, sits in a bigger cell, which is hidden only when all of it is,
  so it is culled less. An object whose square reaches out of the grid goes to the root, which only an occlusion
  object can hide.
- The distance of the cell from the camera is also what objects use to pick their level of detail and to disappear
  beyond their draw distance.

### Why big div areas break culling

Each div area is tested on its own, against the leaf cells it touches. What makes big div areas, and badly made div
files in general, cull badly ([Findings 3](#3-attaching-the-div-areas-to-the-tree),
[4](#4-clip-objects-and-the-clip-id), [7](#7-showing-and-hiding-index-streams) and
[10](#10-culling-of-different-divisions)):

1. **A div area is drawn if any leaf cell it touches is visible.** A rectangle that spans four leaf cells needs all
   four hidden. A rectangle that spans half the course is practically always drawn, with all its triangles.
2. **The grid comes from the bounding box of all the div areas.** Geometry far from the track (a big sea or ground
   plane, a distant backdrop in the course model) enlarges every leaf cell, so every div area touches cells that are
   almost always in view.
3. **Clip quads hide whole cells only.** A div area that lies inside a clip quad is still drawn if one of its leaf
   cells is not entirely inside the clip quad.
4. **Touching counts.** A rectangle that ends exactly on a cell's edge also touches the next cell.
5. **Wide triangles widen their div area.** A single long triangle in an index stream stretches its rectangle over
   many cells and takes the rest of the stream's triangles with it.

### How the retail div files were made

Every retail div file matches one rule ([Finding 9](#9-how-the-retail-div-files-were-made)): take the 8 × 8 grid over
the XZ bounding box of the whole course model (the same grid the game builds); for each shape, put each triangle into
the leaf cell that holds the centre of the triangle's XZ bounding box; make one index stream of each non-empty leaf
cell; write its bounding box as the div area. Over the 40 retail courses this puts 98.8% of the triangles into the same
group as Nintendo's files; the others are next to a cell's edge and were probably grouped by the polygon they came from
(two triangles of one quad kept together) before the model was triangulated. The header value 1000 has nothing to do
with it.

KMPExpander's original generator made div areas of about 1000 × 1000 units from the triangles' minimum corners,
whatever the course's size, so its div areas did not follow the game's grid. KMPExpander 2.1 uses the retail rule.

### Seeing the culling in KMPExpander

KMPExpander 2.1 makes div files with the retail rule and previews what the game culls, with the rules of this
document. The div areas, the grid and the culling are drawn only in the top view (the XZ view plane, in 2D).

- **Making a div file**: File, Create Div opens the course model, splits each mesh into one index stream per
  leaf cell as the retail files are split, saves the split model as a `.bcmdl` and loads the div file made for it; Save
  Div writes the div file. Open Div loads an existing one.
- **The grid**: while a div file is loaded and checked in the tree, its 8 × 8 grid of leaf cells is drawn over it, in
  the div colour. Without a div file, a loaded OBJ of the course model gives the grid, as if a div file were made from
  it.
- **A checkpoint's clip ID**: selecting a checkpoint fills the clip quads of its clip ID (the four-point routes of the
  clip objects with that clip ID) with a faint route colour, shades the leaf cells the game hides for it, and draws only
  the div areas the game hides (none when its clip ID hides nothing). A loaded OBJ loses the triangles the game would
  not draw. Only routes of exactly four points are shown as clip quads.
- **The kart simulator**: the Kart Simulator section, at the end of the tree, holds eight karts that are not saved in
  the KMP. Checking it shows the enabled karts; selecting one, or turning on Kart Camera, previews the culling for it as
  the culling target kart (the **camera kart**). The section's settings choose what hides cells: Clip ID culling (on at
  first) and Camera view culling (off at first), which draws the camera's flattened view as a translucent orange cone.
  Only the div areas and OBJ triangles the game would draw stay on screen.
- **Karts**: the camera kart is drawn as an orange arrow and the others as blue arrows, faded where the game would not
  draw them. In the grid view, the Shown column says "drawn" or "hidden"; the ClipID and HiddenCells columns give the
  camera kart's clip ID and how many of the 64 leaf cells are hidden.
- **Driving**: Drive Karts drives the enabled karts along the enemy points as CPUs would, and Reset Karts puts them
  back on the start grid. The camera kart's checkpoint comes from the game's checkpoint search, so ghost checkpoints
  change its clip ID as in the game. Kart Camera looks through its race camera in the 3D view.
- **Statistics**: View, Triangle statistics shows at the top right of the map how many OBJ triangles, div areas and
  other karts are drawn, out of their totals.
- **Error checker**: it warns when there are more than 32 clip objects.

The preview does not show the delay of up to 8 frames with which the game hides div areas, nor occlusion objects.

### Guide for custom course creators

1. **Always ship a `.div` file**, made for the same course model. Without one the course model is never culled.
2. **Split the model like the retail files**: one index stream per mesh and leaf cell, with triangles assigned by the
   centre of their bounding box. KMPExpander's Create Div does this.
3. **Keep the course model tight.** The game's grid spans every div area. Far-away scenery in the course model makes
   every leaf cell bigger: put it in the skybox or in the `_perm` model, or keep it close. Check the size of a leaf
   cell: the course's width and depth divided by 8.
4. **Use the `_perm` model for what is always seen.** It is never culled and does not count for the grid, so it suits
   backdrops visible from everywhere; everything that should be culled goes in the course model.
5. **Avoid long triangles** that cross several cells: cut big floors and walls along the grid lines (every eighth of
   the course) so that each index stream stays inside one cell.
6. **Plan the clip IDs from the checkpoints.** For each stretch of checkpoints, decide what cannot be seen from there,
   and give those checkpoints one clip ID. For each region to hide, make a four-point route around it and a clip object
   (object ID 30) with that route as its route ID and the clip ID as its setting 1.
7. **Make clip quads convex and generous.** Four route points, in order around the quad. A cell is hidden only when all
   of it is inside one clip quad: draw the quads well past the cells to hide, as the retail courses do, using several
   clip objects with the same clip ID if one quad is not enough (each cell must still fit entirely in one of them).
8. **Use clip IDs 0 to 31, and at most 32 clip objects** in total. Clip objects after the 32nd are ignored.
9. **Set the clip ID on every checkpoint**, −1 (255) where nothing is hidden. The clip ID changes as soon as the kart
   enters the checkpoint, so give the checkpoints around a hidden region clip IDs that keep in view what can be seen
   from there, and check for ghost checkpoints, which can switch the clip ID unexpectedly.
10. **Remember that CPUs and objects in hidden cells disappear too**, and that a big object, or one on a cell's edge,
    is hidden only with a bigger cell.
11. **Expect a short delay when hiding**: div areas disappear over up to 8 frames, and appear at once, so a clip ID
    that hides too much shows up as geometry popping in, not as a delay.
12. **Do not count on the camera for what is ahead.** It only hides what is behind it and far to the sides, cell by
    cell; geometry in front of the camera but behind a wall or a hill is hidden only by clip IDs (or an occlusion
    object).
13. **Check it in KMPExpander**: select each checkpoint to see what its clip ID hides, then drive the simulated karts
    with Camera view culling on and Triangle statistics shown.

## Glossary

Offsets are those of `eur2`. Classes without a template so far are added by `course-culling.patch`.

### Field::QuadTree (size 0x140, template/Field/QuadTree.hpp)

The quadtree of the course, built once per race.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_cells` | 0x04 | `sead::PtrArray<QuadCell>` | new | 85 cells, level by level, each level in Morton order; leaf n is index 21 + n |
| `m_cell_num` | 0x18 | `s32` | new | 85 |
| `m_leaf_num` | 0x1C | `s32` | new | 64; `getCellImpl_` compares the Morton codes with it |
| `m_leaf_index_max` | 0x20 | `s32` | new | 7; clamp of `getLowestIndex` |
| `m_depth` | 0x24 | `u8` | new | 3, from `FieldDirector::createQuadTree` |
| `m_reset_requested` | 0x26 | `bool` | new | `update` calls `reset` and clears it |
| `m_rect_min`, `m_rect_max` | 0x28, 0x30 | `sead::Vector2f` | new | the root rectangle |
| `m_margin` | 0x38 | `sead::Vector2f` | new | 0.025 × `m_leaf_size` |
| `m_outer_min`, `m_outer_max` | 0x40, 0x48 | `sead::Vector2f` | new | the root rectangle grown by `m_margin`; `getCell` sends what goes beyond it to the root |
| `m_model_min`, `m_model_max` | 0x50, 0x5C | `sead::Vector3f` | new | `FieldModel::getModelAABB`, read by `convertTo` |
| `m_leaf_size` | 0x78 | `sead::Vector2f` | new | root size / 8 |
| `m_leaf_size_inv` | 0x80 | `sead::Vector2f` | new | |
| `m_use_clip_id` | 0x8C | `bool` | new | 1 at creation; when 0, `update` uses clip ID −1 |
| `m_visible_leaves` | 0x90 | `u64[2]` | new | the visible leaf cells, double buffered |
| `m_lap_rank_checker` | 0xB0 | `RaceSys::LapRankChecker *` | new | |
| `m_check_point_accessor` | 0xB4 | `MapdataCheckPointAccessor *` | new | |
| `m_invisible_walls` | 0xB8 | `sead::PtrArray<QuadInvisibleWall>` | new | one per occlusion object, at most 8 |
| `m_thread` | 0xE4 | `QuadTreeThread *` | new | holds the index of the current half of the double buffers |
| `m_result_ready` | 0xE8 | `bool` | new | set by `update`; `calcBeforeStructure` calls `changeStreamVisible` only while it is set, then clears it |
| `m_hide_all` | 0xE9 | `bool` | new | `update` hides every cell while it is set |

### Field::QuadCell (size 0xB0, template/Field/QuadTree.hpp)

One cell of the quadtree.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_index` | 0x04 | `u16` | new | Morton code in its level (bit 0 X, bit 1 Z, ...) |
| `m_level` | 0x06 | `u8` | new | 0 root .. 3 leaf |
| `m_has_children` | 0x07 | `bool` | new | |
| `m_prev_visible` | 0x09 | `bool` | new | copy of `m_visible` taken at the start of `update` |
| `m_pos`, `m_size` | 0x0C, 0x14 | `sead::Vector2f` | new | the cell rectangle; never changed after `setupRect` in practice ([Finding 3](#3-attaching-the-div-areas-to-the-tree)) |
| `m_corners` | 0x1C | `sead::Vector2f[4]` | new | from `rectFixed`; used by the clip quad test |
| `m_outer_corners` | 0x3C | `sead::Vector2f[4]` | new | corners pushed out by `QuadTree::m_margin`; used by the view test |
| `m_expand_limit_pos`, `m_expand_limit_size` | 0x5C, 0x64 | `sead::Vector2f` | new | `m_pos` − 0.85 leaf, 1.7 leaf; read by `expandRect` |
| `m_visible` | 0x70 | `bool[2]` | new | double buffered |
| `m_view_dist_min`, `m_view_dist_max` | 0x74, 0x7C | `f32[2]` | new | from `checkInside`; read by `getLodState` |
| `m_thread` | 0x84 | `QuadTreeThread *` | new | |
| `m_clip_id_flags` | 0x8C | `u32` | new | bit n: clip ID n hides the cell |
| `m_children` | 0x90 | `sead::PtrArray<QuadCell>` | new | buffer `m_children_buffer` at 0x9C |
| `m_parent` | 0xAC | `QuadCell *` | new | |

### Field::QuadCell::SClipData (size 0xA4, template/Field/QuadTree.hpp)

A convex region: the camera's view, a clip quad or an occlusion region.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_origin`, `m_dir` | 0x00, 0x08 | `sead::Vector2f` | new | camera position and direction, for `m_view_dist_min` / `m_view_dist_max` |
| `m_normals` | 0x10 | `sead::Vector2f[8]` | new | outward normal of each edge |
| `m_points` | 0x50 | `sead::Vector2f[8]` | new | a point of each edge |
| `m_edge_num` | 0x90 | `u8` | new | 4 for a clip quad, 3 or 4 for an occlusion region; 0 means no region |
| `m_min`, `m_max` | 0x94, 0x9C | `sead::Vector2f` | new | bounding box of `m_points` |

### Field::ClipContext (size 0x1C, template/Field/QuadTree.hpp)

The cell of an object, item, coin or kart.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_cell` | 0x00 | `QuadCell *` | new | set by `QuadTree::getClipContext` |
| `m_center` | 0x04 | `sead::Vector2f` | new | X, Z |
| `m_radius` | 0x0C | `f32` | new | |
| `m_field_director` | 0x10 | `FieldDirector *` | new | read by `isVisible_` for the circle test |
| `m_view_test` | 0x14 | `bool` | new | last argument of `getClipContext` |
| `m_was_visible` | 0x15 | `bool` | new | |
| `m_view_test_timer` | 0x18 | `f32` | new | |

### Field::FieldModel (size 0x98, template/Field/FieldModel.hpp)

The course model actor, created by `FieldDirector::createCourseActor`. Base `Object::Actor3DMdl` (0x58 bytes).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mesh_infos` | 0x68 | `sead::Buffer<MeshInfo>` | new | one per index stream of the model; on Mario Circuit 202 entries for 201 index streams, the last one left empty |
| `m_div_file` | 0x74 | `DivFile` | new | |
| `m_hide_slot` | 0x88 | `u32` | new | 0..7, advanced by `changeStreamVisible` every frame |
| `m_mesh_checker_num` | 0x8C | `s32` | new | |
| `m_mesh_checkers` | 0x90 | `sead::Buffer<MeshChecker>` | new | one per mesh |

### Field::FieldModel::MeshInfo (size 0x30, template/Field/FieldModel.hpp)

One index stream and its div area. The name is from the `dlp` symbols (`MeshInfo::MeshInfo`).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_cell` | 0x00 | `QuadCell *` | new | from `getCellForField`; only tested for null |
| `m_leaf_mask` | 0x08 | `u64` | new | from `getFlag` |
| `m_min`, `m_max` | 0x10, 0x18 | `sead::Vector2f` | new | the div area |
| `m_index_stream` | 0x20 | `void *` | new | the stream's resource; its byte 5 is its visibility |
| `m_shape` | 0x24 | `void *` | new | |
| `m_mesh_checker` | 0x28 | `MeshChecker *` | new | |

### Field::FieldModel::MeshChecker (size 0xC, template/Field/FieldModel.hpp)

One mesh of the model. The name is from the `dlp` symbols (`MeshChecker::MeshChecker`).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mesh` | 0x00 | `void *` | new | the mesh resource: shape index at 0x18, visibility at 0x24 |
| `m_stream_num` | 0x04 | `s16` | new | index streams of its shape |
| `m_visible_stream_num` | 0x06 | `s16` | new | the mesh is drawn while it is not 0 |

### The div file format

All numbers are little endian. Offsets are from the start of the file.

| Offset | Size | Content |
| --- | --- | --- |
| 0x00 | 4 | `BADC` |
| 0x04 | 4 | file size |
| 0x08 | 4 | header size, 16 |
| 0x0C | 4 | 1000 in every retail file; **the game never reads it** |
| 0x10 | 4 | `PAHS` |
| 0x14 | 4 | number of shapes (the game reads only the low 16 bits) |
| 0x18 | | one block per shape, in the order of the course model's shapes |

Each shape block is `MRTS`, a 16-bit number of div areas (the number of index streams of the shape), a 16-bit vertex
count of the shape (not read by the game), then one div area per index stream, in the order of the streams: minimum X,
minimum Z, maximum X, maximum Z, four floats. In every retail file each div area is exactly the XZ bounding box of the
vertices of its index stream ([Finding 9](#9-how-the-retail-div-files-were-made)).

### Field::DivFile (size 0x14, template/Field/DivFile.hpp)

The loaded `.div` file. Nested `SStream` (0x8: `m_magic`, `m_area_num`, `m_vertex_num`) and `SArea` (0x10: `m_min`,
`m_max`) describe the file's blocks ([The div file format](#the-div-file-format)).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_file` | 0x00 | `void *` | new | null when the course has no `.div` |
| `m_stream_num` | 0x04 | `u16` | new | file offset 0x14 |
| `m_streams` | 0x08 | `sead::PtrArray<SStream>` | new | |

### Field::CameraData (size 0xA0, template/Field/QuadTree.hpp)

The copy of the camera that `QuadTreeThread` hands to `QuadTree::update`; two of them at +0xB8 of the
`QuadTreeThread`, 0xA0 bytes apart, one per half of its double buffer. The name is from the `dlp` symbols
(`QuadTree::update(const Field::CameraData&)`).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_position` | 0x00 | `sead::Vector3f` | new | |
| `m_far` | 0x10 | `f32` | new | 50000 in game |
| `m_dir` | 0x14 | `sead::Vector3f` | new | unit view direction |
| `m_corners` | 0x3C | `sead::Vector3f[8]` | new | bit 0 bottom, bit 1 near, bit 2 the other side; 0, 1, 4 and 5 are far |

### Other classes

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `Field::FieldDirector::m_field_model` | 0x40 | `FieldModel *` | new | |
| `Field::FieldDirector::m_quad_tree` | 0x50 | `QuadTree *` | new | |
| `Field::MapdataCheckPointData::m_clip_id` | 0x14 | `s8` | new | was an unnamed `u8`; read with `ldrsb` |
| `Kart::Director::m_culling_target_player_id` | 0x30 | `s32` | existing | |
| `RaceSys::LapRankChecker::KartInfo::m_previous_checkpoint_index` | 0x0C | `u8` | existing | the checkpoint whose clip ID is used |
| `Field::MapdataGeoObjData::m_route_id`, `m_settings` | 0x28, 0x2A | `s16`, `u16[8]` | existing | `m_settings[0]` is the clip ID of a clip object |

### Functions

| Name | Address (eur2) | Status | Note |
| --- | --- | --- | --- |
| `Field::FieldModel::FieldModel` | 0x0034000C | existing | body continues at 0x00340034 (`sub_00340034`) |
| `Field::FieldModel::attachCells` | 0x0033F54C | existing | |
| `Field::FieldModel::changeStreamVisible` | 0x0033FD30 | existing | |
| `Field::FieldModel::getModelRect` | 0x0033FBC4 | existing | |
| `Field::FieldModel::getModelAABB` | 0x0033FA64 | existing | |
| `Field::FieldModel::MeshChecker::MeshChecker` | 0x0033F530 | existing | |
| `Field::FieldModel::MeshInfo::MeshInfo` | 0x0033FE4C | existing | |
| `Field::FieldDirector::createCourseActor` | 0x00355F70 | existing | |
| `Field::FieldModelPermanent::FieldModelPermanent` | 0x003A252C | existing | the `_perm` model |
| `Field::FieldDirector::createQuadTree` | 0x0035585C | existing | |
| `Field::FieldDirector::calcBeforeStructure` | 0x003560F8 | existing | calls `changeStreamVisible` |
| `Field::DivFile::setFile` | 0x003BBC48 | existing | |
| `Field::DivFile::getMinMax` | 0x003BBCD0 | existing | |
| `Field::DivFile::getTotalMinMax` | 0x003BBB44 | existing | |
| `Field::QuadTree::QuadTree` | 0x003BF958 | existing | |
| `Field::QuadTree::reset` | 0x003BE678 | existing | |
| `Field::QuadTree::update` | 0x003BE718 | existing | `sub_003be718` in the symbol maps; `dlp` name, 97% equal |
| `Field::QuadTree::convertTo` | 0x003BEF9C | existing | `sub_003bef9c`; `dlp` name, 100% equal |
| `Field::QuadTree::rectFixed` | 0x003BF888 | existing | |
| `Field::QuadTree::getCellForField` | 0x003BEBA8 | existing | falls into `getCell` with its last argument 1 |
| `Field::QuadTree::getCell` | 0x003BEBB4 | existing | |
| `Field::QuadTree::getCellImpl_` | 0x003BE1C0 | existing | |
| `Field::QuadTree::getLowestIndex` | 0x003BE3AC | existing | |
| `Field::QuadTree::getFlag` | 0x003BEE90 | existing | |
| `Field::QuadTree::getClipContext` | 0x003BE318 | existing | |
| `Field::QuadCell::expandRect` | 0x003BDA30 | existing | |
| `Field::QuadCell::checkInside` | 0x003BDB2C | existing | |
| `Field::QuadCell::checkWholeInside` | 0x003BDC68 | existing | |
| `Field::QuadCell::checkClipInternal` | 0x003BDD04 | existing | `sub_003bdd04`; `dlp` name, 95% equal |
| `Field::QuadCell::checkWallInternal` | 0x003BDDF0 | existing | `sub_003bddf0`; `dlp` name, 97% equal |
| `Field::QuadCell::setInvisibleInternal` | 0x003BDE78 | existing | `sub_003bde78`; `dlp` name, 92% equal |
| `Field::QuadCell::setupManualClipInternal` | 0x003BDF0C | existing | |
| `Field::QuadCell::setManualClipFlagInternal` | 0x003BDFD0 | existing | |
| `Field::QuadCell::setupRect` | 0x003BE02C | existing | |
| `Field::QuadInvisibleWall::getClipInfo` | 0x003965D8 | existing | |
| `Field::QuadTreeThread::calcInner_` | 0x00378B70 | existing | calls `update` |
| `Field::ClipContext::isVisible_` | 0x00344F28 | existing | |
| `Field::getLodState` | 0x003489FC | existing | |
| `Field::MapdataGeoObjAccessor::collect_AllPointer` | 0x003A86B4 | existing | |
| `Field::ObjectSimpleModelBase::initQTClipContext` | 0x003AB7D0 | existing | |
| `Field::ObjectSimpleModelBase::updateQTClipContext` | 0x003ABAD4 | existing | |
| `Field::ObjectSimpleModelBase::updateClipParam_final` | 0x003ABC1C | existing | |
| `Kart::Unit::calcDraw` | 0x002EE634 | existing | |

### Data

| Name | Address (eur2) | Note |
| --- | --- | --- |
| far corner table | 0x005EEB08 | `u32` 0, 1, 4, 5: the far corners of `CameraData::m_corners` that `convertTo` may pull in |
| level start table | 0x005EEB18 | `u32` 1, 5, 21, 85, 341, ...: number of cells above each level |
| kart draw parameters | 0x00664A08 | `.bss`, filled at run time; the float at +0xC is the kart's culling radius (20.0 on Mario Circuit) |

## Findings

### Sources and method

- Decompiled (`mk7 decomp`) and disassembled (`mk7 dis`) the functions of the [Functions](#functions) table in `eur2`;
  names that `eur2` lacks were ported from `dlp` (`mk7 port`) where the bodies match.
- In Azahar, on a Mario Circuit time trial: read the whole tree, every cell and every `MeshInfo`, and compared them with
  a model of the functions written in Python; forced clip IDs by writing `m_clip_id` of every checkpoint and read the
  results; took screenshots with cells hidden. On Wario Shipyard: read the clip ID marks of every cell.
- Parsed the 40 retail `.div` files and the course models of their `.bcmdl` (CGFX: shapes, index streams, interleaved
  positions) to compare each div area with the triangles of its index stream, and to test generation rules, with
  [the tool](#12-the-model-course_cullingpy).
- In Azahar (Mario Circuit): read the `CameraData` the quadtree thread uses at six positions, and while the AI drove the
  player's kart.

### 1. Loading the div file

- `FieldModel::FieldModel` first calls `DivFile::setFile(&m_div_file, 0)`, then asks for the course resource with the
  extension `"div"` (`RaceSys::GetCourseResourceNameExt(..., "div")`), and calls `setFile` with it only if it exists.
- `DivFile::setFile` stores the file, reads `u16` at file offset 0x14 into `m_stream_num`, and walks the blocks from
  offset 0x18: `iVar2 = iVar2 + *(ushort *)(iVar2 + 4) * 0x10 + 8`. Nothing reads offsets 0x04 to 0x13 or the `u16` at
  +6 of a block (`getMinMax` reads `block + 8 + index * 0x10`, `getTotalMinMax` the same, with the count at +4).
- `FieldModel::getModelRect` returns `DivFile::getTotalMinMax` when `m_div_file.m_file` is set, otherwise the union of
  the shapes' bounding boxes. `attachCells` sets cells only `if (*(int *)(param_1 + 0x74) != 0 && iVar9 != 0)`, so
  without a div file every `MeshInfo::m_cell` stays null, and `changeStreamVisible` skips those (`if (*piVar8 != 0)`):
  nothing is culled.
- In every retail file, offset 0x0C is 1000 and the block's vertex count is the shape's vertex count.
- `FieldDirector::createCourseActor` stores the `FieldModel` in `m_field_model` (`str r5, [r4, #0x40]`) and creates the
  `<course>_perm` model as a `FieldModelPermanent`. `attachCells` and `changeStreamVisible` have one caller each, which
  passes `m_field_model`, so the `_perm` model is never culled by the quadtree.

### 2. Building the quadtree

`FieldDirector::createQuadTree`:

```
FieldModel::getModelRect(m_field_model, &rect);
m_quad_tree = new QuadTree(3, rect);
FieldModel::attachCells(m_field_model, m_quad_tree);
QuadTree::rectFixed(m_quad_tree);
FieldModel::getModelAABB(...) -> m_quad_tree->m_model_min / m_model_max
// then the occlusion objects (ID 10) and the clip objects (ID 30)
```

- The depth is the constant 3. `QuadTree::QuadTree` allocates `table[depth]` cells (the level start table: 85), links
  each cell of a level to its four children at `table[level] + index * 4 + k`, and sets `m_leaf_size = rect.size / (1 <<
  depth)`, `m_margin = m_leaf_size * 0.025` (`vldr s0, =0.025f`), `m_outer_min/max` = rectangle ± margin.
- `QuadCell::setupRect` gives the children the quarters of the parent rectangle: child 0 at (x, z), 1 at (x + w/2, z),
  2 at (x, z + h/2), 3 at (x + w/2, z + h/2). With `getLowestIndex` (X bits on the even positions, Z bits on the odd
  ones) this is Morton order.
- `setupRect` sets `m_expand_limit_pos = m_pos − 1.7 × leaf × 0.5` and `m_expand_limit_size = 1.7 × leaf` (`vldr s1,
  =1.7f`, `vmls`), the same leaf size for every level.
- In game (Mario Circuit): `m_depth` 3, `m_rect_min` (−4993.1, −4532.9), `m_rect_max` (4298.8, 4868.7), which is the
  bounding box of the 201 div areas; `m_leaf_size` (1161.48, 1175.20); `m_margin` (29.04, 29.38); all 85 cell
  rectangles equal to the even grid.

### 3. Attaching the div areas to the tree

`FieldModel::attachCells` walks the course model's shapes (shape index s), their primitive sets, primitives and index
streams (index k within the primitive). For each index stream with a bounding box resource:

```
DivFile::getMinMax(&m_div_file, &min, &max, s, k);
info.m_cell = QuadTree::getCellForField(tree, &aabb);
info.m_min/max = aabb;  info.m_index_stream = stream;  info.m_shape = shape;
info.m_leaf_mask = QuadTree::getFlag(tree, &aabb);
info.m_mesh_checker = first MeshChecker whose mesh has shape index s;  ++checker.m_stream_num;
```

#### The leaf mask

`QuadTree::getFlag` returns 0 if `m_depth > 3`, otherwise loops over the `table[depth] − table[depth − 1]` = 64 leaf
cells and sets bit n when `aabb.min.x <= cell.x + cell.w && cell.x <= aabb.max.x` and the same in Z: touching counts. In
game, the 201 `MeshInfo::m_leaf_mask` of Mario Circuit equal the Python model of this test.

#### The cell, and a wrong index

`getCellForField` clamps the rectangle to the root and enters `getCell` with its last argument 1: it takes the Morton
code of the leaf that holds the centre (`getLowestIndex`, 0..63), then `expandRect(m_cells[code], ...)` and, if that
returns 1, returns `m_cells[code]` (`ldr r0, [r1, r5, lsl #2]`): **the code is used as an index into all 85 cells**,
without adding the 21 cells above the leaves. Otherwise `getCellImpl_` shrinks the rectangle by `m_margin` (to its
centre if it inverts), takes the Morton codes of its two corners and returns the cell of their common prefix (level
`(clz(a ^ b) >> 1) − 16 + depth`).

`expandRect` returns 1 when the rectangle is inside the cell; otherwise it would grow the cell within `m_expand_limit`,
but that area is centred on the cell's minimum corner and only 1.7 leaf cells wide, so it never holds the cell itself
and the function returns 0. In game no cell of Mario Circuit was grown, and one area (`(−2164.4, −2364.7)`–`(−1822.1,
−2322.4)`, centre in leaf code 6) was linked to `m_cells[6]`, a level-2 cell, where the model of `getCellImpl_` gives
leaf 27; the other 200 matched.

`MeshInfo::m_cell` is only tested for null (Finding 7), so neither effect changes what is drawn.

### 4. Clip objects and the clip ID

#### Setting up the marks

In `createQuadTree`, `MapdataGeoObjAccessor::collect_AllPointer(accessor, 0x1E, &array, 0x20)` collects the clip
objects; it returns as soon as it has counted `0x20` of them (`if (uVar1 == param_4 || ...) return`), so only the first
32 are read. For each, the route `m_route_id` gives four points: point i while the route has more than i points; for i
equal to the number of points, point 0 again when the route's `m_route_setting_2` (header byte 3) is 0; otherwise the
previous value is kept. For each edge (i, i+1 mod 4) the normal is `(dz, −dx)`, flipped when the first point that is
not on the edge lies on its positive side, and normalized. Then
`QuadCell::setupManualClipInternal(root, &clipData, (s16)m_settings[0])` (`ldrsh r2, [r1, #0x2a]`):

- if the cell is not the root (`m_level != 0`) and is wholly inside (`checkWholeInside(..., 0)`: every one of
  `m_corners` has `dot(corner − point, normal) <= 0` for every edge), set bit `1 << id` of `m_clip_id_flags` in the
  cell and, through `setManualClipFlagInternal`, in all its descendants;
- otherwise recurse into the children.

The root is never marked. The shift is `orr r0, r1, r0, lsl r6`, which uses only the low byte of the ID: a shift of 32
or more gives 0, so IDs 32 to 255 set nothing, and an ID of 256 or more acts as its low byte. On the checkpoint side the
ID is a signed byte, so 32 to 127 hide nothing.

In game, Mario Circuit's marks were `0x6` (IDs 1 and 2, route 19), `0x1C` (2, 3, 4, route 20) and `0x28` (3, 5,
route 18), on the cells inside those routes, as the KMP's seven clip objects give. Wario Shipyard has 40 clip objects;
in game the union of all marks was `0xFFF` (IDs 0 to 11), and the objects with IDs 12, 13 and 14 are the 33rd to 40th.

#### Choosing the clip ID

In `QuadTree::update`, when `m_lap_rank_checker` and `m_check_point_accessor` are set: the player index is
`Kart::Director::m_culling_target_player_id` (the race's director list, `+0x10`, `+0x30`), the kart info is
`m_kart_infos[player]`, `ldrb r0, [r0, #0xc]` reads `KartInfo::m_previous_checkpoint_index`, and `ldrsb r3, [r0, #0x14]`
reads that checkpoint's `m_clip_id`. If `m_use_clip_id` is 0 the ID is −1. The ID goes to `checkClipInternal`, which
hides a cell and its subtree `if (id >= 0 && (m_clip_id_flags & (1 << id)))`. `LapRankChecker::calcLapPosition_`
writes `m_previous_checkpoint_index` with the result of `Field::FindSector` whenever that result is not negative, so it
is the checkpoint of the latest search, and stays the last one found while the kart is outside every checkpoint.

In game (Mario Circuit, start line), writing `m_clip_id` of all checkpoints and stepping 12 frames:

| Clip ID | Visible leaves | Leaves marked for the ID |
| --- | --- | --- |
| none | `0x1F0104FFFF` | |
| 2 | `0x1F0104FEFF` | `0xFAF00100` |
| 3 | `0x00104FEFF` | `0x5FDF00000100` |
| 5 | `0x000104FFFF` | `0x5FDF00000000` |
| 40 | `0x1F0104FFFF` | none |

Every visible leaf marked for the ID disappeared, and no other.

### 5. Occlusion objects

`createQuadTree` calls `MapdataGeoObjAccessor::collect_AllPointer(accessor, 10, &array, 8)`, so it reads at most 8
objects with ID 10, takes four route points of each the same way as for clip objects (Finding 4), and stores them in a
new `QuadInvisibleWall` (0x2C bytes: a vtable at 0x00, the four points as X, Z pairs at 0x04, and their centre at 0x24,
the sum of the four points times 0.25, `DAT_00355c88`), added to `QuadTree::m_invisible_walls`. Only the object's
`m_route_id` (+0x28) is read.

Every frame `update` calls `QuadInvisibleWall::getClipInfo(wall, &clipData, camera)` with the `CameraData` it was
given, whose first member is `m_position`. `getClipInfo` (X and Z only):

1. `d = normalize(centre − camera)`. For each point `p`, `s = d.z·(p.x − camera.x) − d.x·(p.z − camera.z)`, the signed
   distance of `p` from the line through the camera and the centre. `R` is the point with the largest `s > 0`, `L` the
   point with the smallest `s <= 0` (the starting bounds are 1 and −1, `DAT_00396998`, `DAT_0039699c`, so any point on
   the right side qualifies). With no `R` or no `L` (all points on one side, which for four points around their own
   centre means all of them on the line), `m_edge_num = 0` and nothing is hidden.
2. Of the two other points, the last one with `(R.z − L.z)·(p.x − L.x) − (R.x − L.x)·(p.z − L.z) > 0` becomes `N`. With
   the camera in front of the quad, that is the camera's side of the line `L`–`R`: `N` is a near corner.
3. Without `N`: 3 edges, through the points `L`, `L`, `R`, along `camera − L`, `R − L` and `R − camera`. With `N`: 4
   edges, through `L`, `L`, `R`, `R`, along `camera − L`, `N − L`, `R − N` and `R − camera`. Each direction `(a, b)`
   becomes the normal `(b, −a)`, normalized; `m_origin` is the camera position, and `m_min` / `m_max` the bounding box
   of `m_points`, which `checkWholeInside` does not use.

`checkWholeInside` counts a cell as inside when every corner has `dot(corner − point, normal) <= 0` for every edge. With
the camera at the origin, the centre straight ahead and `L` and `R` level with it, the edges along `camera − L` and
`R − camera` keep the side between the two rays, and the edge along `R − L` (or the two through `N`) keeps the side away
from the camera: the region is the quad and everything behind it as seen from the camera, unbounded, cut by the
camera's side of the quad. `L` and `R` are chosen by distance from the centre line, not by angle, so for a deep quad
seen at a slant the two rays can cut slightly into the quad; and when both other points lie on the camera's side only
the later one bounds the region.

If the root is visible and wholly inside the region (`checkWholeInside(..., 1)`, with the margin) every cell is hidden;
otherwise `checkWallInternal` (`0x003BDDF0`) goes down from each child of the root and hides each still-visible cell
that is wholly inside (`checkWholeInside(..., 1)`), with its subtree, and recurses into the children of the others.
Among the retail KMPs, only Koopa Troopa Beach has an object with ID 10 (GOBJ entry 21, route 5). Not tested in game.

### 6. The update of each frame

`QuadTreeThread::calcInner_` calls `QuadTree::update(camera)`, which:

1. If `m_hide_all`: clears `m_visible` of all 85 cells (the loop runs to `m_cell_num`), sets `m_visible_leaves` to 0,
   sets `m_result_ready` and returns.
2. Copies `m_visible` into `m_prev_visible` and marks every cell visible; calls `reset` if `m_reset_requested`.
3. `convertTo` turns the camera into an `SClipData` ([The view region](#the-view-region)).
4. Picks the clip ID (Finding 4) and calls `checkClipInternal(root, view, id)`: a cell marked for the ID is hidden with
   its subtree (`setInvisibleInternal`); otherwise `checkInside(cell, view, &near, &far, 1)` tests `m_outer_corners`:
   the cell is outside when, for some edge, all four corners have `dot >= 0`. Outside: hidden with its subtree. Inside:
   visible, `m_view_dist_min/max` set from the corners' distances along the camera direction, children tested.
   `checkInside` skips the edge test for the root (`if (m_level != 0 && m_edge_num != 0)`), and the root is never
   marked (Finding 4), so the root stays visible here.
5. Occlusion objects (Finding 5).
6. Builds the 64-bit mask of leaves whose `m_visible` is set, stores it in `m_visible_leaves` and sets
   `m_result_ready`.

`m_visible`, `m_view_dist_min/max` and `m_visible_leaves` are double buffered: `update` writes the half
`1 − m_thread->[0xB0]`, readers use `m_thread->[0xB0]`. `QuadTreeThread::calcInner_` copies the `CameraData` of its
current half (`param_1 + 0xb8 + index * 0xa0`) under a critical section before calling `update`.

#### The view region

`QuadTree::convertTo(tree, &clipData, &camera)`:

1. Copies the 8 `m_corners`.
2. For each axis a (X, Y, Z) with `|m_dir[a]| >= 1.19e-7` (`cmp r2, #0x34000000` on the absolute value): `t = (m_model_min[a]
   − m_position[a]) / m_dir[a]`; if not `0 <= t < m_far`, the same with `m_model_max[a]`; the smallest t wins. The side
   (−1 for the minimum, +1 for the maximum, `mvngt r2, #0` / `movgt r2, #1`) is kept only when the winner is Y (`cmp r0,
   #1`); otherwise it is 0.
3. If the side is not 0, for the far corners 0, 1, 4 and 5 (the far corner table): the ray from `m_position` to the
   corner, normalized; if its Y is not tiny, the distance to `m_model_min.y` (side −1) or `m_model_max.y` (side +1)
   along it, and the corner moves there when that distance is not negative and shorter than the corner's own.
4. For each of the 12 edges of the view volume (`(0,1), (0,2), (0,4), (1,3), (1,5), (2,3), (2,6), (3,7), (4,5), (4,6),
   (5,7), (6,7)`, built by a guarded static table): the line through the two corners on the XZ plane, normal `(dz,
   −dx)`. The edge is a side of the shape when the other six corners are all on one side (`fVar21 * fVar20 < 0` rejects
   it). With 8 edges already, `m_edge_num = 0` and the function returns: no view culling. The normal is normalized and
   turned outwards; an edge whose normal equals one already kept (within ±1.19e-7 on both axes) is skipped; the edge is
   kept only when a corner of the XZ rectangle of `m_model_min`/`m_model_max` lies outside it.
5. `m_min`/`m_max` become the bounding box of the kept points.

In game this was checked by reading `CameraData`, the model box and `m_visible_leaves` at six positions on Mario Circuit
and computing the mask with `course_culling.py viewmask`: the computation matched the game at all six with step 3 as
described, and at only four of them without it. At the start line: `m_position` (354.2, 414.2, −1995.0), `m_dir`
(−0.968, −0.251, 0), near corners 1.5 units ahead, `m_far` 50000; side −1 (the view reaches the bottom of the model,
`m_model_min.y` −526.6, after 3748 units); corners 1 and 5 move to 1793 units; five edges, among them the near edge
with normal (1, 0) through x = 352.9; mask `0x1F0104FFFF`.

### 7. Showing and hiding index streams

`FieldModel::changeStreamVisible` is called by `FieldDirector::calcBeforeStructure` when `QuadTree::m_result_ready`
is set, which then clears it (`strb r8, [r0, #0xe8]` with r8 = 0). In game the flag was set every frame: stepping one
frame at a time, `m_hide_slot` advanced by one each frame.

```
m_hide_slot = (m_hide_slot + 1) & 7;
for (i = 0; i < m_mesh_infos.size; i++) {
    info = m_mesh_infos[i];
    if (!info.m_cell) continue;
    was = info.m_index_stream->visible;              // byte at +5
    if (was && (i & 7) != m_hide_slot) continue;      // visible streams: one frame in eight
    now = (info.m_leaf_mask & tree->m_visible_leaves[current]) != 0;
    if (was != now) {
        info.m_index_stream->visible = now;
        checker.m_visible_stream_num += now ? 1 : -1;
        mesh->visible = checker.m_visible_stream_num != 0;   // byte at +0x24 of the mesh
    }
}
```

In game (Mario Circuit), after forcing clip ID 3, the number of streams whose visibility disagreed with the mask went
19, 18, 14, 1, 0 at 1, 2, 4, 8 and 12 frames (in the fact check, starting from clip ID 2: 19, 16, 10, 4, 0); after
restoring the IDs all agreed. The mask itself is computed on the quadtree thread and changes a frame or two after the
clip ID, which is why some streams were still visible 8 frames after the change. Screenshots: with every cell marked
and the clip ID forced, the whole course model disappeared (sky, the player's kart and background models remained);
with every leaf but leaf 24 (the start line) marked, the road around the kart stayed, the far barriers, buildings and
Lakitu disappeared, so the renderer skips hidden index streams one by one.

### 8. Objects, items, coins and karts

- `QuadTree::getClipContext(tree, ctx, pos, radius, viewTest)` builds the square `pos.xz ± radius` and calls `getCell(...,
  0)`, then stores the cell, the centre, the radius and `viewTest` (`m_view_test`) and clears `m_was_visible`.
- `getCell` with its last argument 0: if the square leaves the root by more than the margin on any side
  (`< m_outer_min` or `> m_outer_max`), it returns the root; otherwise it clamps the square to the root and returns
  `getCellImpl_` (the smallest cell that holds it after shrinking by the margin). The leaf path of Finding 3 is not
  taken.
- `ClipContext::isVisible_` returns 0 when `m_cell->m_visible[current]` is 0; with `m_view_test` it also tests the
  circle against two edges kept by `m_field_director` (not analysed). Those are the two normals that `convertTo` writes
  at `QuadTree` + 0x68 and + 0x70, which `calcBeforeStructure` copies to `FieldDirector` + 0x84 to + 0x90.
- A `ClipContext` in the root is hidden only by an occlusion object (Findings 4 and 6).
- `Kart::Unit::calcDraw` calls `getClipContext` every frame with `vldr s0, [r8, #0xc]` from the kart draw parameters
  (20.0 read in game) and `viewTest` 1, then `isVisible_`.
- `ObjectSimpleModelBase::initQTClipContext` (only when `ObjectBase::m_update_culling`) computes the radius from the
  model's bounding box (`initClipParam_fromAABB`, `updateClipParam_byScale`, `updateClipParam_final`), and calls
  `getClipContext` with the position plus the clip centre offset; `updateQTClipContext` repeats the call for moving
  objects. Items (`Item::ItemObjBase::_calcBaseAfter`), coins (`Object::CoinManager`) and several objects of their own
  call `getClipContext` too.
- `Field::getLodState` returns `CULLED` when the cell's `m_view_dist_min` (scaled) is at least the object's draw
  distance (a value of its `ObjectParameter::Parameter`), and otherwise picks a level of detail from
  `m_view_dist_min/max` and the distance to the camera.

### 9. How the retail div files were made

- For all 40 courses, each div area equals the XZ bounding box of the vertices of its index stream (largest difference
  0), the number of areas of a block equals the index streams of the shape, and the blocks follow the shapes.
- Rule tested: grid = 8 × 8 over the bounding box of all the areas; key of a triangle = cell of the centre of its XZ
  bounding box. 249 397 of 252 321 triangles (98.8%) have the key that most triangles of their own stream have; the
  number of streams (8084) is close to the number of distinct (shape, key) pairs (8048). Using the centroid instead
  gives worse results (127 against 73 misplaced triangles on Mario Circuit), and shifting or resizing the grid does not
  improve on the exact bounds.
- About 70% of the misplaced triangles share an edge with a triangle of the stream such that the pair's centre falls in
  the stream's cell, which fits a split done on polygons before triangulation.
- KMPExpander's original generator sorts by minimum Z, makes strips while `minZ − first <= 1000`, sorts each strip by
  minimum X and makes groups while `minX − first <= 1000`.

### 10. Culling of different divisions

The retail models were re-divided with the three rules and evaluated with the game's tests (Findings 3, 4 and 7):
"leaves" is the average number of leaf cells an area touches, weighted by triangles; "hidden" is the share of triangles
hidden by the clip IDs, averaged over all checkpoints. "Retail rule" is the rule of Finding 9;
"by span" puts together the triangles whose bounding boxes cover the same range of leaf cells.

| Course | Leaf cell | Retail file | Retail rule | Old KMPExpander | By span |
| --- | --- | --- | --- | --- | --- |
| Mario Circuit | 1161 × 1175 | 201 areas, 4.13 leaves, 4.8% | 202, 4.16, 4.5% | 170, 3.60, 5.0% | 406, 1.25, 7.7% |
| N64 Luigi Raceway | 571 × 1001 | 201, 3.44, 14.5% | 201, 3.37, 14.5% | 115, 4.53, 13.6% | 395, 1.29, 16.2% |
| Toad Circuit | 849 × 889 | 252, 3.35, 4.4% | 251, 3.29, 4.5% | 157, 3.92, 4.3% | 486, 1.24, 8.1% |
| Wii Mushroom Gorge | 1071 × 1076 | 223, 3.92, 16.8% | 225, 3.67, 17.5% | 190, 3.72, 17.4% | 436, 1.32, 25.5% |
| DK Jungle | 1234 × 1136 | 246, 4.63, 44.4% | 242, 4.44, 45.1% | 195, 3.59, 47.9% | 493, 1.26, 55.2% |
| Wuhu Island Loop | 2432 × 2397 | 248, 3.91, 38.8% | 244, 3.77, 39.0% | 517, 1.99, 43.8% | 481, 1.13, 46.7% |

On these models, made for the retail rule, the old generator culls about as well; the retail rule's areas touch about
four leaf cells each because a stream's triangles stick out of their cell. Grouping by span halves the leaves touched
and culls more, at the cost of about twice as many index streams.

### 11. The race camera

`CameraData` read every 30 frames while the AI drove the player's kart on Mario Circuit (`--player cpu`): the camera
was 55 to 68 units behind the kart and 20 to 40 above it, looking 7 to 22 degrees down; the near corners were 1.5 units
ahead and the far ones 50000; the far face's half height over its distance was 0.488 at cruising speed and up to 0.543
at top speed, its half width 0.813 to 0.905, a 5:3 view.

### 12. The model: course_culling.py

`course_culling.py` re-implements, from the functions of this document: the CGFX reading of a course model (shapes,
primitive sets, primitives, index streams with their triangle lists or strips, the interleaved vertex buffer of usage
0x15 and its position attribute with format, scale and offset, plus the shape's position offset), the div and KMP
reading (clip objects in GOBJ order, routes, checkpoints' clip IDs), `getFlag` (leaf mask), `checkWholeInside` with the
clip quads' edge orientation, the 32-object and 0-to-31 limits, `convertTo` and the view test of `checkInside`, and the
three ways of dividing a model of Finding 10. Its commands:

- `check`: for all 40 courses, every div area equals its index stream's bounding box (largest difference 0), and the
  counts and vertex counts agree (Finding 9).
- `rule`: the 98.84% of Finding 9.
- `compare`: the table of Finding 10.
- `viewmask`: the visible leaf cells for a `CameraData`, as in [The view region](#the-view-region).

## Confidence

- **Certain** (code and in game): the tree's depth, rectangle and grid; the leaf mask and its use for index streams;
  the 8-frame hiding; per-stream drawing; the clip marks, the 32-object limit, the IDs from 0 to 31, the clip ID read
  from `m_previous_checkpoint_index` of the culling target kart; `expandRect` never growing a cell; the wrong index in
  `getCellForField` and that it does not matter for drawing; the kart radius of 20 on Mario Circuit; courses without a
  `.div` not being culled (code only); the root never being marked or tested against the view (code, and no mark on
  the root in game on Mario Circuit and Wario Shipyard).
- **Certain** (data): the div file layout, the areas being the streams' bounding boxes, the header value being unused.
- **Certain** (code and in game): the view region of `convertTo` (six positions on one course).
- **Certain** (code): the occlusion region being the quad and the part behind it as seen from the camera.
- **Likely**: the retail generation rule (98.8% of triangles; the rest unexplained except for the polygon guess);
  objects' radius coming from their model's box; `m_far` being
  50000 on every course (read on Mario Circuit only).
- **Not tested in game**: CPU karts and objects disappearing in hidden cells (code only; Lakitu at the start line did
  disappear in the screenshot test of Finding 7, but which path culls it was not checked), occlusion objects.

## Open questions

- What writes `QuadTree::m_use_clip_id` and `m_hide_all` besides the constructor (multiplayer, replays, demos)?
- Which parameter file fills the kart draw parameters (the culling radius of 20)?
- Which two edges of the view region `convertTo` picks for the circle test of `ClipContext::isVisible_` (written at `QuadTree` + 0x68 and + 0x70, copied to `FieldDirector`).
- Why `FieldModel::m_mesh_infos` has one entry more than the index streams on Mario Circuit.
- Whether `Field::FieldModelBase` sits between `Object::Actor3DMdl` and `FieldModel`.
- Whether more index streams (as "by span" makes) cost noticeable drawing time on the console.
- Whether the remaining 1.2% of retail triangles follow another rule than source polygons.
- What `CameraData` holds between 0x0C and 0x3B (0x0C is 3.0, 0x20 a unit vector that is not perpendicular to
  `m_dir`).
- How the race camera's distance, height and angle depend on speed, boosts and the course.
