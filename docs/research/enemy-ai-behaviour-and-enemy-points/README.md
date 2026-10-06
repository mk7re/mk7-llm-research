# Enemy AI behaviour and enemy points (KMP ENPT / ENPH)

- Status: verified
- Asked: Let's research MapdataEnemyPoint and MapdataEnemyPath for both race modes and battle modes. I want to understand what the different settings of each enemy point and path entries do, so that we better understand how CPUs behave and create better custom tracks.
  - Follow-up (2026-10-05): Try to answer all the open questions in the enemy point topic. Rename the cpu should avoid object name to properly represent the research. Then check how the train crossing in Kalimari Desert works, document in the overview a bit how the enemies decide to go to the next point (how they cross the plane), find any other advice that may be worth telling to course creators, including setting up small routes near corners and edges of the tracks to reroute Bullet Bill and CPUs that got stuck. Also document how the back up state works, what triggers it.
  - Second follow-up (2026-10-05): test the bullet bill and stuck cpu re-routes in game, answer the open questions, add the new classes to the template (AIStuck and AIAutoSteer) along with the relevant members. Tests on courses with a modified KMP were left for a later session.
- Base commit: 050242ebef3fcea6c25cc36d13ddd53fd9db8053
- Images: `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95), `dlp` only as the source of names. `eur2` also run in Azahar
  (the installed game with its v1.2 update) for the measurements of the findings.

## Contents

- [Overview](#overview): what was researched and found, for readers new to the topic
  - [Words used in this document](#words-used-in-this-document)
  - [CPU levels and Mii titles](#cpu-levels-and-mii-titles)
  - [How CPUs follow the route](#how-cpus-follow-the-route)
  - [Enemy point settings](#enemy-point-settings)
  - [Enemy point flags](#enemy-point-flags)
  - [Enemy path settings](#enemy-path-settings)
  - [Objects linked to race paths](#objects-linked-to-race-paths)
  - [Train crossings](#train-crossings)
  - [Moving boards in battle](#moving-boards-in-battle)
  - [When a CPU gets stuck](#when-a-cpu-gets-stuck)
  - [Helper paths for lost CPUs and Bullet Bills](#helper-paths-for-lost-cpus-and-bullet-bills)
  - [What each Mii title changes](#what-each-mii-title-changes)
  - [Race and battle compared](#race-and-battle-compared)
  - [What each setting does, at a glance](#what-each-setting-does-at-a-glance)
- [Glossary](#glossary): the classes, members and enums involved, with their offsets; the
  [functions](#functions) and [data](#data) tables with addresses
- [Findings](#findings): each claim with its evidence
  - [Sources and method](#sources-and-method)
  - [1. How the entries become a route](#1-how-the-entries-become-a-route)
  - [2. Links between points, and the link end flags](#2-links-between-points-and-the-link-end-flags)
  - [3. Race only: re-sampling](#3-race-only-re-sampling)
  - [4. Race only: corner value and side axis](#4-race-only-corner-value-and-side-axis)
  - [5. Reaching a point](#5-reaching-a-point)
  - [6. Per-field detail](#6-per-field-detail)
  - [7. Start points and respawns](#7-start-points-and-respawns)
  - [8. Junction choice](#8-junction-choice)
  - [9. Fields without a reader](#9-fields-without-a-reader)
  - [10. Train crossings and battle boards](#10-train-crossings-and-battle-boards)
  - [11. Stuck CPUs, back-up and Lakitu](#11-stuck-cpus-back-up-and-lakitu)
  - [12. Re-routes to the nearest point](#12-re-routes-to-the-nearest-point)
  - [13. In-game tests and the original courses](#13-in-game-tests-and-the-original-courses)
  - [14. Values used by the original courses](#14-values-used-by-the-original-courses)
  - [15. Mii titles](#15-mii-titles)
  - [16. Differences from the input notes](#16-differences-from-the-input-notes)
- [Confidence](#confidence): what is certain, what is likely, what is a guess
- [Open questions](#open-questions): what was not resolved

## Overview

CPU players follow a route that the course file (the KMP) describes in two sections: **enemy points** (ENPT), positions on
the road with a few settings each, and **enemy paths** (ENPH), runs of consecutive enemy points that are linked to each
other. This research explains what every setting of these entries does, and how the CPUs use the route: how they move from
one point to the next, how they choose a branch at a fork, how they wait at the level crossings of N64 Kalimari Desert, and
what the game does when a CPU gets stuck. In short:

- Races and battles read the same two sections in very different ways. In a race the game draws a smooth curve through the
  enemy points and adds points along it, and the paths are one-way. In a battle the enemy points are used as they are, and
  the paths are two-way roads ([Race and battle compared](#race-and-battle-compared)).
- Most settings only act in races. Apart from the position and the width of each point, the only setting the original
  battle courses use is flag 0x80, which in battle makes CPUs drive on the centre of the points and hop at every trick
  chance ([Flag 0x80](#flag-0x80-base-speed-race-and-jump-point-battle)).
- The last field of an enemy path, which the notes this research started from did not cover, tells the game in battle
  which end of each linked path is the one where the two paths meet ([Link end flags](#link-end-flags)).
- A CPU that stops making progress is first sent to the nearest route point, then backs up, and is finally picked up by
  Lakitu ([When a CPU gets stuck](#when-a-cpu-gets-stuck)). Small extra paths near the route, which a CPU can only reach
  by being sent to the nearest route point, bring such CPUs and a player's Bullet Bill back to the route; 30 of the 32 Grand Prix courses have them
  ([Helper paths](#helper-paths-for-lost-cpus-and-bullet-bills)).

The behaviour was read in the game's code, and most of it was also checked in the running game. The advice for course
creators follows from both, but was not tested on a modified course ([Confidence](#confidence)).

### Words used in this document

- **Race mode** covers races (Grand Prix, VS and online races) and the award ceremony shown after a Grand Prix.
  **Battle mode** covers balloon and coin battles.
- An enemy path names its **previous paths** (the paths that lead into it) and its **next paths** (the paths it leads to).
  A **fork** is the end of a path with several next paths; each of them is a **branch**. A **merge** is the start of a
  path with several previous paths. Forks and merges are **junctions**; in a battle, where paths are two-way roads, a
  junction is any place where the ends of several paths meet.
- **Route points** are the points a CPU actually drives toward: in a battle the enemy points themselves, in a race the
  enemy points plus the points the game adds between them ([The route in a race](#the-route-in-a-race)). "Point" alone
  means a route point.
- The **target point** is the point a CPU is heading to. When the CPU is close enough to it, it has **reached** it, and
  the next point becomes its target. Some settings are read from the target point, others from the point just reached.
- **Lakitu** picks up a kart that falls off the course and puts it back at a **respawn point** (the JGPT section of the
  KMP).
- **Bullet Bill** is the item that turns a kart into a Bullet Bill that drives itself along the route.
- A **re-route** is how the game finds the route again for a CPU that has lost it ([Re-routes](#re-routes)).
- Distances are in course units, and a second is 60 frames.

### CPU levels and Mii titles

Several settings act differently with the CPU level, of which there are three. In a race it follows the engine class
(50cc, 100cc, 150cc); online races always use the 150cc level. In a single-player battle it is the CPU setting of the battle (easy,
normal, hard); multiplayer and online battles always use the highest level ([Finding 6](#ai-level)).

Some rules below apply only to Mii CPUs with a given title, such as Aviator or Rookie. Such CPUs exist only in
single-player Grand Prix. The sections below name the title wherever it changes a rule, and [What each Mii title
changes](#what-each-mii-title-changes) sums them up at the end. The title names are most likely right, but not certain
([Finding 15](#15-mii-titles)).

### How CPUs follow the route

#### The route in a race

In a race (Grand Prix, VS, online, award ceremony):

- The game does not drive on the enemy points directly. When the course loads, it draws a smooth curve through them and
  adds extra points along it, so that the CPUs get a point every 75 to 150 units. The enemy points are kept at their exact
  positions ([Finding 3](#3-race-only-re-sampling)).
- Each added point copies all the settings of the nearest enemy point. A setting on one enemy point therefore covers the
  road from halfway back to the previous enemy point to halfway on to the next one, not a single spot.
- Paths are one-way: from the first point to the last point, then on to one of the next paths
  ([Finding 2](#2-links-between-points-and-the-link-end-flags)).
- Each CPU drives on its own **lane**: the point it aims for is the route point moved sideways by an amount that depends
  on the CPU and on the width of the road at that point ([Scale](#scale-width)).

#### Moving on to the next point

In a race, a CPU moves on to the next point as soon as it is within 280 units of its target point, or has driven past it
([Finding 5](#5-reaching-a-point)):

- "Driven past" means that the CPU has crossed an invisible wall standing at the spot it aims for (the point, moved
  sideways to the CPU's lane). The wall is turned so that it splits the bend in two: it faces halfway between the
  direction the road arrives from and the direction it leaves in. On a straight it is square to the road; at a bend it is
  tilted like the line from the inside to the outside corner of the bend. The wall has no edges and no height limit, so a
  CPU that is far to the side, or above or below, also counts as past once it is beyond it. Right after the CPU has been
  put back on the route (after a fall or a respawn), the first wall faces the direction in which the road leaves the
  point instead.
- In practice the 280 units come first almost every time: measured in game, 2573 of 2584 moves happened within the
  distance and 11 at the wall. The wall catches the CPUs that pass a point more than 280 units away from it (pushed wide,
  or on a far lane of a wide road), so that they do not turn back for it.
- A CPU that has just got a Bullet Bill must come within 100 units of its target (or drive past it) before it moves on;
  after that the 280 applies again.
- Measured in game, the new target was usually 210 to 490 units ahead right after moving on (half of the time more than
  about 375); less after a point with [flag 0x04](#flag-0x04-precise), and up to about 900 units where points are far
  apart (the straight links between paths are not given extra points).
- Settings of "the point just reached" therefore start a few hundred units **before** that point, and settings of "the
  target point" start one point spacing earlier still. Each setting below says which of the two it is.

#### The route in a battle

In a battle (balloon and coin battle):

- The game uses the enemy points as they are, without extra points ([Finding 1](#1-how-the-entries-become-a-route)).
- Paths are two-way roads. CPUs drive a path in whichever direction they entered it, and only choose where to go at the
  ends of a path ([Finding 2](#2-links-between-points-and-the-link-end-flags), [Finding 8](#8-junction-choice)).
- A CPU moves on when it is within 100 units of its target point. There is no invisible wall
  ([Finding 5](#5-reaching-a-point)).
- Which way a CPU turns at a junction depends on what it is doing: looking for item boxes, chasing a rival, running away,
  collecting coins, or wandering at random ([Finding 8](#8-junction-choice)).

#### Re-routes

When the game decides that a CPU has lost its route, it looks for the route point nearest to the CPU, on any path: the
nearest one within 500 units horizontally that is not too far above or below the CPU (each enemy point sets its own
height limit, the [Max search Y offset](#max-search-y-offset), and the points added in a race copy it). In a race the
points the game adds are searched as well, so the point found can be one of them. If that point is on another path than
the one the CPU is heading along, the CPU continues from there: in a race from the first point after it that is more than
180 units away from the CPU, following the first next link of each point, in a battle from the nearest point itself.
Otherwise the CPU keeps its target, with two exceptions: a player's kart that the game drives (in a race, during the
player's Bullet Bill and once the player has finished) is moved in any case, and the height re-route of [flag
0x02](#flag-0x02-height-re-route) gives up the target in any case ([Finding 5](#height-re-route), [Finding
12](#12-re-routes-to-the-nearest-point)). The cases in which the game re-routes a CPU are listed under [Flag
0x02](#flag-0x02-height-re-route), [When a CPU gets stuck](#when-a-cpu-gets-stuck) and [Helper
paths](#helper-paths-for-lost-cpus-and-bullet-bills).

#### Placing race points

- Space the enemy points evenly. The number of extra points on a stretch is decided by the length of the stretch
  **before** it, so a long stretch that follows a short one gets too few extra points, and a short one after a long one
  gets too many ([Finding 3](#3-race-only-re-sampling)).
- Do not turn by more than 90 degrees at a single point. The game then misjudges which way the road bends, and CPUs drift
  and cut the corner to the wrong side ([Finding 4](#4-race-only-corner-value-and-side-axis)). The invisible wall a CPU
  has to cross also turns until it lies almost along the road, so whether the CPU counts the point as passed comes down to
  which side of the road it is on (this follows from the formula of [Finding 5](#the-pass-through-plane); not tested in
  game). Use more points on hairpins.
- Give every race path at least one next path, also at the end of a side route. At the last point of a path without one,
  the game reads a next link that does not exist and sends the CPU toward whatever point that gives. In two tests with the
  next paths of a path removed in memory (Wuhu Loop and Mario Circuit), it was point 0, the start of the route: the CPUs
  drove off the route toward it, got stuck against walls and were re-routed ([When a CPU gets stuck](#when-a-cpu-gets-stuck)),
  losing several seconds ([Finding 13](#dead-end-path)). No original race course has such a dead end.
- The connection from one path to the next is a straight line, and so are the stretch into a fork and the stretch out of a
  merge. Put the enemy points close together there if the road curves ([Finding 3](#3-race-only-re-sampling)).
- Keep the enemy points on the road surface. The game measures the slope of the road under each point, and uses it to work
  out which way is "sideways" for the CPU lanes ([Finding 4](#4-race-only-corner-value-and-side-axis)).
- Avoid paths of a single point: they get no link from their previous paths ([Finding 2](#2-links-between-points-and-the-link-end-flags)).

### Enemy point settings

KMP editors may show these settings under other names. Each enemy point is 0x18 bytes; offsets are from the start of the
entry:

| Offset | Size | Name used here |
| --- | --- | --- |
| 0x00 | 3 floats | Position |
| 0x0C | float | Scale (width) |
| 0x10 | 16-bit | Mushroom setting |
| 0x12 | 8-bit | Drift setting |
| 0x13 | 8-bit | Flags ([Enemy point flags](#enemy-point-flags)) |
| 0x14 | signed 16-bit | Path find options |
| 0x16 | signed 16-bit | Max search Y offset |

The use of each value in the original courses is in [Finding 14](#14-values-used-by-the-original-courses).

#### Position

The route itself. See [How CPUs follow the route](#how-cpus-follow-the-route) for how it is used.

In a race, all CPUs start heading to the route point found near the start line (see [Path find
options](#path-find-options)). The Wuhu Loop and Maka Wuhu course slots are an exception: there the CPUs always start
heading to enemy point 0. A custom course placed in one of those slots should therefore have its first enemy point just
after the start line.

In a battle, also make sure there is an enemy point within 500 units (horizontally) of every battle start position: each
CPU starts heading to the enemy point nearest to its start position ([Finding 7](#7-start-points-and-respawns)).

#### Scale (width)

The half-width of the road for the CPUs, in steps of 50 units: the **half-width** is scale × 50, and CPUs may spread up
to 85 % of it to each side of the point, so scale 1 means about 42 units to each side ([Finding 6](#scale)).

In a race:

- Every CPU gets its own lane at the start, chosen from its starting grid position. The lanes range from about 60 % of
  the half-width on one side to about 55 % on the other; on courses where byte 1 of the STGI entry (the stage info
  section of the KMP) is 0 (most original race courses) the pattern is mirrored and shifted, from about 73 % on one side
  to about 42 % on the other. Lanes beyond 50 % slowly settle back to at most 50 %. A drifting CPU at a cornering point
  shifts further toward the inside of the corner (see [flag 0x01](#flag-0x01-cornering)), up to 85 % of the half-width.
  A CPU also changes lane to block or avoid other karts, and goes back to the centre after a Bullet Bill or after a
  re-route. So the scale decides how much of the road the CPUs use.
- Set it to roughly the usable road width, divided by 2, divided by 50, and a little less where the edges are dangerous
  (walls, drops, off-road). The original race courses mostly use 0.5 to 2 (1.0 is by far the most common); a few points
  go down to 0.1 or up to 7.125, and 13 points have a small negative value (-0.25 or -0.375), which swaps the sides of the
  lanes.
- Rookie and Star Racer Mii CPUs, CPUs in Bullet Bill, and the award ceremony ignore the scale and drive exactly on the
  points.

In a battle, CPUs drive on the centre of the points. The scale limits how far the obstacle avoidance can push them
sideways. It also decides what the CPUs "see" when they choose where to go at a junction: an item box, a coin or a kart
counts only when it lies within scale × 50 units of a point, or within the width of the road between two linked points
(the width changes evenly from one point's value to the other's). Anything outside every such zone is ignored by the
junction choice, so give battle points a scale that covers the whole arena floor, item boxes and coins included
([Finding 6](#scale), [Finding 8](#8-junction-choice)).

#### Mushroom setting

Whether a CPU may use a Mushroom here, and where the mushroom shortcuts start. It applies from the point just reached
([Finding 6](#mushroom_setting)).

| Value | Race | Battle |
| --- | --- | --- |
| 0 | CPUs may use a Mushroom | CPUs may use a Mushroom |
| 1 | first point of a mushroom shortcut (see below); no Mushroom use | no Mushroom use |
| 2 (or anything else) | no Mushroom use | no Mushroom use |

- A CPU that gets a Mushroom waits a random time (up to 3 seconds in race, under 1 second in battle) and then uses it at
  the next chance where the setting is 0. A CPU holding a single Mushroom also uses it immediately whenever it reaches a
  point with 0. It never uses one while drifting. In race, the waiting time does not run out while the point after the
  CPU's target is a junction point (a point with several previous or next points), so timed uses are held back around
  forks and merges.
- Aviator and Dolphin Mii CPUs (race) ignore this setting: once the waiting time is over, an Aviator uses its Mushroom
  while gliding and a Dolphin while in water.
- Use 2 where a speed boost would throw a CPU off the road: before sharp turns, on narrow bridges, near drops, before
  jumps that must be taken slowly. The original race courses use 2 on more than half of their points.

#### Mushroom shortcuts

Race only. At a fork, a branch whose **first point** has Mushroom setting 1 is a shortcut. Only that point matters; set
the rest of the shortcut to 2 if CPUs should not waste Mushrooms there. Which CPUs take it ([Finding 6](#mushroom_setting),
[Finding 8](#8-junction-choice)):

| CPU | Takes the shortcut |
| --- | --- |
| 150cc and online, holding a Mushroom or Triple Mushroom | always |
| 100cc, holding a Mushroom or Triple Mushroom | half of the time (decided when the item is received) |
| 50cc | never |
| holding a Golden Mushroom, Aviator and Dolphin Miis, or no Mushroom | never |

A CPU with a single Mushroom that has chosen the shortcut normally fires it on the frame it chooses the branch, a few
hundred units before the fork, provided the point it has just reached has value 0. Always give a fork at least one normal
branch: when every branch starts with value 1, CPUs going for a shortcut pick one of them at random and every other CPU
takes the first branch listed.

#### Drift setting

Where CPUs may drift. Race only; battle CPUs never drift and ignore this setting ([Finding 6](#drift_setting)).

| Value | Meaning |
| --- | --- |
| 0 | Drifting allowed. A CPU may start a drift toward this point, and an ongoing drift continues. |
| 1 | End of drift. No drift may start toward this point, and a CPU that reaches it while drifting ends the drift. The mini-turbo is kept if the CPU passes a random check (Drift Wizard Miis always). |
| 2 | No drifting. Like 1, but the mini-turbo is thrown away, and so is any mini-turbo from a drift that ends before the next point. |
| 3 and above | Let the corner decide: a drift may start here, and it ends when the road starts bending the other way or straightens out. Used on 8 points of Wuhu Loop. |

- A CPU only starts a drift when its target point is in a bend (about 3.6 degrees of turn or more after smoothing), the
  target point allows it (0 or 3+), the CPU is within 400 units of it, and a random check passes (the **drift start
  check**; Drift Wizard Miis skip it). Rookie and Star Racer Miis never drift.
- Typical use: 0 through a corner, 1 on the corner exit so the CPU fires its mini-turbo there, 2 on straights, narrow parts
  and ramps. A run of points with 1 or 2 is a no-drift zone.
- The original race courses mostly use 2 (about two thirds of the points), 0 in corners, and 1 at a few corner exits.

#### Path find options

Marks enemy points and paths for special cases, in races only. Besides the effect of its own row, every value other than 0
also has the effect of the last row. Keep 0 on battle courses ([Finding 6](#path_find_options)).

| Value | Effect (race) | Original use |
| --- | --- | --- |
| 0 | normal | almost every point |
| -1 | CPUs that have finished the race (and players whose kart is driven by the game after the finish) are never re-routed to these points | 33 points (DS Airship Fortress, GCN Daisy Cruiser, Maka Wuhu, ...) |
| -2 | a Bullet Bill is never re-routed to these points, and a player's Bullet Bill never starts on them. When a Bullet Bill starts and no other point is within 500 units horizontally (and passes the Max search Y offset), it ends immediately | 72 points (Rainbow Road, Rock Rock Mountain, ...) |
| -3 | the path is preferred by Boost Jumper and Aviator Mii CPUs | 13 points (Bowser's Castle, DK Jungle, Wuhu Loop, ...) |
| -4 | the path is preferred by Dolphin Mii CPUs | 5 points (Cheep Cheep Lagoon, Wario Shipyard, GCN Daisy Cruiser) |
| 1, 2, 3 | award ceremony course only: the path on which kart 1, 2 or 3 drives | the Grand Prix winning cutscene course |
| any value other than 0 | the point is not used to find where the CPUs start the race | |

- One point with -3 or -4 is enough to mark the whole path. When several branches of a fork qualify, the first one listed
  is taken ([Finding 8](#8-junction-choice)).
- Keep 0 on the enemy points around the start line.

#### Max search Y offset

A height limit used whenever the game looks for the route point nearest to a kart: when it re-routes a CPU (after a fall,
with [flag 0x02](#flag-0x02-height-re-route), or after 7.5 seconds without progress; see [When a CPU gets
stuck](#when-a-cpu-gets-stuck)), when a Bullet Bill starts, when the game works out where CPUs continue after a Lakitu
rescue, and for the battle start positions. The game picks the nearest point within 500 units horizontally whose height
difference passes this limit ([Finding 6](#max_search_y_offset), [Finding 7](#7-start-points-and-respawns)). In a race
the search also covers the points the game adds, and each of them has the limit of the enemy point it copies its settings
from ([The route in a race](#the-route-in-a-race)).

| Value | Height limit |
| --- | --- |
| 0 | none |
| negative | 75 units |
| positive | the value, in units |

- Use it on multi-level courses, so that a CPU on a lower road is not put back on a bridge above it, and the other way
  round. The original courses use -1 on 475 points, and 20, 30 or 40 on a few.
- Every respawn point needs a route point within 500 units horizontally that passes the limit. The game looks for it
  once when the course loads; if there is none, a CPU rescued there is sent back to point 0 of the route (enemy point 0
  in the original courses). In a race a point the game adds is enough, but where it adds points cannot be seen in the
  KMP, and the straight stretches between paths, into a fork and out of a merge get none ([Placing race
  points](#placing-race-points)); an enemy point within the 500 units is the safe choice. Every respawn point of the original courses has an enemy point
  within reach, except one point of the winning cutscene course, where no kart falls (checked against the enemy points
  only, which can only miss a point, not invent one; [Finding 7](#7-start-points-and-respawns)).
- On award ceremony courses, the value 1 has a special meaning that is not understood yet.

### Enemy point flags

The Flags byte of an enemy point holds eight flags, and any number of them can be set at once. The original race courses
often combine 0x04 with 0x10, 0x20 or 0x80.

Flags 0x01, 0x08, 0x10 and the cornering part of 0x04 are read from the **target point**. Flags 0x02, 0x20, 0x40, 0x80 and
the distance part of 0x04 are read from the point the CPU **has just reached** ([Finding 5](#5-reaching-a-point)). In a
race both kinds start working a few hundred units before the point ([Moving on to the next
point](#moving-on-to-the-next-point)). To cover a stretch of road, flag every point of it and one or two points past its
end.

| Flag | Race | Battle | Race-course points using it |
| --- | --- | --- | --- |
| 0x01 | drifting CPUs take a line through the corner that depends on the CPU level | nothing | 467 |
| 0x02 | a CPU that lost its route vertically can switch to a route at its height | same | 569 |
| 0x04 | CPUs follow the route closely (move on at 140 units instead of 280), and flag 0x01 | CPUs move on earlier (140 instead of 100) | 1152 |
| 0x08 | no trick hops | nothing | 42 |
| 0x10 | long, gentle drifts that are not cut short | nothing | 329 |
| 0x20 | a Bullet Bill flies at the route's height | nothing | 773 |
| 0x40 | a Bullet Bill cannot end here | nothing | 247 |
| 0x80 | no rubber-banding (a fixed share of the top speed) | no rubber-banding, drive on the point centre, hop at every trick chance | 349 |

#### Flag 0x01: cornering

Race only. A CPU that is **drifting** when it starts heading to the point changes its line: at 150cc and online it aims
70 % of the half-width (see [Scale](#scale-width)) toward the inside of the turn, at 100cc 40 % toward the inside, at
50cc 15 % toward the outside. A CPU that is not drifting ignores the flag, and so do Rookie and Star Racer Miis. Tight
bends already behave this way without the flag ([Finding 6](#flags-0x01-and-0x04), [Finding 5](#5-reaching-a-point)).
Use it on wider corners where fast CPUs should hug the apex. The corner must also allow drifting (drift setting 0). Do not
use it where the inside of the corner is off-road, a wall or a drop, since the scale then decides how far CPUs cut into
it.

#### Flag 0x02: height re-route

Race and battle. If a CPU has not reached a new point for a third of a second and its target is steeply above or below it
(more than about 29 degrees), the game re-routes it: it looks for the nearest route point within 500 units horizontally,
and if that point is on another path, the CPU continues from there; in any case it gives up its current target
([Finding 5](#height-re-route)). Use it on multi-level sections, bridges, drops and jumps, where a CPU can land on a route
above or below the one it was following. Set the Max search Y offset of the points on the other routes, so that the CPU
does not pick a route at the wrong height. Without the flag the game only does this for CPUs that are in Bullet Bill,
gliding, or have been in the air for about a third of a second (for example after a jump or while falling), so the flag
makes the check work for CPUs that are driving on the ground.

#### Flag 0x04: precise

Race: the CPU must get within 140 units of the next point instead of 280 before moving on, so it looks less far ahead and
follows the shape of the route instead of cutting across it. The flag on a point controls how closely the **following**
point is approached, so flag the points before the tight part. It also acts as flag 0x01. Use it on hairpins, chicanes,
narrow bridges and anywhere cutting the line sends CPUs off the track. A CPU that is pushed wide still moves on once it
has driven past the point, so the flag does not make CPUs turn back. Battle: the normal distance is 100, so the flag makes
CPUs **less** precise. No original battle course uses it ([Finding 5](#5-reaching-a-point), [Finding 6](#flags-0x01-and-0x04)).

#### Flag 0x08: no tricks

Race: CPUs heading to the point do not hop at trick chances (ramps, jumps, glider pads). The hop that starts a drift is
not blocked, so if the ramp is on a curve also set drift setting 2 on its approach. Use it on ramps where a trick would
throw CPUs off course. Battle: no effect, because battle CPUs only trick through flag 0x80 ([Finding 6](#flag-0x08)).

#### Flag 0x10: hold drift

Race: a drift toward the point is only given up when the kart is badly out of line, the drift is steered more gently, and
the CPU does not end it just because the mini-turbo is charged or the drift has lasted 2 seconds. Use it on long sweeping
curves that should be taken in one drift. It needs drift setting 0. Battle: no effect ([Finding 6](#flag-0x10)).

#### Flag 0x20: Bullet Bill follows the route height

Race: while a kart is in Bullet Bill on the flagged stretch, its height is pulled toward the height of the route instead
of following the ground. The pull builds up over about 4.7 seconds and stops at once on the first point without the flag.
Use it over gaps, pits and jumps, and place the enemy points at the height the Bullet Bill should fly. Flag the whole
stretch without holes. Battle: no effect ([Finding 6](#flags-0x20-and-0x40)).

#### Flag 0x40: Bullet Bill cannot end

Race: once a Bullet Bill has started to end, the ending is paused while the kart is on the flagged stretch. It still ends
after 16 seconds of Bullet Bill in total, and when the kart has spent 7 seconds in a row on the flagged stretch without
reaching a new point (for example when it is stuck between two points). Use it over pits,
water and anything a kart must not be dropped into. Flag the whole stretch and one or two points past it. Battle: no
effect ([Finding 6](#flags-0x20-and-0x40)).

#### Flag 0x80: base speed (race) and jump point (battle)

Race: the CPU ignores rubber-banding (the speed the game normally asks of each CPU) and drives at a fixed share of its top
speed: 80 % at 50cc, 90 % at 100cc, 100 % at 150cc and online. A CPU far ahead speeds up to it and one far behind slows
down to it. Use it where a specific speed matters, such as jumps that must be cleared. The speed still differs between
engine classes. CPUs also drive at this speed, with or without the flag, while a boost lasts and once they have been in
the air for a third of a second without gliding ([Finding 6](#flag-0x80)).

Battle: the same speed rule (the 80 / 90 / 100 % step follows the CPU level of the battle, and is always 100 % in
multiplayer and online), and in addition the CPU drives exactly on the centre of the points and hops at every trick
chance. Use it on the points leading onto a ramp or jump, and on narrow passages where CPUs must stay centred. Apart
from the position and the scale, it is the only setting the original battle courses use (GBA Battle Course 1 and Wuhu
Town; [Finding 14](#14-values-used-by-the-original-courses)).

### Enemy path settings

Each enemy path is 0x48 bytes; offsets are from the start of the entry:

| Offset | Size | Name used here |
| --- | --- | --- |
| 0x00 | 16-bit | First point |
| 0x02 | 16-bit | Point count |
| 0x04 | 16 x 16-bit | Previous paths (0xFFFF = empty slot) |
| 0x24 | 16 x 16-bit | Next paths (0xFFFF = empty slot) |
| 0x44 | 32-bit | Link end flags |

#### First point and point count

A path is a run of consecutive enemy points: the first point and how many follow. Give every enemy point to exactly one
path; the game assumes paths do not overlap ([Finding 2](#2-links-between-points-and-the-link-end-flags)).

#### Previous and next paths in a race

Up to 16 each. Fill them from the first slot on, without empty slots in between, because the game stops reading at the
number of valid entries ([Finding 2](#2-links-between-points-and-the-link-end-flags)).

The CPU drives each path from its first to its last point, then continues on one of the next paths. The previous paths
tell the game which paths lead into this one; list them to match the next paths of those paths. At a fork, a CPU
([Finding 8](#8-junction-choice)):

1. never picks a branch that leads straight back to where it came from;
2. skips a branch whose linked object tells CPUs to stay away (see [Objects linked to race
   paths](#objects-linked-to-race-paths));
3. takes a Mii title path (path find options -3 / -4) if it has the matching title;
4. takes a mushroom shortcut if it decided to (see [Mushroom shortcuts](#mushroom-shortcuts));
5. otherwise picks one of the normal branches at random, with equal chances.

To make CPUs prefer one branch, you cannot weight the choice directly; split the unwanted branch into a mushroom shortcut
or link an object to it.

#### Previous and next paths in a battle

The same 16 slots each, filled from the first slot on. Paths are roads that can be driven both ways, and the two lists
have a different meaning: "previous paths" are all the paths that meet this one at its **first** point, and "next paths"
are all the paths that meet it at its **last** point. The [link end flags](#link-end-flags) say which end of each of those
paths is at the junction ([Finding 2](#2-links-between-points-and-the-link-end-flags)).

#### Link end flags

On race courses, leave it at 0: a non-zero value can only make CPUs skip a path. No original race course uses it
([Finding 2](#2-links-between-points-and-the-link-end-flags)).

On battle courses it tells the game which end of each linked path touches this path. Each path has two ends, its first
point and its last point. A junction is a place where several path ends meet. For every path, and for each of its two
ends:

1. List every other path that has an end at that junction.
2. If the junction is at this path's **first** point, put them in the previous paths. If it is at this path's **last**
   point, put them in the next paths.
3. For each entry, decide whether the other path touches the junction with its "unusual" end:

   | Junction at this path's | List | The other path touches it with its | Add |
   | --- | --- | --- | --- |
   | first point | previous paths, slot n | last point | nothing |
   | first point | previous paths, slot n | first point | the value of slot n from the "Previous" column below |
   | last point | next paths, slot n | first point | nothing |
   | last point | next paths, slot n | last point | the value of slot n from the "Next" column below |

   Rule of thumb: add the value when the two paths point **into each other** or **away from each other** at the
   junction, and add nothing when one runs into the other head to tail.
4. The link end flags value is the sum of everything you added, for both ends of the path.

| Slot | Previous | Next |
| --- | --- | --- |
| 0 | 1 (0x1) | 65536 (0x10000) |
| 1 | 2 (0x2) | 131072 (0x20000) |
| 2 | 4 (0x4) | 262144 (0x40000) |
| 3 | 8 (0x8) | 524288 (0x80000) |
| 4 | 16 (0x10) | 1048576 (0x100000) |
| 5 | 32 (0x20) | 2097152 (0x200000) |
| 6 | 64 (0x40) | 4194304 (0x400000) |
| 7 | 128 (0x80) | 8388608 (0x800000) |
| n | 2 to the power n | 65536 times 2 to the power n |

Example: a crossroads where four paths meet. Paths A and B **end** there (their last points are at the crossroads), paths
C and D **start** there.

| Path | Its end at the crossroads | List | Entries (slot 0, 1, 2) | Added | Value |
| --- | --- | --- | --- | --- | --- |
| A | last point | next paths | B, C, D | B touches with its last point: slot 0 of Next = 65536 | 65536 (0x10000) |
| B | last point | next paths | A, C, D | A touches with its last point: 65536 | 65536 (0x10000) |
| C | first point | previous paths | A, B, D | D touches with its first point: slot 2 of Previous = 4 | 4 (0x4) |
| D | first point | previous paths | A, B, C | C touches with its first point: 4 | 4 (0x4) |

The values of the path's other end are added on top. GBA Battle Course 1 is built this way, with up to nine path ends
meeting at one junction.

#### More rules for battle paths

- A link only exists from the path that lists it. If path P lists Q but Q does not list P, CPUs can go from P to Q at that
  junction but not back. Normally, list every junction on all its paths ([Finding 2](#2-links-between-points-and-the-link-end-flags)).
- A path can list itself: a loop whose last point joins its own first point lists itself in both lists, with nothing added
  (Sherbet Rink does this). CPUs normally never pick a branch on the path they are already on, so the self-link itself is
  not taken; the loop only works as a junction when other paths also meet there (as they do on Sherbet Rink)
  ([Finding 8](#8-junction-choice)).
- A path of a single point takes no links from its previous paths. List all its neighbours in the next paths, with the
  Next values.
- CPUs only decide where to go at the ends of a path. Put a path end wherever a CPU should be able to turn; a long path
  with no junction in the middle is a corridor the CPU cannot leave.

### Objects linked to race paths

A course object (an entry of the GOBJ section) can be tied to an enemy path with two of its settings: the enemy route
field (offset 0x3C of the GOBJ entry) and setting 8 (offset 0x38). Setting 8 = 0 links the object to the path given in
the enemy route; setting 8 = 1 links it to every path that lists that path among its next paths. At a fork, CPUs look at
the objects linked to each branch ([Finding 8](#8-junction-choice)):

- An object can close its branch: the branch is skipped while the object says it is closed. On Music Park, measured in
  game, the objects linked to the two branches of a fork (`MpBoard`, ID 0x1AA, and `packunLight`, ID 0x1A8) open and close
  over time, mostly one branch open and the other closed, and the CPUs took the open branch at 29 of 36 forks.
- A branch linked to an object with ID 0x180, 0x1A9 or 0x1AA (`TcBoard`, `GbaBoard`, `MpBoard`; the original courses place
  them on Toad Circuit, GBA Bowser Castle 1 and Music Park) is taken at once by Boost Jumper and Aviator Mii CPUs, when it
  is open.

Ordinary CPUs check the linked objects at 75 % of forks (50 % in the Music Park course slot); Mii CPUs with a title always
do. Object ID 0x13E (the Kalimari Desert level crossing) is never linked to a path; its enemy route field has another use
(see [Train crossings](#train-crossings)).

Every object starts "closed", except an escalator, which starts open or closed depending on its setting 2 (offset 0x2C),
and `MeltIce` (ID 0x1C, not linked on any original course), which starts open. Only the object types below and `MeltIce`
ever open, so linking any other object to a branch closes that branch for every CPU that checks the objects (75 % of
them). The objects of the original courses with an enemy route, and when they open the branch, as the code of each object
sets it (only the Music Park objects were watched in game):

| Object (ID) | Course | Branch open while |
| --- | --- | --- |
| `TcBoard` (0x180), `GbaBoard` (0x1A9), `MpBoard` (0x1AA) | Toad Circuit, GBA Bowser Castle 1, Music Park | the board is fully moved into place and holds there (the three share the same code) |
| `BcFirePillar` (0x14) | Bowser's Castle | the pillar is not erupting: closed when it leaves its waiting state, open again when the eruption has finished |
| `WiiEscalator` (0x15B) | Wii Coconut Mall | the escalator runs up; closed while it runs down. Its starting value: open when its setting 2 is 0 |
| `ShellFish` (0xD5) | Cheep Cheep Lagoon | depends on where the giant clam is in its open and shut cycle |
| `packunLight` (0x1A8) | Music Park | set by the light and by its Piranha Plant (`packunMusic`) |
| `WiiCarA` (0x6E), `GcTable` (0x71) | Wii Coconut Mall, GCN Daisy Cruiser | follows a state bit of the object's own movement route |

The enemy route field must be 0 or more for any of this; -1 (the usual value) leaves the object out.

### Train crossings

On N64 Kalimari Desert, CPUs stop in front of the level crossings when a train comes. This is done by the crossing objects
(`N64Crossing`, ID 0x13E), not by the enemy route ([Finding 10](#10-train-crossings-and-battle-boards)).

#### How the crossings work

- The crossings come in pairs, one on each side of the tracks; two crossings with the same setting 1 (offset 0x2A of the
  GOBJ entry) form a pair and always show the same state. The game finds the two trains (`N64Train`, ID 0x68, the first
  two placed) by itself.
- When a train comes within 1000 units (measured horizontally) of a crossing, its lights start flashing, and stop when the
  train is more than 1000 units away again. Measured in game, they flashed for about 11 seconds each time a train passed.
- For the first 4 seconds of flashing the CPUs ignore the crossing. During the next 5 seconds a CPU that comes within 500
  units of the crossing while driving toward it (the crossing within about 84 degrees of straight ahead), and is not
  gliding or in Bullet Bill, starts waiting. After that, the CPUs ignore it again even if the lights still flash;
  measured, that is about the last 2 seconds before the train is gone.
- When a CPU starts waiting it draws: 3 times in 4 it lets go of the accelerator and coasts to a stop; otherwise it drives
  on. It stops waiting when the 5 seconds are over or when it has passed the crossing. Measured in a 150cc race: of 13
  waits, 11 braked, and 10 of those came to a stop 96 to 261 units before the crossing (the eleventh began just before the
  end of the 5 seconds); every one of them drove on as soon as the 5 seconds were over. In the 2 others the CPU kept
  driving; one of them started a new wait a moment later and then stopped.
- A CPU that is already close to the crossing when the 5 seconds begin stops where it is, as long as the crossing is still
  ahead of it (one stopped 136 units before it).
- The CPUs look only at crossings whose enemy route field (offset 0x3C) is 0 or more; its value does not matter. Kalimari
  Desert sets it on one crossing of each pair, which is enough because both show the same state.

#### CPUs that do not wait

- A CPU more than 1500 units behind the player's kart (behind in the race and farther than that) never starts a wait and
  leaves one it is in. Measured in game ([Finding 13](#m_is_far_behind)); CPUs far ahead of the player's kart wait as
  usual.
- A CPU hit by a Blooper's ink (or under a Star) does not start a wait; ink during a wait makes it zig-zag instead.
- A CPU whose kart is in an unknown state of the game (a kart status bit the templates call `accident_1`) when the wait
  starts always lets go of the accelerator, and also waits for a crossing that is beside or behind it.

#### Crossings on a custom course

Place the crossings in pairs with the same setting 1, give one of each pair an enemy route of 0 or more, and make sure the
trains reach the crossing about 4 to 9 seconds after they come within 1000 units, since that is when the CPUs are
stopped. Waiting CPUs are not treated as stuck (see below).

### Moving boards in battle

In a battle, CPUs steer away from the moving boards of N64 Big Donut (`BdBoard`, ID 0x192, four on that course; no other
original course has them). They use the same code as the boards of [Objects linked to race
paths](#objects-linked-to-race-paths), which count as "open" while the board holds still in place. A CPU runs away from a
board that does not, when the board is within 300 units and lies roughly in the direction the CPU is driving (within
about 53 degrees). It then drives toward a spot about 400 units from the board, off to one side at a random angle, for 2
seconds at most or until it gets within 40 units of that spot. Measured in game on Big Donut: 32 run-aways in about a
minute of battle, 25 of them ending after the 2 seconds. A CPU that is running away is not treated as stuck
([Finding 10](#10-train-crossings-and-battle-boards)).

### When a CPU gets stuck

Every CPU checks all the time whether it is making progress ([Finding 11](#11-stuck-cpus-back-up-and-lakitu)). It does not
check while it is in Bullet Bill, being rescued by Lakitu, waiting at a crossing, running away from a board ([Moving
boards in battle](#moving-boards-in-battle)), or in the unknown kart state of [Train crossings](#cpus-that-do-not-wait)
(`accident_1`); those reset the checks.

#### Re-route after 7.5 seconds

When a CPU has not reached a new point for 7.5 seconds, the game re-routes it once (see [Re-routes](#re-routes)). Unlike
the height re-route of [flag 0x02](#flag-0x02-height-re-route), it does not matter whether the target is above or below
the CPU. If the nearest route point is on another path than the one the CPU is heading along, the CPU continues from
there, and the checks below start over. Otherwise nothing happens. This is how a CPU that was knocked off the route by a
hit or an item and is stuck in the scenery can reach another path ([Finding 12](#12-re-routes-to-the-nearest-point)).
Measured in game: a CPU held still beside another path switched to it on the frame after the 7.5 seconds ([Finding
13](#stuck-cpu)).

#### Re-route against a wall

A CPU (or a player's kart driven by the game) that touches a wall for more than half a second in a row is re-routed the
same way, and again every half second while it stays against it. In Bullet Bill, touching a wall re-routes it at once.
Measured in game ([Finding 12](#12-re-routes-to-the-nearest-point)).

#### Backing up

When a CPU has been driving at less than 10 % of its top speed for 10 seconds in a row (about 3.3 seconds while it touches
a wall), it backs up ([Finding 11](#11-stuck-cpus-back-up-and-lakitu)):

1. It reverses in a straight line, wheels straight, for 1.7 seconds in a race (0.8 seconds in battle), at reduced speed
   (measured in game: 100 frames with the brake held and the stick centred).
2. It then turns around and drives toward a spot on the route behind it: three points before the one it last reached in a
   race (one point before in battle). With the race spacing of 75 to 150 units, that is roughly 225 to 450 units behind
   that point.
3. Once within 100 units of that spot it turns back toward the route, and as soon as the spot lies straight ahead or
   straight behind it (within about 37 degrees), it carries on normally. It also stops backing up as soon as it reaches a
   new point.

During steps 2 and 3 the game also re-routes the CPU every 2 seconds, as in the 7.5-second re-route above.

#### Lakitu

A CPU that has not reached a new point for 15 seconds (time spent backing up does not count, and a re-route that moves the
CPU starts the count again), or whose back-up lasts 10 seconds without reaching a new point (the count starts again when
it gets within 100 units of the spot of step 2), is picked up by Lakitu and put back on the course like a player who fell
off. In multiplayer this only happens while neither the kart nor the race has finished. Measured in game: a CPU held in
place was picked up after 15 seconds, and a CPU whose back-up drove it into a wall was picked up 10 seconds after the
back-up began ([Finding 11](#11-stuck-cpus-back-up-and-lakitu)).

#### Re-routed again and again

A CPU that a re-route moves (after a fall or any of the re-routes above) six times in a row at the same spot (within 10
units) is also handed to Lakitu ([Finding 11](#11-stuck-cpus-back-up-and-lakitu)).

#### A rare trap

If a CPU is re-routed by a fall during the first 1.7 seconds of a back-up (for example because it reversed off a ledge),
it keeps reversing: the "backing up" state is only cleared at the end of that phase. It keeps going backwards (reversing
counts as "slow") until a later back-up gets through its first 1.7 seconds. Seen in game after starting a back-up on
purpose on DS DK Pass: the CPU fell, then reversed for about 34 seconds, through one more interrupted back-up, before it
drove normally again. This looks like an oversight in the game; it was only seen with a back-up started on purpose
([Finding 11](#11-stuck-cpus-back-up-and-lakitu)).

#### What this means for a course

For a CPU that is stuck with no way out, and whose nearest route point is on the path it is following, the re-routes
change nothing. A CPU that pushes against a wall drives at less than 10 % of its top speed (measured: 3 to 5 %), so it
backs up after about 3.3 seconds; one that is slow without touching a wall backs up after 10 seconds. If the back-up does
not bring it to a new point, Lakitu takes it:

- 10 seconds after the back-up began, if the back-up itself gets stuck. Measured in game: a CPU pushing against a wall
  backed up, drove into another wall on its way back to the route, and was handed to Lakitu 10 seconds after the back-up
  began ([Finding 11](#stuck-cpus-measured-in-game)).
- otherwise at most about 11.7 seconds after the back-up ends (against a wall) or about 5 seconds (without a wall), later
  if it backs up again in the meantime, since time spent backing up does not count.

A helper path can shorten all of this (see the next section). Avoid corners where a CPU can drive into a dead end at a
shallow angle, avoid ledges right behind places where CPUs often get stuck (the back-up goes straight backwards), and keep
the route clear of obstacles for about 400 units behind such places, since a CPU that backs up drives back along the
route.

### Helper paths for lost CPUs and Bullet Bills

Small extra paths near the edges of the road, in corners or below jumps can bring lost CPUs and Bullet Bills back to the
route. They work through the re-route ([Re-routes](#re-routes)): the nearest route point can belong to any path, including
a helper path. A CPU switches to it only when it is on another path than the one the CPU is heading along; a player's
kart in Bullet Bill always switches ([Finding 5](#height-re-route), [Finding 12](#12-re-routes-to-the-nearest-point)).

#### When a helper path is used

| Case | Helper path used | How |
| --- | --- | --- |
| A CPU stuck at the same height | yes | A CPU that was knocked off the route by a hit or an item and is stuck in the scenery is re-routed after half a second against a wall, after 7.5 seconds without reaching a new point, and every 2 seconds while it backs up ([When a CPU gets stuck](#when-a-cpu-gets-stuck)). If the nearest point is on a helper path, the CPU drives off along it instead of waiting for the back-up or for Lakitu. Seen in game on Mario Circuit, where a CPU stuck against a wall was moved onto one of the course's own helper paths ([Finding 13](#dead-end-path)). |
| A CPU (or Bullet Bill) that ends up at another height | yes | When a CPU falls, jumps or flies off its route, and its target is steeply above or below it for a third of a second, the game re-routes it. This needs the CPU to be in the air, gliding, in Bullet Bill, or to have just reached a point with flag 0x02 ([Flag 0x02](#flag-0x02-height-re-route)). A short path laid along a lower road, a pit or an area below a jump, linked into the main route through its next paths, therefore gives such CPUs a way back. Set flag 0x02 on the main route above it, and use the Max search Y offset so that the helper path is only found from its own height. |
| A player's Bullet Bill | yes | When a player (not a CPU) uses a Bullet Bill, the game takes over the kart and starts it at the nearest point other than -2, so a helper path is used when it holds the point nearest to the player. If there is none, the Bullet Bill ends at once. Measured in game: the player's route jumped to the path next to the kart on the frame the Bullet Bill started, exactly to the point the rule above gives ([Finding 13](#a-players-bullet-bill)). |
| A player's kart when its race ends | yes | When the race is over for a player, the game takes over the kart the same way (points with path find option -1 are skipped then). Seen in game ([Finding 13](#end-of-a-players-race)). |
| A CPU rescued by Lakitu | yes | Each respawn point sends CPUs to the route point nearest to it. A helper path next to a respawn point can give the rescued CPUs a better place to start from ([Finding 7](#7-start-points-and-respawns)). |
| A CPU's Bullet Bill at its start | no | A CPU that starts a Bullet Bill keeps its target point; the game only checks that some point other than -2 exists within 500 units, and ends the Bullet Bill at once otherwise. Bullet Bills are re-routed like other CPUs once they are steeply above or below their target (flag 0x20 keeps them at the route's height over gaps) ([Finding 6](#path_find_options)). |

#### Helper paths on the original courses

The original courses do this. 30 of the 32 Grand Prix courses (all but GBA Bowser Castle 1 and SNES Rainbow Road) have
paths that no other path leads into, which only a re-route can reach: 187 paths of 2 to 31 points (typically about 8), mostly
with one next path. Their points lie a median of about 100 units beside the route at the same height (a tenth of them
300 or more units below it, under jumps and drops), and 83 % of them have drift setting 2
([Finding 13](#original-helper-paths)).

#### How to build one

This follows from the code and the original courses; it was not tested on a modified course.

- Make it a path of its own. An extra enemy point on the main path changes nothing, since a CPU only switches when the
  nearest point is on another path.
- Place its points so that they are the nearest ones only from the spots where CPUs get stuck or land. In a race the main
  route has a point every 75 to 150 units, the points the game adds included, so the helper path has to be nearer to
  those spots than the main route itself, not only than its enemy points; only on the stretches the game leaves straight
  (between paths, into a fork, out of a merge) are the enemy points at their ends the only points. Anywhere the helper
  path is nearer than the main route, a player's Bullet Bill also starts on it.
- It is an ordinary race path: give it at least one next path, list it as a previous path of the paths it leads into, and
  keep its points' settings sensible (drift 2, no Mushroom), since CPUs drive it like any other path. Give its first point
  a path find option of 0 unless it must be skipped by finished CPUs (-1) or Bullet Bills (-2).

### What each Mii title changes

The game turns the title of a Mii CPU into a set of bits. The bits that the route logic uses, the title each most likely
stands for, and what it changes ([Finding 15](#15-mii-titles)):

| Bit | Title (likely) | Effect on the route logic |
| --- | --- | --- |
| 0x4 | Boost Jumper | hops very often: at every trick chance, and on its own every 2 to 5 seconds; takes -3 paths and board-linked branches |
| 0x10 | Safe Driver | lanes beyond 50 % settle back three times faster |
| 0x20 | Drift Wizard | always keeps the mini-turbo; drift start check always passes |
| 0x40 | Aviator | takes -3 paths and board-linked branches; uses Mushrooms while gliding; no shortcuts; hops at every trick chance |
| 0x80 | Dolphin | takes -4 paths; uses Mushrooms in water; no shortcuts |
| 0x800 | Model Driver | hops at every trick chance |
| 0x100, 0x1000 | Rookie, Star Racer | drive exactly on the points; never drift; never hop at trick chances |

The terms of the last column are those of the sections above: lanes ([Scale](#scale-width)), the drift start check and
the mini-turbo ([Drift setting](#drift-setting)), shortcuts ([Mushroom shortcuts](#mushroom-shortcuts)), -3 and -4 paths
([Path find options](#path-find-options)), board-linked branches ([Objects linked to race
paths](#objects-linked-to-race-paths)) and trick chances ([Flag 0x08](#flag-0x08-no-tricks)).

The title names come from the order of the game's title messages; for bits 0x4, 0x20, 0x40 and 0x80 the name matches
what the code does with the bit, the others are taken from the same order and are less certain.

### Race and battle compared

| | Race (and award ceremony) | Battle |
| --- | --- | --- |
| Route the CPUs drive | A denser copy of the enemy points and paths, built when the course loads: points every 75 to 150 units along a smooth curve | The enemy points as they are |
| Direction of a path | One way, first point to last point | Both ways; the paths form a network of two-way roads |
| Links of a point | previous and next | next only: the neighbours in the path plus one end point of every previous **and** next path |
| Link end flags | Not used by the original courses (always 0). The "Next" bits are honoured and would enter a next path at its last point | Essential. One bit per link: which end of the linked path the junction is at |
| Choice at a junction | random among normal branches; mushroom shortcut; Mii title paths; linked objects | by what the CPU is doing: random, the highest or lowest score of the branch (worked out from the item boxes, rivals or coins around it), the branch nearest to or farthest from a target |
| Reaching a point | within 280 units (140 with flag 0x04), or past the invisible wall | within 100 units (140 with flag 0x04), unless the point is almost exactly to the side of the kart; no wall |
| Lane | per CPU, up to 85 % of the half-width | centre of the point, unless the obstacle avoidance pushes it (at most 85 % of the half-width) |

The sources of this table: [Findings 1 to 3](#1-how-the-entries-become-a-route), [5](#5-reaching-a-point),
[6](#scale) and [8](#8-junction-choice).

### What each setting does, at a glance

| Setting | Race | Battle |
| --- | --- | --- |
| Position | route point (plus the added points) | point of the network |
| Scale | half-width of the lanes: scale × 50 | limit of the sideways push; also the width of the zone around the route in which item boxes, coins and karts count for the junction choice |
| Mushroom setting | 0: a Mushroom may be used. 1: first point of a mushroom shortcut branch. Other: no Mushroom | 0: a Mushroom may be used. Other: no Mushroom. No shortcuts. All original battle points are 0 |
| Drift setting | 0: drift allowed. 1: drift ends here. 2: drift ends here and the mini-turbo is lost. 3 and above: the corner decides | never read (battle CPUs do not drift) |
| Flag 0x01 | cornering line for drifting CPUs | no effect |
| Flag 0x02 | height re-route | same |
| Flag 0x04 | move on at 140 units instead of 280, and acts as 0x01 | move on at 140 units instead of 100 (less precise) |
| Flag 0x08 | no trick hops | no effect in practice (tricks only come from 0x80) |
| Flag 0x10 | longer, gentler drifts | no effect |
| Flags 0x20 / 0x40 | Bullet Bill height pull / ending paused | no effect |
| Flag 0x80 | no rubber-banding: fixed share of the top speed | **jump point**: fixed share of the top speed, aim at the exact centre, and hop (trick) at every trick chance. The only flag the original battle courses use |
| Path find options | -1 / -2: skipped by some re-routes. -3 / -4: Mii title path. Non-zero: not used to find the CPUs' start | -3 / -4 are recorded but have no effect; the other values only matter in races. All original battle points are 0 |
| Max search Y offset | height filter of the nearest-point search | same filter (start points, respawns, re-routes) |
| First point, point count | the consecutive enemy points of the path | same |
| Previous paths | the first point of the path gets the last point of each as a previous point | they become next links of the first point |
| Next paths | next links of the last point | same |
| Link end flags | bit 16 + n: next path number n is joined at its **last** point instead of its first; bits 0 to 15 are not read. n counts the valid entries in slot order | bit n (0 to 15): previous path number n is joined at its **first** point instead of its last. Bit 16 + n: next path number n is joined at its **last** point instead of its first |

## Glossary

### Field::MapdataEnemyPointData (size 0x18, template/Field/Entry/EnemyPoint.hpp)

One KMP ENPT entry.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `position` | 0x00 | `sead::Vector3f` | existing | |
| `scale` | 0x0C | `float` | new | lateral half-width is `scale * 50` |
| `mushroom_setting` | 0x10 | `EMushroomSetting` | new | |
| `drift_setting` | 0x12 | `EDriftSetting` | new | values above 3 act as `BY_CORNER` |
| `flags` | 0x13 | `u8` | new | a set of `EnemyPointFlags` bits |
| `path_find_options` | 0x14 | `s16` | new | |
| `max_search_y_offset` | 0x16 | `s16` | new | |

#### Field::MapdataEnemyPointData::EMushroomSetting (enum class : u16)

New; named by this research. Any value other than 0 and 1 acts as `NO_USE`.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `USE` | new | CPUs may use a Mushroom |
| 1 | `SHORTCUT_START` | new | first point of a mushroom shortcut branch (race); no Mushroom use |
| 2 | `NO_USE` | new | |

#### Field::MapdataEnemyPointData::EDriftSetting (enum class : u8)

New; named by this research.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `ALLOW` | new | |
| 1 | `END` | new | |
| 2 | `END_NO_MINI_TURBO` | new | |
| 3 | `BY_CORNER` | new | the drift ends where the road straightens or bends the other way |

#### Field::EnemyPointFlags (enum : u8)

New; named by this research. A plain enum in the `Field` namespace, since `flags` holds any combination of its values.

| Value | Name | Status |
| --- | --- | --- |
| 0x01 | `ENEMY_POINT_CORNERING` | new |
| 0x02 | `ENEMY_POINT_HEIGHT_REROUTE` | new |
| 0x04 | `ENEMY_POINT_PRECISE` | new |
| 0x08 | `ENEMY_POINT_NO_TRICK` | new |
| 0x10 | `ENEMY_POINT_HOLD_DRIFT` | new |
| 0x20 | `ENEMY_POINT_KILLER_FOLLOW_HEIGHT` | new |
| 0x40 | `ENEMY_POINT_KILLER_NO_END` | new |
| 0x80 | `ENEMY_POINT_FORCE_BASE_SPEED` | new |

### Field::MapdataEnemyPoint (size 0x54, template/Field/Entry/EnemyPoint.hpp)

Runtime wrapper of one point: links, derived geometry.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_data` | 0x00 | `MapdataEnemyPointData *` | existing | from the base class |
| `m_path` | 0x04 | `MapdataEnemyPath *` | new | owning path |
| `m_prev_points` | 0x08 | `s32 *` | new | point indices; not allocated in battle |
| `m_next_points` | 0x0C | `s32 *` | new | point indices |
| `m_prev_count` | 0x10 | `s32` | new | always 0 in battle |
| `m_next_count` | 0x14 | `s32` | new | |
| `m_sector` | 0x18 | `s32` | new | checkpoint sector, 0xFF when not set |
| `m_index` | 0x1C | `s32` | new | own index in its accessor |
| `m_path_index` | 0x20 | `s32` | new | index of the owning path |
| `m_corner` | 0x24 | `f32` | new | signed cosine of the horizontal turn; 1.0 by default; race only |
| `m_width` | 0x28 | `f32` | new | `scale * 50` |
| `m_normal` | 0x2C | `sead::Vector3f` | new | ground normal under the point |
| `m_side_axis` | 0x38 | `sead::Vector3f` | new | `normalize(next - this) x m_normal`; race only |
| `m_direction` | 0x44 | `sead::Vector3f` | new | only the constructor writes it, (0, 0, 1) in game; read as an axis by `AIObjectSearcher::isMapObjectToAvoid_`, Finding 6 |
| `m_internal_flags` | 0x50 | `u32` | new | 1: `m_side_axis` valid. 0xA: point of an award start path; bits 0x2 and 0x8 have no reader |

