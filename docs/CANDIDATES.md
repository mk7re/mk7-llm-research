# Candidate topics

Subjects that could become research topics, each with where the idea comes from. Nothing here is established: a
research that picks one up treats the entry as a lead and verifies it in `eur2` first. How entries are added, picked up
and dropped is in [WORKFLOW.md](tooling/WORKFLOW.md#candidate-topics).

## Contents

- [Candidates](#candidates): subjects not researched yet, grouped by part of the game
- [Started](#started): candidates that became a research, named by subject
- [Dropped](#dropped): candidates rejected, and why

## Candidates

### Karts

- **`kart-movement-physics`**: how a kart moves: speed and acceleration, gravity and fall speed, the collision
  radius, how walls push a kart back, off-road and boost factors, gliding, cannons, driving under water (and what the
  `WaterDive` object, GOBJ 321, sets), and the respawn timing. The values are most likely in `Kart::VehicleMove`
  (`calcPosAtt`, `calcGndCollision`, `calcDriveHitWall`, `initColRadius`, `calcMoveControlGnd`, `calcMoveControlAir`,
  `calcMoveControlWing`, `calcMoveControlWingPath`, `execDashOne`) and probably in the kart parameter files.
  Source: the research on the KMPExpander culling preview, Open questions (its simulator uses guessed values; noted
  as a topic of its own at the user's request, 2026-10-29).

### Course data (KMP)

- **`kmp-glide-route`**: the glide route (KMP GLPT / GLPH): what every field of a glide point and a glide path does,
  how a gliding kart follows it, and how cannons use it, including byte +0x0F of a glide path (copied to
  `VehicleMove::m_is_cannon_wing_path` when a glide starts and tested by `ObjectWiiCannon::setReaction_fromKart`).
  Source: the research on course areas and cameras (AREA / CAME), Open questions and its section on cannons.

## Started

None yet.

## Dropped

None yet.
