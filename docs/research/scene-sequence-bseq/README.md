# Scene and menu sequencing (BSEQ: `.brs` / `.bss`)

- Status: verified
- Asked: Let's research a new topic, this time about the game's scene and menu sequencing system. The game seems to not hardcode
  the linkage between diferent menus and scenes, instead it uses .bss and .brs files in the UI/common.szs file. Perform a general
  research task on this system, how menus are linked, how does the game know which classes to use, what are the enter and exit
  codes, fully document the bss and brs files and anything else you may find useful to modify those files. There is some research
  already in EveryFileExplorer and in https://github.com/mk7re/MK7-Binary-Scripts but only take that information as hints. The
  common szs files also seem to have some debug leftovers that may not be used by the final game.
- Base commit: b65de469294c2b1fe7e0b25cd66993bf9e0236b3
- Images: `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95); `dlp` as the source of names and for the comparisons of
  Findings 8, 9 and 12.

## Overview

The order in which Mario Kart 7 shows its screens (boot checks, title screen, menus, races, trophy ceremony, credits) is not
written in the code. It is data: 29 files inside `UI/common.szs` (the root file `Root-Default.brs`, one `.bss` file per scene
and an unused second root file), in a format whose files start with the letters `BSEQ`
([Finding 1](#1-the-files-and-how-they-are-loaded)). The code only
provides the building blocks (the screens, small invisible tasks, and a few ways of chaining them) and looks each one up **by
name**. This document describes the file format completely ([Finding 2](#2-file-format)), how the game turns a file into a
running flow, what the enter and return codes are, which parts of the files the retail game never uses, and what an edited file
has to respect ([Finding 14](#14-editing-the-files)). 20 of the 29 files are missing from the list of known file names that
the research tools use to name the files of an archive; their names were recovered, and all of them but one are debug, E3 demo
or test leftovers. A tool in this folder draws the whole flow as one image ([Finding 15](#15-the-flow-graph-tool)).

### Sections, codes and flows

A file is a list of **sections**. A section is one node of the flow: a screen, a task, or a group that runs other sections. Each
section has a number that identifies it, its **section ID**, and a name such as `Page_Title` or `Seq_Single`. The name is only a
label, except for the sections that start a scene, which are described [below](#scenes)
([Finding 3](#section-names-and-section-ids)).

Sections only talk to each other through **codes**. When a section is started, it receives an **enter code** that says why it was
started: `Next` when the player went forward, `Back` when they came back to it. When it ends, it reports a **return code** (what
the question calls an exit code) that says what happened: `Next00` for the first button of a menu, `Back` for the back button. A
third kind of code, the **mode**, selects a variant of a section. Each section lists the codes it accepts and reports in **code
tables**. Every code in a table is a small number with a name, and every table names one of its codes as the **default**, which
is used whenever a code is not in the table ([Finding 4](#4-enter-codes-return-codes-and-modes)).

A group of sections has a list of its children and a **flow list**, whose entries read "when child A ends with return code x,
start child B with enter code y". The group itself can be the source of an entry ("when the group is started with x, start B with
y") or its destination ("end the group with return code y"). The first entry that matches wins. A section never knows what comes
before or after it; only the flow list of its group does. This is why the same screen can be reused in several places, and why
the menus can be relinked by editing data ([Finding 5](#5-how-the-sequence-classes-use-the-flow-list)).

Every file has one group at the top that contains all its other sections, directly or through other groups: the **root** of the
file. The flow of a file starts and ends there.

Inside the files, codes are only numbers. Their names matter in two places. The first is the boundary with the program code: a
screen or task translates the name of its enter code into a value its program code understands, and translates its result back
into a name, which is then looked up in its return code table. So the names in the code tables of a screen or task must be the
ones its program code knows, while the numbers can be anything. The second is the very start of the game, where the code picks
the first enter code by name ([below](#from-boot-to-the-menus-and-back);
[Finding 4](#4-enter-codes-return-codes-and-modes)).

### Pages, tasks and sequences

There are three kinds of building blocks ([Finding 6](#6-the-building-blocks-in-use)):

- A **page** is a screen, or a part of the screen, that the player sees and acts on. It fades in when it starts and fades out
  when it ends. A page usually ends when the player presses one of its buttons, and reports the return code that the button was
  given; a few pages end in other ways, such as the title screen after a time without input
  ([Finding 13](#13-how-button-controls-complete-pages)). A menu page decides nothing about where that leads.
- A **task** has nothing on screen. It prepares or changes state, makes a decision, or waits for something. Some tasks act as
  routers: their return code depends on the state of the game, and so selects a branch of the flow.
- A **sequence** is a group of sections as described above: it runs other sections. There are four kinds:
  - a **serial** sequence shows one child at a time, like a menu wizard: when the child ends, its return code chooses the next
    child. Going back is just another flow entry. The same screen can appear several times in one serial sequence, so that it
    continues differently depending on how the player reached it;
  - a **parallel** sequence runs all its children at once, each on its own **layer**. Every child is started; the flow list only
    chooses their enter codes. The first child that ends with a code the flow list maps to an exit ends the whole group. Its pages
    fade in together;
  - a **cross fade** sequence is a serial sequence whose transitions can overlap, and a **delegate** sequence lets one child hand
    control to another and get it back afterwards. No file uses these two.

The program code of a page or task is chosen by a class name written in the file, looked up in a list of 76 page classes and
15 task classes. A name that is not in the list does not cause an error: the section silently becomes an empty page or task that
never ends, so a menu flow that reaches it stops there for good
([Finding 3](#3-from-blocks-to-objects-pools-layers-and-class-lookup)).

### Scenes

The game runs one **scene** at a time, and changing scene loads other data. Each scene is of one of seven **kinds**: boot, menu,
race, trophy, ending, "thank you" or demo. In the root file, a scene is a single section, a **scene proxy**. A proxy names the
kind of scene it needs, and several proxies can need the same kind: the course intro before a Grand Prix race (`DemoScene`), the
race itself (`RaceScene`), the title demo and the winning run all run in a race scene ([Finding 7](#retail-scene-proxies)). When a
proxy is started, the game switches to a scene of that kind and loads the file `<proxy name>-<mode name>.bss`, named after the
proxy section and its mode, for example `MenuScene-Default.bss`. That file holds the flow inside the scene and lists the scene's
**engines**, the parts of the game that each scene creates for itself: camera, rendering and characters. The proxy passes its
enter code on to the root of the `.bss` and reports the return code of that root as its own, by number: the code tables of the
proxy in the root file and those of the root of the `.bss` must use the same numbers
([Finding 7](#7-scenes-bss-files-and-engines)).

The root of each `.bss` is a parallel sequence. In the menu, race and trophy scenes it combines the parts of the screen that stay
for the whole scene with one serial sequence that holds the actual menus, race or ceremony. In the menu scene these parts are the
background, the timer, the top bar, the system dialog (the page in which the game opens its message windows), the screen fader
and two background tasks; in the race and trophy scenes only the system dialog and the screen fader, plus one task in the trophy
scene. The other scenes are simpler: the course intro, title demo, winning run, ending and thank-you scenes show a single page
next to the screen fader, and the boot scene runs the boot task, which does the save data and Mii checks of the start of the game
([below](#from-boot-to-the-menus-and-back)), next to the system dialog and the fader ([Finding 8](#the-scene-files)).

Everything the root file runs stays alive for the whole session, while a scene's `.bss`, engines and memory are discarded when the
scene ends. Only two things cross a scene change: the codes, through the root file, and data kept by the parts of the game that
never unload, such as the race settings and the menu state ([Finding 11](#11-what-a-scene-change-does)).

### From boot to the menus and back

The root file is loaded once, at boot, and started with one of two enter codes that the game picks
([Finding 8](#how-the-root-enter-code-is-decided)): `FromFriendList` when the game was started from the HOME Menu friend list
to join a friend, and `TitleScene` otherwise. Both go through a boot task that runs the save data and Mii checks and switches to
the boot scene (`BootScene`) when one of them needs to show something ([Finding 8](#boottask-and-bootscene)), and then into the
main loop, `ProductMain`. The Download Play child (the build of the game that a console without the game card downloads to join a
local multiplayer session) starts the same file with a third code, `DLC`, which skips the title screen and goes straight into
local multiplayer ([Finding 8](#dlc-is-the-download-play-child)).

`ProductMain` chains the scenes: menu, course intro, race, title demo, winning run, trophy, ending and thank-you.
Whenever a race, trophy or credits outcome leads back to the menus, it passes through a task, `ClearRaceInfoTask`, with the name
of the menu to reopen, for example `SingleTA_Chara` to reopen time trial character selection. The menu scene then opens its
menus at that point instead of at the title screen ([Finding 8](#productmain)).

`ProductMain` most likely never ends in the retail game: the only ways out of it lead to debug content that the retail game,
as far as the code and the tests show, never reaches ([Debug and unused content](#debug-and-unused-content)). The game ends
through a task that runs next to it for the whole session, `RootExitTask`: it waits until the system asks the application to
close, most likely when the player closes the game from the HOME Menu, and then ends the root of the root file, which ends the
whole flow ([Finding 12](#12-how-the-game-ends)).

### Network errors

The system dialog page is part of four scenes (`MenuScene`, `RaceScene`, `TrophyScene` and `BootScene`) for as long as the scene
runs, invisible until something opens a window in it. It only ends after a network error, with `Error` or `SimpleError`. In
`MenuScene`, `RaceScene` and `TrophyScene` the scene then ends with it. `SimpleError` is used when the other players have left an
online session, and the game goes back to the online menu. Every other network error ends with `Error`, which leads back to the
title screen. `BootScene` runs only during the boot checks, before the menus. The flow list of its root does not map either code
to an exit, so there the end of the page would not end the scene, which goes on until the boot task ends it; whether a network
error can happen that early was not followed. This was read from the code and the files, not tested in game
([Finding 10](#10-the-system-dialog-and-network-errors)).

### Debug and unused content

- `BootScene-Default.bss` is used by the retail game even though its name is missing from the list of known file names. The
  other 19 unnamed files (a debug menu, a debug race scene, a debug channel scene, per-developer test scenes, a sound test, a
  viewer, an E3 demo, two network tests, and an alternative root file) are never loaded ([Finding 9](#unreferenced-files)).
- The root file contains a whole debug menu branch that the retail game most likely cannot enter: the enter codes that would
  start it are never produced, and no path through the menu scene's flow returns the `Back` code that would lead to it
  ([Finding 9](#9-debug-and-unused-content)).
- The race page has debug set-ups that are compiled behind a switch fixed to "off": a debug end-of-race menu (Retry / Exit), and
  a pause menu whose quit button returns the debug return code `Debug_Exit`, which leads to the debug menu. One related path is
  not behind that switch. Every page that shows a race is set up for a **play mode**: single player, multiplayer, online, replay,
  or `Demo`. When the page of an ordinary race (in `RaceScene`) is set up for `Demo`, the quit button of its pause menu is given
  `Debug_Exit` as well. The retail game most likely never does this: `Demo` is only used for the course intro,
  the title demo and the winning run, which have pages of their own, and the course intro switches the mode back before the
  race starts. This was read in the code and watched in the running game for single-player play; multiplayer and online races
  were not run ([Finding 9](#no-race-of-racescene-runs-in-play-mode-3)).
- The debug files name page classes that do not exist in the retail game; they would be built as empty pages
  ([Finding 9](#unreferenced-files)).

### Editing the files

The rules an edited file must follow are in [Finding 14](#14-editing-the-files). In short:

- The root file is always `Root-Default.brs`. A new scene file needs a new proxy section in the root file, not a new kind of
  scene: the proxy only picks one of the seven kinds for it (a kind the game does not know gives the boot kind).
- The counts in the file header must be right: the total number of sections exactly, the others large enough. They size
  arrays that the game fills without checking, so a wrong count probably crashes the game (read from the code, not tested).
- Class names of pages and tasks must be names the game knows, and the code names in their tables must be the ones that class
  knows. The simplest way to reuse a screen is to copy its tables from a section that already uses it.
- Menus are relinked by editing flow entries. To reach the same screen with different follow-ups, list it several times in the
  sequence's children.
- The code numbers of a proxy and of the root of its `.bss` must stay equal.

### The flow graph tool

`bseq_flow_graph.py` reads the BSEQ files and draws every sequence and scene of the game as one image, `game_flow.png`, with one
panel per sequence and one arrow per flow entry ([Finding 15](#15-the-flow-graph-tool)). Everything specific to Mario Kart 7 (the
scene list, the registered classes, the root enter codes) comes from a separate profile file, so the tool can also be used for
other games that use the format.

## Glossary

Offsets of file structures are relative to the start of the structure. "The file" is the BSEQ file as loaded in memory.

### Sequence::BSEQ (size 0x38, template/Sequence/SequenceResource.hpp)

File header of a `.brs` / `.bss` file. Little endian.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_magic` | 0x00 | `u32` | existing | `BSEQ` |
| `m_sequence_id` | 0x04 | `u32` | existing | section ID of the file's root section |
| `m_root_mode_id` | 0x08 | `u16` | renamed | was `field_0x08`; mode ID the root is readied with |
| `field_0x0A` | 0x0A | `u16` | existing | always 4; no read found in `eur2` or `dlp` (Finding 2) |
| `field_0x0C` | 0x0C | `u16` | existing | always 1; no read found in `eur2` or `dlp` (Finding 2) |
| `m_num_sections` | 0x0E | `u16` | existing | capacity of the section array; see Finding 3 |
| `m_num_serial_sequences` | 0x10 | `u16` | existing | pool size |
| `m_num_cross_fade_sequences` | 0x12 | `u16` | existing | pool size |
| `m_num_parallel_sequences` | 0x14 | `u16` | existing | pool size, the root included |
| `m_num_delegate_sequences` | 0x16 | `u16` | existing | pool size |
| `m_num_scene_sequence_proxy` | 0x18 | `u16` | existing | pool size |
| `m_num_layers` | 0x1A | `u16` | existing | layers of every `ParallelSequence` of the file |
| `m_num_section_block` | 0x1C | `u16` | existing | entries of `m_section_block_offsets` |
| `m_num_engine_creator` | 0x1E | `u16` | existing | entries of the engine creator table |
| `field_0x20` | 0x20 | `u32` | existing | always 0; no read found |
| `field_0x24` | 0x24 | `u32` | existing | always 0; no read found |
| `m_first_section_block_offset` | 0x28 | `u32` | existing | always `0x34 + 4 * m_num_section_block`; no read found |
| `m_engine_creator_table_offset` | 0x2C | `u32` | existing | from the start of the file |
| `m_nametable_offset` | 0x30 | `u32` | existing | string table, from the start of the file |
| `m_section_block_offsets` | 0x34 | `u32[]` | renamed | was `m_section_block_array_offset` (a single `u32`); `m_num_section_block` offsets from the start of the file |

### Sequence::BSEQEngineCreatorTable (size 0x4, template/Sequence/SequenceResource.hpp)

One entry of the engine creator table.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_engine_creator_name_offset` | 0x00 | `u16` | existing | string: creator class name |
| `m_mode_name_offset` | 0x02 | `u16` | renamed | was `m_scene_name_offset`; string: engine mode ("Menu", "Race", ...) |

### Sequence::SequenceResource (size 0x14, template/Sequence/SequenceResource.hpp)

A loaded BSEQ file.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_bseq` | 0x04 | `BSEQ *` | existing | same value as `m_bseq_file_buffer` (0x00) |
| `m_string_table` | 0x08 | `char *` | renamed | was `m_stringTableBlock` (`char **`) |
| `m_engine_creator_table` | 0x0C | `BSEQEngineCreatorTable *` | renamed | was `m_engine_creator_table_offset` (`u32`); it is a resolved pointer |
| `m_section_blocks` | 0x10 | `SectionBlock **` | existing | `m_section_block_offsets` resolved |

### Sequence::SequenceResource::SectionBlock (size 0x14, template/Sequence/SequenceResource.hpp)

Common header of every section block.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_section_type` | 0x00 | `u8` | existing | `SectionType`: 0 page, 1 task, 2 data holder, 3 serial, 4 cross fade, 5 parallel, 6 delegate, 7 scene proxy, 8 brs root |
| `field_0x02` | 0x02 | `u16` | existing | always 0 (byte 0x01 too) |
| `m_sequence_id` | 0x04 | `u32` | existing | section ID |
| `m_section_block_name_offset` | 0x08 | `u16` | existing | string: section name |
| `m_enter_code_table_offset` | 0x0A | `u16` | existing | `NameTableBlock`, from the start of this block |
| `m_return_code_table_offset` | 0x0C | `u16` | existing | `NameTableBlock`, from the start of this block |
| `m_block_type` | 0x0E | `u16` | existing | `SectionBlockType`: 0/1 practical, 2 sequence, 3 cross fade, 4 scene proxy |
| `m_block_offset` | 0x10 | `u16` | existing | type-specific block, from the start of this block |

Bytes 0x12-0x13 are always 0 and are not read.

### Sequence::SequenceResource::NameTableBlock (size 0x4, followed by entries; template/Sequence/SequenceResource.hpp)

A code table (enter codes, return codes, modes): this header, then `m_num_entries` x `NameTableBlockEntry`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_num_entries` | 0x00 | `u16` | existing | |
| `m_default_id` | 0x02 | `u16` | renamed | was `m_field_0x02`; the fallback when a lookup fails |

### Sequence::SequenceResource::NameTableBlockEntry (size 0x4, template/Sequence/SequenceResource.hpp)

One code of a code table.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_id` | 0x00 | `u16` | renamed | was `m_index`; the code value |
| `m_name_offset` | 0x02 | `u16` | existing | string: the code's name |

### Type-specific blocks (template/Sequence/SequenceResource.hpp)

The block that `SectionBlock::m_block_offset` points to depends on `SectionBlock::m_block_type`. The patch removes
`SectionBlockDataHeader` (`field_0x00`, `m_class_name_offset`): its two fields do not mean the same thing in the four blocks that
embedded it.

#### Sequence::SequenceResource::PracticalSectionBlock (size 0x8)

Block of a page, task or data holder (block types 0 and 1).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_num_instances` | 0x00 | `u16` | new | objects created for this section; 1 in every file |
| `m_class_name_offset` | 0x02 | `u16` | new | string: C++ class name |
| `m_mode_table_offset` | 0x04 | `u16` | existing | `NameTableBlock` of modes, from the start of this block |

#### Sequence::SequenceResource::SequenceBlock (size 0x8)

Block of a serial, parallel or delegate sequence (block type 2).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mode_id` | 0x00 | `u16` | new | which mode this block implements |
| `m_mode_name_offset` | 0x02 | `u16` | new | string: mode name |
| `m_subsection_list_offset` | 0x04 | `u16` | existing | from the start of this block |
| `m_flow_list_offset` | 0x06 | `u16` | existing | from the start of this block |

#### Sequence::SequenceResource::CrossFadeSequenceBlock (size 0x8)

Block of a cross fade sequence (block type 3). Same layout as `SequenceBlock`; its flow list has 0xC-byte entries.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mode_id` | 0x00 | `u16` | new | as in `SequenceBlock` |
| `m_mode_name_offset` | 0x02 | `u16` | new | as in `SequenceBlock` |

#### Sequence::SequenceResource::SceneSequenceProxyBlock (size 0x8)

