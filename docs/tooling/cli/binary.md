# Binary, build and Ghidra commands

Every argument of the commands that read the game binaries, compare builds and run Ghidra. Overview:
[CLI.md](../CLI.md).

## Contents

- [Looking around in a binary](#looking-around-in-a-binary): `images`, `sym`, `dis`, `xref`, `vtable`, `read`,
  `strings`
- [Field accesses](#field-accesses): `access`
- [Builds](#builds): `port`, `diff`
- [Ghidra](#ghidra): `ghidra`, `decomp`
- [Use examples](#use-examples)

## Looking around in a binary

### `images`

List the binaries configured in `images.json` with their hashes and segments. No arguments.

### `sym QUERY [-r] [--limit N] [-i IMAGE]`

Look up symbols by name, or describe an address (segment, nearest symbol, the function containing it or the word
stored there).

| Argument | Description |
| --- | --- |
| `QUERY` | an address in hex (5 to 8 digits, `0x` optional), or a name: the exact name, the name without its parameter list, or a case-insensitive part of it; every matching symbol is listed |
| `-r`, `--regex` | treat `QUERY` as a case-insensitive regular expression on symbol names |
| `--limit N` | print at most N symbols (default 60) |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `dis TARGET [-n LENGTH] [-i IMAGE]`

Disassemble the function at or containing a target. The end is the next known entry point, so it may include a
following function.

| Argument | Description |
| --- | --- |
| `TARGET` | an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol |
| `-n`, `--length LENGTH` | disassemble exactly LENGTH bytes from the address instead of the function (decimal or `0x` hex) |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `xref TARGET [--limit N] [-i IMAGE]`

Callers of a function and the words that hold an address: calls, literal-pool loads, data words and pointer-table
slots.

| Argument | Description |
| --- | --- |
| `TARGET` | an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol |
| `--limit N` | print at most N references (default 80) |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `vtable ADDR [--containing] [-i IMAGE]`

Dump a table of function pointers, slot by slot, with the functions that load its address.

| Argument | Description |
| --- | --- |
| `ADDR` | the table's address, in hex |
| `--containing` | `ADDR` is some slot of the table; walk back to the table's start first |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `read ADDR [COUNT] [-i IMAGE]`

Dump words from the file at an address, each with its float value, what it points to and any string there. Stops at
the end of the file (`.bss` is not in it).

| Argument | Description |
| --- | --- |
| `ADDR` | an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol; rounded down to a multiple of 4 |
| `COUNT` | number of 32-bit words (default 8) |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `strings PATTERN [--limit N] [-i IMAGE]`

Case-insensitive regex search in the binary's 8-bit strings, with the functions that reference each string.

| Argument | Description |
| --- | --- |
| `PATTERN` | regular expression |
| `--limit N` | print at most N strings (default 40) |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

## Field accesses

### `access [TARGETS ...] [--class CLS [--match RX]] [--as CLASS] [--reg REG] [--gaps] [--addresses] [-i IMAGE]`

Which offsets of an object functions read and write (a heuristic dataflow over the disassembly), mapped onto the
templates: each offset with its access size and the member that covers it, or `GAP` / `OUTSIDE` / `undeclared`.

| Argument | Description |
| --- | --- |
| `TARGETS` | one or more functions, each an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol; ignored with `--class` |
| `--class CLS` | analyse every method of this class (the symbols named `CLS::<method>`) instead of `TARGETS`, and map the offsets onto its template if it has one |
| `--match RX` | with `--class`: only the methods whose name matches this regular expression (case-sensitive) |
| `--as CLASS` | with `TARGETS`: map the offsets onto this template class; without it they are listed unmapped. Ignored with `--class` |
| `--reg REG` | the register that holds the object on entry (default `r0`, `this`) |
| `--gaps` | only list the offsets the templates do not explain |
| `--addresses` | show one instruction address per row |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |
| `--templates DIR` | given before `access` (`mk7 --templates DIR access ...`), or set as `MK7_TEMPLATES=DIR`: map the offsets onto the classes of this copy of the templates |

## Builds

### `port [TARGET] [--all] [--changed [RX]] [--missing [RX]] [--limit N] [--from SRC] [--to DST]`

Find a function or data address of one image in another, using the port map that `--all` builds. Without a map that is
up to date with both images, every query asks for `--all` first.

| Argument | Description |
| --- | --- |
| `TARGET` | a function or data in the source image, an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol; prints its counterpart, how it was matched and whether the body differs, or the closest candidate bodies |
| `--all` | (re)build the full map from `--from` to `--to`; afterwards `--to` shows the ported names with a `~` prefix (slow, cached) |
| `--changed [RX]` | list matched functions whose body differs, with the share of equal words; optionally only names matching RX (case-insensitive) |
| `--missing [RX]` | list source functions with no counterpart found; optionally only names matching RX (case-insensitive) |
| `--limit N` | print at most N rows for `--changed` and `--missing` (default 60) |
| `--from SRC` | the source image, by its name in `images.json`: `dlp` (default), `eur0`, `eur1` or `eur2` |
| `--to DST` | the image to look in, by its name in `images.json`: `eur2` (default), `eur1`, `eur0` or `dlp` |

### `diff TARGET [--at ADDR] [--from SRC] [--to DST]`

Instruction-level differences of one function between two images.

| Argument | Description |
| --- | --- |
| `TARGET` | the function in the source image, an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol |
| `--at ADDR` | the function's address in the target image, in hex, overriding the port map |
| `--from SRC` | the source image, by its name in `images.json`: `dlp` (default), `eur0`, `eur1` or `eur2` |
| `--to DST` | the image to look in, by its name in `images.json`: `eur2` (default), `eur1`, `eur0` or `dlp` |

## Ghidra

### `ghidra ACTION [-i IMAGE]`

Manage the headless Ghidra project (`mk7-llm-research/local/ghidra/mk7.gpr`) used by `decomp`. Close the project in the
Ghidra GUI before running headless commands.

| Argument | Description |
| --- | --- |
| `ACTION` | `status` (which images are imported and analysed, for every image), `setup` (import and analyse the image; slow, once per image; log `local/ghidra/<image>.setup.log`) or `sync` (re-apply the symbols to the image's program; cached decompilations become stale, use `decomp --refresh`) |
| `-i`, `--image IMAGE` | for `setup` and `sync`: the binary, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |

### `decomp TARGETS ... [--as CLASS] [--param P] [--refresh] [-i IMAGE]`

Decompile functions with Ghidra (needs `ghidra setup` once per image). Output is cached.

| Argument | Description |
| --- | --- |
| `TARGETS` | one or more functions, each an address in hex (5 to 8 digits, `0x` optional), or a symbol name: the exact name, the name without its parameter list (`Kart::Unit::changeToCPU`), or a case-insensitive part of it; a name must match exactly one symbol; an address inside a function decompiles the whole function |
| `--as CLASS` | list the offsets used off the object parameter and map them onto this template class |
| `--param P` | the parameter that holds the object, for `--as` (default `param_1`) |
| `--refresh` | ignore the cached output and decompile again |
| `-i`, `--image IMAGE` | the binary to read, by its name in `images.json`: `eur2` (default, the target), `eur1`, `eur0` or `dlp` |
| `--templates DIR` | given before `decomp` (`mk7 --templates DIR decomp ...`), or set as `MK7_TEMPLATES=DIR`: with `--as`: map the offsets onto the classes of this copy of the templates |

## Use examples

```
mk7-llm-research/mk7 sym changeToCPU
mk7-llm-research/mk7 dis Field::MapdataEnemyPoint::setup
mk7-llm-research/mk7 access --class Kart::Unit --match calc --gaps
mk7-llm-research/mk7 port --changed Kart::
mk7-llm-research/mk7 diff Field::MapdataEnemyPoint::setup
mk7-llm-research/mk7 decomp Field::MapdataEnemyPoint::setup --as Field::MapdataEnemyPoint
```
