# Template commands

Every argument of the commands that read `template/` and build its headers. Overview: [CLI.md](../CLI.md).

## Contents

- [`struct`](#struct-name---flat---gaps): a class layout
- [`field`](#field-name-offset): what is at an offset of a class
- [`find`](#find-pattern---comments): search class and member names
- [`gaps`](#gaps-filter---min-n---limit-n---unknown): classes ranked by unexplored bytes
- [`gen`](#gen): generate the headers
- [`verify`](#verify---version-v---all-versions---namespace---offsets--v): compile-check the headers
- [Use examples](#use-examples)

## `struct NAME [--flat] [--gaps]`

Show the layout of a class described in `template/`: size, file, base, then one line per member with its offset.

| Argument | Description |
| --- | --- |
| `NAME` | class name, qualified (`Kart::Unit`) or not if unambiguous; an unknown name lists close matches. A class declared once per game version shows the first declaration |
| `--flat` | include the members inherited from bases that are described in `template/` |
| `--gaps` | only show gaps and unnamed (`/U/`) members |
| `--templates DIR` | given before `struct` (`mk7 --templates DIR struct ...`), or set as `MK7_TEMPLATES=DIR`: read the class from this copy of the templates instead of `<repo>/template` |

## `field NAME OFFSET`

What is at `CLASS+OFFSET`: the member that covers the offset, searched through the bases described in `template/`,
and one level into a by-value member whose type is a template class. Also says when the offset is in a base without a
template or is the vtable pointer.

| Argument | Description |
| --- | --- |
| `NAME` | class name, as for `struct` |
| `OFFSET` | offset into the class; decimal or `0x` hex |
| `--templates DIR` | given before `field` (`mk7 --templates DIR field ...`), or set as `MK7_TEMPLATES=DIR`: read the class from this copy of the templates instead of `<repo>/template` |

## `find PATTERN [--comments]`

Regex search (case-insensitive) over class names and member declarations.

| Argument | Description |
| --- | --- |
| `PATTERN` | regular expression |
| `--comments` | also search the members' comments |
| `--templates DIR` | given before `find` (`mk7 --templates DIR find ...`), or set as `MK7_TEMPLATES=DIR`: search this copy of the templates instead of `<repo>/template` |

## `gaps [FILTER] [--min N] [--limit N] [--unknown]`

Rank classes by unexplored bytes (gaps not described by any member): research targets. Prints unexplored bytes, the
class's own size (without bases), the percentage and the file.

| Argument | Description |
| --- | --- |
| `FILTER` | regular expression on the qualified class name (case-insensitive); default every class |
| `--min N` | only classes with at least N unexplored bytes (default 1; decimal or `0x` hex) |
| `--limit N` | print at most N classes (default 40) |
| `--unknown` | also count unnamed `/U/` members as unexplored |
| `--templates DIR` | given before `gaps` (`mk7 --templates DIR gaps ...`), or set as `MK7_TEMPLATES=DIR`: rank the classes of this copy of the templates instead of `<repo>/template` |

## `gen`

Generate the headers with `make` into `<repo>/include`.

| Argument | Description |
| --- | --- |
| `--templates DIR` | given before `gen` (`mk7 --templates DIR gen ...`), or set as `MK7_TEMPLATES=DIR`: generate the headers of this copy of the templates, into the `include` folder next to it |

## `verify [--version V] [--all-versions] [--namespace] [--offsets] [-v]`

Generate the headers and compile-check them with devkitARM's g++ for the 3DS ABI.

| Argument | Description |
| --- | --- |
| `--version V` | the `GAME_VERSION` to compile for: a `VERSION_*` name of `template/versions.h`, with or without the prefix (`EUR_REV2`); default `VERSION_USA_REV1`, what CI compiles |
| `--all-versions` | check every version of `template/versions.h` instead of one |
| `--namespace` | also compile with `MK7MEMORY_NAMESPACE`, as CI does |
| `--offsets` | also assert `offsetof` and `sizeof` of every member against the templates (strict: see [Known caveats](../CLI.md#known-caveats)) |
| `-v`, `--verbose` | print the full compiler output instead of a summary |
| `--templates DIR` | given before `verify` (`mk7 --templates DIR verify ...`), or set as `MK7_TEMPLATES=DIR`: check this copy of the templates; its headers are generated into the `include` folder next to it |

## Use examples

```
mk7-llm-research/mk7 struct Kart::Unit --gaps
mk7-llm-research/mk7 field Kart::Unit 0x2C
mk7-llm-research/mk7 gaps Field:: --limit 10
mk7-llm-research/mk7 verify --version EUR_REV2 --offsets
mk7-llm-research/mk7 --templates mk7-llm-research/local/work/<topic>/b/template verify
```