Block of a scene sequence proxy (block type 4).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mode_id` | 0x00 | `u16` | new | as in `SequenceBlock` |
| `m_mode_name_offset` | 0x02 | `u16` | new | string: mode name, used in the `.bss` file name |
| `m_scene_name_offset` | 0x04 | `u16` | existing | string: scene name ("Menu", "Race", ...) |

#### Sequence::SequenceResource::SubsectionListBlock (size 0x4, followed by entries) and SubsectionListBlockEntry (size 0x8)

The children of a sequence.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `SubsectionListBlock::m_num_entries` | 0x00 | `u16` | existing | followed by 2 bytes of padding, then the entries |
| `SubsectionListBlockEntry::m_sequence_id` | 0x00 | `u32` | existing | section ID of the child |
| `SubsectionListBlockEntry::m_mode_id` | 0x04 | `u16` | renamed | was `m_mode_name_item_offset`; mode ID of the child |

#### Sequence::SequenceResource::SequenceBlockFlowList (size 0x4, followed by entries) and SequenceBlockFlowListEntry (size 0x8)

The transitions of a sequence.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `SequenceBlockFlowList::m_num_entries` | 0x00 | `u16` | existing | followed by 2 bytes of padding, then the entries |
| `SequenceBlockFlowListEntry::m_src_subsection_index` | 0x00 | `s16` | renamed | was `m_prev_subsection_list_block_entry_index` (`u16`) |
| `SequenceBlockFlowListEntry::m_src_code` | 0x02 | `u16` | renamed | was `m_prev_return_code_item_index` |
| `SequenceBlockFlowListEntry::m_dst_subsection_index` | 0x04 | `s16` | renamed | was `m_next_subsection_list_block_entry_index` (`u16`) |
| `SequenceBlockFlowListEntry::m_dst_code` | 0x06 | `u16` | renamed | was `m_next_return_code_item_index` |

#### Sequence::SequenceResource::CrossFadeSequenceBlockFlowListEntry (size 0xC)

A flow entry of a cross fade block: a `SequenceBlockFlowListEntry` plus the transition kind.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_cross_fade_type` | 0x08 | `u16` | existing | only the low byte is read |

### Sequence::Section (size 0x34, template/Sequence/Section.hpp)

Base of every runtime section.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_resource` | 0x08 | `SequenceResource *` | existing | the file the section was created from |
| `m_parent_layer` | 0x0C | `SequenceLayer *` | existing | layer the section was last attached to; null until the first attach, and kept by `clearOuter` |
| `m_block` | 0x10 | `SectionBlock *` | existing | |
| `m_current_state` | 0x14 | `EState` | existing | |
| `m_next_state` | 0x15 | `EState` | existing | |
| `m_sequence_id` | 0x18 | `u32` | existing | section ID |
| `m_mode_id` | 0x1C | `u16` | renamed | was `m_mode_name_item_offset` |
| `m_enter_code_id` | 0x1E | `u16` | renamed | was `m_enter_code_item_offset` |
| `m_return_code_id` | 0x20 | `u16` | renamed | was `m_return_code_item_offset` |

### Sequence::PracticalSection (size 0x48, template/Sequence/PracticalSection.hpp)

Base of pages, tasks and data holders.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `mode` | 0x34 | `s32` | existing | the class's mode enum, from `convertMode` |
| `m_section_class_info` | 0x44 | `SectionClassInfoBase *` | existing | |

### Sequence::ExecutableSection (size 0x50, template/Sequence/ExecutableSection.hpp)

Base of pages and tasks (derives from `PracticalSection`).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_enter_code` | 0x48 | `s32` | existing | the class's enter code enum |
| `m_return_code` | 0x4C | `s32` | existing | the class's return code enum |

### Sequence::SectionClassManager (size 0x100, template/Sequence/SectionClassManager.hpp)

Name -> class registry for practical sections.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_task_info` | 0x04 | `SectionClassInfoBase` | existing | `DummySectionClassInfo<DummyTask>`, the fallback for tasks |
| `m_page_info` | 0x28 | `SectionClassInfoBase` | existing | `DummySectionClassInfo<DummyPage>` |
| `m_data_holder_info` | 0x4C | `SectionClassInfoBase` | existing | `DummySectionClassInfo<DummyDataHolder>` |
| `m_page_list` | 0x70 | `SectionClassInfoList` | existing | searched for section type 0 |
| `m_task_list` | 0xA0 | `SectionClassInfoList` | existing | searched for section type 1 |
| `m_data_holder_list` | 0xD0 | `SectionClassInfoList` | existing | searched for section type 2; empty |

### Sequence::SceneSequence (size 0x48, template/Sequence/SceneSequence.hpp)

A loaded `.brs` or `.bss` file with its sections.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_resource` | 0x00 | `SequenceResource` | existing | the file of the scene sequence |
| `m_section` | 0x18 | `Section *` | existing | the file's root section |
| `m_proxy` | 0x1C | `SceneSequenceProxy *` | existing | null for the `.brs` |

### Sequence::SceneSequenceProxy (size 0x60, template/Sequence/SceneSequenceProxy.hpp)

The section that switches to another scene and runs its `.bss`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_block` | 0x34 | `SceneSequenceProxyBlock *` | existing | |
| `m_scene_id` | 0x38 | `System::SceneID` | existing | |
| `m_scene_sequence` | 0x40 | `SceneSequence *` | existing | the `.bss` while the scene runs |

### Sequence::SequenceEngine (size 0xAC, template/Sequence/SequenceEngine.hpp)

The engine that runs the sequences.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_brs_scene_sequence` | 0x08 | `SceneSequence *` | existing | the `.brs` |

### Sequence::DashSequenceEngine (size 0x16F5C, template/Sequence/DashSequenceEngine.hpp)

MK7's sequence engine (derives from `SequenceEngine`).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_menu_data` | 0xC0 | `MenuData *` | existing | menu state; `BootTask` keeps its state there |
| `m_root_exit_task` | 0xCC | `RootExitTask *` | new | set by `RootExitTask::onTaskStart`, used by `Sequence::ExitApp` |
| `m_exit_app` | 0xD0 | `bool` | existing | set by `RootExitTask::exitApp` |

### Sequence::MenuData (size 0x978, template/Sequence/MenuData.hpp)

Menu state that lives in the root scene.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_common_system_dialog` | 0x1C | `Common_SystemDialog *` | existing | the system dialog page of the current scene |
| `m_time_attack_chart` | 0x28 | `TimeAttackChart *` | existing | set by the `TimeAttackChart` constructor |
| `m_boot_task_resume_state` | 0x60 | `BootTask::EState` | new | `BootTask` state to resume in the Boot scene; written by `BootTask::onTaskStep`, read by `BootTask::onTaskStart` |
| `m_boot_task_enter_code` | 0x61 | `u8` | existing | the enter code `BootTask` was first entered with |
| `m_race_info` | 0x74 | `RaceSys::CRaceInfo` | existing | the race settings the menus build; returned by `GetRaceInfo` |
| `m_demo_race_info` | 0x204 | `RaceSys::CRaceInfo` | existing | `setDemoMode` saves the race mode of `m_race_info` here |
| `m_selected_option` | 0x669 | `u8` | existing | tested by `UI::BaseMenuButtonControl::completeNext` (Finding 13) |

### Sequence::BootTask::EState (enum class : u8, template/Sequence/BootTask.hpp)

New; named by this research. The state of `BootTask::onTaskStep`, the type of `MenuData::m_boot_task_resume_state`. No
value is known yet: the states of `onTaskStep` were not followed (Finding 8).

### UI::BaseMenuButtonControl (size 0x23C, template/UI/BaseMenuButtonControl.hpp)

A menu button; pressing it completes its page.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_active_handlers` | 0x7C | `ActiveHandlersButton` | existing | which inputs the button reacts to |
| `m_selected_option_idx` | 0x210 | `s32` | existing | |
| `m_0x220` | 0x220 | `bool` | existing | set for the codes -2 and -4; meaning not traced |
| `m_page` | 0x22C | `Sequence::BaseMenuPage *` | existing | page the button completes |
| `m_return_code` | 0x230 | `s32` | existing | code reported when pressed; 0 by default |
| `m_on_complete_next_mode` | 0x234 | `s32` | existing | code used while the page's menu is open; -1 = none |

### Sequence::BasePage (size 0x26C, template/Sequence/BasePage.hpp)

Base of the menu, race and system pages.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_menu_state` | 0x8F | `u8` | existing | state of the page's overlay menu |

### Sequence::BaseRacePage (size 0x31FC, template/Sequence/BaseRacePage.hpp)

Base of the race page.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_race_mode` | 0x26C | `RaceSys::CRaceMode` | existing | play mode and rule mode the page is set up for |
| `m_pause_buttons` | 0x324 | `PauseButtons` | existing | the pause menu buttons; `PauseButtons::m_button_2` (+0x4) is its quit button |

### RaceSys::CRaceInfo (size 0x190, template/RaceSys/RaceInfo/CRaceInfo.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_race_mode` | 0x164 | `CRaceMode` | existing | copied into `BaseRacePage::m_race_mode` by `BaseRacePage::initCommon` |

### Sequence::MenuSingle_Mode (size 0x2E8, template/Sequence/MenuSingle_Mode.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_play_mode` | 0x2BC | `RaceSys::ERacePlayMode` | existing | set to 0 by `onPageEnter`, passed to `BasePage::setRaceMode` |

### RaceSys::CRaceMode (size 0xC, template/RaceSys/CRaceMode.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_play_mode` | 0x00 | `ERacePlayMode` | existing | 0 single player, 1 multiplayer, 2 online, 3 `Demo`, 4 replay |
| `m_rule_mode` | 0x04 | `ERaceRuleMode` | existing | Grand Prix, time trial, VS, battle |

### System::Scene (size 0x1E0, template/System/Scene.hpp)

A scene task.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_child_scene_id` | 0x1C0 | `SceneID` | existing | written by `changeChildScene` |
| `m_is_exiting_scene` | 0x1C1 | `bool` | existing | written by `exitScene` |
| `m_previous_scene` | 0x1C4 | `Scene *` | existing | scene that was current when this one was created |
| `m_scene_id` | 0x1D8 | `SceneID` | existing | which scene this is |

### System::SystemEngine (size 0xFC, template/System/SystemEngine.hpp)

The root engine that holds the system settings and handles sleep and application close requests.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_game_setting` | 0x40 | `GameSetting *` | existing | |
| `m_is_exit_started` | 0x78 | `bool` | new | set right after `Sequence::ExitApp` is called, so it is called once |
| `m_is_close_requested` | 0x79 | `bool` | new | set by `calcBeforeStructure` when one of the two `nn::applet` getters returns non-zero |
| `m_is_title_page_active` | 0x7C | `bool` | new | set by `MenuTitle::onPageEnter`, cleared by `MenuTitle::onPageComplete`; read by the sleep code; see Finding 8 |
| `m_title_sleep_flag` | 0x7D | `bool` | new | cleared by `MenuTitle::onPageEnter`, set under a condition in `MenuTitle::onPageComplete`; read by `gpuSleepProc` |

### System::GameSetting (size 0x1050, template/System/GameSetting.hpp)

System settings read at boot.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_is_from_friend_list` | 0x1038 | `bool` | existing | set at boot, picks the root enter code (Finding 8) |
| `m_friend_key` | 0x1040 | `nnfriendsFriendKey` | existing | the friend the game was launched for |

### Sequence::Common_SystemDialog (size 0x6C8, template/Sequence/Common_SystemDialog.hpp)

The system dialog page (Finding 10).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_error_return_code` | 0x340 | `ReturnCode` | renamed | was `s32 m_0x340`; the existing `Common_SystemDialog::ReturnCode`: 1 `ERROR` or 2 `SIMPLE_ERROR`; set to 1 by `onPageEnter`, chosen by `NetworkErrorChecker::calc` |
| `m_check_network_errors` | 0x350 | `bool` | existing | the checker runs only while it is set; also written by other pages through `MenuData::m_common_system_dialog` |
| `m_network_error_checker` | 0x354 | `NetworkErrorChecker` | existing | |

### Sequence::NetworkErrorChecker (size 0x24, template/Sequence/NetworkErrorChecker.hpp)

The state machine that handles a network error for the system dialog (Finding 10).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_error_handler` | 0x00 | `Net::NetworkErrorHandler *` | new | `NetworkEngine::m_network_error_handler`, copied by `Common_SystemDialog::onPageEnter` |
| `m_state` | 0x08 | `EState` | new | state of `calc` |
| `m_common_system_dialog` | 0x10 | `Common_SystemDialog *` | existing | |
| `m_error_kind` | 0x14 | `Net::NetworkErrorHandler::EErrorKind` | new | copy of `NetworkErrorHandler::m_error_kind`, made by `calc` |
| `m_network_mode` | 0x1C | `Net::NetworkEngine::ENetworkMode` | new | copy of `NetworkEngine::m_network_mode`, made by `startDisconnect_` |

#### Sequence::NetworkErrorChecker::EState (enum class : s32)

New; named by this research. The states of `NetworkErrorChecker::calc`; only those described in Finding 10 are listed.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `WATCH` | new | waits for a network error |
| 7 | `SELECT_RETURN_CODE` | new | chooses `Common_SystemDialog::m_error_return_code` once the dialog is closed |
| 9 | `DONE` | new | `calc` returns true |

### Net::NetworkEngine (size 0x598, template/Net/NetworkEngine.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_network_mode` | 0x134 | `ENetworkMode` | new | read by `checkStandAlone` and `Sequence::NetworkErrorChecker::startDisconnect_` |
| `m_network_error_handler` | 0x290 | `NetworkErrorHandler *` | existing | |

#### Net::NetworkEngine::ENetworkMode (enum class : s32)

New; named by this research.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 1 | `WIFI` | new | online play: `checkStandAlone` then asks `WifiMatchingManager::checkSessionIsOrphan` |

### Net::NetworkErrorHandler (size 0x4C, template/Net/NetworkErrorHandler.hpp)

