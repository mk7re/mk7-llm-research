"""The simulated player (eur2): the local player's kart driven by the tooling,
with inputs a human could give, computed inside the game every frame.

Where the inputs go in. A human kart's input takes its own path, apart
from the menus': `System::KDPadInputer::calcInput` (0x004419E4) clears the
pad's `KDPadDataOnFrame` and fills it from the console pad (inputButton:
game button bits through the table at 0x005ED2E0; inputStick: the stick in
steps 0..14, 7 the centre); `KDPad::calc` (0x004579CC) hands that data to
its `KDPadControllerCore` (+0x15C), whose `calcImpl_` (0x004503CC) turns it
back into a button mask (+0x110) and a stick (+0x11C, +0x120);
`Kart::VehicleControl::updateLocal` (0x002E4C54) reads those through
`m_controller_base` (+0xE4): A accelerates, B brakes, R hops, the stick
steers. The ghost recorder records the same data.

The hook replaces calcInput's last instruction, the tail call into
inputStick (`bx r1` at 0x00441A48), with a branch to `drive_input_hook`: it
calls inputStick, then `drive_frame` (driver.c) with the KDPadInputer.
While a mode is on and the race runs, drive_frame overwrites the frame's
data with its own buttons and stick. The menus read the console pad and the
UI pads (KDPadUIInputer), so they are not affected. In mirror mode the pad
gets a KDPadMirrorInputer, which only overrides inputStick (it flips the
stick); calcInput and so the hook run after it, so the driver's stick, worked
out in the course's own coordinates, reaches the kart unflipped.

Everything else happens in the game, in driver.c: the host only sets a mode
and a target and reads the status. Measured on 2026-10-05 (time trial,
Mario Circuit): the vehicle's `Rigid::m_kd_mtx` (+0x0) holds the columns
side, up, forward and position; the kart's velocity is
`VehicleMove::m_xyz_speed_vec` (+0xC60); stick +x turns right (toward
forward x up). A and B held together with the full stick turn a stopped kart
in place, about 2 degrees per frame, without moving it.

Modes (`DriveCtrl::mode`):
- goto: straight toward a point, braking to a stop within a radius, where it
  stays.
- route: along the CPUs' route to the route point nearest a target, then as
  goto. The route search (Dijkstra) runs in the game, from the route point
  nearest the kart, and again whenever the kart is re-routed (a fall,
  Lakitu, a Bullet Bill, the game's re-route rules). It goes both ways along
  the route unless `forward_only` (then only along the next links, as CPUs
  drive) and takes a mushroom shortcut only when there is no other way.
- race: along the route lap after lap, choosing at forks as CPUs do (never a
  mushroom shortcut when there is another branch, else at random); in a
  battle, wandering along the two-way paths. It holds across races until it
  is turned off: each countdown starts it over. goto and route end at the
  next countdown.

The route is the race's re-sampled one (`AIPathManager` + 0x28, a point
every 75 to 150 units, also built in time trials) or, in a battle, the KMP's
enemy points. What the driver takes from the CPUs
(the research on enemy AI behaviour and enemy points): "nearest point" searched as
`findNearEnemyPoint` (500 units horizontally and the point's max search Y
offset); reaching a point within 280 units (100 in battle, 140 after a point
with flag 0x04) or, in a race, beyond the plane that bisects the turn there;
re-routes after 450 frames without reaching a point, after 30 frames against
a wall, and when the target is steeply above or below after 20 frames while
airborne, gliding or after a point with flag 0x02 (the kart only moves to
the nearest point when it is on another path than its target); the back-up
(slow below 10 % of the top speed for 600 frames, a wall counting 3:
reverse 100 frames with the stick centred, 50 in battle, then back to the
route three points behind); drifts (started toward a corner point with
drift setting 0 or 3+ within 400 units, going straight at more than 60 % of
the top speed; ended where the route turns the other way or the corner is
over, on gliding, when badly out of line, or once the mini-turbo is charged
to red; drifting through a point with flag 0x01 or 0x04, or a sharp corner,
cuts toward the inside by `corner_shift` of the half-width); trick hops at
the game's trick chances (`calcSmallJumpTimingAI`) unless the target has
flag 0x08 or a sharp corner is close ahead, in battle only at points with
flag 0x80. The driver aims at the route point `lookahead` (+
`lookahead_speed` x speed) ahead along the route, half that after a point
with flag 0x04, since a kart driven with the stick cannot turn at once as the
AI does (`AI::setRotateRadAI`).

The driver is a tool to drive around with, so it drives for speed as a
player would, not with the limits that keep CPUs fair: it holds drifts to
the red mini-turbo (the AI lets the blue one go after 120 frames) and past
points with drift setting 1 or 2 (where the AI ends them), drifts again at
once after a charged drift while the corner goes on, steers the drift with
the stick (out to widen it, in to cut the corner and charge faster), and
skips tricks before sharp corners. Items, objects (train crossings, boards)
and other karts are left out.

In race mode the driver also takes the start boost as a player does: A held
from frame 124 of the countdown (241 frames; measured on Mario Circuit: from
frame 122-126 a full boost, 130-149 a smaller one, 120 or earlier a wheel
spin). The CPUs get theirs without input (`AIControlBase::setStartDashTypeToKart`).

While Lakitu has the kart (status bits jugem_recover 0x20,
jugem_recover_ai_oob 0x40 or hang 0x800000 of `VehicleMove::m_status_flags`,
+0xC30) or it is in Bullet Bill (0x400000: the game drives it), the driver
gives no input; afterwards it re-routes from where the kart is.

The code lives in the code pages (codepages.DRIVER_CODE, control block
DRIVER_CTRL, working memory DRIVER_RAM) and holds until the game restarts.
"""
import math
import struct
from pathlib import Path

