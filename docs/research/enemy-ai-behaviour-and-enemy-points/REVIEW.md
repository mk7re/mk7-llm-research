# Review and verification steps for `Enemy AI behaviour and enemy points (KMP ENPT / ENPH)`

## Contents

- [How to verify](#how-to-verify): the commands that reproduce the key evidence
  - [Code](#code)
  - [Patch](#patch)
  - [Course data](#course-data)
- [Review](#review): the record of the review passes, one subsection per pass
  - [Fact check](#fact-check)
  - [Fact check, second round (in game)](#fact-check-second-round-in-game)
  - [Follow-up research](#follow-up-research)
  - [Fact check, third round](#fact-check-third-round)
  - [Second follow-up research](#second-follow-up-research)
  - [Fact check, fourth round](#fact-check-fourth-round)
  - [Document review](#document-review)
  - [Fact check, fifth round](#fact-check-fifth-round)
  - [Document review, second round](#document-review-second-round)
  - [Fact check, sixth round](#fact-check-sixth-round)
  - [Document review, third round](#document-review-third-round)
  - [Fact check, seventh round](#fact-check-seventh-round)
  - [Document review, fourth round](#document-review-fourth-round)
  - [Document review, fifth round](#document-review-fifth-round)

## How to verify

### Code

The commands run from the repository root. `0x5665b0` is `sinit_ObjectCrossingParam`, which has no name in the symbol
maps yet; the `read` targets are the constants the comments give, and `0x62a1ec` is the `AIEngine` state table.

```
M=mk7-llm-research/mk7
$M port --changed 'Enemy::|MapdataEnemy|EnemyPt'   # only AIAutoSteer::stateIdle differs from dlp
$M decomp Field::MapdataEnemyPoint::setup   # setup: rule mode 3/7, the two tests on data + 0x44
$M decomp Field::MapdataEnemyPathAccessor::setupPathPointLink Field::MapdataEnemyPathAccessor::setupPathDepth Field::MapdataEnemyPath::createDepth_ Field::MapdataEnemyPathAccessor::setupObjLink_   # m_find_type, m_depth, object links
$M decomp Enemy::AIPathManager::init; $M dis Enemy::AIPathManager::init | grep -n 'vldr'   # init order, 150 / 75
$M dis Enemy::PathSmoother::init; $M dis Enemy::PathSmoother::setupBezier_   # smoother (the decompiler truncates both)
$M decomp Enemy::AIPathHandler::update Enemy::AIPathHandler::goNextPath_   # reach test, flags 0x04 / 0x02 / 0x80, current and next param
$M read 0x3352a8 1; $M read 0x338870 2; $M read 0x333388 1; $M read 0x33750c 1   # 19600, 10000 / 0.1, 78400, 40000
$M decomp Enemy::AIControlBase::setBasicDriveInfo_ Enemy::AIControlBattle::setBasicDriveInfo_   # drift_setting: race version, battle override
$M decomp Enemy::AIControlBattle::update Enemy::AISpeedBattle::update Enemy::AI::setMaxSpeedRatio   # flag 0x80 readers
$M xref Enemy::AIProbabilityBase::isLaunchJumpAction   # isLaunchJumpAction of the battle vtable
$M decomp Enemy::AIPathPoint::selectNextPointHandleIndexWithShortcut_ Enemy::AIPathPointBattle::selectNextPointHandle_ Enemy::AIPathPointBattle::selectNextPointHandleIndex_   # junction choice, race and battle
$M dis Enemy::AIPathHandler::onOutOfBoundsInner   # respawn: result of FindNearestEnemyPtHndl not stored
$M decomp Enemy::AIPathManager::findNearEnemyPoint   # findNearEnemyPoint filters
$M dis Enemy::AIPathHandler::isPassedThroughPathPoint_   # pass-through plane (decompiler truncates it)
$M dis Field::ObjectDirector::createBeforeStructure | grep -B4 -A12 'ldrsh.*#0x3c'   # m_obj_link_array: m_enemy_route >= 0
$M decomp Enemy::AIAutoSteer::isNeedWait_ Enemy::AIAutoSteer::stateInitWait Enemy::AIAutoSteer::stateWait Enemy::AIAutoSteer::init   # crossing wait: isNeedWait_, stateInitWait, stateWait, list of 0x13e
$M decomp Field::ObjectCrossing::set_isFlickering Field::ObjectCrossing::initObj; $M dis 0x5665b0 | tail -20   # crossing: flag window, trains and partner, 1000 / 240 / 300
$M decomp Enemy::AIStuck::stateCheckStuck Enemy::AIStuck::checkAccident_ Enemy::AIStuck::stateInitBackPathPoint Enemy::AIStuck::stateBackPathPoint Enemy::AIStuck::stateStartOutOfBounds Enemy::AIStuck::onAIFall   # AIStuck: counters, back-up, Lakitu, repeated falls
$M dis Enemy::AIPathPoint::getInterpolateTarget; $M dis Kart::VehicleMove::applyDriveSpeed | grep -A3 '#0xf30'   # back-up aim along the history; m_forward_speed_ratio
$M decomp Enemy::AIDriftDrive::calcSteerNormal_ | head -60   # brake only while backing up, no pedal with request bit 0x40
$M decomp 'Enemy::TargetSearcher<unsigned short>::setTarget'; $M dis Enemy::AIBattleSearcher::init | grep -B3 'TargetSearcher('   # battle: node width decides which edges a target is on
$M decomp Enemy::AIObjectSearcher::isMapObjectToAvoid_ Util::Math::verticalize   # the only reader of MapdataEnemyPoint::m_direction
$M decomp Enemy::AIManager::calcAILevel_ Sequence::GetEnemyLevel Enemy::AI::init   # AI level in battle; AI::m_is_player_kart
$M decomp Enemy::AIEngine::update Enemy::AIEngine::awake Enemy::AIEngine::sleep Enemy::AIEngine::stateReady   # AIEngine: re-route signals, awake from state 3, sleep, ready
$M dis Enemy::AIControlBase::isAIFallSignal; $M decomp Kart::VehicleMove::startKiller_Impl Enemy::AI::startKiller   # isAIFallSignal reads AIStuck + 0x69; player Bullet Bill start
$M read 0x62a1ec 14   # AIEngine state functions, in state order
$M decomp Enemy::AIStuck::stateInitIdle Enemy::AIStuck::onOutOfBoundsInner Enemy::AIControlBattle::onAIFall   # AIStuck counters cleared on relocation; battle onAIFall
$M decomp Enemy::AIAutoSteer::stateInitGather Enemy::AIAutoSteer::stateGather; $M dis Enemy::AIAutoSteer::stateExitGather   # coin-battle gathering and its re-route
$M dis Kart::VehicleMove::VehicleMove | sed -n 5,25p   # five CheckIF_EX from +0xC80: +0xC94 = m_col_checks[1].m_collision_result
$M decomp Enemy::AIControlRace::watchPlayerAndSwitchCollision Enemy::AIAutoSteer::isNeedRunAway_ Enemy::AIAutoSteer::stateRunAway   # m_is_far_behind; battle run-away from boards
$M dis Enemy::AIControlRace::watchPlayerAndSwitchCollision | grep -A2 vcmpe; $M decomp RaceSys::LapRankChecker::calc | tail -40   # own progress < watched -> 1; rank 1 = highest progress
$M decomp Enemy::AIPathPoint::selectNextPointHandle_ Enemy::AIEngine::statePlayerIdle   # dead-end read of m_next_points[0]; end of a player's race
$M dis Enemy::AIPathPoint::calcPointOffsetDistance_; $M dis Enemy::AIManager::getRandF32   # lanes beyond 50 % drift back, 0.01 / 0.03 with title bit 0x10
$M dis 0x330020 -n 0x1c0 | grep -A40 '#0x1100'   # hop block of calcSteerNormal_ (past the literal pool that ends its detected range): 0x1100 / 0x4 / 0x840
$M decomp Enemy::AIProbabilityRace::isLaunchDrift; $M xref Enemy::AIProbabilityRace::isLaunchDrift   # random drift-start check, slot 3; title bit 0x20 skips it in setBasicDriveInfo_
$M decomp Enemy::AIItemRace::stateKinoko | head -30   # no Mushroom use while m_drift_state & 0x18
$M dis Enemy::AIManager::calcAILevel_; $M decomp RaceSys::CRaceInfo::updateRaceModeFlag | grep -B1 '| 8'   # online race -> level 2; multiplayer bit for play modes 1 and 2
$M dis Enemy::AIControlBattle::stateInitLockedOn   # +0x95 read on the same this as m_search_mode
$M decomp Enemy::AIControlBattle::setBattleType Enemy::AIControlBattle::setDoNotSelectBackward Enemy::TeamInfo::decideTeamBattleType   # writers of m_battle_type / m_do_not_select_backward
$M dis 'Enemy::AIControlBattle::AIControlBattle' | sed -n 5,20p   # constructor zeroes +0x60, +0x90, +0x95
$M dis Enemy::AIAutoSteer::stateInitGather | grep -A6 '#0x4800'   # CoinManager::m_coins: count at +0x48E8, pointers at +0x48F0
```

The writers of `ObjectBase::m_ai_signal` and of `AIControlBase::m_search_mode` were found by scanning a disassembly of the
whole code segment for byte stores at +0x78 and word stores at +0x48 (a throw-away script over `mk7re.static.disasm`).

### Patch

```
M=mk7-llm-research/mk7
W=mk7-llm-research/local/work/enemy-ai-check; mkdir -p $W && cp -r template $W/template
(cd $W && patch -s -p1 < ../../../final/enemy-ai-behaviour-and-enemy-points/enemy-ai-behaviour-and-enemy-points.patch)
$M --templates $W/template verify --version EUR_REV2
$M --templates $W/template access --class Enemy::AIStuck; $M --templates $W/template access --class Enemy::AIAutoSteer --gaps
git apply --check mk7-llm-research/final/enemy-ai-behaviour-and-enemy-points/enemy-ai-behaviour-and-enemy-points.patch
```

### Course data

The data checks (`m_link_end_flags` against geometry, value histograms, objects with an enemy route, respawn points without
a nearby enemy point) need a KMP parser (`JBOG` has 0x40 bytes per entry, `TPGJ` 0x1C): header `DMDC`, section offsets at
0x10 relative to the header length at 0x0A, sections `TPNE` (0x18 per entry) and `HPNE` (0x48 per entry), little endian, files
under `mk7-llm-research/local/romfs/eur2/`.

## Review

### Fact check

Second pass, fresh context, 2026-09-30, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2`
(sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95).

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied with `patch -p1` to a fresh copy of `template/`;
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (USA_REV1) both pass.
- **Layouts.** Sizes from the allocation sites: `AIPathHandler` 0x4C (`mov r0, #0x4c` at 0x00332FB4), `AIPathPoint` 0x58,
  `AIPathPointBattle` / `AIPathPointBattleCoin` 0x70, `PointParam` 0x10 (all in `AIPathHandler::AIPathHandler`, 0x00335354).
  `GoNextInfo` 0x30 and its members from the stack frames in `AIPathHandler::update` and `onOutOfBoundsInner` (0x00334A3C to
  0x00334AB8). `MapdataEnemyPoint` / `MapdataEnemyPath` defaults from both `constructLocal`. Existing names used by the doc
  (`m_settings[7]` = GOBJ 0x38, `m_enemy_route` = 0x3C, `CRaceInfo::m_rule_mode` = 0x168, `m_course_id` = 0x160,
  `StatusFlags` bits 0x80 `wing_open` / 0x400000 `killer`) checked against `template/`.
- **Findings 1 to 8.** Every function in the Functions table was decompiled or disassembled again in `eur2`, and the constants
  were read with `mk7 read`: `setup` (links, both `+0x44` tests, rule mode 3/7), `setupNrm`, `setupPathPointLink`,
  `setupPathDepth`, `createDepth_`, `setupObjLink_`, `AIPathManager::init`, `findNearEnemyPoint` (250000, 75, option filters),
  `FindSectorForEnemyPt`, both `FindNearestEnemyPtHndl*`, `onOutOfBoundsInner` (result of `FindNearestEnemyPtHndl` in r0 never
  used), `PathSmoother::init` / `setupBezier_` / `setupAccessor` / `calcPathCosineAndAxis` / `calcPointCosineAndAxis_`,
  `AIPathHandler::update` / `goNextPath_` / `init` (19600, 0.3, the three `InitArg` tables), `goNextPoint`,
  `calcNextTargetTrans` (race, award, battle), `calcPointOffsetDistance_`, the `PointParam` predicates, `isTimeToEndDrift`,
  `isTargetToStartDrift`, both `setBasicDriveInfo_`, `calcSteerNormal_` / `calcSteerDrift_` (flags 0x08 / 0x10),
  `AIControlRace::update` / `startKiller` / `onAIFall`, `AIControlBattle::update` / `onAIFall`, `AISpeedBattle::update`,
  `AI::setMaxSpeedRatio` / `initAfterManager` / `init`, `AIManager::calcAILevel_`, the three mushroom states and their helpers,
  `ShortCutInfo::isProbableToSelect`, `selectNextPointHandleIndexWithShortcut_`, the battle selectors, the `m_airborne_rate`
  update (0x002D9220) and its static initializer (`r2 = 0x14` at 0x0054E0A0 reaches the `stm` at 0x0054E720 unchanged).
- **Course data.** Re-counted with an independent throw-away parser (40 course archives + the 4 `pat1` overrides = 40
  courses, 34 race and 6 battle). The flag counts, drift 1 / 2 / 3, `path_find_options`, `max_search_y_offset` (value 1 only
  in `Gctr_WinningRun`), the zero `m_link_end_flags` of race courses and the link-end agreement (288/288, 134/134, 212/220)
  all reproduce. The other three battle courses agree too: `Bctr_WuhuIsland3` 238/240, `Bds_PalmShore` 173/174,
  `Bn64_BigDonut` 80/80.

#### What was changed

- **Drift setting counts.** "0 (2407 points)" included the 527 battle points; the race courses have 1880. The guide's
  "about 60 % use 2" becomes "about two thirds" (4655 of 6890).
- **Scale range.** The race courses use -0.375 to 7.125 (13 negative points), not 0.25 to 6, and most often 0.5 to 2.
- **Lane range.** The formula in Findings 6 is right, but the guide's "70 % one side, 55 % the other" was not: it is about
  61 % / 54 %, or 73 % / 42 % when STGI byte 1 is 0 (22 of the 34 race KMPs). The guide now also says that the lane is moved
  by blocking and avoidance (`AIBlockLine::stateBlock` and `AIAutoSteer::calcTargetToAvoid_` reach
  `AIPathPoint::addOffsetRate` through the `AIPathHandler` wrappers) and reset to the centre by a Bullet Bill (`goNextPoint`,
  the `m_is_killer` branch writes 0 to `m_offset_rate`) or a relocation.
- **Mii titles.** The guide called bit 0x1100 "Safe Driver and Rookie" without evidence. `AI::init` (0x0033CAAC) maps a
  per-player value 1 to 16 to the bits; read against the order of the `Title1_*` messages, 6 / 7 / 8 / 9 are Boost Jumper,
  Aviator, Dolphin and Drift Wizard, which matches what the code does with bits 0x4 / 0x40 / 0x80 / 0x20. By the same order
  0x100 is Rookie, 0x1000 Star Racer and 0x10 Safe Driver. The guide now uses those names and has a [Mii titles](README.md#cpu-levels-and-mii-titles)
  table, marked as likely.
- **AI level in battle.** `AIManager::calcAILevel_` (0x0033E6AC) takes the engine class only in race; in single-player battle
  the level comes from `Sequence::GetEnemyLevel()`, and multiplayer / online battle always use level 2. Added to flag 0x80.
- **Mushrooms.** Added two branches of `AIItemRace::stateKinoko` the doc did not mention: title 0x40 / 0x80 CPUs ignore
  `mushroom_setting` and use the Mushroom while gliding / in water, and the timer is held at 10 or more while
  `m_next_point` has no side axis (`m_internal_flags & 1` clear, i.e. junction points).
- **Fork where every branch is a shortcut.** CPUs with `m_do_select_shortcut` pick among them at random; only the other CPUs
  take branch 0.
- **Battle self-links.** A self-link lies on the CPU's current path and is excluded by `m_do_not_select_backward`; the guide
  now says so. That flag is set by `AIPathHandler::init` in every mode and cleared by `AIControlBattle::stateInitLockedOn`
  (unless `+0x95`); added to Findings 8.
- **Flag 0x10.** Without the flag, `calcSteerDrift_` also gives up an aligned drift after 120 frames or once
  `isMiniTurbo_OverLv2()` (0x0032F874 to 0x0032F8B4); the flag skips that test. Added the 2-second part to the guide.
- **Battle search modes.** 10 is `stateInitRunAway`, 3 `stateInitSearchItem`, 5 `stateSearchCoin`, 6 / 2
  `stateInitSearchRival`, 7 `stateSearchItem`, 8 `stateInitSearchCoin`; modes 1 and 8 (outside coin battle) take branch 0.
  One open question resolved; no writer of 4 found.
- **Race `onAIFall`.** Also relocates when `AI + 0x24` is set, not only on a path change.
- **Glossary.** `m_depth` is the depth-first discovery depth, not the shortest; `m_start_adjust` / `m_count_adjust` hold the
  part of the re-sampled start / count above 0xFFFF (`PathSmoother::setupAccessor` copies them from its `PathOffset` array,
  and `setupBezier_` writes 0xFFFF into the 16-bit fields when they overflow).
- **Items the doc listed as unchecked, now confirmed.** The `setupNrm` radius is 25 (0x0038F75C). `calcNextTargetTrans`
  receives `GoNextInfo::m_corner_line_shift` as its float argument and `true` as its bool (`vldr s16, [r5, #0x2c]` at
  0x0032E8E8, `vmov.f32 s0, s16` / `mov r1, #1` at 0x0032E938). The other drift-ending conditions of `calcSteerDrift_` are the
  120-frame / mini-turbo test above.

The patch was not changed: its names and offsets all hold, and none of the corrections above touches it.

#### What remains uncertain

- The title names of bits 0x10, 0x100 and 0x1000 (see Confidence).
- `isPassedThroughPathPoint_` and the Bullet Bill phases, as before.
- The course-creator advice itself was not tested in game.

### Fact check, second round (in game)

Second pass repeated with dynamic testing, fresh context, 2026-10-05, same base commit and `eur2` image, in Azahar
(`mk7 emu`). The runtime structures were read live with a throw-away script (not part of the tooling) through the chain
`Kart::Director::m_ai_manager` -> `AIManager::m_ais[i]` -> `AI + 0x8` (`AIEngine`) -> `AIEngine::m_ai_control` ->
`AIControlBase::m_ai_path_handler` / `m_ai_path_point`, the race accessors at `AIPathManager + 0x28` / `+ 0x40` and the KMP
accessors of `JmpResourceCourse`. Runs: a 150cc Flower Cup with the player as a CPU (Wuhu Loop, Mario Circuit, Music Park),
its winning run (award), and a balloon battle on Wuhu Town with the CPUs on hard.

#### What was confirmed

- **Re-sampling (Findings 3).** A re-implementation of `PathSmoother` from the KMP points (handles, sub counts from the
  segment before, Bézier, settings of the nearer point, path order) reproduced the race accessor exactly: Wuhu Loop 339 -> 665
  points, Mario Circuit 250, Music Park 341; every path start and count, positions within 0.0015 units, all 0x18-byte
  settings. Links between paths get no inserted points (allowing them gives the wrong counts).
- **Point setup (Findings 2, 4).** On the three race courses: links (race rule), `m_width = scale * 50`, `m_side_axis`,
  `m_corner` (all 1213 points with one previous and one next point; the sign test uses the flattened vectors, as the
  pseudo-code says; with the 3D vectors, 3 near-straight points of Wuhu Loop get the wrong sign), `m_internal_flags` 1,
  `m_corner = 1.0` and no flag elsewhere, sector 0xFF exactly where `path_find_options != 0`, `m_path_index`, `m_index`.
  The re-sampled paths keep their links and `m_link_end_flags`; `m_find_type` -3 and `m_depth` are written to the race
  accessor only (the KMP accessor keeps -2 / -1). On Wuhu Town: the KMP points are used (`PathSmoother` null,
  `PathAnalyzer` set), `m_prev_count` 0 and no `m_prev_points`, next links as Findings 2 gives them with the
  `m_link_end_flags` of 33 paths, `m_corner = 1.0` and `m_internal_flags = 0` on every point.
- **Start points and respawns (Findings 7).** Wuhu Loop (course 8) all 0; Mario Circuit and Music Park all equal (0, the
  sector search); Wuhu Town each entry the nearest point to its KTPT position (8 of 8); award as Findings 6 says. Every
  `m_nearest_enemy_point` (39, 11, 14, 8) equals a re-implementation of `findNearEnemyPoint`. A CPU that fell on Wuhu Loop was
  put back at Lakitu point 17 and targeted its nearest point, 219, with `m_current_param` zeroed. With all the values set to
  -1, a CPU that was made to fall headed to point 0, as the disassembly says.
- **`AIPathHandler::init` values (Findings 5).** 150cc race: 78400, cos 0, corner shift -0.7, shortcut mode 2, relocation
  pass mode 2, `m_obj_check_rate` 75 (50 on Music Park, course 15). Award: 40000, 0, 0, 0. Battle: 10000, 0.1, 0, 0,
  `m_is_battle` 1, `AI::m_base_speed_ratio` 1.0 at hard.
- **Starting lanes (Findings 6, scale).** On Wuhu Loop (STGI byte 1 = 0), the `m_offset_rate` of each of the 8 CPUs was in the
  range the formula gives for its grid rank (`Sequence::GetKartGridRank`, called in game).
- **Advancing (Findings 5).** 6000 race frames of 8 CPUs, 2584 advances: 2573 within the reach radius (280, or 140 when the
  point just reached has flag 0x04), 11 farther (the pass-through plane; none in battle). After each advance
  `m_current_param` held the settings of the old target and `m_next_param` those of the new one (the one exception was a
  relocation). In battle (4000 frames, 497 advances) all within about 100 units, every step inside a path in the entry
  direction (356) and every choice at a path end a linked point (141).
- **Flag 0x80.** `m_force_base_speed` equalled flag 0x80 of `m_current_param` on every frame of every CPU; in battle the
  target was exactly the point centre on all 3034 frames with the flag.
- **Drift setting.** All 41 drift starts happened with a target whose `drift_setting` was not 1 or 2, `|m_corner| <= 0.998` and
  the target within 400 units; 37 of 68 drift ends came right after reaching a point with 1 or 2.
- **Patch.** `git apply --check` passes; `verify` passes for EUR_REV2 and USA_REV1 on a fresh copy with the patch applied.

#### What was changed

- **Reach radius not constant** (Findings 5, guide): `goNextPath_` restores `m_default_reach_radius_sq` on every advance;
  `AIPathHandler::startKiller` sets 100 units and `initMoveBackTargetToPreviousPath` 50 units until then. Found in the trace (a
  CPU in Bullet Bill had 10000 for 19 frames), then read in the code.
- **"A CPU always aims 280 to 430 units ahead"** (guide) was wrong. Measured right after an advance: 5 % to 95 % of 213 to 493
  units, median 375, maximum about 900 on long segments that get no inserted points.
- **`AI::setMaxSpeedRatio`** (Findings 6, guide flag 0x80): the base speed ratio is also used while boosting and after 20
  frames in the air without gliding, with or without the flag.
- **Battle search modes** (Findings 8): 5 is also written by `stateInitSearchRival` (and by `stateSearchCoin` only in a coin
  battle); 2 and 3 have more writers. Found because mode 5 was in use in a balloon battle.
- **Linked objects** (Findings 8, guide, open questions): the branch exclusion by `m_ai_signal == 0` (then `m_cpu_should_avoid_object`) was
  measured on Music Park; the member's name is the opposite of its effect.
- **Award start points** (Findings 6): a later path with the same value overwrites an earlier one.
- **`m_airborne_rate`** (Findings 5): steps of exactly 1/20 measured; a Lakitu respawn resets it to 0 at once.

The patch was not changed.

#### What remains uncertain

- Not tested in game: the mushroom setting and shortcuts, flags 0x01, 0x02, 0x08, 0x10, 0x20, 0x40 beyond what the trace
  shows, `path_find_options` -1 to -4 and `max_search_y_offset` beyond the nearest-point searches, the Mii titles, coin
  battle, and the course-creator advice itself (no course was modified).
- The left/right meaning of the sign of `m_corner`, `isPassedThroughPathPoint_` and the Bullet Bill phases, as before.

### Follow-up research

Third research pass, 2026-10-05, same base commit and `eur2` image, asked after the dynamic fact check (see `Asked
afterwards` at the top). Static work with `mk7 dis` / `decomp` / `xref` / `read`, two throw-away scans of the whole
disassembly (byte stores at +0x78, word stores at +0x48), a throw-away KMP parser, and one Azahar session (150cc Grand Prix
with the player as a CPU: Wii Koopa Cape, GCN Dino Dino Jungle, N64 Kalimari Desert, DS DK Pass). The status is back to
`pending verification`: everything below is new and has not been fact checked.

The former open questions:

| Question | Answer |
| --- | --- |
| Readers of `m_depth` / `m_depth_num` | none; not read during a race (watchpoints), Findings 9 |
| `m_cpu_should_avoid_object`: rename, writers | renamed `m_ai_signal`; its meaning depends on the reader (branch open, crossing wait, run away, avoid), so the name is neutral; writers per object type in Findings 8 |
| Which objects enter `ObjectDirector::m_obj_link_array` | every object with `m_enemy_route >= 0`, Findings 8 |
| `m_search_mode` 4 | never written; the constructor, not `stateInit`, writes 0 (corrected in Findings 8) |
| `Sequence::GetEnemyLevel()`, `AI + 0x24` | 1 / 2 / 3 = easy / normal / hard -> AI level 0 / 1 / 2 (Findings 6); `AI::m_is_player_kart`, the kart is not a CPU (Findings 5) |
| `PathAnalyzer` node width | decides which road edges a battle target counts on, Findings 6 |
| `MapdataEnemyPoint + 0x44`, `m_internal_flags` 0x2 / 0x8 | +0x44 is read by `isMapObjectToAvoid_` (named `m_direction`, provisional), Findings 6; bits 0x2 / 0x8 have no reader, Findings 9 |
| Rename `m_previous_points` / `m_next_points` of `MapdataEnemyPathData`? | no: `MapdataCheckPathData` and `MapdataItemPathData` use the same names for their path indices, so the three stay consistent; the comment of the patch says they hold paths |
| Dropped result in `onOutOfBoundsInner` reachable? | not on the original courses (one Lakitu point of the award cutscene only); only on custom courses, Findings 7 |

Added: the pass-through plane (Findings 5 and the guide), train crossings (Findings 10, guide), stuck CPUs, back-up and
Lakitu (Findings 11, guide), the battle scale zone (Findings 6, guide), linked objects per type (Findings 8, guide),
helper routes and dead-end paths (guide), and `VehicleMove::m_forward_speed_ratio`, `ObjectCrossing::sParam` and the
members of `AIStuck` / `AIAutoSteer` in the glossary.

Corrected: the search mode 0 writer (Findings 8); the search mode table, which a paragraph split in two; `DriveInfo + 0x2C`
is a word of request bits (bit 0x40 holds the pedals), so it is called `m_request_flags` instead of `m_drift_request`.

For the fact check: the claims to test are in Findings 5 (plane), 6 (`scale` battle part, `m_direction`, AI level), 7 (last
bullet), 8 (`m_obj_link_array`, writers table, mode 4), 9, 10, 11 and in the guide sections [Train
crossings](README.md#train-crossings), [When a CPU gets stuck](README.md#when-a-cpu-gets-stuck) and [Helper routes for lost CPUs and Bullet
Bills](README.md#helper-paths-for-lost-cpus-and-bullet-bills). The patch changed: `ObjectBase.hpp` (rename), `EnemyPoint.hpp`
(`m_direction`), `VehicleMove.hpp` (`m_forward_speed_ratio`).

### Fact check, third round

Second pass on the follow-up research, fresh context, 2026-10-05, `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95).
The repository was at 4767b3628594c92aa7b203b4b1d1430051f6ddd6; `template/` is unchanged since the base commit
(`git diff --stat b65de46 HEAD -- template` is empty). Static only (`mk7 dis` / `decomp` / `xref` / `read`, two throw-away
scans over the whole disassembly, a throw-away KMP parser); nothing was run in Azahar. The user asked to check in particular
that helper routes can be reached by a player who starts a Bullet Bill, and by a CPU that a hit or an item pushed away and
that got stuck in the scenery.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes; applied to a fresh copy of `template/`, `verify --version EUR_REV2` and `verify`
  (USA_REV1) pass.
- **Findings 5, plane.** `isPassedThroughPathPoint_` disassembled again: aim point from `AIPathPoint + 0x4C`, the three
  points, the mode switch, the `m_index` comparison, the zero-vector fallback, `dot >= 0` for mode 1 and 2. `goNextPath_`
  writes `m_pass_mode = 1` on an advance and `m_relocate_pass_mode` on a relocation. `AIPathHandler::update`: the re-route
  conditions (timer above 20, Bullet Bill, gliding, `m_airborne_rate >= 1.0`, flag 0x02, steepness) as written.
- **Findings 6.** `TargetSearcher::setTarget` (edge test, interpolated width, node pass, main edge), the width scale 1.0 at
  the four constructor calls (`vldr s16, = 1f` / `vmov.f32 s1, s16`, and `= 1f` in `AIBattleSearcherCoin::init`),
  `PathAnalyzer` storing `scale * 50`; `isMapObjectToAvoid_` and `verticalize` (including the single-next-path test on
  `m_next_points[1] == 0xFFFF`); `calcAILevel_` and `GetEnemyLevel`.
- **Findings 7, last bullet.** A new throw-away KMP parser and a re-implementation of `findNearEnemyPoint` (re-read: integer
  compare of the XZ distance with 250000, at most 128 candidates, the height filter, options 1 and 2) over the 40 courses
  (4 from `pat1`) find a point for every Lakitu point except point 1 of `Gctr_WinningRun`.
- **Findings 8.** `setupObjLink_` and the `m_obj_link_array` filter of `createBeforeStructure`; the junction selector
  (object check rate, `m_ai_signal == 0`, the three board IDs with title mask 0x44, the -3 / -4 tests). A new scan for byte
  stores at +0x78 reproduces every writer of the table and finds one more, `ObjectWiiEscalator::initObj` (added). A new scan
  for word stores at +0x48 in `Enemy` finds no store of 4.
- **Findings 9.** A scan for loads of +0x50 followed by a bit test in `Enemy` and `Field::Mapdata` code finds only `tst #1`, in
  the three functions named. The `m_depth` readers were not re-scanned; the watchpoint evidence stands.
- **Findings 10.** `sParam` (the `vldr s0, = 1000f` / `mov r0, #0xf0` / `mov r1, #0x12c` stores), `ObjectCrossing::initObj`
  / `calcObj` / `set_isFlickering`, `AIAutoSteer::init` (ID 0x13E), `stateIdle`, `isNeedWait_` (500, 0.1), `stateInitWait`
  (75), `stateWait`.
- **Findings 11.** `stateCheckStuck`, `checkAccident_`, `stateInitBackPathPoint`, `stateBackPathPoint`,
  `stateStartOutOfBounds`, `AIStuck::onAIFall` and their constants (0.1, 0.04, 100, 0.8, 2.0 / 4.0, 10 units).
- **The user's two cases**, by following every caller of `onAIFall` (`mk7 xref` of `AIControlRace::onAIFall` (vtable),
  `AIEngine::onAIFall`, `AI::onAIFall`) and of `findNearEnemyPoint`.

#### What was changed

- **A stuck CPU is re-routed** (Findings 11, new Findings 12, guide sections [When a CPU gets stuck](README.md#when-a-cpu-gets-stuck)
  and [Helper routes](README.md#helper-paths-for-lost-cpus-and-bullet-bills), open questions). `AIStuck + 0x69`, listed as having no
  reader, is read by `AIControlBase::isAIFallSignal`, and `AIEngine::update` then re-routes the CPU to the nearest point at
  any height. It is set at 450 frames without an advance and every 120 frames of back-up phases 1 and 2. The guide said a
  CPU stuck at the same height is never re-routed and a helper path next to it is never chosen; both were wrong. A
  relocation also restarts the Lakitu count (`stateInitIdle`), which the guide did not say. Named
  `AIStuck::m_reroute_request` (provisional, no template, not in the patch).
- **A player's Bullet Bill starts at the nearest point** (Findings 6, 12, guide). Starting a Bullet Bill wakes the AI of a
  player's kart (`AIEngine::awake` from `statePlayerIdle`), which re-routes it with option 2 and relocates it even on the
  same path. The guide's "Does not work: Bullet Bill at its start" holds only for CPUs; the -2 row and the Max search Y
  offset section now mention it.
- **Other re-routes the document did not list** (Findings 12): `VehicleMove + 0xC94` bit 0 for more than 30 frames, or in
  Bullet Bill; the end of coin-battle gathering (`AIAutoSteer::stateExitGather`).
- **"Falling again and again"** counted only falls; `AIStuck::onAIFall` runs on every relocation of both control classes.
- **Lakitu after a back-up**: `m_back_frames` restarts when phase 2 begins, so the 10 seconds are not counted from the
  start of the back-up only.
- **Linked objects**: the escalator's starting value comes from its setting 2, and `MeltIce` starts open; the guide said
  every object starts closed.
- **Crossings**: `stateWait` also leaves to state 4 while `VehicleMove + 0xFF8 >= 1`.
- **Glossary**: `sinit_ObjectCrossingParam` initializes more than `sParam` (name marked provisional); the `AIEngine` state
  numbers, `AIStuck::m_reroute_request` and `AIAutoSteer::m_gather_target_found` (both provisional) and the new functions
  added.
- **Patches**: the second `## Patches` section, an older copy that left out the `ObjectBase` rename and
  `m_forward_speed_ratio`, was removed.

The patch was not changed.

#### What remains uncertain

- None of the re-routes of Findings 12 was watched in game, and no helper path was tested on a modified course.
- What `VehicleMove + 0xC94` bit 0 and `VehicleMove + 0xFF8` stand for.
- Which coin objects gathering looks at.

### Second follow-up research

Fourth research pass, 2026-10-05, same base commit and `eur2` image, asked after the fact check (see `Asked afterwards`).
Static work as before plus two throw-away scans of the whole disassembly (stores at +0xC94 / +0xFF4 / +0xFF8 / +0x94), and
one Azahar session: Grand Prix Flower Cup 150cc (Wuhu Loop, Mario Circuit, with the human player), balloon battles on
Sherbet Rink, Wuhu Town, GBA Battle Course 1 and N64 Big Donut, and N64 Kalimari Desert twice. The status is back to
`pending verification`: what is listed here has not been fact checked.

- **Tested in game** (Findings 13): the 7.5-second re-route, the wall re-route, a player's Bullet Bill start, the end of a
  player's race, a dead-end path, the board run-away, crossing waits.
- **Former open questions answered**: `VehicleMove + 0xC94` bit 0 is wall contact (`m_col_checks[1]`, Findings 12);
  `+0xFF8` / `+0xFF4` are the existing `m_ink_frames` / `m_star_frames`; the coins of gathering (Findings 12); the crossing
  exit (Findings 10, only partly: `m_is_far_behind` (then `m_is_far_ahead`) found and seen, the old case not reproduced); `m_depth` in battle
  (Findings 9); the dead-end path (Findings 13); the board run-away (Findings 10).
- **Added**: the original courses' helper paths (Findings 13, guide); the end-of-race re-route; `AIAutoSteer::m_is_far_behind` (then `m_is_far_ahead`)
  and the crossing exceptions in the guide.
- **Templates**: new `Enemy/AIStuck.hpp` and `Enemy/AIAutoSteer.hpp`; `AIEngine::m_wall_frames`,
  `AIControlRace::m_watched_ai`, `VehicleMove::m_col_checks`. Their members leave the "Other classes" table for glossary
  tables of their own. `mk7 --templates ... access` maps every access of the two classes onto the new layouts; `verify` passes
  for `EUR_REV2` and `USA_REV1`; `git apply --check` passes.
- **Tooling**: during the session the game crashed once in `RaceSys::ModeManagerBase::calc` (a call through a null vtable
  entry) while `mk7 emu continue --until results` finished the Music Park race right after a gdb session that had stopped in
  `AIPathManager::init`. It was not investigated; it may come from the tooling or from that breakpoint.
- **Left for a later session** (as asked): tests on courses with a modified KMP, such as helper paths added by hand.

For the fact check: Findings 9 (battle), 10 (`m_is_far_behind`, then `m_is_far_ahead`, run-away, second Kalimari run), 11 (wall counter), 12
(wall bit, table, coins), 13, the glossary tables of `AIStuck` and `AIAutoSteer`, and the guide sections [When a CPU gets
stuck](README.md#when-a-cpu-gets-stuck), [Helper routes](README.md#helper-paths-for-lost-cpus-and-bullet-bills), [Train
crossings](README.md#train-crossings) and the dead-end bullet of [How CPUs follow the route](README.md#how-cpus-follow-the-route).

### Fact check, fourth round

Second pass, fresh context, 2026-10-05, `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95). The repository was at
4767b3628594c92aa7b203b4b1d1430051f6ddd6; `template/` is unchanged since the base commit (`git diff --stat b65de46 HEAD --
template` is empty). Static work with `mk7 dis` / `decomp` / `read` / `access`, and one Azahar session (150cc Flower Cup,
races 1, 2 and 4) for `AIAutoSteer + 0x94`. At the user's request the topic was renamed from `enemy-point-path` to
"Enemy AI behaviour and enemy points" (folder `enemy-ai-behaviour-and-enemy-points`, patch of the same name).

#### What was re-checked, and how

- **Patch.** `git apply --check` passes on the base commit; applied to a fresh copy of `template/`, `verify --version
  EUR_REV2` and `verify` (USA_REV1) pass, before and after the changes below. `access --class Enemy::AIStuck` maps every
  access onto the new layout.
- **Glossary of `AIStuck` and `AIAutoSteer`.** Every offset against `AIStuck::init`, `stateCheckStuck`, `checkAccident_`,
  `stateInitBackPathPoint`, `stateBackPathPoint`, `stateStartOutOfBounds`, `stateIdle`, `onAIFall`, `onOutOfBoundsInner`,
  `stateInitIdle`, and `AIAutoSteer::init`, `stateIdle`, `isNeedWait_`, `stateInitWait`, `stateWait`, `isNeedRunAway_`,
  `stateRunAway`, `stateInitGather`, `stateGather`, `stateExitGather`. `m_gather_radius` (50 / 150 / 70 on course IDs 33 /
  35, 36 / other) checked against `template/RaceSys/ECourseID.hpp`.
- **Findings 11.** The constants 0.1, 600, 450, 901, 100.0, 0.04, 2.0 / 4.0, 0.8, the 120-frame modulo
  (`0x88888889`), the +3 per wall frame, the "fifth relocation within 10 units after a first one" rule (`3 < count` before
  the increment), the counters each state resets, `getInterpolateTarget` (target, previous point, history 0 to 2 for rates
  0 to 4), and the fall-through of `stateExitBackPathPoint`.
- **Findings 12.** `AIEngine::update` (re-route request, Bullet Bill and wall, more than 30 wall frames, `m_wall_frames`
  counted after the test), `awake`, `sleep`, `stateReady`, `statePlayerIdle`, the `AIEngine` vtable order, `isAIFallSignal`,
  `VehicleMove::VehicleMove` (five `CheckIF_EX` from +0xC80, `CheckIF::m_collision_result` at +0x4), `startKiller_Impl`,
  `awakeAI_byKillerStart`, `noticeAI_StartKiller`, `AI::startKiller`, `ChangeToAI`, `Director::changeToAI`, and the coin
  gathering.
- **Findings 10.** `set_isFlickering` (240 / 300), the crossing wait (500, 0.1 i.e. 84 degrees, 75 %), the run-away (90000,
  0.6, a random angle of up to 0.4 pi, 400 units, +50 in Y, 120 frames or 40 units), and
  `watchPlayerAndSwitchCollision` together with `LapRankChecker::calc`, see below.
- **Findings 13** (dead-end read): `selectNextPointHandle_` reads `m_next_points[idx]` with the index 0 when
  `m_next_count` is 0 or 1. The other in-game results of Findings 13 were not repeated; they agree with the code read here.
- **Older findings, spot check.** The constants of Findings 4 to 7 cited in `## How to verify` (19600, 0.3, 10000 / 0.1,
  78400, 40000, 250000, 75, 32400, +-0.85, 0.98, 0.998) read again.

#### What was changed

- **`AIAutoSteer::m_is_far_ahead` is set for CPUs far behind, renamed `m_is_far_behind`** (glossary, Findings 10 and 13,
  guide [Train crossings](README.md#train-crossings), patch). `watchPlayerAndSwitchCollision` writes 1 when the CPU's own
  `m_current_race_progress` is **lower** than the watched kart's, and `LapRankChecker::calc` gives rank 1 to the highest
  value, so the CPU is behind. Measured in game (Findings 13): with the player's kart driven as a CPU and with a human
  player, CPUs more than 1500 units behind had the flag, CPUs more than 1500 units ahead never did. The guide said that
  CPUs far ahead of the player do not wait at crossings; it is CPUs far behind.
- **`AIAutoSteer::m_wait_reversing` renamed `m_wait_any_direction`** (glossary, Findings 10, patch). It holds status bit
  0x10000 (`accident_1`) when the wait began, and what it does is keep the wait going when the crossing is behind the kart.
  What `accident_1` stands for is an open question, so the old name claimed something that was not shown.
- **Guide, [When a CPU gets stuck](README.md#when-a-cpu-gets-stuck).** The checks are paused for status bit 0x10000, not for
  "spinning out" (the meaning of that bit is not known), and also while a battle CPU runs away from a board
  (`checkAccident_`, state 5). The Lakitu count after a back-up starts again near the spot of step 2 (the spot the CPU
  drives to), not of step 3.
- **Findings 10.** The 500-unit test of `isNeedWait_` is an integer compare of the float bits, not a float compare.
- **Findings 12.** `startKiller_Impl` calls the two `Director` functions only when its `bool` argument is 0.
- **Patch.** The two renames and their comments in `Enemy/AIAutoSteer.hpp`; the comment of `ObjectBase::m_ai_signal`
  names the topic by its new name. Regenerated from a fresh work copy; nothing else in it changed.
- **`## How to verify`.** New paths, and the commands for the progress comparison and the rank order.

#### What remains uncertain

- The in-game tests of Findings 13 other than the new one were not repeated in this pass.
- The course IDs of the races used for the new measurement were read only for the first one (Wuhu Loop, 8).
- What status bit 0x10000 (`accident_1`) and `AIControlRace + 0x91` stand for, as before.
- No course with a modified KMP was tested; the course-creator advice is still untested on one.

### Document review

Third pass, fresh context, 2026-10-05, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2` (sha1
e3edb9771fea3149ddfe309e3ca8453046ef8a95). The document was brought to the current WRITING.md; the
passes before it followed older rules.

#### What was changed

- **Structure.** `## Summary` and `## Course creator guide` became `## Overview`, which now comes before `## Glossary`.
  The header keeps Status, Asked, Base commit and Images; the two follow-up questions are listed under Asked, the Input
  and Data lines and the "Terms" paragraph moved to [Sources and method](README.md#sources-and-method), and the rename of the topic
  is recorded in the fourth fact check. `## Differences from the input notes` became Finding 16. The Review keeps every
  earlier pass, under headings that follow the same pattern.
- **Overview.** It opens with what was found. A new [Words used in this document](README.md#words-used-in-this-document)
  introduces race and battle mode, previous and next paths, forks and branches, route points, the target point, Lakitu
  and respawn points, Bullet Bill and the re-route before any section relies on them; [Re-routes](README.md#re-routes) explains the
  nearest-point search once, before the settings that use it. The CPU level and the Mii titles table (which was at the
  end) moved before the settings. The two summary tables moved to the end ([Race and battle
  compared](README.md#race-and-battle-compared), [What each setting does, at a glance](README.md#what-each-setting-does-at-a-glance)) and
  lost their code names (`PathSmoother`, `m_link_end_flags`, `IsRaceTypeThinkAsRace()`, `scale * 50`, ...). The byte
  layouts of the two entries moved into the sections of their settings.
- **Bold-titled paragraphs** became headings: in the overview ("Race courses", "Battle courses", "Placing race points",
  "Mushroom shortcuts", the eight flags, "Race." / "Battle." of the path lists, the stuck-CPU mechanisms) and in Findings
  5, 6, 10, 11, 12 and 13. The "Works:" / "Does not work:" bullets of the helper paths became a table. Finding headings no
  longer carry code names.
- **Wording.** One term per thing: "helper path" (was also "helper route"), "respawn point" (was also "Lakitu point" and
  "Lakitu respawn point"), "target point" (was also "the point the CPU is heading to"), "re-route" for the nearest-point
  search. The rows -1 and -2 of Path find options said "never put back on these points after falling off"; the option is
  read by the re-route (Findings 6 and 12), while a Lakitu respawn uses the point found at load with no option (Findings 1
  and 7), so they now say "never re-routed to these points". "Findings N" became "Finding N" for a single finding.
- **Overview claims backed by findings.** Measurements that the overview used but that were only in the review moved into
  the findings: the advances and the distance to the new target (Finding 5); the lane range, the lane changes, the two
  extra Mushroom branches, the drift measurements, the 2-second limit of flag 0x10 and the battle centring (Finding 6); the
  values of the original courses (new Finding 14); the title-to-bit mapping (new Finding 15). Every overview section links
  to its findings. "About 375 on average" became "half of the time more than about 375": the fact check measured a
  median.
- **Finding 10.** The Kalimari Desert measurement stood under the battle run-away heading; it has its own subsection now,
  before the second run that refers to it.
- **Addresses** in the findings and the glossary notes were replaced by the function, instruction or constant they pointed
  to. The static initializer that writes the 20-frame constant and the data it writes are named (`sinit_AirborneFramesParam`,
  `sAirborneFramesParam`); its start, 0x0054DD78, was found from its `push` (the address cited before, 0x0054E720, is the
  store inside it). The default normal and the vtables cited got rows in `### Data`.
- **Offsets** in part 2 were replaced by member names. Existing names the text used are now in the glossary
  (`VehicleMove::m_status_flags` and its bit names, `m_air_frames`, `m_boost_frames`, `VehicleBase::m_is_fake_goal`,
  `unk_0x99`, `Director::m_is_ai_valid`, `CRaceInfo::m_race_mode`, `m_engine_level`, `m_race_mode_flag`,
  `MenuData::m_ai_level`, the `AIControlBase`, `AIEngine` and `AIManager` pointers, ...). Members of classes without a
  template got descriptive names in [Other classes](README.md#other-classes) (`ObjectCrossing`, `Coin`, `AIObjectSearcher`,
  `DriveInfo`, `AI::m_ai_engine`).
- **Glossary.** The Functions table has the Status and Note columns and lists the about 60 functions the text cited
  without an entry.
- **How to verify** uses symbol names where `mk7` accepts them, and is split into code, patch and course data; the
  `access` commands run on the patched work copy.

No claim was changed beyond the wording above.

#### What looks factually wrong

These overview statements have no finding behind them, and none of the earlier reviews gives evidence for them either.
They were left as they were for pass 2 to support or remove:

- "Lanes beyond 50 % slowly settle back to at most 50 %" ([Scale](README.md#scale-width)) and "lanes beyond 50 % settle back three
  times faster" for Safe Driver ([Mii titles](README.md#cpu-levels-and-mii-titles)). `AIPathPoint::calcPointOffsetDistance_` is in
  the glossary but no finding describes it.
- Boost Jumper "hops very often" and Aviator "hops at every trick chance" (Mii titles table). Finding 6 only says that
  the hop block asks the probability class for CPUs without a title.
- Drift Wizard: "drift start check always passes" (Mii titles table). Finding 6 shows bit 0x20 only in the mini-turbo
  test.
- "It never uses one [a Mushroom] while drifting" ([Mushroom setting](README.md#mushroom-setting)).
- "In a race it follows the engine class: 50cc, 100cc, and 150cc, which online races also use", and the "150cc and online"
  of flag 0x01, flag 0x80 and the shortcut table. Finding 6 gives the multiplayer case for battle only. Read while
  reviewing: with `CRaceInfo::m_race_mode_flag.multiplayer_or_online` set, `AIManager::calcAILevel_` gives level 2 when
  `CRaceInfo::m_race_mode.m_play_mode` is 2 and the engine class otherwise, so the statement may hold, but it needs a
  finding (which play mode 2 is was not checked).

#### Noted, not blocking

- The new member names of the gaps (`VehicleMove::m_air_rate`, `m_drift_state`, `m_forward_dir`,
  `VehicleControlAI::m_max_speed_ratio`, `m_award_flag`, `m_collision_switch`, `AIControlRace::m_skip_watch`,
  `AIControlBattle::m_search_weights`, `m_coin_search_state`, `m_lock_on_keeps_backward_block`,
  `CoinManager::m_coin_num`, `m_coins`) are provisional and not in the patch. WRITING.md wants new names in the patch;
  adding them needs their types checked, which is pass 1 or 2 work.
- `AIControlBattle::m_lock_on_keeps_backward_block` reads "the byte at its +0x95" of Finding 8 as a member of
  `AIControlBattle`; the finding did not say which object.

The status is set back to `pending verification`, so that the topic goes through pass 2 again for the statements above.

### Fact check, fifth round

Second pass after the document review, fresh context, 2026-10-05, `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95).
The repository was at 4767b3628594c92aa7b203b4b1d1430051f6ddd6; `template/` is unchanged since the base commit. Static
only (`mk7 dis` / `decomp` / `xref` / `read`, and a throw-away reader of the English `Common.msbt`); nothing was run in
Azahar. The pass covers the statements the document review listed under "What looks factually wrong" and its two
non-blocking notes; the findings that the four earlier fact checks re-checked were not checked again, except for the
patch.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes on the base commit; applied to a fresh copy of `template/`, `verify --version
  EUR_REV2` and `verify` (USA_REV1) pass.
- **Lanes beyond 50 %.** `AIPathPoint::calcPointOffsetDistance_` disassembled (the decompiler output garbles the two
  float-bit compares), its only caller (`goNextPoint`, outside the `m_is_killer` branch) and `AIManager::getRandF32`.
- **Hops of Boost Jumper and Aviator.** The hop block of `AIDriftDrive::calcSteerNormal_`, disassembled past the literal
  pool at which `mk7` ends the function (0x0032FCB8 to 0x003301CC).
- **Drift Wizard drift start.** `AIControlBase::setBasicDriveInfo_` and `AIProbabilityRace::isLaunchDrift` (slot 3 of the
  `AIProbabilityRace` vtable, `mk7 xref`); the constant 160000 read again.
- **No Mushroom while drifting.** `AIItemRace::stateKinoko`.
- **CPU level of races with the multiplayer bit.** `AIManager::calcAILevel_` disassembled; `CRaceInfo::m_race_mode` and
  `ERacePlayMode` in `template/`; the writer of the bit, `RaceSys::CRaceInfo::updateRaceModeFlag`.
- **Title order.** The title messages 1900 to 1915 of `pat1:/Patch/UI/common-ee/Common.msbt` against the value-to-bit
  switch of `AI::init`.
- **`AIControlBattle` +0x95** (then `m_lock_on_keeps_backward_block`). `stateInitLockedOn` disassembled.

#### What was changed

- **All five statements hold**, and each now has a finding behind it: the lane drift-back and its Safe Driver factor
  (Finding 6, `scale`), the hops (Finding 6, flag 0x08), the drift-start check skipped by bit 0x20 (Finding 6,
  `drift_setting`), no Mushroom while drifting (Finding 6, `mushroom_setting`), and the CPU level of races (Finding 6,
  AI level: single-player and local multiplayer races follow the engine class, online races always use level 2). Finding
  15 lists the new readers.
- **Found while checking the hops** (Finding 6, flag 0x08; overview Mii table): Boost Jumper also hops on its own every
  120 to 299 frames; bit 0x800 (value 12, Model Driver by the message order) hops at every trick opportunity like
  Aviator; Rookie and Star Racer (0x1100) never hop at trick opportunities. Added to the table, with a row for 0x800.
- **Overview wording.** "50cc, 100cc, and 150cc, which online races also use" now says that online races use the 150cc
  level. The sentence under the Mii table said "the first four rows" match the code; it is bits 0x4, 0x20, 0x40 and 0x80,
  which are not the first four rows.
- **`AIControlBattle::m_lock_on_keeps_backward_block`** (now `m_do_not_select_backward`, see below) is a byte of the
  `AIControlBattle` object itself: `stateInitLockedOn`
  reads it with `ldrb r2, [r0, #0x95]` on the same `this` through which it writes `m_search_mode`. Finding 8 and the
  glossary say so.
- **Glossary.** `AIDriftDrive::m_hop_interval` / `m_hop_frames` (Other classes), `CRaceInfo::m_race_mode.m_play_mode`,
  and the functions `AIManager::getRandF32`, `AIProbabilityRace::isLaunchDrift`, `CRaceInfo::updateRaceModeFlag`.
  `How to verify` has the commands for all of the above; Confidence lists the new code-only results as likely.

- **Gap names in the patch** (the review's first non-blocking note, done at the user's request). The access widths were
  taken from a throw-away scan of the whole `eur2` disassembly for loads and stores at each offset, from `mk7 access
  --class`, and from the constructors:
  - `VehicleMove::m_drift_state` is a `u8`, not a `u32` as the glossary said: every access in the code is `ldrb` / `strb`.
    `m_air_rate` `f32`, `m_forward_dir` `sead::Vector3f` (read as three floats by `calcSteerNormal_`).
  - `VehicleControlAI::m_max_speed_ratio` `f32` (word stores in `AIControlRace::update`); `m_award_flag` and
    `m_collision_switch` `bool` (byte stores in `VehicleControlAI::init` and their writers; `m_collision_switch` is also
    read by `ObjectBase::checkDetail_KartHitObj`). `AIControlRace::m_skip_watch` `bool`.
  - `AIControlBattle` +0x90, called `m_coin_search_state`, is written by the virtual `AIControlBattle::setBattleType(int)`
    (a `dlp` name) and is renamed `m_battle_type`: `TeamInfo::decideTeamBattleType` sets 1 or 2 per CPU in coin battle.
    +0x95, called `m_lock_on_keeps_backward_block`, is written by `AIControlBattle::setDoNotSelectBackward(bool)` and is
    renamed `m_do_not_select_backward`. `m_search_weights` is an `s32 *` (two entries summed by `stateInitSearchRival`).
    The constructor zeroes all three.
  - `CoinManager::m_coin_num` / `m_coins` (+0x48E8 / +0x48F0) are one `sead::PtrArray<Coin>` at +0x48E8: the gathering
    code reads the count, skips one word (the maximum) and reads the pointer array.

  The patch now adds these members to `Kart/Vehicle/VehicleMove.hpp`, `Kart/Vehicle/VehicleControlAI.hpp`,
  `Enemy/AIControl/AIControlRace.hpp`, `Enemy/AIControl/AIControlBattle.hpp` and `Object/CoinManager.hpp`, regenerated
  from a fresh work copy. `git apply --check` passes; `verify --version EUR_REV2` and `verify` (USA_REV1) pass, and
  `struct` shows each member at its offset. The members of `AIDriftDrive` stay in Other classes, since that class has no
  template.

#### What remains uncertain

- The new results were read in the code, not watched in game.
- What `AIControlBattle::m_battle_type` 1 and 2 mean, and what `m_drift_state`, `m_forward_dir`, `m_award_flag`,
  `m_collision_switch` and `m_skip_watch` stand for beyond the uses quoted (their names stay provisional).

### Document review, second round

Third pass after the fifth fact check, fresh context, 2026-10-05, on base commit
b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95). The whole document
was read against WRITING.md. The code was looked at only to understand two passages
(`AIControlRace::onAIFall`, `AIStuck::stateCheckStuck`).

#### What was changed

- **Ideas introduced before use (overview).** [Words used in this document](README.md#words-used-in-this-document) now introduces
  merges and junctions, which the overview used without explaining. The Mii title table relied on lanes, the drift start
  check, shortcuts, -3 / -4 paths, board-linked branches and trick chances, all explained later; it moved to a new
  section after the settings, [What each Mii title changes](README.md#what-each-mii-title-changes), next to the other summary
  tables, with links to where each term is explained. [CPU levels and Mii titles](README.md#cpu-levels-and-mii-titles) keeps a
  short introduction of Mii CPUs, which the settings sections need. The opening summary no longer uses "junction" before
  it is introduced, the Drift setting section names the "drift start check" that the Mii table refers to, and STGI is
  explained where the lanes use it.
- **Battle boards in the overview.** [When a CPU gets stuck](README.md#when-a-cpu-gets-stuck) named "running away from a board"
  without the overview ever explaining it. A short section, [Moving boards in battle](README.md#moving-boards-in-battle), now
  gives what Finding 10 says about it. Finding 10, which held both the crossings and the boards, is renamed "Train
  crossings and battle boards".
- **Wording.** [Re-routes](README.md#re-routes): "more than 180 units away from it" now says from the CPU (`AIControlRace::onAIFall`
  compares each point with the kart position, and Finding 12 says so), and the height limit is explained in a few words
  before the link to its setting. The section said that a CPU keeps its target when the nearest point is on its own path,
  while [Flag 0x02](README.md#flag-0x02-height-re-route) and Finding 5 say that the height re-route gives it up in any case; it now
  names that exception. [Re-route after 7.5 seconds](README.md#re-route-after-75-seconds) said "on any path and at any height"
  next to the height limit; it now says what was meant (unlike the height re-route, the target need not be above or
  below the CPU, Finding 12) and refers to [Re-routes](README.md#re-routes) instead of repeating the search. [Path find
  options](README.md#path-find-options): "Race only, except that any value other than 0 also has the effect in the last row" now
  says that every non-zero value has the effect of the last row on top of its own. Finding 11: "+3 while the kart touches
  a wall" now says "+3 instead on such a frame", i.e. a slow frame (the counter only grows on slow frames, as the code
  shows). "Lakitu point" in Findings 1 and 7 became "respawn point", the term of the rest of the document.
- **Structure.** In [Moving on to the next point](README.md#moving-on-to-the-next-point) the explanation of "driven past" now
  directly follows the sentence that uses it. In [Position](README.md#position) and [Scale](README.md#scale-width) race comes before
  battle, as everywhere else, and Scale no longer opens its bullets with bold "Race:" / "Battle:" labels.
- **Part 2, names before use.** Finding 1 says in a few words what `PathSmoother` and `PathAnalyzer` are, and Finding 5
  introduces `AIPathPoint`, its aim point `m_target_trans` and the two `PointParam` pointers before the pseudo-code of the
  reach test uses them.
- **Glossary.** The rows of [Other members](README.md#other-members) and [Other classes](README.md#other-classes) are grouped by class and
  ordered by offset; no row was changed.
- **Confidence and Open questions.** Two items listed under "Likely" were open questions (the side the sign of
  `m_corner` stands for, and the 65-frame crossing exit); they moved to [Open questions](README.md#open-questions), together with
  the questions that were only in the reviews (the award value 1 of `max_search_y_offset`, `m_battle_type` 1 and 2, the
  provisional names).

No claim was changed beyond the wording above.

#### What looks factually wrong

- [What this means for a course](README.md#what-this-means-for-a-course): "A CPU that is stuck against a wall or in a corner with
  no way out, and whose nearest enemy point is on the path it is following, loses about 10 seconds before it backs up, and
  if the back-up does not bring it to a new point, Lakitu takes it about 5 seconds after the back-up ends." By
  [Backing up](README.md#backing-up) and Finding 11, a slow CPU that also touches a wall counts 3 frames per frame and backs up
  after about 3.3 seconds (`AIStuck::stateCheckStuck`: `m_slow_frames` is set to the old value + 3 instead of + 1 when
  bit 0 of `m_col_checks[1].m_collision_result` is set, inside the slow-speed branch). With the 15-second Lakitu limit
  and the back-up time not counted, Lakitu would then come about 11.7 seconds after the back-up ends, not 5. The figures
  of the sentence hold for a CPU that is slow without touching a wall. Whether a CPU pressed against a wall counts as slow
  at all was not measured (in the DK Pass test of Finding 11, a CPU held in place had a speed ratio of about 1.1). Pass 2
  should establish which case the sentence describes and correct the figures.

#### Noted, not blocking

- The overview says that a CPU moves on within 280 units (100 in battle) "of its target point". Finding 5 measures the
  distance to the aim point, which is the target point moved sideways to the CPU's lane (by up to 85 % of the
  half-width). The overview's simpler wording was kept; the invisible wall bullet of the same section already uses the
  aim point.

The status is set back to `pending verification`, so that the topic goes through pass 2 again for the statement above.

### Fact check, sixth round

Second pass after the second document review, fresh context, 2026-10-05, `eur2` (sha1
e3edb9771fea3149ddfe309e3ca8453046ef8a95), repository at 4767b3628594c92aa7b203b4b1d1430051f6ddd6 (`template/` unchanged
since the base commit). Static (`mk7 dis`), then one test in Azahar ([Measured in game](#measured-in-game)). The pass covers only the statement the
document review listed under "What looks factually wrong"; the rest was not checked again, except for the patch.

#### What was re-checked, and how

- **The faster count against a wall** (`AIStuck::stateCheckStuck`, 0x0033D01C): inside the slow branch (`ldr r0, [r0,
  #0xf30]` / `cmp r0, r1` / `bge` against 0x3DCCCCCD) `m_slow_frames` is incremented, then `addne r1, r0, #2` / `strne`
  when bit 0 of `VehicleMove` +0xC94 is set, so a slow frame against a wall adds 3. The limit is `cmp r0, #0x258` / `ble`,
  so the back-up starts on the 201st such frame (3.35 seconds), against the 601st frame (10 seconds) otherwise. Confirmed.
- **The wall re-routes do not reset the counters**: `AIControlRace::onAIFall` (0x00333CC8) calls `AIStuck::onAIFall` (at
  0x00333DA8) only after the path-index compare (`beq loc_333e68` skips it) or for a player's kart, as Finding 12 says. A
  CPU whose nearest point is on its own path is therefore not reset by the half-second wall re-routes, the 7.5-second
  re-route or the re-routes during the back-up.
- **Lakitu after the back-up**: `m_no_advance_frames` is not updated during the back-up (Finding 11) and Lakitu comes at
  901 frames. A CPU that stopped advancing when it became slow has 601 frames after a back-up without a wall (300 left,
  5 seconds) and 201 against a wall (700 left, about 11.7 seconds). If it stopped advancing earlier, Lakitu comes sooner,
  hence "at most"; a further back-up pauses the count again.
- **The patch**: `git apply --check` passes on the repository; on a fresh copy of `template/` with the patch applied
  (`mk7-llm-research/local/work/enemy-ai-pass2/`), `mk7 --templates ... verify --version EUR_REV2` and `verify` (USA_REV1)
  both pass.

#### What was changed

- [What this means for a course](README.md#what-this-means-for-a-course): the document review was right. The sentence gave the
  figures of a CPU that is slow without touching a wall (10 seconds, then Lakitu about 5 seconds after the back-up) for a
  CPU "stuck against a wall". It now gives both cases: 10 seconds and at most about 5 seconds without a wall, about 3.3
  seconds and at most about 11.7 seconds against a wall, and 15 seconds with no back-up if a CPU against a wall is not
  slow. It also says that the re-routes change nothing for such a CPU, which is why the timings apply.
- [Open questions](README.md#open-questions): whether a CPU pushing against a wall counts as slow; added, then answered in game and
  removed again.

#### What remains uncertain

- Nothing for the statement checked. The two 11.7- and 5-second figures after a back-up that ends are computed from the
  code, not measured; the in-game test below ended through the 10-second back-up limit instead.

#### Measured in game

Asked by the user after the static check, same session, in Azahar (`mk7 emu`, 150cc Flower Cup with the player's kart
as a CPU, Mario Circuit). A throw-away script read the kart's `VehicleMove` and its `AIStuck` (through
`Kart::Director::m_ai_manager` -> `AIManager::m_ais[i]` -> `AI + 0x8` -> `AIEngine::m_ai_control` ->
`AIControlBase::m_ai_stuck`, matched to the kart by `AIStuck::m_ai`) every frame. The test is the last bullet of [Stuck
CPUs measured in game](README.md#stuck-cpus-measured-in-game).

- A CPU pushing against a wall counts as slow: speed ratio 0.035 to 0.05, so the +3 count applies and it backed up after
  about 200 slow frames. The open question this round had added is answered and removed.
- The wall re-routes did not move it (nearest point on its own path), as the static check said.
- Its back-up drove it into another wall and Lakitu came through the 10-second back-up limit. [What this means for a
  course](README.md#what-this-means-for-a-course) now gives that case too, with the measurement, and [Lakitu](README.md#lakitu) and
  [Confidence](README.md#confidence) mention it.
- Two earlier attempts on GBA Bowser Castle 1 and on the Mario Circuit start straight put the kart where there was no
  floor; it fell and Lakitu took it. They say nothing about walls.

### Document review, third round

Third pass after the sixth fact check, fresh context, 2026-10-05, on base commit
b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95); the repository was
at 4767b3628594c92aa7b203b4b1d1430051f6ddd6 and `template/` is unchanged since the base commit. The whole document was
read against WRITING.md. The code was looked at only to understand one passage (the Bullet Bill
branch of `AIControlRace::update`, see below) and to find the addresses of two functions the text names.

#### What was changed

- **Wording.** One term for the hop at a ramp or jump: part 2 said "trick opportunity" where the overview says "trick
  chance"; Findings 6 and 15 now say "trick chance" too, and the battle cell of flag 0x80 in the flags table says "hop at
  every trick chance" instead of "trick at every chance". In [How to build one](README.md#how-to-build-one), "a point added to the
  main path" could be read as one of the points the game adds in a race; it now says "an extra enemy point on the main
  path". [Helper paths on the original courses](README.md#helper-paths-on-the-original-courses) said "8 on average" for a median
  (Finding 13); it now says "typically about 8".
- **Ideas introduced before use.** [Re-routes](README.md#re-routes) named "a player's kart that the game drives" before the
  overview says when that happens; it now says in a few words (during the player's Bullet Bill and once the player has
  finished, as in the table of [When a helper path is used](README.md#when-a-helper-path-is-used) and Finding 12). Finding 5 used
  "relocation" before saying what it is; its first use now explains it.
- **Overview, technical detail.** [Race and battle compared](README.md#race-and-battle-compared): "not seen exactly sideways"
  became "unless the point is almost exactly to the side of the kart", and "applied to X and Z" was dropped from the battle
  lane (it stays in Finding 6).
- **Addresses in the findings.** Finding 10 cited the decompiler label `DAT_0032d58c`, which is an address; it now says
  that the function loads the constant.
- **Glossary.** `Item::KartItemProxy::getStockItem` (Finding 6) and `Util::TStateObserverEx<Enemy::AIEngine>::executeState`
  (Finding 12, which called it "`executeState`") were cited without a row in the Functions table; added, and the text names
  them in full.
- **Confidence.** The list of what was confirmed in game cited "Findings 9 to 11" and "(Finding 13)" for results that are
  in Findings 3 to 13; it is now a list with the finding of each result. No item was added or removed.
- **Layout.** Two paragraphs of the overview were wrapped in the middle of a sentence ([Lakitu](README.md#lakitu), [What this
  means for a course](README.md#what-this-means-for-a-course)), and Finding 12 had a doubled blank line.

No claim was changed beyond the wording above.

#### What looks factually wrong

- **"Enemy point" in the nearest-point search.** The overview says that a re-route, the Max search Y offset and the
  respawn points look for the nearest **enemy point** ([Re-routes](README.md#re-routes), [Max search Y offset](README.md#max-search-y-offset),
  [Re-route after 7.5 seconds](README.md#re-route-after-75-seconds), [Helper paths](README.md#helper-paths-for-lost-cpus-and-bullet-bills),
  the Lakitu row of [When a helper path is used](README.md#when-a-helper-path-is-used)). By the overview's own words, an enemy point
  is a KMP entry, and in a race the route points also include the points the game adds. Part 2 says that in a race the
  search runs over the race accessor, which holds the KMP points plus the added ones (Finding 1, step 4; Finding 7, last
  bullet), and Finding 13 measured it: on Wuhu Loop (339 enemy points, 665 route points) a CPU held on point 478 was
  re-routed to point 308. So in a race the nearest **route point** is found. The consequences for the advice were not
  worked out and are left to pass 2: the respawn bullet of [Max search Y offset](README.md#max-search-y-offset) ("if there is none,
  a CPU rescued there is sent back to the first enemy point") may not hold when an added point is within 500 units, and
  [How to build one](README.md#how-to-build-one) ("the nearest ones only from the spots where CPUs get stuck") would have to count
  the added points of the main route, which lie between its enemy points. Not changed here, because the correction
  changes what these statements say.
- **Flag 0x40, "stuck for 7 seconds between two points".** [Flag 0x40](README.md#flag-0x40-bullet-bill-cannot-end) says that a
  Bullet Bill still ends "when the kart gets stuck for 7 seconds between two points". Finding 6 only says "after 420 held
  frames it is forced to 61", without saying what restarts that count, so the overview statement has no finding behind
  it. Read while reviewing, to understand the passage: `AIControlRace::update` zeroes a 16-bit counter of the
  `AIControlRace` object (+0x7C) on a frame with `AIPathHandler::m_advanced_this_frame`, and in the ending phase counts it
  up while `m_current_param` has flag 0x40 and zeroes it without the flag; at 421 it writes 0x3D to the Bullet Bill timer.
  That seems to support the overview, but it needs a finding (and a name for the counter), which is pass 2 work.

#### Noted, not blocking

- The earlier subsections of this review keep the addresses and offsets they cited; they are records of those passes
  and were not rewritten.
- Some lines of part 2 are longer than the rest (decompiled quotes, instruction lists); they were not reflowed.
- The first document review's note still holds: the overview measures "within 280 units of its target point", while the
  reach test uses the aim point on the CPU's lane (Finding 5).

The status is set back to `pending verification`, so that the topic goes through pass 2 again for the two statements
above.

### Fact check, seventh round

Second pass after the third document review, fresh context, 2026-10-05, `eur2` (sha1
e3edb9771fea3149ddfe309e3ca8453046ef8a95), repository at 4767b3628594c92aa7b203b4b1d1430051f6ddd6 (`template/` unchanged
since the base commit). Static only (`mk7 dis`, `mk7 decomp`), plus two throw-away scripts over the KMP files of the
RomFS. The pass covers only the two statements the document review listed under "What looks factually wrong"; the rest
was not checked again, except for the patch.

#### What was re-checked, and how

- **Which points the nearest-point search covers.** `AIPathManager::init` picks its point accessor at the top:
  `IsRaceTypeThinkAsRace()` gives `AIPathManager` + 0x28 (filled by `PathSmoother::setupAccessor`), otherwise
  `Field::GetEnemyPointAccessor()`; the `m_nearest_enemy_point` loop of the respawn points passes that accessor to
  `findNearEnemyPoint`. `AIControlBase::initAfterManager` stores `AIPathManager::getEnemyPointAccessor()` at + 0x38, and
  `getEnemyPointAccessor` returns + 0x28 in race mode (`addne r0, r4, #0x28`) and the KMP accessor otherwise.
  `AIControlRace::onAIFall` and `AIControlRace::startKiller` pass + 0x38 to `findNearEnemyPoint`. So in a race every
  nearest-point search (re-routes, Bullet Bill start, respawn points) and the race start point
  (`FindNearestEnemyPtHndlFromSector` on + 0x28) run over the re-sampled list, inserted points included, which matches
  the Wuhu Loop measurement of Finding 13. The review was right.
- **The consequences for the advice.** An inserted point copies the whole 0x18-byte entry of the nearer KMP point
  (Finding 3), `max_search_y_offset` and `path_find_options` included, so the height limit and the skip options apply to
  it. Index 0 of the re-sampled list is the copy of the first point of path 0, and in all 39 KMP files of the RomFS with
  enemy paths path 0 starts at enemy point 0. `findNearEnemyPoint` keeps only the first 128 points within 500 units by
  index; an estimate of the re-sampled lists of the original courses (Finding 3's counts, straight lines) gives at most
  103 near a respawn point, so the cap does not change the result of Finding 7 there.
- **Flag 0x40 and the 7 seconds.** In `AIControlRace::update` (0x00333548): near the top, before the Bullet Bill test, a
  frame with `AIPathHandler::m_advanced_this_frame` zeroes the u16 at + 0x7C (`strh r7, [r4, #0x7c]`). In the ending phase
  (`AIControlRace` + 0x90 set), after the test that ends the Bullet Bill once the timer at + 0x74 is above 60: with flag
  0x40 on `m_current_param` the counter is incremented and, above 420, the timer is set to 61; without the flag the counter
  is zeroed and the timer incremented. `startKiller` and the switch to the ending phase by the timer also zero it. The
  overview statement holds, read as "7 seconds in a row on the flagged stretch without reaching a new point".
- **The patch**: `git apply --check` passes on the repository; on a fresh copy of `template/` with the patch applied
  (`mk7-llm-research/local/work/enemy-ai-pass2-r7/`), `mk7 --templates ... verify --version EUR_REV2` and `verify` (USA_REV1)
  both pass.

#### What was changed

- "Nearest enemy point" became "nearest route point" where the search is meant: the overview summary, [Position](README.md#position)
  (race start point), [Re-routes](README.md#re-routes) (which now says that in a race the added points are searched too, and that
  they copy the height limit), [Max search Y offset](README.md#max-search-y-offset), [Flag 0x02](README.md#flag-0x02-height-re-route),
  [Re-route after 7.5 seconds](README.md#re-route-after-75-seconds), [What this means for a course](README.md#what-this-means-for-a-course),
  the introduction of [Helper paths](README.md#helper-paths-for-lost-cpus-and-bullet-bills), the Lakitu row of [When a helper path
  is used](README.md#when-a-helper-path-is-used) and the list of [Confidence](README.md#confidence).
- [Max search Y offset](README.md#max-search-y-offset), respawn bullet: a respawn point needs a **route** point within reach; the
  fallback is point 0 of the route (enemy point 0 on the original courses), not "the first enemy point"; an added point is
  enough in a race, but an enemy point within 500 units is advised since the added points cannot be seen in the KMP and
  the straight stretches have none. The statement about the original courses now says that it was checked against the
  enemy points only.
- [How to build one](README.md#how-to-build-one): in a race the helper path must be nearer than the main route itself, whose points
  (added ones included) lie every 75 to 150 units, not only nearer than its enemy points.
- [Flag 0x40](README.md#flag-0x40-bullet-bill-cannot-end): "stuck for 7 seconds between two points" became "7 seconds in a row on
  the flagged stretch without reaching a new point (for example when it is stuck between two points)".
- Part 2: Finding 1 (step 4 names the accessors), Finding 6 (the flag 0x40 counter, with the instructions), Finding 7 (race
  start point and respawn search on the race accessor, what index 0 is, the 128-point cap), Finding 12 (the accessor of the
  re-route search).
- Glossary: `AIControlRace::m_killer_hold_frames` (new, also added to the patch), `AIPathManager::m_race_point_accessor` /
  `m_race_path_accessor` (no template), `AIPathManager::getEnemyPointAccessor`, and the note of
  `MapdataJugemPoint::m_nearest_enemy_point`. The name `m_nearest_enemy_point` was kept: the entries of the re-sampled list
  are `MapdataEnemyPoint` objects as well, and the game's search is `findNearEnemyPoint`.

#### What remains uncertain

- The end of a Bullet Bill held by flag 0x40 for 7 seconds was read in the code, not measured in game.
- The 103-point estimate of the re-sampled lists is an approximation (straight lines instead of the Bézier, inserted
  points only inside each path); the margin to 128 makes the conclusion safe, but the count itself is not exact.

### Document review, fourth round

Third pass after the seventh fact check, fresh context, 2026-10-05, on base commit
b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95); the repository was
at 4767b3628594c92aa7b203b4b1d1430051f6ddd6 and `template/` is unchanged since the base commit. The whole document was
read against WRITING.md, and a throw-away script checked that every internal link resolves, that no
address appears outside the glossary, `## How to verify` and the review, and that every function the text cites has a
row in the Functions table. The code was looked at for two passages (`AIItemRace::stateInitKinoko`, the item test of the
mushroom shortcut; the `AIControlBase` template, for the accessor of Finding 12) and the six battle KMPs of
`rom:/Course` were read for one (the settings the battle courses use).

#### What was changed

- **Names, part 2.** Finding 12 cited the re-route accessor as "`AIControlBase` + 0x38"; `template/` already names that
  member `AIControlBase::m_enemy_point_accessor`, which the text now uses, with a row in [Other members](README.md#other-members).
- **Glossary.** `Field::GetEnemyPointAccessor` (Finding 1, Finding 12) had no row in the Functions table; added
  (0x003A83C4). `AIItemBase::isPowerfulKinoko_` added with the change below (0x0032AF14).
- **Overview claims backed by findings.** The shortcut table says that a CPU holding a Golden Mushroom never takes a
  shortcut, while Finding 6 only said "a 'powerful' mushroom". `AIItemRace::stateInitKinoko` calls
  `AIItemBase::isPowerfulKinoko_`, which tests item slot 11, `eItemSlot::KinokoP` (the Golden Mushroom) in
  `template/Item/eItemSlot.hpp`; Finding 6 now says so. The respawn fallback to point 0 was listed in Confidence as
  confirmed in game with a link to the review only; the measurement (every `m_nearest_enemy_point` set to -1, a CPU that
  fell headed to point 0) moved into Finding 7, and Confidence links there.
- **Wording.** "The only setting the original battle courses change is flag 0x80" (summary, [Flag
  0x80](README.md#flag-0x80-base-speed-race-and-jump-point-battle), Finding 6) could be read as saying that the battle courses also
  keep one scale everywhere; they use scales from 0.375 to 6.0. It now says "apart from the position and the width (scale)
  of each point". The battle cells of Finding 14 that were empty now give what the battle courses use (scale 0.375 to
  6.0, `drift_setting` and `max_search_y_offset` 0 on every point), counted in this pass; the claim itself does not
  change. In the summary, "which a CPU can only reach that way" now says which way (by being sent to the nearest route
  point). The flags table glosses "no rubber-banding" for race, which the table used before [Flag
  0x80](README.md#flag-0x80-base-speed-race-and-jump-point-battle) explains it.
- **Paths.** The commands of [Patch](#patch) under How to verify point to `final/` instead of
  `pending-verification/`.
- **Layout.** [Lakitu](README.md#lakitu) still had a line break in the middle of a sentence ("held in / place was / picked up"),
  and two overview paragraphs ([Re-routes](README.md#re-routes), the respawn bullet of [Max search Y
  offset](README.md#max-search-y-offset)) and a paragraph of Finding 12 had lines far longer than the rest; reflowed.

No claim was changed beyond the wording above.

#### What looks factually wrong

Nothing.

#### Noted, not blocking

- The first document review's note still holds: the overview says "within 280 units of its target point", while the
  reach test uses the aim point on the CPU's lane (Finding 5); the overview's simpler wording was kept.
- Some lines of part 2 (decompiled quotes, instruction lists, table rows) and of the header are longer than the rest;
  they were not reflowed.
- The open questions remain as listed, and the course-creator advice is still untested on a modified course; both are
  stated in [Confidence](README.md#confidence) and [Open questions](README.md#open-questions).

The status is set to `verified` and the folder moved to `final/enemy-ai-behaviour-and-enemy-points/`.

### Document review, fifth round

Third pass again, fresh context, 2026-10-06, made at the user's request on a topic already in `final/`, to bring it in line
with the rules for topic documents and patches that changed after the fourth document review (`REVIEW.md` split from
the topic document, no section on the patches, no links outside the topic folder, names never marked provisional, patch
comments without the functions that set or read a member, enums for members that hold one of a set of values). `eur2`
(sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95), repository at 050242ebef3fcea6c25cc36d13ddd53fd9db8053. The overview
and the glossary were read in full against WRITING.md, and part 2 for the passages the patch comments or the changes
below touch. A throw-away script checked that every link of both documents resolves. The code was looked at once
(`AIAutoSteer::stateInitGather` / `stateGather`, to word the comment of `m_gather_coins`).

#### What was changed

- **Split.** `## How to verify` and `## Review` moved from the topic document to this file, and `## Patches` was removed
  (what the patch names or renames is in the Status column of the glossary). The links between the two documents now
  name the file.
- **Base commit.** `template/` had moved on since b65de469294c2b1fe7e0b25cd66993bf9e0236b3: the checkpoint research
  added `MapdataJugemPoint::m_check_point_index` at 0x28, and the hunk adding `m_nearest_enemy_point` at 0x2C no longer
  applied. It was made again by hand next to the new member; the rest applied as it was. `Base commit` is now
  050242ebef3fcea6c25cc36d13ddd53fd9db8053.
- **Patch comments.** Every comment that named the functions that set, read, zero or test a member was cut down to what
  the member holds (`AIAutoSteer`, `AIControlBattle`, `AIControlRace`, `AIEngine`, `AIStuck`, `MapdataJugemPoint`,
  `ObjectBase::m_ai_signal`, `VehicleControlAI`, `VehicleMove`, `CoinManager`); comments that fit in one line moved
  after the member. The facts were already in the glossary and the findings, except what `AIAutoSteer::m_gather_coins`
  holds, now in its glossary note. The comment of `ObjectBase::m_ai_signal` no longer lists the readers or names this
  research; `VehicleControlAI::m_collision_switch` has no comment left. "Name is provisional", "Meaning unknown", "Not
  looked at further", "Note: The names of this enum are made up" and the `/U/` comment of `AIStuck` +0x54 were removed.
  The two-line class comments of `AIAutoSteer` and `AIStuck` became one line each, and their lists of state numbers
  became enums.
- **Enums.** New, declared in their classes: `AIAutoSteer::EState` and `AIStuck::EState` (`u8`, named after the state
  functions, values as the glossary listed them), `AIStuck::EBackPhase` (type of `m_back_phase`),
  `AIPathHandler::EPassMode` (type of `m_pass_mode` and `m_relocate_pass_mode`), `AIPathHandler::EShortcutMode` (type of
  `m_shortcut_mode`), `MapdataEnemyPointData::EMushroomSetting` and `EDriftSetting` (types of `mushroom_setting` /
  `drift_setting` and of their copies in `PointParam`, which now includes `Field/Entry/EnemyPoint.hpp`). Each has a
  table in the glossary, and `EnemyPointFlags`, which stays a plain enum since `flags` holds a combination of its values,
  has one as well. The values and what they mean are those the document already gave; no claim changed.
- **Names.** No name is marked provisional any more, in the glossary (`m_direction`, `m_skip_watch`, `m_award_flag`,
  `m_collision_switch`, `m_drift_state`, `m_forward_dir`, `GoNextInfo::m_corner_line_shift`, `m_pending_path`,
  `m_can_adjust_offset`, the two `sinit_*` functions and two data names) or in `## Open questions`; what is not
  understood about them stays in the open questions. No name changed.
- **Glossary.** The paragraph on the state machines points to the new `EState` tables and keeps only the `AIEngine`
  states, which have no enum.
- **Links.** Finding 6 (AI level) cited a workspace document by its path for the measurement of the battle settings page;
  it now says where the value was measured, in words.
- **Patch checks.** On a fresh copy of `template/` at 050242ebef3fcea6c25cc36d13ddd53fd9db8053 with the patch applied,
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (`USA_REV1`) pass; `git apply --check` passes on the
  repository.

#### What looks factually wrong

Nothing.

#### Noted, not blocking

- Left as integers, for the human to decide: `AIControlBase::m_search_mode` (existing) and its copy
  `GoNextInfo::m_search_mode`, `AIControlBattle::m_battle_type`, `MapdataEnemyPath::m_find_type` and
  `MapdataEnemyPointData::path_find_options`. They hold modes or kinds, but for `m_search_mode` and `m_battle_type` the
  meaning of several values is not known (only how the CPU chooses, not which target searcher a mode uses; what 1 and 2
  of `m_battle_type` mean is an open question), and `path_find_options` mixes codes (-1 to -4) with the award kart
  numbers 1 to 3, which `m_find_type` shares. Naming them would go beyond what the findings show.
- The earlier subsections of this review keep the section names and addresses they cited (`## Patches`, `[Patch]`,
  "provisional"); they are records of those passes and were not rewritten.
- The notes of the earlier document reviews still hold: "within 280 units of its target point" in the overview is
  simpler than the reach test on the aim point (Finding 5), some lines of part 2 are longer than the rest, and the
  course-creator advice is untested on a modified course.

The status stays `verified`, and the folder stays in `final/enemy-ai-behaviour-and-enemy-points/`.
