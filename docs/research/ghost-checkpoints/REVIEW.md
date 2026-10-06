# Review and verification steps for `Ghost checkpoints`

## How to verify

### Code

```
mk7-llm-research/mk7 dis Field::MapdataCheckPoint::checkSectorAndDistanceRatio     # quad test (Finding 1)
mk7-llm-research/mk7 dis Field::FindRecursiveSector                  # the walk, with the v1.1 gate (Finding 2)
mk7-llm-research/mk7 dis -i eur0 0x003a1bc8                          # v1.0 version without the gate (Finding 3)
mk7-llm-research/mk7 decomp Field::FindSector
mk7-llm-research/mk7 dis -n 0x90 0x00469dc8                          # course_has_patch / disable_ghost_checkpoints
mk7-llm-research/mk7 dis -n 0x40 0x00378de0; mk7-llm-research/mk7 dis -n 0x20 0x00356834   # SetDisableGhostCheckPoints and its caller
mk7-llm-research/mk7 decomp Field::FieldDirector::createBeforeStructure   # KMP loaded with the course_has_patch byte
mk7-llm-research/mk7 dis -n 0x40 0x00447ef0                          # the loader reads that byte (load argument + 0x14)
mk7-llm-research/mk7 decomp RaceSys::LapRankChecker::calcLapPosition_ RaceSys::GetKartJugemRecoverSectorIndex \
    RaceSys::LapRankChecker::onOutOfBounds                       # search result -> respawn (Finding 4)
mk7-llm-research/mk7 dis Kart::Unit::startJugemRecover               # Ghidra truncates the decompilation
mk7-llm-research/mk7 dis -n 0x500 0x00356880                         # MapdataJugemPoint::m_check_point_index at load
git apply --check mk7-llm-research/final/ghost-checkpoints/checkpoint-members.patch
```

### Running ghost_checkpoints.py

```
mk7-llm-research/local/venv/bin/python mk7-llm-research/final/ghost-checkpoints/ghost_checkpoints.py \
    <extracted .szs directory> [-o out.png] [--kmp other.kmp] [--online] [--mode full viable practical] [--step 4] [--max-skip 2]
```

`{mode}` in `-o` is replaced by the mode name (with several modes and no `{mode}`, `_<mode>` is added before the
extension), and each report goes next to its image with the extension `.txt`. Wuhu Loop takes about 1.5 minutes with
five worker processes (`--jobs`) for one mode, and about 2 minutes for all three, most of it searching from every
checkpoint. The time grows with the square of the grid resolution: `--step 1` is 16 times the default.

### Reproducing the Wuhu Loop results

