# Race multiplayer

- Status: pending verification
- Asked: Start the research on the race multiplayer topic, use the menu multiplayer pending verification topic as a base
  (for research if needed and for the .patch)
  - Scope, from the candidate written on 2026-11-14: how a race or battle stays in sync between consoles once it
    starts (karts, items, events, ranking and goal, players leaving, spectators), at the level of the data buffers
    the connection layer hands the game. NEX, local wireless and everything closer to the wire are out of scope.
  - Base: the research on menu multiplayer, still pending verification, is used as a source for the buffer layer
    (packets, buffers, aids, SystemInfo) at the user's request. What this topic takes from it is restated where it is
    used. What this research found about the menu topic's own classes (two SystemInfo members) was added at the end
    of that topic's document, to be folded in by its next pass.
- Base commit: 843cc69f11cc3c8b057a1647c3a3c01d13a36186, with the patch of the research on menu multiplayer applied
  first: `race-multiplayer.patch` applies on top of it, not on the bare commit.
- Images: `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95); `dlp` only as the source of names (`mk7 port`).
  Nothing was tested in game: the emulator setup cannot connect two consoles yet.

## Contents

- [Overview](#overview): what was researched and found, for readers new to the topic
  - [Words used in this document](#words-used-in-this-document)
  - [Five buffers for the race](#five-buffers-for-the-race)
  - [Who drives which kart](#who-drives-which-kart)
  - [What a kart sends](#what-a-kart-sends)
  - [How the other consoles show a kart](#how-the-other-consoles-show-a-kart)
  - [Players who leave, and the CPUs](#players-who-leave-and-the-cpus)
  - [Items from item boxes](#items-from-item-boxes)
  - [Item limits and waiting times](#item-limits-and-waiting-times)
  - [Events: shells, explosions, battle objects](#events-shells-explosions-battle-objects)
  - [Goals, scores and ranks](#goals-scores-and-ranks)
  - [Starting together, watching, finishing](#starting-together-watching-finishing)
  - [What changes in the templates](#what-changes-in-the-templates)
- [Glossary](#glossary): classes, members and enums, then [functions](#functions) and [data](#data)
- [Findings](#findings): each claim with its evidence
  - [Sources and method](#sources-and-method)
  - [1. The KartData buffer](#1-the-kartdata-buffer)
  - [2. What NetData holds](#2-what-netdata-holds)
  - [3. Kart events](#3-kart-events)
  - [4. Who drives which kart](#4-who-drives-which-kart)
  - [5. A received kart](#5-a-received-kart)
  - [6. Takeover](#6-takeover)
  - [7. GameData: goals and scores](#7-gamedata-goals-and-scores)
  - [8. Agreeing on ranks](#8-agreeing-on-ranks)
  - [9. ItemSlot: item requests](#9-itemslot-item-requests)
  - [10. Item limits and waiting times](#10-item-limits-and-waiting-times)
  - [11. The event channel: ItemEvent and GameEvent](#11-the-event-channel-itemevent-and-gameevent)
  - [12. Starting the race together](#12-starting-the-race-together)
  - [13. Spectators catching up](#13-spectators-catching-up)
  - [14. The end of the race](#14-the-end-of-the-race)
  - [15. Corrections to the templates and to the menu research](#15-corrections-to-the-templates-and-to-the-menu-research)
- [Confidence](#confidence): what is certain, likely or a guess
- [Open questions](#open-questions): what was not resolved

## Overview

Once a multiplayer race or battle starts, every console simulates the whole race on its own and tells the others
what it alone knows: how the karts it drives move, which items they ask for, what its items do, and when its karts
reach the goal. There is no server and, for most things, no master: each console decides for the karts it drives,
and the others follow.

In short:

- Each console drives its own player's kart and sends it to the others about every frame; the other karts are
  replayed from what their consoles send ([What a kart sends](#what-a-kart-sends)).
- A replayed kart is not just moved to the received position: the receiving console drives it with the received
  buttons and stick and nudges it towards where it should be, and only teleports it when it is too far off
  ([How the other consoles show a kart](#how-the-other-consoles-show-a-kart)).
- The CPUs, and online the karts of players who leave, are given to one of the remaining consoles, chosen the same
  way on every console ([Players who leave, and the CPUs](#players-who-leave-and-the-cpus)).
- The roulette, in every race, leaves out items that would go over their limit on the course (one Blue Shell,
  Blooper, Bullet Bill, Lucky Seven or Fire Flower at a time, for example) or that are still in their waiting time
  (Lightning and Blooper: 30 seconds after any kart used one; none of the strong items at the very start)
  ([Item limits and waiting times](#item-limits-and-waiting-times)).
- Online, an item from an item box must also be accepted by every other console, which applies the same count limits;
  a refused item is replaced. The same buffer tells the others which item each kart holds and uses
  ([Items from item boxes](#items-from-item-boxes)).
- What items and battle objects do is sent as events, each with the frame at which every console runs it. Item
  events name the item by its owner and serial number, so that every console acts on the same shell or banana
  ([Events](#events-shells-explosions-battle-objects)).
- Goals, times and scores are agreed in several steps, so that every console ends with the same ranking
  ([Goals, scores and ranks](#goals-scores-and-ranks)).
- The race starts on every console at the same moment, after a shared countdown of 3 seconds corrected for the
  delay between consoles ([Starting together, watching, finishing](#starting-together-watching-finishing)).

All of this was read in the game's code (`eur2`, the European version 1.2). Nothing could be tested in game; what
rests on reading alone, or on parts of the code that were only skimmed, is marked as probable in
[Confidence](#confidence).

### Words used in this document

- **Console**, **racer**, **spectator**, **CPU**, **aid**, **player id**, **master** and **buffer** mean what they
  mean in the research on menu multiplayer: a console is one 3DS, a racer drives in the race, a spectator only
  watches, an aid (0 to 7) numbers the racers and CPUs, and a player id is equal to the aid. A **buffer** is one of
  the eleven kinds of data in the packet each console sends a few times per second; only the latest data of each
  kind is sent.
- **Race frame**: the number of frames since the race's countdown, counted on each console.
- **Driving a kart** (on a console): that console runs the kart's controls (the player's pad or the CPU logic) and
  sends its state. Every other console **replays** the kart from what it receives.
- **Takeover**: a console starts driving a kart that nobody drives.
- **Goal**: the end of a kart's race (its finish time) or, in battles, its final score.

### Five buffers for the race

The race uses five of the eleven buffers. All five are sent in the same packet as the menus' buffers, at the same
rate ([Finding 1](#1-the-kartdata-buffer)).

| Buffer | What it carries |
| --- | --- |
| KartData | the state of each kart the console drives |
| ItemSlot | the item each of its karts asks for, and the answers to the other karts' requests |
| ItemEvent | what its items do (a shell hits, a Bob-omb explodes, a Lucky Seven turns...) |
| GameEvent | what happens to the battle objects (coins and balloons in battles) |
| GameData | goals, times and scores, and how far the consoles agree on them |

### Who drives which kart

At the start of a race, every console drives only its own player's kart. Every other kart, the CPUs included, is
replayed. Right after, the CPUs are handed out to the consoles: each CPU is driven by one of the human racers'
consoles, which runs the usual CPU logic for it and sends it like its own kart
([Findings 4](#4-who-drives-which-kart) and [6](#6-takeover)).

### What a kart sends

Every frame, each console writes the state of every kart it drives into its KartData buffer, as one block of 72
bytes per kart. A packet carries at most four such blocks: the console's own kart and up to three CPUs
([Finding 1](#1-the-kartdata-buffer)). A block holds ([Finding 2](#2-what-netdata-holds)):

- the console's frame, so that older blocks are ignored;
- the buttons (accelerate, brake, hop) and the stick, each stick axis reduced to 31 steps either way;
- the position (in whole units), speed, direction, drift, boost and the timers of star, ink, lightning, being
  squashed and blinking;
- the coins (or, in balloon battles, the balloons), the glider route, the pipe warp and the respawn point;
- what hit the kart, and from where;
- a set of **event bits**, each flipped when something happens: a hop, a trick, a throw forward or back, a new boost,
  a bump with another kart, or a request to teleport the kart. Because a bit is flipped rather than set, an event
  is seen even when the packets before it were lost, as long as the same event does not happen twice between two
  packets ([Finding 3](#3-kart-events)).

### How the other consoles show a kart

A replayed kart is driven on each console with the buttons and stick it received, through the normal physics, so
that it moves smoothly between packets. The console measures how many frames old each block is, keeps the last 16
received positions and the kart's own last 60 positions, and steers the kart towards the received position for the
same moment. Speed, drift, boosts, star, ink and lightning, gliders, Bullet Bill and Lakitu are copied from the block;
crashes are replayed from what hit the kart. When the kart is far from where it should be for too long, it is
teleported. When no block arrives for 60 frames, the buttons are released, and the stick fades out
([Finding 5](#5-a-received-kart)).

### Players who leave, and the CPUs

Karts that nobody drives (the CPUs, and online the karts of consoles that left) get a new owner. Every console
computes the same owner from the same list: the first human racer, in a fixed order starting two places after the
kart's aid, that is still connected. The new owner switches the kart to CPU logic and starts sending it; the first
block it sends asks the others to teleport the kart to its position. In local play, the kart of a player who left is
probably not taken over ([Finding 6](#6-takeover)).

### Items from item boxes

When a kart driven by a console hits an item box, the roulette starts and the console asks the others for the item
the roulette chose: it sends the item and the frame of the request in its ItemSlot buffer. Each other console checks,
for every kart it drives (its player and the CPUs it took over), that the item would not go over the limit of that
item on the course (counting the items on the course, those held by karts, and those already granted) and answers yes
or no. The item is accepted when every console said yes; when any said no, the kart gets a replacement item; after
120 frames (2 seconds) without all answers it is accepted anyway. When the roulette stops while the answers are still
missing, the kart gets the replacement item ([Finding 9](#9-itemslot-item-requests)).

The same buffer tells the other consoles what each kart holds (which item, and whether one, two or three of it) and
what it uses (the item around or behind it, and how many are left). A console sends this for its own kart in the
main fields and for up to three karts it took over in a second set of fields. The other consoles take a replayed
kart's held item from it, and remove the items around or behind it when the owner says it has fewer, or has started
a new item ([Finding 9](#9-itemslot-item-requests)).

### Item limits and waiting times

Before the network is asked anything, the roulette of the console that drives the kart already leaves out the items
that are not allowed at that moment. This happens in every race, online or not ([Finding 10](#10-item-limits-and-waiting-times)).
Two kinds of rules decide it, and online the other consoles apply the first one again when they answer.

#### How many may be out at once

Each item has a limit, and each kind counts for a number of items: the triple
items and the Fire Flower count as 3, a Lucky Seven as 7, the Mushrooms and the Golden Mushroom as nothing, the others
as 1. An item is left out when the items of its kind on the course and held by karts, plus what it counts for, would
go over the limit. So, with all items allowed:

| Item | At most at once |
| --- | --- |
| Lucky Seven | 1 (counts as 7, limit 7) |
| Fire Flower | 1 (counts as 3, limit 3) |
| Blue Shell, Blooper, Bullet Bill | 1 |
| Star | 2 |
| Lightning, Super Leaf | 3 |
| Green Shell, Red Shell, Banana, Bob-omb | 8 (a triple counts as 3) |
| Mushroom, Triple Mushroom, Golden Mushroom | no limit |

With a single-item setting (only Mushrooms, Shells, Bananas or Bob-ombs), Lightning, Super Leaf and Fire Flower drop
to 1 and the allowed item gets its higher offline limit. A Lucky Seven is also left out unless there is room for one
more Banana, Green Shell, Red Shell, Bob-omb, Star, Mushroom and Blooper, the items that circle the kart. While any kart
has a Lucky Seven, or the kart itself is using a Fire Flower, a Lucky Seven or a triple item, the roulette gives no
Fire Flower and no triple item (and, in the second case, no Lucky Seven).

#### Waiting times

Some items are left out for a while after one was used. Each console keeps its own timers, which start at zero with
the race, so every one of these items is also left out at the start:

| Item | Left out |
| --- | --- |
| Lightning, Blooper | during the first 30 seconds, and for 30 seconds after one was used by any kart: the use is sent to every console, which restarts its own timer |
| Lucky Seven | during the first 30 seconds, and for 30 seconds after a kart of this console used one |
| Blue Shell | for 22 seconds after a kart of this console used one, and during the first 34 seconds after the countdown starts |
| Bullet Bill, Golden Mushroom | during the first 30 seconds of the race |

So Lightning is rare in practice: once one strikes, no roulette offers another for 30 seconds. The count limit itself
still lets up to three karts hold one at the same time; nothing found in the code prevents that (to be tested in
game). A console that receives a Lightning or Blooper less than 15 seconds after its own last one ignores it
([Finding 11](#11-the-event-channel-itemevent-and-gameevent)).

### Events: shells, explosions, battle objects

What items and battle objects do goes through an event channel shared by ItemEvent and GameEvent. A console that
causes an event (its shell hits someone, its Bob-omb explodes) adds it to its list with the race frame at which it
must happen. The list is sent with every packet for 4 seconds (240 frames), so a lost packet does no harm. Each
receiving console keeps every event once, orders them by frame, and runs each when its race frame reaches the event's
frame ([Finding 11](#11-the-event-channel-itemevent-and-gameevent)). A console ignores its own events, which it has
already carried out; a spectator sends none and runs the others' events as soon as they arrive.

The ItemEvent buffer carries eleven kinds of events. Each names the item by its owner and a number the owner gives
every item object it creates, so that every console acts on the same shell or banana
([Finding 11](#11-the-event-channel-itemevent-and-gameevent)):

| Event | Sent when | The other consoles |
| --- | --- | --- |
| use | a kart uses an item | for a Lightning, Blooper or Super Leaf only: make the replayed kart use it here (the others show through the kart's state or the item's own events) |
| free move | an item is thrown or dropped | start it from the sender's position, speed and gravity, moved on by the delay |
| lock on | a Red Shell, Blue Shell or Bob-omb picks a target | aim it at the same kart |
| explode | a Bob-omb or Blue Shell explodes | make it explode |
| tail swing | a Super Leaf swings | swing it |
| held item hit | an item held around or behind a kart is knocked off | remove that item (the one nearest to the hitting kart) |
| destroyed (two kinds) | an item is destroyed, by itself or by something else | remove it; if it does not exist here yet, keep the event and apply it when the item appears |
| expired | a Super Leaf's time is up | remove it |
| Lucky Seven, Lucky Seven turn | an item of a Lucky Seven is used; the ring turns | remove that item from the ring; turn the ring the same way |

What the GameEvent buffer (battle objects) carries was not researched.

### Goals, scores and ranks

When a kart a console drives reaches the goal, the console records the kart's time (or, in battles, its score) and
marks it in its GameData buffer. A console only accepts GameData that adds information: a packet that would take back
a goal or change a known time is dropped. The consoles then agree in steps: a goal is first known, then known by every
console, and a rank is fixed only when no kart still racing could beat it. Departures are agreed the same way. When
only one rank is left, it goes to the last kart, and the ranking is final
([Findings 7](#7-gamedata-goals-and-scores) and [8](#8-agreeing-on-ranks)). The steps were only partly read
(probable).

### Starting together, watching, finishing

- **Start.** Every console counts down 3 seconds before the race starts. Each one sends its countdown and lowers its
  own to the smallest countdown of the others, corrected for the delay of their packets, so that all reach zero at
  about the same time ([Finding 12](#12-starting-the-race-together)).
- **Spectators** (consoles that joined during a race) follow the race of another console. They count the race's
  frames and, when they are behind the racers, skip frames to catch up, more often the further behind they are
  ([Finding 13](#13-spectators-catching-up)).
- **End.** When the race is over for everybody, every kart is switched to CPU logic and nothing more is sent or
  received for the karts ([Finding 14](#14-the-end-of-the-race)).

### What changes in the templates

The research names the replay state of a kart (`Kart::VehicleControlNet`, which had no member named), the bits of the
kart block, the item slot data and its states (and corrects their sizes), renames one item event type and one flag of
the free-move event, the event slots, the classes of the GameData buffer (new in the templates), and the start and
spectator synchronisation
([Finding 15](#15-corrections-to-the-templates-and-to-the-menu-research)). Two members of SystemInfo that the research on
menu multiplayer thought unused carry the start countdown and the spectators' frame counter; they are named by that
research, not by this one.

## Glossary

All offsets are those of `eur2`, relative to the start of the class of the table. Status `existing` means named in
`template/` (or in the patch of the research on menu multiplayer), `renamed` that this patch changes the name, `new`
that this patch adds it.

### Kart::NetData (size 0x48, template/Kart/NetData.hpp)

One kart's block in the KartData buffer. Only the members this research changed or uses are listed.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_frame` | 0x00 | `s32` | existing | sender's frame; `read` keeps only newer blocks |
| `m_kart_data` | 0x04 | `KartData` | existing | buttons, stick, event bits ([Finding 3](#3-kart-events)) |
| `m_status_flags` | 0x08 | `VehicleMove::StatusFlags` | existing | |
| `m_sender_player_id` | 0x0C | `s8` | existing | player id of the kart |
| `m_coins` | 0x0D | `u8` | existing | |
| `m_balloon_points`, `m_balloon_count` | 0x0E, 0x0F | `u8` | existing | balloon battles only |
| `m_position` | 0x10 | `sead::Vector3<s16>` | existing | whole units |
| `m_velocity` | 0x16 | `sead::Vector3<s16>` | existing | × 256, length at most 50 |
| `m_forward_dir` | 0x1C | `sead::Vector3<s16>` | renamed | was `m_angular_velocity`; `VehicleMove::m_forward_dir` × 1024 |
| `m_turning_speed`, `m_forward_speed` | 0x22, 0x24 | `s16` | existing | × 1024, × 256 |
| `m_drift_steering`, `m_directional_speed` | 0x26, 0x28 | `s16` | existing | × 64 |
| `m_boost_type`, `m_boost_speed`, `m_boost_frames` | 0x2D, 0x2E, 0x30 | | existing | speed × 256 |
| `m_star_timer` to `m_blink_timer` | 0x31 to 0x35 | `u8` | existing | frames / 4 |
| `m_respawn_point_id` | 0x36 | `s8` | existing | -1: none |
| `m_hit_item_type_id`, `m_hit_player_id` | 0x37, 0x38 | `u8` | existing | 8: no player |
| `m_accident_type` | 0x39 | `VehicleReact::EAcdType` | existing | `Dummy` (0x12): none |
| `m_hit_direction_1`, `m_hit_direction_2` | 0x3A, 0x40 | `sead::Vector3<s16>` | existing | × 256, lowest bit of y set when present |

#### Kart::NetData::KartData (bit field, 4 bytes)

| Bits | Name | Status | Note |
| --- | --- | --- | --- |
| 0x1, 0x2, 0x4 | `accelerate_forwards`, `accelerate_backwards`, `hop` | existing | `VehicleControl::m_controls` |
| 0x10 | `stick_x_positive` | new | |
| 0x3E0 | `stick_x` | new | \|`VehicleControl::m_stick_x`\| × 31 |
| 0x400 | `stick_y_positive` | new | |
| 0xF800 | `stick_y` | new | \|`VehicleControl::m_stick_y`\| × 31 |
| 0x10000 | `drift_jump` | new | event bits from here on: flipped once per event |
| 0x20000 | `warp` | existing | |
| 0x3FC0000 | `hit_kart` | new | one bit per player id |
| 0x4000000 to 0x40000000 | `jump_action`, `twist`, `throw_forward`, `throw_backward`, `dash_restart` | new | |

### Kart::VehicleControlNet (size 0xBE8, template/Kart/Vehicle/VehicleControlNet.hpp)

A base class of `Kart::Vehicle` (`Vehicle` → ... → `VehicleMove` → `VehicleControlAI` → `VehicleControlNet` →
`VehicleControl` → `VehicleBase`): the network state of a kart. All its members are new.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_net_send_data` | 0x11C | `u8[0x48]` | new | a `NetData`; typed as bytes to avoid an include cycle |
| `m_net_recv_datas` | 0x164 | `u8[2][0x48]` | new | two `NetData` |
| `m_net_recv_data` | 0x1F4 | `NetData *` | new | newest received block |
| `m_net_recv_data_prev` | 0x1F8 | `NetData *` | new | the block before it |
| `m_net_recv_frame` | 0x1FC | `s32` | new | own frame when the newest block arrived; -1 at start |
| `m_net_delay` | 0x200 | `f32` | new | smoothed age of the received blocks, in frames |
| `m_net_delay_weight` | 0x204 | `f32` | new | |
| `m_net_track_delay` | 0x208 | `f32` | new | |
| `m_own_track` | 0x20C | `NetTrackRing` | new | ring over `m_own_track_storage` |
| `m_own_track_storage` | 0x21C | `NetTrackData[60]` | new | |
| `m_recv_track` | 0x99C | `NetTrackRing` | new | ring over `m_recv_track_storage` |
| `m_recv_track_storage` | 0x9AC | `NetTrackData[16]` | new | |
| `m_net_correction` | 0xBAC | `sead::Vector3f` | new | |
| `m_net_track_offset` | 0xBB8 | `sead::Vector3f` | new | |
| `m_net_track_rotation` | 0xBC4 | `sead::Quatf` | new | |
| `m_net_track_frame` | 0xBD4 | `u32` | new | |
| `m_net_warp_frame` | 0xBD8 | `u32` | new | |
| `m_net_event_send_bits` | 0xBDC | `u32` | new | `ENetEvent` |
| `m_net_event_recv_bits` | 0xBE0 | `u32` | new | `ENetEvent` |
| `m_network_engine` | 0xBE4 | `Net::NetworkEngine *` | new | |
| `NetTrackData::forward_dir` | 0x0C | `sead::Vector3f` | new | was unnamed |
| `NetTrackRing` (size 0x10) | | | new | `m_entries`, `m_capacity`, `m_head`, `m_count` |

#### Kart::VehicleControlNet::ENetEvent (enum : u32)

New; named by this research.

| Value | Name | Note |
| --- | --- | --- |
| 0x1 | `DRIFT_JUMP` | |
| 0x2 | `WARP` | |
| 0x4 | `HIT_KART_0` | `HIT_KART_0 << n` for player id n |
| 0x400 | `JUMP_ACTION` | |
| 0x800 | `TWIST` | |
| 0x1000 | `THROW_FORWARD` | |
| 0x2000 | `THROW_BACKWARD` | |
| 0x4000 | `DASH_RESTART` | |

### Kart::VehicleBase (template/Kart/Vehicle/VehicleBase.hpp)

Existing, unchanged; the members the race uses.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_player_id` | 0x84 | `s32` | existing | |
| `m_is_net_object` | 0x9C | `bool` | existing | the race is a network race |
| `m_is_net_send` | 0x9D | `bool` | existing | this console drives the kart |
| `m_is_net_recv` | 0x9E | `bool` | existing | this console replays the kart |
| `CreateArg::is_player` | 0x19 | `bool` | existing | in a network race: the kart is replayed ([Finding 4](#4-who-drives-which-kart)) |

### Net::NetworkItemSlotMgr (size 0x26C, template/Net/NetworkItemSlotMgr.hpp)

The ItemSlot manager, `NetworkEngine::m_network_item_slot_mgr`. The template gave size 0x264, and 0x254 for its
`Buffer`, which is 0x264. `Buffer` is `NetworkDataManager<Node>`: its `m_node_data` (0x10) is the node this console
sends, built by `Buffer::commit`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_buffer` | 0x08 | `Buffer` | existing | |
| `Buffer::m_nodes` | 0x71 | `Node[8]` | existing | by kart aid: the state of every kart, as this console knows it |
| `Buffer::m_is_idle` | 0x240 | `bool` | new | set outside races; `calc` does nothing |
| `Buffer::m_request_frames` | 0x244 | `s32[8]` | new | by aid: race frame of the last request |
| `Node::m_frame` | 0x00 | `u8` | existing | race frame of the request / 8 |
| `Node::m_stock_item` | 0x01 | `Item::eItemSlot` | existing | the item asked for or held; `Empty` (0xFF): none |
| `Node::m_equip_item` | 0x02 | `Item::eItemSlot` | existing | the item in use |
| `Node::m_stock_item_state` | 0x03 | `u8` | existing | `EStockItemState` |
| `Node::m_equip_item_state` | 0x04 | `u8` | existing | `EEquipItemState` |
| `Node::m_accepted_request_aid_bits` | 0x05 | `u8` | renamed | was `m_player_bit`; karts whose request the sender of the node accepts |
| `Node::m_equip_items_used` | 0x06 | `u8` | existing | low byte of `KartItem::m_equip_items_used`: changes with each new item in use |
| `Node::m_judged_frames` | 0x07 | `u8[8]` | renamed | was `m_0x7`; by kart aid, the `m_frame` of the request the sender judged |
| `Node::m_takeover_aids` | 0x0F | `s8[3]` | renamed | was `m_0xF`; karts the sender took over; -1: none |
| `Node::m_takeover` | 0x12 | `Takeover` | existing | the fields 0x00 to 0x04 and 0x06 for those karts, one column each |

#### Net::NetworkItemSlotMgr::EStockItemState (enum class : u32)

Existing (name from `dlp`, `GetNumStockItem(EStockItemState)`), empty in the template; values named by this research.

| Value | Name | Note |
| --- | --- | --- |
| 0 | `NONE` | |
| 1 | `REQUESTED` | waiting for the answers |
| 2 | `DECIDED` | accepted or replaced |
| 3 | `HOLD_3` | `GetNumStockItem` returns 3 |
| 4 | `HOLD_2` | 2 |
| 5 | `HOLD_1` | 1; also a Lucky Seven |

#### Net::NetworkItemSlotMgr::EEquipItemState (enum class : u32)

Existing (name from `dlp`, `GetNumEquipItem(EEquipItemState)`), empty in the template; values named by this research.
`GetNumEquipItem` returns 8 minus the value, for values 1 to 7.

| Value | Name | Note |
| --- | --- | --- |
| 0 | `NONE` | |
| 1 to 7 | `LEFT_7` to `LEFT_1` | items left |

### Item::ItemDirector (template/Item/ItemDirector.hpp)

Existing, unchanged; the members the item limits and events use.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_gesso_time` to `m_kinokop_time` | 0x5C to 0x70 | `s32` | existing | Blooper, Lightning, Blue Shell, Bullet Bill, Lucky Seven, Golden Mushroom waiting times, in frames |
| `m_special_items_threshold_passed` | 0x74 | `bool` | existing | |
| `m_invalid_flag` | 0x78 | `eInvalidFlag` | existing | one bit per `eItemSlot` the roulette must not give |
| `m_stand_item_objs` | 0xA8 | `sead::PtrArray<ItemObjBase>` | existing | |
| `m_kart_items` | 0xC0 | `sead::PtrArray<KartItem>` | existing | by player id |
| Lightning user | 0xFC | `s32` | | unnamed |
| pending events | 0x11C to 0x128 | | | unnamed; ring of `SlotData`: entries, capacity, head, count |

### Net::NetworkEngine (template/Net/NetworkEngine.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_network_item_event_mgr` | 0x2A4 | `NetworkItemEventMgr *` | existing | |
| `m_network_item_slot_mgr` | 0x2D0 | `NetworkItemSlotMgr *` | new | |

### Net::NetworkItemEventDataMgr (template/Net/NetworkItemEventDataMgr.hpp)

The ItemEvent data manager, with its `NetworkEventModule` at 0x50; it lives in `NetworkItemEventMgr` at 0x08. Its
layout is left as it is in the template (size 0x1).

| Member or value | Offset | Status | Note |
| --- | --- | --- | --- |
| event module | 0x50 | | unnamed |
| handler | 0x114 | | unnamed; calls `ItemDirector::_itemEventRecvHandler` |
| `SlotData::frame_count` | 0x00 | existing | the event's `m_exec_frame` |
| `SlotData::item_type`, `event_type` | 0x04, 0x05 | existing | the first two bytes of the event data |
| `SlotData::unk_0x6` | 0x06 | existing | comment changed: not set by the receiver |
| `SlotData::data_size`, `data` | 0x07, 0x08 | existing | the rest of the event data |
| `SSelfMove` (size 0x24) | | existing | the data of `SelfMove`; its size confirmed |
| `SSelfMove::is_serial_kept` | 0x03 | renamed | was `is_deflected` |

#### Net::NetworkItemEventDataMgr::EEventType (enum class : u8)

Existing. Data and senders are in [Finding 11](#11-the-event-channel-itemevent-and-gameevent).

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `InitBurst` | existing | |
| 1 | `SevenFrame` | existing | |
| 2 | `SelfMove` | existing | |
| 3 | `UpdateKartItem_EquipHit` | renamed | was `SevenInitUse` |
| 4 | `UpdateKartItem_DestroyOther` | existing | |
| 5 | `UpdateKartItem_DestroySelf` | existing | |
| 6 | `InitSpin` | existing | |
| 7 | `Action` | existing | |
| 8 | `Seven` | existing | |
| 9 | `InitUse` | existing | |
| 10 | `UseExpire` | existing | |

### Net::NetworkEventModule (template/Net/NetworkEventModule.hpp)

The event channel shared by ItemEvent and GameEvent. Its own layout is left as it is in the template (size 0x1);
the offsets below are those read in the code.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| active | 0x01 | `bool` | | unnamed; set by `initRace`, cleared by `finalizeRace` |
| run at once | 0x04 | `bool` | | unnamed; events run as soon as they arrive (spectators) |
| handler | 0x08 | `IDelegate2R *` | | unnamed |
| slots by aid | 0x0C | `sead::Buffer<Slot>[8]` | | unnamed; one per console |
| ordered list | 0x4C | | | unnamed; first slot at 0x60 |
| send buffer: capacity, data, size | 0x70, 0x74, 0x78 | | | unnamed |
| buffer size, slots per console, data size | 0x80, 0x84, 0x88 | `s32` | | unnamed; set by `init` |
| receive only | 0x8C | `bool` | | unnamed; nothing is sent (spectators) |
| local aid | 0x90 | `s32` | | unnamed |
| event counter | 0x94 | `s32` | | unnamed; next `EventHeader::m_index` |
| `EventHeader` (size 0x4) | | | new | `m_index` (u8), `m_size` (u8), `m_exec_frame` (u16) |
| `Slot::m_is_used` | 0x00 | `bool` | new | |
| `Slot::m_is_handled` | 0x01 | `bool` | new | |
| `Slot::frame` | 0x04 | `u32` | existing | race frame when the slot was filled |
| `Slot::m_is_seen` | 0x08 | `bool` | new | |
| `Slot::m_aid` | 0x0C | `s32` | new | sender |
| `Slot::m_prev`, `Slot::m_next` | 0x10, 0x14 | `Slot *` | new | ordered list |
| `Slot::m_header` | 0x18 | `EventHeader` | new | |
| `Slot::m_data_capacity` | 0x1C | `u32` | new | |
| `Slot::m_data` | 0x20 | `u8 *` | new | |

### Net::NetworkGameDataFormat (size 0x30, template/Net/NetworkGameMgr.hpp)

New in the templates (name from `dlp`). What each console sends in the GameData buffer; the bitmaps are by aid.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_goal_aid_bits` | 0x00 | `u8` | new | goals the sender knows |
| `m_goal_confirmed_aid_bits` | 0x01 | `u8` | new | goals every connected console has |
| `m_disconnected_aid_bits` | 0x02 | `u8` | new | |
| `m_disconnect_confirmed_aid_bits` | 0x03 | `u8` | new | |
| `m_takeover_goal_aid_bits` | 0x05 | `u8` | new | goals of karts the sender took over |
| `m_accepted_takeover_goal_aid_bits` | 0x06 | `u8[8]` | new | by aid of the owner |
| `m_scores` | 0x10 | `s32[8]` | new | by aid; time or points; -1: none |

### Net::NetworkGameDataManager (size 0x90, template/Net/NetworkGameMgr.hpp)

New in the templates (name from `dlp`): `NetworkDataManager<NetworkGameDataFormat>`, with `m_node_data` at 0x10 and
`unk` at 0x7C.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_received` | 0x80 | `sead::Buffer<NetworkGameDataFormat>` | new | by aid |
| `m_is_before_start` | 0x88 | `bool` | new | |
| `m_is_rank_fixed` | 0x89 | `bool` | new | |
| `m_network_game_mgr` | 0x8C | `NetworkGameMgr *` | new | |

### Net::NetworkGameMgr (size 0xC4, template/Net/NetworkGameMgr.hpp)

New in the templates (name from `dlp`). An `Object::Actor`, `NetworkEngine::m_network_game_mgr`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_data_manager` | 0x08 | `NetworkGameDataManager` | new | |
| `m_rank` | 0x98 | `Rank *` | new | |
| `m_is_race_active` | 0x9C | `bool` | new | set by `initRace`, cleared by `finalizeRace` |
| `m_is_alone` | 0x9D | `bool` | new | set by `calc` when only the local console is left |
| `m_goal_frame_counter` | 0xC0 | `u32` | new | |

#### Net::NetworkGameMgr::Rank (size 0xC8)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `Type` | | `enum class : s32` | new | 1 `TIME`, 2 `SCORE` (the `dlp` name of the enum, values named by this research) |
| `m_data_manager` | 0x00 | `NetworkGameDataManager *` | new | |
| `m_takeover_migration` | 0x04 | `TakeoverMigration *` | new | |
| `m_policy` | 0x08 | `void *` | new | points to 0x0C or 0x10 |
| `m_policy_time`, `m_policy_score` | 0x0C, 0x10 | `void *` | new | vtables of `PolicyTime` and `PolicyScore` |
| `m_my_score` | 0x18 | `s32` | new | |
| `m_is_my_goal` | 0x1C | `bool` | new | |
| `m_is_finished` | 0x1F | `bool` | new | |
| `m_goal_confirmed_aid_bits` | 0x20 | `u8` | new | |
| `m_disconnect_confirmed_aid_bits` | 0x21 | `u8` | new | |
| `m_auto_rank_aid_bits` | 0x22 | `u8` | new | |
| `m_disconnected_aid_bits` | 0x24 | `u8` | new | |
| `m_ranks`, `m_auto_ranks` | 0x28, 0x48 | `s32[8]` | new | by aid; -1: none |
| `m_aids_by_rank`, `m_aids_by_auto_rank` | 0x68, 0x88 | `s32[8]` | new | |
| `m_scores` | 0xA8 | `s32[8]` | new | by aid |

#### Net::NetworkGameMgr::TakeoverMigration (size 0x5C)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_data_manager` | 0x00 | `NetworkGameDataManager *` | new | |
| `m_owner_player_ids` | 0x04 | `s32[8]` | new | by aid; -1: none |
| `m_handler` | 0x44 | `sead::IDelegate2<s32, s32> *` | new | the mode manager's takeover handler |
| `m_lost_aid_bits`, `m_lost_aid_bits_prev` | 0x48, 0x49 | `u8` | new | |
| `m_absent_aid_bits` | 0x4B | `u8` | new | slots without a human racer |
| `m_taken_over_by_me_aid_bits` | 0x4C | `u8` | new | |
| `m_handled_aid_bits` | 0x4E | `u8` | new | |
| `m_is_enabled` | 0x4F | `bool` | new | |
| `m_take_over_humans` | 0x50 | `bool` | new | |
| `m_takeover_goal_aid_bits` | 0x58 | `u8` | new | |

### Net::NetworkSystemSendFormat, Net::NetworkSystemInfo, Net::NetworkSystemInfoManager

Classes of the research on menu multiplayer. The first four members are named by that research (its next pass picks
them up from what this research added to its document); until then they are `m_spare_u16` and two unnamed bytes in
its patch. The others are added by this patch.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `NetworkSystemSendFormat::m_start_countdown` | 0x08 | `u16` | existing | menu research; ms |
| `NetworkSystemSendFormat::m_sync_frame` | 0x1C | `u16` | existing | menu research |
| `NetworkSystemInfo::m_start_countdown` | 0xEE | `u16` | existing | menu research |
| `NetworkSystemInfo::m_is_start_counting` | 0x104 | `bool` | existing | menu research |
| `NetworkSystemInfoManager::m_sync` | 0x248 | `Sync *` | new | |
| `NetworkSystemInfoManager::m_frame_sync` | 0x24C | `FrameSync *` | new | |
| `NetworkSystemInfoManager::m_is_sync_started` | 0x250 | `bool` | new | |
| `Sync` (size 0x58) | | | new | `m_state` (`NetworkStateManager<Sync>`, 0x04), `m_is_syncing` (0x50), `m_system_info` (0x54) |
| `FrameSync` (size 0x14) | | | new | `m_system_info` (0x00), `m_wait` (0x08), `m_frame` (u16, 0x0C), `m_is_active` (0x0E), `m_target_player_id` (0x10) |

### Functions

Names marked `new` were given by this research; the others are ported from `dlp` (`mk7 port`).

| Name | Address (eur2) | Status | Note |
| --- | --- | --- | --- |
| `Item::GetNum_InItemType` | 0x002cd868 | existing | |
| `Item::GetNum_InItemType_Net` | 0x002d0418 | existing | |
| `Item::ItemDirector::_calcInvalidFlag` | 0x002bbbc0 | existing | |
| `Item::ItemDirector::_calcKeyInput_EachPlayer` | 0x002be26c | existing | |
| `Item::ItemDirector::_calcNet` | 0x002be908 | existing | |
| `Item::ItemDirector::_entryItem` | 0x002ba120 | existing | |
| `Item::ItemDirector::_isReserveSeven` | 0x002bb884 | existing | |
| `Item::ItemDirector::_isReserveSevenImpl` | 0x002bca18 | existing | |
| `Item::ItemDirector::_itemEventRecvHandler` | 0x002bcd8c | existing | |
| `Item::ItemDirector::calcBeforeStructure` | 0x002bca64 | existing | |
| `Item::ItemDirector::clearItem` | 0x002befac | existing | |
| `Item::ItemDirector::emitItem` | 0x002beeec, 0x002bef4c | existing | two overloads |
| `Item::ItemDirector::getReplacementItem` | 0x002bc914 | existing | |
| `Item::ItemDirector::initBeforeStructure` | 0x002bcc2c | existing | |
| `Item::ItemDirector::slot_StartSlot` | 0x002bb320 | existing | |
| `Item::ItemObjBase::stateInitUse` | 0x002b56ec | existing | |
| `Item::ItemObjBase::stateSelfMove` | 0x002b5c2c | existing | |
| `Item::ItemObjBase::updateKartItem_EquipItemExit` | 0x002b7778 | existing | |
| `Item::ItemObjBomhei::_calcSearch` | 0x002c1e80 | existing | |
| `Item::ItemObjBomhei::stateInitBurst` | 0x002c35d8 | existing | |
| `Item::ItemObjBomheiDirector::setBurst` | 0x002d0a04 | existing | |
| `Item::ItemObjBomheiDirector::setState_LockOn` | 0x002d0850 | existing | |
| `Item::ItemObjDirectorBase::setState_SelfMove_Force` | 0x002ce794 | existing | |
| `Item::ItemObjDirectorBase::vanishEquip_NearHitPos` | 0x002ce4f0 | existing | |
| `Item::ItemObjDirectorBase::vanishEquip_One` | 0x002cdd90 | existing | |
| `Item::ItemObjDirectorBase::vanish_Force` | 0x002cda50 | existing | |
| `Item::ItemObjDirectorBase::vanish_Force_FromOwner` | 0x002ce73c | existing | |
| `Item::ItemObjKouraB::searchKart` | 0x002c519c | existing | |
| `Item::ItemObjKouraBDirector::setBurst` | 0x002d0e9c | existing | |
| `Item::ItemObjKouraBDirector::setState_LockOn` | 0x002d0d60 | existing | |
| `Item::ItemObjKouraR::searchKart` | 0x002c8b08 | existing | |
| `Item::ItemObjKouraRDirector::setState_LockOn` | 0x002d0fdc | existing | |
| `Item::ItemObjSevenDirector::_sendEvent` | 0x002cf2bc | existing | |
| `Item::ItemObjSevenDirector::entry` | 0x002cfeac | existing | |
| `Item::ItemObjSevenDirector::isAroundEquip` | 0x002cf370 | existing | |
| `Item::ItemObjSevenDirector::setState_SelfMove_Force_Seven` | 0x002cfd64 | existing | |
| `Item::ItemObjSevenDirector::vanishAroundEquip` | 0x002cf820 | existing | |
| `Item::ItemObjTail::stateInitSpin` | 0x002b97d0 | existing | |
| `Item::ItemObjTailDirector::spinTrig` | 0x002cf018 | existing | |
| `Item::ItemSlot::_calcNetKartSlot` | 0x002d13a0 | existing | |
| `Item::ItemSlot::stateSpin` | 0x002d184c | existing | |
| `Item::KartItem::_setStockItem` | 0x002d1f3c | existing | |
| `Item::KartItem::_vanishEquip_Hang` | 0x002d1f78 | existing | |
| `Item::KartItem::_vanishEquip_Multi` | 0x002d1fe8 | existing | |
| `Item::KartItem::isNetRecv` | 0x00506710 | existing | |
| `Item::KartItem::setEquipInfo` | 0x002d1dcc | existing | |
| `Kart::Director::calcBeforeStructure` | 0x002fa710 | existing | |
| `Kart::Director::changeToAI` | 0x002fa300 | existing | |
| `Kart::Director::changeToAI_NetStop_All` | 0x002fb268 | existing | |
| `Kart::Director::changeToNetSend` | 0x002fa33c | existing | |
| `Kart::Driver::startJumpAction` | 0x002f3d7c | existing | |
| `Kart::Driver::startThrow` | 0x002f3698 | existing | |
| `Kart::NetData::clear` | 0x002f5630 | existing | |
| `Kart::NetData::read` | 0x002f55c4 | existing | |
| `Kart::NetData::send` | 0x00506e1c | existing | |
| `Kart::Unit::Unit` | 0x002eedf4 | existing | |
| `Kart::Unit::changeToCPU` | 0x002e4bd8 | existing | |
| `Kart::Unit::changeToNetSend` | 0x002e8aa8 | existing | runs on into `VehicleControlNet::changeToNetSend` |
| `Kart::Unit::changeToNetStop` | 0x002ed7c0 | existing | |
| `Kart::Vehicle::calcApply` | 0x002f9ad4 | existing | |
| `Kart::Vehicle::startJugemHangNetRecv` | 0x002f847c | existing | |
| `Kart::Vehicle::startTwist` | 0x002f57ec | existing | |
| `Kart::VehicleBase::VehicleBase` | 0x002d2f64 | existing | |
| `Kart::VehicleControlNet::VehicleControlNet` | 0x002e9004 | existing | |
| `Kart::VehicleControlNet::applyNetVS` | 0x002e6d90 | existing | |
| `Kart::VehicleControlNet::changeToNetSend` | 0x002e8ab0 | existing | |
| `Kart::VehicleControlNet::init` | 0x002e8e04 | existing | |
| `Kart::VehicleControlNet::prepareOpenningNetCurtain` | 0x002e8c80 | existing | |
| `Kart::VehicleControlNet::update` | 0x002e4b4c | existing | |
| `Kart::VehicleControlNet::updateNetRecv` | 0x002e6e98 | existing | |
| `Kart::VehicleControlNet::updateNetSend` | 0x002e85b4 | existing | |
| `Kart::VehicleControlNet::updateNetSend_Accident` | 0x002e8b88 | existing | |
| `Kart::VehicleControlNet::warp` | 0x002e8e7c | existing | |
| `Kart::VehicleMove::calcDriftJump` | 0x002d4af4 | existing | |
| `Kart::VehicleMove::calcMoveControlCommon` | 0x002db7bc | existing | |
| `Kart::VehicleMove::dokanWarp` | 0x002de100 | existing | |
| `Kart::VehicleMove::execDashOne` | 0x002d45b8 | existing | |
| `Kart::VehicleMove::startDriftJump` | 0x002d5468 | existing | |
| `Kart::VehicleMove::startKiller_NetRecv` | 0x002db7a4 | existing | |
| `Kart::VehicleReact::calcReact` | 0x002e1b6c | existing | |
| `Kart::VehicleReact::reactAccidentNet` | 0x002e0db4 | existing | |
| `Net::NetUtil::endWriteKartSendBuffer` | 0x002adf18 | existing | |
| `Net::NetUtil::getKartRecvBuffer` | 0x002ade78 | existing | |
| `Net::NetUtil::startWriteKartSendBuffer` | 0x002ae054 | existing | |
| `Net::NetworkBufferController::procSplitBuffer_` | 0x002a4ad4 | new | `dlp` name; named in `eur2` by the research on menu multiplayer |
| `Net::NetworkEngine::createBeforeStructure` | 0x00291974 | existing | |
| `Net::NetworkEventModule::CreateSendBuffer` | 0x0029ac70 | existing | |
| `Net::NetworkEventModule::calc` | 0x0029af10 | existing | |
| `Net::NetworkEventModule::finalizeRace` | 0x0029aa38 | existing | |
| `Net::NetworkEventModule::init` | 0x0029b0fc | existing | |
| `Net::NetworkEventModule::initRace` | 0x0029b2bc | existing | |
| `Net::NetworkEventModule::recvHook` | 0x0029b3ac | existing | |
| `Net::NetworkEventModule::sendHook` | 0x0029b710 | existing | |
| `Net::NetworkEventModule::setSendEvent` | 0x0029aa68 | existing | |
| `Net::NetworkGameDataManager::onReceivedCore` | 0x002a4094 | existing | |
| `Net::NetworkGameEventMgr::Buffer::postInit` | 0x0029e344 | existing | |
| `Net::NetworkGameMgr::NetworkGameMgr` | 0x00297d34 | existing | |
| `Net::NetworkGameMgr::Rank::Rank` | 0x002978bc | existing | |
| `Net::NetworkGameMgr::Rank::TakeoverMigration::calc` | 0x00297368 | existing | no caller in `eur2`; its code is repeated inside `Rank::calc` |
| `Net::NetworkGameMgr::Rank::TakeoverMigration::setEnable` | 0x002978a4 | existing | |
| `Net::NetworkGameMgr::Rank::TakeoverMigration::setTakeoverGoal` | 0x00295fa0 | existing | |
| `Net::NetworkGameMgr::Rank::calc` | 0x00296020 | existing | |
| `Net::NetworkGameMgr::Rank::getRank` | 0x00502bb8 | existing | |
| `Net::NetworkGameMgr::Rank::getScore` | 0x00502be4 | existing | |
| `Net::NetworkGameMgr::calc` | 0x0029796c | existing | |
| `Net::NetworkGameMgr::finalizeRace` | 0x00295cd0 | existing | |
| `Net::NetworkGameMgr::initRace` | 0x00297c40 | existing | |
| `Net::NetworkGameMgr::isQAidTakeoveredByMe` | 0x00502b18 | existing | |
| `Net::NetworkGameMgr::requestGoal` | 0x00295bc8 | existing | |
| `Net::NetworkGameMgr::setCurrScore` | 0x00295d0c | existing | |
| `Net::NetworkGameMgr::start` | 0x00297c00 | existing | |
| `Net::NetworkItemEventDataMgr::eventHandler` | 0x002a4e98 | existing | |
| `Net::NetworkItemEventDataMgr::onReceivedCore` | 0x002a4fd0 | existing | |
| `Net::NetworkItemEventDataMgr::postInit` | 0x002a501c | existing | |
| `Net::NetworkItemEventDataMgr::setSendEvent` | 0x002a4f48 | existing | |
| `Net::NetworkItemEventDataMgr::updateCore` | 0x002a4e4c | existing | |
| `Net::NetworkItemEventMgr::initRace` | 0x0029e5f8 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::commit` | 0x0029d494 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::isRequestNGFromAny` | 0x00502e9c | existing | |
| `Net::NetworkItemSlotMgr::Buffer::isRequestOKFromAll` | 0x00503000 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::onReceivedCore` | 0x0029cca4 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::postInit` | 0x0029d6a8 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::setEquipItemType` | 0x0029ceec | existing | |
| `Net::NetworkItemSlotMgr::Buffer::setPeerRequestResult` | 0x0029d0c8 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::setRequest` | 0x0029cbe8 | existing | |
| `Net::NetworkItemSlotMgr::Buffer::setStockItemType` | 0x0029cff4 | existing | |
| `Net::NetworkItemSlotMgr::GetNumEquipItem` | 0x0029bae0 | existing | |
| `Net::NetworkItemSlotMgr::GetNumStockItem` | 0x0029bb50 | existing | |
| `Net::NetworkItemSlotMgr::Node::init` | 0x0029c2ec | existing | |
| `Net::NetworkItemSlotMgr::calc` | 0x0029c364 | existing | |
| `Net::NetworkItemSlotMgr::clear` | 0x0029c870 | existing | |
| `Net::NetworkItemSlotMgr::finalizeRace` | 0x0029b83c | existing | |
| `Net::NetworkItemSlotMgr::getStockItemType` | 0x00502d38 | existing | |
| `Net::NetworkItemSlotMgr::init` | 0x0029c7bc | existing | |
| `Net::NetworkItemSlotMgr::initRace` | 0x0029da94 | existing | |
| `Net::NetworkItemSlotMgr::judgeMyRequest` | 0x0029b8f0 | existing | |
| `Net::NetworkItemSlotMgr::judgePeerRequest` | 0x0029bb78 | existing | |
| `Net::NetworkItemSlotMgr::request` | 0x0029d930 | existing | |
| `Net::NetworkItemSlotMgr::stock` | 0x0029c968 | existing | |
| `Net::NetworkItemSlotMgr::updateMyKartEquipState` | 0x0029bf78 | existing | |
| `Net::NetworkItemSlotMgr::updateMyKartStockState` | 0x0029c0e8 | existing | |
| `Net::NetworkSystemInfoManager::FrameSync::calc` | 0x002aaea0 | existing | |
| `Net::NetworkSystemInfoManager::Sync::Sync` | 0x002aa878 | existing | |
| `Net::NetworkSystemInfoManager::Sync::ready` | 0x002aa574 | existing | |
| `Net::NetworkSystemInfoManager::Sync::stateReady` | 0x002aa19c | existing | |
| `Net::NetworkSystemInfoManager::Sync::stateSync` | 0x002aa668 | existing | |
| `Net::NetworkSystemInfoManager::goalRace` | 0x002aae90 | existing | |
| `Net::NetworkSystemInfoManager::startWatchFrameSync` | 0x002a9a84 | existing | |
| `Object::CoinManager::syncCoin` | 0x00416d58 | existing | |
| `RaceSys::ModeManagerBase::calc` | 0x00463b54 | existing | |
| `RaceSys::ModeManagerBase::stateInitGoal` | 0x00463520 | existing | |
| `RaceSys::ModeManagerBattle::calcRace` | 0x00466270 | existing | |
| `RaceSys::ModeManagerBattle::calcWait` | 0x00466770 | existing | |
| `RaceSys::ModeManagerBattle::initWait` | 0x004668b4 | existing | |
| `RaceSys::ModeManagerBattle::takeoverHandler` | 0x00465f5c | existing | |
| `RaceSys::ModeManagerRace::calcRace` | 0x00464c34 | existing | |
| `RaceSys::ModeManagerRace::calcWait` | 0x004653dc | existing | |
| `RaceSys::ModeManagerRace::initWait` | 0x00465590 | existing | |
| `RaceSys::ModeManagerRace::takeoverHandler` | 0x004649b4 | existing | |

### Data

| Name | Address (eur2) | Note |
| --- | --- | --- |
| `Kart::sNetRecvParam` | 0x00665058 | new name; `.bss`, 0x98 bytes, filled by a static initialiser at 0x00574b40 to 0x00574cc8; the tuning values of `updateNetRecv` |
| `Net::sTakeoverCandidateOffsets` | 0x005f3e44 | new name; `s32[6]` = 2, 1, 5, 6, 4, 3 |
| `Item::sItemTimeParam` | 0x00665c68 | new name; `.bss`, filled at 0x005413f0: `s32[7]` = 1800, 1800, 1320, 1800, 1800, 1800, 1800, then two floats (10, 1600) not used here |

## Findings

### Sources and method

- Decompilation (`mk7 decomp`) and disassembly (`mk7 dis`) of `eur2`, with names ported from `dlp`.
- To find who sets a member, a scratch disassembly of the whole `eur2` code was searched for stores to its offset;
  every hit was then checked with `mk7 dis` / `mk7 sym`. Such a search can miss a store through another pointer.
- Several long functions were only skimmed: `VehicleControlNet::updateNetRecv` (the correction of a received kart's
  position), `NetworkGameMgr::Rank::calc` (the rank agreement) and the event handlers of items and battle objects.
  What is said of them is marked in [Confidence](#confidence).
- Taken from the research on menu multiplayer (pending verification): the packet and its eleven buffers, the receive
  path (`NetworkStationBufferManager::onReceived` → `NetworkBufferController::onReceived`), the station tables
  (`m_connector_info_humans`, `m_connector_info_cpus`, `m_player_num`, `m_player_id_to_aid`), the SystemInfo format
  and `NetworkStateCalc`. They were re-read in `eur2` only where this research uses them.

### 1. The KartData buffer

- `NetUtil::startWriteKartSendBuffer` makes a `NetworkBuffer` view of 0x88 bytes in the KartData write buffer, 4
  bytes after its current end. `NetData::send(player id)` writes the 0x48-byte `NetData` into it, then
  `NetUtil::endWriteKartSendBuffer(player id, view)` adds a 4-byte block header (`NetworkBuffer::add(write buffer,
  header, 4)`) and advances the end by the size. The header is `{u16 size, u8 aid}`: the aid is
  `m_player_id_to_aid[player id]` (player id -1: the local one); the fourth byte is not set:

  ```
  local_18 = CONCAT22(CONCAT11(local_18._3_1_,uVar1),(short)*(undefined4 *)(param_2 + 0xc));
  NetworkBuffer::add(iVar2,&local_18,4);
  ```
- `Kart::Director::calcBeforeStructure`, at the start of every kart frame, when `m_is_net_object` is set, sets the
  KartData write buffer's end to 0 (`*(iVar8 + 0xc) = 0` on `getWriteBuffer(..., 3)`): the blocks are rewritten
  every frame, one per kart the console drives.
- `NetworkBufferController::procSplitBuffer_(controller, slice, size, station manager)`, called by
  `NetworkBufferController::onReceived` for type 3 only: walks the blocks; for each, the aid must be below 8 and have
  a station in `m_connector_info_humans` or `m_connector_info_cpus` with a buffer id other than -1; the block (without
  its header) goes through the receive delegate and into the read buffer of that buffer id, and the aid's bit is set
  in `m_has_recv_bitfield`. It stops after 4 blocks (`if (iVar7 == 4) return;`), or when the bytes walked exceed
  0x22F or reach the slice size. Nothing checks that the sending console drives the kart of that aid.
- `NetData::send` has one caller, the end of `VehicleControlNet::updateNetSend`; `applyNetVS` calls `updateNetSend`
  for a kart with `m_is_net_send`, and is called from `Vehicle::calcApply`.
- `NetUtil::getKartRecvBuffer(player id, engine)` returns the read buffer of that player's aid.
- Probable: a packet carries the console's kart and its CPUs, at most four, since the buffer type is 0x230 bytes and
  a block 0x4C; with eight karts and two consoles, one console drives four karts.

### 2. What NetData holds

`VehicleControlNet::updateNetSend` fills `m_net_send_data` from the kart (`VehicleMove`/`Vehicle` members of the same
object, through `VehicleBase::m_vehicle`):

| `NetData` member | Value |
| --- | --- |
| `m_frame` | `*VehicleBase::m_frame` |
| `m_sender_player_id` | `VehicleBase::m_player_id` |
| `m_kart_data` | [Finding 3](#3-kart-events); `&= 0x7FFF0000` first, so the event bits are kept |
| `m_position` | `Rigid` position, each axis cast to `s16` |
| `m_velocity` | `Rigid` velocity minus a vertical component of the vehicle, `adjustLength` to 50 when longer (2500 squared), × 256 |
| `m_forward_dir` | `VehicleMove::m_forward_dir` × 1024 |
| `m_turning_speed`, `m_forward_speed` | × 1024, `VehicleMove::m_forward_speed` × 256 |
| `m_drift_type` | `VehicleMove::m_drift_state` |
| `m_drift_steering`, `m_directional_speed` | two vehicle floats × 64 |
| `m_boost_type`, `m_boost_frames`, `m_boost_speed` | `m_current_boost_type`, `m_boost_frames`, `m_boost_speed` × 256 |
| `m_star_timer` ... `m_blink_timer` | `m_star_frames`, `m_ink_frames`, `m_thunder_frames`, `m_press_frames`, `m_invincibility_frames`, each `>> 2` |
| `m_coins` | a `u16` of `VehicleBase::m_kart_info` (+0x46) |
| `m_balloon_points`, `m_balloon_count` | two `u16` of `m_kart_info` (+0x54, +0x56) when the vehicle's battle object exists and is a balloon battle, else 0 |
| `m_status_flags` | `VehicleMove::m_status_flags` |
| `m_wing_path_id`, `m_dokan_warp`, `m_respawn_point_id` | current glider route or 0xFF, `VehicleMove::m_dokan_warp`, respawn point or 0xFF |

The constants are loaded next to the function: 31 and -31 for the stick, 2500 and 50 for the velocity, 256, 1024 and
64 for the scales. `updateNetSend_Accident(type, item, player id, direction 1, direction 2)` writes
`m_accident_type`, `m_hit_item_type_id` (-1 → 0xFF), `m_hit_player_id` (-1 → 8) and the two directions × 256 with the
lowest bit of y set (`*(ushort *)(param_1 + 0x158) = uVar1 | 1;`), or zero when absent. `clearNetSend_Accident` sets
the type to 0x12, `NetData::clear` sets frame 0, kart data 0, type 0x12, pipe warp 0xFF and the player id.

`NetData::read(current, buffer, &newest, &previous)`: the block is taken when the buffer holds data, its player id
equals the kart's and its frame is greater than the newest one's (`*(int *)this < *piVar2`); 0x46 bytes are copied
over the older `NetData` and the two pointers are swapped, so `m_net_recv_data` is the newest block and
`m_net_recv_data_prev` the one before.

### 3. Kart events

The stick and buttons, in `updateNetSend`: bits 0 to 2 copy `VehicleControl::m_controls`; for each stick axis, a
negative value is stored as `VectorFloatToUnsigned(value * -31) << 5` (x) or `<< 11` (y), a positive one as the same
of `value * 31` with bit 4 (x) or bit 10 (y) set.

The events: each bit of `m_net_event_send_bits` that is set flips one bit of `m_kart_data`, and is cleared:
bit 0 → 0x10000, bit 1 → 0x20000, bits 2 to 9 → 0x40000 << n, bits 10 to 14 → 0x4000000 to 0x40000000:

```
if ((*(uint *)(param_1 + 0xbdc) & 1) != 0) {
  *puVar4 = uVar13 ^ 0x10000;
  *(uint *)(param_1 + 0xbdc) = *(uint *)(param_1 + 0xbdc) & 0xfffffffe;
}
```

`updateNetRecv` sets the matching bit of `m_net_event_recv_bits` for each bit that differs between the newest and the
previous block (`((uint)*pfVar9 ^ *puVar10) & 0x10000`). Senders and receivers, found by the search for stores and
loads of 0xBDC and 0xBE0:

| Bit | Set on the driving console by | Replayed by |
| --- | --- | --- |
| `DRIFT_JUMP` | `VehicleMove::startDriftJump` | `VehicleMove::calcDriftJump` |
| `WARP` | `VehicleControlNet::changeToNetSend`; `init` when `m_is_net_send` | `updateNetRecv` calls `warp` |
| `HIT_KART_0 << n` | `VehicleReact::calcReact`, for two karts that collide: each driven kart marks the other's player id | `calcReact` |
| `JUMP_ACTION` | `VehicleMove::calcMoveControlCommon`, with `BoostFlags::trick` | `calcMoveControlCommon` → `Driver::startJumpAction` |
| `TWIST` | `Vehicle::startTwist` | `calcMoveControlCommon` → `startTwist(true)` |
| `THROW_FORWARD`, `THROW_BACKWARD` | `Driver::startThrow(true / false)` | `calcMoveControlCommon` → `startThrow(true / false)` |
| `DASH_RESTART` | `VehicleMove::execDashOne` | `updateNetRecv`, as the third argument of `execDashOne` |

Each sender tests `m_is_net_send` (`ldrb r0, [r5, #0x9d]`) before setting the bit.

### 4. Who drives which kart

- `VehicleBase::VehicleBase`: `m_is_net_object` = `CRaceInfo::m_race_mode_flag.multiplayer_or_online`;
  `m_is_net_send` = net and not `CreateArg::is_player`; `m_is_net_recv` (and the unnamed byte after it) = net and
  `CreateArg::is_player`.
- `Unit::Unit` fills the `CreateArg`: `is_cpu` is set for a kart whose `EPlayerType` is not `Master`, `User`, `Ghost`
  or `Master_Replay` (that is, `CPU`); in a network race such a kart gets `is_cpu` cleared and `is_player` set, and
  `is_player` is also set for type `User` (a remote human):

  ```
  bVar25 = (param_3[0x5e] & 8) != 0 && (bool)local_10c;
  if (bVar25) local_10c = false;
  local_10b = bVar25 || uVar23 == 2;
  ```

  So `CreateArg::is_player` means "replayed" in a network race, and at the start every console drives only its own
  kart (`Master`); the template's name of the member does not fit this use.
- `VehicleControlNet::update`: `updateNetRecv` when `m_is_net_recv`, else `VehicleControl::updateLocal`.
- `ModeManagerRace::takeoverHandler(kart, owner)` (and the same function of `ModeManagerBattle`): when the owner's aid
  is the local player's, `Director::changeToAI(kart, true)` (`Unit::changeToCPU`, `Enemy::AI::awake`) and
  `Director::changeToNetSend(kart)` → `Unit::changeToNetSend` → `VehicleControlNet::changeToNetSend`: `m_is_net_send`
  = 1, `m_is_net_recv` = 0, `m_net_event_send_bits |= WARP`. These are the only callers of `Director::changeToNetSend`.

### 5. A received kart

`VehicleControlNet::updateNetRecv(bool)`, every frame for a replayed kart. Read in full for the reading of the block
and the state it copies; the position correction was only skimmed.

- Reading: unless the kart's status has 0x8000000 or the director's flag at 0x18E is set, `NetData::read` with
  `getKartRecvBuffer(m_player_id, m_network_engine)`.
- Delay: on a new block, `m_net_delay += (now - block frame - m_net_delay) * (1 - m_net_delay_weight)` and
  `m_net_delay_weight = 1`; otherwise the weight is multiplied by `sNetRecvParam` +0x14 (0.992).
  `m_net_track_delay` moves towards `m_net_delay` minus 10 (or minus 2 below that) by 0.03 of the gap each frame.
- On a new block: its position, forward direction and frame go into `m_recv_track`; `applyNetVS` records the kart's
  own position, direction and frame in `m_own_track` every frame. The newest received entry older than
  `m_net_track_delay` is compared with the own entry of the same age: `m_net_track_offset` = received position minus
  own position (`sub(r7 = 0xBB8, r6 = received, r8 = own)`), `m_net_track_rotation` = rotation between the two forward
  directions, `m_net_track_frame` = its frame. These feed `m_net_correction` and `retoucnFollowVecGndNrm` (skimmed).
- No block: after 60 frames (`sNetRecvParam` +0x00, +0x04, +0x08) since `m_net_recv_frame`, the three buttons are
  cleared one by one; the stick axes are multiplied by 0.95 every frame (+0x0C, +0x10).
- Block: buttons copied; stick = 5-bit value × (1 / 31), negative unless the sign bit is set; event bits as in
  [Finding 3](#3-kart-events).
- Teleport (`warp` to the received position and direction): when `WARP` was received or Lakitu starts carrying the
  kart, or, after distance and time tests against `sNetRecvParam` (values such as 180, 60, 120 and 60 frames since
  `m_net_warp_frame`), when the kart stays too far off. Probable: the exact tests were not followed.
- Copied from the block every frame: turning speed, forward speed, drift state and the two drift floats; boost type,
  frames and speed, with `execDashOne` when the type or the frames grew (the flag passed depends on the type: 0 →
  0x4000, 1 → 0x400, 2 → 4, 3 → 0x8000, 4 → 0x2000, 5 → 0x800, 6 → 2); star (`startStar` / `endStar`), ink, lightning
  (`VehicleReact::startThunder`), squashed (`startPress`) and blinking frames (`<< 2`).
- Coins: `CoinManager::syncCoin(player id, m_coins)`; in balloon battles, the difference of balloon points is added to
  the kart info (clamped to 0 to 99) and the balloon count copied.
- Crash: when the block's `m_accident_type` is not 0x12 and differs from the previous block's,
  `VehicleReact::reactAccidentNet(type, ...)` with the two directions when their marker bit is set. Pipe warp below
  0xFF → `VehicleMove::dokanWarp`.
- Status bits of the block: 0x1000 screw (`startScrew` / `closeScrew`), 0x80 glider (`startWingReady` + `openWing` /
  `closeWingNet`), 0x400000 Bullet Bill (`startKiller_NetRecv` / `endKiller_NetRecv`), 0x800000 Lakitu
  (`Vehicle::startJugemHangNetRecv(respawn point)`).
- `prepareOpenningNetCurtain`, called by `Director::calcBeforeStructure` for every kart when the director's flag at
  0x18D falls from 1 to 0: a replayed kart that has a block is warped to it, its two track rings are emptied and the
  delay is reset to the block's age.

### 6. Takeover

- `TakeoverMigration::calc(lost aids, ...)` has no caller in `eur2`; the same code runs inside `Rank::calc`. With the
  lost aids = disconnected aids | `m_absent_aid_bits` (set by `initRace` for the aids from `m_player_num` on, the CPU
  slots): for each lost aid not in `m_handled_aid_bits`, if `m_take_over_humans` is clear and the aid is a human
  slot, it is only marked handled; otherwise the owner is the first aid `(aid + k) % 8`, for k in
  `sTakeoverCandidateOffsets` (2, 1, 5, 6, 4, 3), that is a human slot (below `m_player_num`) and not lost. Then
  `m_owner_player_ids[aid]` = owner, `m_handler(aid, owner)`, and the bit goes to `m_taken_over_by_me_aid_bits` when
  the owner is the local player. Nothing is done when the number of lost aids is the number of karts minus one.
- `ModeManagerRace::initWait` (and `ModeManagerBattle::initWait`): `setEnable(true, play mode == Online)` and
  `m_handler` = the mode manager's delegate at +0x508, which calls `takeoverHandler`.
- `NetworkGameMgr::isQAidTakeoveredByMe(aid)`: `m_owner_player_ids[aid]` is the local player id.
- Probable: `m_take_over_humans` is the play mode `Online` (`CRaceMode::m_play_mode == 2`, read in `initWait` as
  `GetRaceInfo()+0x164`), so in local play a departed player's kart keeps no driver.

### 7. GameData: goals and scores

- `NetworkGameMgr::requestGoal(player id, value)`, called by `ModeManagerRace::calcRace` and
  `ModeManagerBattle::calcRace`: for the local player's kart, if no goal yet, `Rank::m_my_score`,
  `m_node_data.m_scores[aid]` and `Rank::m_scores[aid]` = value, `m_is_my_goal` = 1, and the aid's bit in
  `m_goal_aid_bits`. For another kart: `setTakeoverGoal(aid, value, false)`: the score is written and the bit set in
  `TakeoverMigration::m_takeover_goal_aid_bits`; when the local console owns the kart, the aid's bit is set in
  `m_takeover_goal_aid_bits` of the format.
- `setCurrScore(player id, value)` (from `ModeManagerRace::calcRace`): the current score of the local kart, or of a
  kart whose goal is not set yet.
- `NetworkGameDataManager::onReceivedCore`, while `NetworkGameMgr::m_is_race_active`: stores nothing once
  `m_is_rank_fixed`; when not `m_is_before_start` and the local player id is valid, drops a packet that would remove
  what was received from that aid before: its own goal bit, its own score once its goal is set, the local console's
  goal bit, any bit of `m_goal_confirmed_aid_bits`, `m_disconnected_aid_bits` or `m_disconnect_confirmed_aid_bits`
  (`if (uVar5 != 0) return 0;`). Otherwise the 0x30 bytes are copied into `m_received[aid]`.
- `NetworkGameMgr::calc`: when only the local console is left, `m_is_alone` is set and nothing more is done; otherwise
  `Rank::calc`, then the send (`preUpdate` / `updateCore` / `postUpdate`) when the session is active.
- `initRace` clears the format and the ranks, sets `m_is_race_active`; `start(type, ...)`, from `calcWait`, picks the
  policy (`Type` 1 time, 2 score) and clears `m_is_before_start`; `finalizeRace` clears `m_is_race_active` and sets the
  data manager's `unk`, so that further packets are accepted unread.

### 8. Agreeing on ranks

`Rank::calc` (0x1348 bytes) was read in its first part and skimmed in the rest:

- For every other connected aid whose received `m_goal_aid_bits` has its own bit and the local one does not: when the
  local kart has no goal, the policy's third function is asked with the local score first (probable: whether the
  local kart could still beat it); then the score is copied into `Rank::m_scores`, the bit set in the local
  `m_goal_aid_bits`, and `setTakeoverGoal` called.
- When the local kart has its goal and every connected peer's `m_goal_aid_bits` has the local bit, the local bit is set
  in `m_goal_confirmed_aid_bits`; the bits the peers confirm are merged into it.
- Disconnected aids go into `m_disconnected_aid_bits` and `Rank::m_disconnected_aid_bits`;
  `m_disconnect_confirmed_aid_bits` becomes the AND of the peers' `m_disconnected_aid_bits` (only when it grows);
  `Rank::m_disconnect_confirmed_aid_bits` the AND of the peers' confirmations, and `Rank::m_goal_confirmed_aid_bits`
  the AND of their `m_goal_confirmed_aid_bits`.
- Ranks are fixed into `m_ranks` / `m_aids_by_rank` with the policy's `is_upper` / `is_equal` / `can_fix_upper`
  (`PolicyTime`: a lower value is better; `PolicyScore`: a higher one).
- When the karts left without a rank (kart number minus the bits of `m_auto_rank_aid_bits` and 0x23) leave one rank,
  the remaining aid gets it in `m_auto_ranks` / `m_aids_by_auto_rank`, and `m_is_rank_fixed` and `m_is_finished` are
  set. `getRank(aid)` returns `m_ranks[aid]`, else `m_auto_ranks[aid]`; `getScore` returns -1 for aids in 0x22 or 0x23.
- Takeover goals: for a kart owned by another console, its score is taken from the owner's packet when the owner's
  bytes 4 and 5 have the kart's bit, and the owner's bit is recorded in `m_accepted_takeover_goal_aid_bits[owner]`.

### 9. ItemSlot: item requests

#### The node and its packet

- `Node::init` and `Buffer::postInit`: `m_frame` 0, `m_stock_item` and `m_equip_item` 0xFF, the states 0,
  `m_judged_frames` cleared, `m_takeover_aids` 0xFF, and the same for the three columns of `m_takeover`.
- `Buffer::commit`, at the end of `calc`: the sent node (`m_node_data`) is a copy of bytes 0x00 to 0x0E of
  `m_nodes[local aid]`, with the local aid's bit added to `m_accepted_request_aid_bits`; then, for every kart whose
  `TakeoverMigration::m_owner_player_ids` entry is the local player, in order, its aid goes to
  `m_takeover_aids[k]`, its `m_frame`, `m_stock_item`, `m_equip_item`, `m_stock_item_state`, `m_equip_item_state` and
  `m_equip_items_used` to column k of `m_takeover`, and its bit to `m_accepted_request_aid_bits`:

  ```
  *(char *)(iVar5 + 0xf) = (char)uVar3;
  *(undefined1 *)(iVar5 + 0x12) = *puVar2;
  ...
  *(undefined1 *)(iVar5 + 0x21) = puVar2[6];
  ```
- `Buffer::onReceivedCore`: bytes 0x00 to 0x0E of the received node go to `m_nodes[sender aid]`; for every kart whose
  aid is in the received `m_takeover_aids` and whose owner is the sender, its `m_nodes` entry gets the matching
  column of `m_takeover`, with bytes 0x05 and 0x07 to 0x0E (the answers) of the sender's node. So a console's answers
  are repeated in the entries of every kart it drives.
- `NetworkEngine::createBeforeStructure` stores the manager at `NetworkEngine` + 0x2D0 (`str r1, [r4, #0x2d0]`, after
  `new(0x26c)`), and sets `Buffer::m_is_idle` (`strb r8, [r0, #0x240]` on the buffer). `init` and `finalizeRace` set
  it, `initRace` clears it; `calc` returns at once while it is set.

#### Asking for an item

- `Item::ItemDirector::slot_StartSlot` calls `NetworkItemSlotMgr::request(player id, item)`: for a kart driven by this
  console (local, or `isQAidTakeoveredByMe`), `Buffer::setRequest(aid, race frame, item)`: `m_frame` = bits 3 to 10
  of the frame, `m_stock_item` = item, `m_stock_item_state` = 1, the kart's own bit in its node's
  `m_accepted_request_aid_bits` and `m_judged_frames[aid]` = `m_frame` (the kart accepts its own request); and
  `m_request_frames[aid]` = race frame.

#### Answering

- `NetworkItemSlotMgr::calc` computes once the counts by item type (`ItemDirector::getEntryNumArray_InType`,
  `Buffer::getStockedItemNumArray`, `ItemDirector::getNumInStandArray_InType`), then calls `judgePeerRequest(judge)`
  for every kart this console drives, then `judgeMyRequest` for the same karts, then `commit` and the send.
- `judgePeerRequest(judge, ...)`: the pending requests of the other karts (`m_stock_item_state` 1, aid not
  excluded), in the order of the sorted list at `Buffer` + 0x234; for each, the item's `eItemType` (a triple item
  counts as its single item) and the number it counts for: 3 for the triple shells and bananas and for the Fire
  Flower (`eItemSlot` 0xC), 7 for Lucky Seven, 0 for Mushroom, Triple Mushroom, Golden Mushroom and `Empty`, 1 for
  the others. When `GetNum_InItemType_Net(type) < count + entries + stocked - in stand + granted`,
  `setPeerRequestResult(judge, requester, false)`, else `true`, and the count is added to the granted count.
- `Buffer::setPeerRequestResult(judge, requester, ok)`: the judge's `m_judged_frames[requester]` = the requester's
  `m_frame`, and the requester's bit set or cleared in the judge's `m_accepted_request_aid_bits`:

  ```
  *(undefined1 *)(iVar3 + param_3 + 7) = *puVar4;      // judge node, judged_frames[requester]
  if (param_4 == 0) { bVar2 = *(byte *)(iVar5 + 5) & ~bVar2; ...
  ```

#### Deciding

- `judgeMyRequest(aid)`, for a request in state 1: `Buffer::isRequestOKFromAll` (every judge aid not excluded by
  `Rank::m_disconnect_confirmed_aid_bits` or `TakeoverMigration::m_handled_aid_bits` has
  `m_judged_frames[aid]` equal to the request's `m_frame` and the aid's bit in `m_accepted_request_aid_bits`) → state
  2; `isRequestNGFromAny` → `ItemDirector::getReplacementItem(aid)` becomes `m_stock_item`, state 2; otherwise state 2
  once `race frame - m_request_frames[aid] >= 0x78`.
- `Item::ItemSlot::stateSpin`, when the roulette stops in a network race: `NetworkItemSlotMgr::stock(player id)`, then
  `getStockItemType(player id)` becomes the kart's item (`KartItem::_setStockItem`):

  ```
  002d1abc  bl      0x29c968	; ~Net::NetworkItemSlotMgr::stock(int)
  002d1aec  bl      0x502d38	; ~Net::NetworkItemSlotMgr::getStockItemType(int) const
  002d1afc  bl      0x2d1f3c	; ~Item::KartItem::_setStockItem(Item::eItemSlot)
  ```
- `stock(player id)`, for a kart this console drives: state 1 (still undecided) → `setStockItemType(aid,
  getReplacementItem(aid))`; state 2 → `setStockItemType(aid, m_stock_item)`.
- Probable: how the roulette's length compares with the 120 frames of `judgeMyRequest` was not checked, so which of
  the two limits ends a request that lacks answers depends on it.

#### Holding and using the item

- `Buffer::setStockItemType(aid, item, count)`: `m_stock_item` = item; with count -1, the count is 7 for Lucky Seven
  (`eItemSlot` 0xE), 3 for Triple Mushroom, Fire Flower and the triple items, 0 for `Empty`, 1 otherwise; the state
  is 5 for 1 or 7, 4 for 2, 3 for 3, and 0 otherwise. `GetNumStockItem` turns 3, 4, 5 back into 3, 2, 1.
- `Buffer::setEquipItemType(aid, item, count)`: `m_equip_item` = item, `m_equip_item_state` = 8 − count (count 1 to
  7), 0 otherwise; `GetNumEquipItem` turns it back.
- `updateMyKartStockState(aid)` and `updateMyKartEquipState(aid)`, from `calc` for every kart this console drives:
  the stock fields follow the kart's held item while the state is 3 to 5 (probable: the decompilation lost the
  arguments of the final `setStockItemType`); the equip fields take the kart item's equipped slot (+0x40) and count
  (+0x44), and `m_equip_items_used` its byte at +0x48.
- `clear(player id)`, from `ItemDirector::clearItem`: `setStockItemType(aid, -1)`, so the state becomes 0.
- `getStockItemType(player id)` is read by `ItemSlot::stateSpin`, `ItemSlot::_calcNetKartSlot` and
  `ItemDirector::_calcNet`.
- `KartItem::m_equip_items_used` (+0x48) is increased by `KartItem::setEquipInfo` whenever its last argument is set,
  as `ItemDirector::_entryItem` does for each item a kart starts to use; the node carries its low byte.
- `ItemDirector::_calcNet`, for every replayed kart (`KartItem::isNetRecv`) not in status 0x8000000: when the node's
  `m_equip_items_used` differs from the value kept for that kart, the kart's hanging and circling items are removed
  (`KartItem::_vanishEquip_Hang`, `_vanishEquip_Multi`); when the kart shows more items in use than
  `GetNumEquipItem(m_equip_item_state)`, `vanishEquip_One` removes the extra ones (not for a Lucky Seven); then
  `getStockItemType` becomes the kart's held item (`KartItem::_setStockItem`).

### 10. Item limits and waiting times

#### The roulette's invalid items

- `Item::ItemDirector::_calcInvalidFlag(kart, bool)`, called by `slot_StartSlot` and both `emitItem`, rebuilds
  `ItemDirector::m_invalid_flag`, one bit per `eItemSlot` that the roulette must not give. Nothing in it tests the
  network, so it applies to every race.
- Waiting times: a bit is set when a timer is not above its value in `Item::sItemTimeParam` (filled by a static
  initialiser at 0x005413f0: 1800, 1800, 1320, 1800, 1800, 1800, 1800 frames, `mov r0, #0x708` and
  `sub r1, r0, #0x1e0`):

  | Bit (slot) | Timer | Value |
  | --- | --- | --- |
  | 0x20 (Blooper) | `m_gesso_time` | +0x00, 1800 |
  | 0x400 (Lightning) | `m_thunder_time` | +0x04, 1800 |
  | 0x40 (Blue Shell) | `m_kourab_time`, or `m_special_items_threshold_passed` clear | +0x08, 1320 |
  | 0x200 (Bullet Bill) | `m_killer_time` | +0x10, 1800 |
  | 0x4000 (Lucky Seven) | `m_seven_time` | +0x14, 1800 |
  | 0x800 (Golden Mushroom) | `m_kinokop_time` | +0x18, 1800 |

  `ItemDirector::calcBeforeStructure` adds 1 to every timer each frame while the mode manager's state byte (+0x48) is
  above 1, and sets `m_special_items_threshold_passed` when `m_frame_since_countdown - 240 > 1800` (+0x0C).
  `initBeforeStructure` sets them all to 0. `_calcKeyInput_EachPlayer`, when a kart of this console uses an item,
  resets `m_gesso_time` (Blooper), `m_thunder_time` (Lightning, and stores the user at +0xFC), `m_seven_time` (Lucky
  Seven) and `m_kourab_time` (Blue Shell). No other store to `m_killer_time` or `m_kinokop_time` was found, so these
  two only bar Bullet Bill and Golden Mushroom at the start of the race.
- Counts: for each slot, its `eItemType` and the number it counts for (the same table as in `judgePeerRequest`:
  3 for triples and Fire Flower, 7 for Lucky Seven, 0 for Mushroom, Triple Mushroom and Golden Mushroom). The bit is
  set when `GetNum_InItemType_Net(type) < objects of the type + held - in stand + count`, with the objects counted by
  each director (+0x24), the held items by `getNumInStockArray_InType` and the items in `m_stand_item_objs` of the type.
  The bool argument of `GetNum_InItemType_Net` is not read (`r1` is overwritten by its first instructions).
- When the kart's `KartItem::m_equip_item` is Fire Flower, Lucky Seven or a triple: `|= 0xE5000` (slots 12, 14,
  17, 18, 19). When any kart holds a Lucky Seven or the Lucky Seven director has objects: `|= 0xE1000` (12, 17, 18,
  19). When `_isReserveSeven` fails: `|= 0x4000`. With the item pattern `Koura` and more than one kart using a triple
  Green or Red Shell: `|= 0xC0000`.
- `_isReserveSeven`: with pattern `All`, `_isReserveSevenImpl(type, 1)` for Banana, Green Shell, Red Shell, Bob-omb,
  Star, Mushroom and Blooper, all of which must hold; with a single-item pattern, room for 7 of that item. The test is
  `objects + held - in stand + n <= GetNum_InItemType(type)` (the base limits below, not the `_Net` ones).

#### The limits

`Item::GetNum_InItemType_Net(type)`, used by the roulette and by `NetworkItemSlotMgr::judgePeerRequest`, with the item
pattern of the race (`CRaceInfo::m_item_pattern`, read through the mode manager): Green and Red Shell return
`GetNum_InItemType(type)` in the pattern `Koura`, Banana in `Banana`, Mushroom in `Kinoko`, Bob-omb in `Bomhei`, and
8 otherwise; Star 2; Blue Shell, Blooper, Bullet Bill 1; Lightning, Super Leaf and Fire Flower 3 with pattern `All`
and 1 with any single-item pattern (`pattern in {1, 2, 3, 4}`); Golden Mushroom 5; Lucky Seven 7; types 7 and 11
(test items) 0. With the counts above, a Lucky Seven (7 against 7) and a Fire Flower (3 against 3) can only be given
when no other is out.

`Item::GetNum_InItemType(type)`, the base limits, also used as the size of each director's pool
(`ItemObj...Director::createBeforeStructure`): Green and Red Shell 16 in `Koura`, Banana 24 in `Banana`, Mushroom 24
in `Kinoko`, Bob-omb 24 in `Bomhei`, otherwise 8; Star 8; Blue Shell 1; Lightning, Bullet Bill and Super Leaf 1 with a
single-item pattern, else 8; Blooper 1 or 9; Fire Flower 1 or 3; Golden Mushroom 5; test items and Lucky Seven 0.

#### Lightning

The count limit lets up to three Lightnings be held at once; what keeps them apart is the waiting time, which every
console restarts when any kart uses one ([Finding 11](#11-the-event-channel-itemevent-and-gameevent), `InitUse`). No
rule limiting held Lightnings to one was found; the item probabilities (`ItemSlotTable`) were not read.

### 11. The event channel: ItemEvent and GameEvent

#### The module

- `NetworkEventModule::init(buffer size, slots per console, data size, handler)` allocates the send buffer and, for
  each of the 8 aids, that many `Slot`s with a data buffer each. `NetworkItemEventDataMgr::postInit` passes 0x200,
  0x7E (126) and 0x2A (42 bytes); `NetworkGameEventMgr::Buffer::postInit` 0x40, 0x18 and 0x22.
- `NetworkEventModule::setSendEvent(&frame, data, size)`: frame 0 means the current race frame
  (`ModeManagerBase::m_frame_since_countdown`); refused when the size is above the data size, when the pending bytes
  plus the size plus 4 exceed the buffer size, or when no slot is free; otherwise the event takes a free slot of the
  local aid, with `m_header` = {counter + 1, size, frame}, `frame` = now, and is inserted into the ordered list.
- `CreateSendBuffer`: u8 count, then the 4-byte headers, then the data of each used slot.
- `calc`: own slots older than 0xF0 frames are freed; every unhandled slot of the list is handed to the handler when
  the race frame reaches `m_exec_frame` or the "run at once" byte (+0x04) is set, and marked handled; the send buffer
  is rebuilt when it changed, unless the "receive only" byte (+0x8C) is set.
- `recvHook(aid, data, size)`: every header already known from that aid only marks its slot seen; a new one fills a
  free slot of that aid and is inserted by `m_exec_frame`, then by `m_index` (wrap-around aware).
- `NetworkItemEventMgr::initRace` calls `NetworkEventModule::initRace(local aid, receive only, run at once)` with
  both flags set when the local player id is not a racer's (outside 0 to the kart number): a spectator sends no
  events and runs the others' events as they arrive. `finalizeRace` clears the active byte.

#### ItemEvent

- `NetworkItemEventDataMgr::setSendEvent(item type, event type, data, size, frame)` prefixes the data with the item
  type and the event type and hands size + 2 bytes to the module; every sender in `eur2` passes frame 0 (now).
- `updateCore` writes the module's send buffer into the ItemEvent write buffer (`sendHook(..., 0x200)`);
  `onReceivedCore` hands the slice to `recvHook` with the sender's aid.
- `eventHandler` builds a `SlotData` (exec frame, item type, event type, data size − 2, data) and calls the handler at
  +0x114, `ItemDirector::_itemEventRecvHandler`, unless the event's aid is the local player id
  (`if (*param_2 != *(int *)(*(int *)(param_1 + 0x2c) + 0x268))`).
- The item objects number themselves: `ItemObjBase::stateInitUse`, `stateSelfMove` (when the object has no serial
  yet) and `ItemObjTail::stateInitSpin` take the next value of a counter of the item type's director
  (`getDirector_FromItemType(...)`, `*(byte *)(iVar4 + 0xb8)`) as `ItemObjBase::m_serial`. Every event's data starts
  with `ItemObjBase::m_owner_player_id` and `m_serial`, and the receivers find the object by the item type, the owner
  and the serial ("sequence id" below).
- `UpdateKartItem_DestroyOther` and `UpdateKartItem_DestroySelf` for an object that `vanish_Force` does not find are
  copied into a ring of 0x30-byte `SlotData` kept by `ItemDirector` (+0x11C entries, +0x120 capacity, +0x124 head,
  +0x128 count). When a `SelfMove` later creates an object, the pending events with its owner and serial are handled
  again and removed from the ring (`_itemEventRecvHandler(param_1, iVar11)` in the `SelfMove` branch).

#### ItemEvent types

From the senders' calls (`setSendEvent(mgr, item type, event, data, size, 0)`) and the branches of
`_itemEventRecvHandler`, which first drops the event when the owner's kart has status bit 0x8000000:

| Event | Data | Receiver |
| --- | --- | --- |
| 0 `InitBurst` | owner, sequence id, `ItemObjBomhei` + 0x258 | Bob-omb: `ItemObjBomheiDirector::setBurst(owner, sequence id, byte)`: with byte 0 the Bob-omb is found by owner and sequence id, otherwise by owner and a virtual test (+0x48); the only stores found to + 0x258 write it at creation (`initEntryInner`, `_ctorImpl`). Blue Shell: `ItemObjKouraBDirector::setBurst(owner, sequence id)` |
| 1 `SevenFrame` | the kart's player id | Lucky Seven director's virtual function at +0x9C with the delay in frames |
| 2 `SelfMove` | `SSelfMove`, 0x24 bytes: owner, sequence id, `ItemObjBase::m_is_dropped`, a flag set when the object kept its serial (`m_is_collisionless` set and `m_serial` already given; cleared when a new serial was taken), stick y, position, velocity, gravity; sent only when the owner's kart has `m_is_net_send` | `ItemObjDirectorBase::setState_SelfMove_Force` with the delay in frames; when the owner's kart uses a Lucky Seven or the item is a Blooper (`eItemType` 10), `ItemObjSevenDirector::setState_SelfMove_Force_Seven` instead, and when that fails and the first flag is set, the receiver sends a `UpdateKartItem_DestroySelf` back |
| 3 `UpdateKartItem_EquipHit` | kart, hitter's player id or 0xFF, items held | when the counts agree: `vanishEquip_NearHitPos` with the hitter's position, else `vanishEquip_One`; for a Lucky Seven, `ItemObjSevenDirector::vanishAroundEquip` |
| 4 `UpdateKartItem_DestroyOther` | owner, sequence id, `ItemObjBase` + 0x1E4 | `ItemObjDirectorBase::vanish_Force(owner, sequence id, true)` (Blue Shell excepted); the third byte is not read; kept pending when the object is missing |
| 5 `UpdateKartItem_DestroySelf` | owner, sequence id, `ItemObjBase::unk_0x1F5` | `vanish_Force(owner, sequence id)` (Blue Shell excepted); the third byte is not read; kept pending when the object is missing |
| 6 `InitSpin` | owner, sequence id | `ItemObjTailDirector::spinTrig` |
| 7 `Action` | owner, sequence id, target | `setState_LockOn` of the Red Shell, Bob-omb or Blue Shell director |
| 8 `Seven` | the kart's player id; item type = the item used | `isAroundEquip`, then `vanishAroundEquip` |
| 9 `InitUse` | owner, sequence id | only for Lightning (6), Blooper (10) and Super Leaf (14); the others return. Lightning: ignored while the receiver's `m_thunder_time` is at most half its waiting time (900 frames), else `m_thunder_time` = 0 and the user stored at +0xFC; Blooper: the same with `m_gesso_time`, and a Lucky Seven of the user loses its Blooper (`vanishAroundEquip(kart, 10, 0)`). Then `ItemDirector::_entryItem(slot, the user's KartItem)`, the function a kart uses an item with on its own console, with the slot from a `switch` over `eItemType` (6 → 10, 10 → 5, 14 → 13) |
| 10 `UseExpire` | owner, sequence id, a byte the decompilation did not show | Super Leaf only (`eItemType` 14): `vanish_Force_FromOwner(owner)`; the third byte is not read |

- The shells and bananas (types 0 to 3) are not in the `InitUse` switch: probable that a thrown or dropped one appears
  on the other consoles through `SelfMove`.
- Value 3 was named `SevenInitUse` in the template; it is sent by `updateKartItem_EquipItemExit` when an item held
  around or behind a kart leaves it because of a hit (data: the kart, `ItemObjBase` + 0x1E0, the kart item's count),
  and handled for any item type, so the patch renames it `UpdateKartItem_EquipHit`.
- `NetworkGameEventMgr::Buffer` wraps the module the same way for the battle objects
  (`Object::BattleObjectMgrBase::receiveBuffer`); its events were not researched.

### 12. Starting the race together

- `ModeManagerRace::initWait` (and Battle's), when the session is active and the race is not a live view:
  `Sync::ready` and `NetworkSystemInfoManager::m_is_sync_started` = 1.
- `Sync::ready`: marks itself ready in its `NetworkStateManager<Sync>`; `NetworkSystemInfo::m_start_countdown` = 3000
  (a constant loaded next to the function), `m_is_start_counting` = 1, `m_spare_u32` = 0, and the received copies'
  `m_spare_u32` and `m_game_frames_at_receive` cleared.
- `Sync::stateReady`: when every object registered with the system info manager is ready (`NetworkGameMgr` registers
  its delegate to `checkBufferInitialized` in `init`), the state number 2 is requested.
- `Sync::stateSync`: each frame, countdown = min(countdown - 16, for every connected peer: its sent countdown − its
  latency − the ms since its packet arrived); when it reaches 0, `m_is_start_counting` = 0, the state is reset, a
  frame counter is registered and `NetworkEngine::startKeepAliveCheck` runs.
- `ModeManagerRace::calcWait` waits for at least 121 frames (`m_frame_since_sync`) and the end of the sync, then
  `NetworkGameMgr::start(1, ...)`.

### 13. Spectators catching up

- `ModeManagerBase::calc` calls `startWatchFrameSync`: `m_is_sync_started` = 0, `FrameSync::m_is_active` = 1,
  `m_target_player_id` = `CRaceInfo::m_camera_target_player_id`.
- `FrameSync::calc`: `m_frame` counts frames while the race runs and is sent as `m_sync_frame`; the target is the
  followed player's `m_sync_frame` (the highest of all peers when the target is -1). When the own frame is more than
  one behind and `m_wait` is 0, a flag word of the race (0xF in a member at +0x2EC) is set and `m_frame` advanced, and
  `m_wait` = 150 (gap below 4), 75 (below 7), 15, or 2 (gap above 60).
- `goalRace` clears `m_is_active`.

### 14. The end of the race

`ModeManagerBase::stateInitGoal`, in a network race: `Director::changeToAI_NetStop_All`: every kart
`Unit::changeToCPU(true)`, its AI awakened, and `Unit::changeToNetStop` (`m_is_net_send` = `m_is_net_recv` = 0).

### 15. Corrections to the templates and to the menu research

- The SystemInfo members of [Findings 12 and 13](#12-starting-the-race-together) (the start countdown, the bytes at
  0x1C of the format) correct the research on menu multiplayer; the details were added at the end of its document.
- `NetworkItemSlotMgr` is 0x26C bytes (`mov r0, #0x26c` before its construction in `NetworkEngine::createBeforeStructure`),
  and its `Buffer` 0x264; `request` and `judgeMyRequest` use `Buffer::m_request_frames` at Buffer + 0x244.
- `NetData::m_angular_velocity` is the forward direction; `NetTrackData`'s unnamed vector at 0x0C too.
- `NetworkItemSlotMgr::Node::m_player_bit` holds the karts whose request the node's sender accepts, not the consoles
  that accepted the node's own request; `m_0x7` and `m_0xF` are the judged request frames and the taken-over karts
  ([Finding 9](#9-itemslot-item-requests)).
- `NetworkItemEventDataMgr::SSelfMove::is_deflected` is set when the item kept its serial number.
- `NetworkItemEventDataMgr::EEventType::SevenInitUse` is the hit of a held item, for any item type
  ([Finding 11](#11-the-event-channel-itemevent-and-gameevent)).
- `VehicleBase::CreateArg::is_player` is set for the replayed karts in a network race (not renamed: its meaning
  outside network races was not checked).

## Confidence

Nothing in this research was tested in game.

### Certain (read directly in the code)

- The KartData blocks, the content and scales of `NetData`, the event bits and who sets and replays them
  ([Findings 1 to 3](#1-the-kartdata-buffer)).
- Which console drives which kart, the takeover handler, the candidate order and the end of race
  ([Findings 4](#4-who-drives-which-kart), [6](#6-takeover), [14](#14-the-end-of-the-race)).
- What a received kart copies from the block, the delay and missing-block handling
  ([Finding 5](#5-a-received-kart), except the teleport tests).
- The item request scheme, the ItemSlot node and its takeover columns, the stock and equip states, how a replayed
  kart's items follow the node, the count limits, the waiting times and the Lucky Seven rules
  ([Findings 9 and 10](#9-itemslot-item-requests)).
- The ItemEvent types, their data and senders, and which receiver function each one calls
  ([Finding 11](#11-the-event-channel-itemevent-and-gameevent)).
- The event channel ([Finding 11](#11-the-event-channel-itemevent-and-gameevent)), the start countdown and the frame
  catch-up ([Findings 12 and 13](#12-starting-the-race-together)), and the corrections of
  [Finding 15](#15-corrections-to-the-templates-and-to-the-menu-research).
- The GameData format, its acceptance check, `requestGoal` and `setCurrScore` ([Finding 7](#7-gamedata-goals-and-scores)).

### Likely

- That a packet carries at most the console's own kart and three CPUs ([Finding 1](#1-the-kartdata-buffer)).
- The stages of the rank agreement and the meaning of the GameData bitmaps after `m_goal_aid_bits` and
  `m_scores` ([Finding 8](#8-agreeing-on-ranks)): `Rank::calc` was only partly read.
- The teleport conditions of a received kart and the role of `m_net_correction` ([Finding 5](#5-a-received-kart)).
- That in local play a departed player's kart is not taken over ([Finding 6](#6-takeover)).
- Which limit ends an unanswered item request, the roulette or the 120 frames; that the held-item fields follow the
  kart's item ([Finding 9](#9-itemslot-item-requests)).
- The waiting times in seconds: the timers count frames while the race's state is above 1, taken here as from the
  start of the race ([Finding 10](#10-item-limits-and-waiting-times)).
- That thrown shells and bananas, and the items other than Lightning, Blooper and Super Leaf, appear on the other
  consoles through the free-move event and the kart's own state, not through the use event
  ([Finding 11](#11-the-event-channel-itemevent-and-gameevent)).

### Guesses

- That the third policy function, called before taking another kart's goal, checks whether the local kart could still
  beat it.

## Open questions

- `Rank::calc` in full: when exactly a rank is fixed, byte 0x04 of `NetworkGameDataFormat` and byte 0x23 of `Rank`,
  `NetworkGameDataManager` byte 0x8A, and `NetworkGameMgr`'s bytes 0xA8 and 0xBC.
- The position correction of a received kart: the use of `m_net_correction`, `retoucnFollowVecGndNrm`, the teleport
  tests, and the meaning of every value of `sNetRecvParam`.
- The flags of `Kart::Director` at 0x18D, 0x18E and 0x18F (from the mode manager's bytes at 0x4E4 and 0x4E5): 0x18D
  seems to pause the replay ("net curtain").
- The GameEvent payloads (the battle objects), `Field::ObjectIronBall::takeOver` and `Field::ObjectVisualSync`, and
  the coin synchronisation in `CoinManager::syncCoin`.
- Whether anything limits held Lightnings to one at a time: the count limit allows three, and the item probabilities
  (`ItemSlotTable`) were not read. An in-game test with several consoles would settle it.
- Whether `ItemObjBomhei` + 0x258 is ever set (the Bob-omb explosion's third byte), and what the virtual test of
  `ItemObjBomheiDirector::setBurst` checks; what `ItemObjBase` + 0x1E4 and `unk_0x1F5` hold (sent but not read).
- `ItemObjBase::m_is_collisionless`, which decides the `is_serial_kept` flag: the name comes from the template and
  was not checked.
- The capacity of `ItemDirector`'s ring of pending events.
- `NetworkEventModule`'s own layout and size (its members are listed unnamed), and the `NetworkItemEventDataMgr`
  layout around the module.
- `Sequence::BaseRacePage::checkWatchSync` and the flag word set at +0x2EC by `FrameSync::calc`.
- The third argument of `NetworkGameMgr::start`.
