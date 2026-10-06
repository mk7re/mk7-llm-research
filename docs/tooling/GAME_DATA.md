# Game data files

The game's data files as `mk7 romfs extract` lays them out, how the game mounts its two archives, and how the course
data (KMP) and scene sequences (BSEQ) are dumped. Every argument of these commands is in
[cli/gamedata.md](cli/gamedata.md).

## Contents

- [The extracted RomFS](#the-extracted-romfs): folder layout, `.szs.d` folders, the hash table of file names
- [How the game uses the two archives](#how-the-game-uses-the-two-archives-eur2): `rom:`, `pat1:` and the `Patch/`
  overrides
- [KMP (course data)](#kmp-course-data): what `mk7 kmp` reads and how to read its dump
- [BSEQ (scene and menu sequences)](#bseq-scene-and-menu-sequences): what `mk7 bseq` reads and how to read its dump

## The extracted RomFS

`mk7 romfs extract` writes the contents of every RomFS of the image to
`mk7-llm-research/local/romfs/<image>/<mount>/`, so for the target:

```
mk7-llm-research/local/romfs/eur2/
  rom/                 rom:/   the base game
    Common.szs         a file of the RomFS, kept as it is
    Common.szs.d/      the files inside Common.szs
    Menu3D/            a folder of the RomFS
    Course/Gctr_DKJungle.szs, Course/Gctr_DKJungle.szs.d/, ...
  pat1/                pat1:/  the update data
    Patch/Course/<course>/<course>.kmp, Patch/UI/<archive>/<file>
```

- **A folder ending in `.szs.d` is the unpacked content of the `.szs` file of the same name beside it; it does not
  exist in the game.** Every other file and folder is in the RomFS exactly as shown.
- A `.szs` file is a Yaz0-compressed SARC archive. The archives of this game store only the hash of each file name.
  Names are looked up in `mk7-llm-research/tools/mk7re/static/data/HashTable.saht`, a hash table in the format of
  [EveryFileExplorer](https://github.com/PabloMK7/EveryFileExplorer); to update it, replace the file with a newer one
  and run `mk7 romfs extract` again. A file whose hash is not in the table is named after its hash (`0x7ECE0B7D`).
- The command does nothing when the output is up to date with the RomFS files and the hash table; `--force` extracts
  again.
- The output is a copy for reading. Never edit it, and never commit it.

## How the game uses the two archives (`eur2`)

- `rom:` is the archive name that `nn::fs::MountRom` (0x0010C2C8) mounts the base RomFS with.
- The update data is mounted with the archive name `pat1` (`sub_00449c4c`; that the function it calls is
  `nn::fs::MountContent` is inferred, not confirmed). On top of it sits a `System::SeadCtrFileDevice` registered in
  sead under the drive name `patch` (`sub_00444564`).
- The v1.2 code takes its overrides from the `Patch/` folder of `pat1:`. A file there replaces the file of the same
  name inside the archive its folder is named after: `pat1:/Patch/Course/Gctr_DKJungle/Gctr_DKJungle.kmp` replaces
  `Gctr_DKJungle.kmp` of `rom:/Course/Gctr_DKJungle.szs`.
- The base RomFS can have a `Patch/` folder of its own, left by an earlier update that was folded into the cartridge
  image (a v1.1 cartridge has `rom:/Patch/Course/`). The v1.2 code does not use it.

## KMP (course data)

Every course archive holds a `<course>.kmp` (signature `DMDC`): start points, CPU and item routes, checkpoints,
objects, routes, areas, cameras, respawn points and the stage info. `mk7 kmp` reads them from the extracted RomFS.

- A course name gives the file the v1.2 game uses: the `pat1:/Patch` override when there is one, otherwise the KMP
  inside `rom:/Course/<course>.szs`. `--base` takes the `rom:` one. A `.kmp` path works too.
- The dump has one line per entry: the entry index, its offset in the file, then `name=value` pairs. A point says which
  path holds it (`path 2[5]`: path 2, its point 5), and a path gives its points (`points 18..26`). Unused slots of the
  previous and next lists are left out (`[3, 5]`).
- The names come from `template/` first, then from research that `template/` does not have yet, then from the game's
  code where `mk7 kmp fields` names the function, then from community tools (KMPExpander, EveryFileExplorer, the
  mk3ds.com wiki), which are only hints and are shown as `name~`. Unnamed fields still have the types the game reads
  them with, and `mk7 kmp fields` notes where it uses them. A field nobody has named is `unk_0x<offset>`, with its value
  in hex. Object IDs, the area enums and the presence flags are read from `template/`.
- A whole-file dump ends with a check that every byte of the file belongs to the header or a section entry; anything
  left over is listed.
- Sections are named as the research names them (`KTPT`, `ENPT`, ...). The file stores the magic reversed (`TPTK`), and
  both spellings work in `-s`.
- `Gctr_MarioCircuit_Divide.kmp` is the only file of version 0xBB8 (the others are 0xC1C). Its GOBJ entries are 0x3C
  bytes, without `enemy_route` and the field after it.

## BSEQ (scene and menu sequences)

The order of the game's screens is data: 29 files in `UI/common.szs` whose content starts with `BSEQ`
(`Root-Default.brs`, one `.bss` per scene, and debug leftovers). The format is described in
the research on scene and menu sequencing (BSEQ). `mk7 bseq` reads them from the extracted RomFS.

- 20 of the files are stored by hash only. Their names are recovered from the root block
  (`<root section>-<root mode>.<brs|bss>`, checked against the stored hash), and such a name works as the target
  (`BootScene-Default` opens `0x73DC5722`). A file in `pat1:/Patch/UI/common/` would replace its namesake; the retail
  update has none.
- Each block shows its code tables (`id name`, and the default ID), its class or scene, its subsections and its flows.
  A flow has every code resolved against the table the game looks it up in:
  `[0] Page_SingleCourse returns Back(9) -> return Back(9)`, followed by the raw entry. An ID missing from its table is
  shown as `#id?->Name(id)`, the default entry the game falls back to. A child of a parallel sequence that no flow
  enters is marked, because the game starts it anyway.
- The header part ends with the rules of the research that an edited file has to respect (`num_sections`,
  `num_layers`, the root block). A whole-file dump also lists strings that nothing refers to and checks that every
  byte is accounted for.