The record of the pending network error. The patch corrects the size from 0x40 to 0x4C, the size that
`NetworkEngine::createBeforeStructure` allocates (`mov r0, #0x4c` before the allocation).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_error_code` | 0x38 | `u32` | existing | |
| `m_error_kind` | 0x40 | `EErrorKind` | new | kind of the pending error |

#### Net::NetworkErrorHandler::EErrorKind (enum class : s32)

New; named by this research.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `NONE` | new | no error pending (when `m_error_code` is below 3) |
| 5 | `STAND_ALONE` | new | written by `NetworkEngine::checkStandAlone`: every other player left the session |

### Functions

Names are ported from `dlp` (existing) unless the Status column says otherwise. Virtual functions that the text names only as a
slot of every page or task (`onTaskStep`, `isSyncFadein`, `completePage`, ...) are listed only where a specific override is
discussed.

| Name | Address (eur2) | Status | Note |
| --- | --- | --- | --- |
| `Sequence::SequenceResource::create` | 0x0049FDA4 | existing | builds the file name, loads it |
| `Sequence::SequenceResource::searchSectionType` | 0x0051D728 | existing | |
| `Sequence::SequenceResource::searchSequenceBlock` | 0x0051D7F4 | existing | |
| `Sequence::SequenceResource::searchPracticalSectionBlock` | 0x0051D8C0 | existing | |
| `Sequence::SequenceResource::NameTableBlock::searchItem(const SafeString &, ...)` | 0x0051D5B8 | existing | lookup by name |
| `Sequence::SequenceResource::NameTableBlock::searchItem(u16)` | 0x0051D6C4 | existing | lookup by ID |
| `Sequence::SequenceResource::SectionBlock::getSequence` | 0x0051D524 | existing | |
| `Sequence::SequenceResource::SectionBlock::getEnterCodeTable` | 0x0051D53C | existing | |
| `Sequence::SequenceResource::SectionBlock::getReturnCodeTable` | 0x0051D548 | existing | |
| `Sequence::SequenceResource::SectionBlock::getPracticalSection` | 0x0051D554 | existing | |
| `Sequence::SequenceResource::SectionBlock::getCrossFadeSequence` | 0x0051D570 | existing | |
| `Sequence::SequenceResource::SectionBlock::getSceneSequenceProxy` | 0x0051D588 | existing | |
| `Sequence::SequenceResource::SubsectionListBlock::getItem` | 0x0051D7E8 | existing | |
| `UI::LoadUI` | 0x00177C80 | existing | |
| `Sequence::SectionDirector::create` | 0x0049481C | existing | |
| `Sequence::SectionDirector::findAttachedDisableSection` | 0x004946AC | existing | |
| `Sequence::SectionDirector::attachedDisableSectionFinder` | 0x00494758 | existing | |
| `Sequence::SectionClassManager::SectionClassManager` | 0x004BA3FC | existing | sets the three dummy class infos |
| `Sequence::SectionClassManager::constructSection` | 0x004B9BD0 | existing | |
| `Sequence::SectionClassManager::SectionClassInfoList::compareByName` | 0x004B9D04 | existing | the overload that takes a name |
| `Sequence::DashSectionClassManager::definePageClassInfoList` | 0x004C4D5C | existing | 76 classes |
| `Sequence::DashSectionClassManager::defineTaskClassInfoList` | 0x004C5CD0 | existing | 15 classes |
| `Sequence::DashSectionClassManager::defineDataHolderClassInfoList` | 0x004C5FE0 | existing | empty (`bx lr`) |
| `Sequence::ExecutableSectionClassInfo<Sequence::BootTask>::getClassName` | 0x005E67E4 | existing | returns "BootTask"; one of the 91 `getClassName` |
| `Sequence::DummySectionClassInfo<Sequence::DummyPage>::constructSection` | 0x005D961C | existing | |
| `Sequence::DummyPage::onPageEnter` | 0x004DCBBC | existing | `bx lr`, its only override |
| `Sequence::DummyTask::onTaskStart` | 0x004DCBD8 | existing | returns -1 |
| `Sequence::DummyTask::onTaskStep` | 0x004DCBD0 | existing | returns -1 |
| `Sequence::DummyDataHolder::onEnableData` | 0x004884AC | existing | `bx lr` |
| `Sequence::DataHolder::enter` | 0x004D2738 | existing | |
| `Sequence::DataHolder::start` | 0x0046F16C | existing | |
| `Sequence::DataHolder::step` | 0x0046F160 | existing | empty |
| `Sequence::Section::createForPracticalSection` | 0x004D28E4 | existing | |
| `Sequence::Section::readyOuter` | 0x004D25F8 | existing | |
| `Sequence::Section::enterOuter` | 0x004D2550 | existing | |
| `Sequence::Section::completeOuter` | 0x004D2748 | existing | |
| `Sequence::Section::reenterOuter` | 0x004D2700 | existing | |
| `Sequence::Section::updateStateOuter` | 0x004D277C | existing | |
| `Sequence::Section::clearOuter` | 0x004D24A8 | existing | |
| `Sequence::Section::getModeName` | 0x00521B94 | existing | |
| `Sequence::Section::getEnterCodeName` | 0x00521C98 | existing | |
| `Sequence::Section::getSectionName` | 0x00521C64 | existing | |
| `Sequence::SequenceLayer::ready` | 0x004D258C | existing | |
| `Sequence::SequenceLayer::attachSection` | 0x00484DD0 | existing | |
| `Sequence::LayeredSequence::createLayer` | 0x004886E4 | existing | |
| `Sequence::SequenceEngine::init` | 0x004874B8 | existing | |
| `Sequence::SequenceEngine::createRootSequence` | 0x00487208 | existing | |
| `Sequence::SequenceEngine::getDefaultRootSceneName` | 0x0051B928 | existing | |
| `Sequence::SequenceEngine::getDefaultRootSceneMode` | 0x0051B908 | existing | |
| `Sequence::SequenceEngine::getDefaultRootSceneEnterCode` | 0x0051B948 | existing | `dlp`: 0x004BD768 |
| `Sequence::SequenceEngine::sceneStart` | 0x00484A90 | existing | |
| `Sequence::SequenceEngine::sceneFinish` | 0x00484AB0 | existing | |
| `Sequence::SceneSequence::create` | 0x00484C6C | existing | |
| `Sequence::SceneSequence::createSections` | 0x00484B78 | existing | |
| `Sequence::SceneSequence::createEngines` | 0x00484B24 | existing | |
| `Sequence::SceneSequence::init` | 0x004D2510 | existing | |
| `Sequence::SceneSequence::destroy` | 0x00484CA0 | existing | |
| `Sequence::SceneSequenceProxy::ready` | 0x004AD8B0 | existing | |
| `Sequence::SceneSequenceProxy::sceneStart` | 0x004AD4CC | existing | |
| `Sequence::SceneSequenceProxy::updateState` | 0x004AD594 | existing | |
| `Sequence::SceneSequenceProxy::step` | 0x004AD784 | existing | |
| `Sequence::SceneSequenceProxy::finish` | 0x004D26C8 | existing | |
| `Sequence::SceneSequenceProxy::sceneFinish` | 0x004AD558 | existing | |
| `Sequence::DashSceneIDConverter::defineSceneIDDictionary` | 0x004BAB64 | existing | |
| `Sequence::SceneIDConverter::initDictionary` | 0x0049FCB8 | existing | |
| `Sequence::SceneIDConverter::convertToSceneID` | 0x0051D4E4 | existing | |
| `Sequence::EngineCreatorManager::createEngines` | 0x004BACA4 | existing | |
| `Sequence::DashEngineCreatorManager::defineEngineCreatorList` | 0x00520990 | existing | |
| `Sequence::CameraEngineCreator::convertMode` | 0x0051E7BC | existing | |
| `Sequence::RenderEngineCreator::convertMode` | 0x0051F44C | existing | same list as the camera creator |
| `Sequence::CharacterEngineCreator::convertMode` | 0x0052024C | existing | same list as the camera creator |
| `Sequence::SerialSequence::enter` | 0x00487BA0 | existing | |
| `Sequence::SerialSequence::updateState` | 0x00487884 | existing | |
| `Sequence::SerialSequence::reenter` | 0x00487D04 | existing | |
| `Sequence::ParallelSequence::create` | 0x0049F780 | existing | |
| `Sequence::ParallelSequence::ready` | 0x0049F66C | existing | |
| `Sequence::ParallelSequence::enter` | 0x0049F594 | existing | |
| `Sequence::ParallelSequence::updateState` | 0x0049F2E4 | existing | |
| `Sequence::ParallelSequence::finish` | 0x0049F80C | existing | cancels running children, finishes the others |
| `Sequence::CrossFadeSequence::enter` | 0x004A1364 | existing | |
| `Sequence::CrossFadeSequence::updateState` | 0x004A0E10 | existing | |
| `Sequence::CrossFadeSequence::changeSubsection` | 0x004A11C4 | existing | |
| `Sequence::DelegateSequence::ready` | 0x004972CC | existing | |
| `Sequence::DelegateSequence::enter` | 0x0049720C | existing | |
| `Sequence::DelegateSequence::updateState` | 0x00496D90 | existing | |
| `Sequence::DataHolder::isCompletable` | 0x0051A35C | existing | returns 1 |
| `Sequence::SerialSequence::isCompletable` | 0x0051BA84 | existing | returns 1 |
| `Sequence::DelegateSequence::isCompletable` | 0x0051CA00 | existing | returns 1 |
| `Sequence::ParallelSequence::isCompletable` | 0x0051D44C | existing | returns 1 |
| `Sequence::CrossFadeSequence::isCompletable` | 0x0051DB28 | existing | returns 1 |
| `Sequence::ExecutableSection::isCompletable` | 0x0051DBC0 | existing | returns 1 |
| `Sequence::SceneSequenceProxy::isCompletable` | 0x0051E724 | existing | returns 1 |
| `Sequence::ExecutableSection::enter` | 0x004A177C | existing | |
| `Sequence::ExecutableSection::setReturnCodeEnum` | 0x004A16D8 | existing | |
| `Sequence::PracticalSection::ready` | 0x0049F9EC | existing | |
| `Sequence::Page::create` | 0x004CFF34 | existing | |
| `Sequence::Page::enter` | 0x004CFCD4 | existing | |
| `Sequence::Page::step` | 0x004CFB68 | existing | |
| `Sequence::Page::finish` | 0x004CFFBC | existing | |
| `Sequence::Page::completePage` | 0x004CF9AC | existing | |
| `Sequence::Page::isSyncFadein` | 0x005219C4 | existing | returns 1 |
| `Sequence::InstantTask::start` | 0x004A16B0 | existing | |
| `Sequence::InstantTask::reenter` | 0x00471DA0 | existing | |
| `Sequence::InstantTask::isSyncFadein` | 0x0051A59C | existing | returns 0 |
| `Sequence::LastingTask::start` | 0x00471FD4 | existing | |
| `Sequence::LastingTask::step` | 0x00471F0C | existing | |
| `Sequence::LastingTask::isSyncFadein` | 0x0051A5BC | existing | returns 0 |
| `Sequence::BootTask::convertEnterCodeImpl` | 0x004D5394 | existing | |
| `Sequence::BootTask::convertReturnCodeImpl` | 0x004D5644 | existing | |
| `Sequence::BootTask::onTaskStart` | 0x004D51A4 | existing | |
| `Sequence::BootTask::onTaskStep` | 0x004D56A0 | existing | |
| `Sequence::ClearRaceInfoTask::onTaskMain` | 0x004A0068 | existing | |
| `Sequence::ClearRaceInfoTask::convertEnterCodeImpl` | 0x004A05E4 | existing | |
| `Sequence::ClearRaceInfoTask::convertReturnCodeImpl` | 0x004A09E8 | existing | |
| `Sequence::MMenCheckPage::onPageEnter` | 0x004826DC | existing | |
| `Sequence::MMenCheckPage::onPagePreStep` | 0x004826F0 | existing | |
| `Sequence::MMenCheckPage::completePage` | 0x004D315C | existing | falls into `BasePage::completeScene` |
| `Sequence::MenuTitle::initControl` | 0x004DDE98 | existing | |
| `Sequence::MenuTitle::onPageEnter` | 0x004DE714 | existing | |
| `Sequence::MenuTitle::onPagePreStep` | 0x004DE7C0 | existing | |
| `Sequence::MenuTitle::onPageComplete` | 0x004DEAE0 | existing | also calls the `applySetting_TitleDemo_*` functions |
| `Sequence::RootExitTask::onTaskStart` | 0x00480518 | existing | |
| `Sequence::RootExitTask::onTaskStep` | 0x004804C0 | existing | |
| `Sequence::RootExitTask::exitApp` | 0x004806E0 | existing | |
| `Sequence::ExitApp` | 0x004D2428 | new | unnamed in `eur2`; the name of `dlp` 0x00478E68, which has the same body |
| `Sequence::IsSaveWorking` | 0x00482688 | existing | |
| `System::SystemEngine::createBeforeStructure` | 0x00442A34 | existing | calls `GameSetting::init` |
| `System::SystemEngine::calcBeforeStructure` | 0x00442740 | existing | |
| `System::SystemEngine::startExit` | 0x00443028 | new | unnamed in `eur2`; `dlp` 0x004073A8 has the same body with the flag at another offset |
| `nn::applet::CTR::detail::GetOrderToCloseState` | 0x001021B8 | new | unnamed in `eur2`; the `dlp` function (0x001041B8) called at the same place of `calcBeforeStructure` |
| `nn::applet::CTR::IsReceivedWakeupByCancel` | 0x00101F80 | new | unnamed in `eur2`; the `dlp` function (0x0010382C) called at the same place of `calcBeforeStructure` |
| `System::ProjectGameFramework::gpuSleepProc` | 0x00450FD4 | existing | |
| `System::SleepChecker::check` | 0x00441EC8 | existing | |
| `System::GameSetting::init` | 0x0043FC8C | existing | |
| `System::GameSetting::getSimpleAddress` | 0x005153AC | existing | |
| `System::GetSaveDataManager` | 0x0044F868 | existing | returns the save data manager of the system engine |
| `nn::friends::CTR::detail::IsFromFriendList` | 0x002391F8 | existing | |
| `Net::NetworkEngine::sceneExit` | 0x00293B08 | existing | clears `m_is_from_friend_list` |
| `Net::NetworkEngine::sceneStart` | 0x002A9068 | existing | |
| `Net::NetworkEngine::createBeforeStructure` | 0x00291974 | existing | allocates the `NetworkErrorHandler` |
| `Net::NetworkEngine::checkStandAlone` | 0x0028F930 | existing | sets error kind 5 |
| `Net::NetworkEngine::resetError` | 0x0028EF88 | existing | |
| `Net::NetworkErrorHandler::handleError` | 0x0029DB54 | existing | writes up to +0x4B |
| `Net::NetworkSelectMenuProcess::disconnectNetwork` | 0x002A6364 | existing | |
| `Net::NetworkSelectMenuProcess::disconnectNetworkAll` | 0x002A6C40 | existing | |
| `Net::WifiMatchingManager::checkSessionIsOrphan` | 0x002A04EC | existing | |
| `Sequence::Common_SystemDialog::Common_SystemDialog` | 0x004B0FB0 | existing | |
| `Sequence::Common_SystemDialog::onPageEnter` | 0x004AE5AC | existing | |
| `Sequence::Common_SystemDialog::onPagePreStep` | 0x004AF184 | existing | |
| `Sequence::Common_SystemDialog::convertReturnCodeImpl` | 0x004B01AC | existing | 0 `Normal`, 1 `Error`, 2 `SimpleError` |
| `Sequence::Common_SystemDialog::onMenuEnter` | 0x004AE010 | existing | |
| `Sequence::Common_SystemDialog::fadeInWindow_` | 0x004AE6E0 | existing | |
| `Sequence::Common_SystemDialog::startSystemWindow` | 0x004AFA08 | existing | |
| `Sequence::OpenDialog` | 0x0046FB70 | existing | |
| `Sequence::NetworkErrorChecker::calc` | 0x004B94D0 | existing | declared in the template, unnamed in the `eur2` port; same structure as `dlp` `calc` at 0x004635B8 |
| `Sequence::NetworkErrorChecker::startDisconnect_` | 0x004B93EC | existing | |
| `Sequence::RacePage::initControl` | 0x004D932C | existing | dispatches on the play and rule mode |
| `Sequence::RacePage::initControl_WiFiVS` | 0x004D947C | new | unnamed in `eur2`; `dlp` 0x0047F484 has the same calls and constants |
| `Sequence::RacePage::initControl_MultiGP` | 0x004D95CC | existing | |
| `Sequence::RacePage::initControl_MultiVS` | 0x004D9758 | existing | |
| `Sequence::RacePage::initControl_SingleGP` | 0x004D99C4 | existing | `dlp`: 0x0047F9BC |
| `Sequence::RacePage::initControl_WiFiBattle` | 0x004D9AE8 | existing | |
| `Sequence::RacePage::initControl_MultiBattle` | 0x004D9C64 | existing | |
| `Sequence::RacePage::initControl_SingleBattle` | 0x004D9F20 | existing | |
| `Sequence::RacePage::initControl_SingleTimeAttack` | 0x004DA1A8 | existing | |
| `Sequence::RacePage::genPause` | 0x004DA734 | existing | |
| `Sequence::RacePage::genNextDebug` | 0x004D72B8 | existing | debug end-of-race menu |
| `Sequence::RacePage::genResult` | 0x004DB9C8 | existing | |
| `Sequence::RacePage::genResultTeam` | 0x004D7FF4 | existing | |
| `Sequence::RacePage::genResultBT` | 0x004D6940 | existing | |
| `Sequence::RacePage::genResultTA` | 0x004D6B88 | existing | |
| `Sequence::RacePage::genResultCommu` | 0x004D8C10 | existing | |
| `Sequence::RacePage::genResultWiFi` | 0x004D89C0 | existing | |
| `Sequence::RacePage::genRaceGP` | 0x004DB918 | existing | first call of `initControl_SingleGP` |
| `Sequence::RacePage::genNext` | 0x004DA34C | existing | |
| `Sequence::RacePage::genNextCommunity` | 0x004D908C | existing | |
| `Sequence::RacePage::genNextGP` | 0x004DB1B8 | existing | |
| `Sequence::RacePage::genNextTA` | 0x004DB584 | existing | |
| `Sequence::GetRaceInfo` | 0x00471CC0 | existing | returns `MenuData::m_race_info` |
| `Sequence::BasePage::setRaceMode` | 0x004D2CF8 | existing | writes the race mode of `MenuData::m_race_info` |
| `Sequence::BasePage::setReplayMode` | 0x004D3320 | existing | play mode 0 or 4 |
| `Sequence::BasePage::setDemoMode` | 0x004D2C24 | existing | saves the mode in `m_demo_race_info`, sets play mode 3, rule mode 5 |
| `Sequence::BaseMenuPage::applySetting_GP` | 0x00472850 | existing | calls `setDemoMode` |
| `Sequence::BaseMenuPage::applySetting_TitleDemo_Race` | 0x00473A4C | existing | play mode 3, rule mode 6 |
| `Sequence::BaseMenuPage::applySetting_TitleDemo_BattleCoin` | 0x00473BD0 | existing | |
| `Sequence::BaseMenuPage::applySetting_TitleDemo_BattleBalloon` | 0x00473D08 | existing | |
| `Sequence::BaseMenuPage::applySetting_WinningRun` | 0x00473778 | existing | play mode 3, rule mode 4 |
| `Sequence::BaseRacePage::complete` | 0x0047CEC4 | existing | calls `setReplayMode` and `setDemoMode` |
| `Sequence::DemoPage::onPageComplete` | 0x004D620C | existing | restores the saved mode with `setRaceMode` |
| `Sequence::WinningRunPage::onPageComplete` | 0x00488248 | existing | |
| `Sequence::WinningRunSelectTask::onTaskMain` | 0x004C133C | existing | calls `applySetting_WinningRun` |
| `Sequence::ClearRaceInfoTask::clearRaceInfo` | 0x004A01B0 | existing | |
| `Sequence::MenuSingle_Mode::onPageEnter` | 0x00492138 | existing | |
| `Sequence::MenuSingle_Mode::buttonHandler_OK` | 0x00492310 | existing | |
| `Sequence::MenuMulti_Mode::onPageEnterCore` | 0x00486028 | existing | |
| `RaceSys::CRaceInfo::updateRaceModeFlag` | 0x00469C90 | existing | called by the three setters after each write |
| `Sequence::MenuNetworkApplyTask::updateBattleMode_` | 0x004BD75C | existing | |
| `Net::CommunityMgr::applyGameMode` | 0x00502598 | existing | |
| `Sequence::BaseRacePage::convertReturnCodeImpl` | 0x0047B11C | existing | |
| `Sequence::BaseRacePage::calcRace` | 0x0047C468 | existing | |
| `Sequence::BaseRacePage::initCommon` | 0x004747F8 | existing | |
| `Sequence::BaseRacePage::onPageFadeout` | 0x00484610 | existing | |
| `Sequence::TrophyPage::onPagePreStep` | 0x00470438 | existing | |
| `Sequence::EndingPage::onPagePreStep` | 0x0046F770 | existing | weak port (0.06), but it fills the `onPagePreStep` slot of the vtable whose other overrides are `EndingPage`'s |
| `System::SceneManager::changeChildScene` | 0x00441EAC | existing | |
| `System::SceneManager::exitScene` | 0x00441EB8 | existing | |
| `System::Scene::Scene` | 0x00109728 | existing | |
| `System::Scene::~Scene` | 0x0045857C | existing | |
| `System::Scene::calc` | 0x00457F50 | existing | |
| `System::Scene::prepare` | 0x004583A0 | existing | |
| `System::Scene::exit` | 0x00458044 | existing | |
| `System::Scene::createDrawHeap` | 0x00457EE0 | existing | |
| `System::GameScene::prepare` | 0x0045B76C | existing | |
| `System::GameScene::exit` | 0x0045B5E8 | existing | |
| `System::GameScene::callRootEngine` | 0x0045B338 | existing | |
| `System::RootScene::sceneCalc` | 0x0045CAEC | existing | runs the sequence engine |
| `System::ThreadManager::safetyQuit` | 0x00445654 | existing | |
| `System::ResourceLoader::createList` | 0x00447D3C | existing | |
| `System::ResourceLoader::destroyList` | 0x004484F4 | existing | |
| `Object::Actor::calcOuter` | 0x004209A4 | existing | |
| `sead::TaskBase::requestPush` | 0x00328EDC | existing | |
| `sead::TaskBase::requestPop` | 0x00326978 | existing | |
| `Sound::SndEngine::isSceneFinishedFadeOut` | 0x003D93A0 | existing | |
| `UI::BaseMenuButtonControl::BaseMenuButtonControl` | 0x00173390 | existing | |
| `UI::BaseMenuButtonControl::completeNext` | 0x00170DB0 | existing | completes the page with the button's code |
| `UI::BaseMenuButtonControl::touchHandlerUp` | 0x00170F4C | existing | ends in `completeNext` |
| `UI::BaseMenuButtonControl::keyHandlerCommon` | 0x00171068 | existing | ends in `completeNext` |
| `UI::BaseMenuButtonControl::keyHandlerCursorA` | 0x00171214 | existing | ends in `completeNext` |
| `UI::BackButtonT::onKeyHandlerB` | 0x00170DA8 | existing | B key -> `keyHandlerCommon` |
| `UI::ManipulatorManager::clear` | 0x00168414 | existing | |
| `Sequence::BasePage::convertReturnCodeImpl` | 0x004D4234 | existing | 0..7 `Next00`..`Next07`, 8 `Back` |
| `Sequence::BasePage::completeNext` | 0x004D2ECC | existing | |
| `Sequence::BasePage::completeScene` | 0x004D3160 | existing | |
| `Sequence::BasePage::openMenu` | 0x004D4970 | existing | |
| `Sequence::BaseMenuPage::getBackReturnCode` | 0x00473308 | existing | returns 8 |
| `Sequence::BaseMenuPage::getBackEnterCode` | 0x00472CFC | existing | returns 1 |
| `Sequence::TimeAttackChart::TimeAttackChart` | 0x004967D0 | existing | |
| `Sequence::TimeAttackChart::onPageCourseEnter` | 0x00495C54 | existing | |
| `Sequence::TimeAttackChart::setCourseName` | 0x00495C28 | existing | |
| `Sequence::TimeAttackChart::changeOut` | 0x00496570 | existing | |
| `Sequence::TimeAttackChart::onPageOut` | 0x00141B70 | existing | |
| `Sequence::TimeAttackChart::onPageFromGhost` | 0x004963E4 | existing | |
| `Sequence::TimeAttackChart::selectGhost` | 0x004958B0 | existing | |
| `Sequence::MenuSingle_Course::onPageEnter` | 0x004A6D34 | existing | |
| `Sequence::MenuSingle_Course::buttonHandler_SelectOn` | 0x004A73F4 | existing | |
| `Sequence::MenuSingle_Course::onPageComplete` | 0x004A70D4 | existing | |
| `Sequence::MenuSingle_Ghost::onPageFadeout` | 0x0049AE9C | existing | |
| `Sequence::GhostList::select` | 0x004DD9B0 | existing | |

### Data

| Name | Address (eur2) | Note |
| --- | --- | --- |
| `Sequence::SequenceEngine` vtable | 0x006469FC | `getDefaultRootSceneName`, `Mode`, `EnterCode` at +0x74, +0x78, +0x7C |
| `Sequence::DashSequenceEngine` vtable | 0x00648FA4 | the same three slots hold the `SequenceEngine` functions |
| `Sequence::DummyPage` vtable | 0x0064DD14 | |
| `Sequence::DummySectionClassInfo<Sequence::DummyTask>` vtable | 0x0064AE6C | |
| `Sequence::DummySectionClassInfo<Sequence::DummyPage>` vtable | 0x0064AE44 | |
| `Sequence::DummySectionClassInfo<Sequence::DummyDataHolder>` vtable | 0x0064AE1C | |
| `Sequence::ExecutableSectionClassInfo<Sequence::BootTask>` vtable | 0x0064CFEC | first class info of `defineTaskClassInfoList` |

## Findings

### Sources and method

- Code: `eur2`, read with `mk7 dis` and `mk7 decomp`, and with a full disassembly of the code made with devkitARM's objdump for the
  scans of Findings 2, 9, 10 and 12. `dlp` only as the source of names and for the comparisons of Findings 8, 9 and 12.
- Data: the 29 BSEQ files of `eur2`, all inside `rom:/UI/common.szs`. Nothing in `pat1:` and nothing in any other archive starts
  with the `BSEQ` magic (every extracted file was scanned). The files were parsed with throw-away scripts to check the layout
  and list what they contain; the graph tool `bseq_flow_graph.py` in this folder parses them the same way (Finding 15).
- Running game: `eur2` in Azahar, driven by `mk7 emu` and its Python library, with gdb breakpoints and watchpoints, for the play
  mode of the race pages (Finding 9).
- Hints: `MarioKart/MK7/BSEQ.cs` of EveryFileExplorer and `MK7_BSEQ_analyser.py` of MK7-Binary-Scripts (cloned to the
  scratchpad, not copied here). Where they disagree with what the code does, see Finding 16.

#### Terms

- A **section** is one node of the sequence graph: a page, a task, a data holder (a section meant to keep data alive, unused in
  MK7; Finding 6), together the **practical** sections, whose block names a C++ class; or a sequence that runs other sections
  (serial, cross fade, parallel, delegate, scene proxy). A section is identified by its **section ID** (a `u32`).
- The children of a sequence are its **subsections**, listed in its subsection list. A flow entry refers to a child by its
  position in that list, the **subsection index**, not by its section ID.
- The **root** of a file is the section whose ID the file header gives; it contains all the others.
- A **code** is a `u16` ID that names an enter code, a return code or a mode; every code has a name string in the file, and an ID
  is only meaningful inside the table it belongs to.
- A **layer** (`SequenceLayer`) is a slot of a parallel or delegate sequence in which one child runs.
- A **scene** is a `System::Scene` task, one at a time above the permanent root scene (Finding 11). Its **scene ID**
  (`System::SceneID`: Boot, Menu, Race, Trophy, Thankyou, Ending, Demo) is the kind of scene. A **scene proxy** is the section
  that switches to a scene and runs a `.bss` in it. The proxy's section name (`MenuScene`, `DemoScene`) names the `.bss`, and
  its **scene name** (`Menu`, `Race`) gives the scene ID, so several proxies can use the same scene ID (Finding 7). In this
  document a scene is called by the name of its proxy.
- At run time each section has a **state**: 1 free, 2 ready, 3 entering, 4 standby, 5 running, 6 completed, 7 finishing or
  cancelling, 8 exited. Finding 5 gives the transitions.
- A chain such as `MenuScene` `Boot` -> `Seq_Title` `Boot` lists sections, each followed by the code it is entered with. When a
  chain starts from a section that ends (`RaceScene` `SingleTA_Chara` -> ...), its first code is the one that section returns.

### 1. The files and how they are loaded

#### How a file name is built

`SequenceResource::create` builds the file name with `"%s-%s.%s"` from a name, a mode and an extension (`"brs"` when its `bool`
argument is set, `"bss"` otherwise) and loads it with `UI::LoadUI(name, EArchiveID::UI_COMMON (3), ...)`, that is from
`UI/common.szs`. It then resolves `BSEQ::m_engine_creator_table_offset` into `SequenceResource::m_engine_creator_table`,
`BSEQ::m_nametable_offset` into `SequenceResource::m_string_table`, and the `BSEQ::m_num_section_block` entries of
`BSEQ::m_section_block_offsets` into the `SequenceResource::m_section_blocks` array. Its only caller is `SceneSequence::create`,
which has two callers:

- `SequenceEngine::init` calls `createRootSequence` with the results of three virtuals, `getDefaultRootSceneName`,
  `getDefaultRootSceneMode` and `getDefaultRootSceneEnterCode`. `DashSequenceEngine` does not override them: their slots hold the
  base functions both in the `SequenceEngine` vtable and in the `DashSequenceEngine` vtable. `getDefaultRootSceneName` returns
  `"Root"` and `getDefaultRootSceneMode` returns `"Default"`, so the root file is always `Root-Default.brs`.
- `SceneSequenceProxy::sceneStart` creates a `SceneSequence` with `getSectionName()` and `getModeName(Section::m_mode_id)` of the
  proxy, so the proxy section `MenuScene` in mode `Default` loads `MenuScene-Default.bss`. For a proxy (as for any sequence),
  `Section::getModeName` ignores its argument and returns the string of the block's `SceneSequenceProxyBlock::m_mode_name_offset`.

The name of a root file is therefore `<root section name>-<root block mode name>`: `Root`/`Default` gives `Root-Default.brs`, and
the file stored under the hash 0xB070E39E (its name is missing from `HashTable.saht`, the list of known file names that the
research tools use, in `tools/mk7re/static/data/`; see the next subsection), whose root is
`SceneTestRoot` with a block of mode `Scene`, hashes as `SceneTestRoot-Scene.brs`.

#### The 29 files

A file shown by its hash is not named in `HashTable.saht`. Its name was recovered by computing the SARC hash (multiplier 0x65) of
`<root section name>-<root mode name>.bss` (`.brs` for 0xB070E39E), which matched every such file:

| File in `common.szs` | Name | Role |
| --- | --- | --- |
| `Root-Default.brs` | | root of the game |
| `MenuScene-Default.bss`, `RaceScene-Default.bss`, `DemoScene-Default.bss`, `TitleDemoScene-Default.bss`, `TrophyScene-Default.bss`, `WinningRunScene-Default.bss`, `EndingScene-Default.bss`, `ThankyouScene-Default.bss` | | retail scenes |
| 0x73DC5722 | `BootScene-Default.bss` | retail, only when the boot checks need the Boot scene (Finding 8) |
| 0xAF13024A | `DebugMenuScene-Default.bss` | debug menu |
| 0x02F96D68 | `DebugRaceScene-Default.bss` | debug |
| 0x750E5AC7 | `SoundTestScene-Default.bss` | debug |
| 0x9BFA82D2 | `Viewer-Default.bss` | debug |
| 0x5B1CB14A | `DebugChannelScene-Default.bss` | debug |
| 0x0352FB77, 0xCDD18772, 0xF50FF6F8, 0x7EBFF6D3, 0x8A0A96A2, 0x5AEA846B, 0x5CA157F1 | `DebugShiraiwa`, `DebugSuzuki`, `DebugKonishi`, `DebugObayashi`, `DebugKartRun`, `DebugField`, `DebugSakuraba` `-Default.bss` | per-developer debug scenes |
| 0x23F2C083, 0x77D92BA1, 0x78BFD596, 0x2C353DCB | `E3MenuScene`, `E3RaceScene`, `E3Trophy`, `E3ThankYou` `-Default.bss` | E3 demo |
| 0x7A6EB5F7, 0xE1C78D26 | `UDSMatchingTest`, `WifiMatchingTest` `-Default.bss` | network tests |
| 0xB070E39E | `SceneTestRoot-Scene.brs` | an alternative root file for testing |

### 2. File format

#### Layout

All values are little endian. Offsets in the header are from the start of the file; offsets inside a section block are from the
start of the structure that holds them. Strings are NUL-terminated ASCII in the string table at the end of the file, referenced by
`u16` offsets from the start of the string table.

```
BSEQ header (0x34 bytes)            see the glossary
u32 section_block_offsets[m_num_section_block]
section blocks ...
engine creator table                m_num_engine_creator x { u16 creator_name, u16 mode_name }
string table                        (the .brs has no engine creators; both offsets point to the string table)
```

#### Header

Which function reads what:

- `BSEQ::m_sequence_id`: `SectionDirector::findAttachedDisableSection` compares the requested ID with it and, when equal,
  searches for a section of type 5 instead of reading the block's type: the root is always a `ParallelSequence`.
  `SceneSequence::createSections` finds the root with it.
- `BSEQ::m_root_mode_id`: `SceneSequence::init` calls `readyOuter(root, m_sequence_id, m_root_mode_id)` (`ldrh r2, [r0, #8]`) and
  then falls through into `Section::enterOuter`. It is 2 in `Root-Default.brs` (its root block has mode ID 2) and 1 everywhere
  else.
- `BSEQ::m_num_sections` .. `BSEQ::m_num_layers`: `SectionDirector::create`, Finding 3.
- `BSEQ::m_num_section_block`: `SequenceResource::create` and every search function.
- `BSEQ::m_num_engine_creator`: `EngineCreatorManager::createEngines`.
- `field_0x0A` (always 4), `field_0x0C` (always 1), `field_0x20`, `field_0x24` (always 0) and `m_first_section_block_offset`:
  no read found. The disassembly of every `Sequence::Section*`, `*Sequence`, `SequenceLayer`, `SectionDirector`,
  `SectionClassManager`, `EngineCreatorManager`, `SequenceEngine` and `SequenceResource` function was scanned for loads at those
  offsets, with no hit.

  For 0x0A and 0x0C the whole code was also scanned. The scan looked for every `ldrh` or `ldrsh` at offset 0xA or 0xC whose base
  register is also used, within 40 instructions, for at least two other header-shaped loads (`ldrh` at 0xE-0x1E, `ldr` at
  0x2C/0x30/0x34). Pass 1 found 24 places in `eur2` and 23 in `dlp`; the repeat in `eur2` during the fact check, with its own
  script, found 31. The only ones in sequence code are `SectionBlock::getEnterCodeTable` and `getReturnCodeTable`, which read
  0xA and 0xC of a **section block**, not of the header. The others are in nw4c layout (`nw::lyt::Window`, `nw::lyt::Picture`),
  fonts (`nw::font::ResFontBase`), `Field::ObjectEel`, `Field::ObjectPenguin`, `Field::ObjectTempoKun`,
  `GameSetting::getSimpleAddress`, `nn::hid` and unnamed functions outside the sequence code. No code reads the two fields, so
  their meaning can only come from the data or from the tool that wrote the files:
  - they never change: 4 and 1 in all 29 files, the `.brs` files included, whatever their size or content;
  - they sit between `m_root_mode_id` and the six count fields, so they are probably two more file-wide values of the same kind.
    One numerical coincidence: the pool counts that follow come in 4 sequence kinds (serial, cross fade, parallel, delegate) plus
    1 proxy kind. That is not evidence, and a format version (4.1) fits the values as well.

  For editing: write 4 and 1. Nothing in the game reads them, so any value works, but other tools may expect the original ones.

#### Section block

`SectionBlock`, 0x14 bytes: see the glossary. The accessors `SectionBlock::getPracticalSection`, `getSequence`,
`getCrossFadeSequence` and `getSceneSequenceProxy` test `SectionBlock::m_block_type` (`0 or 1` practical, `== 2` sequence, `== 3`
cross fade, `== 4` proxy) and return `this + m_block_offset`, or null. Block types 0 and 1 are not told apart by the code: which
registry is searched depends on `m_section_type`, not on the block type (Finding 3). The files use 0 for tasks and 1 for pages.

`m_section_type` is read by `SequenceResource::searchSectionType` (returns the byte of the first block with the ID),
`searchPracticalSectionBlock` (accepts types `< 3`) and `SectionClassManager::constructSection`. The value 8 is only written in the
root of `Root-Default.brs` and `SceneTestRoot-Scene.brs`; the roots of the `.bss` files say 7. Neither is read for a root.

#### Code table

`NameTableBlock`: `u16 count, u16 default_id`, then `count` x `{u16 id, u16 name}`. `searchItem(u16)` returns the entry whose
`NameTableBlockEntry::m_id` matches, otherwise the last entry whose `m_id` equals `NameTableBlock::m_default_id`, otherwise null.
`searchItem(name)` does the same with a string compare on the name. An ID is only unique inside its table: `RaceScene` has return
code 5 = `SingleGP_Next` while `ClearRaceInfoTask` has return code 5 = `Title_Top`.

#### Practical block

`PracticalSectionBlock`, block types 0 and 1: `u16 m_num_instances, u16 m_class_name_offset, u16 m_mode_table_offset, u16 pad`;
the mode table is a code table. `SectionDirector::create` constructs `*getPracticalSection()` objects per practical block (the loop
at the end of the function); every file says 1. `SectionClassManager::constructSection` reads the class name from
`m_class_name_offset` (`local_1c = strings + *(u16 *)(block + 2)`).

#### Sequence block

`SequenceBlock`, block type 2: `u16 m_mode_id, u16 m_mode_name_offset, u16 m_subsection_list_offset, u16 m_flow_list_offset`.
`SequenceResource::searchSequenceBlock(id, mode)` returns the block with that section ID **and** `*(u16 *)block == mode` (for block
types 2, 3 and 4). So a sequence can have several blocks with the same section ID, one per mode; the game's files never do this.

#### Cross fade block

Block type 3: same layout as the sequence block, but its flow entries are 0xC bytes: the 8 bytes of a normal entry plus
`u16 m_cross_fade_type` (only the low byte is used: `puVar5[iVar4 * 6 + 6] & 0xff` in `CrossFadeSequence::updateState`) and 2
bytes of padding. `CrossFadeSequence::enter` walks the entries with a stride of 6 halfwords. No file uses it.

#### Scene proxy block

`SceneSequenceProxyBlock`, block type 4: `u16 m_mode_id, u16 m_mode_name_offset, u16 m_scene_name_offset, u16 pad`.
`SceneSequenceProxy::ready` reads the scene name from `m_scene_name_offset`.

#### Subsection list

`u16 count, u16 pad`, then `count` x `{u32 section_id, u16 mode_id, u16 pad}` (`SubsectionListBlock::getItem` returns
`this + 4 + i * 8`). The same section ID may appear several times: `Seq_Race` lists `MenuNetworkSelectMenuTask` at indices 3, 4
and 5. The index, not the ID, is what the flow list refers to, so the same section can be placed at several points of the graph
with different outgoing flows.

#### Flow list

`u16 count, u16 pad`, then `count` x `{s16 src_index, u16 src_code, s16 dst_index, u16 dst_code}` (the members
`SequenceBlockFlowListEntry::m_src_subsection_index`, `m_src_code`, `m_dst_subsection_index` and `m_dst_code`). The two indices
are subsection indices, and -1 (0xFFFF) stands for the sequence itself. How each sequence class reads the list is in Finding 5,
which uses the short names.

#### Engine creator table

`{u16 creator class name, u16 mode name}` per entry, Finding 7.

### 3. From blocks to objects: pools, layers and class lookup

#### Pools

`SectionDirector::create`, called once per file from `SceneSequence::createSections`:

1. Allocates an array of `BSEQ::m_num_sections` pointers and sets both the capacity and the size of the director's section array
   (its `Object::TDirectorArray` base, which has no file in `template/`) to that count.
2. Creates `m_num_serial_sequences` `SerialSequence` objects, `m_num_cross_fade_sequences` `CrossFadeSequence`,
   `m_num_parallel_sequences` `ParallelSequence` (each `create`d with `BSEQ::m_num_layers`), `m_num_delegate_sequences`
   `DelegateSequence` and `m_num_scene_sequence_proxy` `SceneSequenceProxy`. These objects are not tied to a block: they are a
   **pool**.
3. For every block with `m_section_type < 3`, calls `SectionClassManager::constructSection` `m_num_instances` times. These objects
   are tied to their section ID and block for good (`Section::createForPracticalSection`, called from `Page::create`, stores
   both).

The append to the array does not check the capacity (`if (array[count] == 0) array[count++] = section`), and
`findAttachedDisableSection` iterates up to the capacity and passes every slot to `attachedDisableSectionFinder`, which
dereferences it. So `m_num_sections` has to be exactly the sum of the five pool sizes plus all `m_num_instances`. This holds in all
29 files.

#### Finding a section for a child

When a sequence needs a child, `SequenceLayer::attachSection` / `SequenceLayer::ready` call `findAttachedDisableSection(id,
layer)` for the layer the child goes to, then for the layer of that layer's owner section, and so on up the tree, and finally
with a null layer. The finder (`attachedDisableSectionFinder`) accepts a section whose `Section::m_current_state` is 1 (free) and
whose `Section::m_parent_layer` equals the layer being tried, and then:

- for types 0-2 (practical): whose `Section::m_sequence_id` equals the ID;
- for the other types: whose class's `getSectionType()` equals the type of the block (`searchSectionType`), or 5 for the root.

The section found gets the layer as its `Section::m_parent_layer`. Then `readyOuter` stores the mode in `Section::m_mode_id`;
for a sequence (type >= 3) it also stores the ID in `Section::m_sequence_id` and picks the block with
`searchSequenceBlock(id, mode)`. Consequences:

- The pool sizes are the largest number of sections of each class that are active at the same time, not the number of blocks.
  `MenuScene-Default.bss` has 8 serial blocks and a serial pool of 3 (the nesting depth); `Root-Default.brs` has 21 proxy blocks and
  a proxy pool of 1 (one scene at a time).
- `Section::clearOuter` frees a section (state 1) but does not reset `Section::m_parent_layer`. A free pool section is therefore
  only found again from the layer it was last attached to, from a layer below it, or by the final search with a null layer
  (which only matches sections never attached). A free section left on a layer outside that chain cannot be reused there. In the
  game's files the counts above are enough; for edited files this means the pool may have to be larger than the number of
  sections active at once (read from the code, not tested).
- The root of each file takes one `ParallelSequence` from its pool; `m_num_parallel_sequences` counts it.
- `ParallelSequence::create` allocates `BSEQ::m_num_layers` layers (`LayeredSequence::createLayer`), and `ParallelSequence::ready`
  fills one layer per subsection without a bound check, so `m_num_layers` must be at least the subsection count of the largest
  parallel block (the root included). In every file it is exactly that maximum.

#### Class lookup

`SectionClassManager::constructSection` chooses the class by `SectionBlock::m_section_type`:

| `m_section_type` | Searched list | Fallback when the name is not found |
| --- | --- | --- |
| 0 page | `m_page_list` | `m_page_info` = `DummySectionClassInfo<DummyPage>` |
| 1 task | `m_task_list` | `m_task_info` = `DummySectionClassInfo<DummyTask>` |
| 2 data holder | `m_data_holder_list` | `m_data_holder_info` = `DummySectionClassInfo<DummyDataHolder>` |

The fallbacks are set in the `SectionClassManager` constructor, which loads the vtables of the `DummyTask`, `DummyPage` and
`DummyDataHolder` class infos. The search is a binary search by name (`SectionClassInfoList::compareByName`), the lists being
sorted after definition, so the registration order does not matter.

#### What a dummy does: nothing, forever

- `DummyPage` is a plain `Page` (`DummySectionClassInfo<DummyPage>::constructSection` constructs `Page::Page` with the `DummyPage`
  vtable). Apart from its DTI accessors and its destructor, the only slot of that vtable that is its own is `onPageEnter` (a
  single `bx lr`); every other slot is a `Page`, `ExecutableSection`, `PracticalSection`, `Section` or `Object::Actor` function,
  and all the `onPage*` hooks of `Page` are empty. The page has no controls, so it enters, reaches standby and starts. Nothing
  ever calls `completePage` on it, so it stays running, drawing nothing and reacting to nothing.
- `DummyTask` is a `LastingTask` whose `onTaskStart` and `onTaskStep` both return -1 (`mvn r0, #0`), which means "not done yet",
  so it never completes either.
- `DummyDataHolder` only overrides `onEnableData` with `bx lr`. A data holder goes to standby as soon as it is entered
  (`DataHolder::enter` sets the next state to 4), and `DataHolder::step` is empty, so it never completes.

In a serial sequence a dummy therefore stops the flow for good: the screen stays as it is and nothing happens. In a parallel
sequence it only keeps its layer busy (every `isCompletable()` returns 1, Finding 5).

#### The registered classes

The names are those returned by each class info's `getClassName` (for example the one of `ExecutableSectionClassInfo<BootTask>`
loads the string "BootTask"); all 91 were read from the vtables that the two `define*ClassInfoList` functions load:

