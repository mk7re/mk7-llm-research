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
  Source: the KMPExpander culling preview work (its simulator used guessed values; noted as a topic of its own at the
  user's request, 2026-10-29). That work is now in KMPExpander upstream and its pending topic was removed (2026-11-18).

### Course data (KMP)

- **`kmp-glide-route`**: the glide route (KMP GLPT / GLPH): what every field of a glide point and a glide path does,
  how a gliding kart follows it, and how cannons use it, including byte +0x0F of a glide path (copied to
  `VehicleMove::m_is_cannon_wing_path` when a glide starts and tested by `ObjectWiiCannon::setReaction_fromKart`).
  Source: the research on course areas and cameras (AREA / CAME), Open questions and its section on cannons.

### Multiplayer (application layer)

These candidates cover what the game does with the data buffers that the connection layer hands it
(`Net::eNetworkBufferType`), and stop there: NEX, local wireless (UDS), matchmaking, Download Play transport and
everything closer to the wire are out of scope. Leads below come from `dlp` symbols and decompilation (2026-11-14);
the key functions were found ported into `eur2` by `mk7 port`, except `NetworkBufferController::procSplitBuffer_`.

- **`race-net-events`**: what the battle events carry and do, on top of the event channel that the research on race
  multiplayer documents (`NetworkEventModule`): the GameEvent types (`NetworkGameEventMgr`, received by
  `Object::BattleObjectMgrBase::receiveBuffer`), and `Field::ObjectIronBall::takeOver`, `Field::ObjectVisualSync` and
  `Object::CoinManager::syncCoin`, which the race research only names. The ItemEvent types are covered by the race
  research.
  Source: the research on race multiplayer, Open questions (what was left of the race multiplayer candidate,
  2026-11-16).

## Started

- Menu multiplayer (lobby, character and kart choice, course vote, race settings, spectators joining, and the
  shared buffer layer): took up `menu-multiplayer`.
- Race multiplayer (kart data, takeover, goals and ranks, item requests, the event channel, start and spectator
  synchronisation, the ItemSlot and ItemEvent buffers): took up `race-multiplayer`; the battle events stay as
  `race-net-events`.

## Dropped

None yet.
