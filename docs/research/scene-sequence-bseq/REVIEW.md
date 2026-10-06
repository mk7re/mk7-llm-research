# Review and verification steps for `Scene and menu sequencing (BSEQ: .brs / .bss)`

## How to verify

The flow graph can be regenerated with the command in [Finding 15](README.md#15-the-flow-graph-tool). Its boxes and labels can be compared
with any panel's file.

```
mk7-llm-research/mk7 decomp Sequence::SequenceResource::create          # "%s-%s.%s", +0x1C, +0x2C, +0x30, +0x34
mk7-llm-research/mk7 read 0x0049ff18 2                                    # "brs", "bss"
mk7-llm-research/mk7 decomp Sequence::SequenceResource::searchSequenceBlock 0x0051d6c4 0x0051d5b8   # block search by (id, mode); code lookups with default
mk7-llm-research/mk7 decomp Sequence::SectionDirector::create Sequence::SectionDirector::findAttachedDisableSection \
    Sequence::SectionDirector::attachedDisableSectionFinder        # pools, instances, finder (root forced to type 5)
mk7-llm-research/mk7 decomp Sequence::SequenceLayer::attachSection Sequence::Section::readyOuter   # layer chain; mode, and ID + block for sequences
mk7-llm-research/mk7 dis Sequence::Section::clearOuter                    # does not reset m_parent_layer (+0xC)
mk7-llm-research/mk7 decomp Sequence::SectionClassManager::constructSection   # class lookup by name, dummy fallbacks
mk7-llm-research/mk7 vtable 0x0064cfec                                    # one registered class info (BootTask)
mk7-llm-research/mk7 decomp Sequence::SceneSequence::init Sequence::SequenceEngine::createRootSequence   # root mode (+0x08), root enter code by name
mk7-llm-research/mk7 decomp Sequence::SequenceEngine::getDefaultRootSceneEnterCode && \
    mk7-llm-research/mk7 decomp -i dlp Sequence::SequenceEngine::getDefaultRootSceneEnterCode   # TitleScene/FromFriendList vs "DLC"
mk7-llm-research/mk7 read 0x00646a70 3 && mk7-llm-research/mk7 read 0x00649018 3   # root name/mode/enter code slots of both vtables
mk7-llm-research/mk7 decomp Sequence::SceneSequenceProxy::ready Sequence::SceneSequenceProxy::sceneStart \
    Sequence::SceneSequenceProxy::updateState Sequence::SceneSequenceProxy::step   # scene change, .bss name, codes by ID, exit wait
mk7-llm-research/mk7 decomp Sequence::DashSceneIDConverter::defineSceneIDDictionary Sequence::SceneIDConverter::initDictionary
mk7-llm-research/mk7 decomp Sequence::SerialSequence::enter Sequence::SerialSequence::updateState \
    Sequence::ParallelSequence::enter Sequence::ParallelSequence::updateState Sequence::DelegateSequence::updateState
mk7-llm-research/mk7 decomp Sequence::ExecutableSection::enter Sequence::ExecutableSection::setReturnCodeEnum Sequence::PracticalSection::ready
mk7-llm-research/mk7 decomp Sequence::BootTask::convertEnterCodeImpl && mk7-llm-research/mk7 dis Sequence::BootTask::onTaskStep   # saves m_boot_task_resume_state, returns 0
mk7-llm-research/mk7 decomp Sequence::RootExitTask::onTaskStart 0x004d2428 # m_root_exit_task (+0xCC); Sequence::ExitApp
mk7-llm-research/mk7 dis -n 0x60 0x00442830                               # calcBeforeStructure: the two applet getters, +0x79, +0x78, ExitApp
mk7-llm-research/mk7 dis 0x00443028 && mk7-llm-research/mk7 dis -i dlp System::SystemEngine::startExit   # same body
mk7-llm-research/mk7 decomp System::GameSetting::init Net::NetworkEngine::sceneExit   # m_is_from_friend_list set at boot, cleared on scene exit
mk7-llm-research/mk7 read 0x0064dd14 64                                   # DummyPage vtable: only onPageEnter is its own
mk7-llm-research/mk7 dis Sequence::DummyTask::onTaskStep && mk7-llm-research/mk7 dis Sequence::DummyTask::onTaskStart   # return -1
mk7-llm-research/mk7 decomp Sequence::MenuTitle::initControl Sequence::MenuTitle::onPagePreStep UI::BaseMenuButtonControl::completeNext
mk7-llm-research/mk7 dis Sequence::RacePage::initControl                  # play mode dispatch; mode 3 sets 0x22 without a guard
mk7-llm-research/mk7 dis 0x004d947c && mk7-llm-research/mk7 dis -i dlp Sequence::RacePage::initControl_WiFiVS   # guard mov r0,#0 / cmp / beq
mk7-llm-research/mk7 dis Sequence::RacePage::initControl_MultiGP         # genResult before the guard; both paths end in the same tail call
mk7-llm-research/mk7 decomp Sequence::RacePage::genNextDebug              # debug end-of-race menu, 0x21 / 0x22
mk7-llm-research/mk7 decomp Sequence::Common_SystemDialog::onPageEnter Sequence::Common_SystemDialog::onPagePreStep \
    0x004b94d0 Sequence::NetworkErrorChecker::startDisconnect_ Net::NetworkEngine::checkStandAlone   # Error vs SimpleError
mk7-llm-research/mk7 dis -n 0x40 0x00291b40                               # NetworkErrorHandler allocated with 0x4c bytes
mk7-llm-research/mk7 sym isCompletable                                    # the seven isCompletable; each is mov r0, #1
mk7-llm-research/mk7 dis -n 0xd0 Sequence::BaseRacePage::initCommon       # race mode copied from GetRaceInfo()+0x164 to +0x26c
mk7-llm-research/mk7 decomp Sequence::BasePage::setDemoMode Sequence::DemoPage::onPageComplete   # save + play mode 3; restore
mk7-llm-research/mk7 xref Sequence::BasePage::setRaceMode                 # the 25 callers (and setDemoMode, setReplayMode)
mk7-llm-research/mk7 decomp System::GetSaveDataManager                    # save data manager from the system engine
git apply --check mk7-llm-research/docs/research/scene-sequence-bseq/bseq-format.patch
```

The play modes of [Finding 9](README.md#9-debug-and-unused-content) were watched in the running game (decompile first,
then start the emulator):

```
mk7-llm-research/mk7 emu start --unlock
```

then, from a Python script on the `mk7re.dynamic` library: `Session.wait_section("Page_Title")`; take `MenuData` from
`Menu.menu_data()`; in a thread, connect a `GdbClient`, set a write watchpoint (kind 2, 4 bytes) on `MenuData` + 0x74 + 0x164
and an execute breakpoint on 0x0047488C (the store in `initCommon`; `r0` is the play mode, `r4` the page, whose vtable names
its class), and log each stop; meanwhile let the title demo start by itself (`run_until` `Page_TitleDemo`, then
`Flow.advance("Page_Title")`), and run `Flow.grand_prix(0)`, `Flow.time_trial(1, 0)` and `Flow.battle("balloon", 0)`. The
watchpoint reports late (the stop's pc is a few instructions after the write; its `lr` names the caller).

The range scans (no completion in the code of `MenuTitle` 0x004DDE98-0x004DED30 or of `TimeAttackChart` 0x00494E24-0x0049693C,
the only `completePage` call of `Common_SystemDialog`, the loads of 0x23 in the race pages, the reads of header offsets 0xA and
0xC, and the accesses to `SystemEngine` +0x78..+0x7D) were made on a full objdump of the code:
`arm-none-eabi-objdump -D -b binary -m arm --adjust-vma=0x100000 local/code/eur_rev2/eur_rev2_code.bin`.

File checks (from `mk7-llm-research/local/romfs/eur2/rom/UI/common.szs.d`): `xxd Root-Default.brs | head` shows the header
(`m_sequence_id` 0x14E548E6, `m_root_mode_id` 2, counts 7/2/0/1/0/1/2, 27 blocks, offsets 0xA0/0xE08/0xE08) and the offset table
from 0x34. The SARC hash (`h = h * 0x65 + c`, as `mk7re/static/romfs.py:name_hash`) of `BootScene-Default.bss` is 0x73DC5722.

## Review

### Fact check

Pass 2 under the current rules (WORKFLOW.md), fresh context, 2026-10-03, on base commit
b65de469294c2b1fe7e0b25cd66993bf9e0236b3 with `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95). The topic had already
been through a combined review under older rules (2026-10-02); its corrections are kept in the text, and this record replaces
that review.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied with `patch -p1` to a fresh copy of `template/`; `mk7 --templates <copy> verify
  --version EUR_REV2` and `verify` (USA_REV1) pass, before and after the additions below. Every member row of the glossary was
  looked up with `mk7 --templates <copy> field <class> <offset>`, and the class sizes with `mk7 struct`; all match.
- **Data.** A new parser, written for this pass from the layout read in the code and derived from neither `bseq_flow_graph.py`
  nor the earlier review's script, read the 29 files: the header constants (4, 1, 0, 0, end of the offset table),
  `m_num_sections` against the pools plus instances, `m_num_layers` against the largest parallel block, root mode IDs, padding,
  the pairs of section type and block type, the SARC hash names of the 20 unnamed files, the equality of the ID and code tables
  of all 23 proxies of the two `.brs` files with their `.bss` roots, the engine creator lists, the unregistered class names, the
  pool and block counts quoted in Finding 3, and every flow quoted in Findings 6 to 10 (`Root`, `RootMain`, `ProductMain`, the
  `MenuScene` root, `Seq_Title`, `Seq_Single`, `Para_TAChart`, `Seq_TAChart`, the `RaceScene` root, `Seq_Race`, `SceneTestRoot`,
  the debug and E3 files).
- **Class registry.** The 91 names were read from the string each `getClassName` loads, through the vtables loaded by
  `definePageClassInfoList` / `defineTaskClassInfoList`, not from the ported symbol names; they are exactly the lists of
  Finding 3. The instant / lasting split matches which classes override `onTaskMain` or `onTaskStart` / `onTaskStep`, and the
  profile of the graph tool has the same lists.
- **Code.** Decompiled or disassembled again in `eur2`: `SequenceResource::create` and its callers, the code and block searches
  and the `SectionBlock` accessors, `SectionDirector::create` and the finder, `SequenceLayer::attachSection` / `ready`,
  `Section::readyOuter` / `enterOuter` / `completeOuter` / `clearOuter` / `updateStateOuter`, `constructSection` and the
  `SectionClassManager` constructor, the dummy hooks and the `DummyPage` vtable, the `SequenceEngine` root functions and the two
  vtables, the serial, parallel, cross fade and delegate functions, every `isCompletable` and `isSyncFadein`, the task bases,
  `BootTask`, `ClearRaceInfoTask`, `MMenCheckPage`, `MenuTitle`, `RootExitTask`, `Sequence::ExitApp` and its callers, the proxy
  functions, the scene dictionary and the engine creators, `Page::create` / `enter` / `step` / `finish` / `completePage`, the
  button functions, the system dialog and `NetworkErrorChecker::calc` / `startDisconnect_`, `checkStandAlone`, the scene and
  scene manager functions, `GameScene::prepare` / `exit` / `callRootEngine`, `RootScene::sceneCalc`, the `RacePage` set-up
  functions and `genNextDebug`. `dlp`: `getDefaultRootSceneEnterCode`, `RacePage::initControl`, `initControl_SingleGP`,
  `initControl_WiFiVS`, `SystemEngine::calcBeforeStructure` and `startExit`.
- **Scans**, on a full objdump of the code: reads of header offsets 0xA / 0xC (repeated with a new script; Finding 2), accesses
  to `SystemEngine` +0x78..+0x7E, loads of 0x23 in the race page functions, and completion calls in the code of `MenuTitle`,
  `TimeAttackChart` and `Common_SystemDialog`.
- **Flow graph.** `bseq_flow_graph.py` was run with the profile; its output is pixel-identical to `game_flow.png` (7717 x 18943,
  37 panels).

#### What was changed

Corrections of claims:

- Finding 9 (was 8): the guard cited "in `initControl`" belongs to the function after it, `RacePage::initControl_WiFiVS`
  (unnamed in `eur2`, named from `dlp`). `RacePage::initControl` itself only dispatches by play and rule mode, and its branch for
  play mode 3 (`Demo`) sets `Debug_Exit` on the pause menu's quit button **without** a guard. The document no longer says that the
  race's debug codes cannot be produced at all; the open case is in Open questions and Confidence, and Finding 12 and the
  overview say so too.
- Finding 3: `readyOuter` stores only the mode for a practical section; the ID and block are stored for sequences only (practical
  sections get them at creation). `clearOuter` does not reset `Section::m_parent_layer`, so the glossary note "null while the
  section is free" was wrong; the consequence for pool reuse was added to Findings 3 and 14.
- Finding 5: a parallel flow entry with `dst_code == 0` lets the default check run only when no child scanned before it is still
  running. `DelegateSequence` was read in full (it was "partly read"): enter, the owner hand-over, the return, and the cases
  without an entry. Finding 6 (was 0) calls subsection 0 the owner in both places.
- Finding 8 (was 7): the two "boot flags" of `SystemEngine` that `SequenceEngine::init` clears are not untouched by other code, as
  the Open questions said: `MenuTitle::onPageEnter` / `onPageComplete` write them and `SleepChecker::check` and `gpuSleepProc`
  read them. They now have provisional names. The mention of the byte after them, cleared by `BootTask::onTaskStart`, was
  dropped as irrelevant.
- Finding 12: the unnamed function called from `gpuSleepProc` is `SystemEngine::startExit` (same body as in `dlp`); the two
  "unnamed SDK getters" are named from the `dlp` calls at the same place; the two `SystemEngine` flags of the exit path are named.
- Finding 10: `Common_SystemDialog::onPagePreStep` completes only when a flag of another engine is clear; `onPageEnter` resets
  the checker only when `m_check_network_errors` is already set, and that flag is also written by other pages through
  `MenuData`; the conditions under
  which `calc` copies the error kind are stated with `NetworkErrorHandler::m_error_code`. `NetworkErrorHandler` is 0x4C bytes
  (allocation in `NetworkEngine::createBeforeStructure`), which allowed naming the error kind.
- Finding 11: the proxy's exit timer starts only after two further checks on other engines.
- Finding 9: `E3ThankYou` has no `RootReset` layer (only the other three E3 files do); `SoundTestScene` and `Viewer` also hold a
  single `BackToDebugMenuPage`.
- Finding 2: the whole-code scan for header reads was repeated with a new script (31 hits; the only sequence-code hits are the
  section-block code-table accessors).

Patch: `NetworkErrorHandler` size 0x40 -> 0x4C and `m_error_kind`; `SystemEngine::m_is_exit_started`, `m_is_close_requested`,
and the provisional `m_is_title_page_active` and `m_title_sleep_flag`; the comments that cited an address or "+0x40" now use the
names; the pool comment says "must cover". The patch was regenerated from a fresh copy of `template/`.

Document, to follow the current WRITING.md (the topic was written under older rules):

- The Summary became `## Overview`, rewritten for readers new to the topic and placed before the glossary, with links to the
  findings. It also takes the plain-language part of the old Finding 0 (design concepts) and of the editing advice.
- The header's `Data` and `Hints` bullets and the terms paragraph moved to `### Sources and method` at the start of the findings.
- The findings were renumbered (old -> new: 0 -> 6, 6 -> 7, 7 -> 8, 8 -> 9, 9 -> 14, 14 -> 15, 15 -> 16; the others keep their
  number), and the headings with arrows were renamed.
- Addresses were removed from the text outside the glossary and `## How to verify`; functions are named instead, and vtable slots
  by their virtual. The Functions table lists every function the text refers to, one per row, and a `### Data` table lists the
  vtables. Glossary tables were added for `System::SystemEngine`, `Net::NetworkErrorHandler` and `RaceSys::CRaceMode`, and a row
  for `BaseRacePage::m_race_mode`.
- `## Review` now has this `### Fact check` subsection; the record of the earlier combined review was replaced by it.

Wording and the depth of the overview are left to pass 3.

#### What remains uncertain

- The "Likely", "Not followed" and "Unknown" items of [Confidence](README.md#confidence).
- Not re-traced in this pass: `GameScene::exit` beyond its order of calls, the meaning of the `nn::applet` state bytes, and the
  heaps freed with a popped scene task.
- The names given from `dlp` by position (`initControl_WiFiVS`, the two `nn::applet` getters) rest on the call structure, not on
  an identical body; `Sequence::ExitApp` and `SystemEngine::startExit` have the same body as in `dlp`.
- Not in the patch, suggested as a follow-up: `SerialSequence` and `CrossFadeSequence` hold the pending destination of a flow
  entry in members that still carry the old flow-entry names (`m_next_subsection_list_block_entry_index`,
  `m_next_return_code_item_index`, the latter declared `u16` with size 4), although that code is an enter code, not a return
  code.

### Document review

Pass 3 (WORKFLOW.md), fresh context, 2026-10-03, against WRITING.md. The document was
read section by section as a reader new to the topic; the binary was not consulted. Two code-table readings were checked
against the files to word a passage correctly (Finding 9: ID 15 belongs to `Seq_Title`'s table; Finding 10: the numbers in the
table are code IDs).

#### What was changed

Overview:

- The user's term "exit code" is tied to the document's term, return code, where return codes are introduced.
- The **root** of a file is introduced before it is used, and "the first section of the `.bss`" (Scenes, Editing the files)
  became "the root of the `.bss`", the term used in part 2. "A group of sections" and "sequence" are tied together in one
  sentence.
- Terms a newcomer could not know are explained where they first appear: engines, the system dialog page, the Download Play
  child, and the "hash table of the tools" (now "the list of known file names", one term throughout).
- Two statements now keep the certainty of their findings: a page *usually* ends with a button, with the title screen's idle
  timer as the other kind of ending (Finding 13); and `ProductMain` does not end in the retail game *except possibly* through
  the race's debug path (Findings 9 and 12, Open questions). "Debug exit code" became the name of the code, `Debug_Exit`. The
  bullet on unregistered debug classes now links to Finding 9 and says "do not exist in the retail game" instead of "no longer
  exist".

Part 2:

- `### Sources and method`: the terms paragraph became a `#### Terms` list and now also introduces data holders, subsections
  and the subsection index, the root of a file, the numbered section states (used in Finding 3 before Finding 5 defines them),
  and the `section` `code` -> `section` `code` notation of the chains.
- One notation for chains: the dotted form (`RaceScene.SingleTA_Chara`, `ClearRaceInfoTask.Title_Top`) of Finding 8 was
  rewritten in the notation used everywhere else.
- Flow entries: Finding 2 now maps the short field names (`src_index`, `src_code`, `dst_index`, `dst_code`) to the glossary
  members, and Finding 5 uses them throughout instead of mixing `src` / `dst` with `dst_index`. Finding 14 uses the same names.
- "Exit code" was replaced by "return code" in Findings 11 and 15.
- Finding 9: "return code ID 15" says which table it belongs to; the `Demo` play mode cites the template comment that the
  overview's description of it comes from.
- Finding 10 got two subsections (`The dialog page in a scene`, `How a network error completes the page`) before the existing
  `Where the codes lead`, and a sentence saying what the numbers in its table are.
- Finding 14: the eight bold-titled list items became `####` subsections, in the same order.
- Finding 1: the hashed file name is explained where it is first used. Bare member names in Findings 3 and 5 were qualified
  (`BSEQ::m_num_layers`, `Section::m_return_code_id`). Paragraphs with overlong lines were rewrapped.

No claim was changed. Addresses appear only in the glossary and `## How to verify`; every in-document link resolves.

#### Found, not resolved

- **"E3 2010"** (overview, twice: the opening paragraph and `### Debug and unused content`). No finding gives a year: Finding 1
  and Finding 9 only say "E3 demo", and the files only name `E3MenuScene`, `E3Title`, ... The only "E3 2010" in the document is
  in Open questions, about an "E3 2010 version of the format" mentioned by the hint scripts next to Nintendogs + Cats, which is
  not evidence for the year of MK7's E3 files. The game was, as far as the reviewer knows, first playable at E3 2011, so the year
  looks wrong; pass 2 should either back it with evidence or drop it.
- **"a model viewer"** (overview, `### Debug and unused content`). Finding 1 lists `Viewer-Default.bss` only as "debug", and
  Finding 9 says it holds a single `BackToDebugMenuPage`; nothing shows what it views. Its engine mode `Viewer` (Finding 7) is
  the only hint. Pass 2 should back "model" or reduce it to "a viewer".
- Finding 10 closes with "This matches what players see": a comparison with play that is not a finding and not tested in the
  game. Not factual in the sense of the code, but pass 2 may want to qualify or remove it.

Because of the first two points the status is set back to `pending verification`, and the topic stays in
`pending-verification/` for another fact check.

### Fact check, second pass

Pass 2 again (WORKFLOW.md), fresh context, 2026-10-04, after the document review above sent the topic
back. Base commit unchanged for `template/` (HEAD is now 4767b36, which changes only `mk7-llm-research/`); `eur2` sha1
e3edb9771fea3149ddfe309e3ca8453046ef8a95.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes on the current HEAD. Applied to a fresh copy of `template/`;
  `mk7 --templates <copy> verify --version EUR_REV2` and `verify` (USA_REV1) pass. Every member row and class size of the
  glossary was looked up with `mk7 --templates <copy> field` / `struct` by a script; all match.
- **Functions table.** Every address was looked up with `mk7 sym`: each is a function start carrying the listed name, except
  the rows marked `new` (unnamed in `eur2`) and `NetworkErrorChecker::calc` (unnamed in the port, as its note says).
  `RacePage::initControl_WiFiVS` is reported by `mk7 sym` as `initControl+0x150`: `initControl` falls through into it after a
  `nop` (its WiFi VS case pops its frame and runs on into the `push` at that address), so the address is a function entry that
  the tool's function bounds miss.
- **Data.** A new BSEQ parser, written for this pass from the glossary layout, read all 29 files: header constants, the
  `m_num_sections` sum and `m_num_layers` maximum, root mode IDs, padding, section/block type pairs, the SARC hash names of the
  20 unnamed files, engine creator modes, the 21 proxy blocks of `Root-Default.brs` and the 23 proxy/`.bss` root table pairs,
  the unregistered class names and where they occur, and the flows of `Root`, `RootMain`, `ProductMain`, the `MenuScene`,
  `RaceScene`, `TrophyScene` and `BootScene` roots, `Seq_Title`, `Seq_Single`, `Seq_Race`, `Para_TAChart` and `Seq_TAChart`,
  with every code ID quoted in Findings 2, 8, 9 and 10. All agree with the document.
- **Class registry.** The `eur2` symbols have 94 `SectionClassInfo<T>::getClassName`: the 91 names of Finding 3 plus the three
  dummies. Every class used by the retail files is among them.
- **Code**, decompiled or disassembled again in `eur2`: `SequenceResource::create` (and the `"brs"` / `"bss"` strings), both
  `searchItem`, `searchSequenceBlock`, `SectionDirector::create`, `findAttachedDisableSection`, `attachedDisableSectionFinder`,
  `constructSection`, `SceneSequence::init`, `createRootSequence`, `getDefaultRootSceneEnterCode` (and the `dlp` one, which loads
  `"DLC"`), the root slots of both vtables, `Section::enterOuter` / `completeOuter`, `ExecutableSection::enter` /
  `setReturnCodeEnum`, `ClearRaceInfoTask::onTaskMain`, `MenuTitle::onPagePreStep` (idle limit 0x708) and the four button codes
  of `initControl`, `MMenCheckPage::onPageEnter` / `onPagePreStep`, `RootExitTask`, `Sequence::ExitApp`,
  `NetworkErrorChecker::calc` / `startDisconnect_`, `NetworkEngine::checkStandAlone`, `Common_SystemDialog::onPageEnter`,
  `ParallelSequence::enter` / `updateState`, `SerialSequence::enter`, `RacePage::initControl` and the debug branches of all
  eight `initControl_*`, the `NetworkErrorHandler` allocation and the seven `isCompletable`.
- **The points of the document review.** The BSEQ files and the code strings of `eur2` and `dlp` (`mk7 strings`) give no year for the E3 files and nothing about what `Viewer` shows: its file holds one `BackToDebugMenuPage`, its
  proxy names the scene `DebugViewer`, and its engines use the mode `Viewer`.
- **Flow graph.** `bseq_flow_graph.py` was run again with the profile; the output is pixel-identical to `game_flow.png`.

#### What was changed

- Overview: "E3 2010" became "E3 demo" in both places, and "a model viewer" became "a viewer"; neither the year nor "model"
  has evidence. The list of the 19 unreferenced files also names the debug race and debug channel scenes, which it left out.
- Finding 9, the race's debug menu: the guarded branch is not at the start of every `initControl_*` function (only of
  `initControl_SingleGP`), and it returns after its last call. The claim that races would end with the Retry / Exit dialog
  without the guard was wrong for `initControl_SingleGP`, whose branch calls neither `genNextDebug` nor `genResult`; it now says
  so.
- Finding 10: "This matches what players see" became a summary of the table that says it is read from the code and the files,
  not tested in game.
- How to verify: `mk7re/romfs.py` moved to `mk7re/static/romfs.py`.
- The `__pycache__` folder that an earlier run of the graph tool left in the topic folder was removed (the run here used
  `python -B`).

No change to the patch.

#### Dynamic check of the open play mode question

Asked by the user after the pass above: whether a race of `RaceScene` can run in play mode 3, the open question of Finding 9.
The writers of the menu race info's play mode were read in the code (`BaseRacePage::initCommon`, the three setters, every
caller of `setRaceMode`, `setDemoMode` and `setReplayMode`), and then watched in Azahar with a gdb watchpoint and breakpoint
through the title demo, a Grand Prix, a time trial and a balloon battle (method in [How to verify](#how-to-verify)). Play
mode 3 is set only for the course intro, the title demo and the winning run, and no `RacePage` was set up with it. The open
question was answered and removed; Finding 9 has a new subsection with the evidence, the overview, Finding 12 and Confidence
were changed to match, and the glossary has the new members and functions. Multiplayer and online races were not run (the
code gives them play mode 1 or 2).

#### What remains uncertain

- The "Likely" and "Unknown" items of [Confidence](README.md#confidence), and the uncertain points of the first fact
  check above.
- Not re-traced in this pass: `GameScene::exit` / `prepare`, the scene stack, `SequenceEngine::init`, the delegate and cross
  fade sequences, `UI::BaseMenuButtonControl::completeNext` and `Page::completePage`, and the whole-code scans of Finding 2 and
  Finding 9. The first fact check covered them, and nothing found here contradicts them.
- `checkStandAlone` sets error kind 5 under several conditions on members that are not named; "the player is left alone" rests
  on the function's name and on the `checkSessionIsOrphan` case.

### Document review, second pass

Pass 3 again (WORKFLOW.md), fresh context, 2026-10-04, against WRITING.md, after the
second fact check. The document was read section by section as a reader new to the topic. The binary and the files were consulted
only to word passages: the enter codes of the `MenuScene` root and of `Seq_Title` (read with the parser of
`bseq_flow_graph.py`), and `mk7 sym` for the functions added to the glossary.

#### What was changed

Overview:

- **Scene and kind of scene.** "Scene" was used both for the kind of scene that the game switches to (boot, menu, race, ...)
  and for the scene that a proxy runs (`DemoScene`, `RaceScene`), which made "`ProductMain` chains the scenes: menu, demo, race,
  ..." read as if the course intro ran in a demo scene. `### Scenes` now introduces the seven **kinds** and says that several
  proxies can use the same kind, with the race kind as the example from the table of Finding 7; the list in
  `### From boot to the menus and back` names the scenes that `ProductMain` runs, and now includes the title demo, which is one
  of its children (Finding 8) but was missing. The network errors paragraph names the four scenes instead of "the menu, race,
  trophy and boot scenes", which would include every race-kind scene, and the editing advice speaks of kinds.
- **Statements that did not match their finding:**
  - "the name is only a label": Finding 3 says the name of a proxy builds its `.bss` file name; the sentence now says so;
  - "names matter in one place": Finding 4 gives a second one, the root enter code chosen by name; both are now given;
  - "29 files: one root file and one `.bss` per scene": the 29 include the unused second root file of Finding 1;
  - "the counts in the file header must be exact": Finding 14 asks the section count to be exact and the pool and layer counts
    to be large enough.
- **Certainty kept from `## Confidence`:** "`ProductMain` does not end" and "the menu scene can never return `Back`" rest on
  items that Confidence lists as likely; they now say "most likely". The network error paragraph now says that its result was
  read from the code and the files, not tested in game, as Finding 10 does.
- The debug race bullet introduces the **play mode** before using it, and describes the `Demo` mode once (it gave two lists of
  its uses, one with "award ceremonies" and one with "the winning run").
- A doubled link to Finding 12 was removed, and the edited paragraphs were rewrapped.

Part 2:

- `#### Terms` introduces the scene, the scene ID, the scene proxy and its scene name, which Findings 7 to 11 rely on.
- The chains of Findings 8 and 10 give the code of every section, as `#### Terms` defines them (`Seq_Title` `FromFriendList`,
  `Page_Title` `Next`, `Seq_WiFi` `DirectOpponent`), read from the files.
- "has no template" / "a class without a template" (Findings 3 and 9) became "no file in `template/`", since "template" also
  reads as a C++ template.
- The dashed "(always)" arrow of the flow graph, used in Findings 6 and 10 before the tool is described, now points to
  Finding 15.
- Functions named in the text but missing from the Functions table were added: `SectionClassInfoList::compareByName`,
  `RacePage::genResult`, `BasePage::openMenu`, `GameSetting::getSimpleAddress`, `SystemSaveData::getLastMenuSetting`.
- A list item of `## Confidence` ended with a full stop inside the list.

No claim of part 2 was changed. Every in-document link resolves.

#### Found, not resolved

- **`getLastMenuSetting`** (Finding 11, `What survives a scene change`): "`MenuData` (menu state, the selections that
  `getLastMenuSetting` compares)". No finding is behind this aside, and the function does not fit it: it is
  `System::SystemSaveData::getLastMenuSetting`, a getter that copies the last driver, body, tire and wing from the save data
  into its four pointers, and compares nothing. The compare is in its caller `SceneSequenceProxy::complete`, which, when
  `SceneSequenceProxy::field_0x4C` is 2, tests the result against `SceneSequenceProxy::m_driver_id`, `m_body_id`, `m_tire_id`
  and `m_wing_id` and starts a save command when they differ; `SceneSequenceProxy::enter_post` calls the getter too. Nothing
  shows that the compared selections are in `MenuData`. Pass 2 should correct the example or remove it. Rewording it would change what it claims, so it was left as it is.

Because of this point the status is set back to `pending verification`, and the topic stays in `pending-verification/` for
another fact check. The rest of the document passed this review.

### Fact check, third pass

Pass 2 again (WORKFLOW.md), fresh context, 2026-10-04, after the second document review sent the topic back.
HEAD is 4767b36 (no change to `template/` since the base commit); `eur2` sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95. Besides
the point of the document review, this pass re-traced what the earlier fact checks left out, and repeated the whole-code scans
with its own scripts.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied to a fresh copy of `template/`; `mk7 --templates <copy> verify --version
  EUR_REV2` and `verify` (USA_REV1) pass. Every member row and class size of the glossary was looked up with `field` / `struct`
  by a script; all match.
- **The point of the document review.** `System::SystemSaveData::getLastMenuSetting` only copies the last driver, body, tire and
  wing out of the save data. `SceneSequenceProxy::enter_post` stores them in the proxy when the current scene is Menu, and
  `SceneSequenceProxy::complete` reads them again and starts a save command when they differ. The selections are save data, not
  `MenuData`. The root engines were read in `RootScene::sceneEnter` (System, Effect, Sound, Network, Sequence, Mii) and the
  save data manager in `GetSaveDataManager` (the system engine). No root engine is called `RaceSys`: `Sequence::GetRaceInfo`
  returns `MenuData::m_race_info`, and `RaceSys::GetRaceInfo` reads an engine of the current scene.
- **Not re-traced by the earlier fact checks, decompiled here:** `SequenceEngine::init`, `createRootSequence` and
  `getDefaultRootSceneEnterCode`; `GameScene::exit` and `prepare`, `Scene::prepare`, `Scene::calc`, the `Scene` constructor
  and destructor, `SceneManager::changeChildScene` / `exitScene`, and the UI archive chosen per scene ID; the root engines
  called by `prepare` (`callRootEngine` 9, 3, 6, 8 = `_9`, System, Sound, Effect); `SceneSequenceProxy::step` (180 frames);
  `DelegateSequence::ready` / `enter` / `updateState`; `CrossFadeSequence::changeSubsection` and its flow lookup;
  `UI::BaseMenuButtonControl::completeNext`, `BasePage::completeNext` and `Page::completePage`. All agree with Findings 3, 5,
  8, 11 and 13.
- **Scans**, on a new objdump of the code, with new scripts:
  - the header reads of Finding 2: 39 hits with this pass's heuristic, and again the only ones in sequence code are
    `SectionBlock::getEnterCodeTable` and `getReturnCodeTable`;
  - the constant 0x23 in the 145 `RacePage` / `BaseRacePage` functions of the symbol map, plus `initControl_WiFiVS`: only the
    compare in `BaseRacePage::convertReturnCodeImpl`;
  - `mov rN, #0` directly followed by `cmp rN, #0` (the compare not a branch target), whole code: 17 places, 12 in sequence code
    (the eight `initControl_*`, `BaseRacePage::initCommon` and `onPageFadeout`, `TrophyPage::onPagePreStep`,
    `EndingPage::onPagePreStep`).
- **The eight `initControl_*`**, disassembled in full: the guard, the 0x22 store into the quit button, `genNextDebug`, the order
  of calls around the guard, and how each path ends.
- **Data.** A new BSEQ parser, written from the glossary layout, read the 29 files: header constants and counts,
  `m_num_sections`, `m_num_layers`, pools and block counts, section/block type pairs, padding, `m_num_instances`, root mode IDs,
  engine creator modes, the SARC hash names of the 20 unnamed files, the 23 proxy/`.bss` root table pairs, the 15 unregistered
  class names and their files, and the flows of `Root`, `RootMain`, `ProductMain`, every retail scene root, `Seq_Title`,
  `Seq_Single`, `Para_TAChart` and `Seq_Race`, including the codes of the chains added by the last document review
  (`Seq_Title` `FromFriendList` / `DLC` / `DirectWiFi`, `Page_Title` `Next`, `Seq_WiFi` `DirectOpponent`). All agree, except
  the scene roots below.
- **Flow graph.** Run again (`python -B`); the output is pixel-identical to `game_flow.png`.

#### What was changed

- Finding 11, `What survives a scene change`: the aside "the selections that `getLastMenuSetting` compares" was removed, and
  "the race settings (`RaceSys`)" became the race settings in `MenuData`. The bullet now says which root engine holds what.
  `getLastMenuSetting` left the Functions table; `System::GetSaveDataManager` was added.
- Finding 9, `The race's debug menu`: in seven of the eight `initControl_*` functions the result menu is built **before** the
  guard, so the debug branch would not replace the result menus, as the document said. It replaces the normal pause menu and
  the menu that follows the results (`genNext`, `genNextCommunity`, `genNextGP`, `genNextTA`). The branch also does not always
  return: in the five multiplayer and online set-ups it joins the end of the function, which the normal path runs too (a tail
  call to a function that `eur0` and `eur1` have as well). In `initControl_SingleGP` the guard follows `genRaceGP`; it is not
  at the very start. The functions that the corrected bullet names were added to the Functions table.
- Finding 9, `Other compiled-out branches`: `MenuChannel_ShowMii::showMyComment` has no such guard (its `mov r0, #0` /
  `cmp r0, #0` is the join point of a loop result, and branches land on the compare); it was replaced by
  `EndingPage::onPagePreStep`, which the scan found. The list is now the complete result of the scan, and the Functions table
  changed with it. `EndingPage::onPagePreStep` is a weak port (0.06), but its function is in the `onPagePreStep` slot of the
  vtable whose other overrides are `EndingPage`'s.
- Overview `### Scenes`, Finding 6 (`Parallel sequences`) and Finding 8 (`The scene files`): not every `.bss` root holds a
  serial sequence. Only `MenuScene`, `RaceScene` and `TrophyScene` do; `DemoScene`, `TitleDemoScene`, `WinningRunScene`,
  `EndingScene` and `ThankyouScene` hold one page next to `Page_Fader`, and `BootScene` holds `BootTask` next to the dialog and
  fader pages. The three passages now say so.
- How to verify: one command for the order of calls in `initControl_MultiGP`, one for `GetSaveDataManager`.

No change to the patch.

#### What remains uncertain

- The "Likely" and "Unknown" items of [Confidence](README.md#confidence), and the uncertain points of the earlier fact checks.
- What the function at the end of the five multiplayer and online `initControl_*` does; it is not part of any claim.
- `SceneSequenceProxy::enter_post` / `complete` (the save of changed driver and parts) were read only as far as the point of the
  document review needed; the document does not describe them.

### Document review, third pass

Pass 3 again (WORKFLOW.md), fresh context, 2026-10-05, against WRITING.md, after the
third fact check. The document was read section by section as a reader new to the topic. The files were consulted only to word
passages: the root children, return code tables and flow lists of `BootScene`, `MenuScene`, `RaceScene` and `TrophyScene`, read
with the parser of `bseq_flow_graph.py`. The binary was not consulted.

#### What was changed

Overview:

- `### Scenes`: the list of the parts of the screen that stay for the whole scene (background, timer, top bar, ...) was given for
  the menu, race and trophy scenes together, which read as if the race and trophy scenes had a background, timer and top bar. It
  now gives the menu scene's list and the shorter one of the race and trophy scenes, as Finding 8 does.
- `### Debug and unused content`: the debug race bullet now says what the compiled-out set-ups are since the last fact check (the
  debug end-of-race menu **and** a pause menu whose quit button returns `Debug_Exit`), so that the unguarded path that follows
  ("the quit button ... is given `Debug_Exit` as well") reads as related to them.

Part 2:

- Finding 1: `HashTable.saht` is introduced where it is first used, as the list of known file names of the research tools, with
  its folder, the term the overview uses.
- Finding 6, `Parallel sequences`: the same imprecise list of persistent parts as in the overview now says that `MenuScene` has
  all of them and the other two fewer.
- Finding 9, `The race's debug menu`: one term each for the debug end-of-race menu ("two-button end-of-race dialog" and "the
  Retry / Exit dialog" became it) and for the pause menu's quit button ("exit button" became it). The bullet rewritten by the
  third fact check was rewrapped (a line break in the middle of a sentence).
- Finding 10, `Where the codes lead`: "the same in the three scenes" became "the same in every scene"; the dialog page's return
  code table is the same in all four scenes that have it.
- Finding 11, `What survives a scene change`: "the sequence engine with `MenuData`, and the other root engines (System,
  Sequence, ...)" listed the sequence engine twice; `Sequence` was dropped from the list.
- Finding 12: "in retail `ProductMain` does not end" now says "most likely", with a link to Confidence, which lists both of its
  premises as likely; the overview already says so.
- Finding 14, `Names`: "a new proxy section, not a new scene" became "not a new scene ID", since `#### Terms` defines the scene ID
  as the kind of scene and a new proxy does make a new scene in the document's sense.
- Overlong lines in Findings 6, 8, 9 and 10 were rewrapped.

No claim was changed. Every in-document link resolves; addresses appear only in the glossary and `## How to verify`.

#### Found, not resolved

- **The system dialog in `BootScene`** (overview `### Network errors`; Finding 10, `The dialog page in a scene`). The overview
  says that the dialog page is part of four scenes, `BootScene` included, and that after a network error "it then ends with
  `Error` or `SimpleError`, and the scene ends with it"; Finding 10 says that the page "only takes part in the flow" when a
  network error has been handled. The table of `Where the codes lead` covers only `MenuScene`, `RaceScene` and `TrophyScene`. In
  `BootScene-Default.bss` the root (children `BootTask`, `Page_CommonSystemDialog`, `Page_Fader`) has no flow entry with the
  dialog page as source: its flow list holds one enter entry and nine entries from `BootTask`. By Finding 5, a parallel child
  whose return has no flow entry is only marked done, so in `BootScene` a completed dialog page would not end the scene. Whether
  the dialog's network check can run in `BootScene` at all (`m_check_network_errors`, a pending error at boot) was not looked at.
  Pass 2 should restrict the overview statement and Finding 10 to the three scenes of the table, or say what happens in
  `BootScene`. Rewording it would change what it claims, so it was left as it is.

Because of this point the status is set back to `pending verification`, and the topic stays in `pending-verification/` for
another fact check. The rest of the document passed this review.

### Fact check, fourth pass

Pass 2 again (WORKFLOW.md), fresh context, 2026-10-05, after the third document review sent the topic back.
HEAD is 4767b36 (no change to `template/` since the base commit); `eur2` sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95.

#### What was re-checked, and how

- **Patch.** `git apply --check` passes. Applied to a fresh copy of `template/`; `mk7 --templates <copy> verify --version
  EUR_REV2` and `verify` (USA_REV1) pass. The 166 member rows and class sizes of the glossary were looked up with `field` /
  `struct` by a script; all match.
- **Functions table.** The 248 addresses were looked up with `mk7 sym` by a script: each is a function start whose symbol carries
  the listed name, except the five rows that are unnamed in `eur2` (`Sequence::ExitApp`, `SystemEngine::startExit`, the two
  `nn::applet` getters, `NetworkErrorChecker::calc`) and `RacePage::initControl_WiFiVS`, which the second fact check explains.
- **The point of the document review**, with a new BSEQ parser written for this pass from the glossary layout:
  - `Page_CommonSystemDialog` is a child of exactly four roots: `MenuScene`, `RaceScene`, `TrophyScene` and `BootScene`. The
    first three map its `Error` (6) and `SimpleError` (7) to the codes of the table in Finding 10. The `BootScene` root
    (children `BootTask`, `Page_CommonSystemDialog`, `Page_Fader`; return default 1) has ten flow entries: `(-1, 15) -> (0, 8)`
    and nine from `BootTask`, none from index 1.
  - `ParallelSequence::updateState` (decompiled): a completed child without a matching entry is only marked done, and the default
    is used only when no child is still running; as Finding 5 says.
  - The `Common_SystemDialog` constructor sets `m_check_network_errors` (+0x350); `onPageEnter` sets it at its end whatever its
    value; `onPagePreStep` calls `NetworkErrorChecker::calc` while the page runs and the flag is set. So the check runs in
    `BootScene` too.
  - In `Root-Default.brs`, `BootScene` (child 1 of `RootMain`) is entered only from `BootTask` `_BootScene`, and `BootTask`
    (child 0) only from the enter entries of `RootMain`: `BootScene` runs only before `ProductMain`.
  - `NetworkErrorHandler::handleError` has five callers (`NetworkThread::calc_`, `NetworkSendPolicy::send` and three unnamed);
    whether one of them can run during the boot checks was not followed.
- **Scene roots.** The children of the nine retail `.bss` roots were listed again with the new parser; they agree with the
  overview's `### Scenes` and Finding 8, as corrected by the third fact check.
- **Flow graph.** Run again (`python -B`); the output is pixel-identical to `game_flow.png` (7717 x 18943, 37 panels).

#### What was changed

- Overview `### Network errors`: the statement that the scene ends with the dialog page is restricted to `MenuScene`, `RaceScene`
  and `TrophyScene`. For `BootScene` it now says that the page's end would not end the scene, and that whether a network error
  can happen that early was not followed.
- Finding 10, `The dialog page in a scene`: "only takes part in the flow" was replaced by what a completion does in each scene,
  with the `BootScene` flow list, the check still running there, and where `BootScene` is entered from. `Where the codes lead`
  says why `BootScene` is not in its table.
- Open questions: whether a network error can be pending while `BootScene` runs.

No change to the patch.

#### What remains uncertain

- The "Likely" and "Unknown" items of [Confidence](README.md#confidence), and the uncertain points of the earlier fact checks.
- Whether a network error can be pending during the boot checks, and, if so, what the boot task's later dialogs do once the
  dialog page has completed (`onPagePreStep` only acts while the page is running).

### Document review, fourth pass

Pass 3 again (WORKFLOW.md), fresh context, 2026-10-05, against WRITING.md, after the
fourth fact check. The whole document was read section by section as a reader new to the topic, with most attention on the
passages that the fourth fact check rewrote (overview `### Network errors`, Finding 10, Open questions). Neither the binary nor
the files were consulted.

#### What was changed

Overview:

- `### Scenes`: the system dialog was first named here without saying what it is; it now says it is the page in which the game
  opens its message windows, and `### Network errors` no longer repeats this. The boot task, used here before
  `### From boot to the menus and back` introduces it, is described in a few words with a link to that subsection.
- `### Network errors`: "Its flow list" (of `BootScene`) became "the flow list of its root", the term used everywhere else.

Part 2:

- Finding 6, `Parallel sequences`: the system dialog page was used before Finding 10 introduces it; it is now named
  (`Page_CommonSystemDialog`), described in a few words and linked to Finding 10. "Reports an error" became "reports a network
  error", which is the only way the page completes (Finding 10).
- Finding 10, `The dialog page in a scene`: "The check itself" referred to the network error check before the next subsection
  describes it; it now says so. The paragraph was rewrapped.
- The command paths of Finding 15 and `## How to verify` point to `final/scene-sequence-bseq/`, and the link in
  `mk7-llm-research/EMULATOR.md` to this document was updated the same way.

No claim was changed. Every in-document link resolves; addresses appear only in the glossary and `## How to verify`.

#### Found, not resolved

Nothing that looks factually wrong. The points left open are those of `## Confidence` and `## Open questions`.

Status set to `verified`; the folder moves to `final/scene-sequence-bseq/`.

### Template conventions update

2026-10-06, made at the user's request outside the pass procedure, to follow the template rules of
PATCHES.md and the naming rules of
WRITING.md that were added after the human review:

- The patch comments are one line, after the member, written for someone using the templates; the comments that said which
  functions set or read a member were removed from the patch, and those facts are in the glossary notes and the findings.
- Members that hold a state, kind or mode are typed with enums: `Common_SystemDialog::m_error_return_code` uses the existing
  `Common_SystemDialog::ReturnCode`; the new `NetworkEngine::ENetworkMode`, `NetworkErrorHandler::EErrorKind`,
  `NetworkErrorChecker::EState` and `BootTask::EState` hold only the values the findings describe.
- No name is provisional any more; the names did not change.
- The patch was regenerated on a fresh copy of `template/`; `git apply --check` and `mk7 --templates <copy> verify` pass for
  `EUR_REV2` and `USA_REV1`.