"""Small ARM hooks patched into the running game (eur2).

Stopping on a breakpoint every frame is too slow, so per-frame work runs
inside the game instead: two instructions of the game are replaced by
branches to code assembled with devkitARM and written into the code pages
that `mk7 emu start` maps after the game's .bss (codepages.py). The code is
written through Azahar's RPC server (rpc.py), which writes in step with the
emulator and invalidates the JIT cache of the range, so patched code runs at
once; at boot, before the game runs, it is written through the gdb stub that
holds the CPU (`install_at_boot`). The host then talks to that code through
a small control block at the start of the pages, read and written live
through the RPC server while the game runs: no halting is needed.

Hooks:
- frame: replaces the first instruction of `sead::ControllerMgr::calc`
  (0x0030B4E8, `push {r4, r5, r6, lr}`), which the sead task tree runs once
  per frame in every scene, before the controllers are read and before the
  game logic of the frame. (`System::RootScene::sceneCalc` is not called
  during races.) It counts frames, runs a pending function call on the game
  thread, and freezes the game (a loop of 1 ms `svcSleepThread`) while the
  frame counter is at or past `freeze_at`.
- pad: replaces `mov r2, r9` at 0x003087DC in `sead::Controller::calc`,
  right after `calcImpl_` read the HID state (r4 = controller). It ORs
  `pad_or` into and clears `pad_clear` from `mPadHold` (+0x110), and can force
  the left stick (+0x11C, +0x120), before the trigger/release masks are derived.
  `Session.press` uses it (`Hooks.set_pad`, `set_stick`) for the screens
  that read the pad instead of page buttons: the course intro, the race
  results, the winning run, the trophy and the ending.

The hooks' code starts with `kernel_set_state` (`svc 0x7C; bx lr`), a
function the host calls on the game thread: Azahar's svcKernelSetState
takes state 0x20000 (KERNEL_STATE_CITRA_EMULATION_SPEED) as a temporary
speed limit in percent of the frame limiter (0: unthrottled, 0xFFFF: back to
the user's setting); Azahar resets it whenever a game boots
(`Hooks.set_speed`).
"""
import struct
import time

from . import codepages
from .codepages import assemble_source
from .memio import MemoryIO

CODE, CODE_END = codepages.HOOKS_CODE
CTRL, CTRL_END = codepages.HOOKS_CTRL   # control block
MAGIC = 0x4B37484B         # "KH7K"
VERSION = 4

FRAME_SITE, FRAME_ORIG = 0x0030B4E8, 0xE92D4070   # push {r4, r5, r6, lr}
PAD_SITE, PAD_ORIG = 0x003087DC, 0xE1A02009       # mov r2, r9

KERNEL_SET_STATE = CODE     # kernel_set_state, the first code of the hooks
KERNEL_STATE_EMULATION_SPEED = 0x20000   # Azahar: svcKernelSetState(0x20000, percent); 0 unthrottled
SPEED_DEFAULT = 0xFFFF      # ends the override: the frame limit set in Azahar applies again

# control block layout
C_MAGIC, C_VERSION = 0x00, 0x04
C_FRAME = 0x08          # u32 frames counted by the frame hook
C_FREEZE_AT = 0x0C      # u32 freeze while frame >= freeze_at (0 = never)
C_FROZEN = 0x10         # u32 1 while the game thread waits in the freeze loop
C_PAD_OR = 0x14         # u32 buttons forced on
C_PAD_CLEAR = 0x18      # u32 buttons forced off
C_STICK_ON = 0x1C       # u32 force the left stick
C_STICK = 0x20          # f32 x, f32 y
C_CALL = 0x28           # u32 function to call on the game thread (cleared when done)
C_ARGS = 0x2C           # u32 r0..r3
C_RESULT = 0x3C         # u32 r0 after the call
C_CALLS = 0x40          # u32 calls done

# sead::Controller button bits (mPadHold). UI::tstDemoButton tests 0x801 (A, Start), UI::tstNextButton 0x681B.
PAD_A = 1 << 0
PAD_B = 1 << 1
PAD_START = 1 << 11
PAD_L = 1 << 13
PAD_R = 1 << 14
PAD_UP = 1 << 16
PAD_DOWN = 1 << 17
PAD_LEFT = 1 << 18
PAD_RIGHT = 1 << 19

