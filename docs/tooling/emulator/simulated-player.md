# The simulated player

`drive` and `--player simulated`: the player's kart driven by inputs computed inside the game every frame, for
research that needs the kart to go somewhere or drive a race. Part of [EMULATOR.md](../EMULATOR.md). Read it when
using or changing `drive`, `driver.py` or `driver.c`.

## Contents

- [Modes](#modes): what `goto`, `route` and `race` do and how long they hold
- [How it drives](#how-it-drives): input path, route, steering, re-routes, back-up, drifts, tricks, start boost
- [Tuning and vehicle data](#tuning-and-vehicle-data): `driver.TUNING`, the vehicle's matrix and velocity
- [Measurements](#measurements): drift radii, start boost window, turning in place; lap and race times per course,
  tuning history

## Modes

`drive` and `--player simulated` (`driver.py`, `driver.c`) drive the player's kart with inputs computed inside the game
every frame, while the player stays a human player (Master): the rubber-banding, the ghost recorder and the race end
treat it as one. A mode holds until the game restarts or `drive off`; `drive race` (and `player simulated`) holds
across races, `goto` and `route` end at the next countdown. Everything is decided by the C code in the game, so the
kart keeps driving between commands and whatever the emulation speed.

## How it drives

The findings cited here are those of the research on enemy AI behaviour and enemy points (KMP ENPT / ENPH), which
describes how the CPUs drive along the same route.

- **Where the inputs go in.** A human kart's input has its own path, apart from the menus'. `KDPadInputer::calcInput`
  (0x004419E4) fills the pad's `KDPadDataOnFrame` from the console pad (game button bits; the stick in steps 0..14,
  7 the centre); `KDPadControllerCore::calcImpl_` turns it into the button mask and stick that
  `VehicleControl::updateLocal` reads. A hook on calcInput's last instruction (0x00441A48) calls `drive_frame`
  (`driver.c`), which overwrites that data while a mode is on and the race runs. The kart is the one whose
  `VehicleControl::m_player_pad` (+0xE0) is the hooked pad. The menus, which read the console pad and the UI pads, are
  not affected; nothing is given during a pause (`KDPad::calc` skips a paused pad), after the goal (the game drives
  the kart then), while Lakitu has the kart or during a Bullet Bill (the game drives it). In mirror mode the pad gets a
  `KDPadMirrorInputer`, which only overrides `inputStick` (it flips the stick); the hook runs after it, so the driver's
  stick, worked out in the course's coordinates, reaches the kart unflipped.
- **The route.** In a race the CPUs' route as re-sampled for races (`AIPathManager` + 0x28, a point every 75 to 150
  units, also built in time trials; `Race.enemy_route`), in a battle the KMP's enemy points
  (`Field::GetEnemyPointAccessor`, two-way links). `route` searches the shortest way (Dijkstra, in the game's code)
  from the route point nearest the kart to the one nearest the target, along the links both ways unless `--forward`
  (then only as CPUs drive); a mushroom shortcut is only taken when there is no other way. `race` follows the links
  lap after lap and chooses at forks as CPUs do (never a mushroom shortcut when there is another branch, else at
  random); in a battle it wanders along the paths. "Nearest" is searched as `findNearEnemyPoint` does: within 500
  units horizontally and each point's max search Y offset. The search runs again whenever the kart is re-routed.
- **Following it** (Finding 5, Reaching a point): a point counts as reached within 280 units (100 in battle, 140
  after a point with flag 0x04) or, in a race, beyond the plane that bisects the turn at it. The kart aims at the
  farthest route point up to 400 + 40 x speed units ahead along the route (half after a point with flag 0x04) whose
  straight line from the kart keeps the route points before it within 0.6 of their half-width (scale x 50) + 20, 0.3
  of it without the 20 at points with flag 0x04 (where cutting the line sends CPUs off the course); more than twice
  the half-width + 20 (once the half-width at a 0x04 point) off the stretch it drives along, it aims at the next point
  only (once the half-width + 20 everywhere made the kart weave and fall on Rainbow Road). A kart steered with the
  stick cannot turn at once as the AI does (`AI::setRotateRadAI`), hence the look-ahead. The stick is proportional to
  the angle between the kart's facing (its direction of travel while it drifts: a drifting kart faces well inside its
  travel) and the aim, full at 25 degrees. With the aim more than 55 degrees off the direction of travel (not the
  facing: after a drift the kart faces well off its travel) or the route turning more than 90 degrees within 150 + 30
  x speed units, it brakes above half the top speed, and drives on with the full stick below; more than 45 degrees
  there, it releases A above 70 %. Only with the aim behind the kart, more than 120 degrees off the facing, it brakes,
  then turns in place with A+B.
- **The game's re-routes** (Findings 11 and 12, Stuck CPUs and Re-routes to the nearest point): after 450 frames without
  reaching a point, after 30 frames against a wall, and when the target is steeply above or below after 20 frames while
  airborne, gliding or after a point with flag 0x02, the kart moves to the nearest point if it is on another path than
  its target. Farther than 800 units from the stretch it drives along (a fall, a cannon) and after Lakitu or a Bullet
  Bill, it starts again from the nearest point.
- **Back-up** (AIStuck, Finding 11): slower than 10 % of the top speed for 600 frames (a frame against a wall counts 3),
  it reverses 100 frames (50 in battle) with the stick centred, then drives back to the route three points behind (one
  in battle) and on.
- **Drifts** (Finding 6, Per-field detail: `drift_setting`, flags 0x01, 0x04, 0x10), races only: started toward a corner
  point (`|m_corner| <= 0.998`) with drift setting 0 or 3+ within 400 units, going straight (`m_forward_dir` along the
  facing, 0.99) at more than 60 % of the top speed: R with the full stick toward the corner until the hop has turned
  into a drift (the game takes the drift's side from the stick on landing; a weak stick there gave no drift), then A+R
  with the stick that bends the drift onto the arc through the aim (curvature 2 sin(angle) / distance, x 1.3), read from
  the radius drifts turned at each stick position ([Measurements](#drift-start-boost-and-turning)), so a wide corner is
  drifted with the stick out. The stick held inward charges the mini-turbo faster, so it is held in while the kart is
  farther out than half the half-width inside the route and faces less than 35 degrees inside its travel (without that
  limit the kart turned round in the drift and left Rainbow Road). Ended when the route turns the other way at a corner
  point reached (`|m_corner| <= 0.998`); when the route ahead (150 + 20 x speed units) bends less than 10 degrees toward
  the drift's side: the corner is over; when gliding; when the aim is more than 66 degrees off the facing (78 with flag
  0x10); once the mini-turbo is charged to red (`isMiniTurbo_OverLv2`); and, beyond the game's rules, once drifting,
  when the aim is more than 20 degrees outside or 50 inside the direction of travel, or when the route at the aim bends
  the other way. A drift ended charged with nothing else wrong starts again 3 frames later while the corner goes on.
  Drifting through a point with flag 0x01 or 0x04 or a sharp corner, the aim moves 0.4 of the half-width to the inside.
  The game's AI also ends its drift at points with drift setting 1 or 2 (2 throws the mini-turbo away), lets the blue
  mini-turbo go after 120 frames (unless flag 0x10) and waits until it goes straight to drift again; the simulated
  player is a tool to drive around with, so it drives for speed as a player would, not with the CPUs' limits.
- **Tricks** (Finding 6, Per-field detail: flag 0x08): R at the game's trick chances
  (`VehicleControlAI::calcSmallJumpTimingAI`: byte `VehicleMove` +0xFE8, a glider pad 3 frames after landing, or
  `m_trick_frames`) unless the target has flag 0x08 or, beyond the game's rules, a sharp corner (as for easing off) is
  close ahead: the trick's boost carried the kart off SNES Rainbow Road's corners; in battle only at points with flag
  0x80.
- **Start boost** (race mode): A held from frame 124 of the 241-frame countdown, in the middle of the window that gives
  a full boost ([Measurements](#drift-start-boost-and-turning)). The CPUs get theirs without input
  (`AIControlBase::setStartDashTypeToKart`, `VehicleMove` +0xC24).
- Left out: items, objects (train crossings, moving boards) and other karts.

## Tuning and vehicle data

The numbers above are tunable in the control block (`driver.TUNING`). The vehicle's matrix (`Rigid::m_kd_mtx`,
+0x0) holds the columns side, up, forward and position; its velocity is `VehicleMove::m_xyz_speed_vec` (+0xC60);
stick +x turns right. A and B held with the full stick turn a stopped kart in place without moving it
([Measurements](#drift-start-boost-and-turning)).

## Measurements

### Drift, start boost and turning

- Drift radius by stick position, measured on N64 Luigi Raceway at 150cc: about 340 with the stick fully in, 450
  centred, 780 half out, 1600 fully out.
- Start boost, measured on Mario Circuit: A held from frame 122-126 of the countdown gave a full boost, 130-149 a
  smaller one, 120 or earlier the wheels spun.
- Measured on 2026-10-05/06: A and B held with the full stick turned a stopped kart in place about 2 degrees per
  frame; pressing them in turn hardly turned it.

### Lap and race times

- **Measured on 2026-10-06** (150cc time trials, the menu's default driver and kart, unthrottled; repeated runs
  came out close: the same settings gave 2:41.802 and 2:41.814 on Mario Circuit). Every race course was driven to the
  goal by `drive race`. With the final settings: Mario Circuit 2:44.6 (the game's AI driving the same kart,
  `player cpu`: 2:30.1), Wuhu Loop 1:52.2, Maka Wuhu 2:03.0, Koopa Cape 3:05.4, DK Jungle 2:57.7, Kalimari Desert
  2:24.1, Piranha Plant Slide 2:40.4, Cheep Cheep Lagoon 2:16.1, Rainbow Road 2:17.8, all without Lakitu; Dino Dino
  Jungle 2:57.6 (Lakitu twice), Rosalina's Ice World 2:49.5 (4 times, all on the narrow icy bridge after the start),
  SNES Rainbow Road 1:59.5 (4 times, at its square corners without walls). With the settings before the last changes
  to cornering (easing off from 60 degrees, no stricter corridor at flag 0x04): Toad Circuit 1:44.2, Daisy Hills
  1:56.7, Shy Guy Bazaar 2:52.0, Music Park 2:33.2, Rock Rock Mountain 2:47.4, Wario Shipyard 2:46.9, Neo Bowser City
  2:46.1, Bowser's Castle 2:55.6, N64 Luigi Raceway 2:26.6, GBA Bowser Castle 1 1:50.4, Mushroom Gorge 2:14.1, DS
  Luigi's Mansion 2:26.8, N64 Koopa Beach 2:13.2, SNES Mario Circuit 2 1:48.5, Coconut Mall 2:52.5, Waluigi Pinball
  3:12.6 (Lakitu twice), DK Pass 3:05.3 (twice), Daisy Cruiser 2:07.5, Maple Treeway 3:04.5, Airship Fortress 2:38.6;
  Ice World did not get past its bridge then (17 falls). No back-up was needed on any course.
- **Measured later on 2026-10-06**, after the changes to steering and drifts (steering by the facing, A+B only with
  the aim behind, braking above half the top speed, drifts steered with the stick, held to the red mini-turbo and
  chained, no tricks before sharp corners), the first lap of a time trial (the race goes on; forks are chosen at
  random, so times vary by a second or two between runs): N64 Luigi Raceway 41.0 (49.2 before; the two big turns
  drifted almost all the way, no longer into the dirt on their inside), GBA Bowser Castle 1 33.1 (no braking to a stop
  in its square corners any more), Mario Circuit 53.1, Rosalina's Ice World 52.6 and DK Pass 56.5, Dino Dino Jungle
  55.7, all without Lakitu; Rainbow Road, one lap the whole course, 2:12.3 without Lakitu; SNES Rainbow Road 51.3 with
  one fall (the narrow straight after point 85, which the kart leaves 70 units wide of a route half-width of 37.5) and
  three hits by Thwomps. A person driving Rainbow Road took 2:03.2: they drifted with the stick fully in or fully out,
  and charged the mini-turbo faster (from 3/7 of the stick inward it charges 4.6 per frame, centred 2.0, out 1.0 to
  1.6). Driving the drift in and out like that was tried and left out: it turned too tightly on Luigi Raceway and too
  widely on Rainbow Road (a respawn loop).
- Also measured: a whole Mushroom Cup Grand Prix (`grandprix 0 --engine 2 --player simulated --wait-goal`) from the
  title to the trophy and back (6 min 23 s of wall time); a mirror race (Wuhu Loop, 4th of 8); a single-player VS race
  (`start --vs`, Music Park, 1st of 8); a balloon battle on N64 Big Donut: `goto` to a point (7 back-ups on the way: a
  straight line into the donut's walls), `route` across the course (720 frames from the start), `race` wandering the
  paths until the battle ended. On Mario Circuit, `route` to a point just behind the start went 4 route points
  backwards; with `--forward` it planned the whole lap (174 points). What changed the results while tuning: steering
  by the direction of travel instead of the facing (a drift ended with the kart facing 55 degrees inside its travel;
  later only while drifting, see [How it drives](#how-it-drives)), ending drifts by the facing as the game does, the
  corridor (instead of a fixed look-ahead that cut over grass), the start boost (2 s) and slowing for sharp corners
  (SNES Rainbow Road from 22 falls to 4).
