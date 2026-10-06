# Menus and reaching a course

How `mk7 emu` drives the game's menus: which run reaches which course, how page buttons are pressed, the character,
kart and settings pages, and the menus outside single player. Part of [EMULATOR.md](../EMULATOR.md). Read it when
getting the game to a course or a page, or when a menu command does not do what is expected.

## Contents

- [Reaching a course](#reaching-a-course): which run to use, course names versus button numbers, the course table
- [Navigating the menus](#navigating-the-menus): `buttons`, `click`, `complete`, the time trial path, `unlock`
- [Character and kart](#character-and-kart): where the pages keep the choice, how the reels are turned
- [Battle and VS settings](#battle-and-vs-settings): the settings controls, their values, teams
- [Menus outside single player](#menus-outside-single-player): the Mario Kart Channel, local multiplayer
- [Measurements](#measurements): time to reach a course

## Reaching a course

**To get to a course, use a time trial unless the research needs the other karts.** `timetrial` goes from the title
straight to any of the 32 race courses. A Grand Prix only reaches the second, third or fourth race of a cup after
finishing the ones before it, with their result screens. Battle courses are reached directly with `battle`.

| Run | Karts | Reaches |
| --- | --- | --- |
| `timetrial COURSE` | the player alone; with `--player cpu` the AI drives it (an `AIManager` without a rank manager, [The player as a CPU](races.md#the-player-as-a-cpu)) | any race course, at once |
| `grandprix CUP --until race`, then `continue --until race` | the player and 7 CPUs, rubber-banding against the player | the cup's races in order |
| `battle KIND COURSE --until race` | the player and 7 CPUs | any battle course, at once |
| `vs COURSE ... --until race` (after `start --vs`) | the player and 7 CPUs (or alone with `--cpu off`), rubber-banding against the player | any race course, at once; the next races on the courses given |

With `start --vs`, VS puts any race course and seven CPUs together at once ([vs.md](vs.md)); that run has no time
trials and no battles. Without it, a Grand Prix is the only way.

Courses are named by their `.szs` archive (`Course/<name>.szs`, [GAME_DATA.md](../GAME_DATA.md)), which is also the
name of their `RaceSys::ECourseID` value. Every command that takes a course takes that name (case ignored, `.szs`
optional). **The numbers these commands take are the positions of the menu buttons, not ECourseIDs**:
`timetrial CUP SLOT` (cup 0..7, slot 0..3) and the battle course 0..5. `race` prints both the ECourseID and the name,
so check it before sampling. `courses.py` holds the game's own tables: `Sequence::GetGPCourse` (cup and slot, table at
0x00694648) and `Sequence::GetBattleCourse` (table at 0x006946C8), both written by a static initializer at
0x00564350, which is where the course pages' buttons take their course from.

| Cup (button) | Slot 0 | Slot 1 | Slot 2 | Slot 3 |
| --- | --- | --- | --- | --- |
| 0 Mushroom | Gctr_ToadCircuit (4) | Gctr_GlideLake (3) | Gctr_MarineRoad (2) | Gctr_SandTown (5) |
| 1 Flower | Gctr_WuhuIsland1 (8) | Gctr_MarioCircuit (0) | Gctr_MusicPark (15) | Gctr_RallyCourse (1) |
| 2 Star | Gctr_UnderGround (12) | Gctr_WarioShip (14) | Gctr_AdvancedCircuit (6) | Gctr_WuhuIsland2 (9) |
| 3 Special | Gctr_DKJungle (7) | Gctr_IceSlider (10) | Gctr_BowserCastle (11) | Gctr_RainbowRoad (13) |
| 4 Shell | Gn64_LuigiCircuit (26) | Gagb_BowserCastle1 (29) | Gwii_MushroomGorge (19) | Gds_LuigisMansion (20) |
| 5 Banana | Gn64_KoopaTroopaBeach (28) | Gsfc_MarioCircuit2 (30) | Gwii_CoconutMall (16) | Gds_WaluigiPinball (23) |
| 6 Leaf | Gn64_KalimariDesert (27) | Gds_DKPass (22) | Ggc_DaisyCruiser (25) | Gwii_MapleTreeway (18) |
| 7 Lightning | Gwii_KoopaCape (17) | Ggc_DinoDinoJungle (24) | Gds_AirshipFortress (21) | Gsfc_RainbowRoad (31) |

Battle course buttons: 0 Bagb_BattleCourse1 (37), 1 Bn64_BigDonut (36), 2 Bds_PalmShore (35), 3 Bctr_HoneyStage
(33), 4 Bctr_IceRink (34), 5 Bctr_WuhuIsland3 (32). `Gctr_WinningRun` (38) is only the Grand Prix winning run.

## Navigating the menus

Menus are driven through the buttons of the pages, the way the game's own input path presses them, with no pad input and
no waiting by frame counts. How pages, manipulators and buttons work is in the research on scene and menu sequencing
(BSEQ), Finding 13 (How button controls complete pages); `menu.py` names the functions and offsets it uses.

- `buttons PAGE` lists the controls of a running page: id, class (from the game's `getDTIClassInfo`), the return code
  a press would give (named by the page class), the cursor index, and whether a press would count now. Not every
  control is a button (the kart page's reels, the ghost list).
- `click PAGE BUTTON` waits until a press would count (the page runs, its manipulator has the input, no fade, the
  button is ready), moves the cursor onto the button, then calls its handler at the start of a frame. The page records
  the choice exactly as with real input. `BUTTON` is an id, a return code name (`Next01`, `Back`) or a class
  (`OKButton`).
- `complete PAGE CODE` completes a page with a return code directly. It skips the button handler, so the page records
  nothing (completing `Page_SingleChara` that way left it in `finishing` for good): only for pages without buttons.
- The flow lists of the `.bss` files say which return code leads to which page.
- The time trial path, as `timetrial` does it: `Page_Title` (Single Player), `Page_SingleMode` (Time Trials),
  `Page_SingleChara`, `Page_SingleKart`, `Page_SingleCup` (cursor 0..7), `Page_SingleCourse` (cursor 0..3),
  `Page_SingleGhost` (`OKButton`, then the menu's `RaceDialogButton`).
- A fresh save only has some cups. `unlock` patches the `System::Flag::IsOpen*` tests for this run only, and the
  save-based tests the menus use for characters and kart parts (`sub_00452b20`, `sub_00452b70`, `sub_00452bc0`,
  `sub_00452c10`: a bit per entry in the save's unlock masks; the character page asks through `sub_004d1b08`). **It has
  to come before the menu scene builds its pages**: the cup pages decide which cups are locked when they are built, and
  patching later leaves them locked. `start --unlock` writes the patches at the game's first instruction, before
  anything runs. Without it, `start` leaves the game frozen at frame 1, so `unlock` still works at any time and after
  any other command until something lets the game run ([Starting frozen at boot](hooks.md#starting-frozen-at-boot)).
- The character and kart pages show what the save has just unlocked (a character after a trophy, ...) as a
  `PresentBox` that holds the input until it is opened; `Menu` opens those before pressing another button.

## Character and kart

- The character page (`MenuSingle_Chara`) keeps the `EDriverID` that each cursor slot shows at `+0x2B0` (17 slots,
  0x13 for a locked one); `choose_character` presses the slot of the driver asked for. With `unlock` all 16
  characters and the Mii slot are there.
- The kart page (`MenuSingle_Kart`) has three `UI::SlotSelect` reels: `+0x2A8` body (17 entries), `+0x2A4` tire (10),
  `+0x2AC` glider (7); each holds its entries' ids (`+0x41C`, 0x1C each, id at +0x14) and the current one (`+0x7C`).
  `choose_kart` moves the cursor onto a reel and presses Up or Down on the pad (Down goes to the previous entry), as
  a player does, so the reels, the model and the race info all follow. `SlotSelect::selectBody` and the like (the
  game's own setters) change the choice and the model but leave the reel graphics where they were.
- The choice ends up in the menu's race info (`MenuData + 0x74`, `Sequence::GetRaceInfo`, `CRaceInfo::CKartInfo`:
  body, tire, wing, screw, driver); the race's own copy is `RaceDirector + 0x2C`.

## Battle and VS settings

The page after the kart page of a single-player battle, `Page_SingleSetting` (`Sequence::MenuSingle_Setting`), has four
`UI::LRSelect` controls; with `start --vs` the same page builds the five of VS (class, CPU, courses, items, teams;
[vs.md](vs.md)). `settings` reads them; `set_setting` moves the cursor onto one and presses Left or Right on the pad
until it shows the value, as a player does, so `LRSelect::apply` and the page's `inputHandler` run. Each control has
its value at `+0x7C`, its range at `+0x80` / `+0x84` and its `LRSelect::ESettingType` at `+0x40C`. Names as the page
shows them:

| Setting | Type | Values | `LRSelect::apply` writes |
| --- | --- | --- | --- |
| `class` (VS) | 0 | 0 50cc, 1 100cc, 2 150cc | `BasePage::setCC` (`CRaceInfo::m_engine_level`) |
| `cpu-on` (VS; `vs --cpu`) | 1 | 0 off, 1 on | `MenuData + 0x668` 0 or 2 (normal) |
| `cpu` | 2 | 1 easy, 2 normal, 3 hard | `MenuData + 0x668` (`Sequence::GetEnemyLevel`); the race's AI level is then 0 / 1 / 2 (`AIManager::calcAILevel_`) |
| `stage` | 3 | 0 choose, 1 random, 2 in order | `MenuData + 0x669`; with random or in order, OK opens the start dialog on the same page instead of the course page |
| `items` | 4 | 0 all, 1 shells, 2 bananas, 3 mushrooms, 4 bob-ombs | `CRaceInfo::m_item_pattern` (`EItemPattern` 0, 2, 3, 1, 4) |
| `teams` | 5 | 0 off, 1 on | `CRaceInfo::m_is_team_mode` |

- The values stay as they were left for the next battle of the run. `battle` with a course sets the stage to choose.
- Teams: turning them on deals the karts into Red and Blue at random (`MenuSingle_Setting::shuffleTeam`); the team is
  `CKartInfo::m_team_type` (`+0x18`, `ETeamType`: 0 red, 1 blue, 3 while teams are off). On the page, L puts the player
  on Red and R on Blue (`keyHandlerCore` -> `moveTeam`), and the page moves a random kart of that team to the other one
  to keep four on each side. `choose_team` presses L or R through the pad hook.
- The race gets the teams, the team mode and the item pattern as set (read in `RaceDirector + 0x2C`).

## Menus outside single player

- The Mario Kart Channel (`Seq_CH`, title button `Next03`): on its first visit of a run the game asks "SpotPass
  will be activated for this software." (OK / Cancel); `open_channel` answers Cancel. The top page is
  `Page_ChannelTop`; its Back button is `MchBtnB`. Opening the channel rebuilds the game's StreetPass box (cecd).
- Local multiplayer (`Seq_Multi`, title button `Next01`) starts on `Page_MultiGroup`, the list of groups; its Back
  (`BackButtonB`) returns to the title.

## Measurements

- Measured on 2026-10-05: 9 s from `start` to the race page of a time trial; a Grand Prix race with its result screens
  takes about a minute unthrottled.
- A `click` on a ready page takes about 0.3 s.
- The settings table above was read on 2026-10-04.
