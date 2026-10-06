# The `mk7re.dynamic` Python library

The modules behind `mk7 emu`, for scripts that do more than a few commands, and where the game's state is read.
Part of [EMULATOR.md](../EMULATOR.md). Read it when writing a script against the running game or adding a reader
or a command to the dynamic tooling.

## Contents

- [Using the library](#using-the-library): one `Session` per script, how to import it
- [Modules](#modules): what each file of `tools/mk7re/dynamic/` holds, where new code goes
- [Classes and methods](#classes-and-methods): `Session`, `Menu`, `Race`, `Driver`, `Flow`
- [Reading the game](#reading-the-game): engines, the sequence tree, race state
- [Use examples](#use-examples): a sample script
- [Measurements](#measurements): sequence-tree walk times

## Using the library

For anything longer than a few commands, write a script that keeps one `Session`, and one `Menu` or `Race` if needed
(`mk7-llm-research/local/venv/bin/python`, with `mk7-llm-research/tools` on `sys.path`); they cache names and classes.
`Session.mem` is the RPC client (`Game`, `Menu` and `Race` read through it, the hooks and `unlock` write their code
through it). `Session.close(unfreeze=False)` keeps the game frozen for the next session.

## Modules

The modules are in `tools/mk7re/dynamic/` (package `mk7re.dynamic`):

| Module | Purpose |
| --- | --- |
| `azahar.py` | `start(on_halt)`, `stop()`, `screenshot(path)` (RPC), `window_screenshot(path)` |
| `rpc.py` | client of Azahar's RPC server (`RpcClient`): live memory reads and writes, `screenshot`, `perf_stats` |
| `gdbrsp.py` | minimal client of the gdb remote protocol (`GdbClient`): registers, memory, breakpoints, watchpoints, `step` |
| `memio.py` | the typed accessors (`u32`, `w32`, ...) both clients share |
| `codepages.py` | the [code pages](hooks.md#code-pages) mapped after the `.bss` at boot, where the tooling's ARM code lives; `assemble_source`, `compile_c` (devkitARM) |
| `hooks.py` | ARM hooks patched into the game: frame counter, freeze/step, calling game functions, the emulation speed ([Hooks](hooks.md#hooks)) |
| `game.py` | the core every topic uses. `Game`: memory helpers, engines, scenes, the sequence tree. `Session`: RPC memory, gdb on demand, hooks, stepping, calls, waiting for a section |
| `menu.py` | `Menu(session)`: page manipulators and buttons, `click`, `complete`, `unlock_all`, battle and VS settings and teams, the player as a CPU, `time_trial`, `vs` |
| `vs.py` | the patches of `start --vs`: single-player VS ([vs.md](vs.md)) |
| `driver.py`, `driver.c` | `Driver(session)`: the [simulated player](simulated-player.md), C code run by the game every frame; `set_player`, `player_mode` |
| `race.py` | `Race(session)`: race director and timer, finishing a race, the course intro and result screens, kart checkpoint state and position, the loaded KMP |
| `courses.py` | `RaceSys::ECourseID` and `.szs` names, the cup, slot and battle buttons of each course ([Reaching a course](menus.md#reaching-a-course)) |
| `flow.py` | `Flow(session)`: whole-game sequences that combine `Menu` and `Race` (a Grand Prix from the title to the trophy, the ending and back; a battle; a time trial), carrying a run on from where it is (`resume`) and the race page's menus |
| `save.py` | the patches that keep the game from writing files ([Saving is disabled](hooks.md#saving-is-disabled)) |
| `cmd_emu.py`, `cmd_emu_menu.py`, `cmd_emu_race.py` | the CLI ([cli/emu.md](../cli/emu.md)), split the same way |

A topic only loads what it needs: `Menu` and `Race` each take the `Session` and do not depend on each other; `Flow`
uses both. New readers for a topic go into the module of that topic (or a new `<topic>.py` next to them), not into
`game.py`.

## Classes and methods

- `Session`: `gdb()`, `freeze`, `step(n)`, `press(buttons, hold)` (`hooks.PAD_A`, ...), `run_until(pred)`,
  `wait_until(pred)`, `section_state(name)`, `find_section`, `wait_section(name)`, `call(func, *args)`,
  `close(unfreeze)`; `hooks.set_speed(percent)` (0 unthrottled, None Azahar's frame limit).
- `Menu`: `buttons(page)`, `find_button`, `cursor_button`, `press_blocked(button)`, `wait_pressable`,
  `click(page, button)`, `complete(page, code)`, `open_presents(page, button)`, `unlock_all(on)`,
  `choose_character(driver)`, `choose_kart(body, tire, wing)`, `choose_driver_and_kart(character, kart)`,
  `settings()`, `set_setting(name, value)`, `player_team()`, `choose_team(team)`, `apply_settings(settings, team)`,
  `cpu_player(on)`, `cpu_player_on()`,
  `time_trial(cup, course, character, kart)`, `time_trial_course(cup, course)` (buttons, or an `.szs` name in `cup`),
  `grand_prix(cup, engine, character, kart)` (stops when the menu scene hands over to the course intro),
  `battle(kind, course, character, kart, settings, team)`, `vs(course, character, kart, settings, team)` and
  `vs_course(cup, course)` (`start --vs`), `battle_course(course)` (button or `.szs` name), `open_channel`,
  `close_channel`, `open_multiplayer`, `close_multiplayer`.
- `Race`: `skip_demo`, `wait_race_page(skip_demo)`, `wait_start`, `finish(order, place)`,
  `finish_battle(order, place)`, `wait_goal`, `results_menu`, `menu_state`, `pause`,
  `race_mode`, `race_state`, `course_id`, `race_timer`, `kart_info(p)`, `kart(p)`, `set_kart_pos(p, xyz)`,
  `checkpoints`, `jugem_points`, `enemy_route` (the CPUs' re-sampled route).
- `Driver(session)`: `install`, `go_to(xyz, radius)`, `go_by_route(xyz, radius, forward_only, drift, trick)`,
  `race(drift, trick)`, `off`, `mode`, `status`, `reached`, `ended`; `set_player(session, mode)`,
  `player_mode(session)`.
- `Flow`: `grand_prix(cup, engine, places, character, kart, instant, skip_demo, until)`, `battle(kind, course, place,
  character, kart, instant, until, settings, team)`, `time_trial(cup, course, character, kart, instant, until)`,
  `vs(courses, places, character, kart, instant, until, settings, team)`, `resume(place, places, instant, skip_demo,
  until, courses)`, `menu_options()`, `menu_option(name)`, `advance(page)`.

## Reading the game

- Engines: `RootSystem` at 0x006789B8. Root-scene engines are at `RootScene+0x1E0`, scene engines at `GameScene+0x1E0`;
  pointers are XOR `0x75F1B26B`.
- Sequence (`Game`): `sequence_tree()` walks `Root-Default.brs` → proxies → the scene's `.bss` with names, classes,
  states and enter/return code names; `running_sections()`; `active_pages()` (`SequenceEngine::m_active_pages`,
  +0x88). File roots are always parallel sequences: the type byte of a `.bss` root block says 7. Section states:
  `free`, `ready`, `entering`, `standby`, `running`, `completed`, `finishing`, `exited`.
- Race (`Race`), only while a race scene runs:
  - `race_timer()`: `RaceDirector::m_race_timer` (+0x28, no template yet). The time is at +0x10 (u16 minutes,
    u16 seconds) and +0x14 (u32 ms); +0x24 is 1 during the countdown and 0 once the timer runs.
  - `kart_info(p)`: `LapRankChecker::KartInfo` (previous, current and last valid checkpoint, key id, flags). The
    fields can be written to put a kart in a checkpoint state (`kart_info(p)["addr"] + 0xC`: `<BBhB`).
  - `kart(p)` / `set_kart_pos(p, xyz)`: `Rigid::m_position` pointer, velocity and status flags. Writing the position
    moves the kart on the next frame; with the velocity cleared it then falls slowly from where it was put.
  - `checkpoints()` and `jugem_points()` return the loaded KMP data (`FieldDirector+0x38` → +0x24 / +0x3C).

## Use examples

```python
from mk7re.dynamic.game import Session
from mk7re.dynamic.menu import Menu
s = Session()                       # RPC memory; installs the hooks if needed
menu = Menu(s)                      # keep one: it caches class and code names
try:
    s.freeze()
    s.wait_section("Page_Title")    # run freely until the page runs, then freeze
    menu.click("Page_Title", "Next00")  # Single Player: waits until the press would count, presses, steps 1 frame
    for b in menu.buttons("Page_SingleMode"):
        print(b["id"], b["class"], b.get("return"))
    s.step(30)                      # exactly 30 frames, then frozen again
    s.hooks.unfreeze()
    with s.gdb() as g:              # halts the CPU; breakpoints are removed and the CPU resumed on exit
        stop = g.run_to(0x00168240) # UI::ManipulatorManager::calc
        print(hex(g.read_register(0)), s.mem.u32(0x00168240))   # RPC reads work while halted
        g.step()                    # one instruction
    s.mem.screenshot()              # (width, height, PNG bytes) of the next frame
finally:
    s.close(unfreeze=False)         # keep the game frozen for the next session
```

## Measurements

The first walk of the sequence tree takes about 30 ms, later walks in the same process about 6 ms (the cache of
names and classes).