- Tasks (15, `defineTaskClassInfoList`): `BootTask`, `RootExitTask`, `RootResetTask`, `ClearRaceInfoTask`,
  `WinningRunSelectTask`, `MenuJoinSelectTask`, `MenuSceneSetterTask`, `MenuModeSetterTask`, `MenuNetworkSelectMenuTask`,
  `MenuNetworkApplyTask`, `MenuNetworkCourseDecideTask`, `MenuNetworkSelectFromWatchTask`, `MenuChannelFinalizeTask`,
  `MenuChannelMgrTask`, `UnlockMessageTask`.
- Pages (76, `definePageClassInfoList`): `TitleDemoPage`, `DemoPage`, `WinningRunPage`, `BaseRacePage`, `RacePage`, `TrophyPage`,
  `EndingPage`, `ThankyouPage`, `MenuTitle`, `MenuSingle_*` (Mode, Class, Chara, Kart, Cup, CupGP, Course, CourseBattle, Setting,
  Ghost, GhostLoad), `TimeAttackChart`, `Menu_UpBarController`, `MenuMulti_*` (Group, Waiting, DlplaySequence, Mode, Class, Chara,
  Kart, VSSetting, BattleSetting, Cup, CupGP, Course, CourseBattle, CourseVote, CourseDL), `MenuWiFi_*` (Connect, ModeOpponent,
  Mode, Chara, Kart, Waiting, WaitingDecide, Confirm, Cup, Course, CourseBattle, CourseVote, Friend), `MenuCommunity_*` (Enter,
  Top, Lobby, Search, SearchConfirm, CreateMark, CreateName, CreateRule, CreateComment, CreateFinish, Chara), `MenuChannel_*` (Top,
  ShowMii, CecMii, CecList, SetupTop, SetupMii, SetupComment, SetupMachine, SetupGP, SetupSetting), `Common_SystemDialog`,
  `BgPage`, `FaderPage`, `MMenCheckPage`, `TimerPage`.