### Field::MapdataEnemyPathData (size 0x48, template/Field/Entry/EnemyPath.hpp)

One KMP ENPH entry.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_start_point` | 0x00 | `u16` | existing | |
| `m_point_num` | 0x02 | `u16` | existing | |
| `m_previous_points` | 0x04 | `u16[16]` | existing | these are **path** indices, 0xFFFF = none |
| `m_next_points` | 0x24 | `u16[16]` | existing | **path** indices, 0xFFFF = none |
| `m_link_end_flags` | 0x44 | `u32` | new | which end of each linked path is joined; see Finding 2 |

### Field::MapdataEnemyPath (size 0x40, template/Field/Entry/EnemyPath.hpp)

Runtime wrapper of one path.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_find_type` | 0x04 | `s8` | new | -2 by default; -3 or -4 when a point of the path has that `path_find_options` |
| `m_start_adjust` | 0x08 | `s32` | new | added to `m_start_point` everywhere it is read; 0 on KMP paths, the part of the re-sampled start above 0xFFFF on `PathSmoother` paths |
| `m_count_adjust` | 0x0C | `s32` | new | added to `m_point_num` everywhere it is read; same idea for the point count |
| `m_depth` | 0x10 | `s32` | new | depth at which a depth-first walk over next paths from path 0 first reaches the path (not necessarily the shortest); -1 when not reachable; never read, Finding 9 |
| `m_obj_link_array` | 0x14 | `sead::FixedPtrArray<ObjectBase, 8>` | existing | objects linked to the path |