Run the tool on the original KMP, on the v1.1 KMP, and in online mode ([Findings
3](README.md#3-what-v11-changed-in-the-bridge), [5](README.md#5-wuhu-loop-course-data-and-model-results) and
[6](README.md#6-the-v11-kmp-of-wuhu-loop)):

```
P=mk7-llm-research/local/venv/bin/python; T=mk7-llm-research/final/ghost-checkpoints/ghost_checkpoints.py
C=mk7-llm-research/local/romfs/eur2/rom/Course/Gctr_WuhuIsland1.szs.d
$P $T $C -o /tmp/orig.png
$P $T $C --kmp mk7-llm-research/local/romfs/eur2/pat1/Patch/Course/Gctr_WuhuIsland1/Gctr_WuhuIsland1.kmp -o /tmp/v11.png
$P $T $C --online -o /tmp/online.png
```

`ghost-renders/<course>/` holds `offline_<mode>` and `online_<mode>` images and reports for every retail course; the
first line of each report gives the grid step and the settings.

### In game

The tests of [Finding 8](README.md#8-in-game) were run with throw-away scripts on the `mk7re.dynamic` library
(EMULATOR.md); they are not kept in this folder. To repeat one:

```
mk7-llm-research/mk7 emu start --unlock
mk7-llm-research/mk7 emu grandprix 1 --engine 2 --until race    # Flower Cup: Wuhu Loop; `continue --until race` x3: Rock Rock Mountain
mk7-llm-research/mk7 emu race-start
```

then, in Python with one `Session` `s` and one `Race` `r`, keeping the game frozen between frames:

- write the start state (`KartInfo::m_previous_checkpoint_index` to `m_key_checkpoint_id`) at
  `r.kart_info(0)["addr"] + 0xC` as `struct.pack("<BBhB", C, C, -1, key_id_of_C)` and clear bits 0x6 of
  `KartInfo::m_flags` at `+ 0x24`;
- each frame `r.set_kart_pos(0, (x, y, z))` (position written, velocity cleared), `s.step(1)`, then read
  `r.kart_info(0)` and `r.kart(0)`; compare with `ghost_checkpoints.find_sector(cps, x, z, previous, online)` at the
  position `r.kart(0)["pos"]`;
- the respawn point: within `s.gdb()`, breakpoints at 0x002EDD2C (`bl Field::GetJugemPoint` in
  `Kart::Unit::startJugemRecover`, r0) and 0x002EDFF4 (`bl RaceSys::OnOutOfBounds`, r1), for player 0
  (`[r4 + 0x28]`), while the hooks run one frame (`s.hooks.freeze_at(s.frame + 1)`);
- the v1.1 gate: `mk7-llm-research/mk7 emu write 0x0065F1A8 01` (back with `00`);
- the patched KMP: `mk7-llm-research/mk7 emu write 0x00356804 c490cde5` before the race is built (the menus), and
  `c490cd15` after it to restore `strbne`; `r.checkpoints()` gives the loaded checkpoints.

## Review

### Fact check

Second pass, fresh context, 2026-10-01, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2`
(sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95).

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied with `patch -p1` to a fresh copy of `template/`; `mk7 --templates
  <copy> verify --version EUR_REV2` and `verify` (USA_REV1) both pass. The members match the constructor (0x0038F008:
  `m_center`, `m_forward`, zeroed counts, `m_path`, the `SNextInfo` array at 0x40 with stride 0x18), `setupLink`
  (0x0038ED20) and the loads in `checkSectorAndDistanceRatio` (`m_next_num` 0x04, `m_search_flags` 0x08, `m_index` 0x0C,
  `m_key_check_point_id` 0x0D, `m_prev_points` 0x24). `check_point_index` (0x1A, `ldrsh`, used when > 0) and
  `m_check_point_index` (0x28) at 0x00356C30..38.
- **Finding 1.** `checkSectorAndDistanceRatio` disassembled again: both side tests, `a`, `b`, the ratio, the float and
  integer compares, and the return values hold. Detail added: the ratio is written for every next that passes the side
  tests, so with several nexts the last one wins.
- **Findings 2 and 3.** `FindRecursiveSector` in `eur2` and `eur0`, and `FindSector` decompiled: depth limit 8/16,
  marking, the forward and backward bridges, the gate `byte == 0 || depth <= 1`, the key checkpoint stop, flag bit 0 for
  the children, the visit orders of the three cases of `FindSector`, the inner-loop-only `break`, the depth −1 / flags 0
  fallback and the full scan. `SetDisableGhostCheckPoints`, its single caller, and `updateRaceModeFlag` (play mode at
  0x164, course ids 8 / 9 / 0x1D / 7, rule modes 3 / 7) hold. The static initializer that loads 0x0065F1A8 (0x00537F8C)
  writes 8 bytes further, not the byte itself.
- **Finding 4.** `calcLapPosition_`, `GetKartJugemRecoverSectorIndex`, `onOutOfBounds`, the `race` test and the
  `OnOutOfBounds` call of `startJugemRecover`, `Vehicle::calcMove` setting 0x40 on `Out_of_Checkpoint_Area`, the
  per-frame clear in `LapRankChecker::calc`, `m_course_lap_amount` (`GetCurrentCourseLapNum() == 3` at
  0x00462DF8..0x00462E08) and the reverse-order respawn point setup at load.
- **`m_section` (CKPT byte 0x15)**, added after the review on request. Read as a signed byte at 0x00462188 (section) and
  in the 3-lap acceptance test. On every KMP of `rom:` and `pat1:` it is −1 except: Wuhu Loop 28 = 0, 90 = 1; Maka Wuhu
  21 = 0, 55 = 1; Rainbow Road 41 = 0, 85 = 1 (the three 1-lap courses, where it marks the start of sections 2 and 3);
  Rock Rock Mountain 3..37 = 1 and Rosalina's Ice World 39..58 = 1 (3-lap courses). Named in the patch.
- **Course data.** Re-read with an independent throw-away KMP parser: group 3 = checkpoints 68..124; key ids 5 / 6 / 7
  for 105 / 107 / 119; respawn ids of 107..120; the v1.1 KMP changes only the right (−X) ends of 106..111 (JGPT and CKPH
  identical); the ratios of the walk (+352, +161, −1565) and the outside results of 108 and 114; the crossing points and
  angles of 118/119 and 119/120; the 27..84 unit gaps between the right ends of 114..120.
- **Model.** The script's search was compared line by line with the disassembly above; no difference found. Run at the
  example point it gives 119 offline, −1 online, and 107 (still inside) with the v1.1 KMP; from 119 at the same point,
  −1. On a 50-unit grid over x −14000..−5000, z −3000..6000, the overlap of Figure 5 and the cells where the search from
  107 returns 119 are the same 691 cells. The three runs of [How to verify](#how-to-verify) reproduce every ghost, jump
  and online result the document quotes.

#### What was changed

- **Summary and the Wuhu Loop example** rewritten to be shorter; the facts are the same. The example now has one
  subsection per reason (ratio, side lines, the overlap) and a table for Figure 3. The 764-cell count was dropped: it
  depends on the view, and the claim it supported (the two areas are the same) holds on any grid tried.
- **Ghost 120 from 108 and 109.** The tool gives ghost 120 (respawn point 33, not 32) for a kart leaving quads 108 or
  109; added to the Summary and to Confidence, which claimed the model reproduces "checkpoints 107..110 and respawn
  point 32".
- **"Tested in game"** in Finding 4 contradicted Confidence ("not checked in game"). Reworded: the respawn at point 32
  is the in-game observation of the question; the frame sequence comes from the code and the model.
- **`VehicleMove+0x9D`** is the existing `VehicleBase::m_is_net_send`; the open question now uses the name. Finding 4
  also gained two branches it did not mention: `m_is_real_goal` skips the acceptance checks, and `onOutOfBounds` also
  resets karts with `m_is_net_recv`. Glossary entries added for these and for `LapRankChecker::m_is_maka_wuhu`.
- **0x0065F1A8** is also read by `calcLapPosition_` (section-based courses only); added to Finding 3.
- **Unsupported example dropped**: "Mario Circuit 26 → 52" had no evidence.
- **Tool** (after the review, on request): `--mode` takes several modes and runs the searches once for all of them, and
  a text report is written next to each image. On Wuhu Loop, the three images and reports are identical to those of
  three separate runs of the previous version, pixel for pixel.
- **Tool section**: the history of the yellow colour shortened to what the colours mean now; the timing measured again;
  paths updated to `final/`, also in the comment of `mk7-llm-research/requirements.txt`.

The search model of the script was not changed. The patch only gained `MapdataCheckPointData::m_section` (see above).

#### What remains uncertain

- Nothing was tested in game in this pass; the offline behaviour on v1.2 and the 108 / 109 → 120 jumps are model
  results.
- The KCL was not examined, as before.

### Document review

Third pass, fresh context, 2026-10-02, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2`. The document
was brought to the current WRITING.md; the passes before it followed older rules.

#### What was changed

- **Structure.** The sections follow WRITING.md: `## Summary` became `## Overview` and comes before `## Glossary`; the
  header keeps Status, Asked, Base commit and Images, and the Data and Method lines moved to [Sources and
  method](README.md#sources-and-method) at the start of the findings. The "Terms:" paragraph is gone: the overview now
  introduces checkpoints, groups, quads, key checkpoints, key checkpoint sections and the current checkpoint in its
  first subsection, and the findings give the numbering of group 3.
- **Bold-titled paragraphs** ("Quads.", "The quad test.", "The flaw: gap bridging.", "What happens on Wuhu Loop.", ...)
  became subsections; the headings that ended in a period lost it.
- **The tool section** was split by reader: what the image shows and the three modes, in plain words, went to the
  overview ([Checking a course for ghost checkpoints](README.md#checking-a-course-for-ghost-checkpoints)); how the model
  works, how the map is placed, the pruning and its check, and the limits became [Finding
  7](README.md#7-the-model-ghost_checkpointspy); the command line and the timing went to [How to
  verify](#how-to-verify), which now also describes `ghost-renders/`.
- **Overview claims backed by findings.** The course numbers of the Wuhu Loop example (walk, ratios, crossing points,
  distances between right ends, the 691-cell check, ghost 120 from 108 and 109) and the effect of the v1.1 KMP were only
  in the overview and in the fact check; they are now [Finding 5](README.md#5-wuhu-loop-course-data-and-model-results)
  and [Finding 6](README.md#6-the-v11-kmp-of-wuhu-loop), and the overview links to every finding it relies on.
- **Addresses** in the findings, the glossary notes and the open questions were replaced by the instruction or
  decompiled line they pointed to, read again in `eur2`; the addresses are now only in the glossary and in How to
  verify. The `eur0` address of `FindRecursiveSector` moved to the Functions table.
- **Glossary.** Added the functions the text cites but the table lacked (`setupDistanceBaseFromStart`,
  `MapdataCheckPointAccessor::setup`, `GetCurrentCourseLapNum`, `GetJugemPoint`, `LapRankChecker::init`,
  `RaceSys::OnOutOfBounds`, `Unit::calcMove`, `Vehicle::calcMove`, `VehicleMove::calcGndCollision`,
  `VehicleMove::calcPosAtt`), a `### Data` table for `Field::sDisableGhostCheckPoints` (named after its setter), and the
  existing members the text uses (`KartInfo::m_current_race_progress`, `VehicleMove::m_status_flags`,
  `CRaceInfo::m_course_id`, `m_race_mode`, `m_race_mode_flag.race`).
- **Wording.** "Sector" is only the game's name for a quad; "ghost area" is defined; "EFE" is spelled out; the kart's
  current checkpoint is called that everywhere (it was also "respawn checkpoint" and "kept checkpoint"). The overview
  replaced `m_section` and `disable_ghost_checkpoints` by plain descriptions (the CKPT byte keeps its file offset).
  Typos fixed ("its points", "diretions", "did not said").
- **Cross-reference.** Finding 1 pointed to Figure 2 for the ratio behind both lines; it is Figure 1.
- How to verify uses symbol names where `mk7` accepts them.

No claim was changed.

#### What looks factually wrong

- **The v1.1 gate never lets the main walk bridge.** The overview says that with `disable_ghost_checkpoints` "the main
  walk only bridges on the quads right next to the kart's last quad". The gate is `depth <= 1`, but the bridge also
  needs flags bit 0, and every depth-1 call of `FindSector` passes flags 6 or 0
  (`FindRecursiveSector(param_1,param_2,param_3,1,1,iVar5,uVar8)` with `uVar8` = 6 or 0). Bit 0 is only set for
  children (depth 2 and up), which the gate then blocks. So, online, the main walk never bridges, and only the fallback
  walk (depth −1) can. The model does the same (`recursive(1, ..., flags)` with `flags` 6), so its results, the two
  remaining ghosts (56, 72) included, are not affected; only the description in the overview (and the comment
  "bridging only near the start" in the script) is. Left as it was for pass 2.

#### Noted, not blocking

- `MapdataCheckPointAccessor::setup(bool)` writes three bytes at 0x18, 0x19 and 0x1A of the accessor (the highest key
  id, the finish line checkpoint, the checkpoint before it), but the template gives the accessor a size of 0x18. These
  members could not be named without finding the accessor's real size, so the glossary notes of
  `LapRankChecker::m_max_checkpoint_id` and `m_checkpoint_type` no longer give "accessor +0x1A / +0x18" and say that
  `setup` computes them.
- `createBeforeStructure` calls `MapdataCheckPointAccessor::setup(m_course_id == 9)`. With `true` (Maka Wuhu) it looks
  for the checkpoint of type 1 instead of 0 and walks the key ids from checkpoint 0. Finding 7 ("walked from the
  checkpoint whose type is 0") holds for every other course; Maka Wuhu is outside what the tool models.
- How `images/fig1..5.png` were made is not recorded, nor which KMP the `online_*` renders of the four patched courses
  used.

The status is set back to `pending verification`, so that the topic goes through pass 2 again for the gate.

### Fact check, second round

Pass 2 again, fresh context, 2026-10-02, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2`
(sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95), after the document review sent the topic back for the v1.1 gate.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied to a fresh copy of `template/`; `mk7 --templates <copy> verify
  --version EUR_REV2` and `verify` (USA_REV1) both pass.
- **Finding 1.** `checkSectorAndDistanceRatio` disassembled again: `d`, `v`, both side tests, `a`, `b`, the ratio, the
  float and integer compares and the return values hold.
- **Findings 2 and 3.** `FindRecursiveSector` in `eur2` and `eur0`, `FindSector` decompiled. Everything in Finding 2
  holds. **The document review's finding is confirmed**: every depth-1 call of `FindSector` passes flags 6 or 0, so
  flags bit 0 is clear at depth 1, and with `sDisableGhostCheckPoints` set the gate fails at every depth above 1. The
  main walk therefore never bridges online; only the fallback walk (depth −1) can. `updateRaceModeFlag`,
  `SetDisableGhostCheckPoints` (one caller) and the four references to `0x0065F1A8` hold.
- **Patched KMP.** Newly checked: `createBeforeStructure` sets byte 0x14 of the KMP load argument from
  `course_has_patch`, and the loader passes it on; the patch RomFS has `Patch/Course/` KMPs for exactly the four
  course ids. `pat1:` and `rom:/Patch/` copies of the Wuhu Loop KMP are identical.
- **Finding 4.** `calcLapPosition_`, `GetKartJugemRecoverSectorIndex`, `onOutOfBounds` decompiled; `startJugemRecover`
  (`race` test, `GetJugemPoint`, `OnOutOfBounds` with `MapdataJugemPoint+0x28`), `Unit::calcMove` (0x2000060),
  `Vehicle::calcMove` (`Out_of_Checkpoint_Area` → 0x40), `calcGndCollision` and `calcPosAtt` (0x20), the per-frame clear
  in `LapRankChecker::calc`, `m_course_lap_amount` in `init`, `GetCurrentCourseLapNum`, and the respawn point setup
  at load (forced value at 0x1A, list popped from the end) all hold, except the point below.
- **Course data.** Re-read with a new throw-away KMP parser: groups (68..124 is CKPH entry 3), key ids 5 / 6 / 7 for
  105 / 107 / 119 (117 is the key checkpoint of id 7), respawn ids of 105..120, `m_section` values of Wuhu Loop, and the
  v1.1 difference (right ends of 106..111 only; JGPT and CKPH identical). Recomputed independently of the script: the
  walk results and ratios at (−8900, 650) (0 for 107, 108, 114; −1.7..−58 for 109..113, 115..116; +352, +161.5, −1564.8
  for 117..119), the crossing points and angles of 118/119 and 119/120, and the 27..84 unit gaps of the right ends.
- **Model.** `ghost_checkpoints.py`'s quad test, walk, `FindSector` visit order, fallback walk and acceptance rule were
  compared with the code above; no difference. In particular its online gate behaves like the game's: depth 1 is
  entered with flags 6, so its main walk never bridges online either, and none of its results depend on the wrong
  description. At the example point it gives 119 offline, −1 online, 107 with the v1.1 KMP, −1 from 119; respawn
  points 27 → 107, 28 → 109, 32 → 118 with both KMPs; the 691-cell check holds. The three runs of How to verify
  (default step, modes full and practical) reproduce the Wuhu Loop ghosts, jumps and online results the document
  quotes, including the v1.1 KMP results of Finding 6 and the online ghosts 56 (from 73, accepted) and 72 (from 41..42,
  rejected).

#### What was changed

- **The v1.1 gate.** The overview said that online "the main walk only bridges on the quads right next to the kart's
  last quad"; it now says that the main walk no longer bridges, and why. Finding 2 gained the paragraph on depth 1 and
  flags bit 0; Finding 3 now says that the main walk never bridges with the flag set. The comment of the gate in
  `ghost_checkpoints.py` was corrected the same way; the code is unchanged.
- **Patched KMP.** Finding 6 cited Finding 3 for "loaded only when `course_has_patch` is set", but Finding 3 only showed
  where the flag is set. Finding 3 now gives the load in `createBeforeStructure`; Confidence lists the choice of file
  as likely. `RaceSys::GetCourseResourceNameExt` added to the glossary, two commands to How to verify.
- **Acceptance rule (Finding 4).** The neighbour tests, described as the "difference 0" case, run last for every result
  whatever the difference, when `m_is_net_send` is clear or `Out_of_Checkpoint_Area` and `Force_No_Lap_Completion` are
  both clear (`tst r0, #6`). "`m_current_checkpoint_index` is not updated" for a rejected jump was too strong, and
  contradicted the open question. Finding 4 now gives the real order, and that the key id steps are skipped while
  `Force_No_Lap_Completion` is set. The open question now names the one case that can matter for far jumps: a
  checkpoint with `m_section` = 1 on Rock Rock Mountain or Rosalina's Ice World.
- **Pair example.** The overview and Finding 7 used "ghost 118, 119 - R32" as a pair found in the same cells, one
  forward and one backward, with 119 "from 105..116". The report gives 119 from 103..117, 121..124 and 0..10, and the
  two areas differ (about 3.0 and 8.5 million square units). Replaced by "ghost 94, 95 - R23" (95 from 79..93, 94 from
  96..110, same area), which the reports and the image show.
- **Missing jump.** The open question on other accepted jumps of Wuhu Loop listed only 77..78 ↔ 90. The tool also
  reports, offline with either KMP, a ghost of checkpoint 95 for a kart leaving quads 84, 85 or 87 (respawn point 23
  instead of 21); added.
- Status set to `facts checked`.

#### What remains uncertain

- Nothing was tested in game; the offline shortcut on v1.2, the 108 / 109 → 120 and 84 / 85 / 87 → 95 jumps are model
  results.
- The file the loader opens when `course_has_patch` is set was not followed to the end.
- When `VehicleBase::m_is_net_send` is clear was not looked at, so whether rejected jumps into `m_section` = 1
  checkpoints are really rejected offline is open.
- The KCL was not examined, as before.

### Document review, second round

Pass 3 again, fresh context, 2026-10-02, on base commit b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2`, after the
second fact check. At the user's request, the document now covers ghost checkpoints in general, and the Wuhu Loop
shortcut is the example that motivated the research.

#### What was changed

- **Title and topic.** `# Wuhu Loop respawn shortcut and "ghost checkpoints"` became `# Ghost checkpoints`, and the
  folder `final/ghost-checkpoints/` (it was `pending-verification/wuhu-loop-ghost-checkpoints/`). The paths of How to
  verify and the comment in `mk7-llm-research/requirements.txt` follow.
- **Opening of the overview.** It explains ghost checkpoints and why they cause respawn glitches, mentions the Wuhu Loop
  shortcut only as the starting point, and summarises v1.1 for all courses. The details of the shortcut (checkpoint 119,
  respawn point 32 instead of 27 or 28) are only in [The Wuhu Loop shortcut](README.md#the-wuhu-loop-shortcut).
- **Wuhu Loop details moved into its section.** The numbering of group 3 (39..42 of group 3 = 107..110) left
  [Checkpoints, quads and respawn points](README.md#checkpoints-quads-and-respawn-points), and the section now opens
  with the glitch as reported. [What v1.1 changed](README.md#what-v11-changed) is general and comes before the example;
  its Wuhu Loop results (ghosts 56 and 72 online, the moved ends of 106..111, the remaining contact of ghost 120) are in
  the new [What v1.1 changed on Wuhu Loop](README.md#what-v11-changed-on-wuhu-loop).
- **Main walk, fallback walk.** Both terms were used before being introduced. The overview now presents the three stages
  of the search in [Gap bridging and ghost checkpoints](README.md#gap-bridging-and-ghost-checkpoints), and Finding 2
  names steps 2 and 3 the same way.
- **Certainty.** The overview said that a patched KMP "is loaded" online; Confidence lists that as likely, so the
  overview says "probably".
- **Ghost checkpoints last one frame** (added on the user's request, after the rest of this review): the new subsection
  [A ghost checkpoint usually lasts one frame](README.md#a-ghost-checkpoint-usually-lasts-one-frame), before What v1.1
  changed, and the Wuhu Loop example now say that the kart has a ghost checkpoint for one frame only, and that the next
  search, started from it, finds nothing. The subsection also explains why, from the rule of Finding 2 that the quads
  tested first never bridge; that nothing further along the walk bridges either rests on the model (Finding 7). This was
  already stated in the tool section and backed by Finding 4 ([Frame by frame on Wuhu
  Loop](README.md#frame-by-frame-on-wuhu-loop)) and by the limits of Finding 7.
- **Smaller points.** The notation C → N is introduced with the quads, and Figure 1 uses → like the rest. The repeated
  "Only exactly parallel checkpoints have no X" became a sentence linking the invalid corner to the bridge. Finding 7
  says what red and orange mean instead of pointing back to the overview. A wrapped line in Finding 3 fixed.

No claim was changed.

#### What looks factually wrong

Nothing.

#### Noted, not blocking

- The third acceptance case of the overview ("in the same key checkpoint section, the course has 3 laps, and byte 0x15
  ... is 1") is how the tool treats it. Finding 4 shows that test running whatever the key id difference when
  `VehicleBase::m_is_net_send` is clear, which is already an open question.
- The two notes of the first document review on `MapdataCheckPointAccessor` and on how the figures were made still
  apply.

Status set to `verified`.

### Fact check, third round (in game)

Pass 2 again, 2026-10-04, on base commit 4767b3628594c92aa7b203b4b1d1430051f6ddd6 with `eur2`, after the topic was
moved back from `final/` at the user's request: the dynamic analysis tooling (`mk7 emu`, EMULATOR.md) now makes it
possible to answer in game what the earlier passes left to the model or to guesses. The static findings, checked twice
already, were not re-derived; only the instructions that the in-game tests needed (the respawn-point calls in
`startJugemRecover`, the load byte in `createBeforeStructure`) were read again.

#### What was re-checked, and how

- **In game** (Finding 8, new): every Wuhu Loop result of Findings 4, 5 and 6 and the open questions about it, frame by
  frame, with the kart's checkpoint state, its status flags and the respawn point read from the game, and the model run
  at the same positions; the v1.1 gate set by hand; the patched KMP loaded by setting the load byte; where a kart falls
  into the sea; `m_is_net_send` offline; jumps across key checkpoint sections on Wuhu Loop and Rock Rock Mountain; the
  loaded checkpoints, key ids and respawn-point checkpoints against the model.
- **Patch.** `git apply --check` passes; applied to a fresh copy of `template/` (`local/work/ghost-checkpoints/`),
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (USA_REV1) pass.
- **Model.** The old and the corrected acceptance rule compared over every pair of checkpoints of every course (see
  below); the next-frame search after the ghosts of Wuhu Loop computed on a 50-unit grid (Finding 5).

#### What was changed

- **Ghost checkpoints do not always last one frame.** The overview said that a kart keeps a ghost checkpoint for one
  frame only, and that the model finds no quads further along the walk that could bridge. Off quad 108 the game gave
  120, then 122 and 119 in turn for 53 frames, and the kart respawned at point 32, not 33; the model gives the same,
  in about a third of 120's ghost area. The subsection became [A ghost checkpoint usually lasts one
  frame](README.md#a-ghost-checkpoint-usually-lasts-one-frame); the Wuhu Loop example, Findings 5 and 7 (Limits) and the
  tool section of the overview follow.
- **Acceptance of jumps across key checkpoint sections.** The overview and the tool said such a jump is always rejected.
  Offline `m_is_net_send` is clear on every kart, so the last tests of `calcLapPosition_` run after it and accept a
  checkpoint they allow: a far checkpoint with `m_section` = 1 on a 3-lap course, and any checkpoint of a group linked
  to the current checkpoint's (when that is the first or last checkpoint of its group). Both were seen in game. [Which
  results the game accepts](README.md#which-results-the-game-accepts), Finding 4 and the glossary notes were corrected,
  and so was the comment of `MapdataCheckPointData::m_section` in the patch ("within the same key checkpoint section").
- **`ghost_checkpoints.py`** (a bug in the topic's model, fixed without asking): `accept_jump` takes `net_send`; offline
  (`net_send` false) a jump across key checkpoint sections goes through the last tests, online (`m_is_net_send` set on
  the player's kart) the old answer is kept. Accepted jumps of that kind are marked in the report ("the key id stays,
  Force_No_Lap_Completion is set"). The search model is unchanged. Over all checkpoint pairs, the answer changes only on
  Rock Rock Mountain, Rosalina's Ice World, Wuhu Loop, Maka Wuhu, Daisy Cruiser, Koopa Beach and the Winning Run course;
  their offline renders were made again with the settings of the old ones (`--step 1`, all three modes). Rosalina's Ice
  World, Maka Wuhu and the Winning Run course came out identical (images and reports). Wuhu Loop, Rock Rock Mountain and
  Koopa Beach gained respawn glitches only in `full` and `viable` (found from a checkpoint next to the finish line, so
  only after a teleport); their `practical` results, and with them every Wuhu Loop claim of this document, are
  unchanged. Daisy Cruiser gained red jumps in all modes (0 → 64..68, tested in game, Finding 8). The new files
  replace the old ones in `ghost-renders/`.
- **Online renders of Wuhu Loop.** Run again with the v1.1 KMP (`--kmp` the patch file, `--online`, `--step 1`), the
  reports are identical to those in `ghost-renders/`: the online ghosts 56 and 72 hold with the KMP the game probably
  loads online. The other three patched courses were not run again.
- **Certainty.** "Offline races should still have ghost checkpoints" (a guess) and "the respawn at point 32 was seen in
  game" (only the user's report) are now measured; the loading of the patched KMP stays likely (forced offline, not
  online); the unreachable v1.1 contact of ghost 120 is backed by where the kart falls. Confidence and the overview
  sentences that cite it were updated.
- **Open questions** answered and removed: the offline shortcut, the 77..78 ↔ 90 and 84 / 85 / 87 → 95 jumps (both
  as the model says), `m_is_net_send` offline, the KCL question (in part). Added: how players cross the edge of quad 107
  in the air, what an accepted jump across key checkpoint sections does to the lap. The question
  on `MapdataJugemPoint::m_check_point_index` now says that only battle courses have respawn points no checkpoint
  contains.
- **How to verify** gained the in-game steps; the glossary `KartInfo::m_current_pos` and `Kart::Rigid::m_position`.

#### What remains uncertain

- Nothing was run online (the hooks must not go online): the gate and the patched KMP were set by hand offline.
  `m_is_net_send` online was given by the user after the tests (set on the karts the console sends: the player's own,
  and a player's kart driven by a CPU after a disconnect or the finish line).
- In every test the kart was placed by writing its position, in the air. That the game does this at those positions is
  measured; that a player can get there by driving is not (a kart driven at the edge of quad 107 fell into the sea
  first).
- The course collision was only probed by dropping the kart at a few places, not read.

Status set to `facts checked`. The changes go beyond corrections of detail (two statements of the overview were wrong,
and the tool's results changed on seven courses), so the topic stays in `pending-verification/` for a document review.

### Document review, third round

Pass 3 again, fresh context, 2026-10-04, on base commit 4767b3628594c92aa7b203b4b1d1430051f6ddd6 with `eur2`, after the
in-game fact check.

#### What was changed

- **Order of the overview.** [Why far quads can pass the bridging
  test](README.md#why-far-quads-can-pass-the-bridging-test) now comes right after [Gap bridging and ghost
  checkpoints](README.md#gap-bridging-and-ghost-checkpoints), which it explains, and before [Which results the game
  accepts](README.md#which-results-the-game-accepts).
- **Ideas introduced before use.** The first subsection of the overview now introduces the respawn point, the links
  between groups (used by the acceptance rules) and the finish line checkpoint (key id 0).
  The ratio says which side of a line is positive. "Jump" was used from the acceptance rules on without being
  introduced; it is now defined there, together with the **jump across key checkpoint sections**, which replaces
  "a jump that skips a (whole) key checkpoint section" and "far jump" everywhere, Finding 4 and the glossary included.
  The overview spoke of "the model" before saying what it is; it now says "the tool of this folder, which re-implements
  the search", and "the tool" after that. The one-frame subsection no longer relies on "the ghost area of checkpoint
  120" before the Wuhu Loop section introduces it.
- **One term per thing.** "Ghost checkpoint" was defined twice, broadly in the opening (a checkpoint whose quad the kart
  is not in) and narrowly in the bridging subsection (one that has nothing to do with where the kart is). It is now
  defined once, as the checkpoint a bridge returns, which is also what the tool draws; the far ones are described as
  such. "Real quad" became "quad" (there is no other kind); "the kart's next checkpoint" became its current checkpoint;
  "beyond X" in the table of Figure 3 became "on the other side of X", as in the text; "the previous quad on the walk"
  became "the quad before it on the walk", as in the later subsections.
- **Certainty kept as in Confidence.** Where the overview stated what is likely or given by the user, it now says so:
  "a player probably has to cross the edge in the air", the v1.1 contact of ghost 120 "probably out of a kart's reach",
  and "according to the user" for `m_is_net_send` online (twice). "Marks the lap so that it cannot be completed" now
  says that this is what the flag's name says and that its effect was not followed, as in the open questions. The
  in-game list of accepted jumps across key checkpoint sections gained Daisy Cruiser, which Finding 8 tests.
- **Precision.** In [Why quad 118 says "past the end"](README.md#why-quad-118-says-past-the-end), "before the start for
  109..116" now excepts 114, which the table above it gives as outside its side lines. Step 10 of the walk table gained
  its reason. The location of the right ends of 114..120, used by the overview, was only in the overview; it was read
  from the KMP (x −6937..−6684, z 4955..5039) and added to Finding 5.
- **History out of the findings.** Finding 8 spoke of "the corrected model" and "corrected in this pass"; it now states
  what the tool does (its offline and online acceptance rules differ on seven courses; Daisy Cruiser is the only retail
  course with red jumps across key checkpoint sections in `practical` mode). The history stays in the third fact
  check.
- **Smaller points.** The opening's "the edge of the track's checkpoint area" (an undefined term) became "just off the
  track"; the overview now says that v1.2 keeps both fixes of v1.1; the method of Finding 8 says the 15 units a frame in
  the right place; the test of quads 77 and 90 is its own paragraph; "(the user)" in the glossary became "(given by the
  user)"; "The hooks must not go online" in Confidence became the reason the value was not measured; lines that ran
  past the width were wrapped.

No claim was changed.

#### What looks factually wrong

- **"A kart only gets a ghost checkpoint off the track"** (the opening and [A ghost checkpoint usually lasts one
  frame](README.md#a-ghost-checkpoint-usually-lasts-one-frame), which also says that the next search "finds nothing
  because the kart is in no quad"). The walk is depth first and can bridge before it reaches a quad the kart is in. Run
  with `find_sector` of `ghost_checkpoints.py` (offline) for every grid cell inside a quad (60-unit step) and every
  start whose quad does not contain the cell but is linked to one that does, the model bridges in 24 of 38702 searches
  on Wuhu Loop (for example from 111 at (−10832, 2704), inside quad 110: ghost 120) and in 1 of 13638 on Mario Circuit
  (from 29 at (−1908, 1851), inside quad 28: ghost 45); none on Rock Rock Mountain. So a kart can get a ghost checkpoint
  while inside a quad. The Wuhu Loop places are at the far −X end of quad 110, over the sea, so "off the track" may
  still hold in practice, but "in no quad" does not. The tool's jump analysis covers these (a search from a quad into a
  neighbouring cell, marked "ghost" when bridged), but its ghost areas only cover cells outside every quad. Not tested
  in game. Pass 2 should decide whether the statement is narrowed and whether the tool's description needs a word.

#### Noted, not blocking

- The notes of the first document review on `MapdataCheckPointAccessor` and on how the figures were made still apply.
- `__pycache__/` in this folder is ignored by `mk7-llm-research/.gitignore`.

The status is set back to `pending verification`, so that the topic goes through pass 2 again for the point above.

### Fact check, fourth round

Pass 2 again, 2026-10-04, on base commit 4767b3628594c92aa7b203b4b1d1430051f6ddd6 with `eur2`, for the point the third
document review found: "a kart only gets a ghost checkpoint off the track", and "the kart is in no quad" in
[A ghost checkpoint usually lasts one frame](README.md#a-ghost-checkpoint-usually-lasts-one-frame).

#### What was re-checked, and how

- **Code.** `FindSector` decompiled again: the order of its groups of calls when `start` reports 0 (the other prevs of
  the nexts, the other nexts of the prevs, the nexts, the prevs) and when it reports 1 (`*param_1 < 0x3f000001`: prevs
  first), and the recursion of `FindRecursiveSector`, which finishes a child's walk before the next child. So a walk
  can bridge in one direction before it tests the neighbour the kart is in. The review's reading holds.
- **Model.** The review's run was repeated (60-unit grid, every cell inside a quad, every start linked to a quad that
  contains the cell but not containing it): the same 24 of 38702 searches on Wuhu Loop and 1 of 13638 on Mario
  Circuit, and bridges on 9 more courses. Then on a 5-unit grid within 30 units of the checkpoint line between the
  start's quad and the kart's, which a kart crosses in one or two frames, and within 300 units on a 10-unit grid; and,
  for every case, the search of the next frame from the ghost and the acceptance rule.
- **In game** (offline, `eur2`): Wuhu Loop, state 111, kart put in quad 110 at three of the review's places; Dino Dino
  Jungle, states 27 and 28, kart moved 12 units across the line into the quad before. Every frame matched the model.
  Where the Dino Dino Jungle places are was probed by dropping the kart.
- **Patch.** `git apply --check` passes; on a fresh copy of `template/` with the patch applied,
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (USA_REV1) pass.

#### What was changed

- **The statement was narrowed.** The opening now says that a kart *mostly* gets a ghost checkpoint off the track, where
  it is in no quad. [A ghost checkpoint usually lasts one frame](README.md#a-ghost-checkpoint-usually-lasts-one-frame)
  limits its first two paragraphs to a kart in no quad, and gained a paragraph on ghosts inside a quad: how the walk
  order allows them, the 12 courses where the tool finds them, and what the game did in the tests (the ghost kept for
  one frame, then the kart's quad again).
- **Finding 2** gained the visit order of the walk and the model results (where, how far from the line crossed, the
  next frame; the 8 places on Mushroom Gorge and Airship Fortress where the model keeps the ghost as the current
  checkpoint, all far from the line crossed).
- **Finding 8** gained [Ghost checkpoints inside a quad](README.md#ghost-checkpoints-inside-a-quad).
- **The tool's description** (overview and Finding 7, Limits) now says that ghost areas only cover places outside
  every quad, and that a ghost inside a quad only appears as a jump at the border the kart crosses. The tool itself
  was not changed: its jump analysis already runs the search from the quad the kart leaves on the neighbouring cell,
  whether that cell is inside another quad or not (for example 25..28 → 36 on Dino Dino Jungle, reported as accepted
  ghost jumps).
- **Confidence**: the walk order under Certain, the in-game tests under Measured, the other courses and the 8 lasting
  places as model only. **Open questions**: whether a respawn that starts in the frame with the ghost uses its respawn
  point.

#### What remains uncertain

- Whether a player can be at those places right after crossing from the neighbouring quad. The tested ones are not on
  the road (over the sea on Wuhu Loop, on the rocks beside the road on Dino Dino Jungle); the others were not looked at
  in game, and the tool does not read the course collision.
- Within 30 units of the line crossed, the game accepts the ghost only on Airship Fortress (one cell) and Dino Dino
  Jungle, and in every case the next frame gives the kart's quad again. A respawn would have to start in that one frame
  to use the ghost's respawn point; not tested.
- The 8 places where the model keeps the ghost as the current checkpoint were not tested in game.

Status set to `facts checked`. The changes add a finding and change two statements of the overview, so the topic stays
in `pending-verification/` for a document review.

### Document review, fourth round

Pass 3 again, fresh context, 2026-10-04, on base commit 4767b3628594c92aa7b203b4b1d1430051f6ddd6 with `eur2`, after
the fourth fact check. At the user's request, the overview now keeps its general sections free of course details: the
Wuhu Loop claims are in the example, and the results on other courses have a section of their own.

#### What was changed

- **"A ghost checkpoint usually lasts one frame" split.** It held three ideas, each with course examples. It now keeps
  only the general case (a kart in no quad), and two new subsections follow it: [Chains of ghost
  checkpoints](README.md#chains-of-ghost-checkpoints) and [Ghost checkpoints for a kart inside a
  quad](README.md#ghost-checkpoints-for-a-kart-inside-a-quad), both without course numbers. The heading of the second
  differs from that of Finding 8, whose links it would otherwise have taken over.
- **Wuhu Loop details moved to the example.** The chain after ghost 120 (122 and 119 for 53 frames, respawn point 32,
  about a third of 120's ghost area) joined the paragraph on quads 108 and 109 of [The Wuhu Loop
  shortcut](README.md#the-wuhu-loop-shortcut), which now also says which ghosts of the chain the game accepted (as
  Finding 8 gives them). The ghost inside quad 110 has its own subsection there, [A ghost checkpoint inside quad
  110](README.md#a-ghost-checkpoint-inside-quad-110). The offline test of the original KMP moved from [What v1.1
  changed](README.md#what-v11-changed) to the end of [What v1.1 changed on Wuhu
  Loop](README.md#what-v11-changed-on-wuhu-loop); What v1.1 changed keeps one general sentence on the tests of Wuhu Loop
  and Dino Dino Jungle, both of which Finding 8 compares with the tool frame by frame.
- **New section [Ghost checkpoints on other courses](README.md#ghost-checkpoints-on-other-courses)**, at the end of the
  overview, after the tool is introduced: ghost checkpoints inside a quad on 12 courses (Dino Dino Jungle and the 8
  lasting places of Mushroom Gorge and Airship Fortress, from Finding 2 and Finding 8), the jump on Daisy Cruiser
  (from Finding 8; the overview only named the course before), and the three other courses with a
  patched KMP. Everything in it was already in Findings 2 and 8, Confidence or Open questions; the opening of the
  overview links to it.
- **Wording.** The chain paragraph said that the kart "respawns when it touches water or falls too low", which could be
  read as the only way a chain ends; in the in-game test of quad 108 it ended when the search found nothing
  (Finding 8). It now gives both ways and that either uses the current checkpoint of that moment (Finding 4). Finding 2
  said that on Dino Dino Jungle the model bridges "up to 3 units from the line", which reads as a limit and would
  contradict the in-game test 12 units across the line; run again with `find_sector`, the model bridges from less than
  1 to about 128 units behind checkpoint 27's and 28's lines near their right ends, so the phrase meant the closest
  place on the 5-unit grid, and now says "from as close as 3 units to the line".
- **Precision.** [Sources and method](README.md#sources-and-method) listed only Wuhu Loop and Rock Rock Mountain among
  the courses run in game; Dino Dino Jungle and Daisy Cruiser added. The method of Finding 8 gives 15 units a frame
  "unless a test says otherwise" (the tests of Dino Dino Jungle, Daisy Cruiser and quads 77 and 90 used other steps).
- Paragraphs wider than 120 characters were rewrapped; the text did not change. The paths of How to verify and the
  comment in `mk7-llm-research/requirements.txt` point to `final/ghost-checkpoints/`.

No claim was changed.

#### What looks factually wrong

Nothing.

#### Noted, not blocking

- The notes of the first document review on `MapdataCheckPointAccessor` and on how the figures were made still apply.
- Finding 8 says of Daisy Cruiser that the kart moved "from (−339, 695) in quad 0 into quad 64 (key id 2), which
  overlaps it there". If quad 64 overlapped quad 0 at that place, the search, which tests the start's quad first, would
  return 0; "it" probably means another quad. The overview says only that the kart is inside the quad it jumps to.

Status set to `verified`; the folder moves to `final/ghost-checkpoints/`.

### Document review, fifth round

Pass 3 again, fresh context, 2026-10-06, on base commit e8aa931bb403027cf47c6505c0cf17ddfcc29abd with `eur2`, at the
user's request, against the current WRITING.md and
PATCHES.md.

#### What was changed

- **Patch comments.** Three comments said where a member is set or tested, which
  the comment rules of PATCHES.md rule out: `MapdataCheckPointData::m_section` ended with
  "(LapRankChecker::calcLapPosition_)", `MapdataCheckPoint::m_search_flags` said "cleared every frame by
  LapRankChecker::calc" and "Bit 31: set by setupChechPointGroup", and `MapdataJugemPoint::m_check_point_index` said
  "see FieldDirector::createBeforeStructure".
  These references were dropped. Bit 31 is now described by what it holds, "m_key_check_point_id has been set"
  (`setupChechPointGroup` sets the bit right after it writes `m_key_check_point_id`, and recurses only into checkpoints
  without the bit). The comment of `m_check_point_index` fits on one line, so it moved after the member. Where these
  members are set and cleared is in the glossary notes, which now also cover the per-frame clear and bit 31.
- **Patch regenerated** from a fresh work copy of `template/` at e8aa931: `git apply --check` passes, and
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (USA_REV1) pass. The two template files have not
  changed since the old base commit; the header's `Base commit` now gives e8aa931.
- **Glossary.** `MapdataCheckPointData::m_section` had the status "new, provisional"; names are final, so it is "new".
- **Ideas introduced before use in part 2.** The findings used quad, key id, key checkpoint section, current checkpoint,
  ghost checkpoint, ghost area and jump, but only the overview introduced them. A paragraph at the end of
  [Sources and method](README.md#sources-and-method) now presents them in the terms of the overview.
- **One meaning per sign.** "→" is C → N, a quad, but Findings 4 and 8 also used it for "respawn point 27 gives
  checkpoint 107" ("27 → 107"); those lists are written out now. "At the point of Finding 5" became "at the position of
  Finding 5", with the position.
- **Precision.** The overview says that a kart inside a quad gets a ghost checkpoint on 12 courses, and Finding 2 gave
  11 on its first grid and Music Park only on the finer one; Finding 2 now gives the total. Step 3 of [Frame by frame on
  Wuhu Loop](README.md#frame-by-frame-on-wuhu-loop) said that `Vehicle::calcMove` starts the respawn; as [Starting a
  respawn](README.md#starting-a-respawn) says, it sets `jugem_recover_ai_oob`, and the respawn starts from that.
- **Daisy Cruiser test.** The note of the fourth document review ("which overlaps it there") was resolved without
  changing the claim. Run with `ghost_checkpoints.py`, (−339, 695) is inside both quad 0 and quad 64, and 5 to 10
  units to −X it is inside 64 only. So "it" was quad 0, and the kart left quad 0 into the part of quad 64 beyond it.
  The sentence now says so.
- **Smaller points.** History was removed from Finding 8 ("an open question of the earlier passes"). In How to verify,
  the in-game recipe now names the members it writes by offset (`KartInfo::m_previous_checkpoint_index` to
  `m_key_checkpoint_id`, `KartInfo::m_flags`). Lines wider than 120 characters in the overview, Finding 4 and Finding 8
  were rewrapped, and "forwards or backwards" became "forward or backward", as elsewhere.

No claim was changed.

#### What looks factually wrong

Nothing.

#### Noted, not blocking

- Finding 3 refers to "the file loader" that reads byte 0x14 of the load argument (How to verify disassembles it at
  0x00447EF0). The function has no name in `eur2` or `dlp`, so it is not in the Functions table as
  the naming rules of WRITING.md ask. It is a generic loader with 35 callers
  (fonts, UI, Mii shaders, ...). Naming it needs research, not a document review.
- The open question that suggests better names for the existing `KartInfo::m_previous_checkpoint_index` and
  `Force_No_Lap_Completion` is left to the human.
- The notes of the first document review on `MapdataCheckPointAccessor` and on how the figures were made still apply.

Status stays `verified`; the folder stays in `final/ghost-checkpoints/`.

### Layout update

2026-10-06, made at the user's request outside the pass procedure, to follow the new layout of a topic in
WRITING.md:

- `## How to verify` and `## Review` moved from `README.md` to this document, unchanged except for their links: those
  to the topic document now name `README.md`, and the mentions of Findings 3, 5, 6 and 8 in the text of How to verify
  became links. The overview's link to [Running ghost_checkpoints.py](#running-ghost_checkpointspy) points here.
- `## Patches` was removed from `README.md`. What it said is in the glossary (the members the patch names, with their
  status) and in the reviews (`verify` passes), except that the bytes 0x06..0x07 and 0x0E..0x0F of `MapdataCheckPoint`
  are padding, which moved to that class's line in the glossary.

No claim was changed. Status stays `verified`.
