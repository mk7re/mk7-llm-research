# Review and verification steps for `Course culling: the div file, the quadtree and clip objects`

## Contents

- [How to verify](#how-to-verify): the commands that reproduce the key evidence
  - [Code](#code)
  - [Patches](#patches)
  - [Course data](#course-data)
  - [In game](#in-game)
- [Review](#review): the record of the review passes, one subsection per pass
  - [Fact check](#fact-check): what was re-checked against `eur2`, what was corrected, what remains uncertain
  - [Document review](#document-review): what was reworded for course creators, what was added, what is left open

## How to verify

### Code

From the repository root. The addresses are those of functions that have no name in the `eur2` symbol maps yet
(`update`, `convertTo`, `checkClipInternal`, `checkWallInternal`, `setInvisibleInternal`) or that the CLI cannot pick
by name; the names are in the glossary of `README.md`.

```
M=mk7-llm-research/mk7
$M decomp Field::DivFile::setFile Field::DivFile::getMinMax Field::DivFile::getTotalMinMax      # Finding 1
$M decomp 0x00340034                        # FieldModel::FieldModel body: "div", setFile only if found
$M decomp Field::FieldModel::getModelRect Field::FieldDirector::createQuadTree                    # Findings 1, 2, 4, 5
$M dis Field::FieldDirector::createCourseActor | grep "#0x40\]"                                   # m_field_model
$M xref Field::FieldModel::attachCells; $M xref 0x0033fd30                                         # one caller each
$M decomp Field::QuadTree::QuadTree Field::QuadCell::setupRect Field::QuadTree::rectFixed        # Finding 2
$M dis Field::QuadCell::setupRect | head -20                                                       # 1.7f, 0.5f, vmls
$M read 0x005eeb18 6                                                                               # level start table
$M decomp 0x0033f54c Field::QuadTree::getFlag Field::QuadTree::getCellImpl_ Field::QuadTree::getLowestIndex   # Finding 3
$M dis 0x003beba8 -n 0x120                  # getCellForField / getCell: ldr r0, [r1, r5, lsl #2] before expandRect
$M dis Field::QuadCell::expandRect
$M decomp Field::MapdataGeoObjAccessor::collect_AllPointer                                        # Finding 4: limit 0x20
$M dis Field::FieldDirector::createQuadTree | grep -B2 -A1 "setupManualClipInternal\|#0x1e$"     # ldrsh [r1, #0x2a]
$M decomp Field::QuadCell::setupManualClipInternal Field::QuadCell::setManualClipFlagInternal Field::QuadCell::checkWholeInside
$M dis 0x003be718 | grep -n "ldrb    r0, \[r0, #0xc\]\|ldrsb\|#0x8c\]\|#0x30\]"               # clip ID read (Finding 4)
$M decomp 0x003be718 0x003bdd04 0x003bddf0 0x003bde78 Field::QuadCell::checkInside              # Finding 6
$M decomp Field::QuadInvisibleWall::getClipInfo 0x003bef9c                                        # Findings 5, 6
$M xref 0x003be718                                                                                 # QuadTreeThread::calcInner_
$M decomp 0x0033fd30; $M xref 0x0033fd30                                                          # Finding 7
$M decomp Field::QuadTree::getClipContext Field::QuadTree::getCell Field::ClipContext::isVisible_  # Finding 8
$M dis 0x002ee634 -n 0x80                                                                          # Kart::Unit::calcDraw
$M decomp Field::ObjectSimpleModelBase::initQTClipContext Field::getLodState
$M xref Field::QuadTree::getClipContext
```

`mk7 port 0x0038e590` (and `0x0038ee14`, `0x0038db7c`, `0x0038dc68`, `0x0038dcf0`) shows the `dlp` functions whose
names the glossary gives to the unnamed `eur2` ones, with their share of equal words.

### Patches

```
W=mk7-llm-research/local/work/course-culling-div-review
mkdir -p $W/a $W/b && cp -r template $W/a/template && cp -r template $W/b/template
(cd $W/b && patch -p1 < ../../../../pending-verification/course-culling-div/course-culling.patch)
mk7-llm-research/mk7 --templates $W/b/template verify --version EUR_REV2
mk7-llm-research/mk7 --templates $W/b/template verify
git apply --check mk7-llm-research/pending-verification/course-culling-div/course-culling.patch
mk7-llm-research/mk7 --templates $W/b/template access 0x0033fd30 --as Field::FieldModel
mk7-llm-research/mk7 --templates $W/b/template access 0x003be718 --as Field::QuadTree
```

### Course data

```
mk7-llm-research/mk7 kmp dump Gctr_MarioCircuit -s GOBJ | grep " id=30 "         # 7 clip objects, routes 18-20
mk7-llm-research/mk7 kmp dump Gctr_MarioCircuit -s POTI:18-20
mk7-llm-research/mk7 kmp dump Gctr_WarioShip -s GOBJ | grep -c " id=30 "         # 40
mk7-llm-research/mk7 kmp dump Gn64_KoopaTroopaBeach -s GOBJ | grep " id=10 "     # the only occlusion object
```

Findings 9, 10 and 12 (and the computed masks of Finding 6) come from `course_culling.py` in this folder, which reads
the extracted RomFS (`mk7 romfs extract` first):

```
T=mk7-llm-research/pending-verification/course-culling-div/course_culling.py
python3 -I $T check all          # every line "largest difference=0 ... ok"
python3 -I $T rule all           # total ... 98.84%
python3 -I $T compare Gctr_MarioCircuit Gn64_LuigiCircuit Gctr_ToadCircuit Gwii_MushroomGorge Gctr_DKJungle Gctr_WuhuIsland1   # Finding 10
python3 -I $T viewmask CAMERA.json                       # see In game
```

### In game

`mk7 emu start --unlock`, `mk7 emu timetrial Gctr_MarioCircuit`, then a script on `mk7re.dynamic` (`Session`,
`Race`):

- `fd = u32(race.director_list() + 0x14)`, `qt = u32(fd + 0x50)`, `fm = u32(fd + 0x40)`.
- Tree: `u8(qt + 0x24)` = 3; floats at `qt + 0x28` (rectangle), `+0x38` (margin), `+0x78` (leaf size); the 85 cells
  from the `PtrArray` at `qt + 0x4` (count at `+0x4`, data at `+0xC`); per cell `m_pos`/`m_size` at `+0xC`, level at
  `+0x6`, `m_clip_id_flags` at `+0x8C`.
- Index streams: `sead::Buffer` at `fm + 0x68` (count, data), `0x30` bytes each: cell at `+0x0`, mask at `+0x8`, area at
  `+0x10`, stream at `+0x20` (visibility byte at `+5`).
- Visible leaves: `u64` at `qt + 0x90 + 8 * u32(u32(qt + 0xE4) + 0xB0)`.
- Clip test: the checkpoint data pointers are the first word of each entry of the accessor at
  `u32(u32(fd + 0x38) + 0x24) + 0xC`; write `m_clip_id` (`+0x14`) of all of them, `step(12)`, read the mask; restore.
- Wario Shipyard: OR of `m_clip_id_flags` over all cells = `0xFFF`.
- View region: `th = u32(qt + 0xE4)`; the `CameraData` of the current half is at `th + 0xB8 + 0xA0 * u32(th + 0xB0)`
  (`m_position` +0x0, `m_far` +0x10, `m_dir` +0x14, `m_corners` +0x3C); the model box is `qt + 0x50` / `qt + 0x5C`.
  Write them to a JSON file with `"rect"` = `qt + 0x28` .. `+0x34`, run `viewmask`, and compare with the visible leaves
  read in the same frame. Moving the kart (`Race.set_kart_pos`, a few steps of 10 frames) gives other positions; the
  camera follows it with a delay, so read the camera and the mask together.
- Race camera: `mk7 emu timetrial Gctr_MarioCircuit --player cpu`, `mk7 emu race-start`, then read `CameraData` and the
  kart position every 30 frames; the kart's direction is the change of its position.

## Review

### Fact check

Done on 2026-11-14, in a fresh context, against `eur2`.

#### What was re-checked, and how

- **Code** (`mk7 decomp`, `mk7 dis`, `mk7 read`, `mk7 xref`): every function of the glossary that the findings rely on,
  following the commands of [Code](#code): `DivFile::setFile`, `getMinMax`, `getTotalMinMax`; the `FieldModel` body
  (`"div"`, `setFile` only when found); `getModelRect`; `createCourseActor` (`new 0x98`, `str r5, [r4, #0x40]`, the
  `_perm` model); `createQuadTree` (depth 3, the order of the calls, `collect_AllPointer` with 8 occlusion and 0x20 clip
  objects, the route points, the edge normals, `ldrsh r2, [r1, #0x2a]`); `QuadTree::QuadTree` (level table, leaf size,
  margin 0.025, outer rectangle, the thread with two `CameraData` at +0xB8); `setupRect` (1.7, 0.5, the leaf size
  passed in s0/s1 at every level); `rectFixed`; `attachCells` (areas indexed by shape and by index stream within the
  primitive, `getCellForField`, `getFlag`, the `MeshChecker` search by shape index); `getFlag`, `getLowestIndex`,
  `getCell`, `getCellImpl_`, `expandRect` (the wrong index, and why a cell never grows); `update`; `convertTo` (the axis
  test, the Y side, the far-corner table 0, 1, 4, 5, the corner pulling, the 12-edge table, the 8-edge limit, the
  duplicate normals, the model rectangle test); `checkInside`, `checkWholeInside`, `checkClipInternal`,
  `checkWallInternal`, `setInvisibleInternal`, `setupManualClipInternal`, `setManualClipFlagInternal`;
  `changeStreamVisible` and its call in `calcBeforeStructure`; `getClipContext`, `isVisible_`, `Kart::Unit::calcDraw`
  (`vldr s0, [r8, #0xc]` on 0x00664A08), `ObjectSimpleModelBase::initQTClipContext` (gated by
  `ObjectBase::m_update_culling`), `getLodState`; the 20 callers of `getClipContext`; `LapRankChecker::calcLapPosition_`
  for `m_previous_checkpoint_index`.
- **Patch**: `git apply --check` on a fresh copy of `template/`, applied to its `b/` copy, `verify` for `EUR_REV2` and
  `USA_REV1`, both before and after the change below.
- **Course data**: an independent reading of the header of all 40 `.div` files (`BADC`, file size, 16, 1000, `PAHS`,
  the blocks ending exactly at the end of the file); `course_culling.py check all` (all 40 "largest difference=0 ...
  ok"), `rule all` (98.84%; a copy of the tool that prints the count gives 249 397 of 252 321), `compare` on the six
  courses (the table of Finding 10, identical); a script on the tool's functions for Mario Circuit (73 misplaced
  triangles by bounding-box centre, 127 by centroid) and over all courses for the pairing of misplaced triangles (2024
  of 2924, 69%); `kmp dump` of all 40 KMPs (occlusion objects only on Koopa Troopa Beach), of Mario Circuit (7 clip
  objects, routes 18 to 20) and of Wario Shipyard (40 clip objects, IDs 12 to 14 only from the 33rd; its checkpoints use
  IDs 12 and 14).
- **In game** (Azahar, `eur2`, time trials): on Mario Circuit, the tree (depth 3, rectangle, margin, leaf size, the 85
  cells on the even grid with 1, 4, 16 and 64 cells per level); the 201 leaf masks against a model of `getFlag` (all
  equal); the 201 linked cells against a model of `getCellForField` (all equal, with the one area linked by the wrong
  index to `m_cells[6]` where `getCellImpl_` gives 27); the visible leaves `0x1F0104FFFF` at the start line; the
  kart radius 20.0; the clip ID table of Finding 4 for IDs 2, 3, 5 and 40 (identical); the hiding over frames; the view
  region of `course_culling.py viewmask` against the game at the start line and two other positions (all three equal,
  with the five edges given in Finding 6 at the start line). On Wario Shipyard, the OR of all clip marks (`0xFFF`), with
  no mark on the root.

#### What was changed

- **Root cell**: `setupManualClipInternal` marks a cell only when `m_level != 0`, and `checkInside` skips the edge test
  for the root, so the root is never hidden by a clip ID or by the camera. Added to the overview (Which cells are
  visible, Clip objects and clip IDs, Objects), to Findings 4, 6 and 8, and to `## Confidence`. "An object whose square
  reaches out of the course's rectangle ... is practically never culled" became "... which only an occlusion object can
  hide".
- **IDs of 32 or more**: the shift is `lsl` by register, which uses the low byte of the ID. A clip object's ID of 256 or
  more is not ignored but acts as its low byte; the checkpoint's ID is a signed byte, so there 32 to 127 hide nothing.
  Corrected in the overview and Finding 4.
- **The route points** of a clip quad: "point 0 again when a closed route has fewer" said more than the code shows. The
  code repeats point 0 only for the point index equal to the number of points, and only when `m_route_setting_2` is 0;
  nothing in the evidence says that this byte means a closed route. Reworded in Finding 4.
- **The checkpoint whose clip ID is used**: "even when the kart's respawn checkpoint has not changed" had no finding
  behind it. `calcLapPosition_` writes `m_previous_checkpoint_index` with every non-negative result of `FindSector`, so
  it is the latest checkpoint found, kept while the kart is outside every checkpoint. The overview and Finding 4 say so
  now.
- **`m_hide_all`**: `update` clears `m_visible` of all 85 cells, not only of the leaves (the loop runs to
  `m_cell_num`). Corrected in Finding 6 and the glossary.
- **`changeStreamVisible`** is not called unconditionally every frame: `calcBeforeStructure` calls it only while the
  byte at `QuadTree` + 0xE8 is set (by `update`, at both of its ends), and clears it after the call. Named
  `QuadTree::m_result_ready`, added to the glossary, to Findings 6 and 7, and to `course-culling.patch`. In game it was
  set every frame (`m_hide_slot` advanced by one on each of 40 single-frame steps).
- **The 8-frame hiding**: re-measured after forcing clip ID 3 (from clip ID 2): 19, 16, 10, 4, 0 streams disagreeing
  at 1, 2, 4, 8 and 12 frames, against 19, 18, 14, 1, 0 in pass 1. Both fit 8 slots once the mask has changed, which
  happens a frame or two later on the quadtree thread. The overview said "hid 19 index streams over 8 frames"; it now
  says 8 to 12 frames and why. Finding 7 gives both measurements.
- **Finding 9**: "249 397 ... triangles are in the stream that holds most triangles of their key" described another
  measure than the one the tool computes, which is the share of triangles whose key is the most common key of their own
  stream. Reworded; the numbers are unchanged.
- **`FieldModel::m_mesh_infos`**: on Mario Circuit it has 202 entries for the 201 index streams; the last one stays
  empty (null cell, zero area). Noted in the glossary and as an open question.
- **Open questions**: `calcBeforeStructure` copies the two normals that `convertTo` writes at `QuadTree` + 0x68 and +
  0x70 to `FieldDirector` + 0x84 to + 0x90, which are the two edges `ClipContext::isVisible_` reads. The two questions
  became one, and Finding 8 says so.
- **Base commit**: `template/` has moved on by five commits since b4f8117. The patch still applied; regenerated on
  db0fec5 (only the line numbers of the `forward.hpp` hunk changed, besides the new member), and `Base commit` updated.

#### What remains uncertain

- Not re-checked in game: the race camera of Finding 11, the screenshots of Finding 7, CPU karts and objects
  disappearing in hidden cells (still code only, as `## Confidence` says), and the occlusion objects.
- The region of `QuadInvisibleWall::getClipInfo` was not followed line by line, in pass 1 or here.
- Why `m_mesh_infos` has one spare entry was not looked into.

### Document review

Done on 2026-11-14, in a fresh context. The user asked for the overview to be written for custom course creators
(the follow-up in `Asked`), so most of the work is there.

#### What was changed

- **Overview rewritten** for course creators, without changing what a claim says: it now opens with what culling does
  in plain words (the grid, the two things that hide cells, the div file, objects and karts, the `_perm` model), then
  answers the questions asked one by one. The view region (eight corners, pulled corners, the five edges at Mario
  Circuit's start line) is described as a wedge, and the corner details are left to Finding 6, which already had them.
- **New subsections**: [Clip objects: hiding cells in front of the camera](README.md#clip-objects-hiding-cells-in-front-of-the-camera)
  explains how a route, a clip object (object ID 30, route ID, setting 1) and the checkpoints' clip IDs work together;
  [The `_perm` model: never culled](README.md#the-_perm-model-never-culled) gathers what Findings 1 and 2 say about it
  (it was only in the word list and the guide); [Seeing the culling in KMPExpander](README.md#seeing-the-culling-in-kmpexpander)
  describes how KMPExpander 2.1 makes div files and draws the culling.
- **Renamed and reordered**: "Which cells are visible in a frame" became "Which cells are hidden in a frame", "Clip
  objects and clip IDs" and "What the camera hides" got headings that say what they do; occlusion objects come right
  after the camera, in the order the game applies them. The contents list follows.
- **Wording**: "div area" everywhere a bare "area" could be read as a KMP AREA entry; "clip quad", "visible", "root" and
  "occlusion object" are now introduced in the word list before use; the guide gained steps for planning clip IDs, the
  `_perm` model and checking the result in KMPExpander.
- **Address in part 2**: Finding 6 named the far corner table by its address; it is now named, and listed in the
  `### Data` table (0x005EEB08, `u32` 0, 1, 4, 5, read with `mk7 read`).
- **Patch**: the comments follow the comment rules of PATCHES.md. `git apply --check` passes on `template/` at db0fec5,
  and `verify` passes for `EUR_REV2` and `USA_REV1` on a fresh copy with the patch applied. Not regenerated, as nothing
  in it changed.

#### What was found and not resolved

- The KMPExpander statements of the overview describe KMPExpander 2.1 (upstream 3ebc650), read from its source:
  Create Div, the grid in the div colour, the checkpoint preview, the Kart Simulator section and its Clip ID culling and
  Camera view culling settings, the Shown, ClipID and HiddenCells columns, Drive Karts, Reset Karts, Kart Camera,
  Triangle statistics and the 32-clip-object warning. They were not run in this pass. The research on the KMPExpander
  culling preview is older than 2.1 in places (it names a Race Start button, which 2.1 calls Reset Karts, and says the
  game's checkpoint search is not reproduced, which 2.1 does) and should be brought up to date.
- Finding 8 and the open questions refer to two members by offset (`QuadTree` + 0x68 and + 0x70, `FieldDirector`
  + 0x84 to + 0x90), against the naming rule of WRITING.md. They are the normals of the circle test, whose meaning is
  an open question; naming them means adding them to the patch, which was left to the user.
- Nothing that looks factually wrong was found.

