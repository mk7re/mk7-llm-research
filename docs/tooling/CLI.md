# The `mk7` CLI

`mk7-llm-research/mk7 <command>` is the research CLI (`tools/mk7re`). This file says which command group does what and
what to watch out for. Every argument of every command, with its values and default, is in the command's table in the
`cli/` subdocuments; `mk7 <command> --help` prints the same arguments.

## Contents

- [Command groups](#command-groups): what each group is for and where its arguments are documented
- [Known caveats](#known-caveats): limits of the tools to keep in mind when reading their output

## Command groups

| Group | Commands | Needs | For | Arguments |
| --- | --- | --- | --- | --- |
| Templates | `struct`, `field`, `find`, `gaps`, `gen`, `verify` | `template/`; make; devkitARM for `verify` | inspecting the layouts of `template/`, finding unexplored bytes, generating and compile-checking the headers | [cli/templates.md](cli/templates.md) |
| Binaries | `images`, `sym`, `dis`, `xref`, `vtable`, `read`, `strings`, `access` | the game binaries | looking around in a binary; which offsets of `this` a function touches | [cli/binary.md](cli/binary.md) |
| Builds | `port`, `diff` | two binaries | matching functions between builds and comparing them | [cli/binary.md](cli/binary.md#builds) |
| Ghidra | `ghidra`, `decomp` | Ghidra | the headless project, decompilation | [cli/binary.md](cli/binary.md#ghidra) |
| Game data | `romfs extract`, `romfs status`, `kmp dump`, `kmp list`, `kmp fields`, `bseq dump`, `bseq list` | the RomFS files, pyctr | extracting the game's data files, dumping course data (KMP) and scene sequences (BSEQ) as text ([GAME_DATA.md](GAME_DATA.md)) | [cli/gamedata.md](cli/gamedata.md) |
| Emulator | `emu ...` | Azahar, the installed game, devkitARM | driving the running game ([EMULATOR.md](EMULATOR.md)) | [cli/emu.md](cli/emu.md) |

## Known caveats

- `mk7 ghidra` and `mk7 decomp` start a headless Ghidra (2 GB Java heap plus the native decompiler), and a running
  Azahar (`mk7 emu`) needs its own memory on top. Where both do not fit in RAM, the system thrashes instead of killing a
  process and can hang completely. Decompile before `mk7 emu start` or after `mk7 emu stop`, unless `free -h` shows
  room for both ([Configuration](emulator/azahar.md#configuration)).
- `mk7 verify --offsets` is stricter than the templates' conventions: many members declare a size that includes their
  trailing padding, which it reports as a size mismatch. Treat its output as hints to review, not as errors.
- `mk7 access` is a heuristic dataflow over the disassembly. Confirm anything surprising with `mk7 dis` or
  `mk7 decomp`.
- Names in the retail images are inferred (`mk7 port`) and are shown with a `~` and how they were matched; they can be
  wrong. Some `dlp` functions have no counterpart found in `eur2` (`mk7 port --missing` lists them), and `eur2` code
  that `dlp` lacks has no name.
- Names are ported from `dlp` to each retail build directly. `eur0` is much closer to `dlp` than `eur2` is, so going
  through it (`dlp` -> `eur0` -> `eur1` -> `eur2`) would likely recover more names; this is not implemented.