from . import codepages
from .game import Session
from .hooks import _branch

CODE, CODE_END = codepages.DRIVER_CODE
CTRL, CTRL_END = codepages.DRIVER_CTRL
RAM, RAM_END = codepages.DRIVER_RAM
MAGIC = 0x56524437          # "7DRV"
VERSION = 18
C_SOURCE = Path(__file__).with_name("driver.c")

SITE, SITE_ORIG = 0x00441A48, 0xE12FFF11     # KDPadInputer::calcInput: bx r1 (tail call into inputStick)

MODES = {"off": 0, "goto": 1, "route": 2, "race": 3}
STATUSES = ["idle", "no race", "waiting for the race", "driving", "turning in place", "braking", "backing up",
            "reached", "ended (a new race began)", "Lakitu has the kart", "Bullet Bill", "drifting",
            "no way to the target", "too many route points", "no route"]
OPT_FORWARD_ONLY, OPT_NO_DRIFT, OPT_NO_TRICK = 0x1, 0x2, 0x4

# control block (struct DriveCtrl in driver.c)
C_MAGIC, C_VERSION, C_MODE, C_STATUS, C_TARGET, C_RADIUS, C_OPTIONS, C_GENERATION = \
    0x00, 0x04, 0x08, 0x0C, 0x10, 0x1C, 0x20, 0x24
REPORT = (0x28, "<II3f3fIf4I2I7I")   # frames .. plans
REPORT_NAMES = ("frames", "vehicle", "pos", "dist", "angle", "speed", "buttons", "stick", "accessor",
                "point_count", "route_count", "route_pos", "target_point", "aim_point", "reroutes", "backups",
                "drifts", "tricks", "advances", "lakitus", "plans")