- Data holders: none (`defineDataHolderClassInfoList` is a single `bx lr`).

`BaseRacePage` is registered but no file uses it. `RootResetTask` is only used by the E3 files. The files use 15 page class names
that are not registered, all in unreferenced files (Finding 9).

#### Section names and section IDs

Section names (`Page_Bg`, `Seq_Title`, `Task_CourseDecide`) are free text: the code only reads them to build the `.bss` file name
of a proxy and in `Section::getSectionName`. Section IDs are only compared for equality; nothing in the functions read derives
them from the names.

### 4. Enter codes, return codes and modes

Each section has an enter code table, a return code table and (practical blocks only) a mode table. The runtime keeps code
**IDs** (`Section::m_mode_id`, `Section::m_enter_code_id`, `Section::m_return_code_id`); names are only used at the boundary with
the C++ classes and for the root's enter code.

| Step | Function | What happens |
| --- | --- | --- |
| a parent starts a child with code *c* | `Section::enterOuter` | `m_enter_code_id = searchItem(enter table, c)->m_id`: an unknown *c* becomes the table's default; with no default entry, `m_enter_code_id` is left as it was |
| a page/task is entered | `ExecutableSection::enter` | `m_enter_code = classInfo->convertEnterCode(getEnterCodeName(m_enter_code_id))`; the name of an ID that is not in the table is `""` |
| a page/task is readied | `PracticalSection::ready` | `mode = classInfo->convertMode(getModeName(m_mode_id))`, the name from the block's mode table; `""` when missing |
| a page/task finishes | `ExecutableSection::setReturnCodeEnum` | name = `classInfo->convertReturnCode(enum)`; entry = `searchItem(return table, name)`; `completeOuter(entry ? entry->m_id : 0)` |
| any section completes with *r* | `Section::completeOuter` | `m_return_code_id = searchItem(return table, r)->m_id`: an unknown *r* becomes the default |

`convertEnterCode`, `convertReturnCode` and `convertMode` of `ExecutableSectionClassInfo<T>` are 8-byte thunks to the static
`T::convertEnterCodeImpl`, `T::convertReturnCodeImpl` and `T::convertModeImpl`. Example, `BootTask`: `convertEnterCodeImpl` maps
the names `_BootScene`, `Boot`, `FromFriendList`, `DLC` to 0, 1, 2, 3 and anything else to 0; `convertReturnCodeImpl` maps the
enums 0..3 back to the same names. So the **names** in a practical section's tables must match the strings in its class's
`convert*Impl` functions; the IDs are free. Names a class does not know fall back to the class's default enum (enter) or to the
table's default ID (return).

Sequences and proxies never convert names: their codes are only used through the flow lists, by ID. The only other name compare
is the root of `Root-Default.brs`: `createRootSequence` walks the root's enter code table and compares each name with the enter
code string from `getDefaultRootSceneEnterCode`, then calls `SceneSequence::init` with the ID of the entry found. The proxy/`.bss`
boundary is by ID (Finding 7).

### 5. How the sequence classes use the flow list

#### Section states

From `Section::updateStateOuter`, which calls the virtual for each change of state: 1 free, 2 ready (`readyOuter`), 3 entering
(`enter` called), 4 standby (`standby`), 5 running (`start`), 6 completed (`complete`; the parent reads
`Section::m_return_code_id`), 7 finishing or cancelling (`finish` from 6, `cancel` from 5), 8 exited (`exit`). `clearOuter`
returns a section to 1 and calls `clear`. From 6, `reenterOuter` goes back to 5 (`reenter`). The parent sequence drives these
transitions; a page or task only calls `completeOuter`, through `setReturnCodeEnum`.

#### SerialSequence

One child at a time:

- `enter`: the first flow entry with `src_index == -1` and `src_code == m_enter_code_id`. If `dst_index >= 0`, it attaches the
  child of subsection `dst_index`, readies it with the subsection's ID and mode, and enters it with `dst_code`. If
  `dst_index == -1`, there is no child, and the sequence completes with `dst_code` as soon as it runs. If there is no entry, there
  is no child, and the sequence completes with the default return code.
- `updateState`, while running: when the child completes, the first entry with `src_index` equal to the current index and
  `src_code` equal to the child's `Section::m_return_code_id`. `dst_index == -1`: complete the sequence with `dst_code` (the
  child is finished later by the sequence's own finish). `dst_index >= 0`: finish the child; when it has exited (state 8), clear
  it and start subsection `dst_index` with `dst_code` (a new child is attached even when `dst_index` is the current index, so a
  page can restart itself). No entry: complete the sequence with the return table's default ID.
- `reenter`, when a parent re-enters the sequence with a new enter code: the same lookup as `enter`. If the target is the current
  child, it is `reenterOuter`ed with `dst_code` instead of restarted; if it is another child, the current one is finished and the
  target started as in `updateState`.

#### ParallelSequence

All children at once, one layer each; every file root is one:

- `ready`: readies every subsection on its own layer.
- `enter`: for each subsection *i*, the first entry with `src_index == -1`, `src_code == m_enter_code_id` and `dst_index == i`
  gives its enter code; without one, the child is entered with 0, which a code table turns into its default. **Every** child is
  started; the flow only chooses the code.
- `updateState`, entering: children in standby whose `isSyncFadein()` is 0 are started at once; when no child is still entering,
  the parallel sequence goes to standby, and its children are started together when it starts.
- `updateState`, running: for each child *i* that has completed and is not marked done, the first entry with `src_index == i` and
  `src_code == child's return code`. If found with `dst_code != 0`, the parallel sequence completes with `dst_code` (`dst_index`
  is not read; the files always write -1). If found with `dst_code == 0`, the scan of the children stops for this frame, and the
  default check below runs only if no child scanned before it is still running (no file has such an entry). If not found, the
  child is marked done. When every child is done and the return table's default ID is not 0, the parallel sequence completes with
  the default. A child that has not completed counts as running when its `isCompletable()` returns non-zero, and every
  `isCompletable()` in the game returns 1, so a child that is still running keeps the parallel sequence alive.
- `finish`: cancels the children that are running and finishes the others.

#### CrossFadeSequence

One child, with an overlapping transition: like serial, plus `m_cross_fade_type` from the flow entry, applied by
`changeSubsection`: 0 = finish the old child first, then start the new one (like serial); 1 = finish the old one with fade kind 1
and start the new one with fade kind 2 at the same time; 2 = start the new one with fade kind 1, then finish the old one with fade
kind 2. When no free section can be attached for the new child, it falls back to 0. Not used by any file.

#### DelegateSequence

Two layers. Subsection 0, the **owner**, runs on layer 0; subsection 1 runs on layer 1 when the owner hands over:

- `ready` readies subsection 0 on layer 0. `enter` enters it with `dst_code` of the first entry with `src_index == -1` and
  `src_code == m_enter_code_id` (`dst_index` is not read), or with 0.
- `updateState`, while running and while layer 1 is empty: when the owner completes, the first entry with `src_index == 0` and
  `src_code == owner's return code`. With `dst_index != -1`, subsection 1 is readied on layer 1 and entered with `dst_code`, while
  the owner stays completed. With `dst_index == -1`, the delegate sequence completes with `dst_code`. Without an entry, it
  completes with its default return code.
- `updateState`, while layer 1 is in use: when that section completes, the first entry with `src_index == 1` and its return code.
  With `dst_index != -1`, it is finished, and once it has exited the layer is cleared and the owner is **re-entered**
  (`reenterOuter`) with `dst_code`. With `dst_index == -1`, the delegate sequence completes with `dst_code`. Without an entry, it
  is finished and the owner is re-entered with 0.

Not used by any file.

### 6. The building blocks in use

The engine splits a game flow into things that are shown (pages), things that are done (tasks), and ways of combining them
(sequences). A section never knows who comes before or after it: it is entered with an enter code and ends with a return code,
and which section runs next is decided only by the flow list of the sequence that contains it (Finding 5). The behaviour below is
read in `eur2`. The *intention* behind it is inferred from that behaviour and from how the game's files use each block.

#### Pages

- `Page::create` gives every page its own `UI::ControlDirector` (layouts and controls). `Page::enter` resets the controls, hands
  the page to a render object, and starts the fade-in. The page only reaches standby once the fade-in is complete and
  `canFinishFadein()` agrees (`Page::step`). `Page::finish` starts the fade-out, and the page exits only when that is complete
  and `canFinishFadeout()` agrees. Tasks do none of this.
- A page ends when the player decides something: `Page::completePage` calls `setReturnCodeEnum` and also clears the input
  manipulators (`UI::ManipulatorManager::clear`; Finding 13).
- The menu pages (`BasePage` and its subclasses) all use the same small vocabulary: enter codes `Next` / `Back` (were we reached
  by going forward or by backing out?) and return codes `Next00`..`Next07` / `Back` (which choice was made). Example from
  `MenuScene-Default.bss`: `Page_SingleChara` (index 10 of `Seq_Single`) returns `Next00` -> `Page_SingleKart` entered with
  `Next`, and `Back` -> `Page_SingleMode` entered with `Back`. The page itself decides nothing about navigation; it only reports
  which button led out.
- `Page::isSyncFadein()` returns 1: pages that start together fade in together (see the parallel sequence below).

#### Tasks

A task prepares or changes state, makes a decision, or waits for a system process. Two kinds:

- `InstantTask` does all its work in one call. `InstantTask::start` calls `onTaskMain()` and completes with its result straight
  away; a re-enter runs it again (`InstantTask::reenter`). Classes (the ones that override `onTaskMain`): `ClearRaceInfoTask`,
  `MenuModeSetterTask`, `MenuSceneSetterTask`, `MenuJoinSelectTask`, `WinningRunSelectTask`, `MenuNetworkSelectFromWatchTask`.
- `LastingTask` runs over several frames. `LastingTask::start` calls `onTaskStart()`, and `LastingTask::step` calls
  `onTaskStep()` every frame until it returns something other than -1, then completes with it. It can be cancelled
  (`onTaskCancel` / `onTaskCancelStep`). Classes (the ones that override `onTaskStart` and `onTaskStep`): `BootTask`,
  `RootExitTask`, `RootResetTask`, `UnlockMessageTask`, `MenuChannelMgrTask`, `MenuChannelFinalizeTask`,
  `MenuNetworkSelectMenuTask`, `MenuNetworkApplyTask`, `MenuNetworkCourseDecideTask` (and `DummyTask`).
