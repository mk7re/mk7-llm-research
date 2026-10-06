# The workspace

Which build of the game is documented and how the others are used, where everything lives in the repository, and how
the user hands files to a session.

## Contents

- [Which build is documented](#which-build-is-documented): `eur2` is the target; what `dlp`, `eur0` and `eur1` are for
- [Layout](#layout): the folders of the repository and of `mk7-llm-research/`
- [Session input files](#session-input-files): `<repo>/local/llm_input_files/` and how to treat it

## Which build is documented

**Only the final retail build, v1.2 (rev2), is documented.** `template/` describes it, and it is the default image of
every tool. The other builds are references that help understand it, never documented for their own sake.

| Build | Image | Role | What to keep in mind |
| --- | --- | --- | --- |
| Download Play child | `dlp` | reference, source of names | Built slightly **before** v1.0. Its linker map (`CTRDash.xmap`) names every function, which is why it matters. Parts are missing, the SDK is older, and some functions were adapted for the DLP client. |
| v1.0 (rev0) | `eur0` | reference | Launch build; the closest retail build to `dlp`. |
| v1.1 (rev1) | `eur1` | reference | Patches a few glitches in some tracks. A full relink, 0xF000 bytes of code larger than v1.0. |
| v1.2 (rev2) | `eur2` | **target** | Fixes a vulnerability. Final build. |

- A name from the xmap is a strong hint, not a fact. A `dlp` function may have a different body in `eur2` or no
  counterpart at all, and `eur2` has functions that `dlp` never had. Nearly every `dlp` function has a counterpart in
  `eur0`, fewer in `eur1` and `eur2`, and many of those have a different body; `mk7 port --all` prints the current
  figures, `mk7 port --changed` and `--missing` list them.
- Offsets, sizes and behaviour are always confirmed in `eur2`. Reading a `dlp` function because it is named is fine;
  concluding from it is not.
- Differences between builds are evidence (`mk7 port --changed`, `mk7 diff`). Against `dlp` they are usually the DLP
  adaptation or the older SDK; between `eur0`, `eur1` and `eur2` they are one of the patches above.

## Layout

```
<repo>/
  template/            data structure templates (the research output)
  process.py, Makefile template -> include/ generator (see <repo>/README.md)
  include/             generated headers            (ignored, made by `make`)
  vendor/              sead, nnheaders, nw4c, libc, lms submodules
  local/code/          game binaries, symbol maps, RomFS files (ignored, user-provided)
  local/llm_input_files/  session input files (ignored)
  mk7-llm-research/
    README.md          the entry point: rules, document map
    LICENSE, LICENSES/ which license covers which files (0BSD for the tooling, CC0 for the rest)
    docs/tooling/      the workspace's own documentation (this file, SETUP.md, CLI.md, ...)
    docs/research/     human-reviewed research: INDEX.md, one <topic>/ folder per subject
    mk7                launcher of the research CLI
    requirements.txt   pip packages of the CLI (installed into local/venv)
    tools/mk7re/       the CLI implementation (Python package): cli.py, paths.py
      static/          static analysis: templates, binaries (disassembly, xrefs, porting, Ghidra), RomFS,
                       data file dumpers (KMP, BSEQ)
        data/          data files (HashTable.saht: the names of the files inside .szs archives)
        ghidra_scripts/   Ghidra headless scripts used by `mk7 ghidra` and `mk7 decomp`
      dynamic/         dynamic analysis: Azahar, its RPC server and gdb stub, the code pages and
                       the hooks, the game core and one module per topic (see EMULATOR.md)
    images.json        which binaries exist and where
    symbols/           hand-made symbol maps per image (committed, shared)
    pending-verification/<topic>/   research results awaiting the agent's reviews
    final/<topic>/     research results that passed both reviews by the agent
    local/             caches, Ghidra project, scratch (ignored)
      work/<topic>/    template work copy and its generated headers
      venv/            Python environment with the packages of requirements.txt
      romfs/<image>/<mount>/   extracted game data (see GAME_DATA.md)
      azahar/          emulator console output and screenshots (see EMULATOR.md)
```

## Session input files

`<repo>/local/llm_input_files/` is where the user puts extra files for the current session (a hash table, a dump, a
document, a save file, ...).

- They are context for the session, nothing more. The agent looks there when the user mentions a file, and reads what
  it needs.
- The agent copies them nowhere on its own. When the user asks for a file to be kept, it is copied where they say, as
  it is, so that a newer version can later be dropped in its place.
- Nothing copyrighted leaves a `local` folder.