C_TUNING = 0x100
TUNING = {"full_steer_angle": ("f", math.radians(25)), "turn_angle": ("f", math.radians(120)),
          "slow_speed": ("f", 0.5), "lookahead": ("f", 400.0), "lookahead_speed": ("f", 40.0),
          "lost_dist": ("f", 800.0), "corner_shift": ("f", 0.4), "drift_gain": ("f", 1.3),
          "slow_limit": ("I", 600), "reverse_frames": ("I", 100), "reroute_frames": ("I", 450),
          "wall_reroute_frames": ("I", 30), "drift_start_dist": ("f", 400.0), "corridor": ("f", 0.6),
          "start_frame": ("I", 124), "drift_behind": ("f", math.radians(50)), "brake_dist": ("f", 150.0),
          "brake_dist_speed": ("f", 30.0), "coast_turn": ("f", math.radians(45)), "coast_ratio": ("f", 0.7),
          "brake_turn": ("f", math.radians(90)), "brake_ratio": ("f", 0.5), "corridor_slack": ("f", 20.0),
          "kart_room": ("f", 2.0), "brake_angle": ("f", math.radians(55)),
          "precise_corridor": ("f", 0.3), "chain_rest": ("I", 3),
          "drift_room": ("f", 0.5),
          "drift_bend": ("f", math.radians(10)), "drift_bend_dist": ("f", 150.0)}

ENTRY = r"""
    .arm
    .syntax unified
    .section .text.entry, "ax"
    .global drive_input_hook
drive_input_hook:               @ instead of `bx r1` in KDPadInputer::calcInput: r0 = this, r1 = inputStick
    push    {r4, r5, r6, lr}
    mov     r4, r0
    blx     r1
    mov     r5, r0
    mov     r0, r4
    bl      drive_frame
    mov     r0, r5
    pop     {r4, r5, r6, pc}
"""


def build() -> tuple[bytes, int]:
    """The machine code of the driver and the address of its hook."""
    code, entries = codepages.compile_c(C_SOURCE, ENTRY, CODE, ("drive_input_hook", "drive_frame"),
                                        {"DRIVE_CTRL": CTRL, "DRIVE_RAM": RAM})
    codepages.check_fits(codepages.DRIVER_CODE, code, "the driver")
    return code, entries["drive_input_hook"]


