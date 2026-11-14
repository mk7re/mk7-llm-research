# Review and verification steps for `Course areas and cameras (KMP AREA / CAME)`

## Contents

- [How to verify](#how-to-verify): the commands that reproduce the key evidence
  - [The patch](#the-patch)
  - [Areas](#areas)
  - [Demo cameras](#demo-cameras)
  - [Effect, moving road and sound areas](#effect-moving-road-and-sound-areas)
  - [Course data](#course-data)
  - [Empty sections](#empty-sections)
  - [In game](#in-game)
- [Review](#review): added by passes 2 and 3
  - [Fact check](#fact-check)
  - [Document review](#document-review)
  - [Names added after the document review](#names-added-after-the-document-review)

## How to verify

Commands run from the repository root; `mk7` is `mk7-llm-research/mk7`.

### The patch

```
git apply --check mk7-llm-research/final/kmp-areas-and-cameras/areas-and-cameras.patch
W=mk7-llm-research/local/work/kmp-areas-and-cameras-check
mkdir -p $W/b && cp -r template $W/b/template && (cd $W/b && patch -p1 < ../../../../final/kmp-areas-and-cameras/areas-and-cameras.patch)
mk7 --templates $W/b/template verify --version EUR_REV2
mk7 --templates $W/b/template verify
```

### Areas

[Finding 1](README.md#1-area-entries-and-their-shapes) and [Finding 2](README.md#2-readers-of-each-area-type):

```
mk7 decomp Field::MapdataAreaAccessor::constructLocal 0x00396e98 0x003b0b24
mk7 read 0x00396f74 3          # 500, 1000 (box)
mk7 read 0x003b0c08 2          # 500 (cylinder)
mk7 dis 0x0050a5f4             # box test, Y from 0 (constant at 0x0050a6b8)
mk7 dis 0x0050aa60             # cylinder test, Y compared with the top only
mk7 xref Field::GetAreaAccessor
mk7 decomp Field::MapdataCourseAccessor::constructLocal   # type 0xc for CORS
```

### Demo cameras

[Findings 3 to 10](README.md#3-building-the-demo-cameras):

```
mk7 decomp Demo::DemoCameraDirector::create Demo::DemoCameraDirector::createCamera_
mk7 dis Demo::DemoCameraDirector::create | grep -B8 createCamera_     # bool argument: fp (0) or 1 for the last
mk7 read 0x002b32d0 8 && mk7 vtable 0x00625d9c && mk7 vtable 0x00625ddc
mk7 decomp Demo::DemoCameraDirector::calcInAreaIndex_ Demo::DemoCameraDirector::stateNormal
mk7 dis Demo::DemoCameraDirector::startGoalDemo                       # m_goal_camera loaded, never stored
mk7 diff --to eur0 --at 0x002b2db4 && mk7 diff --to eur1 --at 0x002b2f74   # startGoalDemo, the same in v1.0 and v1.1
mk7 access --class Demo::DemoCameraDirector | grep 0x0060
mk7 decomp Demo::DemoCameraBase::init Demo::DemoCameraBase::calc Demo::DemoCameraBase::calcEnd
mk7 decomp Demo::CameraPath::updateSpeed Field::PathBase::createRail Field::PathBase::calc
mk7 dis 0x002b48e8 && mk7 dis 0x002b4890                              # moving look-at point
mk7 decomp 0x002b4c34 0x002b4bac                                      # last intro camera
mk7 dis 0x002b2ac0 && mk7 dis 0x002b4414 && mk7 dis 0x002b47c4        # follow cameras
mk7 dis Kart::Camera::init | grep -B1 '#0xe[048]\]'                    # m_up_dir copied from the vehicle
mk7 dis 0x002f1e18 -n 0xb0                                            # calcDraw: look-at minus position -> m_look_dir
mk7 decomp Demo::DemoCameraDirector::stateCourse Demo::DemoCameraDirector::stateInitCourse Demo::DemoCameraDirector::changeCourseCamera
mk7 read 0x005eea30 4                                                 # 232, 204, 240, then string bytes
mk7 decomp Kart::Unit::calcDraw Sequence::DemoPage::onPagePreStep
mk7 decomp Camera::KartCameraDirector::initBeforeStructure Camera::KartCameraDirector::calcInner
mk7 decomp Demo::DemoCameraDirector::stateWinningRun Demo::DemoCameraDirector::startWatchImage Demo::DemoCameraDirector::stateInitWatchImage
```

### Effect, moving road and sound areas

[Findings 11 to 13](README.md#11-environment-effect-areas):

```
mk7 decomp Effect::KartEffect::_calcEnvEffect                         # m_env_area_index stored last, -1 for none
mk7 dis Effect::KartEffect::_calcCameraParam                          # str r0, [r4, #0x6a0]: m_camera
mk7 dis Kart::VehicleMove::calcGndCollision | grep -B6 'str.*#0xd14\]'  # m_gnd_col_type = attribute & 0x1f
mk7 decomp Kart::PullPath::init Kart::PullPath::update Kart::PullPathData::PullPathData
mk7 dis Kart::VehicleMove::calcGndCollision | sed -n '/002d7204/,/002d7248/p'   # 0xc -> PullPath::update
mk7 decomp Sound::SndAreaMgr::initArea Sound::SndAreaMgr::calcArea Sound::SndAreaMgr::setArea Sound::SndAreaMgr::calcPathArea Sound::SndPathData::update
mk7 dis Sound::SndAreaMgr::create                                     # three buffers of 0x28 bytes
mk7 read 0x003c7280 14 && mk7 read 0x003c65ec 17 && mk7 read 0x003c6be8 20
mk7 dis Sound::SndSceneRace::isAirshipOutside && mk7 xref Sound::SndSceneRace::isAirshipOutside
```

The sound names come from the string table of `mk7-llm-research/local/romfs/eur2/rom/Sound/ctr_dash.bcsar`: the INFO
block's sound table entry number `ID & 0xFFFFFF` has its string ID in its first optional value (option flags bit 0, at
+0x18 of the entry), an index into the STRG string table. No tool of the workspace reads BCSAR; the research used a
throwaway script.

### Course data

[Finding 15](README.md#15-values-used-by-the-original-courses):

```
mk7 kmp list
mk7 kmp dump Gctr_MarioCircuit -s AREA -s CAME -s POTI:2 -s POTI:14 -s POTI:15
mk7 kmp dump Gctr_WinningRun -s CAME
mk7 kmp dump Gwii_KoopaCape -s AREA
ls mk7-llm-research/local/romfs/eur2/rom/UI/mobiclip/
```

`mk7 kmp fields` still shows the CAME fields as community names, also with `--templates` pointing at the patched copy.

### Empty sections

[Finding 18](README.md#18-the-empty-sections-cnpt-mspt-and-cors):

```
mk7 kmp list --base                                  # CNPT, MSPT, CORS: 0 in every row
for f in mk7-llm-research/local/romfs/eur2/rom/Patch/Course/*/*.kmp; do mk7 kmp dump $f -s CNPT -s MSPT -s CORS; done
mk7 decomp Util::JmpResource::mount Util::JmpResource::search
mk7 read 0x00302b38 1                                # 0xc1c, the lowest version accepted
mk7 decomp Field::JmpResourceCourse::mount           # +0x40, +0x44, +0x4c; no null check after search
mk7 read 0x0038eb40 10                               # vtables and the magics CNPT, MSPT, STGI, CORS
mk7 vtable 0x0063dc08; mk7 vtable 0x0063e730; mk7 vtable 0x0063b4cc
mk7 decomp 0x005d0b8c 0x005d0c10 Field::MapdataCourseAccessor::constructLocal
mk7 dis 0x005d0b8c; mk7 dis 0x005d0b04               # getPosture on the entry, as for the start points
mk7 xref 0x0063dc08; mk7 xref 0x0063e730; mk7 xref 0x0063b4cc
mk7 sym -i dlp -r "CannonPoint|MissionPoint|MapdataCourse"
mk7 kmp dump Gwii_MapleTreeway -s GLPH -s GLPT       # glide path 0 starts at the cannon
mk7 kmp dump Gwii_MapleTreeway -s GOBJ:59
mk7 kmp fields GLPH                                  # +0x0F -> VehicleMove +0xE81
mk7 decomp Field::ObjectWiiCannon::setReaction_fromKart   # tests +0xE81
```

The two code scans for readers of the course info and of the area type were throwaway scripts, described in the finding;
re-doing one of them (or a Ghidra search for reads of `CourseInfo` +0x40, +0x44, +0x4C) is the way to check the
"no reader" claim.

The patch names `position` and `rotation` in the CNPT and MSPT entries; `mk7 kmp fields CNPT MSPT` still shows no layout
for them, also with `--templates` pointing at the patched copy, because the tool's layouts are written in its code.

### In game

[Finding 16](README.md#16-in-game-tests). The director is `u32(u32(u32(CameraEngine + 0x1C)) + 0x5C)`, with the camera
engine from `Game.scene_engine("Camera")` of `mk7re.dynamic.game`; its state is the byte at +0x18 and the current camera
at +0x5C.

```
mk7 emu start --unlock
mk7 emu timetrial Gctr_ToadCircuit --player cpu
mk7 emu call 0x002B1BEC <m_goal_camera>        # DemoCameraBase::init, during the race
mk7 emu write 0x002B3348 5c0084e5              # startGoalDemo: str r0, [r4, #0x5c]
mk7 emu race-start                             # then step until the director's state is 4 (GOAL)
mk7 emu call 0x003DD8CC <KartCameraDirector> 1  # requestChangeMode(DEMO)
mk7 emu step 30 && mk7 emu screenshot shot.png
```

[Finding 10](README.md#10-award-ceremony-and-live-view) and [Finding 17](README.md#17-what-each-effect-slot-shows):

```
mk7 decomp Sequence::BaseMenuPage::applySetting_WinningRun
strings -t x mk7-llm-research/local/romfs/eur2/rom/RaceCommon.szs.d/Effect/GPUPtclEnv0.bin | head -90
mk7 decomp Effect::EnvEffectGPU::_createCommandCache Effect::ParticleDrawer::setEnvEffectFlag
```

The rows start two rows (2 × 43 × 4 bytes) after the column names. In a race, the particle drawer is
`u32(u32(RenderEngine + 0x1C) + 0x30)`; its texture table is at `+0x38` (texture *i* at `+0x230 + 4i`) and its four
effect objects at `+0x48` to `+0x54` (shader type, texture index and texture count at +0x4C, +0x50, +0x54). The textures
were decoded from the CTPK with a throwaway ETC1A4 decoder (4×4 blocks, each 8 bytes of 4-bit alpha then an ETC1 block,
in 8×8 tiles of 2×2 blocks, image stored bottom-up).

## Review

### Fact check

Pass 2, 2026-11-14, on `eur2`.

**Patch rebased.** It no longer applied: commits `a469430` and `0ad5c6d` changed `template/Demo/DemoCameraDirector.hpp`
after the base commit (a `TLinkNode` at +0x08, `m_area_cameras` with its own comment, both arrays typed
`PtrArray<Demo::DemoCameraBase>`, +0x9F named `s8 m_area_camera_index`, state `INIT` renamed `WAIT`). The hunk was merged
by hand on a fresh work copy of `db0fec5`, which is now the base commit. Where the repository and the topic disagreed:

- +0x40: the repository's comment says the array leaves out the goal camera and cameras whose field 0x2 is 0. `create`
  builds an area camera only when the CAME type is not 0 **and** `m_video_next == 0`, so cameras with a non-zero field
  0x2 are the ones left out. The patch's comment now says both conditions.
- +0x9F: `start` stores `index >> 31` (1 when the kart is in no area); `stateNormal` and `stateGoal` store only 0 and 1 and
  compare it with 0. It is a flag, so the topic's `bool m_is_out_of_area` replaces `s8 m_area_camera_index`.
- `INIT` is `WAIT` in the document now.

**Re-checked in the code**, by decompiling or disassembling every function the findings cite: the area accessor, both
calculators and their tests, with the constants 500 and 1000 (Finding 1); the callers of `GetAreaAccessor` and
`GetCameraAccessor` (2); `create`, its three `createCamera_` calls and the bool on the stack, the jump table and all nine
vtables, including the goal and follow vtables slot by slot (3, 7); `calcInAreaIndex_`, `changeCamera`, `start`,
`stateNormal`, `startGoalDemo`, `stateGoal`, `reinit`, `KartCameraDirector::initBeforeStructure` against the enums of
`template/RaceSys`, and the two callers of `startGoalDemo` (4, 5); `DemoCameraBase` and its constants 45, 0.01 and
0.0174533, `CameraPath::updateSpeed`, `PathBase::create`, `createRail` and `calc` (6, 8); the three moving look-at
cameras and the follow cameras, with the constant 2³²/360 (7); the intro states, the frame table, the near clip 3 × 10,
`changeFog_`, `DemoPage::onPagePreStep`, the kart hiding through +0x18B (9); the award and live view states and
`applySetting_WinningRun` (10); every branch of `_calcEnvEffect` by course and the source of `m_waterbox_height` (11);
`PullPathData`, `PullPath::update` and the collision switch against `KDGndCol::ECollisionTypes::PULL` (12);
`SndAreaMgr::create`, `initArea` with its default ambients, `setArea` and `calcPathArea` against their literal tables,
`calc`, `SndPathData::update` and `isAirshipOutside` (13); the CAME accessor, `getPosture`, and the route link of
`MapdataCamera::m_path` in `JmpResourceCourse::mount` (14); `JmpResource::mount` and `search`, the magics, accessor
sizes and vtables of CNPT, MSPT and CORS, their `constructLocal` and `getPosture` calls, and `setReaction_fromKart`
(18). A scan of the state stores of the director found states 0, 1, 4, 5, 6 and 7 written, and 2 and 3 never (16).

The sound names were checked against `template/Sound/SoundID.hpp`, which names all 13 ambient and 17 route sound IDs as
the topic does, instead of the BCSAR.

**Re-checked in the data**: AREA, CAME and POTI of the 40 course KMPs (`mk7 kmp dump`, summed with a throwaway script):
area and camera type counts, shapes, priorities, moving roads, effect delays, sound area counts, the `next = -2`
cameras, point speed and flags, the 28 goal cameras and their values, every intro chain and every linked pair, and that
no camera area points to a left-out camera (15). The four effect tables of `RaceCommon.szs`, row by row against the
overview table, with the world positions, the DK Pass objects and Neo Bowser City's slot 1 values (17). The effect area
positions cited in Finding 17. The section counts of all 48 KMP files and the Maple Treeway glide paths (18). Two of the
goal camera screenshots of Finding 16.

**Changed:**

- Overview: 27 → **28** race courses with a goal camera (Finding 15 and the overview's own later section say 28).
- The replay falls back to the kart camera on the **19th** frame outside the areas, not after 20: the timer is reset to
  0 and then incremented on every frame inside, so it is 1 on the last one (overview, advice, Finding 5, Confidence).
- Type 6 to 8 routes are not all small circles: 71 of the 178 stay within about 30 to 65 units of the origin, the others
  reach 100 to 300 units (the last award ceremony camera over 1000). Mario Circuit route 14 grows from 45 to 68 units
  rather than being an arc of radius 47 (overview, Finding 8).
- The two "video next" cameras of SNES Mario Circuit 2 point to intro cameras 13 and 12, not to each other (overview).
- `m_video_next` does not keep a camera out of the intro chain: only the camera the chain search starts from must have it
  at 0 (glossary, patch comment, Finding 3). An out-of-range `m_next` ends the chain after the camera that holds it,
  which is built as a non-last camera; the old wording said a camera was left unbuilt (Finding 3).
- With a viewpoint speed of 0 the frame count is not infinite: `vcvt` saturates it and the `+ 1` wraps it negative. The
  outcome, a look-at that stays at begin, is unchanged (Finding 7).
- `MapdataAreaCalcBase::m_area_point_data` points to `position` (entry + 4), not to the entry, so its type
  `MapdataArea::SData *` was 4 bytes off. The patch now declares `MapdataAreaCalcBase::SMapdataAreaCalcData` (position,
  rotation, scale), the name of the `dlp` symbols, and types the member with it (glossary, patch).
- "The same in every build" for the goal camera was backed by `dlp` and `eur2` only; `startGoalDemo` was also compared
  with `eur0` and `eur1` and is identical (overview, Finding 5).
- Fixed points of the effect rows: about 270 to 1000 units from their area, not "a few hundred"; Wario Shipyard slot 0
  has a `scaleX` of 10; the `Test` row also sets `around_WorldPosY` (overview, Finding 17).
- Glide path byte +0x0F is set on one path of DS Airship Fortress, DS Waluigi Pinball and Maple Treeway, not only Maple
  Treeway (Finding 18, Confidence).
- "Nothing was run in the emulator" in the sources contradicted Finding 16; replaced by a link to it.
- The CORS accessor is one word larger than those of CNPT and MSPT, not than all others (several accessors are 0x1C
  bytes) (glossary).
- Patch comments: `GOAL` said both "shown after the finish" and "never made current"; `ENVIRONMENT_EFFECT` said setting 1
  is the effect slot, which several course slots do differently. Both reworded.

**Patch.** Checked with `git apply --check` on `db0fec5`, applied to a fresh work copy, `verify` passes for
`VERSION_EUR_REV2` and `VERSION_USA_REV1`.

**Not re-done:** the in-game tests of Finding 16 (only two screenshots looked at) and the texture order measured in the
running game; the decoding of the CTPK textures; the two throwaway code scans of Finding 18 (the `xref`, vtable and
literal checks they back were re-done). The uncertain points listed under `## Confidence` and `## Open questions` remain
as they are.

### Document review

Pass 3, 2026-11-14. `README.md` was read section by section against the rules of WRITING.md, then this document and the
patch.

#### Overview

- New terms introduced in "Words used in this document": the **route settings** and **point settings** (the overview
  used "the two route settings" and "the first setting of the route points" without saying a route has settings of its
  own), and the **course slot**, used everywhere in the effect and sound sections. "Base course" (heading and table
  column of the effect table) was a second term for the course slot and is now "course slot"; "slot" alone, which could
  be read as a course slot, is "effect slot" in the prose of the effect section.
- The **listener** of the sound areas was used without introduction; it is now introduced, with the certainty
  `## Confidence` gives it (most likely the camera).
- The **live view** was used without saying what it is. It is now introduced as a mode marked by a flag of the race
  information, and "which screen uses it" was added to `## Open questions`: the research does not say, and the reader
  would ask.
- "The normal finish view" and "the normal kart camera" were the kart camera; reworded.
- Effect areas were said to switch the particles on "around the watched kart", while the section goes on to say most
  rows place them around the camera. Finding 11 tests the kart's position against the areas; reworded to "while the
  watched kart is inside them". The area type table said "for the player inside"; same fix.
- "During the course preview the camera's position is tested" used "course preview" for the course intro, while the
  same word names the menu preview videos. Reworded to the course intro, with a link to Finding 11 for the other modes
  it lists.
- The advice "what an effect slot shows comes from the course's effect files" contradicted the section above it (the
  particles are set per course slot in `RaceCommon.szs`, not in the course files); reworded to match it.
- The remarks recorded in the `Asked` line were written "as the user remarked"; the topic is for any reader, so they
  are now "as remarked when this research was asked" (overview, Finding 18, Confidence).
- The Maple Treeway cannon was said to be "driven by the glide route", which `## Confidence` only rates as likely and
  Finding 18 did not research further; the overview now says "most likely", with the reason.
- The fixed points of the effect rows were "about 300 to 1000 units" from their area in the overview and "about 270 to
  1000" in Finding 17; the overview now gives 270, which the five positions of Finding 17 confirm (272 to 1000).
- The example of a type 3 viewpoint in the advice, (−12, −24, 53), had no finding behind it. It is camera 2 of Mario
  Circuit (`mk7 kmp dump Gctr_MarioCircuit -s CAME`); the advice says so and Finding 15 now cites it.
- A duplicate link in the camera routes paragraph removed; long lines rewrapped.

#### Glossary

- `Field::eMapdataAreaType` moved under `MapdataAreaData`, whose `m_type` it types, and
  `MapdataAreaCalcBase::SMapdataAreaCalcData` under `MapdataAreaCalcBase`, which declares it; both were under
  `MapdataAreaCalcCylinder`.
- Status `retyped` (`MapdataAreaCalcBase::m_area_point_data`) is not one of the three statuses; it is `existing`, with
  the retyping in the note. `MapdataCannonPoint::m_posture` was `renamed` from an unnamed `/U/` member while
  `MapdataCamera::m_posture`, the same case, was `new`; both are `new`.
- Members of other classes that part 2 cited by offset and that `template/` already names are now written by name and
  listed in new tables: `Kart::Rigid::m_position`, `Kart::VehicleMove::m_status_flags` (and the names of its bits),
  `Kart::Camera::m_target_position`, `Camera::CameraBase::m_near` and `m_position`,
  `Camera::KartCameraDirector::m_camera_target_player` and `m_demo_camera_director`, `RaceSys::KartInfo::m_flags`,
  `RaceSys::CRaceInfo::m_race_mode_flag` (bits `live_view` and `replay_grand_prix`),
  `RaceSys::ModeManagerBase::m_frame_since_countdown`, `Field::FieldDirector::m_course_info`, the AREA, CAME, STGI and
  GLPH accessors of `JmpResourceCourse`, and `m_header`, `m_magic` and `m_accessor_num` of `Util::JmpResource`. Each
  name was checked against the offset the finding gave; `KartInfo::m_flags.real_goal_1` was also checked in
  `KartCameraDirector::calcInner` (`*(param_1 + 0x58) + 0x40) & 1`).
- 18 functions the findings name were missing from the Functions table, and the three accessor vtables of Finding 18
  from the Data table; added with their `eur2` addresses from `mk7 sym`.

#### Findings

- Addresses outside the glossary removed: the literal of Finding 1, `DAT_002b1d84` of Finding 7, the up vector and the
  patched instruction of Finding 16, the function, literal and vtable addresses of Finding 18, and the `mk7 diff`
  addresses of Finding 5, which moved to [Demo cameras](#demo-cameras) above.
- The bold-titled paragraphs of Finding 18 (**In the files.**, **Loading.**, ...) are `####` headings.

#### Patch

Two comments said where a value is used, against the comment rules of PATCHES.md: the comment of
`MapdataCamera::EType` ("Which subclass `DemoCameraDirector::createCamera_` builds", now "How the camera moves and where
it looks") and the `Used by Kart::PullPath` of `MOVING_ROAD`, which the patch rewrites. Regenerated from a fresh work
copy of `db0fec5`; `git apply --check` passes and `verify` passes for `VERSION_EUR_REV2` and `VERSION_USA_REV1`. The two
comments are the only change. The commands of [The patch](#the-patch) now use the path of the topic in `final/`.

#### Not resolved

Part 2 still cites some members by offset because `template/` has no name for them, and naming them
would add members to classes this topic only touches (or, for the sound and particle classes, has no template at all):
`KartEffect` +0x69C and +0x6A0, `Kart::Camera` +0xE0 and +0x164, `Kart::Director` +0x18B, `VehicleMove` +0xCDC, +0xD14
and +0xE81, `PullPath` +0x4C and +0x50, the menu data +0x1D4, and the members of `Sound::SndAreaMgr`,
`Sound::SndSceneRace`, `Sound::SndPathData` and `Effect::ParticleDrawer` used in Findings 13, 16 and 17. They are left
for the human to name or keep.

Nothing that looks factually wrong was found. Status set to `verified`, and the topic moved to `final/`.

### Names added after the document review

2026-11-14, asked by the human after pass 3: name the members that the document review left as offsets because
`template/` had none. The patch now adds them, each checked in `eur2` before naming:

- `Effect::KartEffect::m_env_area_index` (0x69C, `s32`): `_calcEnvEffect` reads it as the index of the previous area
  and stores the area found (or −1) as its last step (`str r4, [r6, #0x69c]`); no other store in the effect code.
- `Effect::KartEffect::m_camera` (0x6A0, `Camera::CameraBase *`): stored by `_calcCameraParam`
  (`str r0, [r4, #0x6a0]`), the only store found in the effect code (0x003D0000 to 0x003F0000).
- `Kart::Camera::m_up_dir` (0xE0, `sead::Vector3f`): copied from the vehicle by `Kart::Camera::init`, updated by
  `calcApply`, read by `DemoCameraFollowBase::initInner` as the up vector.
- `Kart::Camera::m_look_dir` (0x164, `sead::Vector3f`): `calcDraw` stores `sub(look-at, position)`, the two vectors it
  has just written to the screen camera (+0x38 and `m_position`). `calcApply` also stores a vector there, copied from
  +0x118 after `KDAttT::normalizeZYX`; what that vector is was not followed, so the comment describes the `calcDraw`
  value.
- `Kart::Director::m_is_kart_hidden` (0x18B, `bool`): the byte of Finding 9; a `bool` like its neighbours.
- `Kart::VehicleMove::m_waterbox_height` (0xCDC, `f32`): the value Finding 11 already described, under the name of the
  `KartEffect` member it is copied to.
- `Kart::VehicleMove::m_gnd_col_type` (0xD14, `KDGndCol::ECollisionTypes`, a `u32` enum like the word it replaces):
  written by `calcGndCollision` as `attribute & 0x1f` of a collision result. Added to Finding 12; `## Confidence` still
  rates "under the kart" as likely.
- `Kart::VehicleMove::m_is_cannon_wing_path` (0xE81, was `/U/bool`): the copy of glide path byte +0x0F of Finding 18.
  The name follows what Finding 18 rates as likely (the byte marks the cannon path).

The "menu data +0x1D4" of Finding 17 needed no new name: `DashSequenceEngine::m_menu_data` is a `Sequence::MenuData`,
and +0x1D4 is `MenuData::m_race_info` (0x74) + `CRaceInfo::m_course_id` (0x160). Glossary tables added for
`Kart::Director` and `Sequence::MenuData`, and rows for the new members; the four functions cited above added to the
Functions table.

Still offsets, because their classes have no template: the `Kart::PullPath` object (+0x4C, +0x50, and its pointer at
+0xE94 of the vehicle), `Sound::SndAreaMgr`, `Sound::SndSceneRace`, `Sound::SndPathData` and `Effect::ParticleDrawer`.

The patch was rebuilt from a fresh work copy of `db0fec5` with the reviewed patch applied; `git apply --check` passes,
and `verify` passes for `VERSION_EUR_REV2` and `VERSION_USA_REV1`. These names have not been through a separate fact
check or document review.