SOURCE = r"""
    .arm
    .syntax unified
    .equ CTRL, {CTRL:#x}
    .equ FRAME_RET, {FRAME_RET:#x}
    .equ PAD_RET, {PAD_RET:#x}
    .global kernel_set_state, frame_hook, pad_hook
    .text
kernel_set_state:
    svc     0x7C
    bx      lr

frame_hook:
    push    {{r0-r3, r12, lr}}
    ldr     r2, =CTRL
    ldr     r0, [r2, #{C_FRAME}]
    add     r0, r0, #1
    str     r0, [r2, #{C_FRAME}]
1:  ldr     r12, [r2, #{C_CALL}]
    cmp     r12, #0
    beq     2f
    push    {{r2, r3}}
    ldr     r0, [r2, #{C_ARGS}]
    ldr     r1, [r2, #{C_ARGS} + 4]
    ldr     r3, [r2, #{C_ARGS} + 12]
    ldr     r2, [r2, #{C_ARGS} + 8]
    blx     r12
    pop     {{r2, r3}}
    str     r0, [r2, #{C_RESULT}]
    ldr     r0, [r2, #{C_CALLS}]
    add     r0, r0, #1
    str     r0, [r2, #{C_CALLS}]
    mov     r0, #0
    str     r0, [r2, #{C_CALL}]
2:  ldr     r1, [r2, #{C_FREEZE_AT}]
    cmp     r1, #0
    beq     3f
    ldr     r0, [r2, #{C_FRAME}]
    cmp     r0, r1
    blo     3f
    mov     r0, #1
    str     r0, [r2, #{C_FROZEN}]
    ldr     r0, =1000000
    mov     r1, #0
    svc     0x0A
    ldr     r2, =CTRL
    b       1b
3:  mov     r0, #0
    str     r0, [r2, #{C_FROZEN}]
    pop     {{r0-r3, r12, lr}}
    push    {{r4, r5, r6, lr}}
    b       FRAME_RET

pad_hook:
    ldr     r1, =CTRL
    ldr     r0, [r4, #0x110]
    ldr     r2, [r1, #{C_PAD_OR}]
    orr     r0, r0, r2
    ldr     r2, [r1, #{C_PAD_CLEAR}]
    bic     r0, r0, r2
    str     r0, [r4, #0x110]
    ldr     r2, [r1, #{C_STICK_ON}]
    cmp     r2, #0
    ldrne   r2, [r1, #{C_STICK}]
    strne   r2, [r4, #0x11C]
    ldrne   r2, [r1, #{C_STICK} + 4]
    strne   r2, [r4, #0x120]
    mov     r2, r9
    b       PAD_RET
    .ltorg
"""


def _branch(site: int, target: int) -> int:
    return 0xEA000000 | (((target - (site + 8)) >> 2) & 0xFFFFFF)


def assemble() -> tuple[bytes, dict[str, int]]:
    """Machine code of the hooks and the addresses of their entry points."""
    src = SOURCE.format(CTRL=CTRL, FRAME_RET=FRAME_SITE + 4, PAD_RET=PAD_SITE + 4,
                        **{k: v for k, v in globals().items() if k.startswith("C_")})
    code, entries = assemble_source(src, CODE, ("frame_hook", "kernel_set_state", "pad_hook"))
    if entries.get("kernel_set_state") != KERNEL_SET_STATE:
        raise SystemExit("kernel_set_state is not at the start of the hooks' code")
    codepages.check_fits(codepages.HOOKS_CODE, code, "the hooks' code")
    return code, entries


def install_at_boot(g, freeze=True):
    """For a game that has not run yet (the stub holds the CPU at its first
    instruction, see azahar.start): install the hooks through `g` and make the
    game freeze at the start of its first frame, before the boot task runs
    (freeze=False: let it run)."""
    h = Hooks(g)
    h.install(force=True)
    if freeze:
        h.freeze_at(1)


