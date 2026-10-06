# `mk7 emu` command reference

Every argument of every `mk7 emu` command. What the commands do inside the game and why is in
[EMULATOR.md](../EMULATOR.md) and its subdocuments; this file is the lookup table.

Every command connects, installs the hooks if needed, does its work and disconnects. The game keeps the state a command
leaves: frozen at a frame boundary (`freeze`, `step`, `wait`, `click`, `complete`, `race-start`, `finish`, `advance`,
the run commands, ...) or running (`run`). Only one gdb client can be connected at a time: run commands one after the
other, never two at once.

## Contents

- [Conventions](#conventions): numbers and pages, and the option groups `DRIVER`, `SETTINGS`, `COURSE`
- [Emulator control](#emulator-control): `start`, `stop`, `status`, `speed`, `screenshot`, `stats`
- [Time and memory](#time-and-memory): `freeze`, `run`, `step`, `pages`, `wait`, `read`, `write`, `call`
- [Menus](#menus): `buttons`, `click`, `complete`, `unlock`, `character`, `kart`, `settings`, `tt-course`,
  `battle-course`, `channel`, `multiplayer`, `player`
- [Runs](#runs): `timetrial`, `grandprix`, `battle`, `vs`, `continue`, `menu`, `finish`, `advance`, `skip-demo`,
  `race-start`
- [Race state and driving](#race-state-and-driving): `race`, `teleport`, `drive`
- [Use examples](#use-examples)

## Conventions

These hold for every command of this file; a table row that relies on one links to it.

### Numbers and pages

- Addresses, sizes, function addresses and call arguments are integers: decimal, or hex with a `0x` prefix
  (`0x006789B8`; a bare `006789B8` is rejected).
- `PAGE` and `SECTION` are section names of the sequence tree as `pages` prints them (`Page_Title`,
  `Page_SingleKart`).

### Driver options

`DRIVER` in a synopsis stands for these options. Left out, the page keeps what it has.

| Option | Description |
| --- | --- |
| `--character NAME` | the character, by `EDriverID` name or number (`template/RaceSys/EDriverID.hpp`): Bowser, Daisy, DonkeyKong, HoneyQueen, KoopaTroopa, Lakitu, Luigi, Mario, MetalMario, MiiMale, MiiFemale, Peach, Rosalina, ShyGuy, Toad, Wario, Wiggler, Yoshi |
| `--body B` | the kart body, by `EBodyID` name or number: Standard, BoltBuggy, BirthdayGirl, Egg1, BDasher, Zucchini, KoopaClown, TinyTug, BumbleV, CactX, Bruiser, PipeFrame, BarrelTrain, Cloud9, BlueSeven, SodaJet, GoldStandard |
| `--tire T` | the tires, by `ETireID` name or number: Standard, Monster, Roller, Slick, Slim, Sponge, GoldTires, Wood, RedMonster, Mushroom |
| `--wing W` | the glider, by `EWingID` name or number: SuperGlider, Paraglider, PeachParasol, FlowerGlider, Swooper, BeastGlider, GoldGlider |
| `--player normal\|cpu\|simulated` | who drives the player's kart, set before the run starts and kept until the game restarts (as the `player` command): the pad, the game's AI, or the [simulated player](../emulator/simulated-player.md) |

### Settings options

`SETTINGS` in a synopsis stands for these options of the battle (and VS) settings page
([Battle and VS settings](../emulator/menus.md#battle-and-vs-settings)). Left out, the page keeps what it has.

| Option | Description |
| --- | --- |
| `--cpu easy\|normal\|hard` | the CPU level setting (battle) |
| `--stage choose\|random\|in-order` | how the course of each round is picked; `choose` opens the course page, the others start from the settings page |
| `--items all\|shells\|bananas\|mushrooms\|bob-ombs` | which items appear |
| `--teams off\|on` | team mode |
| `--team red\|blue` | the player's team; turns teams on |

### Course arguments

`COURSE` is a race course's full `.szs` name (`Gn64_KalimariDesert`; case ignored, `.szs` optional), or two numbers
`CUP SLOT`: the cup button 0..7 (0..3 the new cups Mushroom, Flower, Star, Special; 4..7 the retro cups Shell, Banana,
Leaf, Lightning) and the course's button 0..3 in that cup. A battle course is its `.szs` name (`Bn64_BigDonut`) or its
button 0..5. **Button numbers are not ECourseIDs** ([course table](../emulator/menus.md#reaching-a-course)).

## Emulator control

### `start [--unlock] [--vs] [--run] [--save] [--speed SPEED]`

Launch Azahar with the game, frozen at its first frame with the hooks installed. Console output goes to
`mk7-llm-research/local/azahar/console.txt`.

| Argument | Description |
| --- | --- |
| `--unlock` | before the game runs, patch every cup, character and kart part to count as unlocked (as `unlock`); the save is not changed. Use it unless the research needs the save's own locks |
| `--vs` | single-player VS for this run: the single-player menu's Time Trials button leads to VS; time trials and battles are off ([vs.md](../emulator/vs.md)) |
| `--run` | let the game boot freely instead of freezing at frame 1; the hooks are installed by the next command |
| `--save` | let the game write its save and other files; by default those writes do nothing, so every run starts from the same save ([Saving is disabled](../emulator/hooks.md#saving-is-disabled)) |
| `--speed SPEED` | emulation speed for this run: `unlimited` (default; also `max` or `0`), a percent of real time (`100`), or `default` (also `azahar`: Azahar's own frame limit) |

### `stop`

Close the Azahar started by `start`. No arguments.

### `status`

Print the frame counter, frozen or running (with the frame rate), whether saving is disabled, VS, whether the player
drives as a CPU, the scene and the running pages. No arguments.

### `speed SPEED`

Change the emulation speed of this run ([Emulation speed](../emulator/azahar.md#emulation-speed)).

| Argument | Description |
| --- | --- |
| `SPEED` | `unlimited` (or `max`, `0`), a percent (`100` = real time), or `default` (or `azahar`: Azahar's frame limit) |

### `screenshot [PATH] [--scale N] [--window]`

Save the next frame Azahar renders, both screens, as a PNG ([Screenshots](../emulator/azahar.md#screenshots)).

| Argument | Description |
| --- | --- |
| `PATH` | PNG to write; default `mk7-llm-research/local/azahar/shot-<date>-<time>.png` |
| `--scale N` | resolution scale 1..10; default (0) is Azahar's internal resolution |
| `--window` | grab the Azahar window from the screen instead (needs `xwininfo`; the window must be visible and not covered) |

### `stats [--interval S]`

Azahar's game and system frame rate, emulation speed and time per frame ([Frame
rate](../emulator/azahar.md#frame-rate)).

| Argument | Description |
| --- | --- |
| `--interval S` | measure over S seconds (default 1); `0` prints what Azahar's status bar last showed |

## Time and memory

### `freeze`

Park the game thread at the start of the next frame. No arguments.

### `run`

Let the game run freely. No arguments.

### `step [FRAMES]`

Run exactly FRAMES frames, then freeze.

| Argument | Description |
| --- | --- |
| `FRAMES` | number of frames (default 1) |

### `pages [--all]`

Print the sequence tree: sections, classes, states, enter and return codes.

| Argument | Description |
| --- | --- |
| `--all` | also list free (unused) sections; by default only the active ones |

### `wait SECTION [--state STATE] [--timeout S]`

Run until a section reaches a state, then freeze. Fails if it does not happen in time.

| Argument | Description |
| --- | --- |
| `SECTION` | section name (`Page_Title`) ([pages](#numbers-and-pages)) |
| `--state STATE` | state to wait for (default `running`): `free`, `ready`, `entering`, `standby`, `running`, `completed`, `finishing`, `exited` |
| `--timeout S` | give up after S seconds (default 120) |

### `read ADDRESS [SIZE] [-f FORMAT] [--gdb]`

Read the game's memory, live through the RPC server; any address.

| Argument | Description |
| --- | --- |
| `ADDRESS` | start address ([numbers](#numbers-and-pages)) |
| `SIZE` | bytes to read (default 0x40) ([numbers](#numbers-and-pages)) |
| `-f`, `--format FORMAT` | how to print: `hex` (default, rows of bytes), `u32`, `s32`, `f32`, `u16`, `s16`, `u8` (one value per line) |
| `--gdb` | read through the gdb stub instead (halts the game briefly): unmapped memory is reported as an error, where RPC returns zeros |

### `write ADDRESS HEX`

Write bytes to the game's memory; writes to code take effect at once.

| Argument | Description |
| --- | --- |
| `ADDRESS` | start address ([numbers](#numbers-and-pages)) |
| `HEX` | the bytes as hex text, in memory order (`00f020e3`; spaces allowed inside quotes) |

### `call FUNCTION [ARGS ...]`

Call a game function on the game thread at a frame boundary and print `r0`.

| Argument | Description |
| --- | --- |
| `FUNCTION` | the function's address ([numbers](#numbers-and-pages)); symbol names are not accepted, look them up with `mk7 sym` |
| `ARGS` | up to 4 integer arguments, passed in r0..r3 ([numbers](#numbers-and-pages)) |

## Menus

How these work: [menus.md](../emulator/menus.md).

### `buttons [PAGE]`

List the controls of a running page: id, class, the return code a press would give, cursor index, whether a press
would count now.

| Argument | Description |
| --- | --- |
| `PAGE` | the page ([pages](#numbers-and-pages)); default every running page that has input |

### `click PAGE BUTTON [--no-select] [--wait] [--timeout S]`

Press a page's button through its handler, as the game's input path does, then step one frame.

| Argument | Description |
| --- | --- |
| `PAGE` | the page ([pages](#numbers-and-pages)) |
| `BUTTON` | the button: its id from `buttons`, the name of the code it returns (`Next01`, `Back`) or its class (`OKButton`) |
| `--no-select` | do not move the cursor onto the button first |
| `--wait` | first wait for the page to be running |
| `--timeout S` | give up after S seconds of waiting for the page (with `--wait`) or for the button to accept a press (default 120) |

### `complete PAGE CODE [--wait] [--timeout S]`

Complete a running page with a return code directly, skipping the button handlers (the page records nothing; only for
pages without buttons).

| Argument | Description |
| --- | --- |
| `PAGE` | the page ([pages](#numbers-and-pages)) |
| `CODE` | the page's return code: `0`..`7`, `Next00`..`Next07` or `Back` |
| `--wait` | first wait for the page to be running |
| `--timeout S` | with `--wait`: give up after S seconds (default 120) |

### `unlock [--off]`

Make every cup, character and kart part count as unlocked until the game restarts; the save is not changed. Must come
before the menu scene builds its pages: prefer `start --unlock`.

| Argument | Description |
| --- | --- |
| `--off` | restore the game's own checks |

### `character NAME [--page PAGE]`

On the character page, press a character.

| Argument | Description |
| --- | --- |
| `NAME` | `EDriverID` name or number (list in [Driver options](#driver-options)) |
| `--page PAGE` | the character page's section ([pages](#numbers-and-pages)) (default `Page_SingleChara`) |

### `kart [--body B] [--tire T] [--wing W] [--no-ok] [--page PAGE]`

On the kart page, turn the reels to the parts given (Up/Down on the pad, as a player does), then press OK.

| Argument | Description |
| --- | --- |
| `--body B`, `--tire T`, `--wing W` | the parts, as in [Driver options](#driver-options); a part left out stays as it is |
| `--no-ok` | do not press OK after turning the reels |
| `--page PAGE` | the kart page's section ([pages](#numbers-and-pages)) (default `Page_SingleKart`) |

### `settings [SETTINGS]`

On the battle (or VS) settings page, set the rules and the player's team as a player does, then list every setting
and the team.

| Argument | Description |
| --- | --- |
| `SETTINGS` | `--cpu`, `--stage`, `--items`, `--teams`, `--team` ([Settings options](#settings-options)); none given only lists them |

### `tt-course COURSE`

From the time trial cup page (where Change Course and Change Character lead) into the race.

| Argument | Description |
| --- | --- |
| `COURSE` | `.szs` name, or `CUP SLOT` buttons ([Course arguments](#course-arguments)) |

### `battle-course COURSE`

From the battle course page (where Change Course leads) into the battle.

| Argument | Description |
| --- | --- |
| `COURSE` | battle course `.szs` name or button 0..5 |

### `channel [--stay]`

From the title menu into the Mario Kart Channel (its SpotPass dialog answered Cancel) and back.

| Argument | Description |
| --- | --- |
| `--stay` | stay on the channel's top page |

### `multiplayer [--stay]`

From the title menu into the local multiplayer group list and back.

| Argument | Description |
| --- | --- |
| `--stay` | stay on the group list |

### `player MODE`

Who drives the player's kart from the next race on, until the game restarts
([The player as a CPU](../emulator/races.md#the-player-as-a-cpu)).

| Argument | Description |
| --- | --- |
| `MODE` | `normal` (the pad), `cpu` (the game's AI, player type CPU) or `simulated` (the simulated player, as `drive race`) |

## Runs

How runs work: [races.md](../emulator/races.md). `--until` says where a run command stops; the game is left frozen
there.

### `timetrial COURSE [--until WHERE] [--wait-goal] [DRIVER]`

From the title menu straight to a time trial on any race course.

| Argument | Description |
| --- | --- |
| `COURSE` | `.szs` name, or `CUP SLOT` buttons ([Course arguments](#course-arguments)) |
| `--until WHERE` | `race` (default: stop when the race page runs), `results` (finish the run and stop at the menu after the results) or `Page_Title` (finish and quit to the title) |
| `--wait-goal` | with `--until results` or `Page_Title`: let the run end by itself instead of finishing it at once |
| `DRIVER` | [Driver options](#driver-options) |

### `grandprix CUP [--engine E] [--place P] [--until WHERE] [--demo] [--wait-goal] [DRIVER]`

From the title menu through a whole Grand Prix, course intros skipped, each race finished at once at the place given.

| Argument | Description |
| --- | --- |
| `CUP` | cup button 0..7 (0..3 new cups Mushroom, Flower, Star, Special; 4..7 retro cups Shell, Banana, Leaf, Lightning) |
| `--engine E` | 0 50cc (default), 1 100cc, 2 150cc, 3 mirror |
| `--place P` | the player's place in every race (default 1), or four comma-separated places, one per race |
| `--until WHERE` | `race` (the first race page, before the countdown ends), `results` (the menu after the last race), or a page: `Page_WinningRun`, `Page_Trophy`, `Page_Ending`, `Page_Thankyou`, `Page_Title` (default) |
| `--demo` | watch the course intros instead of skipping them |
| `--wait-goal` | do not finish the races at once: wait until each ends by itself (the research drives) |
| `DRIVER` | [Driver options](#driver-options) |

### `battle KIND [COURSE] [--place N] [SETTINGS] [--until WHERE] [--wait-goal] [DRIVER]`

From the title menu through a single-player battle, ended at once with the player at the place given.

| Argument | Description |
| --- | --- |
| `KIND` | `balloon` or `coin` |
| `COURSE` | battle course `.szs` name or button 0..5; sets the stage to choose. Not with `--stage random` or `in-order` |
| `--place N` | the player's place (default 1) |
| `SETTINGS` | [Settings options](#settings-options) |
| `--until WHERE` | `race` (on the race page, before the countdown ends), `results` (the menu after the results) or `Page_Title` (default, back at the title) |
| `--wait-goal` | do not end the battle at once: wait for its clock |
| `DRIVER` | [Driver options](#driver-options) |

### `vs [COURSE ...] [--place P] [--class C] [--cpu off|on] [SETTINGS] [--until WHERE] [--wait-goal] [DRIVER]`

Only in a run started with `start --vs`: from the title menu through a single-player VS run of 4 races against 7 CPUs,
each finished at once at the place given, then the trophy and the title ([vs.md](../emulator/vs.md)).

| Argument | Description |
| --- | --- |
| `COURSE ...` | the course of each race by `.szs` name (sets the stage to choose); with `--stage in-order` only the first; none with `--stage random` |
| `--place P` | the player's place in every race (default 1), or one per race, comma-separated |
| `--class C` | `50cc`, `100cc` or `150cc`; left out, the page keeps what it has |
| `--cpu off\|on` | CPUs on (default) or off (the player races alone) |
| `SETTINGS` | `--stage`, `--items`, `--teams`, `--team` ([Settings options](#settings-options)) |
| `--until WHERE` | `race` (the first race page, before the countdown ends), `results` (the menu after the next results) or `Page_Title` (default, back at the title after the trophy) |
| `--wait-goal` | do not finish the races at once: wait until each ends by itself |
| `DRIVER` | [Driver options](#driver-options) |

### `continue [--place P] [--until WHERE] [--wait-goal] [--demo] [--course C ...]`

Carry the run on from where it is (race, pause, goal, results, replay): a race under way is finished at once, the
results pressed through, then the next race, the trophy and the scenes after it, or quit to the title (time trial,
battle).

| Argument | Description |
| --- | --- |
| `--place P` | the player's place (default 1), or one per remaining race, comma-separated |
| `--until WHERE` | `race` (the next race page), `results` (the next result menu), or a page: `Page_WinningRun`, `Page_Trophy`, `Page_Ending`, `Page_Thankyou`, `Page_Title` (default) |
| `--wait-goal` | let a race under way end by itself instead of finishing it |
| `--demo` | watch the course intros |
| `--course C` | VS with the stage at choose: the course of the next race (`.szs` name); repeat once per race left |

### `menu [OPTION]`

Choose an option of the race page's menu: opens the pause menu (Start), the replay menu (A) or, at the goal, the
result menu. Without an option, list the options offered
([the menus](../emulator/races.md#runs)).

| Argument | Description |
| --- | --- |
| `OPTION` | `continue`, `restart`, `course`, `character`, `replay`, `next`, `trophy` or `quit` (answers Yes to the Grand Prix's "quit?") |

### `finish [--place N | --order IDS] [--no-results]`

End the race now with the places chosen, then press A through the result screens to the race page's menu.

| Argument | Description |
| --- | --- |
| `--place N` | the player's place (default 1); the other karts keep their id order |
| `--order IDS` | player ids in finishing order, comma-separated, instead of `--place` |
| `--no-results` | stop at the goal, before the result screens |

### `advance PAGE [--no-press] [--frames N]`

Press A every 30 frames until a page runs: the winning run, trophy, ending and thank-you screens read the pad, not page
buttons.

| Argument | Description |
| --- | --- |
| `PAGE` | section to wait for (`Page_Trophy`, `Page_Ending`, `Page_Title`) ([pages](#numbers-and-pages)) |
| `--no-press` | only let the game run, press nothing |
| `--frames N` | give up after N frames (default 36000) |

### `skip-demo`

Skip the course intro of a Grand Prix race (A on `Page_Demo`). No arguments.

### `race-start [--timeout S]`

Run until the countdown is over (the race timer runs), then freeze.

| Argument | Description |
| --- | --- |
| `--timeout S` | give up after S seconds (default 300) |

## Race state and driving

### `race [-p N]`

Print the course (ECourseID and `.szs` name), the checkpoint state (none in a battle) and the position of a kart.

| Argument | Description |
| --- | --- |
| `-p`, `--player N` | the kart's player index (default 0, the player) |

### `teleport X Y Z [-p N]`

Move a kart to a position and stop it. One big jump breaks race progress; move in steps.

| Argument | Description |
| --- | --- |
| `X`, `Y`, `Z` | the position, in course coordinates |
| `-p`, `--player N` | the kart's player index (default 0, the player) |

### `drive ACTION [X Y Z] [--radius R] [--forward] [--no-drift] [--no-trick] [--wait] [--timeout S]`

The [simulated player](../emulator/simulated-player.md): drive the player's kart with computed inputs. Races and
battles.

| Argument | Description |
| --- | --- |
| `ACTION` | `goto` (straight to the point), `route` (along the CPUs' route to the route point nearest the point, then as `goto`), `race` (drive the race along the route, in every race until `off`), `off` (back to the pad), `status` |
| `X Y Z` | `goto`, `route`: the target point |
| `--radius R` | `goto`, `route`: stop within R units of the point (default 150) |
| `--forward` | `route`: only along the route's direction, as CPUs drive; by default the shortest way, also backwards |
| `--no-drift` | `route`, `race`: never drift |
| `--no-trick` | `route`, `race`: never hop at trick chances |
| `--wait` | run the game until the point is reached (`race`: until the goal), then freeze |
| `--timeout S` | with `--wait`: give up after S seconds (default 300) |

## Use examples

Boot, reach a race on Wuhu Loop, stop at the end of the countdown, look around:

```
mk7-llm-research/mk7 emu start --unlock
mk7-llm-research/mk7 emu timetrial Gctr_WuhuIsland1
mk7-llm-research/mk7 emu race-start
mk7-llm-research/mk7 emu race
mk7-llm-research/mk7 emu step 60
mk7-llm-research/mk7 emu read 0x006789B8 0x20 -f u32
```

Other combinations:

```
mk7-llm-research/mk7 emu timetrial 4 1 --player cpu         # Shell cup, slot 1 (GBA Bowser Castle 1), AI drives
mk7-llm-research/mk7 emu grandprix 0 --engine 2 --player simulated --wait-goal   # whole cup, simulated player
mk7-llm-research/mk7 emu battle balloon Bn64_BigDonut --until race --team red
mk7-llm-research/mk7 emu continue --until race                 # next race of the run
```
