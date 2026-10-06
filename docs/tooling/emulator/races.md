# Races, runs and the player as a CPU

What happens after a race and how `mk7 emu` ends races and carries runs on, the race page's menus, and the player's
kart driven by the game's AI. Part of [EMULATOR.md](../EMULATOR.md). Read it when a research step happens during or
after a race, or when the player's kart has to drive by itself.

## Contents

- [After a race](#after-a-race): the scenes after the last race, how races and battles are ended at once
- [Runs](#runs): stopping a run and carrying it on, the race page's menus
- [The player as a CPU](#the-player-as-a-cpu): `player cpu`, AI level, rubber-banding, time trials, ghosts
- [Measurements](#measurements): which cups reach which scenes, CPU runs

## After a race

The Grand Prix scenes follow `Root-Default.brs`: the menu, then for each race the course intro (`DemoScene`,
`Page_Demo`) and the race (`RaceScene`, `Page_Race`); after the last race `SingleGP_Trophy` leads to the winning run
(`WinningRunScene`, only in the top 3: `WinningRunSelectTask`), the trophy (`TrophyScene`), and for the Special and
Lightning cups with a trophy (`TrophyPage::selectNextScene`) the ending (`EndingScene`, the credits) and
`ThankyouScene`, then the title.

- `Race.finish` ends a race at once with the places chosen (GP, VS and time trials, offline). It ranks the karts,
  calls `ModeManagerRace::allGoalProc`, which finishes every kart that has not, and switches the race state to Goal,
  as `calcRace` does when the player finishes. The race then goes on as after a real finish: Grand Prix points,
  trophies and unlocks count for the rest of the run (and reach the save only with `start --save`).
- `Race.finish_battle` ends a balloon or coin battle the way its clock does: it gives the karts scores in the order
  chosen (points at `KartInfo+0x54`, coins at `+0x46` of the mode manager's KartInfo) and sets the frames left of
  the battle clock (`RaceTimer::m_frame_watch`, a `CFrameDecWatch`, +0x4) to 1. `ModeManagerBattle::calcRace` then
  ends the battle ("TIME'S UP!") and ranks the karts by score. Writing the displayed time (`RaceTimer+0x10`) does
  nothing: `RaceTimer::calc` recomputes it from the frame watch every frame.
- A single-player battle and a time trial end on the race page's menu (battle: Change Course, Quit; time trial:
  Retry, ..., Quit); `Flow` quits them to the title.
- These screens read the pad instead of page buttons. `Session.press` holds buttons through the pad hook;
  `UI::tstDemoButton` (A or Start) completes the course intro (`DemoPage::onPagePreStep`, otherwise after 700
  frames), the winning run, the trophy and the thank-you page. The ending accepts it only once the game counts it as
  seen (`System::Flag::IsOpen`, which `unlock` opens); otherwise it runs to its end.
- The race results take many presses of A, one every 30 frames (the early ones do nothing), before the race page
  opens its menu (`Race.results_menu`; [Measurements](#measurements)).

## Runs

A run does not have to be finished at once. `grandprix`, `battle`, `vs` and `timetrial` with `--until race` stop on
the first race page; the research then steps, reads or moves karts, and `continue` carries the run on from there (or
`finish` ends just this race, `menu ...` chooses a menu option). `Flow.resume` decides from the state of the race
page: a countdown is waited out, a race under way is finished at once (`instant=True`) or left to end by itself
(`--wait-goal`: `Race.wait_goal` lets the game run until the race state is goal, e.g. while the research drives), a
pause menu is closed, the goal is pressed through to the result menu, then the next race, the trophy, or Quit.

The race page's menus (`Flow.menu_option` names in brackets):

| Menu | Opened by | Options |
| --- | --- | --- |
| time trial pause | Start | Continue (`continue`), Restart (`restart`), Change Course (`course`: the cup page), Change Character (`character`: the character page, the kart page, the cup page), Quit (`quit`: the title) |
| time trial results | the result screens | Retry, Change Course, Change Character, Replay (`replay`), Quit |
| time trial replay | A, while the replay runs | Continue Replay, Retry, Change Course, Change Character, Restart Replay (`replay`), Quit |
| Grand Prix pause | Start | Continue, Quit (a Yes/No dialog on `Page_CommonSystemDialog`, Yes is cursor 2; then the title) |
| Grand Prix results | the result screens | Next Race (`next`) or, after the last race, Trophy (`trophy`), Replay, Quit |
| Grand Prix replay | A, while the replay runs | Continue Replay, Next Race, Restart Replay, Quit |
| battle pause | Start | Continue, Quit (no dialog) |
| battle results | the result screens | Change Course (`course`: the battle course page; `SingleBB_Course` balloon, `SingleBC_Course` coin), Quit |
| VS pause (`start --vs`) | Start | Continue, Quit (Yes/No dialog, as in a Grand Prix; then the title) |
| VS results | the result screens | Next Race (`next`, `MultiVS_Next`, courses random or in order; `course`, `MultiVS_Course`, courses choose: the cup page) or, after the 4th race, Trophy (`trophy`), Quit |

- The page takes Start or A only while the race runs (race state `race`) and its menu is fully closed (menu state
  0, `BasePage+0x8F`); a press while it closes (state 5) is lost. `Race.pause` waits for both.
- A replay plays the recorded run in play mode `Replay` and starts over when it reaches the end of the data
  (scene reload, countdown). A race finished at once has only what was driven before `finish` in it.
- `system_dialog_has_input` only sees dialogs that `Page_CommonSystemDialog` owns itself (the SpotPass question);
  the Grand Prix's "quit?" dialog belongs to the race page but takes the input the same way (`active_manipulator`).

## The player as a CPU

`player cpu` (`Menu.cpu_player`, `--player cpu`) gives the player's `CKartInfo::m_player_type` CPU (1) instead of
Master (0). The kart is then built as a CPU's (`Kart::Unit`: every type except Master, User, Ghost and Master_Replay;
`VehicleBase` +0x99, +0x9A and +0x9B set) and the AI drives it. The camera, the HUD and `m_detail_kart_id` still follow
it, and the race ends when it finishes, as for the player.

- The single-player menus give the player Master in two places: the character page (`MenuSingle_Chara::buttonHandler_OK`
  -> `setDriver(player, driver, Master)`) and the race page when it is left (`BaseRacePage::complete` ->
  `setPlayerType(player, Master)` for Next Race, Retry, Change Course and Change Character; Master_Replay for a replay).
  Writing the type once is not enough: race 2 of a Grand Prix had the player back on Master. `cpu_player` patches both
  to give CPU (`CPU_PLAYER_PATCHES` in `menu.py`) and changes the menu's race info at once, so it counts from the next
  race built, until the game restarts or `player normal`.
- AI level: one level holds for every AI of a race, `AIManager::m_ai_level` (`calcAILevel_`): the engine class in Grand
  Prix, VS and time trials (50cc easy, 100cc normal, 150cc and mirror hard), the `cpu` setting in a single-player
  battle, 2 in multiplayer. The player's AI gets it like the others; nothing has to be set per kart.
- Rubber-banding: in a Grand Prix and VS, `AIRankManager` manages the CPUs' speed. It keeps CPUs and human karts in two
  lists (`registerAI`, by `VehicleBase + 0x99`), and `watchPlayerAndCpuTop_` / `watchPlayerAndCpuLast_` speed the CPUs
  up or down against the human karts. With the player as a CPU there are 8 CPUs and no human kart: the rank groups still
  work (`decideAllGroup_` sizes them by the number of CPUs) and the player's kart is ranked like any CPU, but the
  catch-up against a human does not run. Before each race `AIManager::init` picks the top group's type from the humans'
  Grand Prix points; with no human it counts 0.
- Time trials: the game builds an `AIManager` for them too (race mode flag bit 1), without a rank manager
  (`IsRaceTypeNeedsRankManagement` excludes them).
- The ghost recording: the pad director (`KDPadDirector`, `SystemEngine` + 0x3C) starts and finishes the pads of
  its race list (`startRace`, and `finishRace` as a goal delegate of `ModeManagerBase::stateInitGoal`). A human
  player's kart has the `KDPlayerRecordPad` there; a CPU player's has a `KDAIPad`, so the player's recording is never
  started or finished. The time trial page waits for it after the goal (`BaseRacePage::calcSave` state 6,
  `KDPlayerRecordPad::getRecordedBuffer`) and never shows its results. `Race.results_menu` (every run command,
  `finish`, `menu`) therefore calls `KDPad::finish` on that pad when the game has not
  (`Race.finish_ghost_recording`). The recording is empty: the ghost of a Retry stays at the start line, and a replay
  of the run has no inputs.
- Battles: `AIControlBattle` drives the player's kart.

## Measurements

- Race results, 2026-10-03: about 20 presses of A, one every 30 frames, before the race page opened its menu.
- Scenes after a Grand Prix, 2026-10-03: Mushroom Cup in 4th went straight to the trophy ("Too bad"), Special Cup in
  1st and Lightning Cup in 3rd went through the winning run, the trophy and the ending. The race page's menus were
  read the same day.
- AI level of the player as a CPU: level 2 and base speed ratio 1.0 for all eight karts at 150cc, level 1 in a battle
  set to normal.
- Time trial with the player as a CPU, Wuhu Loop at 150cc: the CPU drove the run to the goal in 1:47.178.
- Ghost recording fix, 2026-10-06 (GBA Bowser Castle 1): the results opened after the AI's run and after a Retry, and
  the run quit to the title.
- Battle with the player as a CPU and teams on: the AI drove until the clock ran out.
