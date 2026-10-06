# Hooks, code pages and boot patches

The code the tooling adds to the running game: the hooks that count, freeze and step frames, the code pages that
hold that code, how `start` freezes the game at boot, and the patches that keep it from saving. Part of
[EMULATOR.md](../EMULATOR.md). Read it when changing `hooks.py`, `codepages.py` or `save.py`, adding code to the
game, or when a command fails around boot or freezing.

## Contents

- [Hooks](#hooks): control block, frame hook, pad hook
- [Code pages](#code-pages): where the added code lives, slot layout, how `start` maps them
- [Starting frozen at boot](#starting-frozen-at-boot): what `start` does before the game's first frame, and why
  `unlock` must come before the menu scene builds its pages
- [Saving is disabled](#saving-is-disabled): what `save.py` patches and what it does not cover
- [Measurements](#measurements): boot frames, freeze and step times, the loader's block and device memory, the save
  check

## Hooks

Code: `hooks.py`. Stopping on a breakpoint every frame is too slow, so per-frame work runs inside the game. The code
is written through RPC (through the stub at boot) into the [code pages](#code-pages); the host then drives it through
the control block, live, with RPC:

- **Control block** at the start of the code pages, 0x006BF000; the hooks' code follows at 0x006BF100.
- **Frame hook** on the first instruction of `sead::ControllerMgr::calc` (0x0030B4E8). It runs once per frame in every
  scene; checked against `GameScene::calcEngines`, it increments exactly once per call. It counts frames, runs a
  pending `call(func, r0..r3)` on the game thread, and freezes the game thread (1 ms `svcSleepThread` loop) while
  `frame >= freeze_at`.
- **Pad hook** at 0x003087DC in `sead::Controller::calc`: it can force buttons and the circle pad. It is installed with
  the frame hook. Menus are driven through their buttons; `Session.press` uses the pad hook for the screens that read
  the pad instead ([After a race](races.md#after-a-race)) and for the pages' pad input (kart reels, settings, teams).

The hooks stay installed until the game restarts (`Hooks.uninstall` restores both instructions). Steps of many frames
take less time unthrottled ([Emulation speed](azahar.md#emulation-speed)).

## Code pages

The code the tooling adds to the game (the hooks, the patches of `start --vs`, the simulated player) lives in pages of
its own, mapped right after the game's `.bss` before the game runs (`codepages.py`); no code of the game is
overwritten to hold it. `nninitRegion`, the first call of `__ctr_start`, zeroes the `.bss` from 0x00676FA0 to
0x006BE508, and nothing is ever mapped at 0x006BF000, the next page. Layout of its 0x20000 bytes, one slot per piece
of code or data (each module checks that its code fits):

| Address | Size | What |
| --- | --- | --- |
| 0x006BF000 | 0x100 | the hooks' control block (`hooks.py`) |
| 0x006BF100 | 0x700 | the hooks' code, `kernel_set_state` first |
| 0x006BF800 | 0x800 | `vs.py` `SOURCE`: race and flow hooks, the BSEQ table |
| 0x006C0000 | 0x800 | `vs.py` `SOURCE_MENU`: the menu hooks |
| 0x006C0800 | 0x800 | `driver.py` control block |
| 0x006C1000 | 0x6000 | `driver.py`: the input hook and `driver.c` |
| 0x006C7000 | 0x10000 | `driver.c` working memory (route search, route list) |
| 0x006D7000 | 0x8000 | free |

`start` maps them first, while the stub holds the CPU at the game's first instruction (0x00100000): it writes a small
loader over the start of `__ctr_start`, lets the main thread run it to its last instruction (a breakpoint there),
then writes the game's code and registers back as they were, so the game starts from its first instruction as if
nothing had run. The loader calls Azahar's HLE kernel (`src/core/hle/kernel/svc.cpp`):

1. `svcCreateMemoryBlock` with address 0: the kernel allocates the block from the linear memory of the BASE region (of
   the application's region if the exheader asked for shared device memory; [Measurements](#device-memory)). Its handle
   stays open for the whole run, which keeps the memory allocated.
2. `svcMapMemoryBlock` maps it for a moment at 0x0FF00000, in the heap range: Azahar maps memory blocks nowhere else.
3. `svcMapProcessMemoryEx` (0xA0, a custom call of Luma3DS that Azahar implements) maps the same memory a second time
   at 0x006BF000, read/write/execute; Azahar checks no range for its destination.
4. `svcUnmapMemoryBlock` removes the mapping at 0x0FF00000.

`svcControlMemory` cannot be used for this: Azahar ignores its region bits (it logs "ControlMemory with specified
region not supported") and commits the memory from the application's region, charged to the game's Commit limit.
The SDK sizes the game's device (linear) memory as the application memory minus the Commit already used
(`sub_001011b4`, called by `nnMain`), so the game would get less of it ([Measurements](#device-memory)). What the game
sees of the loader is one handle more in its handle table, one memory block more in its resource limit's count, and
the mapping. RPC writes and reads work there as anywhere in the process image (it is in its address range).

A game started otherwise than with `mk7 emu start` (by hand in Azahar) has no code pages: RPC drops writes to unmapped
memory, so `Hooks.install` checks its control block after writing it and stops with an error.

## Starting frozen at boot

The stub holds the CPU at the game's first instruction (0x00100000) until a client continues it, and the code is
already loaded then. `start` maps the [code pages](#code-pages) at that point, installs the hooks through the stub
and sets `freeze_at = 1` (`hooks.install_at_boot`, called by `azahar.start(on_halt=...)`), with `--unlock` also the
unlock patches (`menu.write_unlock`), then lets the CPU go: the game thread stops in the frame hook at the start of its
first frame, with only `Root`, `RootMain` and `RootExit` (`ready`) in the sequence tree and the boot logo on screen.
From there it steps frame by frame like any other scene.

The menu scene builds all its pages in one frame, and every cup page decides then which cups are locked (its
`initControl`, from `BasePage::onGenerateControl`, asks `IsOpen(EGrandPrixID)` for each cup through `sub_004d19d0`).
That frame moves between runs, so no fixed frame number is safe: `unlock` has to come before it, which `start --unlock`
guarantees ([Measurements](#boot-frames)).

## Saving is disabled

`mk7 emu start` patches the game at its first instruction so that it writes no files (`save.py`), unless `--save` is
given. The game's state in memory changes as usual (trophies, unlocks, records count until the game restarts); the
next boot starts from the same save again. `status` says whether the patches are in place.

- The save data (system data, ghosts) is written only by `System::SaveDataManager`'s thread, through
  `System::BackupManager::write` and `::move`; both return success at once.
- Everything else goes through the SDK's FS:USER IPC wrappers (found by the command header in their literal pool):
  File::Write, CreateFile, DeleteFile, RenameFile, CreateDirectory, FormatSaveData, CreateExtSaveData,
  DeleteExtSaveData return success without sending the request.
- Not covered: the game's StreetPass box, which the StreetPass service (cecd) keeps in the system's data
  (`nand/.../sysdata/00010026/00000000/CEC/00030600/`). The game updates it at boot and rebuilds it when the channel
  opens; faking those cecd writes left the box inconsistent and the channel showed "SD Card error.". The box holds
  only the outgoing message and its info, which the game rebuilds from its own state.
- Things the game shows once and then remembers in the save come back on every run: the "SpotPass will be
  activated" dialog, the present box of a newly unlocked character.

## Measurements

### Boot frames

Measured on 2026-10-03, stepping one frame at a time from frame 1:

| Frame | |
| --- | --- |
| 1 | scene 0 (root), boot logo |
| 2 | `BootTask` running |
| 19-24 | scene 2 (menu), `MenuScene` entering, no pages yet |
| next frame | the menu scene builds all its pages in one frame (about 1.8 s of real time) |
| about 40 frames later | `Page_Title` running |

The frame of the build moved between runs (19 to 25). In the same run, unlocking in the last frame before the build
opened the cups and unlocking in the first frame after it left them locked, twice each; `IsOpen(EGrandPrixID)` itself
returned 1 for every cup after a late unlock. Without a frozen start (`--run`), the title menu was already running 8 s
after `start`, so whether `unlock` came in time depended on how quickly it was run.

### Freeze, step and call times

Measured at 100 % speed (RPC, polling the control block every 4 ms): freezing takes 20-70 ms, a 1-frame step 17-37 ms,
a 30-frame step 0.52 s (the game's own time at 60 FPS), a game function call up to 19 ms (median 15).

### Device memory

With Azahar's New 3DS setting, the loader's block was at physical address 0x2E004000, inside the BASE region (the
last 0x2000000 bytes of the FCRAM).

Measured on 2026-10-05: device memory 0x3801000 bytes without the loader and with it, 0x37FD000 after a
`svcControlMemory` commit of 0x4000 bytes (region BASE asked for).

### The save check

Checked on 2026-10-03 by hashing every file of Azahar's `sdmc/` and `nand/` before and after a run with a won Grand
Prix, two battles, a time trial and two channel visits: only the three StreetPass box files changed.