### Other members

Members of classes that have a template. The rows with status `new` are added by the patch.

| Class | Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- | --- |
| `Enemy::AIControlBase` | `m_ai_path_handler` / `m_ai_path_point` / `m_ai_stuck` | 0x10 / 0x18 / 0x28 | pointers | existing | |
| `Enemy::AIControlBase` | `m_enemy_point_accessor` | 0x38 | `MapdataEnemyPointAccessor *` | existing | the accessor of the re-route search: the re-sampled list in race mode, Finding 12 |
| `Enemy::AIControlBase` | `m_search_mode` | 0x48 | `u32` | existing | how a battle CPU chooses at a junction, Finding 8 |
| `Enemy::AIControlBattle` | `m_search_weights` | 0x60 | `s32 *` | new | weight table of the random search mode choice, Finding 8 |
| `Enemy::AIControlBattle` | `m_battle_type` | 0x90 | `s32` | new | named after its setter `AIControlBattle::setBattleType`; 1 or 2 per CPU in coin battle, 0 from the constructor, Finding 8 |
| `Enemy::AIControlBattle` | `m_do_not_select_backward` | 0x95 | `bool` | new | named after its setter `AIControlBattle::setDoNotSelectBackward`; when set, `stateInitLockedOn` keeps `AIPathHandler::m_do_not_select_backward`, Finding 8 |
| `Enemy::AIControlRace` | `m_watched_ai` | 0x60 | `AI *` | new | AI of `CRaceInfo::m_detail_kart_id`, Finding 10 |
| `Enemy::AIControlRace` | `m_killer_hold_frames` | 0x7C | `u16` | new | frames in a row of a Bullet Bill's ending phase on points with flag 0x40 without reaching a new point, Finding 6 |
| `Enemy::AIControlRace` | `m_skip_watch` | 0x91 | `bool` | new | while set, `update` does not call `watchPlayerAndSwitchCollision`; what it stands for is an open question |
| `Enemy::AIEngine` | `m_ai_control` | 0x30 | `AIControlBase *` | existing | |
| `Enemy::AIEngine` | `m_wall_frames` | 0x4C | `u32` | new | frames in a row touching a wall, Finding 12 |
| `Enemy::AIManager` | `m_ais` | 0x38 | `AI *[8]` | existing | |
| `Field::MapdataEnemyPathAccessor` | `m_depth_num` | 0x1C | `s32` | new (was unnamed) | highest `m_depth` + 1; never read, Finding 9 |
| `Field::MapdataGeoObjData` | `m_settings[0]`, `m_settings[7]`, `m_enemy_route` | 0x2A, 0x38, 0x3C | | existing | how an object is linked to a path, Finding 8; `m_settings[0]` pairs two crossings, Finding 10 |
| `Field::MapdataJugemPoint` | `m_nearest_enemy_point` | 0x2C | `s32` | new | point a CPU resumes from after a respawn here, an index of the re-sampled list in race mode (whose entries are `MapdataEnemyPoint` objects too, hence the name); -1 when none |
| `Field::ObjectBase` | `m_path` | 0x10 | `ObjectPathBase *` | existing | the object's own movement route |
| `Field::ObjectBase` | `m_ai_signal` | 0x78 | `bool` | renamed (was `m_cpu_should_avoid_object`) | a state the object shows to the CPUs; its meaning depends on the reader, Findings 8 and 10 |
| `Field::ObjectDirector` | `m_obj_link_array` | 0x50 | | existing | every object whose GOBJ `m_enemy_route` is 0 or more, Finding 8 |
| `Field::ObjectDirector` | `m_coin_manager` / `m_bd_board_objects` / `m_cmn_start_grid_sdata` | 0xB8 / 0xC8 / 0x154 | | existing | |
| `KDGndCol::CheckIF` | `m_collision_result` | 0x04 | `u32` | existing | bit 0 `COLLIDING_WITH_WALL` |
| `Kart::Director` | `m_ai_manager` / `m_is_ai_valid` | 0x58 / 0x19C | | existing | |
| `Kart::VehicleBase` | `unk_0x99` | 0x99 | `u8` | existing | tested by `startKiller_Impl`; 0 for a human player's kart in the tests |
| `Kart::VehicleBase` | `m_is_fake_goal` | 0xA6 | `bool` | existing | set once the kart has finished |
| `Kart::VehicleControlAI` | `m_max_speed_ratio` | 0xBE8 | `f32` | new | the speed ratio `AI::setMaxSpeedRatio` asks for |
| `Kart::VehicleControlAI` | `m_award_flag` | 0xBF8 | `bool` | new | award: `max_search_y_offset == 1` of the target; what it does is an open question |
| `Kart::VehicleControlAI` | `m_collision_switch` | 0xC25 | `bool` | new | written by `watchPlayerAndSwitchCollision`, read by `ObjectBase::checkDetail_KartHitObj`; not looked at |
| `Kart::VehicleMove` | `m_status_flags` | 0xC30 | `StatusFlags` | existing | bits used here: `jugem_recover` 0x20, `jugem_recover_ai_oob` 0x40, `wing_open` 0x80 (gliding), `accident_1` 0x10000 (meaning unknown), `killer` 0x400000 (Bullet Bill), `hang` 0x800000 |
| `Kart::VehicleMove` | `m_col_checks` | 0xC80 | `KDGndCol::CheckIF_EX[5]` | new | built one after the other by the constructor; bit 0 (`COLLIDING_WITH_WALL`) of `m_col_checks[1].m_collision_result` is "touching a wall" for the AI, Finding 12 |
| `Kart::VehicleMove` | `m_air_frames` / `m_boost_frames` | 0xD48 / 0xF9C | `s32` | existing | |
| `Kart::VehicleMove` | `m_air_rate` | 0xD98 | `f32` | new | `min(m_air_frames / 20, 1)`, Finding 5 |
| `Kart::VehicleMove` | `m_airborne_rate` | 0xDA4 | `f32` | new | 0 to 1; +1/20 per frame in the air, -1/20 per frame on the ground |
| `Kart::VehicleMove` | `m_drift_state` | 0xEF4 | `u8` | new | bits 0x18: the kart is drifting; only byte loads and stores in the whole code |
| `Kart::VehicleMove` | `m_forward_speed_ratio` | 0xF30 | `f32` | new | `m_forward_speed / m_current_max_speed_base`, 0 when moving backwards, Finding 11 |
| `Kart::VehicleMove` | `m_forward_dir` | 0xF44 | `sead::Vector3f` | new | a direction of the kart, used as "straight ahead" by `AIStuck::stateBackPathPoint` and `AIDriftDrive::calcSteerNormal_` |
| `Kart::VehicleMove` | `m_star_frames` / `m_ink_frames` | 0xFF4 / 0xFF8 | `s32` | existing | Star and Blooper ink frames left, Finding 10 |
| `Object::CoinManager` | `m_coins` | 0x48E8 | `sead::PtrArray<Coin>` | new | the `Object::Coin` objects (count at +0x48E8, pointers at +0x48F0), Finding 12 |
| `RaceSys::CRaceInfo` | `m_race_mode.m_play_mode` / `m_race_mode.m_rule_mode` / `m_race_mode.m_type` | 0x164 / 0x168 / 0x16C | | existing | play mode 1 MultiPlayer, 2 Online (`ERacePlayMode`); rule mode 1 Time Trials, 3 Battle, 7 DemoBattle; type 0 Coin (in battle) |
| `RaceSys::CRaceInfo` | `m_engine_level` / `m_race_mode_flag` / `m_detail_kart_id` | 0x170 / 0x178 / 0x184 | | existing | `m_race_mode_flag.multiplayer_or_online` is bit 3 (0x8) |
| `RaceSys::CRaceInfo::CKartInfo` | `m_player_type` | 0x14 | `EPlayerType` | existing | |
| `RaceSys::LapRankChecker::KartInfo` | `m_current_race_progress` | 0x14 | `f32` | existing | higher is further ahead |
| `Sequence::MenuData` | `m_ai_level` | 0x668 | `u8` | existing | CPU setting of a battle: 1 easy, 2 normal, 3 hard |

### Enemy::PointParam (size 0x10, template/Enemy/PointParam.hpp, new file)

Copy of the settings of one point, owned by `AIPathHandler`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mushroom_setting` | 0x0 | `MapdataEnemyPointData::EMushroomSetting` | new | |
| `m_drift_setting` | 0x2 | `MapdataEnemyPointData::EDriftSetting` | new | |
| `m_flags` | 0x4 | `u32` | new | |
| `m_corner` | 0x8 | `f32` | new | copy of `AIPathPoint::m_corner` |

### Enemy::GoNextInfo (size 0x30, template/Enemy/GoNextInfo.hpp, new file)

Argument of every "advance to the next point" call. Size taken from the stack layout in `AIPathHandler::update`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_is_relocate` | 0x00 | `bool` | new | 1: jump to `m_base_point_index` instead of advancing |
| `m_kart_pos` | 0x04 | `sead::Vector3f` | new | |
| `m_base_point_index` | 0x10 | `s32` | new | point whose next points are chosen from |
| `m_target_point_index` | 0x14 | `s32` | new | |
| `m_branch_num` | 0x18 | `s32` | new | output |
| `m_branch_index` | 0x1C | `s32` | new | output |
| `m_search_mode` | 0x20 | `u32` | new | copy of `AIControlBase::m_search_mode` |
| `m_do_select_shortcut` | 0x24 | `bool` | new | |
| `m_do_not_select_backward` | 0x25 | `bool` | new | |
| `m_do_select_root_branch` | 0x26 | `bool` | new | 1: always take branch 0 |
| `m_is_killer` | 0x27 | `bool` | new | 1: aim at the point centre |
| `m_corner_line_shift` | 0x2C | `f32` | new | filled from `AIPathHandler::m_corner_line_shift` |

