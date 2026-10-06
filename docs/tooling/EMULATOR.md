# Dynamic analysis with Azahar

Running the game (`eur2`, EUR v1.2) in the Azahar 3DS emulator and driving it with `mk7 emu`, through Azahar's RPC
server (live memory, code patches, screenshots, frame rate) and its gdb stub (breakpoints, watchpoints, single steps).
Static analysis stays the default; the emulator confirms in game what the code says.

## Contents

- [Setup](#setup): where Azahar, the game and the ports are, and what to enable
- [Rules for a session](#rules-for-a-session): what every dynamic session must respect
- [What a session can do](#what-a-session-can-do): the command groups, with links to the argument tables
- [Subdocuments](#subdocuments): which file to read for which task

## Setup

| What | Where (override) |
| --- | --- |
| Azahar | `<repo>/local/azahar/azahar.AppImage` (`AZAHAR_APPIMAGE`); a build with azahar PRs 2631 and 2633 (RPC protocol version 2, screenshots, statistics, gdb stepping), e.g. `d8b2ad0` |
| Azahar user dir | `~/.local/share/azahar-emu` (`AZAHAR_USER_DIR`); its log is `log/azahar_log.txt` |
| The game | installed title `0004000000030700` plus its v1.2 update, boot content `.../title/00040000/00030700/content/00000000.app` (`MK7_TITLE`) |
| gdb stub | `localhost:4000` (`AZAHAR_GDB_PORT`); `use_gdbstub=true` in Azahar's config |
| RPC server | UDP `localhost:45987` (fixed in Azahar); `enable_rpc_server=true` in Azahar's config, effective from the next game boot |
| Azahar config | `log_filter=*:Info RPC_Server:Warning`; `graphics_api=1` (OpenGL) on a machine without a GPU; edit it only while Azahar is closed ([Configuration](emulator/azahar.md#configuration)) |
| Hooks | devkitARM (`as`, `ld`, `objcopy`, `nm`; `gcc` for the simulated player), as for `mk7 verify` |

## Rules for a session

- **`mk7 emu start` first.** It launches Azahar and leaves the game frozen at its first frame on the boot logo, with
  the hooks installed, saving disabled and the emulation unthrottled. A game started by hand in Azahar has no code
  pages, and the hooks refuse to install ([Hooks](emulator/hooks.md)).
- **Use `start --unlock`** unless the research needs the save's own locks: `unlock` only works before the menu scene
  builds its pages ([Starting frozen at boot](emulator/hooks.md#starting-frozen-at-boot)).
- **One command at a time.** Only one gdb client can be connected; a script that holds one stops every command that
  steps frames.
- **No GPU: use OpenGL.** Vulkan on a software renderer keeps every pipeline in memory until the machine runs out.
- **No headless Ghidra alongside Azahar** (`mk7 decomp`, `mk7 ghidra`) unless `free -h` shows room for both: where they
  do not fit, the system thrashes and hangs instead of killing a process. Decompile before `start` or after `stop`.
- **Reach courses with a time trial** unless the research needs the other karts; the numbers commands take are menu
  buttons, not ECourseIDs ([Reaching a course](emulator/menus.md#reaching-a-course)).
- The game runs unthrottled except while the hooks freeze it or gdb halts it; commands that step a number of frames
  are exact at any speed ([Emulation speed](emulator/azahar.md#emulation-speed)).

## What a session can do

Every argument of every command is in [cli/emu.md](cli/emu.md).

| Group | Commands | For |
| --- | --- | --- |
| Emulator control | `start`, `stop`, `status`, `speed`, `screenshot`, `stats` | launching, speed, screenshots, frame rate |
| Time and memory | `freeze`, `run`, `step`, `pages`, `wait`, `read`, `write`, `call` | frame-exact time control, the sequence tree, live memory, calling game functions |
| Menus | `buttons`, `click`, `complete`, `unlock`, `character`, `kart`, `settings`, `tt-course`, `battle-course`, `channel`, `multiplayer`, `player` | pressing page buttons, choosing driver, kart and rules |
| Runs | `timetrial`, `grandprix`, `battle`, `vs`, `continue`, `menu`, `finish`, `advance`, `skip-demo`, `race-start` | whole runs from the title, stopping on a race page, ending races, the race page's menus |
| Race state and driving | `race`, `teleport`, `drive` | course and kart state, moving karts, the simulated player |

For longer work, a Python script on `mk7re.dynamic` keeps one session and its caches
([library.md](emulator/library.md)).

## Subdocuments

| File | Read it when |
| --- | --- |
| [cli/emu.md](cli/emu.md) | you need the exact arguments of an `mk7 emu` command |
| [emulator/menus.md](emulator/menus.md) | getting to a course or a page: which run to use, the course and button table, how buttons are pressed, the character, kart and settings pages |
| [emulator/races.md](emulator/races.md) | working during or after a race: ending races, carrying a run on, the race page's menus, the player's kart driven by the AI |
| [emulator/simulated-player.md](emulator/simulated-player.md) | the player's kart has to drive somewhere or a whole race (`drive`, `--player simulated`), or `driver.c` changes |
| [emulator/vs.md](emulator/vs.md) | a run needs any race course with seven CPUs (`start --vs`), or `vs.py` changes |
| [emulator/library.md](emulator/library.md) | writing a Python script against the running game, adding a reader or command; where game state is read |
| [emulator/hooks.md](emulator/hooks.md) | changing the hooks, the code pages or the boot patches; a command fails around boot, freezing or saving |
| [emulator/azahar.md](emulator/azahar.md) | Azahar misbehaves or its limits matter: config, RPC and gdb stub behaviour, screenshots, speed, frame rate |
