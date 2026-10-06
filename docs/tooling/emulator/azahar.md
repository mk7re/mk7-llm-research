# Azahar: configuration and behaviour

How the Azahar build used by `mk7 emu` behaves: its configuration, its RPC server and gdb stub, screenshots,
emulation speed and frame rate. Part of [EMULATOR.md](../EMULATOR.md).

## Contents

- [Configuration](#configuration): log filter, renderer, memory next to Ghidra
- [How the RPC server behaves](#how-the-rpc-server-behaves): protocol, timing, what is safe to read and write
- [How the gdb stub behaves](#how-the-gdb-stub-behaves): connection, breakpoints, steps, watchpoints
- [Screenshots](#screenshots): `screenshot` through RPC or from the window
- [Emulation speed](#emulation-speed): how the speed limit is set from the guest
- [Frame rate](#frame-rate): `stats` and `status`
- [Measurements](#measurements): log volume, renderer memory, RPC, gdb and screenshot times, emulation speed,
  frame rates

## Configuration

- **Log filter.** Azahar logs two lines per RPC request at the Info level, which fills its log quickly while a
  command polls. Its config therefore has `log_filter=*:Info RPC_Server:Warning`. Azahar must be closed while the
  config is edited: it writes its settings back.
- **Use the OpenGL renderer when there is no GPU** (`graphics_api=1` in Azahar's config, Azahar closed while it is
  edited). Without a GPU driver for Vulkan (a VM, for instance), Azahar renders through llvmpipe, Mesa's software
  driver, and Vulkan then keeps every pipeline it compiles in memory; its disk shader cache then holds all of them, and
  the next boot compiles them again at once. OpenGL on llvmpipe stays small and runs at full speed
  ([Measurements](#renderer-memory)). Azahar's log names the driver (`GL_RENDERER` or `VK_DEVICE`). A shader cache
  built under Vulkan can be deleted (`shaders/` in the user dir); it is not needed.
- **Mind the memory: Azahar and headless Ghidra together can exhaust it.** A headless Ghidra run (`mk7 decomp`,
  `mk7 ghidra`) adds a 2 GB Java heap (`MAXMEM_DEFAULT` in `analyzeHeadless`), the rest of the JVM and the native
  decompiler to a running Azahar. Where the two do not fit, nothing is killed for lack of memory: the kernel keeps
  evicting program files and reading them back, the disk runs at full read speed, and the whole system can hang until
  it is powered off. Decompile what a dynamic session needs before `mk7 emu start` or after `mk7 emu stop`, unless
  `free -h` shows enough memory available for both. If a command stalls while the emulator runs, look at the memory
  before running it again.

## How the RPC server behaves

Sources: `src/core/rpc/` of Azahar and its demo client `dist/scripting/AzaharRPC.py` (azahar PR 2631).

- UDP, one request per datagram: a header of four u32 (version 2, id, type, data size), then at most 32 KiB. Types:
  1 read (address, size), 2 write (address, size, bytes), 3 process list, 4 get/select the process, 5 take a
  screenshot, 6 read the screenshot back, 7 performance statistics. The server answers requests of any other version
  with an empty reply. `RpcClient` selects the game's process (title `0004000000030700`) when it connects; the
  server's default is whatever process runs.
- Every request except reading back a screenshot runs on the emulation thread, between CPU slices or while the frame
  limiter waits (`ENABLE_SCRIPTING_SYNC`, on in Azahar's default build). Reads and writes are therefore in step with
  the emulated CPU and GPU: any address is safe, VRAM included.
- The game keeps running, but emulation waits while a request runs, so long series of large reads slow the game down
  ([Measurements](#rpc-gdb-and-screenshot-times)).
- After a write the server invalidates the JIT cache of the range on every core, so code written through RPC runs at
  once ([Measurements](#rpc-gdb-and-screenshot-times)). The hooks, `unlock` and `write` go through RPC; the gdb
  stub is only needed for breakpoints, watchpoints, single steps and the patches at boot.
- Requests keep working while gdb halts the game.
- Reads of unmapped memory return zeros (and Azahar logs an error); writes outside the process image and the heaps are
  dropped. Neither is reported to the client, so `Game.is_ptr` checks pointers that may be garbage, and `read --gdb`
  is there to tell unmapped memory apart.
- The server starts with the game: changing `enable_rpc_server` takes effect at the next boot.

## How the gdb stub behaves

The stub is used for breakpoints, watchpoints and single steps, and for the patches written at boot.
`Session.gdb()` connects only for those and disconnects at once. Since azahar PR 2631 a reader thread receives the
packets and wakes the emulation thread, which answers them in step with the cores (PR 2633 added single stepping and
fixed protocol details).

- At boot the stub holds the CPU at the first instruction until a client continues it (`azahar.start` does this).
  For a few seconds after Azahar starts, the stub may refuse or reset connections; `start` and `Session.gdb()` retry.
- Connecting halts the game. `D` (detach) and a closed connection both let it run again: a client that is killed no
  longer leaves the game halted, and no command can leave it halted for the next one.
- A breakpoint that is hit every frame slows the game down a lot: each resume clears the JIT cache
  ([Measurements](#rpc-gdb-and-screenshot-times)).
- An execute breakpoint at the current pc fires again before its instruction runs: `c` or `s` from a stop on it stop
  at once at the same pc. `GdbClient.step` and `cont` lift the breakpoint for one `s` and put it back.
- `s` executes one instruction of the current thread; the other threads run meanwhile (no `Hc` selected).
- `interrupt` reports thread 1. `Hg<id>` selects another thread (`qXfer:threads:read` lists them).
- Memory writes (`M`) take effect in code at once: the stub clears the JIT cache of every core. Code the game writes
  itself would need `svcInvalidateEntireInstructionCache` (0x94) or `svcInvalidateInstructionCacheRange` (0x93), which
  Azahar implements; nothing here needs them.
- Watchpoints work but report late (JIT); the stop reply names the address (`watch:1f9588`,
  `StopReply.watch_address`). Execute breakpoints are exact.
- Memory packets carry up to 9996 characters; `GdbClient` reads and writes 4 KiB per packet.

## Screenshots

`mk7 emu screenshot` (`azahar.screenshot`, `RpcClient.screenshot`) asks the RPC server for the next frame Azahar
renders: both screens as laid out in the window, 400x480 at the native resolution (`--scale` 1..10, default Azahar's
internal resolution), whether the window is visible, covered or minimised. It works while the game is frozen by the
hooks and while gdb halts it, since Azahar keeps rendering frames; it fails after 10 s if no frame is rendered
(emulation paused), and the software renderer does not support it. Raw RGB (`raw=True`) is faster than a PNG
([Measurements](#rpc-gdb-and-screenshot-times)).

`screenshot --window` (`azahar.window_screenshot`) grabs the Azahar window from the screen instead, with `xwininfo` and
Pillow. Without a compositor, a window covering Azahar is captured too; a minimised window gives nothing useful, and a
screensaver or a locked screen is captured instead of the game.

## Emulation speed

Azahar's `svcKernelSetState` (SVC 0x7C) takes state `0x20000` (`KERNEL_STATE_CITRA_EMULATION_SPEED`) from the guest: a
temporary speed limit in percent, 0 for unthrottled, 0xFFFF to go back to the frame limit set in Azahar
(`src/core/hle/kernel/svc.cpp`; azahar PR 758 made it work). Azahar resets it whenever a game boots. The hooks' code
starts with `kernel_set_state` (`svc 0x7C; bx lr`, at 0x006BF100), and `Hooks.set_speed` calls it on the game thread.
`start` sets unthrottled once the game reaches frame 1 (`--speed`: a percent, or `default`); `speed` changes it at any
time.

Commands that wait for a state (`run_until`, `wait`) check it about every 0.1 s, so unthrottled they stop a few more
frames after the state is reached; commands that step a number of frames are exact at any speed.

## Frame rate

`mk7 emu stats` (`RpcClient.perf_stats`) reads Azahar's performance figures: game and system frame rate, emulation
speed, and the time per frame spent in the GPU, the HLE services and waiting. By default it measures over one second
(`reset=True` twice); `--interval 0` returns what Azahar's status bar last computed (it refreshes every few seconds).
`status` prints the last figures while the game runs. While the hooks freeze the game, the game frame rate is 0.

## Measurements

### Log volume

Each RPC request logged about 300 bytes at the Info level; waiting a minute for a page wrote 15 MB. The log filter
of [Configuration](#configuration) was set on 2026-10-03 because of it.

### Renderer memory

Measured with Vulkan on llvmpipe: Azahar grew from 0.9 GB at the title to 1.8 GB at the first race and 2.1 GB at the
second, and a session with eight courses ended at 11 GB; the next boot compiled the cached pipelines again, 10 GB
within 15 s of `start`. With OpenGL, also on llvmpipe, the same steps took 0.8, 1.0 and 1.1 GB, and eight courses
1.5 GB, at 60 FPS. A running Azahar was measured using 5-7 GB of RAM under Vulkan on llvmpipe.

### RPC, gdb and screenshot times

Measured on Azahar `d8b2ad0`:

- RPC: a request takes about 0.2 ms, a 32 KiB read the same, a 1 MB read 10 ms. All 6 MB of VRAM read 239 times in
  5 s while the game rendered, without trouble; reading it back to back for those 5 s let the game run about 180
  frames instead of 300. A function rewritten three times through RPC ran the new code at each call.
- gdb stub: a packet is answered in about 0.04 ms, connecting takes 1 ms, a single step (`s`) 10-25 ms. A stop on a
  breakpoint that is hit every frame costs about 0.2 s per frame.
- Screenshots: a PNG takes about 30 ms, raw RGB about 7 ms.

### Emulation speed

Measured on 2026-10-04 (OpenGL on llvmpipe): the title menu ran at 225 FPS (speed 377 %) unthrottled and 60 FPS with
the limit; a 150cc Grand Prix race of 1:49 took 57 s, a 3-minute battle 70 s.

### Frame rate while frozen

The system rate stayed at 60 FPS frozen on the title page, but frozen at frame 1 of the boot Azahar ran far faster
than real time (about 1800 FPS, speed 30x).