### Enemy::AIPathPoint (size 0x58) and AIPathPointBattle (size 0x70) (template/Enemy/AIPathPoint.hpp, new file)

Per-CPU cursor on the route. `AIPathPointAward` (0x58) and `AIPathPointBattleCoin` (0x70) add no members.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_ai_path_manager` | 0x04 | `AIPathManager *` | new | |
| `m_ai_manager` | 0x08 | `AIManager *` | new | |
| `m_ai` | 0x0C | `AI *` | new | |
| `m_enemy_point_accessor` | 0x10 | `MapdataEnemyPointAccessor *` | new | |
| `m_next_point` | 0x14 | `MapdataEnemyPoint *` | new | the point after the target |
| `m_target_point` | 0x18 | `MapdataEnemyPoint *` | new | the point the CPU is heading to |
| `m_prev_point` | 0x1C | `MapdataEnemyPoint *` | new | the point just reached |
| `m_history_points` | 0x20 | `MapdataEnemyPoint *[3]` | new | older points |
| `m_start_point_index` | 0x2C | `s32` | new | |
| `m_branch_index` | 0x30 | `s32` | new | |
| `m_obj_check_rate` | 0x34 | `u32` | new | 75, or 50 on course 15 |
| `m_corner` | 0x38 | `f32` | new | |
| `m_width` | 0x3C | `f32` | new | |
| `m_offset` | 0x40 | `f32` | new | lateral offset in units |
| `m_offset_rate` | 0x44 | `f32` | new | lane, as a fraction of `m_width` |
| `m_move_back_rate` | 0x48 | `f32` | new | |
| `m_target_trans` | 0x4C | `sead::Vector3f` | new | aim point |
| `AIPathPointBattle::m_battle_searcher` | 0x58 | `AIBattleSearcher *` | new | |
| `AIPathPointBattle::m_target_for_branch_trans` | 0x5C | `sead::Vector3f` | new | |
| `AIPathPointBattle::m_current_path` | 0x68 | `MapdataEnemyPath *` | new | path being traversed |
| `AIPathPointBattle::m_path_entry_point` | 0x6C | `s32` | new | end point the path was entered from |

### Enemy::AIPathHandler (size 0x4C, template/Enemy/AIPathHandler.hpp, new file)

Per-CPU route logic.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_pass_mode` | 0x00 | `EPassMode` | new | |
| `m_relocate_pass_mode` | 0x04 | `EPassMode` | new | value `m_pass_mode` takes after a relocation |
| `m_check_timer` | 0x0C | `u32` | new | frames since the last advance or check |
| `m_reach_radius_sq` | 0x10 | `f32` | new | |
| `m_default_reach_radius_sq` | 0x14 | `f32` | new | |
| `m_reach_cos_min` | 0x18 | `f32` | new | |
| `m_corner_line_shift` | 0x1C | `f32` | new | |
| `m_target_dist_sq` | 0x20 | `f32` | new | |
| `m_path_point` | 0x24 | `AIPathPoint *` | new | |
| `m_ai_manager` / `m_ai` / `m_ai_auto_steer` / `m_ai_control` | 0x28 / 0x2C / 0x30 / 0x34 | pointers | new | |
| `m_current_param` | 0x38 | `PointParam *` | new | settings of the point **just reached** |
| `m_next_param` | 0x3C | `PointParam *` | new | settings of the **target** point |
| `m_pending_path` | 0x40 | `MapdataEnemyPath *` | new | |
| `m_can_adjust_offset` | 0x44 | `bool` | new | |
| `m_do_not_select_backward` | 0x45 | `bool` | new | |
| `m_do_select_root_branch` | 0x46 | `bool` | new | |
| `m_is_battle` | 0x47 | `bool` | new | |
| `m_shortcut_mode` | 0x48 | `EShortcutMode` | new | |
| `m_do_select_shortcut` | 0x49 | `bool` | new | |
| `m_advanced_this_frame` | 0x4A | `bool` | new | |

#### Enemy::AIPathHandler::EPassMode (enum class : s32)

New; named by this research. The pass-through test of Finding 5.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `NONE` | new | no test |
| 1 | `BISECTOR` | new | plane bisecting the turn at the target |
| 2 | `LEAVING` | new | plane square to the direction the route leaves the target in |

#### Enemy::AIPathHandler::EShortcutMode (enum class : u8)

New; named by this research. Whether a CPU holding a Mushroom takes a mushroom shortcut (Finding 6).

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `NEVER` | new | |
| 1 | `HALF` | new | decided at random when the item is received, 50 % |
| 2 | `ALWAYS` | new | |

### Enemy::AIStuck (size 0x70, template/Enemy/AIStuck.hpp, new file)

Per-CPU progress watch: back-up, re-route request, Lakitu. A state machine (`Util::TStateObserverEx` at +0x4); its nine
state functions are its vtable.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_ai_path_handler` / `m_ai_path_point` / `m_ai` / `m_ai_auto_steer` | 0x28 / 0x2C / 0x30 / 0x38 | pointers | new | set by `init` |
| `m_fall_pos` | 0x3C | `sead::Vector3f` | new | kart position at the last relocation |
| `m_slow_frames` | 0x48 | `s32` | new | Finding 11 |
| `m_no_advance_frames` | 0x4C | `s32` | new | Finding 11 |
| `m_fall_count` | 0x50 | `s32` | new | Finding 11 |
| `m_back_phase` / `m_back_frames` | 0x58 / 0x5C | `EBackPhase` / `u32` | new | Finding 11 |
| `m_back_rate` / `m_back_rate_max` | 0x60 / 0x64 | `f32` | new | Finding 11 |
| `m_reroute_request` | 0x69 | `bool` | new | set for one frame to ask for a re-route, read by `AIControlBase::isAIFallSignal`, Finding 12 |
| `m_is_battle` / `m_is_multiplayer` | 0x6A / 0x6B | `bool` | new | |
| `m_is_race_started` | 0x6C | `bool` | new | `stateIdle` waits for `RaceSys::IsRaceState` |

+0x54 is only written by the constructor and stays unnamed.

#### Enemy::AIStuck::EState (enum class : u8)

New; the names come from the state functions (`stateIdle`, `stateCheckStuck`, ...). The state of the `TStateObserverEx`.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `IDLE` | new | |
| 1 | `CHECK_STUCK` | new | watching for progress |
| 2 | `BACK_PATH_POINT` | new | backing up |
| 3 | `START_OUT_OF_BOUNDS` | new | handing the kart to Lakitu |

#### Enemy::AIStuck::EBackPhase (enum class : s32)

New; named by this research. The phases of the back-up of Finding 11.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `REVERSE` | new | |
| 1 | `DRIVE_BACK` | new | driving to the aim point behind |
| 2 | `TURN_TO_ROUTE` | new | turning back toward the route |

### Enemy::AIAutoSteer (size 0x100, template/Enemy/AIAutoSteer.hpp, new file)

Steering a CPU does outside the route: avoiding, waiting at crossings, running from boards, gathering coins. A state
machine (`Util::TStateObserverEx` at +0x4); its 23 state functions are its vtable. Only the members this topic uses are
named; the gaps belong to the avoid, zig-zag and side-attack states.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_ai` / `m_ai_path_handler` / `m_ai_stuck` / `m_ai_manager` | 0x28 / 0x30 / 0x38 / 0x3C | pointers | new | |
| `m_object_director` | 0x4C | `Field::ObjectDirector *` | new | |
| `m_wait_object` | 0x50 | `Field::ObjectBase *` | new | the crossing the CPU waits for |
| `m_drive_info` | 0x54 | `DriveInfo *` | new | |
| `m_coin_manager` / `m_gather_target` | 0x58 / 0x5C | `Object::CoinManager *` / `Object::Coin *` | new | Finding 12 |
| `m_state_frames` / `m_state_frames_max` | 0x6C / 0x78 | `u32` | new | timers of the states that time themselves |
| `m_bd_board_num` | 0x84 | `s32` | new | size of `ObjectDirector::m_bd_board_objects` in battle, Finding 10 |
| `m_ai_level` | 0x88 | `EAILevel` | new | |
| `m_gather_radius` | 0x90 | `f32` | new | Finding 12 |
| `m_is_far_behind` | 0x94 | `bool` | new | 1 while the CPU is behind `AIControlRace::m_watched_ai` and more than 1500 units from it, Finding 10 |
| `m_wait_brake` / `m_wait_any_direction` | 0x95 / 0x96 | `bool` | new | Finding 10; `m_wait_any_direction` is status bit 0x10000 when the wait began, and keeps the wait going when the crossing is behind the kart |
| `m_is_battle` | 0x97 | `bool` | new | |
| `m_gather_target_found` | 0x98 | `bool` | new | Finding 12 |
| `m_run_away_target` | 0x9C | `sead::Vector3f` | new | Finding 10 |
| `m_crossings` / `m_gather_coins` | 0xA8 / 0xD4 | `sead::FixedPtrArray<..., 8>` | new | the crossings of Finding 10; the coins `stateInitGather` collects and `stateGather` still has to visit, Finding 12 |

#### Enemy::AIAutoSteer::EState (enum class : u8)

New; the names come from the state functions (`stateIdle`, `stateAvoid`, ...), in vtable order. The state of the
`TStateObserverEx`.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `IDLE` | new | |
| 1 | `AVOID` | new | |
| 2 | `REACT` | new | |
| 3 | `GOTO` | new | |
| 4 | `ZIG_ZAG` | new | |
| 5 | `RUN_AWAY` | new | battle: driving away from a board, Finding 10 |
| 6 | `WAIT` | new | waiting before a train crossing, Finding 10 |
| 7 | `SIDE_ATTACK` | new | |
| 8 | `GENERATE` | new | |
| 9 | `GATHER` | new | coin battle: driving to nearby coins, Finding 12 |
| 10 | `GO_MASTER` | new | |

### Other classes

Members of classes that still have no template and are only mentioned in passing keep a descriptive name in the text.
They are not in the patch.

| Class | Member | Offset | Note |
| --- | --- | --- | --- |
| `Enemy::AI` | `m_ai_engine` | 0x08 | the AI's `AIEngine` |
| `Enemy::AI` | `m_title_mask` | 0x10 | |
| `Enemy::AI` | `m_base_speed_ratio` | 0x18 | |
| `Enemy::AI` | `m_is_player_kart` | 0x24 | 1 when the kart's `CKartInfo::m_player_type` is Master, User, Ghost or Master_Replay (`AI::init`), i.e. not a CPU |
| `Enemy::AI` | `m_force_base_speed` | 0x25 | |
| `Enemy::AI` | `m_is_backing_up` | 0x26 | Finding 11 |
| `Enemy::AIDriftDrive` | `m_hop_interval` / `m_hop_frames` | 0x48 / 0x4C | `u32`; frames between the extra hops of title bit 0x4, and frames since the last hop, Finding 6 (flag 0x08) |
| `Enemy::AIObjectSearcher` | `m_is_race` | 0x30 | `IsRaceTypeThinkAsRace()`, written by `AIObjectManager::init` |
| `Enemy::AIPathManager` | `m_path_analyzer` | 0x24 | `PathAnalyzer *`, battle only |
| `Enemy::AIPathManager` | `m_race_point_accessor` / `m_race_path_accessor` | 0x28 / 0x40 | the accessors of the re-sampled race route (`PathSmoother::setupAccessor`), race mode only, Finding 1 |
| `Enemy::AIPathManager` | `m_start_points` | 0x64 | `s32[8]` |
| `Enemy::DriveInfo` | `m_stick` | 0x0C | `sead::Vector2f` |
| `Enemy::DriveInfo` | `m_buttons` | 0x14 | 1 accelerate, 2 brake / reverse, 0x4000 hop |
| `Enemy::DriveInfo` | `m_allow_miniturbo` | 0x28 | |
| `Enemy::DriveInfo` | `m_request_flags` | 0x2C | (was called `m_drift_request` here) bit 0x40: neither accelerate nor brake, Finding 10 |
| `Enemy::DriveInfo` | `m_collision_switch` | 0x31 | written by `watchPlayerAndSwitchCollision` like `VehicleControlAI::m_collision_switch`; not looked at |
| `Enemy::PathAnalyzer` | `m_nodes` / `m_edges` | 0x04 / 0x0C | node 0x20 bytes: point index, position, `scale * 50` (+0x10), neighbour count, neighbours, edges; edge 0x24 bytes: two nodes, direction, length, 1 / length |
| `Enemy::TargetSearcher` | `m_width_scale` | 0x3C | 1.0 for all four searchers (`AIBattleSearcher::init`, `AIBattleSearcherCoin::init`) |
| `Field::ObjectCrossing` | `m_trains` | 0x188 | the two `N64Train` objects (+0x188, +0x18C) |
| `Field::ObjectCrossing` | `m_is_master` | 0x191 | the crossing of the pair that its partner found first |
| `Field::ObjectCrossing` | `m_partner` | 0x1A0 | the other crossing with the same `m_settings[0]` |
| `Field::ObjectCrossing` | `m_train_dist_sq` | 0x1A4 | `sParam` +0x4, squared |
| `Field::ObjectCrossing` | `m_flash_frames` / `m_signal_frames` | 0x1AC / 0x1B0 | Finding 10 |
| `Field::ObjectFirePillar`, `Field::ObjectShellFish` | `m_state` | 0x185 | state byte of the object |
| `Object::Coin` | `m_flags` | 0x28 | bit 0x8 is set by `Coin::kill` |

The AI state machines (`Util::TStateObserverEx`) keep the current state at +0x8 of their owner, the next state at +0x21
and a "change requested" byte at +0xA. The states of `AIStuck` and `AIAutoSteer` are listed in their `EState` enums above;
`AIEngine` (the vtable of its state functions read in order) has no enum: its state 0 is `stateIdle`, 1 `stateReady`, 2
`stateRun`, 3 `statePlayerIdle`, 4 `stateGhostIdle`, 5 `stateAfterGoal`, 6 `stateStop`.

### Functions

Names ported from `dlp` (exact matches) count as existing.

