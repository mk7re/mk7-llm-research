# Menu multiplayer

- Status: pending verification
- Asked: Start the research of the menu multiplayer topic from candidates
  - Scope, set by the user when the candidate was written (2026-11-14): the multiplayer application layer, "everything
    that is after NEX and local communication has already been handled. The nex and local layer hands the
    multiplayer logic a series of buffers (eNetworkBufferType). The limit of the research will be the buffers and how
    they are used". This topic covers the menus and the buffer layer that the race research will build on.
- Base commit: 843cc69f11cc3c8b057a1647c3a3c01d13a36186
- Images: `eur2` (sha1 e3edb9771fea3149ddfe309e3ca8453046ef8a95); `dlp` only as the source of names and for one
  comparison ([Finding 17](#17-block-transfer-wbt)). The page flow comes from the scene sequence file
  `MenuScene-Default.bss` of the `eur2` RomFS. Nothing was tested in game: the emulator setup has no way to connect
  two consoles yet.

## Contents

- [Overview](#overview): what was researched and found, for readers new to the topic
  - [Words used in this document](#words-used-in-this-document)
  - [One packet, eleven buffers](#one-packet-eleven-buffers)
  - [Who takes part: racers, spectators and CPUs](#who-takes-part-racers-spectators-and-cpus)
  - [SystemInfo: the heartbeat of every console](#systeminfo-the-heartbeat-of-every-console)
  - [Moving through the menus together](#moving-through-the-menus-together)
  - [What each player chooses: SelectMenu](#what-each-player-chooses-selectmenu)
  - [Choosing the course](#choosing-the-course)
  - [Profiles, Miis and late information](#profiles-miis-and-late-information)
  - [Becoming friends in local play](#becoming-friends-in-local-play)
  - [Sending the course to Download Play consoles](#sending-the-course-to-download-play-consoles)
  - [Local play, step by step](#local-play-step-by-step)
  - [Online play and communities, step by step](#online-play-and-communities-step-by-step)
  - [Spectators](#spectators)
  - [The last step before the race](#the-last-step-before-the-race)
  - [What changes in the templates](#what-changes-in-the-templates)
- [Glossary](#glossary): the classes, members and enums involved, with their offsets; the [functions](#functions) and
  [data](#data) tables with addresses
- [Findings](#findings): each claim with its evidence
  - [Sources and method](#sources-and-method)
  - [1. Creating the buffers](#1-creating-the-buffers)
  - [2. Sending](#2-sending)
  - [3. Receiving](#3-receiving)
  - [4. Stations, aids and player ids](#4-stations-aids-and-player-ids)
  - [5. SystemInfo packets](#5-systeminfo-packets)
  - [6. SystemInfo checks used by the menus](#6-systeminfo-checks-used-by-the-menus)
  - [7. Keep-alive](#7-keep-alive)
  - [8. The shared state number](#8-the-shared-state-number)
  - [9. SelectMenu packets](#9-selectmenu-packets)
  - [10. Pages that move together, VS settings and teams](#10-pages-that-move-together-vs-settings-and-teams)
  - [11. The course vote](#11-the-course-vote)
  - [12. The course chosen by the master](#12-the-course-chosen-by-the-master)
  - [13. Miis](#13-miis)
  - [14. Player profiles](#14-player-profiles)
  - [15. SupplyInfo](#15-supplyinfo)
  - [16. Friends](#16-friends)
  - [17. Block transfer (Wbt)](#17-block-transfer-wbt)
  - [18. Where the network steps sit in the scene sequence](#18-where-the-network-steps-sit-in-the-scene-sequence)
  - [19. Entering the menus: MenuNetworkSelectMenuTask](#19-entering-the-menus-menunetworkselectmenutask)
  - [20. The local handshake](#20-the-local-handshake)
  - [21. The online pages](#21-the-online-pages)
  - [22. Spectators](#22-spectators)
  - [23. The last step: MenuNetworkApplyTask](#23-the-last-step-menunetworkapplytask)
  - [24. The two ways out of the settings pages](#24-the-two-ways-out-of-the-settings-pages)
  - [25. Corrections to the templates and to earlier notes](#25-corrections-to-the-templates-and-to-earlier-notes)
- [Confidence](#confidence): what is certain, what is likely, what is a guess
- [Open questions](#open-questions): what was not resolved
- [Additions from the research on race multiplayer](#additions-from-the-research-on-race-multiplayer): to fold
  into this document by its next pass

## Overview

When two to eight consoles play together, the menus before each race have to agree on a lot: who takes part, the mode
and the engine class, the character and kart of every player, the next course and the order of the karts on the
starting grid. This research covers how the game reaches that agreement once the consoles are connected. How they
connect (local wireless, the online servers, matchmaking, the Download Play transfer itself) is out of scope: the
starting point is the data the game hands to the connection layer every frame, and the data it gets back.

In short:

- Every console sends the others a packet a few times per second. The packet is made of eleven parts called
  **buffers**, one for each kind of data; the menus use six of them, the races the other five
  ([One packet, eleven buffers](#one-packet-eleven-buffers)).
- There is no server that decides for everybody. Each console sends its own state and reads the state of the others.
  Where a single decision is needed (the winning vote, a random course, the random seed of the race), one console, the
  **master**, makes it and the others copy it ([Choosing the course](#choosing-the-course)).
- The menu pages of all consoles move together through a shared **state number**: a console that is done with a page
  asks for the next state, and every console switches when all of them are ready
  ([Moving through the menus together](#moving-through-the-menus-together)).
- Every console also repeats what it knows about the choices of every other player. A console that missed a packet,
  joined late or lost a player still learns those choices from the others
  ([Profiles, Miis and late information](#profiles-miis-and-late-information)).
- A console that joins an online room while a race is running becomes a **spectator**: its packets are ignored, and the
  menus send it straight into the race to watch ([Spectators](#spectators)).
- Before the race, every console computes the same starting order on its own, from the same data and the master's
  random seed ([The last step before the race](#the-last-step-before-the-race)).

All of this was read in the game's code (`eur2`, the European version 1.2) and the scene sequence file of the menus.
Nothing could be tested in game, because the emulator setup cannot connect two consoles yet; what rests on reading
alone is marked as probable in [Confidence](#confidence).

### Words used in this document

- **Console**: one 3DS taking part in the session. The connection layer calls it a **station** and gives it a
  **station id**.
- **Racer** and **spectator**: a racer drives in the race; a spectator only watches it. Up to eight karts race; the
  ones no human drives are **CPUs**.
- **Aid**: a small number (0 to 7 for the racers) that the game gives each racer, human or CPU, and each spectator. The
  data of a player is stored and looked up by aid. In the tables of this research, a player's **player id** is always
  equal to its aid ([Finding 4](#4-stations-aids-and-player-ids)).
- **Master**: the console whose decisions the others follow. The connection layer chooses it; how is out of scope.
- **Buffer**: one of the eleven kinds of data in a packet, and the memory that holds it. Each console has, for each
  kind, one buffer it writes and one buffer per other console that it reads.
- **Phase**: a number every console sends to say where it is (choosing in the menus, the last step before a race, a
  race, the award ceremony) ([SystemInfo](#systeminfo-the-heartbeat-of-every-console)).
- **Local play** is local wireless multiplayer, Download Play included; **online play** is play over the internet,
  with **communities** as a kind of online room.

### One packet, eleven buffers

The eleven kinds of data have fixed maximum sizes, and a packet holds them one after the other, after a 28-byte header
that gives the size of each one. The largest packet is 3372 bytes ([Finding 1](#1-creating-the-buffers)).

| Buffer | Used by | What it carries |
| --- | --- | --- |
| SystemInfo | menus and races | the heartbeat of each console: sequence number, phase, profile, who is connected, timing |
| SelectMenu | menus | the player's choices: mode, class, vote, character, kart, settings, teams |
| GameData, KartData, ItemSlot, ItemEvent, GameEvent | races | not covered here: see the race research |
| Wbt | loading | pieces of the course file sent to Download Play consoles |
| Friend | local menus | what is needed to register each other as friends |
| Mii | menus | the player's Mii |
| NetworkSupplyInfo | menus | the choices of every player, as this console knows them |

Each frame, every part of the game that has something to send writes it into its buffer, replacing what was there.
The packet goes out at a fixed rate, not every frame: online, every 16 milliseconds to one other console at a time,
taking turns; in local play, to all consoles at once, every 112 milliseconds at first. Outside races, online play adds
50 milliseconds to the wait ([Finding 2](#2-sending)). So only the latest data of each kind reaches the others; a value
written and replaced between two packets is never sent.

On the receiving side, the packet is cut back into its eleven parts, and each part is stored as the latest data of that
kind from that console. It becomes readable at the start of the next frame, so that a page never sees it change in the
middle of a frame. A kind can refuse a packet: SystemInfo drops packets older than the last one it accepted
([Finding 3](#3-receiving)).

### Who takes part: racers, spectators and CPUs

The connection layer keeps two lists of consoles: the racers and the spectators. The game numbers them: first the human
racers, then the spectators, then the CPUs, which get the numbers after the last human. Only racers, human or CPU, get a
slot for incoming data: a packet from a spectator is dropped as soon as it arrives ([Finding 4](#4-stations-aids-and-player-ids)).

A console also knows whether it is itself a racer. Until the master's list of racers holds it, it is not, and while it
is not, it sends neither its SystemInfo nor its SelectMenu data ([Finding 4](#4-stations-aids-and-player-ids)).

### SystemInfo: the heartbeat of every console

Every console sends its SystemInfo data with every packet. It holds:

- a **sequence number**, increased with every packet. A packet whose number is not higher than the last one accepted
  from that console is dropped, so late or repeated packets do no harm;
- the **phase**: choosing in the menus, the last step before the race, the race (in local play, its race number) or the
  award ceremony. A packet from another phase is normally dropped, so that data from the menus cannot mix with data from
  a race;
- the player's **profile**: rating (VR), wins and losses, the character and kart parts shown on the profile, the player
  id of the 3DS account, the country;
- **who the console sees**: the racers it is connected to, and the station ids of the human racers;
- **timing**: each console sends its clock and echoes the clocks it received, so that each console can measure the
  round trip to every other one; during a race, its game frame;
- the **master's random seed** and a few values of the master that the others copy: a course chosen without a vote, the
  race number of a community match, whether the master still accepts new players.

The menus use it to check that every console sees the same set of racers before going on, and to notice a console that
has gone silent: consoles nobody has heard from for a few seconds are dropped (probable)
([Findings 5 to 7](#5-systeminfo-packets)).

### Moving through the menus together

The pages of all consoles stay in step through a shared state number, from 0 to 16, kept by `NetworkSelectMenuProcess`.
A console that is done with a page asks for the next number and marks itself ready. Every console switches to the new
number once all connected racers are ready at the same number; a console that sees another one already ahead catches
up at once ([Finding 8](#8-the-shared-state-number)). The numbers mean nothing by themselves: a page only waits for the
number to change.

Some pages are chosen on every console, others only on the master's. On a page of the second kind, the other consoles
show the page, wait for the change of state number, then for the master's SelectMenu data, and then copy the master's
choice ([Finding 10](#10-pages-that-move-together-vs-settings-and-teams)). Which page is of which kind was not mapped
one by one; what each page sends suggests that the character and kart pages are chosen on every console, and the
mode, class and cup pages on the master's.

### What each player chooses: SelectMenu

Every racer sends, with every packet, its SelectMenu data: the mode and engine class (only the master's count), its
course vote, its character, body, tires and glider, its points and rank so far, the button that ended the last shared
page, and, from the master, the settings of the VS page, the number of CPUs, the unlocked cups and the teams
([Finding 9](#9-selectmenu-packets)).

On the VS settings page, only the master can change the settings, and the others see its choices live: the master
writes the value of every setting into its data every frame, and the other consoles set their own controls to those
values. When teams are on, the master decides the team of every player: the other consoles follow its choice live,
and get the final list of teams when the master confirms the page, which it can only do while the teams are balanced
(they may differ by one at most) ([Finding 10](#10-pages-that-move-together-vs-settings-and-teams)).

### Choosing the course

There are two ways to pick the next course.

- **The vote** (course page, or "random" on the course page): each racer sends its vote. The master puts the votes in a
  list that the others copy, so that every console shows them in the same order. Once every vote is in, the master
  draws one of them at random; if the drawn vote is "random", the master also draws a course. The others copy
  both, and the roulette starts once every console shows the same result ([Finding 11](#11-the-course-vote)).
- **No vote**: in local play, when the settings say "random" or "in order" for the course, and in a Grand Prix, the
  master picks the course itself and sends it in its SystemInfo data; every console waits until all of them show the
  same course ([Finding 12](#12-the-course-chosen-by-the-master)).

### Profiles, Miis and late information

Each console sends its player's Mii as a small packet in the Mii buffer; the game turns the Miis of all racers back
into full Miis for the menus and the race. A player who has left gets a random default Mii ([Finding 13](#13-miis)).
The profiles shown in the menus (Mii, rating, character) are built from the Mii and SystemInfo data of each racer
([Finding 14](#14-player-profiles)).

The NetworkSupplyInfo buffer fills the gaps. Every console sends, for every player it knows of, that player's choices
packed into five bytes (character, kart parts, points, rank, course, mode and team), and keeps the profile and Mii it
received from each console. When a console needs everybody's choices (when joining, between online races, or for a
player who has left), it merges these reports: for each player, the report from the console heard from most recently
wins, and a console's report about its own player wins over all others ([Finding 15](#15-supplyinfo)). This is how a
spectator learns the settings of the race it joins, and how a player who left still appears with the right character.

### Becoming friends in local play

In the local lobby, a player can tick the other consoles they want to register as friends. During the handshake after
the lobby, every console sends the data its system needs to register a friend, and the list of consoles its player
ticked. Two consoles become friends only if both players ticked each other; a system message then shows the new
friend's Mii name ([Finding 16](#16-friends)).

### Sending the course to Download Play consoles

A console that joined through Download Play does not have the game's courses, so the master sends it the course file
and the course's sound data before each race. The data is cut into pieces of 892 bytes and sent six packets per frame;
the receiving consoles ask again for the pieces they missed. The game itself (the one on a game card or installed) is
always the sender, or a console that takes part without receiving anything: the receiving code is turned off in it, and
only runs in the separate Download Play program ([Finding 17](#17-block-transfer-wbt)).

### Local play, step by step

After choosing local multiplayer, the player joins or creates a group, waits in the lobby for the host to start, and then
goes through the handshake: every console checks that all see the same racers, exchanges the friend data, registers the
new friends and receives the master's random seed. From then on, the set of consoles is fixed for the menus. Then come
the mode, the class (Grand Prix), the character, the kart, the settings (VS and battles) and the course pages, and
finally the last step before the race. After a race, the next one goes straight to the course page, skipping the
character and kart pages ([Findings 18 to 20](#18-where-the-network-steps-sit-in-the-scene-sequence)).

### Online play and communities, step by step

Online, the player first chooses the opponents (anybody, friends, a community), then the mode, character and kart, and
waits in the matchmaking room. The room closes when more than seven consoles are connected, or after five seconds (300
frames) with at least two, and the consoles introduce their Miis on the globe. Then come a waiting page, a timed "next race" page and
the course vote. Between races only the waiting page, the "next race" page and the course pages run: the character and
kart chosen at the start are kept. A community match ends after four races and goes back to the community lobby
(probable) ([Finding 21](#21-the-online-pages)).

### Spectators

A console that joins an online room or community match while a race is running is put among the spectators by the
connection layer. The menu pages notice that a race is running (another console's phase is "race"), wait until they
have the settings of every player, the profiles and the master's seed, and then skip all choice pages and go straight to
the race. The spectator has no kart: its camera follows a chosen player if that player races, else a friend among the
racers, else any racer. The character it chose before is kept and restored after the race, when it joins as a racer
([Finding 22](#22-spectators)).

### The last step before the race

Just before the race (and the course download in local play), a step common to all modes writes everything into the
race settings: the master marks the players as decided, the course and mode are taken from the agreed data, and the
character, kart, rating, points and team of every human are filled in, then the CPUs. A player who left is filled in
from the merged reports, and one without any data gets Mario with the default kart. The total ranking and the starting
order are computed by every console on its own: CPUs without a rank get a random one, and the random numbers come from
the master's seed, so all consoles get the same result ([Finding 23](#23-the-last-step-menunetworkapplytask)).

### What changes in the templates

The research names most of what the menus send and receive, and corrects a size and several names in the templates
([Finding 25](#25-corrections-to-the-templates-and-to-earlier-notes)). The main ones: the class that keeps the
SystemInfo data was 0x18 bytes larger than the templates said; the SelectMenu field named "course id" is the index of
the winning vote; the two tables of the station manager named "racers" and "audience" hold the humans and the CPUs;
and the bitmap named "free aids" holds the aids of the human racers.

## Glossary

All offsets are those of `eur2`, relative to the start of the class of the table. Status `existing` means named in
`template/` already, `renamed` that the patch changes the name, `new` that the patch adds it.

### Net::eNetworkBufferType (enum class : u8, template/Net/eNetworkBufferType.hpp)

Existing. The sizes are those of the buffer size table `Net::sNetworkBufferSizes`, and match the comments of the enum.

| Value | Name | Size | Note |
| --- | --- | --- | --- |
| 0 | `SystemInfo` | 0xA0 | [Finding 5](#5-systeminfo-packets) |
| 1 | `SelectMenu` | 0xA0 | [Finding 9](#9-selectmenu-packets) |
| 2 | `GameData` | 0x30 | race |
| 3 | `KartData` | 0x230 | race; the only type split into blocks on receipt |
| 4 | `ItemSlot` | 0x24 | race |
| 5 | `ItemEvent` | 0x200 | race |
| 6 | `Wbt` | 0x384 | [Finding 17](#17-block-transfer-wbt) |
| 7 | `Friend` | 0x264 | [Finding 16](#16-friends) |
| 8 | `GameEvent` | 0x40 | race |
| 9 | `Mii` | 0xC0 | [Finding 13](#13-miis) |
| 10 | `NetworkSupplyInfo` | 0x64 | [Finding 15](#15-supplyinfo) |
| 11 | `Container` | 0xD2C | the whole packet: a 0x1C-byte header and the eleven types |

### Net::NetworkBufferController (size 0x50, template/Net/NetworkBufferController.hpp)

The buffers of one type: one write buffer and eight read buffers, each double buffered. `Net::NetworkSendBufferController`
is the same class for type 11, the packet as sent.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_type` | 0x04 | `eNetworkBufferType` | existing | |
| `m_write_buffers` | 0x08 | `sead::PtrArray<Buffer>` | existing | one entry |
| `m_read_buffers` | 0x14 | `sead::PtrArray<Buffer>` | existing | eight entries, indexed by buffer id |
| `m_total_recv_buffer` | 0x28 | `u32` | existing | 8 |
| `on_received_delegate1R` | 0x2C | `void *` | existing | the receive delegate of the data manager; null: every packet is stored |
| `m_has_recv_bitfield` | 0x4C | `u8` | existing | aids whose data of this type arrived since the last `resetReceiveBmp` |
| `m_empty_recv_bitfield` | 0x4D | `u8` | renamed | was `m_connector_ack_bitfield`; aids whose last packet held none of this type; 0xFF at start |

#### Net::NetworkBufferController::Buffer (size 0x1C)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_double_buffer` | 0x00 | `sead::FixedPtrArray<NetworkBuffer, 2>` | existing | |
| `m_active_buffer` | 0x14 | `u32` | existing | the half the game reads or writes |
| `m_should_swap` | 0x18 | `bool` | existing | read buffer: new data waits in the other half |

### Net::NetworkStationBufferManager (size 0xE0, template/Net/NetworkStationBufferManager.hpp)

Owns the eleven controllers and the tables that turn stations into aids, player ids and buffer ids.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_buffer_controllers` | 0x00 | `sead::PtrArray<NetworkBufferController>` | existing | by type, 0 to 10 |
| `m_container_controller` | 0x0C | `NetworkBufferController` | existing | a `NetworkSendBufferController`, type 11 |
| `m_station_access_info_racers` | 0x5C | `StationAccessInfo` | existing | list type 0 |
| `m_station_access_info_audience` | 0x6C | `StationAccessInfo` | existing | list type 1 |
| `m_connector_info_humans` | 0x7C | `sead::Buffer<ConnectorInfo>` | renamed | was `m_connector_info_racers`; by aid: human racers, then spectators |
| `m_connector_info_cpus` | 0x84 | `sead::Buffer<ConnectorInfo>` | renamed | was `m_connector_info_audience`; by aid: the CPU slots |
| `m_human_connectors` | 0x8C | `sead::PtrArray<ConnectorInfo>` | new | racers and spectators |
| `m_racer_connectors` | 0x98 | `sead::PtrArray<ConnectorInfo>` | renamed | was `m_player_without_deleted`; human racers, disconnected ones included |
| `m_other_racer_connectors` | 0xA4 | `sead::PtrArray<ConnectorInfo>` | renamed | was `m_other_player_not_deleted`; the same without the local station |
| `m_without_unregistered` | 0xB0 | `sead::PtrArray<ConnectorInfo>` | existing | `m_other_racer_connectors` without the disconnected stations |
| `m_player_id_to_aid` | 0xBC | `sead::Buffer<s32>` | existing | identity in practice |
| `m_buffer_id_to_aid` | 0xC4 | `sead::Buffer<s32>` | existing | |
| `m_racer_aid_bits` | 0xCC | `u8` | renamed | was `m_free_aid_bits`; aids of the human racers |
| `m_unregistered_aid_bits` | 0xCD | `u8` | existing | aids of the disconnected human racers |
| `m_registered_aid_bits` | 0xCE | `u8` | existing | connected human racers |
| `m_player_num` | 0xD0 | `s32` | existing | entries of `m_racer_connectors` |
| `m_human_num` | 0xD4 | `s32` | new | was an unknown 8-byte member; entries of `m_connector_info_humans` in use |
| `m_connected_human_num` | 0xD8 | `s32` | new | the same without the disconnected stations |
| `m_wbt_started` | 0xDC | `u8` | existing | set while a block transfer runs |

#### Net::NetworkStationBufferManager::StationInfo (size 0x14)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_status` | 0x00 | `Status` | existing | 1 `Registered`, 2 `Unregistered` (the console left) |
| `m_is_ai` | 0x04 | `bool` | existing | a CPU slot |
| `m_station_id` | 0x08 | `s32` | existing | 0 for CPUs |
| `m_do_handle` | 0x0C | `void *` | existing | the connection layer's handle |
| `m_buffer_id` | 0x10 | `s32` | existing | slot in the read buffers; -1 for spectators |

#### Net::NetworkStationBufferManager::ConnectorInfo (size 0xC)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_station_info` | 0x00 | `StationInfo *` | existing | |
| `m_player_id` | 0x04 | `s32` | existing | equal to `m_aid` |
| `m_aid` | 0x08 | `u32` | existing | |

### Net::NetworkEngine (size 0x598, template/Net/NetworkEngine.hpp)

The owner of the network managers.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_network_mode` | 0x134 | `ENetworkMode` | existing | |
| `m_network_station_buffer_manager` | 0x25C | `NetworkStationBufferManager *` | existing | |
| `m_local_station_id` | 0x264 | `s32` | existing | |
| `m_local_player_id` | 0x268 | `s32` | existing | |
| `m_master_player_id` | 0x270 | `s32` | existing | the local console is the master when equal to `m_local_player_id` |
| `m_is_accepting_players` | 0x27C | `bool` | new | set by `acceptPlayers`; clients copy the master's |
| `m_is_players_decided` | 0x27D | `bool` | new | set by `decidePlayers`; clients copy the master's |
| `m_is_not_racer` | 0x280 | `bool` | new | set by `initNetworkInfo`, cleared once the master lists the local station |
| `m_network_error_handler` | 0x290 | `NetworkErrorHandler *` | existing | |
| `m_network_system_info_manager` | 0x298 | `NetworkSystemInfoManager *` | existing | |
| `m_network_wbt_mgr` | 0x2A8 | `NetworkWbtMgr *` | existing | |
| `m_network_friends_manager` | 0x2AC | `NetworkFriendsManager *` | existing | |
| `m_network_mii_manager` | 0x2B0 | `NetworkMiiManager *` | existing | |
| `m_network_supply_info_manager` | 0x2B4 | `NetworkSupplyInfoManager *` | existing | |
| `m_network_player_data_manager` | 0x2B8 | `NetworkPlayerDataManager *` | existing | |
| `m_dlp_child_aid_bits` | 0x438 | `u8` | new | `withDlp` tests it |
| `m_is_wbt_running` | 0x4B4 | `bool` | new | |
| `m_heard_aid_bits` | 0x4F0 | `u8` | new | set by `NetworkSystemInfo::onReceivedCore` |
| `m_no_send_delay` | 0x534 | `u32` | new | 0: `NetworkSendPolicy::send` waits 50 ms more |

#### Net::NetworkEngine::ENetworkMode (enum class : s32)

Existing; the patch adds `LOCAL`.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `LOCAL` | new | `LocalMatchingManager` |
| 1 | `WIFI` | existing | `WifiMatchingManager` |

### Net::NetworkDataManager\<T\> (template/Net/NetworkDataManager.hpp)

The base of every per-type manager: the data `T` the console sends, and the receive delegate. Offsets depend on the
size of `T`; those given are for `NetworkSystemSendFormat`. Existing, unchanged.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_node_data` | 0x10 | `T` | existing | what this console sends |
| `m_network_buffer_type` | 0xB0 | `eNetworkBufferType` | existing | |
| `m_network_buffer_controller` | 0xB4 | `NetworkBufferController *` | existing | |
| `m_network_station_buffer_manager` | 0xB8 | `NetworkStationBufferManager *` | existing | |
| `m_delegate_on_received` | 0xBC | `sead::Delegate1R<...>` | existing | stored in the controller's `on_received_delegate1R` by `init` |
| `m_network_engine` | 0xCC | `NetworkEngine *` | existing | |
| `unk` | 0xEC | `bool` | existing | set: `onReceived` accepts without calling `onReceivedCore` |

### Net::NetworkSystemSendFormat (size 0xA0, template/Net/NetworkSystemSendFormat.hpp)

What each console sends in the SystemInfo buffer.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_sequence` | 0x00 | `u64` | new | |
| `m_spare_u16` | 0x08 | `u16` | new | copied from `NetworkSystemInfo::m_spare_u16`; no writer found |
| `m_sequence_sync_return_code` | 0x0A | `u8` | new | race |
| `m_phase` | 0x0B | `EPhase` | new | |
| `m_spare_u32` | 0x0C | `u32` | new | copied from `NetworkSystemInfo::m_spare_u32`; no writer found |
| `m_game_frame` | 0x10 | `s32` | renamed | was `m_master_game_frame`: every console sends its own |
| `m_community_race_point` | 0x14 | `u8` | new | |
| `m_race_num` | 0x15 | `u8` | new | |
| `m_lobby_talk_id` | 0x16 | `u8` | new | |
| `m_decided_course_id` | 0x17 | `u8` | new | |
| `m_master_random` | 0x18 | `u32` | existing | |
| `m_flags` | 0x1E | `u8` | new | `EFlags`; bits 1 and 2 are cleared by the menus, their meaning is open |
| `m_player_data` | 0x20 | `System::PlayerDataNoMii` | new | its `rate` is the VR |
| `m_connected_racer_aid_bits` | 0x66 | `u8` | new | |
| `m_heard_aid_bits` | 0x67 | `u8` | new | |
| `m_match_flags` | 0x68 | `u8` | new | `EMatchFlags` |
| `m_racer_station_ids` | 0x6C | `u32[8]` | new | |
| `m_latency_timestamps` | 0x8C | `u16[8]` | new | |

Bytes 0x1F and 0x62 to 0x65 carry race data (a flag of the race director, and the two state numbers of the race's
finish synchronisation) and are left to the race research.

#### Net::NetworkSystemSendFormat::EPhase (enum class : u8)

New; named by this research. In local play a race sends its race number, which is always below `WIFI_RACE`.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0x31 | `WIFI_RACE` | new | set when an online race starts |
| 0x32 | `SELECT_MENU` | new | set by `MenuNetworkSelectMenuTask::onTaskStart` |
| 0x33 | `TROPHY` | new | set by `TrophyPage::enter` when another race follows |
| 0x34 | `APPLY` | new | set by `MenuNetworkApplyTask::onTaskStart` |

#### Net::NetworkSystemSendFormat::EFlags (enum : u8) and EMatchFlags (enum : u8)

New; named by this research.

| Enum | Value | Name | Note |
| --- | --- | --- | --- |
| `EFlags` | 0x01 | `SEND_PLAY_LOG` | online master: from a setting of the server; clients copy it |
| `EMatchFlags` | 0x01 | `ACCEPTING_PLAYERS` | `NetworkEngine::m_is_accepting_players` |
| `EMatchFlags` | 0x02 | `PLAYERS_DECIDED` | `NetworkEngine::m_is_players_decided` |

### Net::NetworkSystemInfo (size 0x208, template/Net/NetworkSystemInfo.hpp)

The SystemInfo data manager (`NetworkDataManager<NetworkSystemSendFormat>`). The template gave size 0x1F0.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_spare_u16` | 0xEE | `u16` | new | no writer found |
| `m_spare_u32` | 0xF0 | `u32` | new | no writer found |
| `m_last_sequences` | 0xF4 | `sead::Buffer<u64>` | new | by aid |
| `m_last_received` | 0xFC | `sead::Buffer<NetworkSystemSendFormat>` | new | by aid; 0x9C bytes copied |
| `m_racer_station_id_num` | 0x108 | `u32` | new | |
| `m_other_phase_received` | 0x10C | `bool[2]` | new | |
| `m_other_phase_received_index` | 0x10E | `u8` | new | toggled by every received packet |
| `m_accept_other_phase` | 0x10F | `bool` | new | |
| `m_skip_game_frame` | 0x110 | `bool` | new | no writer found |
| `m_latencies` | 0x112 | `u16[8]` | new | ms, by aid |
| `m_last_accepted_ticks` | 0x128 | `u64[8]` | new | |
| `m_accepted_intervals` | 0x168 | `u64[8]` | new | |
| `m_ticks` | 0x1A8 | `u64[8]` | existing | tick of the last packet of each aid, accepted or not |
| `m_game_frames_at_receive` | 0x1E8 | `s32[8]` | new | used by `NetworkSystemInfoManager::getMasterGameFrame` |

### Net::NetworkSystemInfoManager (size 0x2F0, template/Net/NetworkSystemInfoManager.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_system_info` | 0x40 | `NetworkSystemInfo` | existing | size 0x208, was 0x1F0; the race synchronisation objects follow it from 0x248 |

### Net::NetworkStateCalc (size 0x2C, template/Net/NetworkStateCalc.hpp)

New class in the templates (name from `dlp`). A state number the connected racers change together.
`Net::NetworkStateManager<T>` (size 0x4C) adds a `Util::TStateObserver<T>` at 0x2C, whose state functions belong to
`T`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `onChangeState` | vtable 0 | virtual | new | called when the state switches |
| `onDisconnect` | vtable 1 | virtual | new | called by `updateDisconnect_` |
| `m_is_active` | 0x04 | `bool` | new | set by `init` |
| `m_ready_aid_bits` | 0x05 | `u8` | new | |
| `m_states` | 0x08 | `sead::Buffer<u8>` | new | by aid |
| `m_requested_state` | 0x10 | `s32` | new | -1: none |
| `m_waiting_state` | 0x14 | `u8` | new | |
| `m_waiting_ready` | 0x15 | `bool` | new | |
| `m_state_changed` | 0x16 | `bool` | new | |
| `m_network_engine` | 0x18 | `NetworkEngine *` | new | |
| `m_connected_racer_aid_bits` | 0x28 | `u8` | new | |
| `m_state_observer` | 0x2C | `Util::TStateObserver<T>` | new | in `NetworkStateManager<T>`; its `m_state_current` is the agreed state |

### Net::NetworkSelectMenuSendFormat (size 0x9C, template/Net/NetworkSelectMenuSendFormat.hpp)

What each racer sends in the SelectMenu buffer. The constructor sets the values given as "none" below.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_mode` | 0x00 | `u8` | new | values differ between local and online play |
| `m_engine_class` | 0x01 | `u8` | new | |
| `m_course_vote` | 0x02 | `u8` | new | 0xFF: none; bit 7: a battle course |
| `m_selected_course_vote_index` | 0x03 | `u8` | renamed | was `m_course_id`; 0x27: none |
| `m_driver_id` | 0x04 | `u8` | existing | 0x12: none (constructor); 0x13: no data |
| `m_body_id` | 0x05 | `u8` | existing | 0x11: none |
| `m_wing_id` | 0x06 | `u8` | existing | 7: none |
| `m_tire_id` | 0x07 | `u8` | existing | 10: none |
| `m_selected_random_course_id` | 0x08 | `u8` | new | |
| `m_page_return_code` | 0x09 | `u8` | new | |
| `m_vs_settings` | 0x0A | `u8[5]` | new | 8: not set |
| `m_race_rank` | 0x0F | `u8` | new | |
| `m_race_point` | 0x10 | `u16` | new | 0x141: none |
| `m_red_team_bits` | 0x12 | `u8` | new | the master's: bit per player id, set for red |
| `m_team_assign_bits` | 0x13 | `u8` | new | the master's: players who still have to take their team from it |
| `m_cpu_num` | 0x14 | `u8` | new | `MenuData::m_num_free_player_slots` of the master |
| `m_unlocked_cups` | 0x15 | `u8` | new | |
| `m_flags` | 0x16 | `u8` | new | `EFlags`; bits 0, 1 and 3 are open |
| `m_course_vote_list` | 0x18 | `CourseVoteEntry[8]` | new | the master's: the votes in the order shown |
| `m_team_list` | 0x58 | `TeamEntry[8]` | new | the master's final teams |
| `m_select_state` | 0x98 | `u8` | new | |
| `m_select_ready` | 0x99 | `bool` | new | |

#### Net::NetworkSelectMenuSendFormat::CourseVoteEntry, TeamEntry (size 0x8 each) and EFlags (enum : u8)

New; named by this research.

| Member or value | Offset or value | Type | Note |
| --- | --- | --- | --- |
| `CourseVoteEntry::m_station_id` | 0x00 | `u32` | the voter; 0: empty entry |
| `CourseVoteEntry::m_course_id` | 0x04 | `u8` | `RaceSys::ECourseID` |
| `TeamEntry::m_station_id` | 0x00 | `u32` | |
| `TeamEntry::m_is_red` | 0x04 | `bool` | |
| `EFlags::TEAM_RED` | 0x04 | | the sender's player is on the red team |

### Net::NetworkSelectMenuDataManager (size 0x5CC, template/Net/NetworkSelectMenuDataManager.hpp)

New in the templates. The SelectMenu data manager (`NetworkDataManager<NetworkSelectMenuSendFormat>`, whose
`m_node_data` is at 0x10 and controller pointer at 0xB0).

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_received` | 0xEC | `NetworkSelectMenuSendFormat[8]` | new | by aid; 0x9A bytes copied |

### Net::NetworkSelectMenuProcess (size 0x634, template/Net/NetworkSelectMenuProcess.hpp)

Kept in `Sequence::MenuData::m_network_select_menu_process`. Its virtual functions are the eighteen state functions
`stateSelectWait` and `stateSelectChange` to `stateSelectChange17`, all empty.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_select_state` | 0x04 | `NetworkStateManager<NetworkSelectMenuProcess>` | new | |
| `m_data_manager` | 0x58 | `NetworkSelectMenuDataManager` | new | replaces three members of the template, below |
| `m_selected_course_vote_index` | 0x6B | `u8` | renamed | now `m_data_manager.m_node_data.m_selected_course_vote_index` |
| `m_selected_random_course_id` | 0x70 | `u8` | renamed | now `m_data_manager.m_node_data.m_selected_random_course_id` |
| `m_buffer_controller` | 0x108 | `NetworkBufferController *` | renamed | now `m_data_manager.m_network_buffer_controller` |

### Net::MiiSendFormat, Net::NetworkMiiStorage, Net::NetworkMiiManager (template/Net/NetworkMiiManager.hpp)

New in the templates (names from `dlp`). `MiiSendFormat` (size 0x88) is a CFL net packet, `m_packet`.
`NetworkMiiManager` (size 0x520) is `NetworkDataManager<MiiSendFormat>`; `NetworkMiiStorage` (size 0x500) holds the
decoded Miis.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `NetworkMiiManager::m_storage` | 0xD8 | `NetworkMiiStorage *` | new | |
| `NetworkMiiManager::m_last_received` | 0xE0 | `MiiSendFormat[8]` | new | by aid; no writer found, so always zero |
| `NetworkMiiStorage::m_nodes` | 0x000 | `sead::PtrArray<Node>` | new | object array of capacity 10 |
| `NetworkMiiStorage::m_node_storage` | 0x014 | `Node[10]` | new | |
| `NetworkMiiStorage::m_nodes_by_player_id` | 0x474 | `Node *[10]` | new | |
| `NetworkMiiStorage::m_net_info_work` | 0x49C | `void *` | new | |
| `NetworkMiiStorage::m_my_store_data` | 0x4A0 | `CFLStoreData` | new | |
| `Node::m_aid` | 0x00 | `s32` | new | |
| `Node::m_player_id` | 0x04 | `s32` | new | |
| `Node::m_is_valid` | 0x08 | `bool` | new | |
| `Node::m_store_data` | 0x0C | `CFLStoreData` | new | |

### Net::NetworkPlayerData (size 0xA8, template/Net/NetworkPlayerData.hpp)

`System::PlayerData` (profile and Mii) and two members.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_race_point` | 0xA0 | `u32` | renamed | was `m_0xA0` |
| `m_created` | 0xA4 | `bool` | existing | filled from received data |

### Net::NetworkPlayerDataManager (size 0xE00, template/Net/NetworkPlayerDataManager.hpp)

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_network_player_datas` | 0x000 | `NetworkPlayerData[10]` | new | by player id |
| `m_network_player_datas_connected` | 0x690 | `NetworkPlayerData[10]` | existing | the local player first |
| `m_connected_mii_datas` | 0xD20 | `CFLStoreData *[10]` | new | |
| `m_my_player_data` | 0xD48 | `NetworkPlayerData` | new | |
| `m_is_built` | 0xDF0 | `bool` | new | |
| `m_is_player_info_updated` | 0xDF1 | `bool` | new | set by `NetworkEngine::updatePlayerInfo` and `BaseRacePage::calcSave`; no reader found |
| `m_racer_num` | 0xDF4 | `s32` | new | the local player counted only when a racer |
| `m_connected_num` | 0xDF8 | `s32` | new | |

### Net::RaceSetting, Net::PlayerInfo, Net::NetworkSupplyInfoSendFormat, Net::NetworkSupplyInfoManager (template/Net/NetworkSupplyInfoManager.hpp)

New in the templates (names from `dlp`). `RaceSetting` (size 0x8) is one player's choices packed into 39 bits,
`m_bits`. `PlayerInfo` (size 0xC) is one entry of `NetworkSupplyInfoSendFormat` (size 0x60, `m_player_infos[8]` by
player id). `NetworkSupplyInfoManager` (size 0xEE8) is `NetworkDataManager<NetworkSupplyInfoSendFormat>`.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `PlayerInfo::m_principal_id` | 0x0 | `u32` | new | 0: empty entry |
| `PlayerInfo::m_race_setting` | 0x4 | `RaceSetting` | new | all zero: empty entry |
| `NetworkSupplyInfoManager::m_inner_player_infos` | 0x0B0 | `InnerPlayerInfo[8]` | new | by player id |
| `NetworkSupplyInfoManager::m_ex_settings` | 0x630 | `sead::PtrArray<ExSetting>` | new | object array of capacity 8 |
| `NetworkSupplyInfoManager::m_ex_setting_storage` | 0x644 | `ExSetting[8]` | new | |
| `InnerPlayerInfo::m_key` | 0x00 | `u64` | new | 0: no entry |
| `InnerPlayerInfo::m_player_info` | 0x08 | `PlayerInfo *` | new | |
| `InnerPlayerInfo::m_ex_setting` | 0x0C | `ExSetting *` | new | |
| `InnerPlayerInfo::m_select_menu_info` | 0x10 | `NetworkSelectMenuSendFormat` | new | |
| `ExSetting::m_station_id` | 0x000 | `s32` | new | |
| `ExSetting::m_player_data` | 0x008 | `System::PlayerData` | new | |
| `ExSetting::m_store_data` | 0x0A8 | `CFLStoreData` | new | second copy of the Mii |
| `ExSetting::m_has_mii` | 0x108 | `bool` | new | |

### Net::FriendApproachSendFormat and Net::NetworkFriendsManager (size 0xA800, template/Net/NetworkFriendsManager.hpp)

`FriendApproachSendFormat` (size 0x264) is new, named by this research.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `FriendApproachSendFormat::m_approach_context` | 0x000 | `u8[0x200]` | new | from `nn::friends` `GetMyApproachContext` |
| `FriendApproachSendFormat::m_friend_codes` | 0x200 | `u8[8][0xC]` | new | scrambled local friend codes |
| `FriendApproachSendFormat::m_is_valid` | 0x260 | `bool` | new | |
| `NetworkFriendsManager::m_my_principal_id` | 0xA314 | `u32` | existing | |
| `NetworkFriendsManager::m_approach_send_format` | 0xA448 | `FriendApproachSendFormat` | new | |
| `NetworkFriendsManager::m_approach_context_result` | 0xA7F8 | `s32` | new | |
| `NetworkFriendsManager::m_approach_flags` | 0xA7FC | `u8` | new | `EApproachFlags`: 0x01 `APPROACH_CONTEXT_OK`, 0x08 `NO_APPROACH`; bits 1 and 2 mark two error results |

### Net::WbtProtocol (size 0x584C, template/Net/WbtProtocol.hpp)

New in the templates (name from `dlp`). The block transfer protocol of one console. `PacketHeader` (size 0x8) starts
every packet; `Block` (size 0xC) is one registered data block.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_is_parent` | 0x000 | `bool` | new | |
| `m_is_running` | 0x001 | `bool` | new | |
| `m_is_finished` | 0x002 | `bool` | new | |
| `m_is_dummy_child` | 0x003 | `bool` | new | |
| `m_player_id` | 0x004 | `s32` | new | 0 for the parent |
| `m_chunk_size` | 0x008 | `s32` | new | 892 |
| `m_max_size` | 0x00C | `s32` | new | 360000; no reader found |
| `m_block_num` | 0x010 | `s32` | new | |
| `m_blocks` | 0x014 | `Block[16]` | new | |
| `m_current_block_id` | 0x0D4 | `s32` | new | |
| `m_chunk_cursor` | 0x0D8 | `s32` | new | |
| `m_child_block_index` | 0x0DC | `s32` | new | |
| `m_child_chunk_num` | 0x0E0 | `s32` | new | |
| `m_child_received_num` | 0x0E4 | `s32` | new | |
| `m_child_chunk_size` | 0x0E8 | `s32` | new | |
| `m_child_received_bits` | 0x0EC | `u32[400]` | new | |
| `m_child_request_cursor` | 0x72C | `s32` | new | |
| `m_child_aid_bits` | 0x730 | `u32` | new | |
| `m_wait_aid_bits` | 0x734 | `u32` | new | |
| `m_child_block_ids` | 0x738 | `s32[32]` | new | |
| `m_parent_chunk_num` | 0x7B8 | `s32` | new | |
| `m_request_buffer` | 0x7BC | `u16 *` | new | ring buffer, capacity 0x2800 |
| `m_request_capacity` | 0x7C0 | `s32` | new | |
| `m_request_head` | 0x7C4 | `s32` | new | |
| `m_request_num` | 0x7C8 | `s32` | new | |
| `m_request_storage` | 0x7CC | `u16[0x2800]` | new | |
| `m_child_received_nums` | 0x57CC | `u32[32]` | new | |
| `PacketHeader::m_block_id` | 0x0 | `u8` | new | |
| `PacketHeader::m_kind` | 0x1 | `EPacketKind` | new | 0 `DATA`, 1 `END_OF_PASS` (enum class : u8, named by this research) |
| `PacketHeader::m_chunk_index` | 0x2 | `u16` | new | |
| `PacketHeader::m_value` | 0x4 | `u32` | new | |

### Net::NetworkWbtMgr (size 0x58E0, template/Net/NetworkWbtMgr.hpp)

New in the templates (name from `dlp`). An `Object::Actor`; `NetworkWbtMgr::Buffer` (size 0x58AC) is
`NetworkDataManager<NetworkWbtMgr::Node>`, with a one-byte `Node` that is never filled.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_buffer` | 0x0008 | `Buffer` | new | |
| `m_saved_send_interval` | 0x58B4 | `u16` | new | |
| `m_packets_per_frame` | 0x58B8 | `s32` | new | 6 |
| `m_frame_counter` | 0x58BC | `s32` | new | |
| `m_finish_delegate` | 0x58C0 | `sead::Delegate<NetworkWbtMgr>` | new | calls `finishHandler` |
| `m_is_waiting` | 0x58D0 | `bool` | new | |
| `m_wait_start` | 0x58D8 | `sead::TickTime` | new | |
| `Buffer::m_protocol` | 0x0050 | `WbtProtocol` | new | |
| `Buffer::m_is_ready` | 0x589C | `bool` | new | |
| `Buffer::m_is_running` | 0x589D | `bool` | new | |
| `Buffer::m_is_parent` | 0x589E | `bool` | new | |
| `Buffer::m_is_finish_pending` | 0x589F | `bool` | new | |
| `Buffer::m_child_aid_bits` | 0x58A0 | `u8` | new | |
| `Buffer::m_player_num_at_ready` | 0x58A4 | `s32` | new | |
| `Buffer::m_finish_delegate` | 0x58A8 | `sead::IDelegate *` | new | points to the manager's `m_finish_delegate` |

### Sequence::MenuData (size 0x978, template/Sequence/MenuData.hpp)

Only the members this research uses.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_race_info` | 0x074 | `RaceSys::CRaceInfo` | existing | |
| `m_kart_info` | 0x394 | `CRaceInfo::CKartInfo` | existing | the local player's own choice, saved while it is a spectator |
| `m_selected_option` | 0x669 | `u8` | existing | comment added: the course setting, 0 choose, 1 random, 2 in order |
| `m_race_no` | 0x670 | `s32` | existing | -1 before the first race |
| `m_course_id` | 0x674 | `RaceSys::ECourseID[40]` | existing | by race number |
| `m_is_community_watch` | 0x714 | `bool` | new | |
| `m_course_votes` | 0x72C | `sead::PtrArray<CourseVote>` | existing | the votes shown on the vote page |
| `m_network_select_menu_process` | 0x7A0 | `Net::NetworkSelectMenuProcess *` | existing | |
| `m_watch_principal_id` | 0x7B8 | `u32` | new | |
| `m_mii_name` | 0x7BC | `sead::WSafeString` | existing | the friend's Mii name shown when joining from the friend list |
| `m_friend_approach` | 0x7E0 | `FriendApproach[8]` | existing | |
| `FriendApproach::m_register_state` | 0x0 | `s32` | new | was unknown; 1: register as a friend |
| `m_cpu_kart_infos` | 0x860 | `CRaceInfo::CKartInfo[6]` | existing | |
| `m_is_cpu_enabled` | 0x968 | `bool` | existing | |
| `m_num_free_player_slots` | 0x96C | `u32` | existing | comment added: number of CPU karts, negative until decided |


### Functions

Names marked `new` were given by this research; the others are ported from `dlp` (`mk7 port`).

| Name | Address (eur2) | Status | Note |
| --- | --- | --- | --- |
| `Mii::MiiEngine::getDefaultMiiStoreData` | 0x00286efc | existing |  |
| `Mii::MiiEngine::getMyMiiStoreDataBySaveData` | 0x00286f1c | existing |  |
| `Net::CommunityMgr::applyGameMode` | 0x00502598 | existing |  |
| `Net::CommunityMgr::applyRaceNum` | 0x0028bb18 | existing |  |
| `Net::IMatchingManager::send` | 0x0029a2c4 | existing |  |
| `Net::LocalMatchingManager::construct` | 0x002a3150 | existing |  |
| `Net::NetUtil::getRecvDataByPlayerId` | 0x002ade84 | existing |  |
| `Net::NetUtil::setDataToAllBuffer` | 0x002addcc | existing |  |
| `Net::NetworkBuffer::set` | 0x0028edb8 | existing |  |
| `Net::NetworkBufferController::NetworkBufferController` | 0x002a4df0 | existing |  |
| `Net::NetworkBufferController::allocBuffer` | 0x002a46f8 | existing |  |
| `Net::NetworkBufferController::checkAllReceive` | 0x002a49f0 | existing |  |
| `Net::NetworkBufferController::checkReceive` | 0x002a4944 | existing |  |
| `Net::NetworkBufferController::init` | 0x002a4cfc | existing |  |
| `Net::NetworkBufferController::onReceived` | 0x002a4550 | new | unnamed in `eur2` |
| `Net::NetworkBufferController::procSplitBuffer_` | 0x002a4ad4 | new | `dlp` name, not ported to `eur2`; race research |
| `Net::NetworkBufferController::regist` | 0x002a4dac | existing |  |
| `Net::NetworkBufferController::resetReceiveBmp` | 0x002a4a90 | existing |  |
| `Net::NetworkBufferController::swapReadBuffer` | 0x002a4958 | existing |  |
| `Net::NetworkDataManager<Net::MiiSendFormat>::updateCore` | 0x002addbc | existing |  |
| `Net::NetworkDataManager<Net::NetworkSelectMenuSendFormat>::init` | 0x005aa530 | existing |  |
| `Net::NetworkDataManager<Net::NetworkSelectMenuSendFormat>::onReceived` | 0x005aa3bc | existing |  |
| `Net::NetworkDataManager<Net::NetworkSelectMenuSendFormat>::updateCore` | 0x005aa410 | existing |  |
| `Net::NetworkDataManager<Net::NetworkSupplyInfoSendFormat>::updateCore` | 0x005aa668 | existing |  |
| `Net::NetworkEngine::acceptPlayers` | 0x0028f488 | existing |  |
| `Net::NetworkEngine::addFriend` | 0x00293754 | existing |  |
| `Net::NetworkEngine::calcAfterStructure` | 0x00290430 | existing |  |
| `Net::NetworkEngine::checkAllRaceSettingReceived` | 0x00292bbc | existing |  |
| `Net::NetworkEngine::checkAllSameSceneReceived` | 0x00292a50 | existing |  |
| `Net::NetworkEngine::checkStandAlone` | 0x0028f930 | existing |  |
| `Net::NetworkEngine::createBeforeStructure` | 0x00291974 | existing |  |
| `Net::NetworkEngine::dataReceiveCallback` | 0x00290eec | existing |  |
| `Net::NetworkEngine::decidePlayers` | 0x0028f49c | existing |  |
| `Net::NetworkEngine::getSequenceSyncReturnCode` | 0x00292b90 | existing |  |
| `Net::NetworkEngine::initNetworkInfo` | 0x0028fa7c | existing |  |
| `Net::NetworkEngine::isMatchInfoSynchronized` | 0x00292770 | existing |  |
| `Net::NetworkEngine::isOtherPhaseDataReceived` | 0x00292a24 | existing |  |
| `Net::NetworkEngine::keepAliveChecker_` | 0x0028fee0 | existing |  |
| `Net::NetworkEngine::kickStation` | 0x0028f2e0 | existing |  |
| `Net::NetworkEngine::request` | 0x00293470 | existing |  |
| `Net::NetworkEngine::sceneEnter` | 0x0028eff0 | existing |  |
| `Net::NetworkEngine::sendBuffers` | 0x0028f3e4 | existing |  |
| `Net::NetworkEngine::sendUnreliableCore` | 0x00290684 | existing |  |
| `Net::NetworkEngine::setSequenceSyncReturnCode` | 0x00292bb0 | existing |  |
| `Net::NetworkEngine::startKeepAliveCheck` | 0x00291118 | existing |  |
| `Net::NetworkEngine::stopKeepAliveCheck` | 0x0029089c | existing |  |
| `Net::NetworkEngine::syncPlayLogSendRequest` | 0x00292414 | existing |  |
| `Net::NetworkEngine::updateConnection_Connecting_` | 0x00292d10 | existing |  |
| `Net::NetworkEngine::updateConnection_StateChange_` | 0x00292f30 | existing |  |
| `Net::NetworkEngine::updateDlpInfo` | 0x0028f5e4 | existing |  |
| `Net::NetworkEngine::updateDlpInfoPart` | 0x002901a0 | existing |  |
| `Net::NetworkEngine::updateMasterOuter` | 0x002903e8 | existing |  |
| `Net::NetworkEngine::updatePlayerInfo` | 0x0028fc98 | existing |  |
| `Net::NetworkEngine::updatePlayerList` | 0x0028fd70 | existing |  |
| `Net::NetworkEngine::updateSendPlayLogRequest` | 0x00292a38 | existing |  |
| `Net::NetworkEngine::updateStationInfo_` | 0x00290c90 | existing |  |
| `Net::NetworkEngine::updateStationListType_` | 0x0029246c | existing |  |
| `Net::NetworkEngine::withDlp` | 0x005028c8 | existing |  |
| `Net::NetworkFriendsManager::NetworkFriendsManager` | 0x002a3ed4 | existing |  |
| `Net::NetworkFriendsManager::addFriend` | 0x002a3b54 | existing |  |
| `Net::NetworkFriendsManager::checkAllCorrectReceive` | 0x002a3704 | existing |  |
| `Net::NetworkFriendsManager::initializeApproach` | 0x002a35d4 | existing |  |
| `Net::NetworkFriendsManager::updateFriendApproachBuffer` | 0x002a3830 | existing |  |
| `Net::NetworkMiiManager::NetworkMiiManager` | 0x00299ac0 | existing |  |
| `Net::NetworkMiiManager::receiveAll` | 0x00299c70 | existing |  |
| `Net::NetworkMiiManager::setupMyMii` | 0x002999f4 | existing |  |
| `Net::NetworkMiiStorage::getSenderPacketSize` | 0x00130384 | existing |  |
| `Net::NetworkMiiStorage::receiveAll` | 0x00299c78 | existing |  |
| `Net::NetworkPlayerDataManager::NetworkPlayerDataManager` | 0x002a5d04 | existing |  |
| `Net::NetworkPlayerDataManager::createPlayerDataFromSystemData` | 0x002a5904 | existing |  |
| `Net::NetworkPlayerDataManager::fixDisconnect` | 0x002a5684 | existing |  |
| `Net::NetworkPlayerDataManager::forceReceiveAll` | 0x002a52bc | existing |  |
| `Net::NetworkPlayerDataManager::ready` | 0x002a5c34 | existing |  |
| `Net::NetworkPlayerDataManager::receiveAll` | 0x002a5240 | existing |  |
| `Net::NetworkPlayerDataManager::receiveCore_` | 0x002a52c4 | existing |  |
| `Net::NetworkSelectMenuDataManager::NetworkSelectMenuDataManager` | 0x002ad9ec | existing |  |
| `Net::NetworkSelectMenuDataManager::onReceivedCore` | 0x002ad990 | existing |  |
| `Net::NetworkSelectMenuProcess::NetworkSelectMenuProcess` | 0x002a7654 | existing |  |
| `Net::NetworkSelectMenuProcess::autoMatchNetwork` | 0x002a62a4 | existing |  |
| `Net::NetworkSelectMenuProcess::calcRaceSettingBit` | 0x002a649c | existing |  |
| `Net::NetworkSelectMenuProcess::checkAllReceive` | 0x002a49e8 | existing |  |
| `Net::NetworkSelectMenuProcess::checkReceive` | 0x002a493c | existing |  |
| `Net::NetworkSelectMenuProcess::disconnectNetwork` | 0x002a6364 | existing |  |
| `Net::NetworkSelectMenuProcess::extractRaceSettingOne` | 0x002a6d20 | existing |  |
| `Net::NetworkSelectMenuProcess::getPlayerStatus` | 0x002a61b0 | existing |  |
| `Net::NetworkSelectMenuProcess::init` | 0x002a7408 | existing |  |
| `Net::NetworkSelectMenuProcess::resetReceive` | 0x002a4a88 | existing |  |
| `Net::NetworkSelectMenuProcess::setSelectStateChange` | 0x002a6ca8 | existing |  |
| `Net::NetworkSelectMenuProcess::startSelect` | 0x002a5d68 | existing |  |
| `Net::NetworkSelectMenuProcess::stateSelectChange` | 0x002a6450 | existing | also stateSelectChange2 to stateSelectChange16, which follow it |
| `Net::NetworkSelectMenuProcess::stateSelectChange17` | 0x002a6bac | existing |  |
| `Net::NetworkSelectMenuProcess::stateSelectWait` | 0x002a62a0 | existing |  |
| `Net::NetworkSelectMenuProcess::syncPlayerConfig` | 0x002a62ec | existing |  |
| `Net::NetworkSelectMenuProcess::update` | 0x002a75b8 | existing |  |
| `Net::NetworkSelectMenuProcess::updateInnerSelectState` | 0x002a70d8 | existing |  |
| `Net::NetworkSelectMenuSendFormat::NetworkSelectMenuSendFormat` | 0x002ab974 | existing |  |
| `Net::NetworkSendBufferController::NetworkSendBufferController` | 0x002abb90 | existing |  |
| `Net::NetworkSendPolicy::send` | 0x0029a2cc | existing |  |
| `Net::NetworkSendPolicy::setSendInterval` | 0x0029a2bc | existing |  |
| `Net::NetworkSendPolicyBroadcast::sendCore_` | 0x002ac934 | existing |  |
| `Net::NetworkSendPolicyBroadcast::setSendInterval` | 0x002ab964 | existing |  |
| `Net::NetworkSendPolicyUnicast::sendCore_` | 0x002a7cd4 | existing |  |
| `Net::NetworkSendPolicyUnicast::setSendInterval` | 0x002a7cd0 | existing |  |
| `Net::NetworkStateCalc::checkAllStationInnerState_` | 0x002998e8 | existing |  |
| `Net::NetworkStateCalc::init` | 0x00299990 | existing |  |
| `Net::NetworkStateCalc::isStateChanging` | 0x00299710 | existing |  |
| `Net::NetworkStateCalc::isStateWaitForMe` | 0x002997a8 | existing |  |
| `Net::NetworkStateCalc::receiveState_` | 0x0029959c | new | unnamed in `eur2`; takes one peer's state and ready bit |
| `Net::NetworkStateCalc::updateDisconnect_` | 0x0029984c | existing |  |
| `Net::NetworkStateManager<Net::NetworkSelectMenuProcess>::executeState` | 0x005aa86c | existing |  |
| `Net::NetworkStateManager<Net::NetworkSelectMenuProcess>::initState` | 0x005aaa34 | existing |  |
| `Net::NetworkStationBufferManager::adjustForAI` | 0x002abda0 | existing |  |
| `Net::NetworkStationBufferManager::clearWriteBuffer` | 0x002ac188 | existing |  |
| `Net::NetworkStationBufferManager::constructSendBuffer_` | 0x002acf14 | existing |  |
| `Net::NetworkStationBufferManager::constructSendHeader_` | 0x002ad090 | existing |  |
| `Net::NetworkStationBufferManager::downStation2Reserver` | 0x002ad1b8 | existing |  |
| `Net::NetworkStationBufferManager::getNextSendAID` | 0x002abfac | existing |  |
| `Net::NetworkStationBufferManager::getPlayerId` | 0x002abe78 | existing |  |
| `Net::NetworkStationBufferManager::getReadBuffer` | 0x002abed8 | existing |  |
| `Net::NetworkStationBufferManager::isAudience` | 0x002abbec | existing |  |
| `Net::NetworkStationBufferManager::isCpu` | 0x002ad4b8 | existing |  |
| `Net::NetworkStationBufferManager::onReceived` | 0x002abc08 | existing |  |
| `Net::NetworkStationBufferManager::registBufferController` | 0x002ad2d4 | existing |  |
| `Net::NetworkStationBufferManager::registStationInfo` | 0x002ac520 | existing |  |
| `Net::NetworkStationBufferManager::sendUnreliableAll` | 0x002ac93c | existing |  |
| `Net::NetworkStationBufferManager::swapReadBuffer` | 0x002ac154 | existing |  |
| `Net::NetworkStationBufferManager::unregistStationInfo` | 0x002ac7c8 | existing |  |
| `Net::NetworkStationBufferManager::updateConvertTable` | 0x002ac954 | existing |  |
| `Net::NetworkStationBufferManager::updateStationToPlayer` | 0x002ac210 | existing |  |
| `Net::NetworkSupplyInfoManager::InnerPlayerInfo::InnerPlayerInfo` | 0x002a83a4 | existing |  |
| `Net::NetworkSupplyInfoManager::NetworkSupplyInfoManager` | 0x002a8d1c | existing |  |
| `Net::NetworkSupplyInfoManager::copySetting` | 0x002a7d14 | existing |  |
| `Net::NetworkSupplyInfoManager::copySettingEx` | 0x002a8028 | existing |  |
| `Net::NetworkSupplyInfoManager::extractRaceSettingToSelectMenu` | 0x002a8498 | existing |  |
| `Net::NetworkSupplyInfoManager::fixManage` | 0x002a8670 | existing |  |
| `Net::NetworkSupplyInfoManager::fixManageExtract_` | 0x002a87e4 | new | unnamed in `eur2`; the end of fixManage, one function in `dlp` |
| `Net::NetworkSupplyInfoManager::getExSetting` | 0x002a7fe4 | existing |  |
| `Net::NetworkSupplyInfoManager::getSelectMenuInfo` | 0x002a8454 | existing |  |
| `Net::NetworkSystemInfo::NetworkSystemInfo` | 0x0029a8b0 | existing |  |
| `Net::NetworkSystemInfo::onReceivedCore` | 0x0029a454 | existing |  |
| `Net::NetworkSystemInfo::updateCore` | 0x0029a3c0 | existing |  |
| `Net::NetworkSystemInfoManager::NetworkSystemInfoManager` | 0x002ab0e8 | existing |  |
| `Net::NetworkSystemInfoManager::calc` | 0x002aaaf0 | existing |  |
| `Net::NetworkSystemInfoManager::checkAllReceive` | 0x002a9374 | existing |  |
| `Net::NetworkSystemInfoManager::checkReceive` | 0x002a9060 | existing |  |
| `Net::NetworkSystemInfoManager::getMasterGameFrame` | 0x002a9634 | existing |  |
| `Net::NetworkSystemInfoManager::isCountConnectedPlayerInfoSync` | 0x002a9fe4 | existing |  |
| `Net::NetworkSystemInfoManager::isCountPlayerInfoSync` | 0x002a9d34 | existing |  |
| `Net::NetworkSystemInfoManager::isCountPlayerInfoSyncReceive` | 0x002a9e14 | existing |  |
| `Net::NetworkSystemInfoManager::resetReceive` | 0x002a90ac | existing |  |
| `Net::NetworkSystemInfoManager::sceneEnter` | 0x002a8ec0 | existing |  |
| `Net::NetworkSystemInfoManager::updateLatencyInfo_` | 0x002a9884 | existing |  |
| `Net::NetworkWbtMgr::Buffer::Buffer` | 0x0029506c | existing |  |
| `Net::NetworkWbtMgr::Buffer::calc` | 0x00294d3c | existing |  |
| `Net::NetworkWbtMgr::Buffer::onReceivedCore` | 0x00294c90 | existing |  |
| `Net::NetworkWbtMgr::Buffer::ready` | 0x00294ed8 | existing |  |
| `Net::NetworkWbtMgr::Buffer::registRecvData` | 0x00294cf4 | existing |  |
| `Net::NetworkWbtMgr::Buffer::registSendData` | 0x00294d18 | existing |  |
| `Net::NetworkWbtMgr::Buffer::updateCore` | 0x00294be0 | existing |  |
| `Net::NetworkWbtMgr::NetworkWbtMgr` | 0x0029517c | existing |  |
| `Net::NetworkWbtMgr::calc` | 0x00294794 | existing |  |
| `Net::NetworkWbtMgr::finishHandler` | 0x002946f4 | existing |  |
| `Net::NetworkWbtMgr::init` | 0x00294a8c | existing |  |
| `Net::NetworkWbtMgr::start` | 0x00294b04 | existing |  |
| `Net::PlayerInfo::PlayerInfo` | 0x00288d14 | existing |  |
| `Net::WbtProtocol::WbtProtocol` | 0x0028b018 | existing |  |
| `Net::WbtProtocol::finalize` | 0x0028a804 | existing |  |
| `Net::WbtProtocol::initAsChild` | 0x0028a5e4 | existing |  |
| `Net::WbtProtocol::initAsDummyChild` | 0x0028a728 | existing |  |
| `Net::WbtProtocol::initAsParent` | 0x0028a648 | existing |  |
| `Net::WbtProtocol::isFinished` | 0x0028a510 | existing |  |
| `Net::WbtProtocol::recvHook` | 0x0028a814 | existing |  |
| `Net::WbtProtocol::sendHook` | 0x0028acf0 | existing |  |
| `Net::WifiMatchingManager::construct` | 0x002a1af4 | existing |  |
| `RaceSys::CRaceInfo::CKartInfo::init` | 0x0046a11c | existing |  |
| `RaceSys::CourseArchiveManager::loadCore` | 0x004672a8 | existing |  |
| `RaceSys::CourseArchiveManager::withTrans` | 0x004673c8 | existing |  |
| `Sequence::BaseMenuPage::applySetting_Battle` | 0x00473310 | existing |  |
| `Sequence::BasePage::clearAllPlayer` | 0x004d337c | existing |  |
| `Sequence::BasePage::initRaceNo` | 0x004d2b28 | existing |  |
| `Sequence::BasePage::loadNextCourse` | 0x004d3450 | existing |  |
| `Sequence::BasePage::setCameraTargetPlayerID` | 0x004d4328 | existing |  |
| `Sequence::BasePage::setMasterPlayerID` | 0x004d4018 | existing |  |
| `Sequence::BasePage::setParts` | 0x004d4c40 | existing |  |
| `Sequence::BasePage::setRacePoint` | 0x004d3084 | existing |  |
| `Sequence::BasePage::setRaceRank` | 0x004d2d4c | existing |  |
| `Sequence::BasePage::setRawCourseID` | 0x004d3898 | existing |  |
| `Sequence::BasePage::setTotalRank` | 0x004d30d4 | existing |  |
| `Sequence::BasePage::setUniqTotalRank` | 0x004d3f7c | existing |  |
| `Sequence::BasePage::updateRaceInfo` | 0x004d38d4 | existing |  |
| `Sequence::BaseRacePage::calcSave` | 0x0047c600 | existing |  |
| `Sequence::BaseRacePage::complete` | 0x0047cec4 | existing |  |
| `Sequence::ClearRaceInfoTask::clearCommuInfo` | 0x004a0328 | existing |  |
| `Sequence::ClearRaceInfoTask::onTaskMain` | 0x004a0068 | existing |  |
| `Sequence::MenuChannel_SetupMii::onPagePreStep` | 0x004bb084 | existing |  |
| `Sequence::MenuCommunity_Lobby::MiiIconList::check` | 0x004b4f80 | existing |  |
| `Sequence::MenuCommunity_Lobby::TalkRecord::calcNewTalk` | 0x004b47e8 | existing |  |
| `Sequence::MenuCommunity_Lobby::onPagePreStep` | 0x004b5d80 | existing |  |
| `Sequence::MenuCommunity_Top::convertReturnCodeImpl` | 0x004a4000 | existing |  |
| `Sequence::MenuCommunity_Top::onPagePreStep` | 0x004a23ec | existing |  |
| `Sequence::MenuMulti_Class::buttonHandler_OK` | 0x0048dc10 | existing |  |
| `Sequence::MenuMulti_Class::isMirrorOpen` | 0x0048db00 | existing |  |
| `Sequence::MenuMulti_Class::onPageEnterCore` | 0x0048db80 | existing |  |
| `Sequence::MenuMulti_CourseVote::onPagePreStep` | 0x004bc724 | existing |  |
| `Sequence::MenuMulti_DlplaySequence::calcDistribute_` | 0x004ccb88 | existing |  |
| `Sequence::MenuMulti_DlplaySequence::calcShakeHands_` | 0x004ccd34 | existing |  |
| `Sequence::MenuMulti_DlplaySequence::calcUdsClient_` | 0x004cc88c | existing |  |
| `Sequence::MenuMulti_DlplaySequence::calcUdsServer_` | 0x004cca88 | existing |  |
| `Sequence::MenuMulti_DlplaySequence::calcWaitDistribute_` | 0x004cd4cc | existing |  |
| `Sequence::MenuMulti_DlplaySequence::onPageEnter` | 0x004cc688 | existing |  |
| `Sequence::MenuMulti_DlplaySequence::onPagePreStep` | 0x004cc7bc | existing |  |
| `Sequence::MenuMulti_Kart::procOpenMenu` | 0x004853ec | existing |  |
| `Sequence::MenuMulti_Mode::buttonHandler_OK` | 0x00486368 | existing |  |
| `Sequence::MenuMulti_Mode::onPagePreStepCore` | 0x004864b0 | existing |  |
| `Sequence::MenuMulti_VSSetting::buttonHandler_OK` | 0x004b7a10 | existing |  |
| `Sequence::MenuMulti_VSSetting::calcTeam_` | 0x004b8754 | existing |  |
| `Sequence::MenuMulti_VSSetting::onCompleteNetwork` | 0x004b7ca8 | existing |  |
| `Sequence::MenuMulti_VSSetting::onPageCompleteCore` | 0x004b86a4 | existing |  |
| `Sequence::MenuMulti_VSSetting::onPageEnterCore` | 0x004b773c | existing |  |
| `Sequence::MenuMulti_VSSetting::procOpenMenu` | 0x004b7414 | existing |  |
| `Sequence::MenuMulti_VSSetting::updateAppend` | 0x004b748c | existing |  |
| `Sequence::MenuMulti_Waiting::onPageEnter` | 0x004a574c | existing |  |
| `Sequence::MenuMulti_Waiting::onPagePreStep` | 0x004a5c7c | existing |  |
| `Sequence::MenuNetworkApplyTask::applyNetworkSetting_` | 0x004bdec0 | existing |  |
| `Sequence::MenuNetworkApplyTask::calcCameraTargetPlayerID_` | 0x004be890 | existing |  |
| `Sequence::MenuNetworkApplyTask::checkWatchCourse_` | 0x004bd64c | existing |  |
| `Sequence::MenuNetworkApplyTask::onTaskStart` | 0x004bd31c | existing |  |
| `Sequence::MenuNetworkApplyTask::onTaskStep` | 0x004bd23c | existing |  |
| `Sequence::MenuNetworkApplyTask::ranksort2_` | 0x004bd300 | existing |  |
| `Sequence::MenuNetworkApplyTask::ranksort_` | 0x004beb0c | existing |  |
| `Sequence::MenuNetworkApplyTask::updateBattleMode_` | 0x004bd75c | existing |  |
| `Sequence::MenuNetworkApplyTask::updateOneDriver_` | 0x004bd410 | existing |  |
| `Sequence::MenuNetworkApplyTask::updatePlayerStatus_` | 0x004bd9a4 | existing |  |
| `Sequence::MenuNetworkCourseDecideTask::convertEnterCodeImpl` | 0x004cf6fc | existing |  |
| `Sequence::MenuNetworkCourseDecideTask::convertReturnCodeImpl` | 0x004cf804 | existing |  |
| `Sequence::MenuNetworkCourseDecideTask::onTaskStart` | 0x004cf5e4 | existing |  |
| `Sequence::MenuNetworkCourseDecideTask::onTaskStep` | 0x004cf038 | existing |  |
| `Sequence::MenuNetworkSelectFromWatchTask::convertReturnCodeImpl` | 0x004cf95c | existing |  |
| `Sequence::MenuNetworkSelectFromWatchTask::onTaskMain` | 0x004cf888 | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::convertEnterCodeImpl` | 0x004cde40 | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::convertModeImpl` | 0x004cda2c | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::onCreate` | 0x004cdfd4 | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::onTaskStart` | 0x004cd638 | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::onTaskStep` | 0x004cd628 | existing |  |
| `Sequence::MenuNetworkSelectMenuTask::syncPlayerConfig_` | 0x004cda9c | existing |  |
| `Sequence::MenuSingle_Setting::buttonHandler_OK` | 0x004aca94 | existing |  |
| `Sequence::MenuSingle_Setting::initControl` | 0x004ab61c | existing |  |
| `Sequence::MenuSingle_Setting::isCOM` | 0x004acc68 | existing |  |
| `Sequence::MenuSingle_Setting::moveBlueOuter` | 0x004ac7e4 | existing |  |
| `Sequence::MenuSingle_Setting::moveRedOuter` | 0x004ac7b0 | existing |  |
| `Sequence::MenuWiFi_Confirm::convertReturnCodeImpl` | 0x0049bfd0 | existing |  |
| `Sequence::MenuWiFi_Confirm::onPageEnter` | 0x0049b9c4 | existing |  |
| `Sequence::MenuWiFi_Confirm::onTimeUpComplete` | 0x0049bfa0 | existing |  |
| `Sequence::MenuWiFi_Connect::onPagePreStep` | 0x0049c394 | existing |  |
| `Sequence::MenuWiFi_Mode::buttonHandler_OK` | 0x004842f8 | existing |  |
| `Sequence::MenuWiFi_Waiting::calcMatchingError_` | 0x0049ee44 | existing |  |
| `Sequence::MenuWiFi_Waiting::convertEnterCodeImpl` | 0x0049f0bc | existing |  |
| `Sequence::MenuWiFi_Waiting::convertReturnCodeImpl` | 0x0049f168 | existing |  |
| `Sequence::MenuWiFi_Waiting::onPageEnter` | 0x0049dca0 | existing |  |
| `Sequence::MenuWiFi_Waiting::onPagePreStep` | 0x0049e2c0 | existing |  |
| `Sequence::MenuWiFi_WaitingDecide::convertEnterCodeImpl` | 0x004c4994 | existing |  |
| `Sequence::MenuWiFi_WaitingDecide::convertReturnCodeImpl` | 0x004c4a14 | existing |  |
| `Sequence::MenuWiFi_WaitingDecide::onPageComplete` | 0x004c4778 | existing |  |
| `Sequence::MenuWiFi_WaitingDecide::onPageEnter` | 0x004c39bc | existing |  |
| `Sequence::MenuWiFi_WaitingDecide::onPagePreStep` | 0x004c3c1c | existing |  |
| `Sequence::TrophyPage::enter` | 0x004714d0 | existing |  |
| `Sequence::checkTeam2_` | 0x00472368 | existing |  |
| `Sequence::checkTeam_` | 0x00471a44 | existing |  |
| `Sequence::copyMasterMode_` | 0x004851a8 | new | unnamed in `eur2`; clients copy the master's `m_mode` |
| `Sequence::correctAIInfo_` | 0x004883f4 | existing |  |
| `Sequence::getRandomCourse_` | 0x0049ff7c | existing |  |
| `Sequence::isAnyReturnFromGame_` | 0x004c157c | existing |  |
| `Sequence::receiveCourseVoteList_` | 0x004c4b2c | existing |  |
| `Sequence::registVote_` | 0x004724c8 | existing |  |
| `Sequence::updateClientRandom_` | 0x004ba81c | existing |  |
| `Sequence::updateCourseVoteList_` | 0x004c309c | existing |  |
| `Sequence::updateMasterRandom_` | 0x004baa5c | existing |  |
| `Sequence::updateRaceMode_` | 0x00496b7c | existing |  |
| `Sequence::updateSendReturnCode_` | 0x004c3308 | existing |  |
| `Sound::SndLoader::getCourseDataPath` | 0x003da0d8 | existing |  |
| `System::BackgroundLoadThread::toStartCourse` | 0x0045058c | existing |  |
| `System::CacheDataCommon::load` | 0x0044b734 | existing |  |
| `System::SystemEngine::getMyPlayerData` | 0x00442500 | existing |  |
| `System::ThreadManager::sleepCurrentThread` | 0x004457a4 | existing |  |
| `UI::BaseMenuButtonControl::completeNext` | 0x00170db0 | existing |  |
| `UI::LRSelect::apply` | 0x0017b5d0 | existing |  |

### Data

| Name | Address (eur2) | Note |
| --- | --- | --- |
| `Net::sNetworkBufferSizes` | 0x005f3658 | new name; `u32[12]`, the size of each buffer type, read by `NetworkBufferController::allocBuffer` |

## Findings

### Sources and method

- Decompilation (`mk7 decomp`) and disassembly (`mk7 dis`) of `eur2`, with names ported from `dlp` by `mk7 port`.
  Names without counterpart in `eur2` were given by this research and are marked `new` in the
  [functions table](#functions).
- To find every writer of a member, the whole `eur2` code was disassembled once and searched for stores to its offset
  through the pointers that lead to it; every hit was then read with `mk7 dis`. Such a search can miss a store made
  through a pointer held elsewhere: "no writer found" below means none was found this way.
- The page flow comes from `mk7 bseq dump MenuScene-Default` (sections `MenuScene`, `Seq_Title`, `Seq_Multi`,
  `Seq_WiFi`, `Seq_Community`, `TaskMenu_CourseDecide`, `MenuNetworkSelectMenuTask`, `isFromWatch`). The kinds of tasks
  (instant and lasting) are those of the research on scene sequencing.
- Out of scope, and only named where the menus call it: the transport (NEX, UDS, `DirectTransport`), matchmaking,
  the connection pages of the lobby, and the race-only uses of the buffers.

### 1. Creating the buffers

- `NetworkEngine::createBeforeStructure` creates the `NetworkStationBufferManager` (size 0xE0, stored in
  `NetworkEngine::m_network_station_buffer_manager`), then for each type 0 to 10 a `NetworkBufferController(type)`
  (size 0x50), calls its first virtual function, `allocBuffer`, and registers it (`regist` ->
  `NetworkStationBufferManager::registBufferController(type, controller)`).
- `NetworkSendBufferController`'s constructor calls the base constructor with type 11 (`Container`); this controller is
  `NetworkStationBufferManager::m_container_controller`.
- `NetworkBufferController::allocBuffer`: `m_total_recv_buffer = 8`; one `Buffer` in `m_write_buffers`, eight in
  `m_read_buffers`; each `Buffer` holds two `NetworkBuffer`s whose size comes from `Net::sNetworkBufferSizes[type]`:
  `a0 a0 30 230 24 200 384 264 40 c0 64 d2c`. Types 0 to 10 add up to 0xD10; the container's 0xD2C is that plus the
  0x1C-byte header ([Finding 2](#2-sending)).
- The constructor sets `m_has_recv_bitfield = 0` and `m_empty_recv_bitfield = 0xFF`; `NetworkBufferController::init`
  clears every buffer and sets `m_empty_recv_bitfield = 0xFF` again.

### 2. Sending

#### Writing

- Each per-type manager derives from `NetworkDataManager<T>`. Its `updateCore` (for example
  `NetworkDataManager<NetworkSelectMenuSendFormat>::updateCore`) is
  `NetUtil::setDataToAllBuffer(&m_node_data, sizeof(T), m_network_buffer_type)`, which gets the controller's write
  buffer and calls `NetworkBuffer::set`: the data replaces what the buffer held.
- The owners call it as `preUpdate()`, then, if it returned true, `updateCore()` and `postUpdate()`. For SelectMenu
  (`NetworkSelectMenuProcess::update`) and SystemInfo (`NetworkSystemInfoManager::calc`) this only happens while the
  session is active and `NetworkEngine::m_is_not_racer` is clear.

#### The packet

`NetworkEngine::calcAfterStructure`, once per frame, when the session is up:

1. Mii and SupplyInfo `send` (preUpdate / updateCore / postUpdate), unless `m_is_wbt_running`. Unlike SelectMenu and
   SystemInfo, this does not test `m_is_not_racer`.
2. If a further guard byte of the engine is clear (unnamed; see [Open questions](#open-questions)) and `m_is_not_racer`
   is clear: `IMatchingManager::send(current matching
   manager, station manager)`. The current matching manager is chosen by `m_network_mode`: `LOCAL` the
   `LocalMatchingManager`, `WIFI` the `WifiMatchingManager`, 2 none.
3. `checkStandAlone`, `NetworkStationBufferManager::swapReadBuffer` and `NetworkStationBufferManager::clearWriteBuffer`
   (which only resets the write position, `m_current = 0`).

`IMatchingManager::send` loads the manager's send policy and falls through into `NetworkSendPolicy::send`: it does
nothing while fewer milliseconds than the policy's interval (`u16` at policy + 4), plus 50 when
`NetworkEngine::m_no_send_delay` is 0, have passed since the last send:

```
if (*(int *)(uVar2 + 0x534) == 0) { iVar4 = 0x32; } else { iVar4 = 0; }
... if (elapsed_ms < *(ushort *)(__fd + 4) + iVar4) -> return
```

otherwise it calls the policy's second virtual function, `sendCore_`, hands an error to `NetworkErrorHandler`, and
restarts the timer. `NetworkEngine::sceneEnter` sets `m_no_send_delay` to 0 on every scene in `WIFI` mode, and to 1 for
the race scene (`SceneID` 3):

```
0028f00c  cmp r0, #1            ; m_network_mode == WIFI
0028f014  mov r0, #0
0028f018  str r0, [r4, #0x534]
```

- Online (`WifiMatchingManager::construct`): `NetworkSendPolicyUnicast`, interval 16 ms; its `setSendInterval` does
  nothing. `NetworkSendPolicyUnicast::sendCore_` takes the next aid in turn
  (`NetworkStationBufferManager::getNextSendAID(last, false)`, which skips the local aid, disconnected stations and
  station id 0) and sends to that one console only.
- Local (`LocalMatchingManager::construct`): `NetworkSendPolicyBroadcast`, interval 0x70 = 112 ms at first;
  `NetworkSendPolicyBroadcast::setSendInterval(n)` stores n × 16. `NetworkSendPolicyBroadcast::sendCore_` calls
  `constructSendBuffer_` and `NetworkStationBufferManager::sendUnreliableAll`, which sends to aid -1, all consoles.

#### Building the packet

- `NetworkStationBufferManager::constructSendBuffer_`: for each type whose active write half holds data, flip the
  write half, so that the game writes the other half from the next frame on. Then `constructSendHeader_`, and for each
  type, append the half just flipped away to the container's write buffer and clear it. Type 3 (`KartData`) is skipped
  while `m_wbt_started` is set.
- `constructSendHeader_` writes 0x1C bytes: a `u32` 0 at 0x00, the size of each of the eleven types as `u16` from 0x04
  (type 3 as 0 while `m_wbt_started`), and a 0 byte at 0x1A, then `NetworkBuffer::set(container, header, 0x1C)`.
- `NetworkEngine::sendUnreliableCore` hands the container to the transport: aid -1 to `SendUnreliableAll`, otherwise
  to the station of that aid, refusing a station the transport marks as faulty. A second mode, enabled by an engine
  flag that was not followed, only sends on every 11th call on the master and every 6th on the others.

### 3. Receiving

- `NetworkEngine::dataReceiveCallback` (called by the transport) passes the packet to
  `NetworkStationBufferManager::onReceived(handle, data, size)`. It finds the aid whose station has that handle in
  `m_connector_info_humans`; drops the packet if that station's status is 2 (`Unregistered`) or its `m_buffer_id` is -1
  (a spectator). Otherwise, for each type 0 to 10, the slice starts at `data + 0x1C` plus the sizes of the types before
  it, with the size read from the header at `data + 4 + 2 × type`, and goes to that type's
  `NetworkBufferController::onReceived(aid, buffer id, slice, size)`; a false result stops the loop.
- `NetworkBufferController::onReceived` (unnamed in `eur2`), under the controller's lock:
  - size 0: set the aid's bit in `m_empty_recv_bitfield`, return true, store nothing; otherwise clear that bit;
  - type 3: hand the slice to `procSplitBuffer_` (race research);
  - a slice larger than the free half of the read buffer of that buffer id: return false;
  - call the receive delegate (`on_received_delegate1R`) with a `NetworkReceivedInfo{data, size, buffer id}`; if it
    returns false, the slice is not stored;
  - otherwise set the aid's bit in `m_has_recv_bitfield`, copy the slice into the back half of the read buffer and set
    `Buffer::m_should_swap`.
- `NetworkBufferController::swapReadBuffer`, called each frame through `NetworkStationBufferManager::swapReadBuffer`
  from `calcAfterStructure`, flips every read buffer whose `m_should_swap` is set and clears the flag, under the lock.
  So data that arrived during a frame becomes readable at the next one.
- Reading: `NetworkStationBufferManager::getReadBuffer(type, aid)` takes the buffer id of the aid's station
  (`m_connector_info_humans` for a human aid, `m_connector_info_cpus` otherwise) and returns the front half of that
  read buffer. `NetUtil::getRecvDataByPlayerId(player id, type, engine)` turns the player id into an aid with
  `m_player_id_to_aid` first.
- `NetworkDataManager<T>::onReceived` (for example
  `NetworkDataManager<NetworkSelectMenuSendFormat>::onReceived`) returns true without further work when the manager's
  `unk` byte is set; otherwise it calls `onReceivedCore` under the manager's lock. The delegate is stored in the
  controller by `NetworkDataManager<T>::init`. `NetworkSelectMenuDataManager::onReceivedCore` also copies 0x9A bytes
  into `m_received[aid]`.
- `NetworkBufferController::checkReceive(aid)` tests `m_has_recv_bitfield`; `resetReceiveBmp` clears it;
  `checkAllReceive` is true when `m_has_recv_bitfield`, plus the local aid while `m_is_not_racer` is clear, covers
  `NetworkStationBufferManager::m_registered_aid_bits`.

### 4. Stations, aids and player ids

- `NetworkStationBufferManager::registStationInfo(station id, handle, list type)` adds a `StationInfo` with status
  `Registered` to `m_station_access_info_racers` (list type 0), with a free buffer id, or to
  `m_station_access_info_audience` (list type 1) with buffer id -1, and sorts the list by station id.
- `adjustForAI` fills the free racer entries with `StationInfo{m_is_ai = 1, station id 0, handle 0, a new buffer id}`.
- `updateConvertTable` (decompiled):
  1. it clears both connector tables, the four lists and the three bitmaps;
  2. for the racer list, then the spectator list, each human station (`m_is_ai` clear, station id not 0) takes the next
     aid: it is stored in `m_connector_info_humans[aid]` and appended to `m_human_connectors`. For the racer list only,
     the aid's bit is set in `m_racer_aid_bits` (and in `m_unregistered_aid_bits` if the status is 2), the entry goes to
     `m_racer_connectors`, and, when the station is not the local one, to `m_other_racer_connectors`, and then, when its
     status is not 2, to `m_without_unregistered`:

     ```
     if (uVar9 == 0) {                                  // racer list
       *(byte *)(param_1 + 0xcc) |= bVar1;              // m_racer_aid_bits
       if (*piVar10 == 2) *(byte *)(param_1 + 0xcd) |= bVar1;
       ... append to +0x98
       if (*(int *)(uVar11 + 0x264) != *(int *)(iVar6 + 8)) {   // not the local station
         ... append to +0xa4
         if (*piVar10 != 2) ... append to +0xb0
     ```
  3. every `m_connector_info_humans` entry gets `m_player_id = m_aid = index`, `m_player_id_to_aid[i] = i`,
     `m_buffer_id_to_aid[buffer id] = i`;
  4. the CPU stations of the racer list go to `m_connector_info_cpus` at the aids after the last human, with the same
     player id and aid;
  5. `m_player_num` = entries of `m_racer_connectors`, `m_human_num` = human aids, `m_connected_human_num` = those whose
     status is not 2, `m_registered_aid_bits = m_racer_aid_bits & ~m_unregistered_aid_bits`.
- So a player id is the aid everywhere in these tables. `NetworkStationBufferManager::getPlayerId(aid)` reads
  `m_connector_info_humans[aid].m_player_id`, else `m_connector_info_cpus[aid]`; `isCpu(player id)` reads `m_is_ai`
  of the station in `m_connector_info_cpus`; `isAudience(station)` looks for it in the spectator list.
- `NetworkEngine::m_is_not_racer`: set by `initNetworkInfo`. `NetworkEngine::updateStationListType_` (on a console that
  is not the master) reads the master's SystemInfo: its `m_racer_station_ids`, `m_connected_racer_aid_bits` and
  `m_match_flags`, whose bits it copies into `m_is_accepting_players` and `m_is_players_decided`. When the local
  station is in the master's list, `updateStationToPlayer` makes it a racer and `m_is_not_racer` is cleared. Stations
  not in the list are removed when their status is 2 (`unregistStationInfo`) or moved from the racers to the
  spectators (`downStation2Reserver`; not in local play).

### 5. SystemInfo packets

#### The objects

- `NetworkSystemInfoManager` (an `Object::Actor`, size 0x2F0, `NetworkEngine::m_network_system_info_manager`) holds
  `NetworkSystemInfo` at 0x40, whose `m_node_data` (the `NetworkSystemSendFormat`) is at manager + 0x50.
- `NetworkSystemInfo` is 0x208 bytes, not 0x1F0: `onReceivedCore` writes `m_game_frames_at_receive[aid]` (0x1E8 + 4 ×
  aid, up to 0x208), and `NetworkSystemInfoManager`'s constructor stores its race synchronisation object at
  `NetworkSystemInfo` + 0x208 (manager + 0x248). The objects from manager + 0x248 on (`Sync`, `FrameSync`, two
  `NetworkStateManager<NetworkSystemInfoManager>` for the finish synchronisation of races) are left to the race
  research.

#### Sending

- `NetworkSystemInfoManager::calc`, while the session is active and the local console is a racer: the race
  synchronisation, then `m_sequence += 1`, `updateLatencyInfo_`, and the preUpdate / updateCore / postUpdate of
  `NetworkSystemInfo`. When `m_is_not_racer` is set, only the frame synchronisation runs and nothing is sent.
- `NetworkSystemInfo::updateCore`: `m_spare_u16` and `m_spare_u32` are copied into the format; unless
  `m_skip_game_frame` is set and when a race director exists, `m_game_frame` = its frame counter; then
  `setDataToAllBuffer(format, 0xA0, SystemInfo)`.

#### Receiving

`NetworkSystemInfo::onReceivedCore`:

1. aid = `m_buffer_id_to_aid[buffer id]`; `NetworkEngine::m_heard_aid_bits |= 1 << aid`; `m_ticks[aid]` = now; toggle
   `m_other_phase_received_index` and clear the new half of `m_other_phase_received`.
2. Return false (drop) when the received `m_sequence` is not greater than `m_last_sequences[aid]`.
3. When the received `m_phase` differs from the own one: set `m_other_phase_received[index]`, and drop unless
   `m_accept_other_phase` is set.
4. Round trip: (now in ms & 0xFFFF) minus the received `m_latency_timestamps[local aid]`, wrapped at 0xFFFF;
   `m_latencies[aid]` = half of it. The value is also added to a sum and a count per aid in the engine.
5. `m_game_frames_at_receive[aid]` = own `m_game_frame`; copy 0x9C bytes into `m_last_received[aid]`;
   `m_last_sequences[aid]` = the sequence; `m_accepted_intervals[aid]` and `m_last_accepted_ticks[aid]`; return true
   (the packet is stored in the read buffer as well).

`NetworkSystemInfoManager::updateLatencyInfo_`, before each send: `m_latency_timestamps[local aid]` = now in ms (16
bits); for each other aid, the timestamp that console sent for itself plus the milliseconds since its packet arrived.
Each console thus echoes the others' clocks, corrected for how long it held them, and the receiver gets the round trip.

#### The fields

| Field | Written by | Read by |
| --- | --- | --- |
| `m_sequence` | `NetworkSystemInfoManager::calc`, +1 per send | `onReceivedCore` drops older ones |
| `m_sequence_sync_return_code` | 0xFF at start, 0 at the race's `sceneEnter`; the master in `BaseRacePage::complete` (`setSequenceSyncReturnCode`) | clients, `getSequenceSyncReturnCode` (race) |
| `m_phase` | `MenuNetworkSelectMenuTask::onTaskStart` 0x32; `MenuNetworkApplyTask::onTaskStart` 0x34 (and the select menu task's unused `Once` mode); `TrophyPage::enter` 0x33 when another race follows; `NetworkSystemInfoManager::sceneEnter` of a race: 0x31 online, else the race number (`MenuData::m_race_no`) | `onReceivedCore`; `checkAllSameSceneReceived` (every peer at the own phase); `checkAllRaceSettingReceived` (no peer still at the own value, and SupplyInfo `fixManage`); `isMatchInfoSynchronized` and `keepAliveChecker_` (same phase) |
| `m_game_frame` | `updateCore` during a race; in the community lobby, `MenuCommunity_Lobby::onPagePreStep` copies the master's while it is above 0, counts it down to 1, and `onPageExit` sets 1 | `NetworkSystemInfoManager::getMasterGameFrame` = the master's value plus the own frames since it arrived (`m_game_frames_at_receive`) |
| `m_community_race_point` | `BaseRacePage::calcSave` in community matches; 0 in `CommunityMgr::applyRaceNum` | `MenuNetworkApplyTask::updatePlayerStatus_` -> `BasePage::setRacePoint` |
| `m_race_num` | race `sceneEnter` = `MenuData::m_race_no`; 0xFF in `applyRaceNum`; clients copy the master's in `MenuWiFi_WaitingDecide::onPagePreStep` | the same page |
| `m_lobby_talk_id` | `MenuCommunity_Lobby` (`onPageEnter`, `buttonHandler_OK`, cleared after 600 frames) | `MenuCommunity_Lobby::TalkRecord::calcNewTalk` |
| `m_decided_course_id` | [Finding 12](#12-the-course-chosen-by-the-master); 0x29 at start and at `sceneEnter` | the same |
| `m_master_random` | `Sequence::updateMasterRandom_` makes a seed if it is 0 and seeds `BasePage`'s fixed seed and the global random generator | `Sequence::updateClientRandom_`, `MenuTitle`, `MenuMulti_Waiting`, `MenuNetworkApplyTask::applyNetworkSetting_` |
| `m_flags` | bit 0: online master from a bit (0x20) of a server setting in `calcAfterStructure`, clients copy the master's (`syncPlayLogSendRequest`), `updateSendPlayLogRequest` stores it in the engine; bit 1 cleared at `sceneEnter`; bit 2 cleared by `MenuMulti_DlplaySequence::calcShakeHands_` | |
| `m_player_data` | `NetworkEngine::updatePlayerInfo`: `System::SystemEngine::getMyPlayerData`, with `myPrincipalId` replaced by `NetworkFriendsManager::m_my_principal_id`; also sets `NetworkPlayerDataManager::m_is_player_info_updated`. Callers: `updateConnection_Connecting_`, `MenuWiFi_Connect::onPagePreStep`. Its `rate` (the VR) starts at 1000; `BaseRacePage::calcSave` writes the new rating, clamped to 1 to 99999 | `NetworkPlayerDataManager` ([Finding 14](#14-player-profiles)) |
| `m_connected_racer_aid_bits` | `NetworkEngine::updateStationInfo_` = `m_registered_aid_bits` | `isCountPlayerInfoSync`, `isCountConnectedPlayerInfoSync`, `NetworkStateCalc::receiveState_` |
| `m_heard_aid_bits` | `keepAliveChecker_` = `NetworkEngine::m_heard_aid_bits` | [Finding 7](#7-keep-alive) |
| `m_match_flags` | the master: from `acceptPlayers` (lobby, select menu task) and `decidePlayers` (apply task, online waiting pages, course download) | clients, `updateStationListType_` |
| `m_racer_station_ids` | `updateStationInfo_`: the station ids of `m_racer_connectors`; the count in `NetworkSystemInfo::m_racer_station_id_num` | `isMatchInfoSynchronized`, `updateStationListType_` |
| `m_latency_timestamps` | `updateLatencyInfo_` | `onReceivedCore` |

### 6. SystemInfo checks used by the menus

| Function | True when | Called by |
| --- | --- | --- |
| `NetworkSystemInfoManager::isCountPlayerInfoSync` | every connected peer's `m_connected_racer_aid_bits` equals the own, and their number is the number of bits | `MenuWiFi_Waiting`, `MenuCommunity_Top`, `MenuCommunity_Lobby::MiiIconList::check`, `MenuWiFi_WaitingDecide`, `MenuMulti_DlplaySequence::calcShakeHands_`, `updateStationListType_`, `isMatchInfoSynchronized` |
| `NetworkSystemInfoManager::isCountConnectedPlayerInfoSync` | for every connected peer, the same bitmap and the same number of station ids | `MenuNetworkApplyTask::onTaskStep`, `MenuNetworkCourseDecideTask::onTaskStep` |
| `NetworkSystemInfoManager::isCountPlayerInfoSyncReceive` | the count check, only over the aids heard from in the last 4 seconds (`m_ticks`) | `keepAliveChecker_` |
| `NetworkEngine::isMatchInfoSynchronized` | every peer sends the same racer list as the own, at the same phase, and the master no longer accepts players | `MenuWiFi_WaitingDecide` |
| `NetworkEngine::checkAllSameSceneReceived` | every peer's phase equals the own | `MenuWiFi_WaitingDecide` |
| `NetworkEngine::checkAllRaceSettingReceived` | no peer is still at the own phase, and SupplyInfo `fixManage` succeeded | `MenuWiFi_Waiting`, `MenuWiFi_WaitingDecide`, `MenuCommunity_Top` (spectators) |
| `NetworkEngine::isOtherPhaseDataReceived` | `m_other_phase_received` is set: some console is in another phase | the same pages, to find a running race |

### 7. Keep-alive

`NetworkEngine::keepAliveChecker_`, while enabled (`startKeepAliveCheck` / `stopKeepAliveCheck`): the window lasts a
number of seconds kept by the engine, times 60 frames. At its end, a racer console calls `kickStation` for the aids it
sent to but did not hear from, and publishes `m_heard_aid_bits` in its `NetworkSystemSendFormat::m_heard_aid_bits`.
Then, once `isCountPlayerInfoSyncReceive` holds, it kicks every connected aid that no console of the same phase heard
from (the union of the peers' `m_heard_aid_bits`). Probable: the arguments of `kickStation` were not checked in the
decompilation.

### 8. The shared state number

`NetworkStateCalc` (and `NetworkStateManager<T>`, which adds a `Util::TStateObserver<T>`) is used by
`NetworkSelectMenuProcess` and twice by `NetworkSystemInfoManager` (race). Offsets from the `NetworkStateCalc` base
are in the glossary.

- Each console sends its state and its ready bit: SelectMenu `m_select_state` / `m_select_ready` (SystemInfo bytes
  0x62 to 0x65 for the two race instances). `NetworkStateCalc::receiveState_` (unnamed in `eur2`), for each peer and
  each frame, from the latest read buffer: the peer's state is taken only when the peer's
  `NetworkSystemSendFormat::m_connected_racer_aid_bits` equals `m_connected_racer_aid_bits`, and the peer's state is
  the own state or the requested one; then `m_states[aid]` = it, and its ready bit is set or cleared.
- `NetworkStateManager<NetworkSelectMenuProcess>::executeState`: clear `m_state_changed`; `updateDisconnect_` (when
  the connected racers changed: `NetworkEngine::updateStationListType_`, clear every state and ready bit, call
  `onDisconnect`). If active and a state is requested, switch when every connected peer is ready at the same state
  (`checkAllStationInnerState_`), or as soon as a peer's state is greater than the own (a console that missed the step
  catches up). Switching: previous = current, current = requested, own state = it, request = -1, ready bits cleared,
  `m_state_changed = 1`, `onChangeState`. Then the current state's function runs unless the local console is marked
  ready.
- `isStateChanging`: some connected peer is at another state. `isStateWaitForMe`: every other peer is ready at the own
  state. `initState(s)` forces state s locally, without agreement, and clears the states and ready bits.
- `NetworkSelectMenuProcess`'s state functions (its virtual functions `stateSelectWait`, `stateSelectChange` to
  `stateSelectChange17`) are all a single `bx lr`, so the state number itself is what the pages watch.
- `NetworkSelectMenuProcess::setSelectStateChange`: request (current + 1) % 17 and mark self ready.
  `startSelect(n)`: initialise, then n = 0: request state 1 and mark ready; n = 1: `initState(0)`; n = 2:
  `initState(4)`. Callers: `MenuMulti_Class::onPageEnterCore`, `MenuWiFi_WaitingDecide`,
  `MenuMulti_DlplaySequence::calcShakeHands_`, `MenuNetworkSelectMenuTask::onTaskStart`.
- `NetworkSelectMenuProcess::update` (session active, local console a racer): the data manager's preUpdate /
  updateCore / postUpdate (the send), then `updateInnerSelectState`: `m_select_state` = current state, `m_select_ready`
  = own ready bit, `receiveState_` for each peer, `executeState`.

### 9. SelectMenu packets

- `NetworkSelectMenuProcess` (size 0x634, `MenuData::m_network_select_menu_process`): `m_select_state` at 0x04,
  `m_data_manager` (`NetworkSelectMenuDataManager`, size 0x5CC) at 0x58, so the own format is at 0x68 and the controller
  pointer at 0x108, where the template had three loose members. `NetworkSelectMenuProcess::init` registers a delegate
  (at 0x624) in a list the engine calls at the end of `calcAfterStructure`; the constructor also clears the engine's
  latency sums.
- `getPlayerStatus(aid)` returns the own format for the local aid, else the front read buffer of that aid.
- `syncPlayerConfig(true)` copies from kart 0 of `MenuData::m_race_info`: driver, body, wing and tire to 0x04 to 0x07,
  team red to `m_flags` bit 2, race point to `m_race_point`, race rank to `m_race_rank`.
- The fields (constructor `NetworkSelectMenuSendFormat::NetworkSelectMenuSendFormat` for the start values):

| Field | Meaning and evidence |
| --- | --- |
| `m_mode` | Local play: the button of `MenuMulti_Mode` (`buttonHandler_OK`): 0 Grand Prix, 1 VS, 2 balloon battle, 3 coin battle; a client writes 4 in `MenuMulti_Mode::onPagePreStepCore` when the master's value is 4 (then a dialog; not followed). Online: `MenuWiFi_Mode::buttonHandler_OK` writes 0 (VS) or 2 (balloon); `MenuNetworkSelectMenuTask::onTaskStart` (entry `WFC_MemberCheck`) writes 0 for VS, 2 for balloon, 1 otherwise (coin); clients copy the master's in `MenuWiFi_WaitingDecide` (`Sequence::copyMasterMode_`) |
| `m_engine_class` | `MenuMulti_Class::buttonHandler_OK` |
| `m_course_vote` | [Finding 11](#11-the-course-vote) |
| `m_selected_course_vote_index` | [Finding 11](#11-the-course-vote); start value 0x27 |
| `m_driver_id` to `m_tire_id` | `syncPlayerConfig`; start values 0x12, 0x11, 7, 10 (the maximum of each id enum); the order body, wing, tire is that of the `CKartInfo` copy and of `BasePage::setParts`. Driver 0x13 means "no data" for `MenuNetworkApplyTask::updateOneDriver_` |
| `m_selected_random_course_id` | [Finding 11](#11-the-course-vote) |
| `m_page_return_code` | `Sequence::updateSendReturnCode_(button)` ([Finding 10](#10-pages-that-move-together-vs-settings-and-teams)) |
| `m_vs_settings` | [Finding 10](#10-pages-that-move-together-vs-settings-and-teams); the constructor fills the five bytes with 8 (`__ARM_common_memset4_5(this + 0xA, 8)`: value 8, five bytes) |
| `m_race_rank`, `m_race_point` | `syncPlayerConfig`; `m_race_point` starts at 0x141 |
| `m_red_team_bits`, `m_team_assign_bits` | [Finding 10](#10-pages-that-move-together-vs-settings-and-teams); cleared by the constructor |
| `m_cpu_num` | the master, `MenuMulti_VSSetting::onPageCompleteCore`: `MenuData::m_num_free_player_slots` |
| `m_unlocked_cups` | the master, `MenuMulti_Mode::onPagePreStepCore`: bit i set when cup i is open (a `System::Flag` check, or the current cup) for i 0 to 7, then bit 0 from flag 4 or a byte of `DashSequenceEngine`. Read by `MenuMulti_Class::isMirrorOpen`, `MenuMulti_VSSetting::onPageEnterCore` and the clients in `MenuWiFi_WaitingDecide` |
| `m_flags` | bit 0 set by `MenuNetworkSelectMenuTask` on the way back from a race, cleared by `MenuWiFi_WaitingDecide::onPageComplete`; bit 1 set by the master in `MenuMulti_VSSetting::procOpenMenu`, cleared in its `buttonHandler_OK`; bit 2 the red team; bit 3 set by the master in `MenuMulti_VSSetting::onPageCompleteCore` |
| `m_course_vote_list` | the constructor clears its eight entries (`str r5, [r2, #0x18]` / `strb r5, [r2, #0x1c]` with r2 = this + 8 × i); [Finding 11](#11-the-course-vote) |
| `m_team_list` | [Finding 10](#10-pages-that-move-together-vs-settings-and-teams); not cleared by the constructor, but by the master in `buttonHandler_OK` and `calcTeam_` |
| `m_select_state`, `m_select_ready` | [Finding 8](#8-the-shared-state-number) |

- `NetworkSelectMenuProcess::calcRaceSettingBit` and `extractRaceSettingOne` pack and unpack one player's choices into
  a `RaceSetting`: driver (5 bits), body (5), tire (4), wing (3), race point (9), race rank minus one (3), course (6,
  from `CRaceInfo`'s course, not from the format), mode (3), team (1). Their only users are SupplyInfo
  ([Finding 15](#15-supplyinfo)).

### 10. Pages that move together, VS settings and teams

#### The common page

The pages `MenuMulti_SyncBase<MenuSingle_X>` (X = Kart, Mode, Class, CupGP, Setting) share one pattern
(`MenuMulti_SyncBase<...>::onPagePreStep`, `onPageComplete`):

- Bit 1 of a flag byte of the page says that the page is chosen on every console; otherwise only the master chooses.
- The choosing console, in `onPageComplete`: `Sequence::updateSendReturnCode_(button)` (`m_page_return_code`) and
  `setSelectStateChange`.
- A waiting console (a client on a page only the master chooses), once the page is active: step 0,
  `setSelectStateChange` (ready); step 1, wait for `m_state_changed`, then reset the SelectMenu receive bitmap; step 2,
  wait until the master's SelectMenu packet arrived (`checkReceive(master aid)`), then let the page follow the master's
  choice through one of its virtual functions.
- Other pages calling `setSelectStateChange`: `MenuWiFi_Kart`, `MenuMulti_Kart::procOpenMenu`, `MenuMulti_Mode`,
  `MenuMulti_CourseVote`, `MenuWiFi_WaitingDecide`, `MenuMulti_DlplaySequence::calcShakeHands_`.

#### The VS settings

- The master, every frame on `MenuMulti_VSSetting` (`onPagePreStepCore`): fill `m_vs_settings` with 8, then for each
  control of the page, `m_vs_settings[row]` = the control's value (`LRSelect` + 0x7C), where the row is the control's
  setting type (`LRSelect` + 0x40C; 0x14 is not a row).
- The other consoles (`onPagePreStepCore`, `onCompleteNetwork`) read the master's format (`getPlayerStatus(master)`);
  for each row that is not 8 and differs from their own control, they set the control's text and value. So a client's
  page shows the master's settings as the master changes them.
- `MenuSingle_Setting::initControl` builds five rows (`game_setup_5_00` to `04`) or four (`game_setup_4_00` to `03`);
  which setting each row holds was not mapped.

#### Teams

While teams are being set on `MenuMulti_VSSetting`, the master decides the team of every player and the other consoles
follow it:

- `MenuMulti_VSSetting::updateAppend` sets the bit of every player id but the local one in `m_team_assign_bits` (and in
  a byte of the page), and writes `m_red_team_bits` from the team of each other human racer in the race settings
  (`CKartInfo::m_team_type` 0, red, sets the bit).
- `MenuMulti_VSSetting::calcTeam_(is master)`: a client copies the master's `m_red_team_bits` into its own; the master
  rebuilds its `m_red_team_bits` from the other racers' `m_flags` bit 2 (or from the race settings while their bit in
  the page byte is set), from the race settings for the CPU slots after the humans and for itself, clears
  `m_team_list`, and clears a player's bit in `m_team_assign_bits` and in the page byte once that player's own
  `m_flags` bit 2 agrees with `m_red_team_bits`. Every console then moves itself to the master's team for it when the
  master's `m_team_assign_bits` holds its bit, and, once the bar at the top has finished, moves every other player to red
  or blue by the master's `m_red_team_bits` (`moveRedOuter` / `moveBlueOuter`):

  ```
  if (local_28 == 0) {                                     // not the master
    *(undefined1 *)(iVar9 + 0x7a) = *(undefined1 *)(iVar5 + 0x12);   // own m_red_team_bits = master's
  }
  ...
  if (((uint)*(byte *)(iVar5 + 0x12) & 1 << (uVar6 & 0xff)) == 0) MenuSingle_Setting::moveBlueOuter(param_1,uVar6);
  else MenuSingle_Setting::moveRedOuter();
  ```

  (`iVar9` is the process, whose own format starts at 0x68; `iVar5` is the master's format.) On the master, the OK
  button gets one animation while the teams differ by at most one and another otherwise (probably usable and greyed
  out).

`MenuMulti_VSSetting::buttonHandler_OK`, with teams on, counts the karts on red (`CKartInfo::m_team_type` 0) in the race
settings, over the first `NetworkPlayerDataManager::m_racer_num` karts, or over all eight when CPUs are on (`isCOM`).
If the two teams differ by two or more, nothing happens. Otherwise the master clears `m_team_list` and fills it, for
each human racer in turn, with its station id and the red bit of its `m_flags`:

```
004b7b70  add  r6, r0, #0x68        ; process + 0x68 = the own NetworkSelectMenuSendFormat
loc_4b7b78:
004b7b80  str  r9, [r1, #0x58]      ; r1 = r6 + 8 * i: m_team_list[i].m_station_id = 0
004b7b88  strb r9, [r1, #0x5c]      ;                  m_team_list[i].m_is_red = 0
```

`onPageCompleteCore` calls `correctAIInfo_`; the master then sets `m_flags` bit 3 and `m_cpu_num`.

The other consoles read the list when the page completes for them (`MenuMulti_VSSetting::onCompleteNetwork`, with the
master's format from `getPlayerStatus(master player id)`): each human racer whose station id is in the master's
`m_team_list` with `m_is_red` set goes to red, every other one to blue, and the local player's own `m_flags` bit 2
follows; `MenuData::m_num_free_player_slots` takes the master's `m_cpu_num`:

```
if (*(int *)(iVar5 + iVar6 * 8 + 0x58) == *(int *)(*piVar8 + 8)) {      // m_team_list[i].m_station_id
  if (*(char *)(iVar5 + iVar6 * 8 + 0x5c) != '\0') {                     // m_team_list[i].m_is_red
    MenuSingle_Setting::moveRedOuter(param_1,piVar8[1]);
...
*(uint *)(*(int *)(uVar11 + 0xc0) + 0x96c) = (uint)*(byte *)(iVar5 + 0x14);   // MenuData + 0x96C = m_cpu_num
```

So the final teams reach the other consoles twice: live through `m_red_team_bits`, and at the end through
`m_team_list`. The team checks of the later steps do not read `m_team_list`: `Sequence::checkTeam_` counts the `m_flags` bit 2 of each human racer (from
the merged SupplyInfo data for a disconnected one) and the teams of the CPUs in `MenuData::m_cpu_kart_infos`, and
`Sequence::checkTeam2_` the teams in the race settings; both accept a difference of at most one.

### 11. The course vote

#### The vote list

Every console must show the same list of votes, since the master draws an index into it. The master builds it and the
others copy it (`Sequence::updateCourseVoteList_`, and `Sequence::receiveCourseVoteList_` on the master once every
SelectMenu packet has arrived and no console is in another phase):

- The master, for each human racer whose SelectMenu packet arrived (or itself), turns its `m_course_vote` into a course
  id: bit 7 set, `Sequence::GetBattleCourse`; otherwise `Sequence::GetGPCourse(cup, course)` when the cup is below 8 and
  the course below 4; course 6, or anything else, a default course id kept in a global. `Sequence::registVote_` adds the
  vote to `MenuData::m_course_votes` and the bar of votes, and returns its index; the master stores {station id, course
  id} at that index of its `m_course_vote_list`:

  ```
  iVar4 = registVote_(local_30,uVar11,local_38,iVar12,param_2,param_3);
  if (-1 < iVar4) {
    iVar4 = iVar6 + 0x68 + iVar4 * 8;                  // own format + 8 * index
    *(undefined4 *)(iVar4 + 0x18) = uVar11;            // m_course_vote_list[index].m_station_id
    *(char *)(iVar4 + 0x1c) = (char)local_3c;          // m_course_vote_list[index].m_course_id
  ```
- A client copies the master's eight entries into its own `m_course_vote_list` and registers each non-empty one, in the
  master's order.

#### The page

`MenuMulti_CourseVote::onPagePreStep`, in sub-steps:

0. The own vote is in `m_course_vote`, `cup << 3 | course in the cup`, written by `MenuMulti_CupGP` /
   `MenuMulti_Course` `buttonHandler_OK`, or 0x46 when time runs out. Wait until every peer's vote is valid (cup at most
   8, course at most 6) and the vote bar has finished, then `setSelectStateChange`.
1. Wait for the state change, and on a client for the master's packet and `Sequence::updateClientRandom_`.
2. The master: `m_selected_course_vote_index` = a random index into the vote list (`MenuData::m_course_votes`); when
   the drawn vote is "random", `m_selected_random_course_id` = `Sequence::getRandomCourse_`.
3. Clients copy the master's two values, waiting while the index is still 0x27.
4. Wait until every peer shows the same two values, then the roulette.

### 12. The course chosen by the master

`MenuNetworkCourseDecideTask` (`TaskMenu_CourseDecide`, a lasting task):

- Enter codes 0 `Multi_GP`, 1 `Multi_VS`, 2 `Multi_BT`, 3 `WiFi_VS`, 4 `WiFi_BT` (`convertEnterCodeImpl`); codes 3 and 4
  end at once in `onTaskStart`, and no flow uses them.
- `onTaskStart`: the task's state = 0, whether the local console is the master, reset the SelectMenu receive bitmap,
  course = 0x29 (none); the master calls `updateMasterRandom_`.
- `onTaskStep`:
  0. Wait for every SelectMenu packet (`checkAllReceive`) and `isCountConnectedPlayerInfoSync`, then
     `NetworkPlayerDataManager::forceReceiveAll`; clients also need `updateClientRandom_`. `NetworkEngine::updateDlpInfoPart`.
  1. The master sets its `m_decided_course_id` to 0x29 and goes on. A client sets its own to 0x29 when the master's is
     still 0x29; otherwise it jumps ahead with the old value (the jump was not followed in detail).
  2. The master: `BasePage::loadNextCourse(!withDlp)` picks the course (how it picks, in cup order or at random, was not
     followed), then `m_decided_course_id` = the course of `CRaceInfo`.
  3. A client waits until the master's value is not 0x29 and takes it. All wait until no peer shows 0x29 and every peer
     shows the own value.
  4. Clients: `MenuData::m_race_no` += 1 (it starts at -1), the course goes to `MenuData::m_course_id[race]`,
     `BasePage::setRawCourseID`, and, unless Download Play children take part,
     `BackgroundLoadThread::toStartCourse`. The task returns its enter code.

### 13. Miis

- `NetworkMiiManager` (size 0x520, `NetworkEngine::m_network_mii_manager`) and `NetworkSupplyInfoManager` have no
  `onReceivedCore`: the slots after `postUpdate` in their vtables are 0, their delegate is null, and no `init` stores it
  in the controller, so every packet is stored ([Finding 3](#3-receiving)).
- `MiiSendFormat` is a CFL net packet of 0x88 bytes (`NetworkMiiStorage::getSenderPacketSize`; the buffer allows 0xC0).
  `NetworkMiiManager::setupMyMii` gets the player's Mii (`Mii::MiiEngine::getMyMiiStoreDataBySaveData`), builds the
  packet with `CFL_InitNetPacket` and `CFL_SetToNetPacket`, and keeps the Mii in
  `NetworkMiiStorage::m_my_store_data`. Callers: `MenuChannel_SetupMii::onPagePreStep`,
  `MenuNetworkSelectMenuTask::onCreate`. `NetworkDataManager<MiiSendFormat>::updateCore` copies the 0x88 bytes into
  the write buffer.
- `NetworkMiiManager::receiveAll(force)` -> `NetworkMiiStorage::receiveAll`: `CFL_InitNetInformation`; for each
  connected human racer but the local one, the packet is its read buffer when `checkReceive` (or `force`), else
  `m_last_received[aid]`, then `CFL_SetReceivedPacketWithoutFlush`; `CFL_FlushNetInformation`. Then the nodes are rebuilt
  for each human racer by player id: a disconnected one gets `Mii::MiiEngine::getDefaultMiiStoreData` with a random
  index from 0 to 5; the local one its own Mii; the others `CFL_NetInfo2StoreData` from their packet; a result of 8
  aborts with false. Callers: `NetworkPlayerDataManager::receiveCore_`, `NetworkSupplyInfoManager::copySettingEx`
  (with `force`).
- No writer of `NetworkMiiManager::m_last_received` was found (stores through `m_network_mii_manager`, accesses of
  the class, and the identical `dlp` body were checked): it stays zero.

### 14. Player profiles

- `NetworkPlayerData` is a `System::PlayerData` (profile and Mii) plus `m_race_point` (the player's SelectMenu
  `m_race_point`, 0 when its SystemInfo did not arrive) and `m_created`.
- `NetworkPlayerDataManager::ready` resets the SystemInfo and Mii receive bitmaps. `receiveAll` calls
  `receiveCore_(false)` only when both SystemInfo and Mii `checkAllReceive` hold; `forceReceiveAll` calls
  `receiveCore_(true)`. Callers of `ready` / `receiveAll`: the online waiting pages, `MenuCommunity_Top`,
  `MenuMulti_DlplaySequence::calcShakeHands_`, `MenuNetworkApplyTask::onTaskStep`,
  `MenuCommunity_Lobby::MiiIconList::check`; of `forceReceiveAll`: `MenuMulti_Cup`, `MenuMulti_Mode` and
  `MenuMulti_CourseBattle` `onPageEnter`, `Menu_UpBarController`, `MenuNetworkCourseDecideTask`,
  `updateConnection_StateChange_`.
- `receiveCore_(force)`: clear; `NetworkMiiManager::receiveAll` (false: return). For each human racer by player id: a
  disconnected one is taken from SupplyInfo `getExSetting` when it has one (its profile, its race point from
  `getSelectMenuInfo`, a random default Mii if none, `m_created = 1`), else from its last accepted SystemInfo
  (`m_last_received`) and the stored Mii; a connected one from `createPlayerDataFromSystemData` (the own format for the
  local player, else its SystemInfo read buffer, copied only when local, received or `force`) and the stored Mii, and
  appended to `m_network_player_datas_connected`. `m_my_player_data` is built from the own format and Mii and copied
  to entry 0 of the connected list.
- `fixDisconnect` (from SupplyInfo `fixManage`): each player id whose principal id is 0 or whose `PlayerID` is all zero
  takes the profile of its SupplyInfo entry, when there is one.
- `m_racer_num` counts the human racers with the disconnected ones, and the local player only while it is a racer; it
  is read by race code and by `MenuWiFi_Confirm` and `MenuMulti_VSSetting`. `m_connected_num` is read by
  `MenuWiFi_Waiting` and `MenuMulti_VSSetting`.

### 15. SupplyInfo

- `NetworkSupplyInfoSendFormat` = `PlayerInfo[8]` by player id: the player's principal id (from its SystemInfo
  profile) and its packed `RaceSetting`.
- `copySetting`: for each connected human racer whose SelectMenu packet arrived (or the local one),
  `m_player_infos[player id]` = {principal id, `calcRaceSettingBit(its SelectMenu format)`}. Callers:
  `MenuWiFi_Waiting::onPagePreStep`, `MenuNetworkApplyTask::applyNetworkSetting_`,
  `MenuWiFi_WaitingDecide::onPagePreStep`.
- `copySettingEx`: clears the `ExSetting` entries; `NetworkMiiManager::receiveAll(true)`; for each connected human racer
  whose SystemInfo arrived, an `ExSetting` with its station id, its profile and its Mii. Callers: the same two online
  pages.
- `fixManage` (whose end is a separate function in `eur2`, `fixManageExtract_`; one function in `dlp`) needs SupplyInfo
  `checkAllReceive`. It clears the eight keys, then:
  1. For each connected console S, key = `NetworkSystemInfo::m_ticks[aid of S]` (when S's last packet arrived). Each
     non-empty entry j of S's table replaces `m_inner_player_infos[j]` when its key is greater, so the newest report
     wins, and links the `ExSetting` of S's station, which holds S's own profile, also for j other than S.
  2. For each connected console S, its own entry is taken with key 1 and S's `ExSetting`.
  3. For each valid j, `extractRaceSettingOne` unpacks the entry into `m_select_menu_info`; a counter (a global)
     advances by one modulo 10; then `NetworkPlayerDataManager::fixDisconnect`.

  Callers: `NetworkEngine::checkAllRaceSettingReceived`, `MenuWiFi_WaitingDecide::onPagePreStep`.
- `extractRaceSettingToSelectMenu`: for each valid player id with a buffer id, copies its merged
  `m_select_menu_info` (0x9C bytes) over the SelectMenu read buffer of that aid, so that `getPlayerStatus` returns the
  merged choices. Callers: `MenuNetworkApplyTask::applyNetworkSetting_`, `MenuWiFi_WaitingDecide`.
- So every console reports what it knows of every player, and a console that missed a player's SelectMenu packet,
  joined late, or lost the player still gets that player's choices and profile from the others. Probable, from the
  flow: only the online pages and the race-setting check use it.

### 16. Friends

`NetworkFriendsManager` (size 0xA800) is only used in local play.

- `initializeApproach` (from `MenuMulti_Waiting::onPageEnter`) prepares the approach context. `MenuMulti_Waiting::
  onPageComplete` fills `MenuData::m_friend_approach[8]` with each other console's local friend code and a
  `m_register_state`: 1 when the player ticked it (a control at list control + 0x40D), 2 from another control (+0x40C,
  probably "already a friend"), only while the friend list has room (fewer than 100).
- `updateFriendApproachBuffer` rebuilds `m_approach_send_format` (`GetMyApproachContext`, then the codes, all bytes
  0xFF first: entry 0 the own local friend code, from the matching manager, scrambled again with the own player id;
  then the codes of the ticked consoles; `m_is_valid`) and puts it in the Friend write buffer. It is called every frame
  of most steps of `MenuMulti_DlplaySequence::calcShakeHands_` (0 and 3 to 8).
- `checkAllCorrectReceive`: every other station's Friend read buffer has `m_is_valid` set.
- `NetworkEngine::addFriend` (through `NetworkEngine::request`, task 0xE) calls, for each other station,
  `NetworkFriendsManager::addFriend(aid)`: if that console's packet arrived, its own code is in
  `MenuData::m_friend_approach` with `m_register_state` 1, and its list holds the local code (both players ticked each
  other), then `nn::friends` `AddFriendWithApproach` with its context, and its Mii name is queued; the handshake shows a
  system message per name.
- `m_approach_flags`: bit 0 the approach context was obtained; bits 1 and 2 two error results of
  `GetMyApproachContext` (0xD860C4F2, 0xD8A0C4F8; which bit for which was not checked); bit 3 set when one of the
  outputs of `GetMyPreference` is set, and then no approach is made.

### 17. Block transfer (Wbt)

The Wbt buffer carries large data, 900 bytes per packet. Its only user is `RaceSys::CourseArchiveManager::withTrans`
(called from `loadCore` when a byte of the manager is set; its writer was not checked): the master sends the course
archive and its sound data to the Download Play consoles.

#### The flow

- Every console first loads the course itself (`System::CacheDataCommon::load` of `/Course/<name>`, and the course sound
  data from `Sound::SndLoader::getCourseDataPath`).
- The master (local player id = master player id, and `withDlp`, that is `m_dlp_child_aid_bits` not 0):
  `Buffer::ready(m_dlp_child_aid_bits, the next engine byte, false)`, which calls `initAsParent`;
  `registSendData(0, archive, size)` and `(1, sound data, size)`; `start`.
- Every other console: `ready(..., true)` (`initAsDummyChild`), `registRecvData(0, null, 0)` and `(1, null, 0)`,
  `start`. The loading thread then sleeps (`sleepCurrentThread(1000)`) until `Buffer::m_is_running` is cleared.
- The branch that receives the data (it frees and prepares the two buffers, `ready(0, 0, false)`, which calls
  `initAsChild`, and registers the buffers) is never taken in `eur2`, where the test loads a constant 0:

  ```
  mov r0, #0
  cmp r0, #0
  beq ...
  ```

  In `dlp` the same test loads 1. So the game in `eur2` is the sender or a dummy child; only the Download Play child
  program receives.

#### Start, frames and finish

- `NetworkWbtMgr::start` (when ready): `m_is_running = 1`; `NetworkEngine::m_is_wbt_running = 1` (Mii and SupplyInfo
  stop sending); `m_wbt_started = 1` (no kart data in the packet); SystemInfo `resetReceive`; a flag of the error handler
  cleared; and some transport globals (out of scope).
- `NetworkWbtMgr::calc` (while running): on the master, unless `m_is_waiting`, send the buffer; while the error
  handler's flag is clear, save the policy's send interval into `m_saved_send_interval`, set it to 0, send 5 more times
  (`NetworkEngine::sendBuffers` and the buffer update), and restore it: 6 packets per frame. When the flag is set, wait
  at least 50 ms (`m_is_waiting`, `m_wait_start`) and clear it. Other consoles update the buffer once per frame. Then
  `Buffer::calc`.
- `Buffer::updateCore`: when a finish is pending, clear the write buffer and call the finish delegate; while running,
  `WbtProtocol::sendHook(write buffer, 900)`, whose result is the size. `Buffer::onReceivedCore` (while running) calls
  `recvHook(aid, data, size)` and returns true.
- `Buffer::calc`: computes the disconnected aids and calls `isFinished`. Not finished: if the number of human racers
  changed since `ready` (`m_player_num_at_ready`), the transfer is ended. Finished: the master is done; a child also
  needs the master's last packet to hold no Wbt data (`m_empty_recv_bitfield` bit 0). Then a finish is pending, the
  buffer is no longer running or ready, and the finish delegate (`finishHandler`) runs: `WbtProtocol::finalize`,
  `m_is_wbt_running = 0`, `m_wbt_started = 0`, SystemInfo `resetReceive`, and the transport globals restored.

#### The protocol

- Every packet starts with a `PacketHeader`. The master's data packets: {block, `DATA`, chunk, block size} and
  min(892, rest) bytes of the block from chunk × 892. Its end-of-pass packet: {block, `END_OF_PASS`, 0xFFFF, 0}, when
  the first pass is over and no request is queued. A child's packet: {its current block, `DATA`, the chunk it asks for,
  chunks received}, block 0xFF when it has every block. A dummy child always sends {0, 0, 0, 0}.
- Master `sendHook`: only with a current block and `m_wait_aid_bits` = 0; the first pass sends every chunk in order,
  then the requests in the queue; with nothing to send, the end-of-pass packet.
- Master `recvHook` (8-byte packets only): a packet from an aid that is not a child clears it in `m_wait_aid_bits`.
  The current block: store the child's count and queue its requested chunk once. Another block id:
  `m_child_block_ids[aid]` = it; once every child reports the same id, start that block (chunk count = size / 892
  rounded up, a new first pass, the queue emptied), or finish when no block has that id (0xFF after the last one).
- Child `sendHook`: before the first chunk of a block, report the block id; after it, ask for the next missing chunk,
  from the cursor up to the highest chunk seen.
- Child `recvHook` (from aid 0 only): the first chunk of the current block sets the chunk size and count; every chunk is
  copied into the registered buffer (bounds-checked against the registered size, which is then replaced by the real
  size) and marked in `m_child_received_bits`. An end-of-pass packet raises the highest chunk seen to the last one, so
  the tail can be asked for. With every chunk, the next block starts, or the transfer is finished after the last one.
  A dummy child counts the master's changes of block in `DATA` packets and finishes after as many as it registered.
- `WbtProtocol::isFinished(disconnected)`, on the master, drops disconnected aids from the child and wait bitmaps; it
  is finished when no child is left, or when a block is current and every remaining child's `m_child_block_ids` entry is
  still -1. The second condition seems odd, since any report stores a byte; in practice `recvHook` sets
  `m_is_finished` when every child reports 0xFF.

### 18. Where the network steps sit in the scene sequence

From `mk7 bseq dump MenuScene-Default`.

#### The network tasks

- `MenuNetworkSelectMenuTask` is subsection 7 of the `MenuScene` root (parallel, mode `Default`). Unlike the other
  parallel subsections it is not started anyway: only the root's flows start it, next to `Seq_Title`, with these enter
  codes: `Title_Top` -> `Default`, `MultiVS_Course` / `MultiBB_Course` / `MultiBC_Course` -> `Multi_Course`, `Multi_Top`
  -> `Multi_Mode`, `WiFi_Top` and `Commu_Top` -> `WFC_Top`, `WiFi_Matching` -> `WFC_MemberCheck`, `Commu_Lobby` ->
  `WFC_CommuLobby`, `Commu_Course` -> `WFC_CommuMember`. It is not started for `Boot`, `DLC`, `FromFriendList`,
  `FromTitleDemo`, the single-player entries and `DirectWiFi`.
- `MenuNetworkApplyTask` (return code `Next`): in `Seq_Multi` (items 26 VS, 29 battle, 33 Grand Prix, each followed by
  `Page_CourseDl`), in `Seq_WiFi` (items 21 and 22 after `Page_WaitDeside` / `Page_WiFiWaiting` return `WatchRace` /
  `WatchBattle`, item 36 after the online course vote) and in `Seq_Community` (items 14 and 15 after
  `Page_CommunityTop` returns `WatchRace` / `WatchBattle`).
- `TaskMenu_CourseDecide` (`MenuNetworkCourseDecideTask`) only in `Seq_Multi`: after `Page_MultiCupGP` (`Multi_GP`),
  after `Page_MultiVSSetting` returns `Next01` (`Multi_VS`) and after `Page_MultiBattleSetting` returns `Next01`
  (`Multi_BT`): the paths that skip the course pages. Its `WiFi_VS` / `WiFi_BT` codes are in its tables but no flow
  uses them.
- `isFromWatch` (`MenuNetworkSelectFromWatchTask`) only in `Seq_Community`, after a mode setter task: it routes to one of
  two `Page_WaitDeside` items ([Finding 21](#21-the-online-pages)).

#### Seq_Multi (local play)

- `Default` -> scene setter (`Multi`) -> `Page_MultiGroup` (join or create a group) -> `Next` / `Next_Create` ->
  `Page_MultiWating` (enter `Next` / `Next_Host`) -> `Next` -> `Page_MultiDlpSeq` -> `Next` -> `Page_MultiMode`.
- `Page_MultiMode` `Next00` (Grand Prix) -> mode setter (`GrandPrix`) -> Class -> Chara -> Kart -> CupGP ->
  CourseDecide (`Multi_GP`) -> Apply -> `Page_CourseDl` (GP).
- `Next01` (VS) -> mode setter (`Versus`) -> Chara -> Kart -> VSSetting. VSSetting `Next00` -> Cup -> Course (`Next00`)
  or CourseVote (`RandomNext`, `Next01`) -> CourseVote -> Apply -> CourseDl (VS). VSSetting `Next01` -> CourseDecide
  (`Multi_VS`) -> Apply -> CourseDl (VS).
- `Next02` / `Next03` (balloon / coin) -> mode setter -> Chara -> Kart -> BattleSetting; `Next00` -> CourseBattle ->
  CourseVote -> Apply -> CourseDl (BT); `Next01` -> CourseDecide (`Multi_BT`) -> Apply -> CourseDl (BT).
- `Page_CourseDl` returns `GP` / `VS` / `BT`, and `Seq_Multi` returns `GP` / `VS` / `Battle`.
- After a race: `VS_Course` / `BB_Course` / `BC_Course` -> scene setter -> mode setter (`Versus` / `BalloonBattle` /
  `CoinRunner`) -> `Page_MultiCup` or `Page_MultiCourseBattle` (enter `ReturnFromGame`): the next race skips the lobby,
  character and kart pages. `ReturnFromGame` -> `Page_MultiMode` (enter `ReturnFromGame`). `DLC` (a Download Play
  console) -> scene setter -> `Page_MultiDlpSeq` directly.

#### Seq_WiFi (online play)

- `Default` -> scene setter (`WFC`) -> `Page_WiFiConnect` -> `Normal` -> `Page_WiFiModeOpponent`: `Anybody` ->
  `Page_WiFiMode` (`Next00` VS, `Next01` battle) -> mode setter -> `Page_WiFiChara` -> `Page_WiFiKart` ->
  `Page_WiFiWaiting` (enter `Next`); `Friend` -> `Page_WiFiFriend` (`Versus` / `BallonBattle` / `CoinRunner`) -> mode
  setter -> Chara -> Kart -> WiFiWaiting (enter `FromFriendList`); `Community` -> `Seq_Community`.
- `Page_WiFiWaiting` returns `Next` -> `Page_WaitDeside` (enter `Next`); `WatchRace` / `WatchBattle` -> Apply items 21 /
  22 -> return `VS` / `Battle` (straight to the race, as a spectator); `MatchingError` -> an error page; `Back` -> Kart.
- `Page_WaitDeside` returns `Next` -> `Page_WiFiConfirm` (enter `Next`) -> `Race` -> `Page_WifiCup` -> `Next00`
  `Page_WiFiCourse` -> `Page_WiFiCourseVote`, `Next01` -> CourseVote (`RandomNext`); `BalloonBattle` / `CoinBattle` ->
  `Page_WiFiCourseBattle` -> CourseVote; CourseVote -> Apply items 36 / 22 -> return `VS` / `Battle`. `WatchRace` /
  `WatchBattle` -> Apply items 21 / 22.
- After an online race the menus are entered with `WiFi_Matching` -> `MemberCheck` -> scene setter -> mode setter
  (`Versus`) -> `Page_WaitDeside` (enter `ReturnFromGame`): between races only WaitDeside -> Confirm -> the course pages
  run.
- Other entries: `TopMenu` -> ModeOpponent; `FromFriendList` -> Connect -> `Normal` -> scene setter -> ModeOpponent,
  `Community` -> `Seq_Community` (`HOME`); `FromChToJoin` (joining a friend from the Mario Kart Channel) -> scene setter ->
  `MenuJoinSelectTask` -> `Versus` / `BalloonBattle` / `CoinRunner` -> mode setter -> Chara (enter `FromHM`) -> Kart ->
  WiFiWaiting (`FromFriendList`).

#### Seq_Community

- `Community` / `FriendList` / `CH` / `HOME` -> `Page_CommunityEnter` -> `Page_CommunityTop` (one item per entry, which
  differ only in where `Back` goes). Top returns: `Lobby` -> `Page_CommunityLobby`; `Race` -> `Page_WaitDeside`;
  `WatchRace` / `WatchBattle` -> Apply items 14 / 15 -> return `VS` / `Battle`; `Search` -> search pages -> Top; `Create`
  -> the pages that create a community -> Top.
- `Page_CommunityLobby` `Next` -> `Page_WaitDeside` (item 13) -> `Next` -> `Page_WiFiConfirm` (item 20) -> mode setter ->
  `Page_CommunityChara` -> WiFiKart -> WifiCup / WiFiCourseBattle -> course pages -> CourseVote -> Apply -> race.
- After a community race (`Commu_Course`) -> scene setter -> mode setter (`Versus`) -> `isFromWatch`: `FromWatch` ->
  WaitDeside item 23, `FromPlay` -> item 24; both go on to Confirm. From `FromWatch`, Confirm (item 29) leads to
  `Page_CommunityChara`: a console that watched picks a character now. From `FromPlay`, Confirm (item 30) leads to
  `Page_WifiCup` (enter `ReturnFromCommu`): the characters are kept. WaitDeside `CommuLobby` -> `Page_CommunityLobby`
  (enter `FromGame`).
- `Commu_Lobby` -> scene setter -> mode setter -> WaitDeside item 19 (`ReturnFromGame`) -> `Next` -> Lobby.

### 19. Entering the menus: MenuNetworkSelectMenuTask

A lasting task.

- Enter codes (`convertEnterCodeImpl`): 0 `Default`, 1 `Multi_Course`, 2 `Multi_Mode`, 3 `WFC_Top`, 4
  `WFC_MemberCheck`, 5 `WFC_CommuLobby`, 6 `WFC_CommuMember`. Modes (`convertModeImpl`): 0 `Default`, 1 `Once`. The
  file only uses `Default`; the `Once` branch (finish the game setting, pause the mode manager, fade the sound out,
  `decidePlayers` on the master, phase 0x34) is unused by the retail data.
- `onCreate`: creates `NetworkSelectMenuProcess` in `MenuData::m_network_select_menu_process` if there is none, calls
  `NetworkMiiManager::setupMyMii`, and clears the task's error flag.
- `onTaskStart`: an unnamed byte of the engine, which several menu pages also set, = 0; `m_phase` = `SELECT_MENU`; `NetworkSelectMenuProcess::init`; code 3
  -> `NetworkSelectMenuProcess::disconnectNetwork`; empties `MenuData::m_course_votes`; `acceptPlayers`.
  - Codes 0 and 3 (a fresh start): `CKartInfo::init(MenuData::m_kart_info)`.
  - Codes 1, 2, 4, 5 and 6 (back from a race): in team mode, when `Sequence::checkTeam2_` fails, error 0xC goes to the
    error handler (unless an error is set already) and the task's error flag is set. Then `syncPlayerConfig_` (below);
    online, `NetworkEngine::updateMasterOuter`; `NetworkSelectMenuProcess::syncPlayerConfig` (true for codes 1, 4 and
    6); `startSelect(1)` (state forced to 0); `m_flags` bit 0 set; the same engine byte = 1. Code 4: `m_mode` from the race
    mode (VS 0, balloon 2, else 1). Codes 1 and 2 on the master: `NetworkEngine::updatePlayerList(0)`.
  - Then: codes 3 and 4 -> `BasePage::initRaceNo`; `BasePage::setMasterPlayerID(0)`, `setCameraTargetPlayerID(0)`;
    `NetworkSystemInfo::m_accept_other_phase = 1`.
- `onTaskStep` returns 0 (done) at once unless the error flag is set, then -1 forever: a one-frame setup, whose return
  code leads nowhere.
- `syncPlayerConfig_`: when `MenuData::m_is_cpu_enabled`, the race point and rank of the CPU slots of the race settings
  are copied into `MenuData::m_cpu_kart_infos`. Then, when the local player id is neither 0 nor -1, the local player's
  choice goes back into kart slot 0 of the menu's race settings (body, tire, wing, driver, race point, rank, team): from
  the race slot of its player id when it was a racer, else from the saved `MenuData::m_kart_info` (race point 0, rank 8,
  team 3), which is then cleared. So after racing in slot N, the menus show the player's own choice again.

### 20. The local handshake

#### MenuMulti_DlplaySequence

- `onPageEnter`: by the state of the local matching object (0 host, 2 client), a host starts with distribution
  (Download Play) and a client with waiting for it; a waiting system window opens.
- `onPagePreStep` (page active) runs one of `calcDistribute_`, `calcUdsServer_`, `calcWaitDistribute_`,
  `calcUdsClient_` (transport, out of scope) and `calcShakeHands_`, then closes the window and ends the page (`Next` ->
  `Page_MultiMode`).
- `calcShakeHands_`, by its own state:
  0. Once every console sees the same racers (`isCountPlayerInfoSync`): `startSelect(0)` and `setSelectStateChange`, the
     friend buffer, `m_flags` bit 2 of SystemInfo cleared, the SelectMenu receive bitmap reset,
     `NetworkPlayerDataManager::ready` -> 3. (States 1 and 2: a timed path for Download Play that compares the number of
     human racers with a count kept in `MenuData`; not followed.)
  3. Every frame `updateFriendApproachBuffer`; wait for the state change, every SelectMenu packet and
     `NetworkPlayerDataManager::receiveAll`, then `startKeepAliveCheck`; then every friend packet
     (`checkAllCorrectReceive`) -> 4.
  4. `NetworkEngine::request(0xE)`, which adds the friends ([Finding 16](#16-friends)) -> 5: wait for the result; with
     names to show -> 6 (one system message per new friend), else 7.
  7. `setSelectStateChange` -> 8: wait for the state change, close the window -> 9: clients wait for
     `updateClientRandom_`; `NetworkEngine::updateDlpInfo`; end of the page.
- From here on the set of consoles is fixed for the menus: `acceptPlayers` was called by the select menu task, and
  `decidePlayers` comes with the apply task.

#### The lobby

`MenuMulti_Waiting::onPagePreStep`: the host's start button is enabled only while one to seven other consoles are
connected (a list of the UDS object); a client ends the page when the host has started. The server list, the connection
and the wireless switch are transport, out of scope.

### 21. The online pages

#### MenuWiFi_Waiting (the matchmaking room)

- Codes: enter 0 `Next`, 1 `Back`, 2 `FromFriendList` (`convertEnterCodeImpl`); return 0 `Next`, 1 `WatchRace`, 2
  `WatchBattle`, 3 `MatchingError` (`convertReturnCodeImpl`).
- `onPageEnter`: from the friend list, a message with the friend's Mii name (`MenuData::m_mii_name`); otherwise a waiting
  message, whose back button is hidden while at least two consoles are connected. Sub-step 0, timer 300.
- `onPagePreStep`, by sub-step (a matching error leads to `calcMatchingError_`):
  - 0: wait until more than one console is connected (`m_human_connectors` without the disconnected ones), and either
    more than seven or the 300 frames are over -> 1: the same unnamed engine byte as in
    [Finding 19](#19-entering-the-menus-menunetworkselectmenutask) = 1, `startKeepAliveCheck`, `decidePlayers` -> 2.
  - 2: once another unnamed flag of the engine is clear and `isCountPlayerInfoSync`: Mii icons, SupplyInfo `copySetting` /
    `copySettingEx`, `NetworkPlayerDataManager::ready` -> 3 (if a countdown runs out first: error 0xC).
  - 3: `receiveAll`; 4 to 8: the Miis are introduced on the globe (`GarageDirector`), then a closing message (120
    frames).
  - 9: a racer ends the page with `Next`. A spectator goes to 10: `stopKeepAliveCheck`, then for 30 frames watches for
    `isOtherPhaseDataReceived` (a race is running) -> 0xC; if none, `startKeepAliveCheck` and `Next`.
  - 0xC (spectator): once `isCountPlayerInfoSync`, `checkAllRaceSettingReceived`, `receiveAll` and
    `updateClientRandom_` hold: `m_accept_other_phase = 0`, the player's kart slot 0 of the race settings is saved in
    `MenuData::m_kart_info`, and the page returns `WatchRace` (rule `Versus`) or `WatchBattle`. If
    `Sequence::isAnyReturnFromGame_`, or the console is no longer a spectator: `Next`.

#### MenuWiFi_WaitingDecide (Page_WaitDeside)

- Codes: enter 0 `Next`, 1 `ReturnFromGame`; return 0 `Next`, 1 `WatchRace`, 2 `WatchBattle`, 3 `CommuLobby`.
- `onPageEnter`: `NetworkPlayerDataManager::ready`; `ReturnFromGame` -> sub-step 5 and `stopKeepAliveCheck`; `Next` ->
  0. In a community, `CommunityMgr::applyGameMode`.
- `onPagePreStep`, every frame: the master `updateMasterRandom_`, clients `updateClientRandom_`;
  `syncPlayLogSendRequest`; when not `ReturnFromGame`, clients copy the master's `m_mode` (`Sequence::copyMasterMode_`);
  after 600 frames the message changes; the unnamed engine byte of
  [Finding 19](#19-entering-the-menus-menunetworkselectmenutask) = 1. Sub-steps:
  - 0: a client -> 3. The master: fewer than two connected racers -> error 5; else 1: `decidePlayers` -> 2: wait for
    `isMatchInfoSynchronized`, select state change -> 4.
  - 3 (client): once the master has decided the players: a spectator waits for `isOtherPhaseDataReceived` and
    `receiveAll` -> 7; a racer waits until the master's select state is not behind, then `copySetting` /
    `copySettingEx`, `startSelect(0)` once, `setSelectStateChange` -> 4.
  - 4: wait for the state change and the message; `updateSendPlayLogRequest`; `receiveAll`; after `ReturnFromGame`,
    SupplyInfo `fixManage` and `extractRaceSettingToSelectMenu`; `Sequence::updateRaceMode_`. In a community, clients
    copy the master's `m_race_num` into their own and into `MenuData::m_race_no` (0xFF -> -1); race number above 2 ->
    `CommuLobby`, or watched (`MenuData::m_is_community_watch`) with race number -1 -> `CommuLobby`. Else `Next`.
  - 5 (`ReturnFromGame`): `checkAllSameSceneReceived` -> `startKeepAliveCheck`, `updatePlayerList(1)`,
    `decidePlayers`, `copySettingEx`; in a community after watching, `CommunityMgr::applyRaceNum` -> 6.
  - 6: `isMatchInfoSynchronized`, else count frames (3601, one minute: error 0xC); `copySetting`; a spectator -> 7.
  - 7: a spectator does what `MenuWiFi_Waiting` does in 0xC: save its kart, `WatchRace` / `WatchBattle`. A racer, once
    `isMatchInfoSynchronized`: select state change -> 4.
- `onPageComplete`: `m_flags` bit 0 cleared, `MenuData::m_is_community_watch = 0`.
- So a community match goes back to the lobby after the race numbered 3, that is after four races (probable).

#### MenuWiFi_Confirm and MenuCommunity_Top

- `MenuWiFi_Confirm::onPageEnter`: the list of players with their Miis and VR (not in a community) and a message by
  race mode; in a community `applyGameMode`. `onTimeUpComplete` returns by race mode: 0 `Race`, 1 `BalloonBattle`, 2
  `CoinBattle` (`convertReturnCodeImpl`).
- `MenuCommunity_Top::onPagePreStep`, states 0xC to 0xE: a community match search (`autoMatchNetwork`), wait for
  SystemInfo `checkAllReceive`, `NetworkPlayerDataManager::ready`; then `isCountPlayerInfoSync` and `receiveAll` ->
  0xE. A racer: `MenuData::m_is_community_watch = 0`; when it is the master, or the master still accepts players
  (`m_is_accepting_players`) -> `Lobby`; else `applyRaceNum` -> `Race` (-> WaitDeside). A spectator: when two further
  checks hold (functions not decompiled) and `checkAllRaceSettingReceived`: `m_accept_other_phase = 0`,
  `MenuData::m_is_community_watch = 1`, `WatchRace` (rule `Versus`) or `WatchBattle`; otherwise
  `m_is_community_watch = 0` and `Race`. Return codes: 0 `Lobby`, 1 `Race`, 2 `WatchRace`, 3 `WatchBattle`, 4
  `Search`, 5 `Create`, and more.
- `MenuNetworkSelectFromWatchTask::onTaskMain` (an instant task): `MenuData::m_is_community_watch` set -> 0
  `FromWatch`, else 1 `FromPlay`.
- Every store to `MenuData::m_is_community_watch` in `eur2`: `MenuCommunity_Top` (1 and 0 above),
  `ClearRaceInfoTask::onTaskMain` and `clearCommuInfo` (0), `MenuWiFi_WaitingDecide::onPageComplete` (0). So it means
  "joined the current community match as a spectator"; online spectators outside communities do not set it.

### 22. Spectators

- Who: a console whose station is in the spectator list, so `m_is_not_racer` stays set because the master's list does
  not hold it ([Finding 4](#4-stations-aids-and-player-ids)). Its packets are dropped by the others, since its
  `m_buffer_id` is -1 ([Finding 3](#3-receiving)).
- Menus: `MenuWiFi_Waiting`, `MenuWiFi_WaitingDecide` and `MenuCommunity_Top` find a running race through
  `isOtherPhaseDataReceived`, wait for the settings (`checkAllRaceSettingReceived`, which runs SupplyInfo `fixManage`),
  the profiles and the master's seed, then go to `MenuNetworkApplyTask` ([Finding 23](#23-the-last-step-menunetworkapplytask)).
- `MenuData::m_kart_info` keeps the spectator's own choice; `MenuNetworkSelectMenuTask::syncPlayerConfig_` restores it
  after the race ([Finding 19](#19-entering-the-menus-menunetworkselectmenutask)).

### 23. The last step: MenuNetworkApplyTask

A lasting task, the last step before the race or the course download.

- `onTaskStart`: the master calls `decidePlayers`; `m_phase` = `APPLY`; online, `MenuData::m_is_cpu_enabled = 0` and
  `m_num_free_player_slots = 0` (no CPUs online).
- `onTaskStep`: in local play, wait until the master no longer accepts players (`m_is_accepting_players`, copied from
  the master), `isCountConnectedPlayerInfoSync`, the master's phase is `APPLY`, and `NetworkPlayerDataManager::receiveAll`.
  Online, no wait. Then `applyNetworkSetting_`; done (0) unless it set the task's retry flag.
- `applyNetworkSetting_` (session active, no error pending):
  - A spectator (`m_is_not_racer`): SupplyInfo `extractRaceSettingToSelectMenu`; `checkWatchCourse_` = the
    `m_selected_course_vote_index` byte of the first other racer's SelectMenu data (0x28: none -> error 5 and retry
    flag); `BasePage::setRawCourseID`; outside communities `updateBattleMode_`, from that racer's `m_mode`: 1 online
    coin battle, 2 online balloon battle, 3 VS 150cc, 4 VS 100cc, 6 VS 150cc mirror (0 and 5 change nothing). Only 0, 1
    and 2 are written online ([Finding 9](#9-selectmenu-packets)); no writer of 3, 4 or 6 was found among the stores to
    the own format (`MenuWiFi_Mode`, `copyMasterMode_`, `MenuMulti_Mode`, the select menu task).
  - In a community (the matching manager's community flag): `CommunityMgr::applyGameMode`.
  - `decidePlayers`; `m_accept_other_phase = 0`; the average latency of each aid from the engine's sums.
  - When `MenuData::m_selected_option` is 0, or 2 and this is the first race: `BasePage::loadNextCourse(1)`.
  - `updatePlayerStatus_(racer)`: a racer -> master player id = its own player id, camera target = itself; a spectator
    -> master player id -1, camera target = `calcCameraTargetPlayerID_` (`MenuData::m_watch_principal_id` if that
    player races, else a random friend among the racers, else a random racer; seeded from the clock).
    `clearAllPlayer`, then for every human racer `updateOneDriver_(player id, SelectMenu data, profile)`: a disconnected
    one from SupplyInfo (`getSelectMenuInfo`, `getExSetting`), the others from `getPlayerStatus` and their SystemInfo
    profile (the local one from its own). `updateOneDriver_`: without data or with driver 0x13, driver 7, parts 0, VR
    1000, point 0, team 1 in team mode; else driver, parts, VR, points and team from the data (the local player marked
    as the player, the others as remote). With `m_is_cpu_enabled`, the CPU slots after the humans get driver, parts and
    team from `MenuData::m_cpu_kart_infos`, as many as `m_num_free_player_slots` (6 when negative, and never past slot
    7); a negative `m_num_free_player_slots` then takes the number of CPUs added:

    ```
    iVar14 = *(int *)(iVar12 + 0x96c);  if (iVar14 < 0) iVar14 = 6;
    ...
    if (*(int *)(iVar12 + 0x96c) < 0) *(int *)(iVar12 + 0x96c) = iVar5;     // number of CPUs added
    Net::NetworkStationBufferManager::adjustForAI(...);
    ```
  - In team mode, when `checkTeam_` fails: error 0xC and the retry flag (the error ends the scene).
  - Otherwise the ranks: for the eight slots, the points and previous rank of each human (the local one from its own
    format, a disconnected one from SupplyInfo, 0x141 -> 0), then the CPUs from `MenuData::m_cpu_kart_infos` (rank
    0xFF -> a random 100 to 255), empty slots point 0 and rank 0xFF. The random numbers come from a `sead::Random`
    seeded with the master's `m_master_random`, so every console gets the same values. Sorted by points, highest first
    (`ranksort_`) -> `setTotalRank` / `setUniqTotalRank`; by previous rank, lowest first (`ranksort2_`) ->
    `setRaceRank` (probably the starting grid). Then `updateRaceInfo` and SupplyInfo `copySetting`.

### 24. The two ways out of the settings pages

`Page_MultiVSSetting` and `Page_MultiBattleSetting` return `Next00` (to the course pages) or `Next01` (to
`MenuNetworkCourseDecideTask`), like `Page_SingleSetting`, whose `Next01` goes straight to the race:

- A page's return code is the id of the button that completed it (`BaseMenuButtonControl::completeNext`, kept in the
  page). `MenuSingle_Setting::buttonHandler_OK` tests the value of the course-selection control (the control at index
  2, or 1 when a byte of the page is set): when it is 1, it asks the garage for state 0xF instead of 0xC, and the page
  opens a start message instead of completing. `onPageComplete`, for return code 1, applies the battle settings at once
  (`BaseMenuPage::applySetting_Battle`) and starts the fade-out, which the single-player flow follows by starting the
  race.
- `UI::LRSelect::apply`, for a control of setting type 3 (the course selection), writes its value into
  `MenuData::m_selected_option`. On the settings page, its values read 0 "choose", 1 "random" and 2 "in order" (the
  order of the control's texts; not tested by this research).
- `MenuMulti_VSSetting::onCompleteNetwork`, on the other consoles, tests `m_selected_option` too: when it is 1, it sets
  a flag of the page and calls one of the page's virtual functions, instead of pressing the page's current button.
- So `Next01` is the way out when the course is not chosen on a course page: the course is then picked by the master
  in `MenuNetworkCourseDecideTask` ([Finding 12](#12-the-course-chosen-by-the-master)). Probable: which button id the
  start message completes the page with was not followed.

### 25. Corrections to the templates and to earlier notes

- `NetworkSystemInfo` is 0x208 bytes, not 0x1F0 ([Finding 5](#5-systeminfo-packets)); `NetworkSystemInfoManager` keeps
  its size of 0x2F0, so only the members after `m_system_info` move.
- `NetworkSelectMenuSendFormat::m_course_id` holds the index of the winning vote, 0x27 when none, not a course id: the
  master draws it in `MenuMulti_CourseVote::onPagePreStep` ([Finding 11](#11-the-course-vote)). The template's
  `NetworkSelectMenuProcess::m_selected_course_vote_index` at the same place (0x68 + 0x03) already had the right name.
- `NetworkStationBufferManager`: the tables at 0x7C and 0x84, named for racers and audience, hold the human stations and
  the CPU slots; the lists at 0x98 and 0xA4 include the disconnected racers; the bitmap at 0xCC holds the racers' aids,
  not free ones; 0xD4 is two counters, not a buffer ([Finding 4](#4-stations-aids-and-player-ids)).
- `NetworkBufferController::m_connector_ack_bitfield` marks the aids whose last packet held none of the type, not an
  acknowledgement ([Finding 3](#3-receiving)).
- `NetworkSystemSendFormat::m_master_game_frame`: each console sends its own frame; only `getMasterGameFrame` reads the
  master's ([Finding 5](#5-systeminfo-packets)).
- `MenuData::m_num_free_player_slots` is the number of CPU karts ([Finding 23](#23-the-last-step-menunetworkapplytask)),
  as its name suggests; `Sequence::checkTeam_` and `checkTeam2_` loop over that many entries of
  `MenuData::m_cpu_kart_infos`.

## Confidence

Nothing in this research was tested in game. Everything rests on the decompilation and disassembly of `eur2` and on
the scene sequence file.

### Certain (read directly in the code)

- The buffer layer: the sizes, the packet header, building and splitting the packet, the double buffering, the receive
  delegates, the send policies and their intervals ([Findings 1 to 3](#1-creating-the-buffers)).
- The station tables, aids and player ids, and the template corrections that follow from them
  ([Finding 4](#4-stations-aids-and-player-ids)).
- The layout of `NetworkSystemSendFormat` where a writer or reader was found, the receive checks (sequence, phase), the
  latency echo, and the size of `NetworkSystemInfo` ([Finding 5](#5-systeminfo-packets)).
- The shared state number and its rules ([Finding 8](#8-the-shared-state-number)).
- The fields of `NetworkSelectMenuSendFormat` with a writer named in [Finding 9](#9-selectmenu-packets), the VS
  settings mirror, the team bitmaps and the team list, the vote list and the vote
  ([Findings 10 and 11](#10-pages-that-move-together-vs-settings-and-teams)).
- The course chosen by the master, the Mii, profile, SupplyInfo, friend and Wbt mechanisms as described
  ([Findings 12 to 17](#12-the-course-chosen-by-the-master)), and that the receiving branch of the block transfer is
  turned off in `eur2`.
- The page flow of the scene sequence file ([Finding 18](#18-where-the-network-steps-sit-in-the-scene-sequence)), and
  the steps of the network tasks and pages ([Findings 19 to 23](#19-entering-the-menus-menunetworkselectmenutask)).

### Likely

- That spectators are the consoles that joined during a race: the menus treat them so, but the lists are filled by the
  connection layer, which was not read ([Finding 22](#22-spectators)).
- The keep-alive kicks ([Finding 7](#7-keep-alive)): the arguments of `kickStation` were not checked.
- That SupplyInfo exists to fill gaps (late joiners, missed packets, players who left): it follows from the flow, not
  from a comment or a name ([Finding 15](#15-supplyinfo)).
- That a community match lasts four races ([Finding 21](#21-the-online-pages)): from the test "race number above 2".
- That `setRaceRank` from the previous ranks sets the starting grid ([Finding 23](#23-the-last-step-menunetworkapplytask)).
- That `Next01` of the settings pages is the way out when the course setting is "random" or "in order"
  ([Finding 24](#24-the-two-ways-out-of-the-settings-pages)): the course setting's values come from the page's texts,
  and the button id of the start message was not followed.
- Which pages are chosen on every console and which only on the master's (overview): not mapped page by page.

### Guesses

- The meaning of the OK button's two animations on the master's VS settings page (usable or greyed out).
- That the cases 3, 4 and 6 of `updateBattleMode_` are leftovers, since no writer was found.

## Open questions

- Which page of the shared pattern is chosen by every console and which only by the master (the flag byte of each page);
  what the seventeen state numbers correspond to, page by page. An emulator run with two consoles would settle both.
- Which setting each of the five rows of `NetworkSelectMenuSendFormat::m_vs_settings` holds.
- `NetworkSelectMenuSendFormat::m_mode` 4 in local play (the dialog of `MenuMulti_Mode`), and the meaning of bits 0, 1
  and 3 of `m_flags`.
- `NetworkSystemSendFormat::m_spare_u16`, `m_spare_u32` and `NetworkSystemInfo::m_skip_game_frame`: no writer found.
  Bits 1 and 2 of `NetworkSystemSendFormat::m_flags`.
- `NetworkMiiManager::m_last_received` is never written, so a missed Mii packet decodes from zeros; possibly a leftover.
- `NetworkPlayerDataManager::m_is_player_info_updated` has no reader found.
- In SupplyInfo `fixManage`, the entry of a player reported by another console is linked to the profile of the
  reporting console, not of the player; this looks wrong for a player whose console left, unless something corrects it
  later. The global counter that `fixManage` advances has another user that was not checked.
- Who sets the send interval of the local broadcast policy (`setSendInterval`), and the second sending mode of
  `NetworkEngine::sendUnreliableCore` (every 11th or 6th call). The `u32` at the start of the packet header and its byte
  at 0x1A are always 0 in `constructSendHeader_`; whether the receiving side ever reads them was not checked.
- The unnamed engine flags: those that guard sending and receiving (the session-active test and the further guard of
  `calcAfterStructure`), the byte that the select menu task and the online pages set, and the flag that
  `MenuWiFi_Waiting` waits for. Their offsets are in the commands of the review document.
- How `BasePage::loadNextCourse` picks the course on the master (cup order, random), and the jump of a client in step 1
  of `MenuNetworkCourseDecideTask`.
- `MenuJoinSelectTask` (joining a friend from the Mario Kart Channel), the two further checks of
  `MenuCommunity_Top` for spectators, and the matching manager's community flag.
- The meaning of the errors 5 and 0xC that the menus give the error handler.
- The writers of `NetworkEngine::m_dlp_child_aid_bits` and of the byte after it, and of the byte of
  `RaceSys::CourseArchiveManager` that starts the block transfer.
- `WbtProtocol::isFinished`'s second condition (every remaining child still at -1).
- The timed path of the local handshake for Download Play (states 1 and 2 of `calcShakeHands_`).
- Which error result sets which of bits 1 and 2 of `NetworkFriendsManager::m_approach_flags`, and what value 2 of
  `MenuData::FriendApproach::m_register_state` means.

## Additions from the research on race multiplayer

Found by the research on race multiplayer (pass 1, 2026-11-16, pending verification) about the SystemInfo classes of
this topic. Left here to be folded into this document and its patch by the next pass; the race research's patch does
not change these members. Addresses are those of `eur2`.

### The two "spare" members are the race start countdown

- `NetworkSystemInfo::m_spare_u16` (0xEE), sent as `NetworkSystemSendFormat::m_spare_u16` (0x08), has writers:
  `Net::NetworkSystemInfoManager::Sync::ready` (0x002aa574) sets it to 3000 (`mk7 read 0x002aa664 1` = 0xbb8), and
  `Sync::stateSync` (0x002aa668) lowers it every frame by 16, to the smallest of the peers' sent values minus their
  latency (`NetworkSystemInfo::m_latencies`) and minus the ms since their packet arrived (`m_last_accepted_ticks`).
  When it reaches 0 the race starts. It is the start countdown, in ms; the race research proposes the name
  `m_start_countdown` in both classes.
- `NetworkSystemInfo::m_spare_u32` (0xF0) is set to 0 by `Sync::ready`, which also clears `m_spare_u32` (+0x0C) and
  `m_game_frames_at_receive` of every `m_last_received` entry. No other writer was found; its meaning stays open.
- `NetworkSystemInfo` + 0x104 (a byte between `m_last_received` and `m_racer_station_id_num`) is set to 1 by
  `Sync::ready` and to 0 by `Sync::stateSync` when the countdown ends: the countdown runs (proposed name
  `m_is_start_counting`).
- `Sync` (size 0x58) keeps the `NetworkSystemInfo *` at +0x54 (`Sync::Sync(NetworkSystemInfo*)`, 0x002aa878,
  `param_1[0x15] = param_2`); `ready` and `stateSync` write through it.
- So the open question "`m_spare_u16`, `m_spare_u32` ... no writer found" is answered for `m_spare_u16` and partly for
  `m_spare_u32`.

### NetworkSystemSendFormat bytes 0x1C to 0x1D

- A `u16` at 0x1C of the format, not listed in this topic's glossary, is written by
  `Net::NetworkSystemInfoManager::FrameSync::calc` (0x002aaea0): `*(short *)(*param_1 + 0x2c) = (short)param_1[3]`,
  where `*param_1` is the `NetworkSystemInfo` (0x10 + 0x1C). It is a frame counter of the running race; a spectator
  compares it with the racers' values and skips frames to catch up. The race research proposes the name
  `m_sync_frame`.

### The objects after NetworkSystemInfo

- `NetworkSystemInfoManager::NetworkSystemInfoManager` stores the `Sync *` at `NetworkSystemInfo` + 0x208 (manager +
  0x248) and a 0x14-byte `FrameSync *` at + 0x20C (manager + 0x24C); the byte at manager + 0x250 is set by
  `ModeManagerRace::initWait` after `Sync::ready` and cleared by `startWatchFrameSync`. These are named by the race
  research's patch (`m_sync`, `m_frame_sync`, `m_is_sync_started`), as this topic left them to it.
- `Sync` contains a `NetworkStateManager<Sync>` at +0x04 (its `m_ready_aid_bits` at Sync + 0x09, `m_requested_state`
  at + 0x14): one of the uses of `NetworkStateCalc` that this topic attributes to `NetworkSystemInfoManager`.
