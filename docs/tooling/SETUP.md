# Setup

How to set up the workspace on a fresh clone. Follow it top to bottom; all commands are run from the repository root.

## Contents

- [Requirements](#requirements): tools to install and the environment variables that find them
- [Steps](#steps): clone, headers, game binaries and RomFS, checks, name porting, Ghidra, Python, game data

## Requirements

| Tool | Used for | Notes |
| --- | --- | --- |
| git, make, python3 (3.10+) with the `venv` module | generating headers, the CLI | on Debian/Ubuntu: `apt install python3-venv` |
| [pyctr](https://pypi.org/project/pyctr/), [Pillow](https://pypi.org/project/pillow/) | reading RomFS files (`mk7 romfs`); images (`mk7 emu screenshot --window`, research tools) | the pip packages of `requirements.txt`; installed into `mk7-llm-research/local/venv` in step 7, nothing is installed system-wide |
| [devkitPro](https://devkitpro.org/wiki/Getting_Started) with devkitARM and libctru | compile-checking headers for the 3DS ABI, `objdump` disassembly, the emulator hooks | install the `3ds-dev` group |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra/releases) + JDK 21 | decompilation (headless) | tested with Ghidra 12.1 |
| cmake, g++-multilib | only for the repository's `make verify` (what CI runs) | optional locally |
| [Azahar](https://github.com/azahar-emu/azahar) AppImage, the game installed in it | dynamic analysis (`mk7 emu`) | optional; a build with azahar PRs 2631 and 2633 (RPC protocol version 2); gdb stub and RPC server enabled in its config; `xwininfo` only for `mk7 emu screenshot --window`; see [EMULATOR.md](EMULATOR.md#setup) for paths and variables |

The tools find the installations through environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DEVKITPRO` | `/opt/devkitpro` | devkitPro root (must contain `libctru/`) |
| `DEVKITARM` | `$DEVKITPRO/devkitARM` | devkitARM root (must contain `bin/arm-none-eabi-g++`) |
| `GHIDRA_INSTALL_DIR` | `~/ghidra` | Ghidra root (must contain `support/analyzeHeadless`) |

If the installations are elsewhere, export these in your shell profile, or tell the agent the paths and it will pass
them along.

## Steps

1. **Clone with submodules**: `git clone <repo url> --recurse-submodules` (or
   `git submodule update --init --recursive` in an existing clone; `vendor/*` must not be empty).

2. **Generate the headers**: `make` runs `process.py` over every file in `template/` and writes `include/`.

3. **Provide the game binaries.** Dump `code.bin` (decompressed ExeFS `.code`) from your own copy of the game and place
   it under `<repo>/local/code/`:

   | Image | Expected files | sha1 of the binary |
   | --- | --- | --- |
   | `eur2` (default, target) | `local/code/eur_rev2/eur_rev2_code.bin` | `e3edb9771fea3149ddfe309e3ca8453046ef8a95` |
   | `eur1` | `local/code/eur_rev1/eur_rev1_code.bin` | `6e29ed303835fedc49569571f6918342a86e7d59` |
   | `eur0` | `local/code/eur_rev0/eur_rev0_code.bin` | `845bf872608b5e79ef6dd1abcf854acce9538bad` |
   | `dlp` | `local/code/dlp_child/dlp_code.bin`, `local/code/dlp_child/CTRDash.xmap` | `871a27d4398d26c51c463c3abe968415808852c4` |

   `eur2` and `dlp` (with its map) are required. `eur0` and `eur1` are optional; commands that use them fail with a
   clear message if they are absent.

   To use another build, add an entry to `images.json` (`role`, `path`, optional `symbols`, `user_symbols`, `romfs`,
   `version` = one of the `VERSION_*` names in `template/versions.h`). Symbol maps are plain text, one
   `hexaddr<TAB>name` per line, `#` for comments.

   Also dump the RomFS of the game and of its update data (plain, decrypted RomFS files starting with `IVFC`) and place
   them next to the target binary. They are listed under `romfs` of the `eur2` image, by the name the game mounts them
   with:

   | Mount | Expected file | What it is |
   | --- | --- | --- |
   | `rom:` | `local/code/eur_rev2/main_romfs.bin` | RomFS of the base game (cartridge or digital copy) |
   | `pat1:` | `local/code/eur_rev2/patch_romfs.bin` | RomFS of the update data, v1.2 |

4. **Check the setup**

   ```
   mk7-llm-research/mk7 images     # lists the binaries with their hashes and segments
   mk7-llm-research/mk7 verify     # make + compile-check of all headers with devkitARM g++
   ```

5. **Carry the names from `dlp` to the retail builds** (slow the first time, then cached)

   ```
   mk7-llm-research/mk7 port --all              # dlp -> eur2, the one that matters
   mk7-llm-research/mk7 port --all --to eur1    # optional references
   mk7-llm-research/mk7 port --all --to eur0
   ```

6. **Create the Ghidra project** (slow, once per image)

   ```
   mk7-llm-research/mk7 ghidra setup -i eur2    # the target
   mk7-llm-research/mk7 ghidra setup -i dlp     # the named reference
   mk7-llm-research/mk7 ghidra status
   ```

   The project lives in `mk7-llm-research/local/ghidra/mk7.gpr` and can also be opened in the Ghidra GUI (not while a
   headless command is running). Logs are next to it (`<image>.setup.log`).

7. **Create the Python environment** (once)

   ```
   python3 -m venv mk7-llm-research/local/venv
   mk7-llm-research/local/venv/bin/python -m pip install -r mk7-llm-research/requirements.txt
   ```

   The `mk7` launcher uses it by itself whenever it exists; there is nothing to activate. Every command except
   `mk7 romfs extract` and `mk7 emu screenshot --window` also works without it.

8. **Extract the game data**: `mk7-llm-research/mk7 romfs extract`, then `mk7-llm-research/mk7 romfs status`. See
   [GAME_DATA.md](GAME_DATA.md) for what this produces.