| Name | Address (eur2) | Status | Note |
| --- | --- | --- | --- |
| `Field::MapdataEnemyPoint::setup` | 0x0038F0E8 | existing | links of a point, Finding 2 |
| `Field::MapdataEnemyPoint::setupNrm` | 0x0038F710 | existing | `m_width`, `m_normal` |
| `Field::MapdataEnemyPath::createDepth_` | 0x003875E4 | existing | `m_depth` |
| `Field::MapdataEnemyPathAccessor::setupObjLink_` | 0x003B2F7C | existing | objects linked to paths |
| `Field::MapdataEnemyPathAccessor::setupPathDepth` | 0x003B3118 | existing | |
| `Field::MapdataEnemyPathAccessor::setupPathPointLink` | 0x003B31F8 | existing | `m_find_type` |
| `Field::MapdataCheckPath::createDepth_` / `Field::MapdataCheckPathAccessor::setupPathDepth` | 0x00387560 / 0x003B2B98 | existing | the same values for the checkpoints |
| `Field::FindSectorForEnemyPt` | 0x003A7538 | existing | |
| `Field::FindNearestEnemyPtHndl` | 0x003BB878 | existing | |
| `Field::FindNearestEnemyPtHndlFromSector` | 0x003BB8A8 | existing | |
| `Field::GetEnemyPathAccessor` | 0x003A7648 | existing | |
| `Field::GetEnemyPointAccessor` | 0x003A83C4 | existing | the KMP point accessor |
| `Field::IsValidEnemyPath` | 0x003874D8 | existing | |
| `MapdataAccessorBase<MapdataEnemyPath>::constructLocal` | 0x005D0774 | existing | |
| `MapdataAccessorBase<MapdataEnemyPoint>::constructLocal` | 0x005D094C | existing | |
| `Enemy::IsRaceTypeThinkAsRace` / `IsRaceTypeThinkAsBattle` | 0x0033C7DC / 0x0033C830 | existing | race mode / battle mode |
| `Enemy::IsDoAsAI` | 0x0033E4C8 | existing | |
| `Enemy::GetAI` | 0x0033CD7C | existing | |
| `Enemy::ChangeToAI` / `Kart::Director::changeToAI` | 0x0032C12C / 0x002FA300 | existing | |
| `Enemy::AIPathManager::init` | 0x00335744 | existing | Finding 1 |
| `Enemy::AIPathManager::findNearEnemyPoint` | 0x0033553C | existing | the nearest-point search |
| `Enemy::AIPathManager::getEnemyPointAccessor` | 0x00335720 | existing | `m_race_point_accessor` in race mode, else `Field::GetEnemyPointAccessor()` |
| `Enemy::PathSmoother::init` | 0x00332054 | existing | |
| `Enemy::PathSmoother::setupBezier_` | 0x00331628 | existing | |
| `Enemy::PathSmoother::setupAccessor` | 0x00331C94 | existing | |
| `Enemy::PathSmoother::calcPathCosineAndAxis` / `calcPointCosineAndAxis_` | 0x00331E50 / 0x00331EF4 | existing | |
| `Enemy::PathAnalyzer::PathAnalyzer` | 0x00330E2C | existing | |
| `Enemy::PointParam::setParam` | 0x0032C174 | existing | |
| `Enemy::PointParam::isUseKinoko` | 0x005094FC | existing | |
| `Enemy::AIPathPoint::goNextPoint` | 0x0032E758 | existing | |
| `Enemy::AIPathPoint::addOffsetRate` | 0x0032E960 | existing | |
| `Enemy::AIPathPoint::calcNextTargetTrans` | 0x0032E9A8 | existing | |
| `Enemy::AIPathPoint::getInterpolateTarget` / `resetNextTargetTrans` | 0x0032EB80 / 0x0032ECC0 | existing | |
| `Enemy::AIPathPoint::selectNextPointHandle_` | 0x0032ECE8 | existing | |
| `Enemy::AIPathPoint::calcPointOffsetDistance_` | 0x0032ED64 | existing | |
| `Enemy::AIPathPoint::selectNextPointHandleIndex_` | 0x0032EE54 | existing | |
| `Enemy::AIPathPoint::selectNextPointHandleIndexWithShortcut_` | 0x0032EF84 | existing | junction choice in race |
| `Enemy::AIPathPointAward::calcNextTargetTrans` | 0x0033AF54 | existing | |
| `Enemy::AIPathPointBattle::calcNextTargetTrans` | 0x0033B040 | existing | |
| `Enemy::AIPathPointBattle::selectNextPointHandle_` | 0x0033B0A4 | existing | |
| `Enemy::AIPathPointBattle::selectNextPointHandleIndex_` | 0x0033B18C | existing | junction choice in battle |
| `Enemy::AIPathPointBattleCoin::selectNextPointHandleIndex_` | 0x0033C51C | existing | |
| `Enemy::AIPathHandler::AIPathHandler` | 0x00335354 | existing | allocates the path classes |
| `Enemy::AIPathHandler::init` | 0x00334EC4 | existing | |
| `Enemy::AIPathHandler::update` | 0x00334F74 | existing | reach test, height re-route |
| `Enemy::AIPathHandler::goNextPath_` | 0x003347E4 | existing | |
| `Enemy::AIPathHandler::startKiller` | 0x0033491C | existing | |
| `Enemy::AIPathHandler::isTimeToEndDrift` | 0x00334974 | existing | |
| `Enemy::AIPathHandler::onOutOfBoundsInner` | 0x003349F0 | existing | respawn |
| `Enemy::AIPathHandler::isTargetToStartDrift` | 0x00334B18 | existing | |
| `Enemy::AIPathHandler::isPassedThroughPathPoint_` | 0x00334B88 | existing | the pass-through plane |
| `Enemy::AIPathHandler::initMoveBackTargetToPreviousPath` / `finishMoveBackTargetToPreviousPath` | 0x00334DF4 / 0x00334EA8 | existing | |
| `Enemy::AIPathHandler::onAIFall` | 0x003352B4 | existing | |
| `Enemy::AIPathHandler::ShortCutInfo::isProbableToSelect` | 0x005095C0 | existing | |
| `Enemy::AIControlBase::AIControlBase__sub_object` (constructor) | 0x00332F38 | existing | |
| `Enemy::AIControlBase::initAfterManager` | 0x00332A38 | existing | |
| `Enemy::AIControlBase::isGoInCornerAngle` / `isDriftCornerAngle` | 0x00332AF4 / 0x00332B24 | existing | |
| `Enemy::AIControlBase::setBasicDriveInfo_` | 0x00332B98 | existing | |
| `Enemy::AIControlBase::isAIFallSignal` | 0x005095A0 | existing | |
| `Enemy::AIControlRace::startKiller` | 0x00333080 | existing | |
| `Enemy::AIControlRace::initAfterManager` | 0x00333204 | existing | |
| `Enemy::AIControlRace::watchPlayerAndSwitchCollision` | 0x0033339C | existing | `AIAutoSteer::m_is_far_behind` |
| `Enemy::AIControlRace::init` | 0x003334B0 | existing | |
| `Enemy::AIControlRace::update` | 0x00333548 | existing | |
| `Enemy::AIControlRace::onAIFall` | 0x00333CC8 | existing | the re-route, race |
| `Enemy::AIControlBattle::stateSearchCoin` | 0x00338480 | existing | |
| `Enemy::AIControlBattle::stateSearchItem` | 0x0033876C | existing | |
| `Enemy::AIControlBattle::initAfterManager` | 0x00338814 | existing | |
| `Enemy::AIControlBattle::stateInitRunAway` | 0x00338878 | existing | |
| `Enemy::AIControlBattle::stateInitLockedOn` | 0x00338970 | existing | |
| `Enemy::AIControlBattle::setBasicDriveInfo_` | 0x00338994 | existing | |
| `Enemy::AIControlBattle::stateInitSearchCoin` | 0x003389E0 | existing | |
| `Enemy::AIControlBattle::stateInitSearchItem` | 0x00338A8C | existing | |
| `Enemy::AIControlBattle::stateInitSearchRival` | 0x00338B2C | existing | |
| `Enemy::AIControlBattle::init` | 0x00338C34 | existing | |
| `Enemy::AIControlBattle::setBattleType` / `setDoNotSelectBackward` | 0x0033863C / 0x00338C2C | existing | virtual (slots 11 and 13); the only writers of `m_battle_type` / `m_do_not_select_backward` besides the constructor |
| `Enemy::TeamInfo::decideTeamBattleType` | 0x0033E520 | existing | calls `setBattleType(1 or 2)` |
| `Enemy::AIBattleManager::stateInitCoinIdle` / `stateCoinIdle` | 0x00337F24 / 0x00337C68 | existing | the callers of `decideTeamBattleType` |
| `Enemy::AIControlBattle::update` | 0x00338D6C | existing | |
| `Enemy::AIControlBattle::onAIFall` | 0x00338EF4 | existing | the re-route, battle |
| `Enemy::AIControlAward::initAfterManager` | 0x003374B0 | existing | |
| `Enemy::AISpeedBattle::update` | 0x003373B8 | existing | |
| `Enemy::AI::initAfterManager` | 0x0033C94C | existing | |
| `Enemy::AI::setMaxSpeedRatio` | 0x0033CA10 | existing | |
| `Enemy::AI::init` | 0x0033CAAC | existing | `m_title_mask`, `m_is_player_kart` |
| `Enemy::AI::awake` | 0x0033CCA8 | existing | |
| `Enemy::AI::startKiller` | 0x0033DCC4 | existing | |
| `Enemy::AIManager::calcAILevel_` | 0x0033E6AC | existing | |
| `Enemy::AIManager::getRandF32` | 0x0033E5B8 | existing | `getU32() * 2^-32 * x` |
| `Enemy::AIProbabilityRace::isLaunchDrift` | 0x0033BC84 | existing | slot 3 of the `AIProbabilityRace` vtable; the random drift-start check |
| `RaceSys::CRaceInfo::updateRaceModeFlag` | 0x00469C90 | existing | ported by call pattern (0.91), not an exact match; its body was read in `eur2` |
| `Enemy::AIEngine::stateReady` | 0x0033D8A0 | existing | |
| `Enemy::AIEngine::stateAfterGoal` / `stateGhostIdle` | 0x0033D9D0 / 0x0033DA28 | existing | |
| `Enemy::AIEngine::statePlayerIdle` | 0x0033DA78 | existing | |
| `Enemy::AIEngine::awake` / `sleep` | 0x0033DCEC / 0x0033DD98 | existing | |
| `Enemy::AIEngine::update` | 0x0033DDC4 | existing | re-route signals |
| `Enemy::AIEngine::onAIFall` | 0x0033DE60 | existing | |
| `Enemy::AIEngine::stateRun` / `stateIdle` / `stateStop` | 0x0033DE70 / 0x0033DF80 / 0x0033DFB0 | existing | |
| `Util::TStateObserverEx<Enemy::AIEngine>::executeState` | 0x005AD538 | existing | runs the current `AIEngine` state; called by `AIEngine::update` |
| `Enemy::AIDriftDrive::calcSteerDrift_` / `calcSteerNormal_` | 0x0032F444 / 0x0032FCB8 | existing | |
| `Enemy::AIItemRace::stateKinoko` / `stateInitKinoko` | 0x0032A918 / 0x0032BD20 | existing | |
| `Enemy::AIItemBattle::stateKinoko` / `stateInitKinoko` | 0x003306C0 / 0x00330A9C | existing | |
| `Enemy::AIItemBase::isPowerfulKinoko_` | 0x0032AF14 | existing | item slot 11 (`eItemSlot::KinokoP`) |
| `Enemy::AIProbabilityBase::isLaunchJumpAction` | 0x0033BC6C | existing | returns 0 |
| `Enemy::AIProbabilityRace::isLaunchMiniTurbo` | 0x0033BD5C | existing | |
| `Enemy::AIBlockLine::stateBlock` | 0x0032E030 | existing | |
| `Enemy::AIObjectManager::init` | 0x0033958C | existing | |
| `Enemy::AIObjectSearcher::isMapObjectToAvoid_` | 0x0033A8E4 | existing | |
| `Enemy::AIBattleSearcher::init` / `AIBattleSearcherCoin::init` | 0x0033A5C4 / 0x0033C2E0 | existing | |
| `Enemy::TargetSearcher<u16>::TargetSearcher` / `setTarget` / `setPoint` | 0x005D02E4 / 0x005CFE2C / 0x005CFBCC | existing | |
| `Enemy::AIAutoSteer::isNeedWait_` | 0x0032C338 | existing | |
| `Enemy::AIAutoSteer::stateGather` | 0x0032C464 | existing | |
| `Enemy::AIAutoSteer::stateZigZag` | 0x0032C5C0 | existing | |
| `Enemy::AIAutoSteer::stateRunAway` | 0x0032C678 | existing | |
| `Enemy::AIAutoSteer::stateInitWait` | 0x0032C884 | existing | |
| `Enemy::AIAutoSteer::isNeedRunAway_` | 0x0032C8D4 | existing | |
| `Enemy::AIAutoSteer::stateExitGather` / `stateInitGather` | 0x0032CCAC / 0x0032CCC8 | existing | |
| `Enemy::AIAutoSteer::calcTargetToAvoid_` | 0x0032CF48 | existing | |
| `Enemy::AIAutoSteer::init` | 0x0032D334 | existing | |
| `Enemy::AIAutoSteer::stateIdle` | 0x0032D884 | existing | the only `Enemy` function whose body differs from `dlp` |
| `Enemy::AIAutoSteer::stateWait` | 0x0032DAF8 | existing | |
| `Enemy::AIStuck::stateInitIdle` | 0x0033CF9C | existing | |
| `Enemy::AIStuck::checkAccident_` | 0x0033CFB4 | existing | |
| `Enemy::AIStuck::stateCheckStuck` | 0x0033D01C | existing | |
| `Enemy::AIStuck::onOutOfBoundsInner` | 0x0033D138 | existing | |
| `Enemy::AIStuck::stateInitBackPathPoint` / `stateBackPathPoint` / `stateExitBackPathPoint` | 0x0033D47C / 0x0033D188 / 0x00334EA0 | existing | |
| `Enemy::AIStuck::stateStartOutOfBounds` | 0x0033D3A0 | existing | |
| `Enemy::AIStuck::init` | 0x0033D4E0 | existing | |
| `Enemy::AIStuck::onAIFall` | 0x0033D5B0 | existing | |
| `Enemy::AIStuck::stateIdle` | 0x0033D63C | existing | |
| `Kart::Director::startJugemRecoverAI` | 0x002FAB14 | existing | |
| `Kart::Director::awakeAI_byKillerStart` / `noticeAI_StartKiller` | 0x002FAB3C / 0x002FAB20 | existing | |
| `Kart::VehicleMove::applyDriveSpeed` | 0x002D5894 | existing | `m_forward_speed_ratio` |
| `Kart::VehicleMove::calcGndCollision` | 0x002D63D0 | existing | `m_airborne_rate` |
| `Kart::VehicleMove::startKiller_Impl` | 0x002D93E4 | existing | |
| `Kart::VehicleMove::calcStarInkThunderPress` / `startInk` / `endInk` / `endStar` | 0x002DCD34 / 0x002DD8C8 / 0x002DD480 / 0x002DD508 | existing | |
| `Kart::VehicleMove::VehicleMove` | 0x002DE3EC | existing | |
| `Kart::VehicleMove::isMiniTurbo_OverLv2` | 0x0050686C | existing | |
| `Kart::VehicleControlAI::calcSmallJumpTimingAI` | 0x002E6CC8 | existing | |
| `Item::KartItem::setItemForce` | 0x002D1DF4 | existing | used to give an item in the tests |
| `Item::KartItemProxy::getStockItem` | 0x005052D8 | existing | the item a kart holds; 3 is a single Mushroom for `AIItemRace::stateKinoko` |
| `RaceSys::IsGoalState` / `IsRaceState` | 0x0045D114 / 0x0045D16C | existing | |
| `RaceSys::LapRankChecker::calc` | 0x004628F0 | existing | rank order |
| `Sequence::GetEnemyLevel` | 0x004825F8 | existing | |
| `Sequence::GetKartGridRank` | 0x004885A4 | existing | |
| `Util::Math::verticalize` | 0x003040E0 | existing | |
| `Object::Coin::kill` | 0x00420570 | existing | |
| `Field::ObjectBase::ObjectBase__sub_object` (constructor) | 0x00343060 | existing | |
| `Field::ObjectBase::checkDetail_KartHitObj` | 0x0034229C | existing | reads `VehicleControlAI::m_collision_switch` |
| `Field::ObjectDirector::createBeforeStructure` | 0x0036CAD4 | existing | fills `m_obj_link_array` |
| `Field::ObjectDirector::findObject` | 0x00509BB0 | existing | |
| `Field::ObjectTcBoard::calcObj` / `ObjectBdBoard::calcObj` | 0x00367128 / 0x003595C8 | existing | |
| `Field::ObjectCrossing::initObj` / `calcObj` / `set_isFlickering` | 0x0036AA90 / 0x0036A61C / 0x0036A384 | existing | |
| `Field::ObjectWiiEscalator::initObj` | 0x003A19F4 | existing | |
| `Field::ObjectWiiEscalator::stateInitUp` / `stateInitDown` | 0x003A0F88 / 0x003A117C | existing | |
| `Field::ObjectFirePillar::calcLavaWaiting` / `calcEruptFinishing` | 0x00388CD4 / 0x00389090 | existing | |
| `Field::ObjectShellFish::calcObj` | 0x003839FC | existing | |
| `Field::ObjectShellFish::calcOpenWaiting` / `start_Yararetoru` | 0x00382CC8 / 0x00382F14 | existing | |
| `Field::ObjectPackunLight::calcObj` | 0x00392AC8 | existing | |
| `Field::ObjectPackunMusic::stateSleep` | 0x00392E3C | existing | |
| `Field::ObjectWiiCar::initObj` / `stateMove` | 0x00354CA8 / 0x00354EC0 | existing | |
| `Field::ObjectGcTable::calcObj` | 0x0035BFF4 | existing | |
| `Field::ObjectMeltIce::calcObj` / `initObj` | 0x003608F8 / 0x00360B28 | existing | |
| `sinit_ObjectCrossingParam` | 0x005665B0 | new | a static initializer that also fills `ObjectCrossing::sParam`; it initializes other globals too (colours, a `nn::nex::DateTime`) |
| `sinit_AirborneFramesParam` | 0x0054DD78 | new | a static initializer that, among other globals, writes `sAirborneFramesParam`; `mk7` does not separate it from `sub_0054bb98` |

### Data

| Name | Address (eur2) | Note |
| --- | --- | --- |
| `Field::ObjectCrossing::sParam` (new name) | 0x0065F660 | +0x4 train distance 1000.0, +0x8 240 frames, +0xC 300 frames; written by `sinit_ObjectCrossingParam` |
| `sAirborneFramesParam` (new name) | 0x00665508 | a parameter block read by `VehicleMove::calcGndCollision`; its word at +0x1D0 is the frame count 20 of `VehicleMove::m_airborne_rate`. Only that word was looked at |
| `sDefaultEnemyPointNormal` (new name) | 0x006BB454 | the default of `MapdataEnemyPoint::m_normal`, written again by `setupNrm` when nothing is hit |
| `AIProbabilityBattle` vtable | 0x0062A154 | loaded by the `AIControlBattle` constructor; slot 6 is `AIProbabilityBase::isLaunchJumpAction` |
| `AIEngine` state table | 0x0062A1EC | loaded by the `AIEngine` constructor; the state functions in state order (init and main function of each) |
| `MpBoard` / `TcBoard` / `GBABoard` vtables | 0x0062F6D8 / 0x0062FF10 / 0x006317B8 | slot 19 is `ObjectTcBoard::calcObj` in all three |

## Findings

### Sources and method

- Code: `eur2`, read with `mk7 dis`, `decomp`, `xref`, `read` and `access`. Every function name is ported from `dlp`; the
  only `Enemy` function whose body differs from `dlp` is `AIAutoSteer::stateIdle` (`mk7 port --changed`). Two throw-away
  scans of a disassembly of the whole code segment found the writers of `ObjectBase::m_ai_signal` and of
  `AIControlBase::m_search_mode` (Finding 8).
- Input notes: `local/llm_input_files/EnemyPointInfo.md` (notes on the `dlp` build) was used as a hint on where to look.
  Every function it names ports to `eur2` as an exact match. Everything stated here was read again in `eur2`; where the
  notes were wrong or incomplete, it is listed in Finding 16.
