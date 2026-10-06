# Game data commands

Every argument of the commands that extract and dump the game's data files. What the files are and how the game
uses them: [GAME_DATA.md](../GAME_DATA.md). Overview: [CLI.md](../CLI.md).

## Contents

- [RomFS](#romfs): `romfs extract`, `romfs status`
- [KMP](#kmp): `kmp dump`, `kmp list`, `kmp fields`
- [BSEQ](#bseq): `bseq dump`, `bseq list`
- [Use examples](#use-examples)

## RomFS

### `romfs extract [--force] [-i IMAGE]`

Extract every RomFS of the image into `mk7-llm-research/local/romfs/<image>/<mount>/` and unpack its `.szs` archives
(needs pyctr). Does nothing when the output is up to date with the RomFS files and the hash table.

| Argument | Description |
| --- | --- |
| `--force` | extract again even when up to date |
| `-i`, `--image IMAGE` | the image whose `romfs` entries in `images.json` are extracted: `eur2` (default, the target; the only one with RomFS files listed by the setup) |

### `romfs status [-i IMAGE]`

Show what is extracted and where.

| Argument | Description |
| --- | --- |
| `-i`, `--image IMAGE` | the image whose extracted RomFS is read, by its name in `images.json`: `eur2` (default, the target) |

## KMP

### `kmp dump TARGET [-s SEC[:N[-M]] ...] [--base] [-o FILE] [-i IMAGE]`

Dump a course's KMP as text: one line per entry, `name=value` pairs ([KMP](../GAME_DATA.md#kmp-course-data)).

| Argument | Description |
| --- | --- |
| `TARGET` | a course name (`Gctr_DKJungle`, or a unique part of it: `DKJungle`) or a path to a `.kmp` file. A course name picks the file the v1.2 game uses: the `pat1:/Patch` override when there is one |
| `-s`, `--section SEC[:N[-M]]` | only this section, optionally only its entries N to M (`ENPT:10-20`) or entry N; repeatable. Sections: KTPT, ENPT, ENPH, ITPT, ITPH, CKPT, CKPH, GOBJ, POTI, AREA, CAME, JGPT, CNPT, MSPT, STGI, CORS, GLPT, GLPH (the reversed magics as stored, `TPTK`, work too). Default: the whole file, ending with a check that every byte is accounted for |
| `--base` | use the KMP in `rom:/Course/<course>.szs` even when `pat1:/Patch` overrides it |
| `-o`, `--output FILE` | write to this file instead of stdout |
| `-i`, `--image IMAGE` | the image whose extracted RomFS is read, by its name in `images.json`: `eur2` (default, the target) |
| `--templates DIR` | given before `kmp dump` (`mk7 --templates DIR kmp dump ...`), or set as `MK7_TEMPLATES=DIR`: read the field names, object IDs, area enums and flags from this copy of the templates |

### `kmp list [--base] [-o FILE] [-i IMAGE]`

Every course KMP of the image, with its entry count per section.

| Argument | Description |
| --- | --- |
| `--base` | also list the original (`rom:`) KMP of the courses that `pat1:/Patch` overrides |
| `-o`, `--output FILE` | write to this file instead of stdout |
| `-i`, `--image IMAGE` | the image whose extracted RomFS is read, by its name in `images.json`: `eur2` (default, the target) |

### `kmp fields [SECTION ...] [-o FILE]`

The layout of each section and where each field name comes from (`template/`, research not in `template/` yet, the
game's code, community tools).

| Argument | Description |
| --- | --- |
| `SECTION` | only these sections; default all |
| `-o`, `--output FILE` | write to this file instead of stdout |
| `--templates DIR` | given before `kmp fields` (`mk7 --templates DIR kmp fields ...`), or set as `MK7_TEMPLATES=DIR`: read the field names from this copy of the templates |

## BSEQ

### `bseq dump TARGET [-s PART ...] [-o FILE] [-i IMAGE]`

Dump a BSEQ file as text: the header with its consistency checks, every section block with its code tables,
subsections and flows (codes resolved to names), the engine creators and the strings nothing refers to
([BSEQ](../GAME_DATA.md#bseq-scene-and-menu-sequences)).

| Argument | Description |
| --- | --- |
| `TARGET` | a file of `UI/common.szs` (`Root-Default.brs`, or its hash name `0xB070E39E`), a recovered name of a file stored by hash (`BootScene-Default`), or a path |
| `-s`, `--section PART` | only this part (`header`, `blocks`, `engines`, `strings`), block (by name) or block index (`#N`); repeatable. Default: everything, with a check that every byte is accounted for |
| `-o`, `--output FILE` | write to this file instead of stdout |
| `-i`, `--image IMAGE` | the image whose extracted RomFS is read, by its name in `images.json`: `eur2` (default, the target) |

### `bseq list [-o FILE] [-i IMAGE]`

Every BSEQ file of `UI/common.szs`, with its name, size, block count and checks.

| Argument | Description |
| --- | --- |
| `-o`, `--output FILE` | write to this file instead of stdout |
| `-i`, `--image IMAGE` | the image whose extracted RomFS is read, by its name in `images.json`: `eur2` (default, the target) |

## Use examples

```
mk7-llm-research/mk7 romfs extract && mk7-llm-research/mk7 romfs status
mk7-llm-research/mk7 kmp list                                  # every course, with its entry count per section
mk7-llm-research/mk7 kmp dump Gctr_DKJungle -o dk.txt          # the whole file
mk7-llm-research/mk7 kmp dump DKJungle -s ENPT:10-20 -s ENPH   # some sections, some entries
mk7-llm-research/mk7 kmp fields GOBJ                           # the layout, and where each field name comes from
mk7-llm-research/mk7 bseq list                                        # every file, its name, size, blocks, checks
mk7-llm-research/mk7 bseq dump MenuScene-Default -o menu.txt          # the whole file
mk7-llm-research/mk7 bseq dump MenuScene-Default -s Para_TAChart -s Seq_TAChart   # some blocks, by name
mk7-llm-research/mk7 bseq dump Root-Default.brs -s header -s '#0'     # parts (header, blocks, engines, strings), block indices
```
