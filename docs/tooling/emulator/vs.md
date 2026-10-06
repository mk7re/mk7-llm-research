# Single-player VS

`start --vs`: VS races against CPUs from the single-player menus, which the retail game only has in local and online
multiplayer. Part of [EMULATOR.md](../EMULATOR.md). Read it when a run needs any race course with seven CPUs at once,
or when changing `vs.py`.

## Contents

- [What the run looks like](#what-the-run-looks-like): menus, settings, grid, races, quitting
- [How it is done](#how-it-is-done): where the patches live and what they fix
- [Measurements](#measurements): load times

## What the run looks like

`start --vs` writes the patches of `vs.py` at the game's first instruction; they hold until the game restarts.

- The single-player mode page shows Grand Prix and VS Race only: the Time Trials button becomes VS (rule mode 2,
  with the icon, label, caption, text and movie local multiplayer uses), Balloon and Coin Battle are hidden and do
  nothing. **Time trials and battles are off for the run**: their flows and pages are reused for VS.
- VS goes character, kart, the VS settings (class, CPU off/on, courses choose/random/in order, items, teams), then
  with Choose or In order the cup page and the time trial's course page (no ghost page, no record chart; a course
  opens the "Start Race" dialog, whose OK fades out into the race), with Random the start dialog of the settings
  page. 7 CPUs with CPU on (the default of `vs`), rubber-banding against the player; with CPU off the player races
  alone, from the centered start of a time trial (with teams on, alone on the player's team). Play mode stays single
  player.
- The first race starts from a Grand Prix grid: the player 8th, the CPUs 7th to 1st. Without that the settings page
  left every race rank at 0 and all eight karts started at one point ((-1, 0, 0) on Mario Circuit).
- The garage behind the menus (`Menu3D::GarageDirector`) has no single-player VS states; it runs the multiplayer VS
  ones for the character, kart, rules, cup and course pages (lights, shutter, the OK whiteout).
- A run is 4 races (`MenuData + 0x66C`, `Sequence::IsLastRace`), with VS points; Next Race goes to the cup page
  (Choose) or straight to the next course (`BasePage::loadNextCourse`: random, or the next in cup order); after the
  4th race the trophy scene shows the final standings, then the title. Quit leads to the title.
- On the cup page after a race (Choose), Back asks "Are you sure you want to quit?"; Yes fades out (as the battle
  course page's Yes) and loads the menu scene again at the title, as Quit on the race page does. (Going to the title
  within the same scene, as the battle course page does, left the garage's kart model hidden, and the next character
  page waited for it for good.)
- Multiplayer VS is not meant to run with `--vs`: some of its flows now lead to the single-player menus and the title.

## How it is done

- What the patches do and why (the race page set-up, the course choice, the points, the trophy page's network wait,
  the flow entries rewritten in the loaded `.bss` / `.brs` files by a hook in `SequenceResource::create`, the garage,
  the course and cup page hooks) is in the docstring of `vs.py`. Its code is in two slots of the
  [code pages](hooks.md#code-pages).
- Teams with CPUs: the game sorts the CPUs into rank groups per team (`AIRankManager::decideAllGroupTeamMode_`) from a
  table indexed by the number of red karts instead of the humans on red; with one human it read stack garbage and
  each race scene load became very slow (same frame count, each frame slow). `vs.py` gives it the humans on red
  ([vs.py](../../../tools/mk7re/dynamic/vs.py) docstring).

## Measurements

- Checked on 2026-10-05 with Choose, Random, In order and teams: 4 races each, trophy, back to the title, menus built
  twice in a run.
- Before the teams fix, each race scene load took about 28 s instead of 2 s.
- Unthrottled, with that fix (2026-10-05): menu to race page about 300 frames (2.5 s), Next Race to the next race page
  about 265 frames (1.5-2 s), teams on or off. Compare wall time as well as frames: a slow load keeps the frame count.
  A Grand Prix takes 270 frames from the menu to its course intro.