- Course data: the KMP files of the 40 courses of `eur2` (`rom:/Course/*.szs`, with the four `pat1:/Patch/Course`
  overrides; 34 race and 6 battle courses) were parsed with a throw-away script (Findings 2, 7, 8, 13 and 14). The parser
  is not part of the tooling; [How to verify](REVIEW.md#how-to-verify) gives the layout it needs.
- Game: `eur2` in Azahar, driven by `mk7 emu` and throw-away scripts over `mk7re.dynamic`; the runs are listed with each
  measurement and in the [Review](REVIEW.md#review).

In the code, race mode is `IsRaceTypeThinkAsRace()` (the race flag of `CRaceInfo`, or rule mode Award) and battle mode is
`IsRaceTypeThinkAsBattle()` (rule mode Battle or DemoBattle). In part 2 a "point" is an ENPT entry or, in race mode, an
entry of the re-sampled list (Finding 3), and a "path" an ENPH entry. Distances are world units, times are frames.

### 1. How the entries become a route

1. `AIPathManager::init` calls `MapdataEnemyPoint::setup(index, pathAccessor)` for every KMP point in every mode
   (`setup(uVar6,uVar12,uVar5)` loop at the top of the function).
2. Race mode (`IsRaceTypeThinkAsRace() != 0`): it allocates a `PathSmoother` (the class that builds the denser race
   route, Finding 3), calls `init(150.0f, 75.0f)` (`vldr s1, = 75f`,
   `vldr s0, = 150f`), wraps the result in two accessors stored in the manager, and calls `setup` and `setupNrm`
   again on the **new** points. Then `FindSectorForEnemyPt` for each new point, the start point, and
   `PathSmoother::calcPathCosineAndAxis`. Every runtime index in race mode refers to the re-sampled list.
3. Other modes: it allocates a `PathAnalyzer` (the graph of nodes and edges that battle CPUs score at a junction,
   Finding 8), fills `m_start_points[i]` with `findNearEnemyPoint(start position i, option 0)` for
   every KTPT entry, and calls `setupNrm` on the KMP points. No corner value, no side axis, no sector.
4. All modes, on the race accessors in race mode and on the KMP accessors otherwise (chosen at the top of the function:
   `IsRaceTypeThinkAsRace() ? m_race_point_accessor : Field::GetEnemyPointAccessor()`, and `m_race_path_accessor` or
   `Field::GetEnemyPathAccessor()` for the paths):
   `setupPathDepth`, `setupPathPointLink`, `m_path_index` of every point, and `m_nearest_enemy_point` of every
   respawn point (`MapdataJugemPoint`, a JGPT entry; `findNearEnemyPoint(position, option 0)`).

### 2. Links between points, and the link end flags

`MapdataEnemyPoint::setup`. `start = m_start_point + m_start_adjust`, `last = start + m_point_num + m_count_adjust - 1`.

Counting pass, for the path that contains the point:

- first point of the path: `m_prev_count` += one per entry of `m_previous_points` that is not 0xFFFF, **only if the path has more
  than one point** (`1 < (int)(m_point_num + m_count_adjust)`). Any other point: `m_prev_count = 1`.
- last point: `m_next_count` += one per valid entry of `m_next_points`. Any other point: `m_next_count = 1`.

Then the mode is tested: `bVar16 = rule mode == 3 || rule mode == 7` (`*(int *)(raceInfo + 0x168)`, `CRaceInfo::m_race_mode.m_rule_mode`, Battle and DemoBattle).

Race and award:

- first point: `m_prev_points[k] = last point of previous path k`. Other points: `m_prev_points[0] = index - 1`.
- last point: for next path `k` (counting valid entries), `m_next_points[k]` is the **first** point of that path, or its **last**
  point when `m_link_end_flags & (1 << (16 + k))` (`if ((*(uint *)(*piVar2 + 0x44) & 1 << (uVar7 + 0x10 & 0xff)) == 0)`, +0x44 being `m_link_end_flags`).
  Other points: `m_next_points[0] = index + 1`.

Battle:

- `m_next_count += m_prev_count; m_prev_count = 0;` and `m_prev_points` is not allocated.
- first point: for previous path `k`, a next link to the **last** point of that path, or to its **first** point when
  `m_link_end_flags & (1 << k)` (`if ((*(uint *)(iVar4 + 0x44) & 1 << (uVar9 & 0xff)) == 0)`). Other points: a next link to
  `index - 1`.
- then the same next-path code as in race, and `index + 1` for points that are not last.

So in battle every point is linked to both neighbours, and a path end is linked to one end of every path listed in either array.
Whether a path is listed as "previous" or "next" only decides which end of **this** path the junction is at; the flag bit decides
which end of the **other** path.

Checked against the data: for three of the six battle courses, the bit agrees with "the nearer end of the linked path" in 288 of 288
links (`Bagb_BattleCourse1`), 134 of 134 (`Bctr_HoneyStage`) and 212 of 220 (`Bctr_IceRink`; the 8 others are self-links and
near-equal distances). No race course has a non-zero `m_link_end_flags`.

Limits that follow from the code:

- The loops that fill the links run over the first `count` array slots, where `count` is the number of valid entries. Valid
  entries must therefore be packed at the start of `m_previous_points` / `m_next_points`.
- A single-point path gets no links from its `m_previous_points` in any mode.
- The flag is read from the path being set up, so both paths of a junction must describe it consistently.

How to fill in these bits for a course: [Link end flags](#link-end-flags) in the overview.

### 3. Race only: re-sampling

`PathSmoother::init(max_spacing = 150, handle_length = 75)`, for every KMP point with exactly one previous and one next point
(the two count tests at the top of its loop):

```
dir        = (next.pos - prev.pos) * (75 / |next.pos - prev.pos|)
handle_out = pos + dir                                                  ; stored at +0xC of the point's control entry
handle_in  = pos - dir                                                  ; stored at +0x0 of the point's control entry
if (next.m_next_count != 1) sub_count = -1
else sub_count = floor(|pos - prev.pos| / 150); step = 1 / (sub_count + 1)
```

Every other point gets `sub_count = -1`. The number of inserted points of the segment `i -> i+1` is thus computed from the length
of the segment **before** point `i`.

`PathSmoother::setupBezier_(path)` copies each point of the path, and after point `i` with `sub_count = n > 0` it
inserts `n` points at `t = k * step` on the cubic Bézier through `pos_i`, `handle_out_i`, `handle_in_{i+1}`, `pos_{i+1}`
(weights `(1-t)^3`, `3t(1-t)^2`, `3t^2(1-t)`, `t^3`). An inserted point copies the whole 0x18-byte entry of point `i` when
`t < 0.5` and of point `i + 1` otherwise (`cmp r0, #0x3f000000`, `bge` to the branch that uses `r6 + 1`), then overwrites the position. The 0x48-byte ENPH entry is copied as it is (`__rt_memcpy_w`, 0x48) and only its
start and count are rewritten, so path indices, links and `m_link_end_flags` are preserved.

Order: path 0 first, then recursively each entry of `m_next_points` until the first entry that is 0 or 0xFFFF
(`cmp r1, r6` / `cmpne r1, #0`), then every path not reached yet.

Consequences for authors:

- Each ENPT setting covers the stretch from halfway back along the previous segment to halfway along the next one.
- Never smoothed (straight, no inserted points): the link between two paths, the segment into a point with several next points,
  and the segment out of a point with several previous points.

### 4. Race only: corner value and side axis

`PathSmoother::calcPointCosineAndAxis_(prev, cur, next)`, called for re-sampled points with one previous and one
next point:

```
in = normalize(cur - prev); out = normalize(next - cur)
cur.m_side_axis = cross(out, cur.m_normal); cur.m_internal_flags |= 1
in.y = out.y = 0
c = dot(in, out) / (|in| * |out|)
if (dot(cross(in, cur.m_normal), out) < 0) c = -c
cur.m_corner = c
```

`isDriftCornerAngle(c)` is `|c| <= 0.998` and `isGoInCornerAngle(c)` is `|c| <= 0.98` (constants 0.998 and 0.98 loaded by the two functions).
Points at junctions keep `m_corner = 1.0` (constant of `constructLocal`), and so do all points in battle.

`setupNrm`: `m_width = scale * 50` (constant 50 loaded by `setupNrm`), and `m_normal` from a collision sphere check at the
point position, radius 25 (`vldr s16, = 25f`); if nothing is hit, the constructor's default (`sDefaultEnemyPointNormal`) is
written again.

### 5. Reaching a point

`AIPathHandler` is the per-CPU route logic; its `update` runs every frame and decides when the CPU has reached its target
point.

#### The reach test

`AIPathPoint` is the per-CPU cursor on the route: it holds the point just reached, the target point and the point after
it, and `m_target_trans`, the aim point (the target point moved sideways to the CPU's lane, Finding 6).
`AIPathHandler::m_current_param` holds the settings of the point just reached and `m_next_param` those of the target point
([below](#the-point-just-reached-and-the-target-point)).

```
d = m_target_trans - kartPos;  m_target_dist_sq = |d|^2
r2 = (m_current_param->m_flags & 4) ? 19600.0f : m_reach_radius_sq        ; constant 19600 of AIPathHandler::update
if (|d|^2 < r2 && m_reach_cos_min * |d| < |dot(d, kart forward)|)  -> advance
if (!m_is_battle && isPassedThroughPathPoint_())                   -> advance
```

`AIPathHandler::init` takes the values from the control class:

| | reach radius | `m_reach_cos_min` | `m_pass_mode` after relocation | `m_corner_line_shift` | `m_shortcut_mode` |
| --- | --- | --- | --- | --- | --- |
| `AIControlRace::initAfterManager` | 280 (78400) | 0 | 2 | +0.15 / -0.4 / -0.7 for AI level 0 / 1 / 2 | 0 / 1 / 2 |
| `AIControlAward::initAfterManager` | 200 (40000) | 0 | 2 | 0 | 0 |
| `AIControlBattle::initAfterManager` | 100 (10000) | 0.1 | 0 | 0 | 0 |

#### The reach radius changes

`m_reach_radius_sq` does not keep this value. `goNextPath_` first copies `m_default_reach_radius_sq` into it (and zeroes
`AIPathPoint::m_move_back_rate`), so every advance restores the default. Two functions lower it until the next advance:
`AIPathHandler::startKiller` (called by `AIControlRace::startKiller`) writes 10000 (100 units), and
`initMoveBackTargetToPreviousPath` (called by `AIStuck::stateInitBackPathPoint`) writes 2500 (50 units);
`finishMoveBackTargetToPreviousPath` (called twice by `AIControlRace::update`) restores the default. Measured in game: a
CPU that got a Bullet Bill had 10000 for 19 frames, back to 78400 on the frame it advanced.

`finishMoveBackTargetToPreviousPath` is also reached from `AIStuck::stateExitBackPathPoint`, whose two instructions fall
through into it (Finding 11).

#### The point just reached and the target point

`goNextPath_` then, on a normal advance: `m_pass_mode = 1`, `m_current_param` = settings of the old target,
`AI::m_force_base_speed = (m_current_param->m_flags & 0x80) != 0`, `AIPathPoint::goNextPoint`, `m_next_param` = settings of
the new target, `m_advanced_this_frame = 1`. On a relocation (`GoNextInfo::m_is_relocate`: the CPU is put on
`GoNextInfo::m_base_point_index` instead of moving on to the next point, see [Height re-route](#height-re-route) and
Finding 12) `m_current_param` is zeroed instead and the lane is reset to 0.

So `m_current_param` is "the point just reached" and `m_next_param` is "the target point". In race the CPU reaches a point
while still up to 280 units away from it, so both take effect well before the kart is physically there.

#### The pass-through plane

`AIPathHandler::isPassedThroughPathPoint_(kartPos)`, read from the disassembly (the decompiler output is truncated). With
`T = AIPathPoint::m_target_trans` (the aim point, lane offset included), `P`, `C`, `N` the positions of `m_prev_point`,
`m_target_point` and `m_next_point`:

```
out = normalize(N - C)
switch (m_pass_mode):
  0: return false
  1: n = out
     if (m_prev_point->m_index != m_target_point->m_index)       ; ldr [r6,#0x1c] / ldr [r7,#0x1c] / cmp
        n = out + normalize(C - P); if (n == 0) n = normalize(C - P)
     return n != 0 && dot(n, kartPos - T) >= 0
  2: n = out
     return n != 0 && dot(n, kartPos - T) >= 0
```

The plane goes through the aim point, so it moves with the CPU's lane. Its normal is the sum of the unit vectors of the
incoming and outgoing segments, i.e. the plane bisects the turn at the point (mode 1, set by every normal advance in
`goNextPath_`); after a relocation the mode is `m_relocate_pass_mode` (2 in race and award), and the plane is square to the
outgoing segment. The vectors are 3D and the plane is unbounded. For a turn close to 180 degrees the normal is short and
points sideways, so the plane lies almost along the road. Battle never calls the function (`!m_is_battle` above), and
`m_relocate_pass_mode` 0 would switch the test off.

#### Height re-route

Same function, all modes: when no advance happened for more than 20 frames (`m_check_timer`), and the kart is in Bullet
Bill, gliding, has `VehicleMove::m_airborne_rate >= 1.0` (airborne for 20 frames, see below), **or
`m_current_param->m_flags & 0x02`**, and `d.y^2 > 0.3 * (d.x^2 + d.z^2)` (constant 0.3 of `AIPathHandler::update`), it
calls `AIEngine::onAIFall()` and then advances.

`AIControlRace::onAIFall` and `AIControlBattle::onAIFall` both search the nearest point with `findNearEnemyPoint` and
relocate only when its `m_path_index` differs from the target's (the race version also relocates when
`AI::m_is_player_kart` is set: `AI::init` sets it when `CKartInfo::m_player_type` of the kart is 0, 2, 3 or 4, Master,
User, Ghost or Master_Replay, i.e. a kart that is not a CPU and that the AI drives, such as a player's kart after the
finish). Each relocation also calls `AIStuck::onAIFall` (Finding 11). The race version then walks `m_next_points[0]` until
a point is more than 180 units away (constant 32400 of `AIControlRace::onAIFall`) and targets that one; the battle version
targets the nearest point itself. The height re-route is one of six callers of `onAIFall`; the others (a stuck CPU, a
player's Bullet Bill, ...) are in Finding 12.

#### `VehicleMove::m_airborne_rate`

It is updated at the end of `VehicleMove::calcGndCollision`: `step = 1 / N` with `N` read as an integer from
`sAirborneFramesParam` +0x1D0; `VehicleMove::m_air_rate = min(m_air_frames * step, 1)`; then `m_airborne_rate += step`
(capped at 1) when that value is above 0, i.e. while the kart is in the air, and `m_airborne_rate -= step` (floored at 0)
otherwise. `N` is written by `sinit_AirborneFramesParam` (`add r4, r1, #0x1d0` / `stm r4, {r2, r3}`, with `r1` the address
of `sAirborneFramesParam`, a base address plus 0x400, and `r2 = 0x14` loaded earlier still), so
`N = 20`. The rate therefore reaches 1.0 after 20 frames in the air, and drops back to 0 after 20 frames on the ground.
Measured in game over 48000 kart-frames: it only ever changed by exactly +1/20 or -1/20, except at a Lakitu respawn, which
reset it from 1.0 to 0 at once.

#### Advances measured in game

From the dynamic fact check ([Fact check, second round](REVIEW.md#fact-check-second-round-in-game)): 6000 race frames of 8 CPUs had
2584 advances, 2573 of them within the reach radius (280, or 140 when the point just reached has flag 0x04) and 11 farther
(the pass-through plane; none in battle). Measured right after an advance, the distance to the new target was 213 to 493
units for 5 % to 95 % of the advances, median 375, and up to about 900 on long segments that get no inserted points. After
each advance `m_current_param` held the settings of the old target and `m_next_param` those of the new one (the one
exception was a relocation). In battle (4000 frames, 497 advances) all were within about 100 units.

### 6. Per-field detail

#### `scale`

Race: `AIPathPoint::calcNextTargetTrans` sets `m_target_trans = pos + clamp(rate, -0.85, 0.85) * m_width * side axis` (the
constants -0.85 and 0.85 are loaded by the function). `rate` is `m_offset_rate`, set at race start by
`AIControlRace::initAfterManager` from the grid position: `0.75 * (0.375 * c - 0.125) + side + rand(-0.15, 0.15)`,
`c = ((grid rank - 1) % 4) - 2`, `side = 0.2`, both negated when byte 1 of the stage info is 0. That gives lanes from about
61 % of the half-width on one side to about 54 % on the other, or from 73 % to 42 % when STGI byte 1 is 0 (22 of the 34
race KMPs). Measured on Wuhu Loop (STGI byte 1 = 0), the `m_offset_rate` of each of the 8 CPUs was in the range the formula
gives for its grid rank (`Sequence::GetKartGridRank`, called in game). CPUs with `AI::m_title_mask & 0x1100` and karts in
Bullet Bill (`GoNextInfo::m_is_killer`) aim at the centre.

The lane also moves later: `AIBlockLine::stateBlock` and `AIAutoSteer::calcTargetToAvoid_` reach
`AIPathPoint::addOffsetRate` through the `AIPathHandler` wrappers (blocking and avoiding), `goNextPoint` writes 0 to
`m_offset_rate` in its `m_is_killer` branch (Bullet Bill), and `goNextPath_` resets the lane on a relocation (Finding 5).

Lanes beyond 50 % drift back. `goNextPoint` calls `AIPathPoint::calcPointOffsetDistance_` on every advance outside its
`m_is_killer` branch (its only caller). The function draws `noise = getRandF32(2 * r) - r`, uniform in `[-r, r)`
(`AIManager::getRandF32(x)` is `getU32() * 2^-32 * x`), with `r = 0.01`, or `0.03` when `AI::m_title_mask & 0x10`
(`vldr s16, = 0.01f` / `tst r0, #0x10` / `vldrne s16, = 0.03f`). When `m_offset_rate > 0.5` and `noise > 0` it subtracts
the noise; when `m_offset_rate < -0.5` and `noise < 0` it adds `|noise|` (the two tests compare the float bits with
0x3F000000 and 0xBF000000); a lane within ±0.5 is left as it is. So a lane beyond 50 % moves toward the centre on half of
the advances, by 0.005 on average (0.015 with title bit 0x10), until it is within 50 %. The function then writes
`m_width` and `m_offset = clamp(m_offset_rate * m_width, ±0.85 * m_width)`.

Battle: `AIPathPointBattle::calcNextTargetTrans` clamps `m_offset` to `0.85 * m_width` and adds it to X and to Z of the
position. The lane starts at 0 (`AIControlBattle::initAfterManager` passes 0). Award: `AIPathPointAward::calcNextTargetTrans`
uses the position unchanged.

Battle, junction scores: `PathAnalyzer::PathAnalyzer` stores `m_data->scale * 50` (constant 50 loaded by the constructor)
as the width of each node. Its only reader is `TargetSearcher<u16>::setTarget(target, pos, value)`, which places a target
(item box, coin, kart) on the graph before `setPoint` spreads its value: for every edge `A -> B` with `pos` between the two
end planes (`dot(dir, pos - A) >= 0` and `dot(-dir, pos - B) >= 0`), `t = min(dot(dir, pos - A) / length, 1)` and the
allowed distance is `(wA + (wB - wA) * t) * m_width_scale`; the target is registered on the edge when its distance from the
edge line is within it, and the nearest such edge becomes its main edge. Then for every node with
`|pos - node| <= w * m_width_scale` the target is registered on all edges of the node, and a node with more than one
neighbour that is nearer than the best edge gives its first edge as the main edge. When no edge is found `setTarget`
returns 0 and the target is not set. `m_width_scale` is the second float argument of the constructor, 1.0 at all four call
sites (`RedTeamSearcher`, `BlueTeamSearcher`, `ItemSearcher` in `AIBattleSearcher::init`; `CoinSearcher` in
`AIBattleSearcherCoin::init`).

#### `mushroom_setting`

`PointParam::isUseKinoko()` is `m_mushroom_setting == 0`. `AIItemRace::stateKinoko` and `AIItemBattle::stateKinoko` both
test it on `m_current_param`, and use the item when the timer has run out, or when the CPU advanced this frame and holds
exactly a single Mushroom (`Item::KartItemProxy::getStockItem() == 3`). Timer: `rand(180)` in race, `rand(50)` in battle.

Two more branches of `AIItemRace::stateKinoko`: CPUs with title bit 0x40 or 0x80 ignore `mushroom_setting` and use the
Mushroom while gliding or in water, and the timer is held at 10 or more while `m_next_point` has no side axis
(`m_internal_flags & 1` clear, i.e. junction points).

While the kart is drifting (`VehicleMove::m_drift_state & 0x18`), `AIItemRace::stateKinoko` counts the timer down and
then skips every use test, the title branches included, so a race CPU never uses a Mushroom while drifting. Battle CPUs
do not drift (see `drift_setting`).

Value 1 is read only in `selectNextPointHandleIndexWithShortcut_` (race): a branch whose first point has
`mushroom_setting == 1` goes to the shortcut group, which is chosen only when `m_do_select_shortcut` is set
(Finding 8). `AIItemRace::stateInitKinoko` sets that from `m_shortcut_mode` (never / 50 % / always for AI level 0 / 1 / 2)
unless the item is a "powerful" mushroom (`AIItemBase::isPowerfulKinoko_`, item slot 11, which `template/` calls
`eItemSlot::KinokoP`, the Golden Mushroom) or `m_title_mask & 0xC0`. `AIItemBattle::stateInitKinoko` always clears it.

#### `drift_setting`

Only `AIControlBase::setBasicDriveInfo_` reads it, through `isTargetToStartDrift` (on `m_next_param`: value is neither 1
nor 2, and the target is a drift corner) and `isTimeToEndDrift` (on `m_current_param`, on the frame a point is reached):

```
isTimeToEndDrift = drift_setting != 0 &&
                   (drift_setting == 1 || drift_setting == 2 ||
                    current.m_corner * next.m_corner < 0 || !isDriftCornerAngle(next.m_corner))
m_allow_miniturbo = !end || (drift_setting != 2 && (m_title_mask & 0x20 || probability->isLaunchMiniTurbo()))
```

A drift also only starts when `m_target_dist_sq < 160000` and `!(m_title_mask & 0x1100)`, and then either
`m_title_mask & 0x20` is set or the probability class's `isLaunchDrift(true)` (slot 3 of the `AIProbabilityRace` vtable)
returns 1; only then is the drift requested. `AIProbabilityRace::isLaunchDrift` draws `rand(100)` against the AI's
probability table once, then returns 0 until it is called with `false`, which `setBasicDriveInfo_` does on every frame
the other conditions fail. So title bit 0x20 skips the random drift-start check. `AIControlBattle` overrides
`setBasicDriveInfo_` with a version that only copies the target, so none of this runs in battle. Measured in game (dynamic
fact check): all 41 drift starts happened with a target whose `drift_setting` was not 1 or 2, `|m_corner| <= 0.998` and the
target within 400 units; 37 of 68 drift ends came right after reaching a point with 1 or 2.

#### Flags 0x01 and 0x04

Cornering. `AIPathPoint::calcNextTargetTrans`: if the kart is drifting (`VehicleMove::m_drift_state & 0x18`) and the target
has flag 0x04, flag 0x01, or `isGoInCornerAngle(m_corner)`, the lane used for this target is shifted by
`m_corner_line_shift`, toward the side given by the sign of `m_corner`, and `m_offset_rate` creeps by `rand(0, 0.01)`. Not
reached in battle or award (overridden function), and the shift is 0 there anyway. The distance part of flag 0x04 is the
reach test of Finding 5.

#### Flag 0x08

`AIDriftDrive::calcSteerNormal_`: `if (not in Bullet Bill && !(target flags & 8))` guards the block that presses the hop
button (`m_buttons |= 0x4000`) at a trick chance. For a CPU without title mask that block asks
`probability->isLaunchJumpAction()`. The battle probability class uses `AIProbabilityBase::isLaunchJumpAction`, which
returns 0 (slot 6 of the `AIProbabilityBattle` vtable), so in battle the block never hops and the flag changes nothing.

The block is only reached while the kart is not gliding (status bit 0x80 tested first). It then branches on
`AI::m_title_mask` (`tst r1, #0x1100` / `tst r1, #4` / `tst r1, #0x840`), with `VehicleControlAI::calcSmallJumpTimingAI()`
as the trick chance and two counters of `AIDriftDrive`, `m_hop_frames` (+1 on each frame the block runs without a
hop) and `m_hop_interval`:

- `& 0x1100`: the block ends at once; these CPUs never hop here.
- `& 0x4`: hop when `m_hop_frames > m_hop_interval` or at a trick chance; after a hop
  `m_hop_interval = 120 + rand(180)` and `m_hop_frames = 0`. So a hop at every trick chance, and one more whenever
  120 to 299 frames of this block have passed since the last.
- `& 0x840`: hop at every trick chance.
- otherwise: at a trick chance once `m_hop_frames > 45`, `m_hop_frames = 0` and the hop only when
  `probability->isLaunchJumpAction()` returns 1.

#### Flag 0x10

`AIDriftDrive::calcSteerDrift_`: with the flag on the target, the alignment below which a drift is abandoned is 0.2 instead
of 0.4 and a steering factor of 0.35 is applied (constants loaded by the function). Without the flag, `calcSteerDrift_` also
gives up an aligned drift after 120 frames or once `VehicleMove::isMiniTurbo_OverLv2()` is true; the flag skips that test.

#### Flags 0x20 and 0x40

`AIControlRace::update`, Bullet Bill branch, both on `m_current_param`. 0x20: the height lock ramps by 0.0025 per frame up
to 0.7 and is written as the strength of the height pull; without the flag the strength written is 0. 0x40: in the ending
phase the timer does not advance; after 420 held frames it is forced to 61. A Bullet Bill that lasted more than 960 frames
ends regardless.

The held frames are counted in `AIControlRace::m_killer_hold_frames` (u16). In the ending phase (`ldrb r0, [r4, #0x90]` /
`beq` to the other phase), after the `cmp r0, #0x3c` / `bls` that ends the Bullet Bill once the timer is above 60:
`tst r0, #0x40` on `m_current_param->m_flags`; with the flag the counter is incremented (`uxth`), and above 420
(`cmp r0, #0x1a4` / `movhi r0, #0x3d`) the timer is set to 61, otherwise left as it is; without the flag the counter is
zeroed (`strh r7, [r4, #0x7c]`) and the timer incremented. The ending check comes first, so the Bullet Bill ends on the
next frame. The counter is also zeroed on every frame with `AIPathHandler::m_advanced_this_frame` (near the top of
`AIControlRace::update`, before the Bullet Bill test), by `AIControlRace::startKiller`, and when the timer starts the
ending phase. So the Bullet Bill ends after 421 frames in a row (7 seconds) in the ending phase on points with flag 0x40
without reaching a new point. Not measured in game.

#### Flag 0x80

`AI::setMaxSpeedRatio`: when not backing up and not in Bullet Bill, `m_force_base_speed` selects `m_base_speed_ratio` (0.8 /
0.9 / 1.0 for AI level 0 / 1 / 2, `AI::initAfterManager`) instead of the ratio asked by the speed code. The same branch is
also taken without the flag when `VehicleMove::m_boost_frames > 0`, or when `VehicleMove::m_air_rate`
(`min(m_air_frames / 20, 1)`, Finding 5) is at least 1.0 and the kart is not gliding (status bit 0x80, `wing_open`); the
ratio is written to `VehicleControlAI::m_max_speed_ratio`. Measured in game: `AI::m_force_base_speed` equalled flag 0x80 of
`m_current_param` on every frame of every CPU (48000 kart-frames in a race, 32000 in a battle). Battle adds two readers:

- `AISpeedBattle::update`: `if (m_ai->m_force_base_speed) AIPathPoint::resetNextTargetTrans(...)`, which zeroes the lane
  and aims at the point centre. Measured in a battle: the target was exactly the point centre on all 3034 frames with the
  flag.
- `AIControlBattle::update`: `if (m_ai->m_force_base_speed && VehicleControlAI::calcSmallJumpTimingAI()) buttons |= 0x4000`.

In the original battle courses this is the only non-zero ENPT setting besides the position and `scale` (4 points in
`Bagb_BattleCourse1`, 12 in `Bctr_WuhuIsland3`; Finding 14).

#### AI level

The AI level comes from `AIManager::calcAILevel_`. Without the multiplayer bit
(`CRaceInfo::m_race_mode_flag.multiplayer_or_online`): in rule mode 3 or 7 it switches on `Sequence::GetEnemyLevel()`,
1 -> level 0, 2 -> level 1, anything else -> level 2; otherwise on the engine class (`CRaceInfo::m_engine_level`).
`Sequence::GetEnemyLevel` returns `MenuData::m_ai_level`, which the CPU setting of the battle settings page writes as 1
easy, 2 normal, 3 hard (measured in game on 2026-10-04, on the battle settings page). With the multiplayer bit,
battle is always level 2. Measured in a hard battle: `AI::m_base_speed_ratio` was 1.0.

Race with the multiplayer bit (`ldrne r1, [r0, #0x164]` / `cmpne r1, #2` / `beq` to the level-2 store): level 2 when
`CRaceInfo::m_race_mode.m_play_mode` is 2 (`ERacePlayMode::Online`), otherwise the engine class as above. The bit is set
by `RaceSys::CRaceInfo::updateRaceModeFlag` when the play mode is 1 (`MultiPlayer`) or 2 (`Online`). Engine class 0 / 1
(`EEngineLevel::_50cc` / `_100cc`) gives level 0 / 1, any other value level 2. So: 50cc, 100cc and 150cc give levels 0,
1 and 2 in single-player and local multiplayer races; online races always use level 2.

#### `path_find_options`

- `findNearEnemyPoint(pos, accessor, option)`: option 1 skips points with -1, option 2 skips points with -2.
  `AIControlRace::onAIFall` uses option 1 when `VehicleBase::m_is_fake_goal` is set, option 2 in Bullet Bill, else 0.
  `AIControlRace::startKiller` uses option 2 and sets the ending flag at once when nothing is found; the index found is not
  used otherwise (`if (iVar4 < 0) *(param_1 + 0x90) = 1`), so `startKiller` itself does not relocate the kart. A CPU keeps
  its target; a player's kart is relocated before that, by `AIEngine::awake` (Finding 12), with option 2 as well. Battle
  only uses option 0.
- `setupPathPointLink`: `m_find_type` of the path becomes -3 or -4 when any of its points has that value. Read only in
  `selectNextPointHandleIndexWithShortcut_` (race): a CPU with `m_title_mask & 0x44` takes a -3 branch at once, one with
  `m_title_mask & 0x80` a -4 branch.
- `FindSectorForEnemyPt` stores the sector only `if (*(short *)(data + 0x14) == 0)` (+0x14 being `path_find_options`);
  other points keep 0xFF and are invisible to the sector-based searches (race start point).
- Award mode, `AIPathManager::init`: the first point of each path with value `N != 0` gives
  `m_start_points[N - 1] = that point` and sets `m_internal_flags |= 0xA` on the whole path. `Gctr_WinningRun` uses 1, 2, 3.
  The paths are visited in order, so a later path with the same value overwrites an earlier one: measured in the winning
  run, paths 0 and 4 both start with value 1 and `m_start_points[0]` was the first point of path 4.

#### `max_search_y_offset`

`findNearEnemyPoint` collects up to 128 points within 500 units in XZ (constant 250000), then keeps the nearest in 3D among
those whose height difference passes: value < 0: at most 75 (constant 75); value 0: no limit; value > 0: at most the value.
Award: `AIPathPointAward::calcNextTargetTrans` also writes `value == 1` to `VehicleControlAI::m_award_flag`.

#### `MapdataEnemyPoint::m_direction`

Its only reader is `AIObjectSearcher::isMapObjectToAvoid_`, in the branch that runs when `AIObjectSearcher::m_is_race` is
set (`AIObjectManager::init` writes `IsRaceTypeThinkAsRace()` there) and no object to avoid was found: for every item box
(ID 4 or 0x143, `ItemBoxTag`, and `m_settings[7] != 1`) collected from the box collision, it takes the nearest point
(`FindNearestEnemyPtHndl`); when that point is on the path of the CPU's target, or on the single next path of that path, it
computes `|verticalize(box - kart, m_direction)| - AIPathPoint::m_offset` and keeps the box with the smallest value as the
one to drive to. `Util::Math::verticalize(out, v, axis)` is `v - axis * dot(v, axis)`. With the measured value (0, 0, 1)
the axis removed is the world Z axis, whatever the direction of the route.

### 7. Start points and respawns

- Race: on course IDs 8 and 9 `m_start_points[0] = 0`. Otherwise, when not award and checkpoints exist,
  `m_start_points[0] = FindNearestEnemyPtHndlFromSector(start position 0, ..., m_race_point_accessor)`, so the start
  point can be an inserted point. Entry 0 is copied to the seven others.
- Battle: `m_start_points[i] = findNearEnemyPoint(start position i, option 0)`; `AIControlBase::initAfterManager` picks the
  entry of the CPU's order index (entry 0 in rule mode 1, Time Trials).
- Respawn, `AIPathHandler::onOutOfBoundsInner`: relocation to `MapdataJugemPoint::m_nearest_enemy_point` when it is >= 0
  (`strge r1, [sp, #0x38]`, into `GoNextInfo::m_base_point_index`). Otherwise `FindNearestEnemyPtHndl` is called but **its
  result is not stored** (its `bl` is followed directly by the `goNextPath_` call), so the relocation goes to point index 0.
  In race mode index 0 of the re-sampled list is the copy of the first point of path 0 (`setupBezier_` starts with path 0,
  Finding 3). In all 39 KMP files of the RomFS that have enemy paths, path 0 starts at enemy point 0. Measured in game
  (second fact check, Wuhu Loop): with every `m_nearest_enemy_point` set to -1, a CPU that was made to fall headed to
  point 0.
- `m_nearest_enemy_point` is searched on `m_race_point_accessor` in race mode (Finding 1, step 4), so in a race an
  inserted point within 500 units is enough to avoid the fallback.
- Whether that fallback happens on the original courses: a re-implementation of `findNearEnemyPoint` (500 units in XZ, the
  `max_search_y_offset` filter, option 0) over the KMP points of all 40 courses finds a point for every respawn point except
  point 1 of `Gctr_WinningRun`, the award cutscene, in which no kart falls. The race accessor holds the KMP points plus the
  inserted ones (Finding 3), so it can only find more, never fewer, as long as fewer than 128 points lie within 500 units
  (`findNearEnemyPoint` keeps the first 128 by index). An estimate of the re-sampled lists (the counts of Finding 3, on
  straight lines instead of the Bézier, within each path) gives at most 103 points within 500 units of a respawn point
  (point 1 of `Gwii_CoconutMall`; 56 of them KMP points). The fallback is therefore reachable only on custom courses.

### 8. Junction choice

Race, `selectNextPointHandleIndexWithShortcut_`, for the next points of `GoNextInfo::m_base_point_index`, only when
`m_search_mode < 2` (`AIControlRace::init` sets 1):

1. A branch equal to `m_target_point_index` is excluded when `m_do_not_select_backward`.
2. Object check, always for CPUs with a title mask, else with probability `m_obj_check_rate` %: for each object in the
   `m_obj_link_array` of the branch's path, `ObjectBase::m_ai_signal == 0` excludes the branch; an object with ID 0x180, 0x1A9
   or 0x1AA (`TcBoard`, `GbaBoard`, `MpBoard`) makes a CPU with `m_title_mask & 0x44` take the branch at once.
3. First point with `mushroom_setting == 1`: shortcut group. Else the title test on `m_find_type`, then the normal group.
4. Random pick in the shortcut group when it is not empty and `m_do_select_shortcut`, else in the normal group; branch 0 when
   the picked group is empty.

Objects are linked in `setupObjLink_`, from `ObjectDirector::m_obj_link_array`, skipping object ID 0x13E: `m_settings[7] == 0`
links the object to path `m_enemy_route`; `m_settings[7] == 1` links it to every path that lists `m_enemy_route` among its next
paths. Original uses: IDs 0x1A9, 0x14, 0xD5, 0x1A8, 0x1AA, 0x180, 0x71, 0x6E, 0x15B.

`ObjectDirector::m_obj_link_array` is filled at the end of `ObjectDirector::createBeforeStructure`: every object of
`m_objects` whose `MapdataGeoObjData::m_enemy_route` (read as signed, `ldrsh r2, [r2, #0x3c]` / `blt`) is 0 or more is
appended. In the GOBJ data of the 40 original courses that is `GbaBoard` (GBA Bowser Castle 1), `BcFirePillar` x4 (Bowser's
Castle), `ShellFish` x4 (Cheep Cheep Lagoon), `packunLight` x2 and `MpBoard` x2 (Music Park), `TcBoard` (Toad Circuit),
`GcTable` (GCN Daisy Cruiser), `N64Crossing` x2 (N64 Kalimari Desert), `WiiCarA` and `WiiEscalator` x4 (Wii Coconut Mall).
In game the array of Kalimari Desert also held a `CmnStartGrid` (0x148), which the director creates itself
(`m_cmn_start_grid_sdata`); Wii Koopa Cape and GCN Dino Dino Jungle held only that one.

`ObjectBase::m_ai_signal` (renamed from `m_cpu_should_avoid_object`, which says the opposite of what the value does in the
junction choice) is 0 after the constructor (`ObjectBase::ObjectBase__sub_object`: `mov r6, #0` / `strb r6, [r4, #0x78]`).
A scan of the whole `eur2` code for byte stores at the offset of `m_ai_signal` (+0x78) in object functions finds these
writers:

| Object | Writer | Value |
| --- | --- | --- |
| `TcBoard`, `GbaBoard`, `MpBoard` | `ObjectTcBoard::calcObj`, slot 19 of the `MpBoard`, `TcBoard` and `GBABoard` vtables | `state == 2`: the board has finished moving and holds; `ObjectBdBoard::calcObj` calls it too |
| `BcFirePillar` | `ObjectFirePillar::calcLavaWaiting` / `calcEruptFinishing` | 0 when it leaves the waiting state (`ObjectFirePillar::m_state` = 1) / 1 |
| `WiiEscalator` | `ObjectWiiEscalator::initObj`; `stateInitUp` / `stateInitDown` | starting value 1 when `m_settings[1] == 0`, else 0 (`ldrh r0, [r0, #0x2c]` / `strbeq r6` / `strbne r7`, r6 = 1, r7 = 0); then 1 / 0 |
| `ShellFish` | `ObjectShellFish::calcObj`, `calcOpenWaiting`, `start_Yararetoru` | 1 and 0 at changes of `ObjectShellFish::m_state` |
| `packunLight` | `ObjectPackunLight::calcObj`; `ObjectPackunMusic::stateSleep` writes 0 to its light | 1 / 0 |
| `WiiCar`, `GcTable` | `ObjectWiiCar::initObj` (0), `stateMove`; `ObjectGcTable::calcObj` | `!(m_path->flags & 4)`, a flags word at +0x4 of the object's `ObjectBase::m_path` |
| `N64Crossing` | `ObjectCrossing::set_isFlickering` | Finding 10 |
| `MeltIce` | `ObjectMeltIce::initObj` (1), `calcObj` (0) | not linked on any original course |

Readers, all in `Enemy`: `selectNextPointHandleIndexWithShortcut_` (above, 0 closes the branch), `AIAutoSteer::isNeedWait_`
and `stateWait` (crossings, Finding 10, 1 makes the CPU wait), `AIAutoSteer::isNeedRunAway_` (battle: the objects of
`ObjectDirector::m_bd_board_objects`, 0 within range and ahead makes the CPU run away), `AIObjectSearcher::isMapObjectToAvoid_`
(object ID 0xD5, `ShellFish`: avoided only while 0). The value therefore has no single meaning; the new name only says that
it is a state shown to the CPUs.

Measured on Music Park (course 15, `m_obj_check_rate` 50 for every CPU): paths 5 and 7 (the branches after path 15) each have
one `MpBoard` (0x1AA), and paths 17 and 18 (after path 2) one object 0x1A8, all with `m_settings[7] == 0`. Their
`m_ai_signal` changes during the race, mostly 1 on one branch and 0 on the other. Sampled on the frame each CPU
chose its branch, the CPUs took the branch whose object had 1 at 29 of 36 such forks. With half of the choices checking the
objects and the other half random, the code reading predicts 75 %, and the opposite reading 25 %. So 0 does exclude the
branch.

Battle, `AIPathPointBattle::selectNextPointHandle_`: while the base point is inside `m_current_path`, the CPU keeps going in the
direction it entered (`index + 1` when `m_path_entry_point` is the first point, `index - 1` when it is the last). At a path end
with more than one link, `selectNextPointHandleIndex_` switches on `m_search_mode`:

| `m_search_mode` | Choice | Set by |
| --- | --- | --- |
| 0, 2 | random | 0: the `AIControlBase` constructor (`param_1[0x12] = 0`), overwritten by `AIControlBattle::init` before the first choice; 2: `AIControlBattle::init`, and one of the random outcomes of `stateInitSearchRival`, `stateSearchItem` and `stateSearchCoin` |
| 3, 5, 6, 8 (8: coin battle only) | highest score from a `TargetSearcher` | 3: `stateInitSearchItem`, `stateSearchItem`; 5: `stateInitSearchRival`, `stateSearchCoin`; 6: `stateInitSearchRival`; 8: `stateInitSearchCoin`, `stateSearchCoin` |
| 4, 7 | lowest score | 7: `stateSearchItem`; 4: never written |
| 9 | branch nearest to `m_target_for_branch_trans` | `stateInitLockedOn` |
| 10 | branch farthest from it | `stateInitRunAway` |

`stateInitSearchRival` draws `rand(100)` against a weight table (`AIControlBattle::m_search_weights`) and writes 6, 5 or 2;
`stateSearchItem` writes 3, 7 or 2 the same way, and `stateSearchCoin` 8, 5 or 2, the latter only when
`AIControlBattle::m_battle_type` is 2 (it writes nothing otherwise). `m_battle_type` is written only by the virtual
`AIControlBattle::setBattleType` (the constructor writes 0); its caller found here is `TeamInfo::decideTeamBattleType`,
called by `AIBattleManager::stateInitCoinIdle` and `stateCoinIdle`, which gives 1 to a random share of a team's CPUs and
2 to the others. What 1 and 2 mean was not looked at. Measured in a balloon battle (Wuhu Town, 8 CPUs, 4000
frames): modes 6, 5, 3, 7 and 2 were in use, 5 for 22 % of the frames, so 5 does not mean coins.

Mode 4: a scan of the whole `eur2` code for word stores at the offset of `m_search_mode` (+0x48) in `Enemy` functions finds, for an `AIControl` object, only
`AIControlRace::init` (1), `AIControlBattle::init` (2), `stateInitRunAway` (10), `stateInitLockedOn` (9),
`stateInitSearchCoin` (8), `stateInitSearchItem` (3), `stateInitSearchRival`, `stateSearchItem` and `stateSearchCoin` (from
their tables above); the constructor writes 0 through `param_1[0x12]`. No code writes 4, so the case is dead in `eur2`.

Mode 1, and mode 8 outside coin battle, fall through the switch and take branch 0.

In every case a branch on the same path as the base point is excluded when `m_do_not_select_backward`, which
`AIPathHandler::init` sets in every mode and `AIControlBattle::stateInitLockedOn` clears unless
`AIControlBattle::m_do_not_select_backward`, a byte of the `AIControlBattle` object itself (`ldrb r2, [r0, #0x95]`
on the same `this` as the `m_search_mode` store, written only by the constructor (0) and by the virtual
`AIControlBattle::setDoNotSelectBackward(bool)`), is set. The chosen branch's
path and point are stored in `m_current_path` / `m_path_entry_point`. The scores come from `PathAnalyzer`, which turns the point
list into nodes (position, `scale * 50`, neighbours) and undirected edges (length, direction); `TargetSearcher::setTarget`
uses the node widths to decide which edges a target is on (Finding 6, `scale`), and `TargetSearcher::setPoint` spreads a
value from a target's edge to the neighbouring edges, decreasing with edge length.

### 9. Fields without a reader

- `MapdataEnemyPath::m_depth` and `MapdataEnemyPathAccessor::m_depth_num`: the only callers of the path accessor getters are
  `PathAnalyzer`, `PathSmoother`, `AIPathManager` (`init`), `AIControlRace::initAfterManager` (reads the path count only),
  `AIObjectManager::init` (stores it in `AIObjectSearcher`, whose `isMapObjectToAvoid_` reads `m_next_points` of a path) and
  `IsValidEnemyPath` (count only). In game, gdb access watchpoints on the race accessor's `m_depth_num` and on `m_depth` of
  paths 0 to 2 caught nothing in 6713 frames of a 150cc race on Wii Koopa Cape, while the same kind of watchpoint on
  `AIPathHandler::m_reach_radius_sq` of a CPU fired five times within 5 seconds. Both are written and never read, at least
  in race. In a balloon battle on GBA Battle Course 1 at real speed, the same watchpoints on the KMP accessor (`m_depth_num`,
  `m_depth` of paths 0 to 2) caught nothing in 60 seconds of battle, while a control watchpoint on a CPU's
  `m_reach_radius_sq` fired three times in 0.4 seconds before and after. They mirror `MapdataCheckPath::createDepth_` /
  `MapdataCheckPathAccessor::setupPathDepth`, which build the same values for the checkpoints.
- `MapdataEnemyPoint::m_internal_flags` bits 0x2 and 0x8: written only by `AIPathManager::init` (`orr r6, r6, #10`, award
  start paths). Every load of `m_internal_flags` (+0x50) followed by a bit test in `Enemy` and `Field` code tests bit 1 only
  (`AIItemRace::stateKinoko`, `AIAutoSteer::calcTargetToAvoid_`, `AIPathPoint::calcNextTargetTrans`).
- `MapdataEnemyPoint::m_direction` has one reader, see Finding 6.

### 10. Train crossings and battle boards

#### The crossing object

`Field::ObjectCrossing` (`N64Crossing`, ID 0x13E). `sinit_ObjectCrossingParam` fills `ObjectCrossing::sParam`:
`vldr s0, =1000f` / `vstr s0, [fp, #4]`, `mov r0, #0xf0` / `mov r1, #0x12c` / `strd r0, [fp, #8]`.

- `ObjectCrossing::initObj`: the train distance squared (`sParam` +0x4, squared) goes to `m_train_dist_sq`; the two trains
  (`m_trains`) are `ObjectDirector::findObject(0x68, 0)` and `findObject(0x68, 1)`; the partner (`m_partner`) is the first
  other crossing among `findObject(0x13E, 0..3)` with the same `m_settings[0]`, and the crossing found first by its partner
  is the master (`m_is_master`).
- `ObjectCrossing::calcObj`, master only: when `min(|XZ(train - crossing)|^2)` over both trains is below `m_train_dist_sq`
  it calls `set_isFlickering(1)` on itself and its partner, else `set_isFlickering(0)`.
- `set_isFlickering(on)`: counts flashing frames (`m_flash_frames`, reset by `on == 0`). While below `sParam` +0x8 (240)
  it writes `m_ai_signal = 0`; afterwards it counts `m_signal_frames` and writes
  `m_ai_signal = (m_signal_frames < sParam +0xC)`, so 1 for 300 frames, then 0 until the flashing stops.

#### The CPU's wait

- `AIAutoSteer::init` collects every object of `ObjectDirector::m_obj_link_array` with ID 0x13E (a constant loaded by the
  function) into `AIAutoSteer::m_crossings`; so a crossing takes part only when its `m_enemy_route` is 0 or more.
- `AIAutoSteer::stateIdle` (race only: `AIAutoSteer::m_is_battle` is set in battle) calls `isNeedWait_` first.
  `isNeedWait_` returns 1 for the first crossing with `m_ai_signal != 0` that is less than 500.0 away (integer compare of
  the float bits of the distance, `cmp r0, r8` / `bge`) and, unless status bit 0x10000 (`accident_1`) is set, ahead
  (`dot(d, kart axis) > 0.1 * |d|`), and only when the kart is not gliding (0x80), not in Bullet Bill (0x400000) and
  `VehicleMove::m_star_frames < 1`. The state then becomes 6. `stateIdle` only calls it while
  `VehicleMove::m_ink_frames < 1` and `AIAutoSteer::m_is_far_behind` is 0.
- `stateInitWait`: `AIAutoSteer::m_wait_brake = rand(100) < 75`, or 1 when status bit 0x10000 is set;
  `AIAutoSteer::m_wait_any_direction` = that bit.
- `stateWait`: leaves the state when the crossing's `m_ai_signal` is 0, when `m_is_far_behind` is set, or (without bit
  0x10000 and `m_wait_any_direction`) when the crossing is behind (`dot(d, kart axis) < 0`); it goes to state 4
  (`stateZigZag`) instead while `VehicleMove::m_ink_frames` is 1 or more (the counters are counted down by
  `VehicleMove::calcStarInkThunderPress`; `startInk` / `endInk` and `endStar` write them). Otherwise, with `m_wait_brake`,
  it sets bit 0x40 of `DriveInfo::m_request_flags`. `AIDriftDrive::calcSteerNormal_` presses neither accelerate (1) nor
  brake (2) while that bit is set (`if ((uVar8 & 0x40) == 0) { ... m_buttons |= 1 }`).
- `AIStuck::checkAccident_` counts `AIAutoSteer` states 5 and 6 as accidents, so a waiting CPU is not stuck (Finding 11).

#### CPUs far behind

`AIAutoSteer::m_is_far_behind` is written only by `AIControlRace::watchPlayerAndSwitchCollision` (end of
`AIControlRace::update`, skipped while `AIControlRace::m_skip_watch` is set): 0 when the CPU is within 1500 units of
`AIControlRace::m_watched_ai` (`d^2 <= 2.25e6`, integer compare), 1 when it is farther and its race progress
(`LapRankChecker::KartInfo::m_current_race_progress`) is **lower** (`vcmpe.f32 s0, s1` / `bcs` skips the store when the
CPU's own value, `s0`, is not below the watched kart's), i.e. the CPU is behind; otherwise unchanged.
`LapRankChecker::calc` gives rank 1 to the highest value of that member, so a higher value is further ahead. The same
function writes `DriveInfo::m_collision_switch` and `VehicleControlAI::m_collision_switch` alike (collision switches, not
looked at). `m_watched_ai` is `GetAI(CRaceInfo::m_detail_kart_id)` (`AIControlRace::init`). The in-game measurements are
in Finding 13.

#### Measured on Kalimari Desert

N64 Kalimari Desert, 150cc Grand Prix, 8 CPUs, 10435 frames, sampled every 5 frames: the four crossings form two pairs that
always showed the same state. Apart from a 50-frame flash at the start of the race, each train passage flashed for 655 to
665 frames; `m_ai_signal` was 1 from flashing frame 240 to 540 (5 of 5 passages per pair). There were 13 waits
(`AIAutoSteer` state 6), starting 136 to 488 units from the crossing. In 11 `m_wait_brake` was 1 and bit 0x40 of
`DriveInfo::m_request_flags` was set; in 10 of them `m_forward_speed_ratio` fell to 0 to 0.033 at 96 to 261 units from the
crossing, the eleventh started 35 frames before the end and fell to 0.41. All 11 ended on the sample where `m_ai_signal`
went back to 0. In the 2 others `m_wait_brake` was 0 and the CPU drove on (ratio 0.95 and 0.61); one of them left state 6
after 65 frames, before the crossing, and started a new wait with `m_wait_brake` 1 five frames later (why it left was not
looked at).

Second run (150cc Grand Prix, player kart as CPU, 10500 frames, every frame, the exit decided on the frame before the state
changed): 12 waits, 11 ended on the frame the crossing's `m_ai_signal` went to 0, one (kart 4, the second pair) with the
signal still 1 and `m_is_far_behind` set. The question of the first run (the CPU that left a wait after 65 frames and
started a new one five frames later with `m_wait_brake` 1) is not answered by data; the code allows two paths:
`m_is_far_behind` flipping, or the crossing passing behind the kart followed by status bit 0x10000, which skips the
direction test of `isNeedWait_` and forces `m_wait_brake` and `m_wait_any_direction` to 1. In a first, faulty log of this
session, three such second waits began with the crossing beside or behind the kart and lasted until the signal ended,
which only the 0x10000 path explains.

#### Battle: running away from boards

`AIAutoSteer::isNeedRunAway_` (battle, `m_bd_board_num > 0`; only N64 Big Donut has `BdBoard` objects, ID 0x192, four):
for each board with `m_ai_signal == 0` within 300 units (`90000`, integer compare) whose direction from the kart is within
about 53 degrees of the CPU's drive target (`dot > 0.6 * |a| * |b|`), it builds `m_run_away_target` = board position + 400
x a board axis turned by a random angle up to 0.4 pi (side chosen by the sign of a dot product) + 50 in Y, and returns 1
(state 5). `stateRunAway` drives there (request bit 0x4) and returns to state 0 after 120 frames or within 40 units; ink
sends it to state 4. `ObjectBdBoard::calcObj` runs the `TcBoard` code, so the signal is 1 while the board holds still.

Measured on Big Donut (balloon battle, hard, 4000 frames sampled every 2 frames): 32 run-aways, entered at 38 to 298 units
from a board showing 0, the target always 403 units from the board; 25 ended after 120 to 122 frames, 4 earlier (the spot
reached), and 3 lasted 244 or 344 frames (a new run-away started between two samples); the boards showed 0 for 58 % and
70 % of the time.

### 11. Stuck CPUs, back-up and Lakitu

`Enemy::AIStuck`, one per CPU, a state machine (0 idle, 1 check, 2 back up, 3 Lakitu). `AIStuck::init`:
`m_is_battle = (rule mode 3 || 7)`, `m_is_multiplayer = CRaceInfo::m_race_mode_flag.multiplayer_or_online`,
`AI::m_is_backing_up = 0`.

#### Checking for progress

`stateCheckStuck`, every frame:

- In Bullet Bill (status bit 0x400000, `killer`): both counters and `m_fall_count` are reset.
- `checkAccident_` is true for status bits 0x10000 (`accident_1`), 0x800000 (`hang`), 0x20 / 0x40 (`jugem_recover`,
  `jugem_recover_ai_oob`), or `AIAutoSteer` in state 5 (run away) or 6 (wait).
- `m_slow_frames`: +1 per frame without accident while `VehicleMove::m_forward_speed_ratio < 0.1` (integer compare of the
  float bits, `cmp r0, r1` / `bge`), +3 instead on such a frame when the kart also touches a wall (bit 0 of `VehicleMove::m_col_checks[1].m_collision_result`,
  Finding 12), else reset to 0. Above 600: state 2.
- `m_no_advance_frames`: +1 per frame without accident and without `AIPathHandler::m_advanced_this_frame`, else reset. At
  exactly 450 it sets `m_reroute_request` and returns (`if (*(int *)(param_1 + 0x4c) == 0x1c2) { *(param_1 + 0x69) = 1;
  return; }`); every other frame without accident clears it first. At 901: state 3. The re-route this asks for is in
  Finding 12.

`VehicleMove::m_forward_speed_ratio` is written by `VehicleMove::applyDriveSpeed`: `s2 = m_forward_speed * (1 /
m_current_max_speed_base)`, stored to `m_forward_speed_ratio`, and replaced by 0 when negative (`vcmpe s2, s3` with `s3 = 0`).

#### The back-up

`stateInitBackPathPoint`: `initMoveBackTargetToPreviousPath` (reach radius 2500, `AIPathPoint::m_move_back_rate = 0`),
`m_back_rate = 0`, `m_back_phase = 0`, `AI::m_is_backing_up = 1`, `m_back_rate_max = m_is_battle ? 2.0 : 4.0`
(`vldrne s0, =2f` / `vldreq s0, =4f` after the load of `m_is_battle`, `ldrb r0, [r4, #0x6a]`). It resets `m_slow_frames`, `m_back_frames` and
`m_back_phase`, not `m_no_advance_frames`, which `stateBackPathPoint` does not update either: after a back-up that reached no
new point, the 901-frame limit is reached after the remaining check frames.

`stateBackPathPoint`, every frame, aims at `AIPathPoint::getInterpolateTarget()`, which slides the aim back along the route
by `m_move_back_rate`: from `m_target_trans` to `m_prev_point` for 0 to 1, then to `m_history_points[0]`, `[1]`, `[2]` for
1 to 2, 2 to 3, 3 to 4 (`setBasicDriveInfo_` of both control classes steers to the same function):

- phase 0: `m_back_rate += 0.04`; at `m_back_rate_max` (100 frames in race, 50 in battle) `AI::m_is_backing_up = 0` and phase
  1. While `m_is_backing_up` is set, `AIDriftDrive::calcSteerNormal_` presses only brake (2) with a zero stick and returns,
  and the speed ratio written to `VehicleControlAI::m_max_speed_ratio` is 0.6 (`AI::setMaxSpeedRatio`, `AIControlRace::update`).
- phase 1: normal driving toward the aim; when it is less than 100 units away (constant 100.0, integer compare of the
  float bits), phase 2 and `m_back_frames = 0`.
- phases 1 and 2: `m_reroute_request = (m_back_frames % 120 == 0)` (multiply by `0x88888889` and shift right by 38, then
  `m_back_frames - q * 120`), so a re-route is asked for every 120 frames, and on the frame phase 2 begins. Phase 0 writes 0.
- phase 2: when `|dot(d, VehicleMove::m_forward_dir)| > 0.8 * |d|`, state 1.
- `m_back_frames` counts up in every phase; above 600 (without an advance), state 3. An advance
  (`m_advanced_this_frame`) ends the state at once (state 1).
- `stateExitBackPathPoint` falls through into `finishMoveBackTargetToPreviousPath` (default radius, rate 0). It does not
  clear `AI::m_is_backing_up`.

#### Handing over to Lakitu

`stateStartOutOfBounds`: `Kart::Director::startJugemRecoverAI(kart)`, unless `m_is_multiplayer` and (the kart has finished,
`VehicleBase::m_is_fake_goal`, or `RaceSys::IsGoalState()`); then both counters reset and state 1.

#### Relocations

`AIStuck::onAIFall` (called by `AIControlRace::onAIFall` and `AIControlBattle::onAIFall` on every relocation): state 0,
whose `stateInitIdle` zeroes `m_slow_frames`, `m_no_advance_frames`, `m_back_phase` and `m_back_frames`, so a relocation
restarts both limits; when the kart is less than 10 units
from the position of the previous relocation (`d^2 < 100.0`, integer compare of the float bits), `m_fall_count` is
incremented, and when it is already above 3, state 3 instead; else `m_fall_count = 0`. The position is stored for the next
time. So the sixth relocation in a row at the same spot calls Lakitu.

#### Stuck CPUs measured in game

150cc Grand Prix, player kart as CPU:

- On Wii Koopa Cape, GCN Dino Dino Jungle and N64 Kalimari Desert (6537 samples every 5 frames, 8 CPUs) no CPU reached state
  2 or 3; the highest `m_slow_frames` was 49 and the highest `m_no_advance_frames` 210.
- DS DK Pass, a CPU held in place by writing its position every 5 frames: `m_forward_speed_ratio` stayed about 1.1 (the
  wheels kept turning), so `m_slow_frames` stayed 0, but `m_no_advance_frames` reached 900 and the state went to 3 after
  890 frames; status bits 0x40 (`jugem_recover_ai_oob`), then 0x800000 (`hang`, Lakitu).
- DS DK Pass, `AIStuck` forced into state 2 (next state 2 and the "change requested" byte set, as the code does) on a CPU at full speed: brake only,
  stick (0, 0), reach radius 2500, `m_move_back_rate` rising by 0.04, `m_forward_speed` going negative. 30 frames later the
  CPU, its height down by about 160 units, was relocated (target point 205 -> 269): state 0, then 1, with `AI::m_is_backing_up` still 1. It kept reversing
  (`m_forward_speed_ratio` 0, so `m_slow_frames` counted) through another interrupted back-up, until a back-up 1960 frames
  after the first reached the end of phase 0 (100 frames, rate 4.0, then `m_is_backing_up` 0, accelerate with stick -1),
  phase 2 after 130 frames and state 1 two frames later.
- Mario Circuit, lap 3, the player's kart as a CPU: when its target was point 122 of path 6 (the climbing loop of points
  110 to 130, where point 126 passes over point 113), the kart was put on point 116 of the same path, unheld. It left the
  road into the lower ground inside the loop, its target moved on to point 128 (on the bridge above), and it pushed
  against a wall below the bridge. Read every frame: bit 0 of `m_col_checks[1].m_collision_result` set,
  `m_forward_speed_ratio` 0.035 to 0.05, `m_slow_frames` growing by 3 per frame; state 2 when it passed 600 (602, about
  200 slow frames after the kart became slow), with `m_no_advance_frames` at 267. No relocation in the whole test
  (`m_fall_count` 0, target point 128 throughout), although the kart touched the wall for far more than 30 frames.
  Phase 0 lasted 100 frames (speed ratio 0, reversing); in phase 1 the kart drove toward the aim, hit a wall again 150
  frames later (bit set, speed ratio about 0.03) and stayed there, never within 100 units of the aim. State 3 came 601
  frames after state 2 began (`m_back_frames` 601, `m_no_advance_frames` still 267), status bit 0x40
  (`jugem_recover_ai_oob`) at once, and 0x800000 (`hang`, Lakitu) 91 frames later.

### 12. Re-routes to the nearest point

A re-route is a call of the control class's `onAIFall` (a virtual function of `AIControlRace` / `AIControlBattle`), directly
or through `AIEngine::onAIFall`. What it does is in Finding 5: `findNearEnemyPoint` (500 units in XZ, the
`max_search_y_offset` filter; option 2 in Bullet Bill, 1 after the finish, else 0 in race, always 0 in battle), relocation
when the point's `m_path_index` differs from the target's, or always for `AI::m_is_player_kart` (race only); the race
version then walks `m_next_points[0]` to the first point more than 180 units from the kart. Each relocation calls
`AIStuck::onAIFall` (Finding 11). No height condition is part of the re-route itself.

The search runs on the point accessor that `AIControlBase::initAfterManager` stores in
`AIControlBase::m_enemy_point_accessor` from `AIPathManager::getEnemyPointAccessor` (`bl` / `str r0, [r4, #0x38]`),
which is `AIPathManager::m_race_point_accessor` in race mode and the KMP accessor otherwise; `AIControlRace::onAIFall`
and `AIControlRace::startKiller` both pass it (`ldr r2, [r4, #0x38]`). In a race the nearest point is therefore a point of the re-sampled list, inserted points
included, as measured in Finding 13 (Wuhu Loop, 339 KMP points, a CPU held on point 478).

#### The callers

| Caller | When | Modes |
| --- | --- | --- |
| `AIPathHandler::update` | the height re-route of Finding 5 (steep target, after more than 20 frames) | all |
| `AIEngine::update` | `AIControlBase::isAIFallSignal()`, i.e. `AIStuck::m_reroute_request` (through `AIControlBase::m_ai_stuck`, `ldrsbne r0, [r0, #0x69]`) | all |
| `AIEngine::update` | in Bullet Bill (status bit 0x400000) and touching a wall, every such frame | race |
| `AIEngine::update` | touching a wall for more than 30 frames in a row (`AIEngine::m_wall_frames`, `0x1e < count`, then reset to 0) | all |
| `AIEngine::awake` | the engine is in state 3 (`statePlayerIdle`) with no change pending: a player's Bullet Bill, and the end of a player's race (`statePlayerIdle` -> `ChangeToAI` -> `Kart::Director::changeToAI` -> `AI::awake` once the kart has finished) | race |
| `AIAutoSteer::stateExitGather` | leaving `stateGather` when `m_gather_target_found` is set | coin battle |

`AIEngine::update` runs these tests every frame before it runs the current state
(`Util::TStateObserverEx<Enemy::AIEngine>::executeState`), whatever the engine state. `AIStuck::m_reroute_request`
is set for one frame at 450 frames without an advance and every 120 frames of back-up phases 1 and 2 (Finding 11).

#### The wall bit

"Touching a wall" is bit 0 of `VehicleMove::m_col_checks[1].m_collision_result`. The `VehicleMove` constructor builds
five `KDGndCol::CheckIF_EX` one after the other from the start of `m_col_checks` (the `str [r0, #0xc38]!` / `add r0, r0,
#0x48` and five constructor calls), so the word the AI tests (`VehicleMove` +0xC94) is `m_col_checks[1].m_collision_result`, whose bit 0 the template's `ECollisionResult` already calls `COLLIDING_WITH_WALL`; no
plain store writes it, so it is filled through the `CheckIF` by the collision code. Measured in game: with the player's
kart driven into the fence of Mario Circuit, the bit was set while the kart was against the fence (screenshot), and a
breakpoint on `AIControlRace::onAIFall` caught the call from `AIEngine::update` with the bit set and no re-route request.

#### Re-route at the start of a player's Bullet Bill

- `AIEngine::stateReady` moves a kart that `IsDoAsAI` rejects (a kart a person drives) to state 3 when the race starts, and
  `AIEngine::sleep` sets state 3 directly. `AIPathHandler::update` returns at once while the engine is in state 3 with no
  change pending, so the route cursor of a player's kart is not updated while the player drives.
- `VehicleMove::startKiller_Impl` sets status bit 0x400000, then, when its `bool` argument is 0 and `VehicleBase::unk_0x99` is 0, calls
  `Director::awakeAI_byKillerStart` (`AI::awake` -> `AIEngine::awake`), then `Director::noticeAI_StartKiller`
  (`AI::startKiller`, also only when the argument is 0). Both `Director` functions do nothing unless `Director::m_is_ai_valid` is set.
- `AIEngine::awake`, in state 3 with no change pending: `AIStuck::onOutOfBoundsInner` (state 0, counters and
  `m_reroute_request` cleared, position stored), the control class's `onAIFall`, then next state 2 (`stateRun`). In any
  other state it does nothing that relocates (it only handles a finished kart). A CPU is in state 2 during the race, so for
  it the call changes nothing.
- The Bullet Bill bit is already set, so `AIControlRace::onAIFall` searches with option 2 (skip -2 points), and since
  `AI::m_is_player_kart` is set it relocates even when the nearest point is on the target's path. When no point is found it
  does not relocate, and `AIControlRace::startKiller`, called next, finds none either and sets its ending flag.

#### Coin battle gathering

The coins are `Object::Coin` objects of `Object::CoinManager` (`ObjectDirector::m_coin_manager`, `CoinManager::m_coins`, a
`sead::PtrArray`); flag 0x8 of `Coin::m_flags` is set by `Coin::kill`, so only coins still in play are gathered. `m_gather_radius` is 50 on
Honeybee Hive (course 33), 150 on DS Palm Shore and N64 Big Donut (35, 36), 70 elsewhere (`AIAutoSteer::init`).

`AIAutoSteer::stateInitGather` runs only when the rule mode is 3 or 7 and `CRaceInfo::m_race_mode.m_type` is 0, Coin. It
collects coins within `AIAutoSteer::m_gather_radius` (in XZ) whose flag 0x8 of `Coin::m_flags` is clear, takes the last
one as the target and sets `m_gather_target_found`; `stateGather` drives to it (`DriveInfo` target, request bit 0x4) for
300 to 599 frames. `stateExitGather` re-routes when `m_gather_target_found` is set. The coin objects and their flag were not
looked at further.

### 13. In-game tests and the original courses

Azahar, `eur2`, 2026-10-05, throw-away scripts over `mk7re.dynamic` (`Session`, `Race`), reading the chain
`Kart::Director::m_ai_manager` -> `AIManager::m_ais` -> `AI::m_ai_engine` -> `AIEngine::m_ai_control`. A relocation shows
as `AIPathPoint::m_prev_point` and the three history points all equal to the new target (`goNextPoint`, relocation branch).

#### Stuck CPU

Wuhu Loop, 150cc Grand Prix: a CPU heading to point 19 of path 0 was held every frame on point 478 of path 33. On the
frame after `m_no_advance_frames` reached 450 with `m_reroute_request` 1, its target became point 308 of path 7, both
counters 0 and `AIStuck` passed through state 0. Point 306 of path 7 lies exactly on point 478 (equal distances, the lower
index wins) and the walk 306 -> 307 (139 units) -> 308 (344 units) is the 180-unit rule.

#### A player's Bullet Bill

Mario Circuit: with the human player's kart on path 5 and its AI heading to point 1 of path 0, `KartItem::setItemForce(9)`
and L. On the frame status bit 0x400000 appeared, the target became point 182 of path 5, the point a re-implementation of
`findNearEnemyPoint` (option 2) and the walk predicted (nearest 180); the engine went from state 3 to 2 one frame later. A
first, less controlled try on Wuhu Loop gave the same picture.

#### Wall

See Finding 12. A later wall re-route of the same kart was invisible because the walk from the nearest point (175, last
point of the lap) ended on point 0, the AI's target already.

#### End of a player's race

A breakpoint on `AIControlRace::onAIFall` caught `AIEngine::awake` relocating the idle player's kart when the race ended
for it (`VehicleBase::m_is_fake_goal` set, engine then in state 6).

#### Dead-end path

With a breakpoint just after `Field::GetEnemyPathAccessor` in `AIPathManager::init`, the 16 next entries of one ENPH entry
were set to 0xFFFF in memory (path 6 of Wuhu Loop and of Mario Circuit, where the route merges). The last point of the path
then had `m_next_count` 0, and `selectNextPointHandle_` read `m_next_points[0]` past the empty array: 0 both times, point 0.
On Mario Circuit three CPUs reached it: each targeted point 0 (about 3300 units away across the infield), left the route
and, 2 to 8 seconds later, was relocated while touching a wall, once onto helper path 11 (no previous path, next path 8),
the other times onto path 8 (the original continuation). The game did not crash.

#### Original helper paths

In the KMP files, a path that no `m_next_points` entry names and that has no previous path is reachable only by a
re-route. 30 of the 32 Grand Prix courses have such paths (none on `Gagb_BowserCastle1` and `Gsfc_RainbowRoad`): 187 paths,
1628 points, 2 to 31 points per path (median 8), 167 with one next path. Horizontal distance from each point to the nearest
point of the other paths: median 96, 10 % below 5, 90 % below 347, at most 1039 units; height relative to it: median 0,
10 % below -320, lowest -2319. Settings: drift 2 on 1357 points, mushroom 0 on 396, flag 0x02 on 251,
`max_search_y_offset` set on 289, `path_find_options` set on 16.

#### `m_is_far_behind`

`AIAutoSteer::m_is_far_behind`, measured in the fourth fact check (150cc Grand Prix, every CPU sampled every 5 or 10
frames, distance and `m_current_race_progress` compared with the watched kart, kart 0):

- Wuhu Loop, the player's kart driven as a CPU, 6600 frames: 3285 samples of a CPU more than 1500 units away and ahead in
  the race, the flag 0 in all of them; no CPU was ever behind.
- The second race of the cup (Mario Circuit by the earlier dynamic check; its course ID was not read again), the player's
  kart driven as a CPU, one CPU held at its start position: the flag became 1 once the CPU was more than 1500 units away
  (1532 at the first change), stayed 1 while it was far behind, went to 0 when the watched kart came back within 1500
  units of it (1489) and to 1 again past 1500.
- The fourth race of the Flower Cup (its course ID was not read) with a human player (Master, `VehicleBase::unk_0x99` 0),
  its kart moved every 5 frames to where a CPU had been 40 frames earlier, so that its checkpoints advance, and one CPU
  held at its start: far (more than 1500 units) and behind, flag 1 in 1888 samples and 0 in 16; far and ahead, 0 in 185;
  near, 1 in 4 samples. The few mismatches are probably samples where the distance or the order changed between the
  game's update and the read. A first try on Music Park (course 15), in which the player's kart was first moved far along
  the course at once, lost its checkpoint progress (it went negative) and is not counted.

### 14. Values used by the original courses

Counted with the throw-away KMP parser of [Sources and method](#sources-and-method) over the 40 courses (34 race, 6 battle),
and counted again with an independent parser in the first fact check. The battle cells of scale, `drift_setting` and
`max_search_y_offset` were counted in the fourth document review, over the 527 points of the six battle KMPs.

| Setting | Race courses | Battle courses |
| --- | --- | --- |
| scale | -0.375 to 7.125, mostly 0.5 to 2, 1.0 by far the most common; a few points down to 0.1; 13 points negative (-0.25 or -0.375) | 0.375 to 6.0 |
| `mushroom_setting` | 2 on more than half of the points | 0 on every point |
| `drift_setting` | 0 on 1880 points, 1 on 347, 2 on 4655 (about two thirds of 6890), 3 on 8 (all in `Gctr_WuhuIsland1`) | 0 on every point |
| flags | 0x01 on 467 points, 0x02 on 569, 0x04 on 1152, 0x08 on 42, 0x10 on 329, 0x20 on 773, 0x40 on 247, 0x80 on 349; 0x04 often together with 0x10, 0x20 or 0x80 | only 0x80: 4 points in `Bagb_BattleCourse1`, 12 in `Bctr_WuhuIsland3` |
| `path_find_options` | -1 on 33 points (DS Airship Fortress, GCN Daisy Cruiser, Maka Wuhu, ...), -2 on 72 (Rainbow Road, Rock Rock Mountain, ...), -3 on 13 (Bowser's Castle, DK Jungle, Wuhu Loop, ...), -4 on 5 (Cheep Cheep Lagoon, Wario Shipyard, GCN Daisy Cruiser); 1, 2, 3 in `Gctr_WinningRun` | 0 on every point |
| `max_search_y_offset` | -1 on 475 points; 20, 30 or 40 on a few; 1 only in `Gctr_WinningRun` | 0 on every point |
| `m_link_end_flags` | 0 on every path | see Finding 2 |
| STGI byte 1 | 0 in 22 of the 34 race KMPs | |

The objects with an enemy route are listed in Finding 8, the helper paths in Finding 13.

### 15. Mii titles

`AI::init` sets `AI::m_title_mask` only in single-player Grand Prix, and maps a per-player value 1 to 16 to its bits. Read
against the order of the `Title1_*` messages (the code maps value n to message n - 1), values 6, 7, 8 and 9 are Boost
Jumper, Aviator, Dolphin and Drift Wizard, which matches what the code does with bits 0x4, 0x40, 0x80 and 0x20. By the same
order 0x100 is Rookie, 0x1000 Star Racer, 0x10 Safe Driver and 0x800 (value 12) Model Driver. The order was read again
in this check from the English `Common.msbt` (`pat1:/Patch/UI/common-ee`): messages 1900 to 1915 are Shell Shark,
Banana Blitzer, Bob-omb Ace, Pro Defender, Rowdy Racer, Boost Jumper, Aviator, Dolphin, Drift Wizard, Quick Starter,
Comeback King, Model Driver, Zig-Zagger, Safe Driver, Rookie, Star Racer. The readers of the bits in this document:

| Bits | Reader | Effect |
| --- | --- | --- |
| 0x1100 | `AIPathPoint::calcNextTargetTrans`, the drift start, `AIDriftDrive::calcSteerNormal_` (Finding 6) | aim at the point centre; never start a drift; never hop at trick chances |
| 0x10 | `AIPathPoint::calcPointOffsetDistance_` (Finding 6, `scale`) | a lane beyond 50 % drifts back with steps three times as large |
| 0x4 | `AIDriftDrive::calcSteerNormal_` (Finding 6, flag 0x08) | hop at every trick chance, and also every 120 to 299 frames |
| 0x840 | `AIDriftDrive::calcSteerNormal_` (Finding 6, flag 0x08) | hop at every trick chance |
| 0x20 | `AIControlBase::setBasicDriveInfo_` (Finding 6) | keep the mini-turbo; skip the random drift-start check |
| 0x44 | `selectNextPointHandleIndexWithShortcut_` (Findings 6 and 8) | take a -3 branch, and a board-linked branch that is open |
| 0x80 | `selectNextPointHandleIndexWithShortcut_` (Finding 6) | take a -4 branch |
| 0xC0 | `AIItemRace::stateInitKinoko`, `stateKinoko` (Finding 6) | no mushroom shortcut; use the Mushroom while gliding (0x40) or in water (0x80) |
| any | `selectNextPointHandleIndexWithShortcut_` (Finding 8) | always check the linked objects |

### 16. Differences from the input notes

| Input notes | Found in `eur2` |
| --- | --- |
| ENPH 0x44 not covered | `m_link_end_flags`, Finding 2 |
| Battle "turns every previous link into a next link" | also picks the end of the linked path from `m_link_end_flags`, and battle paths are driven both ways |
| Flag 0x80 "also works in battle" as a speed flag | in battle it also centres the CPU and makes it hop at trick chances |
| `drift_setting` has "no practical effect" in battle because the rolls fail | it is not read at all: `AIControlBattle::setBasicDriveInfo_` replaces the function |
| `drift_setting >= 3` "reportedly unused" | 8 points of `Gctr_WuhuIsland1` use 3 |
| Respawn falls back to the checkpoint-sector search | the search is called but its result is dropped; the fallback is point 0 |
| `MapdataEnemyPath` 0x10 not covered | `m_depth` |
| `VehicleMove` +0xDA4 (enables the flag 0x02 check without the flag) unidentified | `m_airborne_rate`: the kart has been in the air for 20 frames |

## Confidence

Certain (read in `eur2` code, and for `m_link_end_flags` also matched against the course data):

- the layouts in the glossary that come from constructors and `setup` functions;
- Findings 1, 2, 3, 5 (including the pass-through plane, read from the disassembly), 7, 9, 10, 11 and 12 as code; the readers and
  constants quoted in 6 and 8, including the writers of `ObjectBase::m_ai_signal`.

Also confirmed in the running game:

- the re-sampling, point for point on three race courses (Finding 3);
- the links, widths, corner values, side axes, sectors and the nearest route points of the respawn points, on three race
  courses and one battle course (Findings 2, 4 and 7);
- the `AIPathHandler` values of the table in Finding 5 for race, award and battle, when CPUs advance, and which settings
  `m_current_param` / `m_next_param` hold (Finding 5);
- flag 0x80 and `m_force_base_speed`, and the starting lanes (Finding 6);
- the respawn fallback to point 0 (Finding 7);
- the branch exclusion by linked objects (Finding 8);
- no read of `m_depth` / `m_depth_num`, in a race and in a battle (Finding 9);
- the crossing timing and the CPUs stopping at Kalimari Desert, the battle run-away from boards, and `m_is_far_behind`
  ending a crossing wait and being set only for CPUs far behind (Findings 10 and 13);
- Lakitu after 15 seconds without progress, the back-up sequence (started on purpose), a CPU pushing against a wall
  counting as slow, the faster count and Lakitu at the end of a 10-second back-up (Finding 11);
- the wall re-route and the meaning of the wall bit (Finding 12);
- the 7.5-second re-route, a player's Bullet Bill start, the end of a player's race and the dead-end path (Finding 13).

Likely:

- Flag 0x80 in battle is meant for jumps and ramps. The code shows centre + base speed + hop; the purpose is an interpretation.
- "Battle CPUs never trick without flag 0x80" assumes no battle CPU has a title mask (`AI::init` only sets it in single-player
  Grand Prix).
- The Mii title names of the `m_title_mask` bits (Finding 15): the value-to-bit switch is read in `AI::init`,
  the value-to-title order is taken from the message IDs.
- When each linked object opens its branch, except `MpBoard` and `packunLight` on Music Park: read from the writers of
  `m_ai_signal`, not watched in game. The states of `ShellFish`, `packunLight`, `WiiCar` and `GcTable` were not tied to what
  the player sees.
- The "trap" of Finding 11 (a CPU that keeps reversing) was seen only with a back-up started on purpose; that it can happen
  in a normal race follows from the code.
- The course creator advice on crossings, stuck CPUs and helper paths follows from the code and was not tested on a
  modified course.
- Coin-battle gathering and the back-up re-route every 120 frames were read in the code, not watched in game.
- What a dead-end path does depends on the memory after the empty array; it was 0 in both tests, which may not hold on
  every course.
- The effects of the Mii titles on lanes, hops and the drift start, the CPU level of online races and "no Mushroom while
  drifting" were read in the code (Findings 6 and 15), not watched in game.

Not re-checked in `eur2`: the detail of the Bullet Bill phases beyond the two flag tests and the flag 0x40 counter. The
end of a Bullet Bill held by flag 0x40 for 7 seconds was read in the code, not watched in game.

## Open questions

- What status bit 0x10000 (`accident_1` in the template) stands for, and `AIControlRace::m_skip_watch`, which switches off
  `watchPlayerAndSwitchCollision`.
- What the dead-end read gives on other courses (Finding 13).
- Which side of the turn the sign of `MapdataEnemyPoint::m_corner` stands for (Finding 4).
- Which of the two code paths explains the 65-frame crossing exit of the first Kalimari Desert run (Finding 10).
- What `max_search_y_offset == 1` means on the award course (`VehicleControlAI::m_award_flag`, Finding 6), and what
  `AIControlBattle::m_battle_type` 1 and 2 mean in coin battle (Finding 8).
- What `VehicleMove::m_drift_state`, `m_forward_dir` and `VehicleControlAI::m_collision_switch` stand for beyond the uses
  quoted.
- Not tested on a course with a modified KMP: helper paths added by hand, and the course-creator advice in general. Left for
  a later session.