- Both return 0 from `isSyncFadein()`: a task does not wait for the fade-in of its neighbours.
- The files use tasks in three ways:
  - **Routers.** An instant task turns runtime state into a branch of the flow, because its return code selects the flow entry:
    `ClearRaceInfoTask` (Finding 8), and `WinningRunSelectTask` in `Seq_Race`.
  - **Setters.** A task placed between two pages records a choice for the code that follows. `Seq_Single` passes through
    `MenuModeSetterTask` with the enter code `GrandPrix`, `TimeTrial`, `BalloonBattle` or `CoinRunner` between `Page_SingleMode`
    and the next page. (The task's table also has `Versus`, which `Seq_Single` does not use.)
  - **Services** that run alongside the pages for the lifetime of a scene: `UnlockMessageTask` and `MenuNetworkSelectMenuTask` in
    the `MenuScene` root, and `RootExitTask` in the root of the game.

#### Data holders

A data holder is a section meant to keep data alive while it is active. It has the virtuals `onInitData`, `onEnableData` and
`onDisableData`, and the template `TDataHolder<T>`. MK7 registers none, and no file uses one.

#### Serial sequences

A serial sequence is the menu "wizard": one child is active, and when that child ends, its return code picks the next child and
the code to enter it with (Finding 5). This gives it four uses:

- **Forward and back navigation** are both plain flow entries. "Back" is an entry to an earlier index with the enter code `Back`.
- **Entry points.** The sequence's own enter codes start the flow at different children. `Seq_Single` can be entered with
  `Default`, `TA_ChangeChara`, `TA_ChangeCourse`, `BB_Course` or `BC_Course`, which is how the game reopens a menu in the middle
  after a race.
- **Exits.** Its return codes (`GP`, `TimeAttack`, `Battle`, `Back`, `SDError` for `Seq_Single`) are the only things its parent
  sees.
- **The same section at several indices.** `Seq_Single` lists `Page_SingleChara` at indices 10, 14 and 18 and `Page_SingleKart`
  at 15, 19 and 21. The same screen then continues differently depending on how it was reached (Grand Prix, time trial, battle)
  without the page knowing.

Nested serial sequences (`Seq_Title` -> `Seq_Single`, `Seq_Multi`, ...) group a menu tree into self-contained parts.

#### Parallel sequences

Every child gets its own layer and they all run at once (Finding 5):

- **Every child is started.** The flow list only chooses each child's enter code.
- **They start together.** Tasks are started as soon as they are ready, while pages wait and are started together when the
  sequence starts. That is the synchronised fade-in: while the parallel sequence is entering, `ParallelSequence::updateState`
  starts a child in standby only if its `isSyncFadein()` is 0.
- **The first exit wins.** The sequence ends as soon as one child ends with a code that the flow list maps to an exit, and then
  all its children are finished together (`ParallelSequence::finish`).

This is the model of a **scene**. The root of every `.bss` is a parallel sequence. In `MenuScene`, `RaceScene` and `TrophyScene`
it combines the persistent parts of the screen (all of `Page_Bg`, `Page_UpBarControl`, `Page_Timer`, `Page_Fader`,
`Page_CommonSystemDialog` and service tasks in `MenuScene`, fewer in the other two) with the one serial sequence that holds the
actual menu, race or ceremony flow; the other scene files have no serial sequence (Finding 8). In `MenuScene`, the scene ends when
`Seq_Title` exits, or when the system dialog page (`Page_CommonSystemDialog`, the page that shows the game's message windows)
reports a network error (Finding 10). The game's root (`Root`) is the same idea one level up: the whole game (`RootMain`) runs
next to `RootExitTask`. Smaller parallel groups exist inside menus: `Para_TAChart` and `Para_CH`.

#### Example: `Para_TAChart`

`Para_TAChart` shows how a parallel group combines one interactive flow with a passive display page. It has two layers:

- `Seq_TAChart`, a serial sequence: `Page_SingleCourse` (`MenuSingle_Course`) -> `Page_SingleGhost` (`MenuSingle_Ghost`), with
  `Back` from the ghost page returning to the course page. This is the flow the player navigates, and all of `Para_TAChart`'s
  flow entries are about it: its enter code `Next` starts it, and its `Next00`, `Next07` and `Back` end the group.
- `Page_SingleTAChart` (`TimeAttackChart`): the time trial record chart (layouts `ta_best`, `ta_time_dot`, `ta_ghost`,
  `ta_ghost_mii`, `course_name`). No flow entry mentions it, so the parallel sequence starts it with its default enter code (in the
  flow graph, the dashed "(always)" arrow of an implicit start; Finding 15).

The two pages do not clash, because the chart takes no part in the navigation. It never completes on its own: no function of
`TimeAttackChart` calls through the `completePage` slot or calls a completion function, and its `initControl` creates visual
controls and a menu view but no button control. Instead it is driven directly by the pages of the other layer. Its constructor
stores itself in `MenuData::m_time_attack_chart`, and through that pointer:

- `MenuSingle_Course::onPageEnter` calls `TimeAttackChart::onPageCourseEnter` and `setCourseName`;
- `MenuSingle_Course::buttonHandler_SelectOn` calls `changeOut` and `setCourseName` when the cursor moves to another course;
- `MenuSingle_Course::onPageComplete` calls `onPageOut`;
- `MenuSingle_Ghost::onPageFadeout` calls `onPageFromGhost`;
- `GhostList::select` calls `selectGhost`.

When `Seq_TAChart` ends, the parallel sequence completes and finishes all its children, the chart included
(`ParallelSequence::finish` cancels running children). So the chart lives exactly as long as the course and ghost selection.
That is the general recipe for something that must be visible next to a flow without being part of it.

#### Delegate and cross fade sequences

A delegate sequence lets its owner hand over to a second section and get control back afterwards, without the owner being rebuilt:
the owner stays completed on its layer while the other section runs, and is re-entered with a code when it ends (Finding 5). The
intended use looks like a screen that opens a sub-screen or a dialog and resumes afterwards. A cross fade sequence is a serial
sequence whose old and new child can fade at the same time (cross fade type 1 or 2). No file uses either.

#### Scene proxies

Changing scene means loading other archives and creating other engines. The proxy hides that: to its parent it is one section
with enter and return codes. Inside, it switches the scene and runs that scene's own `.bss`, passing the codes through by ID
(Finding 7). The game's root flow is therefore short: boot, then the menu, race, trophy and credits scenes as nodes.

### 7. Scenes, `.bss` files and engines

#### From proxy to scene

`SceneSequenceProxy::ready` converts the block's scene name with `DashSceneIDConverter`, stores the result in
`SceneSequenceProxy::m_scene_id` and calls `System::SceneManager::changeChildScene(scene)`. The dictionary
(`DashSceneIDConverter::defineSceneIDDictionary`): `Boot` 1, `Menu` 2, `Race` 3, `Trophy` 4, `Thankyou` 5, `Ending` 6, `Demo` 7
(`System::SceneID`). `initDictionary(9, 1)` sets the default that `convertToSceneID` returns for unknown names to 1, so any other
name opens the **Boot** scene: `BootScene`, `DebugMenu`, `DebugKonishi`, `SoundTest`, `DebugViewer` and the other debug scene
names of `Root-Default.brs` (two debug proxies use real scene names: `DebugRaceScene` uses `Race` and `DebugChannelScene` uses
`Menu`).

#### From scene to `.bss`

`SequenceEngine::sceneStart` forwards the new scene ID down the active sections. `SceneSequenceProxy::sceneStart` reacts when it
matches `SceneSequenceProxy::m_scene_id`: it creates the `SceneSequence` of `<section name>-<mode name>.bss` (Finding 1) and keeps
it in `SceneSequenceProxy::m_scene_sequence`. Its `createSections` builds the sections and finds the root by
`BSEQ::m_sequence_id`, and `SceneSequence::createEngines` runs the engine creator table (Finding 11 gives the order).

#### Codes across the boundary

In `SceneSequenceProxy::updateState`:

- while the proxy is entering, once the `.bss` root is free (state 1), `SceneSequence::init` is called with the proxy's
  `Section::m_enter_code_id` (`ldrh r1, [r4, #0x1e]` right before the call). It readies the root with `BSEQ::m_root_mode_id` and
  enters it with that **ID**;
- while the proxy is running, when the `.bss` root completes (state 6), the proxy calls `completeOuter` with the root's
  `Section::m_return_code_id`.

So the IDs of the proxy's tables in the `.brs` and of the root's tables in the `.bss` have to agree; the names do not matter
there. In the game files the two pairs of tables are identical (root section ID included) for all 23 proxies of the two `.brs`
files.

#### Engines

For every entry of the engine creator table, `EngineCreatorManager::createEngines` finds the creator by class name (binary search
in the list of `DashEngineCreatorManager::defineEngineCreatorList`; an unknown name is skipped) and calls its
`createEngine(scene, sequence, mode)`. The creators are `CameraEngineCreator`, `RenderEngineCreator` and
`CharacterEngineCreator`; each converts the mode with its `convertMode`: `Title` 0, `Menu` 1, `Race` 2, `Trophy` 3, `Thankyou`
4, `Ending` 5, `Demo` 6, `RefSetting` 7, `Viewer` 8, anything else 9 (`Default`). The retail files use `Menu`, `Race`, `Trophy`,
`Ending`, `Thankyou` and (BootScene) `Default`. `DebugMenuScene` and the per-developer files use names the creators do not know
(`Debug`, `DebugField`, `DebugKonishi`, ...), which become 9 like `Default`; `SoundTestScene` writes `Default`, `Viewer` uses
`Viewer` (8), and the E3, network test, `DebugRaceScene` and `DebugChannelScene` files use `Menu`, `Race` or `Trophy`. The `.brs`
files have no engine creators.

#### Retail scene proxies

The retail scene proxies of `Root-Default.brs`:

| Proxy section | Scene name -> ID | `.bss` | Engine mode |
| --- | --- | --- | --- |
| `BootScene` | `BootScene` -> Boot (default) | `BootScene-Default.bss` | Default |
| `MenuScene` | `Menu` | `MenuScene-Default.bss` | Menu |
| `RaceScene` | `Race` | `RaceScene-Default.bss` | Race |
| `DemoScene` | `Race` | `DemoScene-Default.bss` | Race |
| `TitleDemoScene` | `Race` | `TitleDemoScene-Default.bss` | Race |
| `WinningRunScene` | `Race` | `WinningRunScene-Default.bss` | Race |
| `TrophyScene` | `Trophy` | `TrophyScene-Default.bss` | Trophy |
| `EndingScene` | `Ending` | `EndingScene-Default.bss` | Ending |
| `ThankyouScene` | `Thankyou` | `ThankyouScene-Default.bss` | Thankyou |

### 8. The retail flow of `Root-Default.brs`

#### How the root enter code is decided

The root file is entered exactly once, at boot, with a name that the code picks:

1. At boot, `SystemEngine::createBeforeStructure` calls `GameSetting::init`, which reads the system settings (region, language,
   country, user name) and then sets `GameSetting::m_is_from_friend_list =
   nn::friends::CTR::detail::IsFromFriendList(&GameSetting::m_friend_key)`. This is true when the game was started from the HOME
   Menu friend list to join a friend, whose key is stored in `GameSetting::m_friend_key`.
2. `SequenceEngine::init` asks `getDefaultRootSceneEnterCode`: `"FromFriendList"` when `GameSetting::m_is_from_friend_list` is
   set, `"TitleScene"` otherwise. If the code is `DLC` or `FromFriendList`, it also clears
   `SystemEngine::m_is_title_page_active` and `SystemEngine::m_title_sleep_flag`. Those two flags are otherwise written by the
   title page (`MenuTitle::onPageEnter` sets the first and clears the second, `MenuTitle::onPageComplete` clears both and may set
   the second again) and read by the sleep code (`SleepChecker::check`, `ProjectGameFramework::gpuSleepProc`); what they change
   there was not followed.
3. `createRootSequence` looks the name up in the enter code table of `Root` (by name, Finding 4) and enters the root with it.
4. `Net::NetworkEngine::sceneExit` clears `GameSetting::m_is_from_friend_list` when any scene other than Boot ends, so the
   friend-list start only applies to the first trip through the menus.

The two retail starts follow the same path with a different code: `TitleScene` -> `RootMain` `TitleScene` -> `BootTask` `Boot`
-> ... -> `MenuScene` `Boot` -> `Seq_Title` `Boot` -> `Page_Title` `Next`. `FromFriendList` -> ... -> `MenuScene`
`FromFriendList` -> `Seq_Title` `FromFriendList` -> `Seq_WiFi` `FromFriendList` (its enter code 4), the online menu that joins
the friend.

#### `DLC` is the Download Play child

`dlp` has the same root file name and mode (`getDefaultRootSceneName` / `Mode` give `"Root"` / `"Default"`), but its
`getDefaultRootSceneEnterCode` returns the constant `"DLC"`. The child of a Download Play session therefore starts from the same
`Root-Default.brs` with `DLC`, which goes `BootTask` `DLC` -> `ProductMain` `DLC` -> `ClearRaceInfoTask` `DLC` -> `MenuScene`
`DLC` -> `Seq_Title` `DLC` -> `Seq_Multi` `DLC` (its enter code 4): straight into the local multiplayer flow, skipping the
title screen. (That the abbreviation means Download Play child was confirmed by the user; the code shows that only the `dlp` build
produces it.) In `eur2` the `DLC` entries are present but never used. The root's other enter codes (`DebugMenu`, `RaceScene`,
`DebugKonishi`, `DebugNetwork`, `Viewer`, `Test`) are produced by neither build.

#### Structure of `Root`

`Root` is a parallel sequence whose block has mode `Default` (mode ID 2):

- layer 0, `RootMain` (serial): `TitleScene` -> `BootTask` with `Boot`; `FromFriendList` -> `BootTask` with `FromFriendList`.
  (`DLC` -> `BootTask` with `DLC` in the Download Play child.) `BootTask` returns `Boot` / `FromFriendList` / `DLC` ->
  `ProductMain`; or `_BootScene` -> `BootScene`, whose `.bss` runs `BootTask` again and returns the same three codes ->
  `ProductMain`. The other returns lead to the debug branch.
- layer 1, `RootExit` (`RootExitTask`), started with its default; its return `End` completes the root with `End`.

#### BootTask and BootScene

`BootTask::onTaskStep` is a state machine of save data and Mii checks with dialogs. Each time it reaches a state that needs the
Boot scene, it checks whether the current scene is Boot (`System::Scene::m_scene_id == 1`); if not, it saves the next state in
`MenuData::m_boot_task_resume_state` (`DashSequenceEngine::m_menu_data`) and returns 0 = `_BootScene`. In the Boot scene,
`BootTask::onTaskStart` restores that state. Outside the Boot scene `onTaskStart` saves the enter code in
`MenuData::m_boot_task_enter_code`, and at the end `onTaskStep` returns it. So `BootScene-Default.bss` is part of the retail flow,
used when a boot check needs to show something; it is not a leftover even though its name is missing from `HashTable.saht`. (Which
checks need the Boot scene was not followed further.)

#### ProductMain

`ProductMain` (serial) is the game. Its children are `ClearRaceInfoTask` and eight of the scene proxies of the table in Finding 7
(all but `BootScene`).

`ClearRaceInfoTask` is the hub. It has 20 enter codes (`Boot`, `FromFriendList`, `DLC`, `Title_Top`, `SingleTA_Chara`,
`SingleTA_Course`, `SingleBB_Course`, `SingleBC_Course`, `MultiBB_Course`, `MultiBC_Course`, `MultiVS_Course`, `WiFi_Matching`,
`Single_Top`, `Multi_Top`, `WiFi_Top`, `FromTitleDemo`, `Commu_Top`, `Commu_Course`, `Commu_Lobby`, `DirectWiFi`) and the same 20
names as return codes. Its `convertEnterCodeImpl` and `convertReturnCodeImpl` map these names to the same enums 0..19, and
`ClearRaceInfoTask::onTaskMain`, after clearing race data according to the code, returns its enter code enum
(`return m_enter_code & 0xff`), so it returns the name it was entered with. `ProductMain`'s flow list maps each of these returns
to the `MenuScene` enter code of the same name. Every race, trophy or credits outcome that goes back to the menus is routed through
`ClearRaceInfoTask` with the name of the menu to reopen, for example `RaceScene` `SingleTA_Chara` -> `ClearRaceInfoTask`
`SingleTA_Chara` -> `MenuScene` `SingleTA_Chara`.

`MenuScene` returns `GP` -> `DemoScene` -> `RaceScene`; `MultiGP`, `VS_TA_Battle` -> `RaceScene`; `TitleDemo` -> `TitleDemoScene`;
`Back` -> `ProductMain` returns `BackToDebugMenu` -> `DebugMenuScene` (debug branch, Finding 9); the three error codes ->
`ClearRaceInfoTask`. `RaceScene` has one return code per outcome (39 codes such as `SingleGP_Next`, `SingleGP_Trophy`,
`SingleGP_WinRun`, `MultiVS_Course`, `WiFiBT_Exit`, `Debug_Retry`). The 36 that are not debug codes each have a flow entry to
`DemoScene` (`SingleGP_Next`, the intro of the next race), `RaceScene` again, `TrophyScene`, `WinningRunScene` or
`ClearRaceInfoTask`; the three debug codes have none (Finding 9). `TrophyScene` `SingleGPEnding` -> `EndingScene` ->
`ThankyouScene` -> `ClearRaceInfoTask` `Title_Top`.

#### The scene files

Every `.bss` root is a parallel sequence. In three of the retail scene files its layers are always-on pages and tasks (in
`MenuScene` `Page_Bg`, `Page_Timer`, `Page_UpBarControl`, `Page_CommonSystemDialog`, `Page_Fader` and two tasks; in `RaceScene`
and `TrophyScene` only the dialog and fader pages, and in `TrophyScene` one task) plus one serial sequence that holds the flow
(`Seq_Title` and its nested `Seq_Single`, `Seq_Multi`, `Seq_WiFi`, `Seq_Community`, `Seq_CH`, ... in `MenuScene`; `Seq_Race` in
`RaceScene`; `Seq_Trophy` in `TrophyScene`). The others have no serial sequence:

- `DemoScene`, `TitleDemoScene`, `WinningRunScene`, `EndingScene` and `ThankyouScene`: one page (`DemoPage`, `TitleDemoPage`,
  `WinningRunPage`, `EndingPage`, `ThankyouPage`) next to `Page_Fader`. The root enters the page and ends with the page's
  `Next00`.
- `BootScene`: `BootTask` next to `Page_CommonSystemDialog` and `Page_Fader`; the root enters the task with `_BootScene` and
  passes its returns on.

### 9. Debug and unused content

#### Debug entries of `Root-Default.brs`

- The root enter codes `DebugMenu`, `RaceScene`, `DebugKonishi`, `DebugNetwork`, `Viewer` and `Test`, and the matching
  `RootMain`/`BootTask` codes (`DebugMenu`, `DebugRace`, `DebugNetwork`, `DebugKonishi`, `DebugViewer`, `DebugTest`), cannot be
  produced (Finding 8). `BootTask::convertEnterCodeImpl` does not know the debug names and would treat them as `_BootScene`.
  (`DLC` is not debug; it belongs to the Download Play child.)
- The proxies `DebugMenuScene`, `DebugKonishi`, `Viewer`, `DebugRaceScene`, `SoundTestScene`, `DebugShiraiwa`, `DebugSuzuki`,
  `DebugObayashi`, `DebugKartRun`, `DebugField`, `DebugSakuraba` and `DebugChannelScene` are reached only from the debug enter
  codes, from each other, or through `ProductMain` returning `BackToDebugMenu`. Their scene names (`DebugMenu`, `SoundTest`,
  `DebugKonishi`, ...) are not in the scene dictionary and would open the Boot scene; `DebugRaceScene` uses `Race` and
  `DebugChannelScene` uses `Menu`.

`ProductMain` returns `BackToDebugMenu` in two ways: through `MenuScene` returning `Back` (its flow entry), or as its **default**
return code, when one of its children returns a code that has no flow entry. Neither happens in `eur2`: the first is shown below,
and the only unmapped returns of a child are the race's debug codes, which the retail game does not produce
([The race's debug menu](#the-races-debug-menu)).

#### `MenuScene` cannot return `Back`

Its root returns `Back` only through `Seq_Title` returning `Back` (ID 15 in the return code table of `Seq_Title`). The parallel
root's own default (also `Back`) needs every child done, and `Page_Bg`, `Page_Timer` and the other always-on pages never complete.
`Seq_Title` returns `Back` either through `Page_Title` returning `Back`, or as its default when a child's return code has no flow
entry. Both were checked:

- `Page_Title` is `MenuTitle`. Its `initControl` creates four buttons whose codes (`UI::BaseMenuButtonControl::m_return_code`) are
  0, 1, 2 and 3 (`Next00`..`Next03`: single player, multiplayer, online, StreetPass/channel). It creates no back button.
  `UI::BaseMenuButtonControl::completeNext` completes a page with the button's code (Finding 13). The only other completion in
  `MenuTitle` is the idle timer in `onPagePreStep`: after 0x708 frames (30 s) without input it completes with 7 (`Next07` -> title
  demo). No other function of `MenuTitle` calls through the `completePage` slot or calls a completion function. So `Page_Title`
  returns `Next00`..`Next03` or `Next07`, and all five have flow entries.
- Every return code that `Seq_Single`, `Seq_Multi`, `Seq_WiFi` and `Seq_CH` define (including their defaults) has a flow entry in
  `Seq_Title`. `Page_MMenCheck` (`MMenCheckPage`) returns the code it was entered with: `onPageEnter` stores
  `ExecutableSection::m_enter_code`, `onPagePreStep` completes with it through `BasePage::completeScene`, and its
  `convertEnterCodeImpl` / `convertReturnCodeImpl` map `EnterNN` and `ReturnNN` to the same enum. `Seq_Title` only enters it with
  `Enter00`..`Enter11`, whose matching returns are all mapped. `ClearRaceInfoTask` is only entered with `Title_Top` and returns it,
  which is mapped. `Seq_Title`'s own 20 enter codes all have an entry.

#### The race's debug menu

`RaceScene` has three debug return codes, `Debug_Retry`, `Debug_Exit` and `Debug_Reload` (`BaseRacePage::convertReturnCodeImpl`
enums 0x21, 0x22, 0x23), and `ProductMain` has no flow entry for any of them. Had one been returned, `ProductMain` would have ended
with its default, `BackToDebugMenu`, and opened `DebugMenuScene`: that is how a debug build went from a race back to the debug
menu. The code that produces them is in `RacePage`:

- `RacePage::genNextDebug` builds the debug end-of-race menu, a dialog (`bg_dialog`) with two `cmn_btn` buttons whose codes are
  0x21 `Debug_Retry` and 0x22 `Debug_Exit`.
- `RacePage::initControl` picks the set-up by `BaseRacePage::m_race_mode`: play modes 0 (single player) and 4 (replay) go to
  `initControl_SingleGP`, `initControl_SingleTimeAttack` or `initControl_SingleBattle`, play mode 1 (multiplayer) to
  `initControl_MultiGP`, `initControl_MultiVS` or `initControl_MultiBattle`, and play mode 2 (online) to `initControl_WiFiVS` or
  `initControl_WiFiBattle`, each by rule mode.
- Each of these eight functions contains a branch that builds the pause menu (`genPause`) and sets the code of its quit button
  (`PauseButtons::m_button_2` of `BaseRacePage::m_pause_buttons`) to 0x22 `Debug_Exit`; in all of them except
  `initControl_SingleGP`, the branch then calls `genNextDebug`. In `initControl_SingleGP` the branch comes right after the first
  call (`genRaceGP`); in the other seven it comes after the result menu has been built (`genResult`, `genResultTeam`,
  `genResultBT`, `genResultTA`, `genResultCommu` or `genResultWiFi`). The branch skips the rest of the normal set-up: the normal
  pause menu and the menu that follows the results (`genNext`, `genNextCommunity`, `genNextGP` or `genNextTA`). In
  `initControl_SingleGP`, `initControl_SingleBattle` and `initControl_SingleTimeAttack` it then returns; in the five multiplayer
  and online set-ups it joins the end of the function, which both paths run. On the normal path the quit button gets the mode's
  own code, for example 0x1C `WiFiVS_Exit` in `initControl_WiFiVS`. Every one of these branches is guarded by `mov r0, #0` /
  `cmp r0, #0` / `beq <normal path>`: a debug switch compiled to the constant 0. The branch is never taken in `eur2`, and `dlp`
  has the same guard (in `initControl_SingleGP` for example). Without it, the pause menu's quit button would return `Debug_Exit`
  (back to the debug menu), and the other seven set-ups would show the debug end-of-race menu after the results instead of the
  normal menu that follows them; `initControl_SingleGP` would build neither the results nor that menu (its branch returns before
  `genResult`).
- For play mode 3 (`Demo` in the template's `ERacePlayMode`, whose comment gives its uses as the title demo, the awards and the
  course preview), `RacePage::initControl` has a branch of its own, **without** that guard: it sets up the race display
  (`BaseRacePage` init functions), builds the pause menu with `genPause` and sets the quit button's code to 0x22 `Debug_Exit`. It
  does not call `genNextDebug`. `dlp` has the same branch. `RacePage` is only used by `RaceScene-Default.bss` (and the
  unreferenced `DebugRaceScene` and `E3RaceScene` files); the demo scenes use their own page classes (`DemoPage`, `TitleDemoPage`,
  `WinningRunPage`). Had a race of `RaceScene` run in play mode 3, quitting from its pause menu would have returned
  `Debug_Exit`, `ProductMain` would have ended with `BackToDebugMenu`, and `DebugMenuScene` would have opened the Boot scene.
  It does not happen in the retail game: see the next subsection.
- Nothing in `RacePage` or `BaseRacePage` loads 0x23 other than the compare in `convertReturnCodeImpl`, so `Debug_Reload` is not
  produced even by the dead code.

#### No race of `RaceScene` runs in play mode 3

A race page takes its play mode from the menu's race info: `BaseRacePage::initCommon`, which `RacePage::initControl` calls
first, copies `CRaceInfo::m_race_mode` of `GetRaceInfo()` (that is `MenuData::m_race_info`) into `BaseRacePage::m_race_mode`
(`ldr r0, [r6, #0x164]` / `str r0, [r4, #0x26c]`). In the code, the play mode of `MenuData::m_race_info` is written by:

- `BasePage::setRaceMode`, with the mode its caller passes. Of its 25 callers, the menu pages and tasks (`MenuSingle_Mode`,
  `MenuMulti_Mode`, `MenuWiFi_*`, `MenuChannel_*`, `MenuNetworkApplyTask::updateBattleMode_`, `Net::CommunityMgr::applyGameMode`)
  pass play mode 0, 1 or 2: a constant, or `MenuSingle_Mode::m_play_mode`, which `MenuSingle_Mode::onPageEnter` sets to 0, and the
  member at the same place of `MenuMulti_Mode` (a class without a file in `template/`), which `MenuMulti_Mode::onPageEnterCore`
  sets to 1. Play mode 3 comes only from `BaseMenuPage::applySetting_TitleDemo_Race`, `_BattleCoin` and `_BattleBalloon` (called
  by `MenuTitle::onPageComplete`, for the title demo) and `BaseMenuPage::applySetting_WinningRun` (called by
  `WinningRunSelectTask::onTaskMain`); the 25th caller, `DemoPage::onPageComplete`, is described below.
- `BasePage::setReplayMode`: play mode 0, or 4 for a replay (callers in `BaseRacePage::complete`).
- `BasePage::setDemoMode`: it first saves the current mode into `MenuData::m_demo_race_info`, then sets play mode 3 with rule
  mode 5 (`CoursePreview`). Its callers are `BaseMenuPage::applySetting_GP` (the start of a Grand Prix) and
  `BaseRacePage::complete` (going on to the next race of a Grand Prix). Both lead to `DemoScene`, the course intro, whose page is a
  `DemoPage`. `DemoPage::onPageComplete` passes the saved mode back to `setRaceMode` before `RaceScene` starts.

So play mode 3 is set only for the course intro, the title demo and the winning run, whose scenes use `DemoPage`,
`TitleDemoPage` and `WinningRunPage`, and the intro restores the mode before the race that follows it.

The running game agrees. In Azahar (`eur2`), a gdb watchpoint on the play mode of `MenuData::m_race_info` logged every write,
and a breakpoint on the store in `BaseRacePage::initCommon` logged the class and play mode of every race page set up, through:
the title demo (left to start by itself), a whole Grand Prix (Mushroom Cup, four races with their course intros, the winning
run, the trophy, back to the title), a time trial and a balloon battle. Results:

| Race page | Play mode | Rule mode | Set by (watchpoint) |
| --- | --- | --- | --- |
| `TitleDemoPage` | 3 | 6 (`DemoGrandPrix`) | `applySetting_TitleDemo_Race` |
| `DemoPage`, before each of the four races | 3 | 5 (`CoursePreview`) | `setDemoMode`, from `applySetting_GP` and then from `BaseRacePage::complete` |
| `RacePage`, each of the four Grand Prix races | 0 | 0 (`GrandPrix`) | `DemoPage::onPageComplete` |
| `WinningRunPage` | 3 | 4 (`Award`) | `applySetting_WinningRun` |
| `RacePage`, time trial | 0 | 1 | `MenuSingle_Mode::buttonHandler_OK` |
| `RacePage`, balloon battle | 0 | 3 | `MenuSingle_Mode::buttonHandler_OK` |

Every other write set play mode 0: `ClearRaceInfoTask::clearRaceInfo` on the way back to the title, and
`WinningRunPage::onPageComplete` after the winning run. No `RacePage` was set up with play mode 3, so the unguarded branch of
`RacePage::initControl` did not run. Multiplayer and online races were not run; the code gives them play mode 1 or 2 (above).

#### Other compiled-out branches

A scan of the whole code for the same guard (`mov rN, #0` directly followed by `cmp rN, #0`, the compare not being a branch
target) finds four more in sequence code, all in pages: `BaseRacePage::initCommon`, `BaseRacePage::onPageFadeout`,
`TrophyPage::onPagePreStep` and `EndingPage::onPagePreStep`. They were not followed: they are compiled-out options, but nothing
shows that they are debug features.

#### Unreferenced files

The unnamed files other than `BootScene-Default.bss` are not referenced by the retail flow:

- the debug `.bss` files listed in Finding 1. `DebugMenuScene-Default.bss` holds a `DebugMenuSeq` with pages whose classes
  (`DebugMenuMainPage`, `DebugSelectPage`, `DebugNetworkPage`, `DebugDaemonSettingPage`, `DebugCecPage`, `DebugBossPage`,
  `DebugTrophySelectPage`, `DebugMsgPage`) are not registered. The per-developer files, `SoundTestScene` and `Viewer` hold a
  single `BackToDebugMenuPage` (`DebugShiraiwa` also has `DebugCapturePage`). None of these classes exist in `eur2`, so they would
  be built as `DummyPage`. `DebugMenuScene` return code 21 is spelled `Titlle`.
- `E3MenuScene`, `E3RaceScene`, `E3Trophy`, `E3ThankYou`: the E3 demo flow (pages `E3Title`, `E3CharaSelect`, `E3PartsSelect`,
  `E3Trophy`, `E3ThankYou`, not registered). The first three also have a `RootReset` task layer (`RootResetTask`, which is
  registered and used nowhere else). Only `DebugMenuScene` names an `E3` return, and no flow consumes it.
- `UDSMatchingTest`, `WifiMatchingTest`: one `BackToDebugMenuPage` each.
- `SceneTestRoot-Scene.brs`: a minimal root (`SceneTestSeq`: `BootTask` -> `DebugMenuScene` -> `DebugRaceScene`). The root name
  and mode are fixed in code, so it is never loaded.

### 10. The system dialog and network errors

#### The dialog page in a scene

`Page_CommonSystemDialog` (class `Common_SystemDialog`) is a child of the root parallel sequence of `MenuScene`, `RaceScene`,
`TrophyScene` and `BootScene`. No flow entry enters it (in the flow graph it only has the dashed "(always)" arrow, Finding 15): a
parallel sequence starts every child with the scene, so the dialog page lives on its own layer for the whole scene with its
default enter code (`Multi`), invisible until some code opens a window in it (`Common_SystemDialog::startSystemWindow`,
`Sequence::OpenDialog`, as `BootTask` does). Opening and closing windows does not complete the page: its buttons get the special
codes -2 and -3 (`onMenuEnter`, `fadeInWindow_` and the button creation functions), which
`UI::BaseMenuButtonControl::completeNext` turns into calls to page virtuals instead of a completion (Finding 13). The only call
through the `completePage` slot in the class is in `onPagePreStep`. So the page only completes when a network error has been fully
handled.

What its completion does depends on the scene. The roots of `MenuScene`, `RaceScene` and `TrophyScene` map both of its error codes
to a return code of the scene ([Where the codes lead](#where-the-codes-lead)). The root of `BootScene` does not: its flow list
holds the entry that enters `BootTask` and nine entries from `BootTask`'s returns, none from the dialog page. By Finding 5, a
completed dialog page would only be marked done there, and the scene would go on until `BootTask` returns (the root's default
return code, 1, is used only once no child is still running). The network error check, which the next subsection describes, is not
switched off in `BootScene`: the constructor and `onPageEnter` set `Common_SystemDialog::m_check_network_errors`, and
`onPagePreStep` runs the check in every scene. `BootScene` is entered only from `RootMain`, through `BootTask`, before
`ProductMain` starts (Finding 8). Whether a network error can be pending at that point was not followed;
`NetworkErrorHandler::handleError` is called from the network code, which was not traced for the boot checks.

#### How a network error completes the page

1. `Common_SystemDialog::onPageEnter`, when `Common_SystemDialog::m_check_network_errors` is set, points the checker at
   `NetworkEngine::m_network_error_handler` and resets `NetworkErrorChecker::m_state` to `WATCH`. It then sets
   `Common_SystemDialog::m_error_return_code` to 1 and sets `m_check_network_errors`. The constructor sets that flag too, and
   many pages write it through `MenuData::m_common_system_dialog` (`MenuTitle::onPageComplete` clears it, for example); which
   pages turn the checks on or off was not followed.
2. Every frame while running and while `m_check_network_errors` is set, `Common_SystemDialog::onPagePreStep` calls
   `NetworkErrorChecker::calc`. When `calc` returns true, the page completes with `Common_SystemDialog::m_error_return_code`
   through the `completePage` slot, unless a flag of another engine is set (the same flag that `SceneSequenceProxy::updateState`
   and `SystemEngine::calcBeforeStructure` test; not identified).
3. `calc` is a state machine (`NetworkErrorChecker::EState`). State 0 (`WATCH`) waits until all pages are running and no fade is in progress, then looks at the error
   handler. An error is pending when `NetworkErrorHandler::m_error_kind` is not 0 while `NetworkErrorHandler::m_error_code` is
   below 3, or when `m_error_code` is 3 or more; only in the first case is the kind copied into
   `NetworkErrorChecker::m_error_kind`. It then disables input and, unless a handler flag is set, calls `startDisconnect_`. The
   next states show the error window, wait for the disconnection and for the player to close the window, and fade out. In state
   7 (`SELECT_RETURN_CODE`) it chooses the return code: **2 (`SimpleError`) if `NetworkErrorChecker::m_network_mode == 1`
   (`WIFI`) and `NetworkErrorChecker::m_error_kind == 5` (`STAND_ALONE`), else 1 (`Error`)**. It then resets the network error
   (`NetworkEngine::resetError`) and returns true in state 9 (`DONE`).
4. `startDisconnect_` copies `NetworkEngine::m_network_mode` into `NetworkErrorChecker::m_network_mode` and makes the same test:
   `Net::NetworkSelectMenuProcess::disconnectNetwork()` for the `SimpleError` case (leave the session only), otherwise
   `disconnectNetworkAll()` (disconnect completely).
5. Error kind 5 is written by `Net::NetworkEngine::checkStandAlone`, when no other error is pending and the player is left alone:
   the other stations are gone, or, with `NetworkEngine::m_network_mode == 1`, `WifiMatchingManager::checkSessionIsOrphan` says
   the online session has no one else left. So `SimpleError` means "the others left you, online", and every other network error
   (your own connection, or any error in local wireless play) is `Error`.

`NetworkErrorHandler` is allocated with 0x4C bytes in `NetworkEngine::createBeforeStructure`, and `NetworkErrorHandler::handleError`
writes up to +0x4B; the template's size of 0x40 was wrong and is corrected by the patch.

#### Where the codes lead

The return codes then follow the files. The numbers in parentheses are code IDs: those of the dialog page's return code table,
which are the same in every scene, and those of the return code table of each scene's root. `BootScene` is not in the table: its
root has no flow entry for the dialog page.

| Scene | Dialog `Error` (6) | Dialog `SimpleError` (7) |
| --- | --- | --- |
| `MenuScene` root | -> `MultiError` (16) | -> `WifiError` (17) |
| `RaceScene` root | -> `MultiError` (39) | -> `WifiError` (40) |
| `TrophyScene` root | -> `Error` (9) | -> `SimpleError` (10) |
| `ProductMain` | -> `ClearRaceInfoTask` `Title_Top` -> `MenuScene` `Title_Top`: **title screen** | -> `ClearRaceInfoTask` `DirectWiFi` -> `MenuScene` `DirectWiFi` -> `Seq_Title` `DirectWiFi` -> `Seq_WiFi` `DirectOpponent` (enter code 8): **online menu** |

So, as read from the code and the files (not tested in game), the player lands on the title screen after a communication error,
unless the error was that the others dropped out of an online session, in which case the game goes back to the online menu.

### 11. What a scene change does

#### Scenes are a stack of sead tasks under a permanent root scene

- `System::Scene` is a `sead::UlcdTask`. Its constructor stores the current scene in `Scene::m_previous_scene` and makes itself
  the current scene of the `SceneManager`. The destructor makes `Scene::m_previous_scene` current again.
- `RootScene` is created once and never leaves. `RootScene::sceneCalc` runs the sequence engine (`Object::Actor::calcOuter` on the
  sequence engine), so `Root-Default.brs` and everything above the scenes (`Root`, `RootMain`, `ProductMain`, the proxies,
  `MenuData`) live in the root scene, for the whole session.
- `SceneManager::changeChildScene(id)` only writes `id` into `Scene::m_child_scene_id` of the current scene.
  `SceneManager::exitScene` only sets its `Scene::m_is_exiting_scene`. `Scene::calc` acts on them: a pending child ID is turned
  into `sead::TaskBase::requestPush` (a new task for that scene, below the current one), and the exit flag into
  `sead::TaskBase::requestPop` (the scene task removes itself).

#### One change, step by step

For example `ProductMain` going from `MenuScene` to `RaceScene`:

1. The `MenuScene` proxy completes in `ProductMain` with the return code of its `.bss` root (Finding 7). `ProductMain` finds the
   flow entry and finishes the proxy (state 7).
2. `SceneSequenceProxy::finish` passes the finish to the root of the `.bss`, which fades out its pages. When the root has exited,
   `SceneSequenceProxy::updateState` clears it and starts a short exit timer, after two further checks on other engines that were
   not identified. `SceneSequenceProxy::step` then waits for the scene's sound to finish fading out
   (`Sound::SndEngine::isSceneFinishedFadeOut`, for at most 180 frames) and calls `exitScene`.
3. The menu scene task pops. `GameScene::exit` runs:
   - `ThreadManager::safetyQuit`;
   - `SequenceEngine::sceneFinish`, which reaches the proxy: `SceneSequenceProxy::sceneFinish` destroys the `SceneSequence` of
     `MenuScene-Default.bss` (`SceneSequence::destroy`), with all its sections and its loaded file;
   - the scene-finish call of each root engine;
   - `Scene::exit`, which frees the draw heaps;
   - `ResourceLoader::destroyList`.

   The task and the scene's own engines are then destroyed with it.
4. With its scene sequence gone, the proxy exits (state 8). `ProductMain` clears it, attaches the next child (the `RaceScene`
   proxy), readies it and enters it with the destination code of the flow entry.
5. `SceneSequenceProxy::ready` calls `changeChildScene(Race)` on the current scene. That is the root scene once the old scene's
   destructor has run; the exact frame order of that destructor against this call was not traced. The root scene pushes the race
   scene task.
6. `GameScene::prepare` builds the new scene:
   - waits for the GPU and creates the resource list (`ResourceLoader::createList`);
   - selects the UI archive of the sequence engine from the scene ID: Menu -> `UI_MENU`, Race -> `UI_RACE`, Trophy ->
     `UI_TROPHY`, Thankyou and Ending -> `UI_ENDING_AND_THANKYOU`, otherwise `ROMFS_ROOT`;
   - calls `SequenceEngine::sceneStart(id)`, which makes the waiting proxy create the `SceneSequence` and load its `.bss`;
   - runs `Scene::prepare`;
   - calls the scene-start hook of four root engines (`GameScene::callRootEngine` with the engine types System, Sound, Effect and
     `_9`);
   - creates this scene's engines from the `.bss` engine creator table (`SceneSequence::createEngines`: camera, render and
     character);
   - initialises them, loads the scene's sound data, creates the sections of the `.bss` (`SceneSequence::createSections`),
     calls `Net::NetworkEngine::sceneStart` and creates the draw heaps (`Scene::createDrawHeap`).
7. When the new root section is free, `SceneSequenceProxy::updateState` calls `SceneSequence::init` with the proxy's enter code
   ID, and the scene starts (Finding 7).

#### The memory clear

`Scene::prepare` loops over the two heaps of the scene task. For each, it allocates the whole free space (`getFreeSize`, then
`alloc`), clears it with `__rt_memclr`, and frees it again. So every scene task has its own heaps, and each new scene starts by
zeroing all the free memory in them. That the heaps themselves are freed with the task when it pops is how sead tasks work; it was
not traced in `eur2`.

#### What survives a scene change

- Everything in the root scene survives: the `.brs` sequence, the sequence engine with `MenuData`, and the other root engines
  (System, Mii, Sound, Network, Effect).
- What belongs to the scene is gone: its `.bss` sections, its camera, render and character engines, and its draw heaps.
- Information crosses in two ways:
  - **Codes, through the `.brs`.** The old `.bss` root's return code becomes the proxy's return code (by ID). `ProductMain`'s flow
    entry maps it to the next child and an enter code, and that enter code becomes the new `.bss` root's enter code (by ID). So
    the next scene does not start with the previous scene's return code itself, but with the code that the flow entry pairs with
    it. Often the names match because the files are written that way (`RaceScene` `SingleTA_Chara` -> `ClearRaceInfoTask`
    `SingleTA_Chara` -> `MenuScene` `SingleTA_Chara`).
  - **Data, in the root engines.** For example `MenuData`, in the sequence engine, with the menu state and the race settings
    that the menus build (`MenuData::m_race_info`, Finding 9), and the save data, which the system engine holds
    (`System::GetSaveDataManager` reads it from there).

### 12. How the game ends

`ProductMain` has one return code, `BackToDebugMenu`, reached through `MenuScene` returning `Back`, which `eur2` never does
(Finding 9). It is also its default return code, so any unmapped return of a child would end there too; the only unmapped
returns are the race's debug codes, which the retail game does not produce ([Finding 9](#the-races-debug-menu)). So in retail
`ProductMain` most likely does not end (both points are listed as likely in [Confidence](#confidence)): the game keeps going
round between the menu and the other scenes.

The game ends through the other layer of the root parallel sequence, `RootExit` (`RootExitTask`):

- `RootExitTask::onTaskStart` stores the task in `DashSequenceEngine::m_root_exit_task` and returns -1, and
  `RootExitTask::onTaskStep` always returns -1, so it waits forever.
- `RootExitTask::exitApp`, when the task is running, completes it with its return code enum 0 and sets
  `DashSequenceEngine::m_exit_app`. `RootExit`'s return code table has a single code, `End`, which is also its default.
- `exitApp` is only called by `Sequence::ExitApp`, which calls it on `DashSequenceEngine::m_root_exit_task` when that is set.
  `Sequence::ExitApp` has two callers:
  - `SystemEngine::calcBeforeStructure` sets `SystemEngine::m_is_close_requested` when
    `nn::applet::CTR::detail::GetOrderToCloseState` or `nn::applet::CTR::IsReceivedWakeupByCancel` returns non-zero (both read a
    byte of the same applet state; the names are those of the `dlp` functions called at the same place, where they read other
    bytes of that state). Once that flag is set, no save is in progress (`Sequence::IsSaveWorking()` is false) and
    `SystemEngine::m_is_exit_started` is clear, it calls `Sequence::ExitApp` and sets `m_is_exit_started`.
  - `ProjectGameFramework::gpuSleepProc` calls `SystemEngine::startExit` under a condition that was not followed; `startExit`
    calls `Sequence::ExitApp` and sets `m_is_exit_started` unless it is set already.

  These are most likely the application-close requests (HOME Menu close, the POWER button); what the applet state bytes mean was
  not checked.
- `RootExit` returning `End` completes the root parallel sequence with `End`, which is the end of the whole flow.

### 13. How button controls complete pages

Pages almost never call `completePage` themselves. They create button controls (`UI::BaseMenuButtonControl` and subclasses:
`TitleButton`, `RaceBasicButton`, `SystemDialogButton`, `BackButton`, `BackButtonB`, `BackButtonT`, ...) and give each button the
return code it stands for. Pressing the button completes the page with that code.

#### Input

Three handlers of `UI::BaseMenuButtonControl` end with a tail call (`b`) to `completeNext`:

- `touchHandlerUp` (touch released on the button);
- `keyHandlerCommon` (a key the button reacts to, per its `UI::BaseMenuButtonControl::m_active_handlers`);
- `keyHandlerCursorA` (A on the button under the cursor).

`UI::BackButtonT::onKeyHandlerB` (a `nop` and a branch to `keyHandlerCommon`) binds the B key to a back button in the same way.

#### `UI::BaseMenuButtonControl::completeNext`

It chooses a code:

1. `code = UI::BaseMenuButtonControl::m_return_code`. The constructor sets it to 0, so a button nobody configured reports the
   page's first code (`Next00` on menu pages).
2. If the page's menu is in state 3 (`BasePage::m_menu_state`, the overlay menu that `openMenu` shows) and
   `UI::BaseMenuButtonControl::m_on_complete_next_mode` is not -1, that value is used instead. A button can therefore act
   differently while the page's menu is open.
3. If the button has handler flag 0x1000 and `MenuData::m_selected_option` is 1, the code becomes -2 (why the button tests that
   member was not traced).
4. If `m_return_code` is -1 (and, while the menu is open, `m_on_complete_next_mode` is -1 too), the button does nothing.
   Otherwise the code is applied (`ECompleteNextMode` in the template for the negative values):

   | Code | Effect |
   | --- | --- |
   | -2 | page virtual `procOpenMenu`: opens the page's menu; also sets `UI::BaseMenuButtonControl::m_0x220` |
   | -3 | page virtual `procCloseMenu`: closes it |
   | -4 | only sets `UI::BaseMenuButtonControl::m_0x220` (meaning not traced) |
   | 0 or more | `Sequence::BasePage::completeNext(page, code)` |

5. If `UI::BaseMenuButtonControl::m_selected_option_idx` is 0 or more, it also calls the page virtual `buttonHandler_OK` (name from
   the template).

#### `Sequence::BasePage::completeNext`

`Sequence::BasePage::completeNext` only acts while the page is running (state 5). Then it calls the page's `completePage` virtual.

#### `Sequence::Page::completePage`

`Sequence::Page::completePage`:

- refuses to complete while a network error is pending: if `NetworkErrorHandler::m_error_kind` is not 0 and the system dialog
  registered in `MenuData::m_common_system_dialog` is another page whose `Common_SystemDialog::m_check_network_errors` is set, it
  returns without completing. The dialog handles the error and its own completion decides the flow (Finding 10);
- otherwise calls `ExecutableSection::setReturnCodeEnum(code)` (Finding 4) and blocks input (`UI::ManipulatorManager`: a flag
  set, then `clear`), so no second button can fire while the page fades out.

#### From button code to flow entry

The code is the page class's return code enum. For every `BasePage` page, `BasePage::convertReturnCodeImpl` names it: 0..7 ->
`Next00`..`Next07`, 8 -> `Back`. `setReturnCodeEnum` looks the name up in the page's return code table and completes with that
ID, which the parent's flow list maps to the next section. `BaseMenuPage::getBackReturnCode` returns 8 and
`BaseMenuPage::getBackEnterCode` returns 1 (`Back` as an enter code, `Next` = 0). Where each page assigns the back code to its back
button was not traced.

#### Examples

- `MenuTitle` gives its four buttons the codes 0, 1, 2, 3, so the title screen returns `Next00`..`Next03` (Finding 9).
- `RacePage::genNextDebug` gives its two buttons 0x21 `Debug_Retry` and 0x22 `Debug_Exit` (`BaseRacePage` has its own, longer
  return code enum).
- `Common_SystemDialog` only uses -2 and -3, so its buttons never complete the page (Finding 10).

#### Other ways pages complete

Some pages complete in other ways: the `MenuTitle` idle timer (Finding 9); `MMenCheckPage`, whose `onPagePreStep` calls
`BasePage::completeScene` and whose `completePage` override falls into it (Finding 9); and `BaseRacePage::calcRace`, which calls
`BasePage::completeNext` itself.

### 14. Editing the files

What the code requires, in the order a modder meets it.

#### Names

The root is always `Root-Default.brs` (Finding 1). A scene file is `<proxy section name>-<proxy block mode name>.bss`, in
`UI/common.szs`. A new scene file needs a new proxy section, not a new scene ID: the scene ID only picks the kind of scene (Boot,
Menu, Race, Trophy, Thankyou, Ending, Demo; any other name gives Boot; Finding 7).

#### Header counts

`BSEQ::m_num_sections` = serial + cross fade + parallel + delegate + proxy pools + the sum of
`PracticalSectionBlock::m_num_instances`, exactly (Finding 3). Each pool must cover the most sections of that class active at once
(the root is one parallel), with some slack if a free section can be left on a layer it cannot be reused from.
`BSEQ::m_num_layers` >= the largest subsection count of any parallel block, the root included. `BSEQ::m_root_mode_id` = the root
block's `SequenceBlock::m_mode_id`. `BSEQ::m_num_section_block` = the number of offsets. The other header fields are not read;
keep them as the game writes them (4, 1, 0, 0, end of the offset table; Finding 2).

#### Section IDs

Any `u32`, unique per file (a sequence may reuse an ID for another mode). The root's ID is `BSEQ::m_sequence_id`. The game's IDs
look like hashes, but nothing checks them (Finding 3).

#### Types

`SectionBlock::m_section_type` decides the class for sequences (3-7) and which registry is searched for practical sections (0-2);
`SectionBlock::m_block_type` must match the layout (0/1 practical, 2 sequence, 3 cross fade, 4 proxy). The root's type byte is
ignored (Finding 2).

#### Pages and tasks

The class name must be one of the 91 registered names. Otherwise the section silently becomes a dummy, which never completes, so a
serial sequence stops there for good (Finding 3). The names of its enter codes, return codes and modes must be the strings of that
class's `convert*Impl`; IDs are free, but every table needs a default ID that exists in it (Finding 4). To reuse a class in
another place, copy its tables from a section that uses it.

#### Flows

Edit flow entries to relink menus: `{src_index or -1, src_code, dst_index or -1, dst_code}`, the codes being IDs of the source's
return table (or of the sequence's enter table for -1) and of the destination's enter table (or the sequence's return table for
-1). The first matching entry wins. To reach the same section with different follow-ups, list it several times in the subsection
list (Findings 2 and 5).

#### Proxy and `.bss` root

Keep the code IDs of the proxy's enter and return tables equal to those of the `.bss` root (Finding 7).

#### Strings

Every name is a `u16` offset into the string table, so a file can hold at most 64 KiB of strings; offsets inside a section block
are `u16` too (Finding 2).

### 15. The flow graph tool

`bseq_flow_graph.py` (Python 3, Pillow) draws a scene and menu flow made of BSEQ files. `game_flow.png` is its output for `eur2`,
made with the game profile `mk7_eur2_profile.json`:

```
mk7-llm-research/local/venv/bin/python mk7-llm-research/final/scene-sequence-bseq/bseq_flow_graph.py \
    --profile mk7-llm-research/final/scene-sequence-bseq/mk7_eur2_profile.json
```

Options: `--dir` (folder with the BSEQ files, default `mk7-llm-research/local/romfs/eur2/rom/UI/common.szs.d`), `--profile`,
`--root NAME-MODE`, `--out`, `--all`.

#### What comes from the files and what comes from the profile

The tool itself knows only the BSEQ format and the engine rules of this document. Everything specific to a game is in the profile
(JSON, every part optional, each with the `eur2` source it was read from):

| Profile entry | Used for | Without it |
| --- | --- | --- |
| `root_file` (name, mode) | which `.brs` to start from | `--root`, or the only `.brs` of the folder |
| `root_enter_codes` (`produced`, `notes`) | ENTER box of the root; root entries never produced are drawn as unused | all root entries drawn as normal |
| `scenes` (`ids`, `default`) | "scene NAME (ID n)" on proxies and frames; names not in the table "fall back to DEFAULT (ID n)" | "scene NAME" only |
| `classes` (`pages`, `instant_tasks`, `lasting_tasks`, `data_holders`) | instant / lasting task colours; unregistered class names drawn as dummies | page / task / data holder by section type only |

The scene ID is therefore not read from the BSEQ files: a proxy only names a scene (`Race`), and the game turns the name into an
ID with its own table (`DashSceneIDConverter` in MK7, Finding 7). `DemoScene`, `RaceScene`, `TitleDemoScene` and
`WinningRunScene` all show ID 3 because their four proxies all name the scene `Race`. Names that are not in the table, such as
`BootScene` or `DebugMenu`, get the converter's default, so the image says "scene BootScene: not a scene name, falls back to
Boot (ID 1)".

#### Panels and frames

- The tool starts at the root of the root file and follows every sequence and every scene proxy (`<name>-<mode>.bss`). Files with
  no known name are found by the SARC hash of `<name>-<mode>.<ext>`, the way the game builds the names. Each sequence is one
  panel. A child that is itself a sequence or a scene says `see [n]`, and each panel says which panels use it. `--all` also draws
  the BSEQ files that the drawn flow never loads.
- The panels are grouped the way the scenes are stacked at run time (Finding 11):
  - a **root scene** frame (dark) holds the panels of the root file, which run in the permanent root scene;
  - each **game scene** frame (red) holds the panels of one `.bss`. Its title gives the scene and the file; its subtitle gives
    the panel whose proxy pushes it and the engines it creates;
  - files that are never loaded get a grey frame (with `--all`).
- Inside a frame the panels follow the nesting of the sequences. Each one is indented by its depth and joined to the panel that
  holds it by a guide line, which runs down from the bottom of that parent panel. Its subtitle gives its path from the file's
  root (`MenuScene › Seq_Title › Seq_Single`). The border of a panel has the colour of its sequence kind, purple for parallel and
  green for serial. Panels are numbered in this order.
- A frame is a scene file, not a parallel sequence. Every file's root is a parallel sequence (the loader forces it, Finding 2),
  but parallel sequences also occur inside a scene (`Para_TAChart` and `Para_CH` in `MenuScene`), and the root of
  `Root-Default.brs` is a parallel sequence that is not a game scene.

#### Boxes and arrows

- Box shapes tell the kinds apart besides their colours: a scene proxy is a stack of cards (it pushes a scene), a serial sequence
  has a solid side band (one lane), and a parallel sequence a striped side band (several lanes).
- ENTER stands for the sequence's own enter codes and RETURN for its own return codes. Every ENTER box says which panel the
  sequence is entered from ("from [n] Parent") and every RETURN box which panel it returns to ("to [n] Parent"). The parent is
  the panel that holds the sequence; for a file root it is the panel holding its proxy. The game root shows instead the enter
  codes the game starts it with (from the profile), and its RETURN "ends the flow".
- An entry from ENTER to a box far to the right, or from a box far to the left into RETURN, ends at a local ENTER or RETURN box
  placed next to that box instead of crossing the panel, so a panel can show several of each. They carry the same "from" / "to"
  line.
- Every flow list entry is an arrow, labelled `source code -> destination code` and resolved the way the game does it: an ID
  missing from its table shows the table's default followed by `?`. Several entries between the same two boxes share one arrow
  and one label, with one line per entry in three aligned columns: the return codes on the side of the source box, the arrows in
  the middle, and the enter codes on the side of the destination box (so in a backward label the return codes are on the right).
  An entry that restarts the same child is listed inside the box as `self:`. A dot on each side of a label box marks where its
  arrow passes through it. Every arrow ends at its own point on the side of a box, ordered by where the arrow goes, and boxes
  with many arrows are drawn taller.
- Arrow kinds:

  | Arrow | Term | Meaning |
  | --- | --- | --- |
  | dark | flow entry | a return code of the source starts the destination with an enter code |
  | orange | backward flow entry | a flow entry to an earlier column; its label is written `destination code <- source code` |
  | teal | enter flow entry | an enter code of the sequence itself (from ENTER) starts the destination |
  | dashed teal | implicit start | a parallel child that no entry targets, started with its default enter code |
  | light grey dashed | unused flow entry | a root enter code the game never produces (needs a profile) |

- The legend uses one `term: definition` format for frames, boxes, arrows, labels and markers, without examples or game-specific
  names, so it also fits other games that use BSEQ.

#### Layout

The image is large: 7717 x 18943 pixels, 37 panels in 22 frames (the root scene and 21 game scenes; 46 panels with `--all`). The
layout is a layered one:

- columns come from longest-path layering, and long edges are routed through placeholder points;
- box order: barycentre sweeps keep the order with the fewest crossings, then neighbouring boxes are swapped while that removes
  crossings;
- each label box takes the free height nearest to its arrow, avoiding the heights where other arrows cross that column, so lines
  do not run hidden behind unrelated labels.

`Seq_Community` stays busy because its flow really is dense: many pages lead to `MenuNetworkApplyTask`.

### 16. Differences from the hint sources

#### EveryFileExplorer (`BSEQ.cs`)

- Header: `InitialSequenceID2` is `m_root_mode_id`; the rest is read as unknowns. It reads the offset table right after the header
  (correct).
- It reads the first `u32` of a section block as the section type; only the first byte is the type.
- It names block types 0 = `PracticalSectionTask`, 1 = `PracticalSectionPage`: this matches the files, but the code does not use
  the difference.
- Practical block: `SequenceID2` is `m_num_instances`, `PracticalName` the class name (correct).
- Sequence block: `SequenceID2` is `SequenceBlock::m_mode_id` and `SequenceName` is the **mode** name, not a class or sequence
  name.
- Proxy block: `Count` ("always 1") is `SceneSequenceProxyBlock::m_mode_id`, `UnknownName` the mode name; `SceneName` is correct.
- Flow entries: src/dst with -1 for the sequence itself (correct). It has no cross fade block.

#### MK7-Binary-Scripts (`MK7_BSEQ_analyser.py`)

- Header field names match the code except `num8` (= `m_root_mode_id`), and `sectionBlockArrayOffset` (+0x34) is the first entry
  of the offset table, not an offset to it.
- The section block `struct` format (`<bBHIHHHbHB`) does not follow the layout: it reads `m_block_type` as a signed byte at +0x0E
  and the block offset at +0x0F, which it then byte-swaps to get the right value.
- `classNameTableOffset` of sequence and cross fade blocks is the mode name; `modeNameItemIndex` is a mode ID.
- Flow entries are named prev/next; they are source/destination, and for a sequence the source code is an enter code when the
  source is -1.
- Cross fade flow entries of 0xC bytes with a type: confirmed by the code. Root type 8: written in the file but never read for the
  root.

The pre-existing template comments that this research corrects are covered by the patch.

## Confidence

- Certain (read in `eur2`): the file layout and every field marked as read; the file names and where they come from; pools,
  layers and `m_num_sections`; class lookup and dummy fallbacks; the list of registered classes; code lookups and defaults; serial,
  parallel and delegate flow semantics; the proxy/`.bss` boundary by ID; the scene dictionary and its default; engine creator
  modes; the root enter code in `eur2` and `dlp`, and how `GameSetting::m_is_from_friend_list` is set and cleared; the names of
  the 20 unnamed files (hash matches); that dummy pages, tasks and data holders never complete; that the debug branches of the
  eight `initControl_*` functions are behind a constant-false guard; how the system dialog chooses `Error` or `SimpleError`; the
  exit path through `RootExitTask`, `Sequence::ExitApp` and `SystemEngine`; the size of `NetworkErrorHandler`.
- Confirmed by the user: `DLC` = Download Play child.
- Likely:
  - that `BootScene-Default.bss` is used only when a boot check needs the Boot scene (the state machine was followed for its
    exits, not for every check);
  - that the out-of-range cases of Finding 3 crash, and that a free pool section left on another layer cannot be reused (read
    from the code, not tested);
  - that `MenuScene` cannot return `Back` (the check covers `MenuTitle`'s own code and every flow entry; a completion of
    `Page_Title` triggered from outside `MenuTitle`, through the `completePage` virtual, would not be seen);
  - that nothing reads `field_0x0A`, `field_0x0C`, `field_0x20`, `field_0x24` and `m_first_section_block_offset` (pattern scans,
    Finding 2);
  - the names `GetOrderToCloseState` and `IsReceivedWakeupByCancel` (the `dlp` functions called at the same place, reading other
    bytes of the applet state), and that the exit path serves the application-close requests;
  - that no race of `RaceScene` runs in play mode 3, so the unguarded `Debug_Exit` of `RacePage::initControl` is never set
    (Finding 9): every caller of the three setters of the play mode was read, and the game was watched in the title demo, a
    Grand Prix with its intros and winning run, a time trial and a balloon battle; multiplayer and online races were not run,
    and a write outside the setters in flows that were not run would not have been seen.
- Unknown: the meaning of `field_0x0A` (4) and `field_0x0C` (1), and what `SystemEngine::m_is_title_page_active` and
  `SystemEngine::m_title_sleep_flag` change in the sleep code.
- Partly read: `CrossFadeSequence` (`enter`, `changeSubsection` and the flow lookup of `updateState`; no file uses it).

## Open questions

- What `field_0x0A` and `field_0x0C` mean. No code reads them; files written by another tool or for another game on the same
  engine (the hint scripts mention Nintendogs + Cats, and an E3 2010 version of the format) might show other values.
- What the other constant-false branches in sequence pages (Finding 9) would enable.
- What `SystemEngine::m_is_title_page_active` and `SystemEngine::m_title_sleep_flag` change in the sleep code, and why
  `SequenceEngine::init` clears them for a `DLC` or `FromFriendList` start.
- The condition under which `gpuSleepProc` calls `SystemEngine::startExit`, what the applet state bytes read by the two
  `nn::applet` getters mean, and the flag of another engine tested by `Common_SystemDialog::onPagePreStep`,
  `SceneSequenceProxy::updateState` and `SystemEngine::calcBeforeStructure`.
- Which pages turn `Common_SystemDialog::m_check_network_errors` on and off through `MenuData`, and when (Finding 10).
- Whether a network error can be pending while `BootScene` runs, so that its dialog page completes there (Finding 10).
- The frame order of a popped scene's destructor against the next proxy's `changeChildScene` (Finding 11).
- The other values of `NetworkErrorHandler::EErrorKind`, `NetworkEngine::ENetworkMode` and `NetworkErrorChecker::EState`,
  the values of `BootTask::EState`, and the members of `NetworkErrorHandler` between 0x44 and 0x4B.
- The full map of `MenuScene-Default.bss` (90 blocks) was not written out; only its structure is described.