class Driver:
    """Install and drive the simulated player through its control block,
    live through RPC."""

    def __init__(self, session: Session):
        self.s = session
        self.mem = session.mem

    def installed(self) -> bool:
        return (self.mem.u32(CTRL + C_MAGIC) == MAGIC and self.mem.u32(CTRL + C_VERSION) == VERSION
                and self.mem.u32(SITE) != SITE_ORIG)

    def install(self, force=False) -> bool:
        """Write the code, a fresh control block (mode off) and the hook.
        Returns False when it was already installed."""
        if self.installed() and not force:
            return False
        code, hook = build()
        self.mem.w32(SITE, SITE_ORIG)           # no frame runs half-written code
        ctrl = bytearray(CTRL_END - CTRL)
        struct.pack_into("<II", ctrl, C_MAGIC, MAGIC, VERSION)
        struct.pack_into("<" + "".join(f for f, _ in TUNING.values()), ctrl, C_TUNING,
                         *(v for _, v in TUNING.values()))
        self.mem.write(CODE, code)
        self.mem.write(CTRL, bytes(ctrl))
        if self.mem.u32(CTRL + C_MAGIC) != MAGIC:
            raise SystemExit(f"the code pages at {codepages.BASE:#x} are not mapped: start the game with "
                             "`mk7 emu start`, which maps them before the game runs")
        self.mem.w32(RAM_END - 4, 0x12345678)
        if self.mem.u32(RAM_END - 4) != 0x12345678:
            raise SystemExit(f"the driver's working memory at {RAM:#x} is not mapped: restart the game with "
                             "`mk7 emu start` (the code pages grew)")
        self.mem.w32(SITE, _branch(SITE, hook))
        return True

    def _set_mode(self, mode: str, xyz=(0.0, 0.0, 0.0), radius=150.0, options=0):
        self.install()
        self.mem.w32(CTRL + C_MODE, 0)
        self.mem.write(CTRL + C_TARGET, struct.pack("<4fI", *xyz, radius, options))
        self.mem.w32(CTRL + C_STATUS, 0)                     # until the next frame sets it
        self.mem.w32(CTRL + C_GENERATION, self.mem.u32(CTRL + C_GENERATION) + 1)
        self.mem.w32(CTRL + C_MODE, MODES[mode])

    def go_to(self, xyz, radius=150.0):
        """Drive straight to `xyz` (only x and z count) and stop within
        `radius` of it; the kart then stays there."""
        self._set_mode("goto", xyz, radius)

    def go_by_route(self, xyz, radius=150.0, forward_only=False, drift=True, trick=True):
        """Drive along the CPUs' route to the route point nearest `xyz`, then
        straight to `xyz`, stopping within `radius`. Both ways along the route
        unless `forward_only`."""
        options = (OPT_FORWARD_ONLY if forward_only else 0) | (0 if drift else OPT_NO_DRIFT) | \
                  (0 if trick else OPT_NO_TRICK)
        self._set_mode("route", xyz, radius, options)

    def race(self, drift=True, trick=True):
        """Drive the race along the route, lap after lap, from now on in every
        race until `off` or the game restarts."""
        self._set_mode("race", options=(0 if drift else OPT_NO_DRIFT) | (0 if trick else OPT_NO_TRICK))

    def off(self):
        """Give the kart back to the console pad."""
        if self.installed():
            self.mem.w32(CTRL + C_MODE, 0)

    def mode(self) -> str:
        if not self.installed():
            return "off"
        m = self.mem.u32(CTRL + C_MODE)
        return next((k for k, v in MODES.items() if v == m), str(m))

    def status(self) -> dict:
        if not self.installed():
            return {"installed": False, "mode": "off"}
        raw = self.mem.read(CTRL, C_TUNING)
        u = lambda off: struct.unpack_from("<I", raw, off)[0]
        st = u(C_STATUS)
        out = {"installed": True, "mode": self.mode(), "status": STATUSES[st] if st < len(STATUSES) else st,
               "target": struct.unpack_from("<3f", raw, C_TARGET), "radius": struct.unpack_from("<f", raw, C_RADIUS)[0],
               "options": u(C_OPTIONS)}
        values = list(struct.unpack_from(REPORT[1], raw, REPORT[0]))
        for name in REPORT_NAMES:
            if name == "pos":
                out[name], values = tuple(values[:3]), values[3:]
            else:
                out[name] = values.pop(0)
        out["angle"] = math.degrees(out["angle"])
        for name in ("target_point", "aim_point"):
            out[name] = struct.unpack("<i", struct.pack("<I", out[name]))[0]
        return out

    def reached(self) -> bool:
        return self.mem.u32(CTRL + C_STATUS) == STATUSES.index("reached")

    def ended(self) -> bool:
        """The mode stopped by itself: reached, no way, or a new race."""
        return self.mem.u32(CTRL + C_STATUS) in (STATUSES.index("reached"), STATUSES.index("no way to the target"),
                                                  STATUSES.index("ended (a new race began)"))


PLAYER_MODES = ("normal", "cpu", "simulated")


def set_player(session: Session, mode: str, menu=None):
    """Who drives the player's kart from the next race on, until the game
    restarts: `normal` the pad, `cpu` the game's AI (`Menu.cpu_player`: player
    type CPU), `simulated` this driver in race mode (player type Master)."""
    if mode not in PLAYER_MODES:
        raise ValueError(f"player mode {mode!r}: one of {', '.join(PLAYER_MODES)}")
    from .menu import Menu
    (menu or Menu(session)).cpu_player(mode == "cpu")
    d = Driver(session)
    if mode == "simulated":
        if d.mode() != "race":
            d.race()
    elif d.mode() == "race":
        d.off()


def player_mode(session: Session, menu=None) -> str:
    from .menu import Menu
    if (menu or Menu(session)).cpu_player_on():
        return "cpu"
    return "simulated" if Driver(session).mode() == "race" else "normal"