class Hooks:
    """Install, query and drive the hooks.

    `mem` reaches the memory live (an RpcClient): the game must not be halted
    by gdb while frames are stepped or functions called. At boot it is the
    GdbClient that holds the CPU (`install_at_boot`)."""

    def __init__(self, mem: MemoryIO):
        self.mem = mem

    # ---- install --------------------------------------------------------
    def installed(self) -> bool:
        return (self.mem.u32(CTRL + C_MAGIC) == MAGIC and self.mem.u32(CTRL + C_VERSION) == VERSION
                and self.mem.u32(FRAME_SITE) != FRAME_ORIG)

    def install(self, force=False) -> bool:
        """Returns False when they were already installed."""
        if self.installed() and not force:
            return False
        code, entries = assemble()
        ctrl = bytearray(CTRL_END - CTRL)
        struct.pack_into("<II", ctrl, 0, MAGIC, VERSION)
        self.mem.write(CODE, code)
        self.mem.write(CTRL, bytes(ctrl))
        if self.mem.u32(CTRL + C_MAGIC) != MAGIC:
            # RPC drops writes to unmapped memory and reads it as zeros
            raise SystemExit(f"the code pages at {codepages.BASE:#x} are not mapped: start the game with "
                             "`mk7 emu start`, which maps them before the game runs")
        self.mem.w32(PAD_SITE, _branch(PAD_SITE, entries["pad_hook"]))
        self.mem.w32(FRAME_SITE, _branch(FRAME_SITE, entries["frame_hook"]))
        return True

    def uninstall(self):
        """Restore the two patched instructions (the code pages keep the code, unused)."""
        self.mem.w32(CTRL + C_FREEZE_AT, 0)
        self.mem.w32(CTRL + C_PAD_OR, 0)
        self.mem.w32(CTRL + C_PAD_CLEAR, 0)
        self.mem.w32(CTRL + C_STICK_ON, 0)
        self.mem.w32(FRAME_SITE, FRAME_ORIG)
        self.mem.w32(PAD_SITE, PAD_ORIG)
        self.mem.w32(CTRL + C_MAGIC, 0)

    # ---- control block ----------------------------------------------------
    def state(self) -> dict:
        raw = self.mem.read(CTRL, 0x44)
        v = lambda off: struct.unpack_from("<I", raw, off)[0]
        return {"frame": v(C_FRAME), "freeze_at": v(C_FREEZE_AT), "frozen": bool(v(C_FROZEN)),
                "pad_or": v(C_PAD_OR), "pad_clear": v(C_PAD_CLEAR), "stick_on": bool(v(C_STICK_ON)),
                "stick": struct.unpack_from("<2f", raw, C_STICK), "call": v(C_CALL),
                "result": v(C_RESULT), "calls": v(C_CALLS)}

    def frame(self) -> int:
        return self.mem.u32(CTRL + C_FRAME)

    def set_pad(self, pad_or=0, pad_clear=0):
        self.mem.write(CTRL + C_PAD_OR, struct.pack("<II", pad_or, pad_clear))

    def set_stick(self, xy=None):
        if xy is None:
            self.mem.w32(CTRL + C_STICK_ON, 0)
        else:
            self.mem.write(CTRL + C_STICK, struct.pack("<2f", *xy))
            self.mem.w32(CTRL + C_STICK_ON, 1)

    def set_speed(self, percent: int | None = 0):
        """Azahar's speed limit for this run, set by the game itself
        (svcKernelSetState 0x20000 on the game thread): `percent` of the
        normal speed, 0 for unthrottled (as fast as the host can emulate),
        None to go back to the frame limit set in Azahar. Lasts until the
        game boots again."""
        value = SPEED_DEFAULT if percent is None else percent
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"speed {percent} out of range")
        self.call(KERNEL_SET_STATE, KERNEL_STATE_EMULATION_SPEED, value)

    def freeze_at(self, frame: int):
        self.mem.w32(CTRL + C_FREEZE_AT, frame)

    # ---- running ------------------------------------------------------------
    def poll(self, predicate, timeout=60.0, interval=0.004):
        """Check predicate(self) every `interval` seconds, while the game runs,
        until it is true. False after `timeout` seconds."""
        deadline = time.monotonic() + timeout
        while not predicate(self):
            if time.monotonic() > deadline:
                return False
            time.sleep(interval)
        return True

    def wait_frozen(self, frame: int | None = None, timeout=60.0) -> bool:
        def ok(h):
            st = h.state()
            return st["frozen"] and (frame is None or st["frame"] >= frame)
        return self.poll(ok, timeout)

    def step(self, frames=1, timeout=60.0) -> int:
        """From a frozen game: run exactly `frames` frames and freeze again.
        Returns the new frame number."""
        target = self.frame() + frames
        self.freeze_at(target)
        if not self.wait_frozen(target, timeout):
            raise TimeoutError(f"game did not reach frame {target}")
        return self.frame()

    def freeze(self, timeout=60.0) -> int:
        """Freeze at the start of the next frame."""
        self.freeze_at(self.frame() + 1)
        if not self.wait_frozen(None, timeout):
            raise TimeoutError("game did not freeze")
        return self.frame()

    def unfreeze(self):
        self.freeze_at(0)

    def call(self, func: int, *args: int, timeout=30.0) -> int:
        """Call func(r0..r3) on the game thread at the start of a frame (or
        right away when frozen). Returns r0."""
        regs = list(args) + [0] * (4 - len(args))
        self.mem.write(CTRL + C_ARGS, struct.pack("<4I", *[r & 0xFFFFFFFF for r in regs]))
        self.mem.w32(CTRL + C_CALL, func)
        if not self.poll(lambda h: h.mem.u32(CTRL + C_CALL) == 0, timeout, 0.001):
            self.mem.w32(CTRL + C_CALL, 0)
            raise TimeoutError(f"call to {func:#x} did not run")
        return self.mem.u32(CTRL + C_RESULT)
