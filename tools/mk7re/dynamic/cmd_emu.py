"""`mk7 emu`: drive the game running in Azahar (see docs/tooling/EMULATOR.md).

This file has the commands every topic uses (emulator, time, sequence,
memory); cmd_emu_menu.py and cmd_emu_race.py add those of the menus and of
races.

Every command reaches the game through Azahar's RPC server (memory, code
patches, screenshots, performance figures; the gdb stub only for `read
--gdb` and the patches at boot), installs the hooks when needed, does its
work and disconnects. The game keeps the state the command left: frozen
at a frame boundary (`freeze`, `step`, `wait`, `click`, `complete`) or
running (`run`).
"""
import struct
import time
from pathlib import Path

from .. import paths
from . import azahar


def _int(text: str) -> int:
    return int(text, 0)


def _session():
    from .game import Session
    from .rpc import RpcError
    try:
        return Session(port=azahar.gdb_port())
    except RpcError as e:
        raise SystemExit(f"{e}; is Azahar running (`mk7 emu start`)?")
    except OSError as e:
        raise SystemExit(f"cannot connect to the gdb stub on port {azahar.gdb_port()} ({e}); "
                         "is Azahar running (`mk7 emu start`)?")


def _gdb():
    """A GdbClient alone (no hooks). The game is halted until `detach`."""
    from .gdbrsp import GdbClient
    try:
        g = GdbClient(port=azahar.gdb_port())
        g.handshake()
        return g
    except OSError as e:
        raise SystemExit(f"cannot connect to the gdb stub on port {azahar.gdb_port()} ({e}); "
                         "is Azahar running (`mk7 emu start`)?")


class _Connected:
    """`with _Connected() as s:` a Session that leaves the game frozen or
    running as it is."""

    def __enter__(self):
        self.s = _session()
        return self.s

    def __exit__(self, *exc):
        self.s.close(unfreeze=False)


def _print_tree(tree):
    for depth, info in tree:
        extra = f" ({info['class']})" if info["class"] else ""
        print(f"{'  ' * depth}{info['name']}{extra}  {info['type']}  {info['state']}  "
              f"enter={info.get('enter')} return={info.get('return')}  @{info['addr']:#x}")


# ---- emulator ------------------------------------------------------------
def cmd_start(args):
    from .game import TITLE_ID
    from .hooks import Hooks, install_at_boot
    from .rpc import RpcClient
    pid = azahar.running_pid()
    if pid:
        print(f"Azahar is already running, pid {pid}; the game was not restarted")
        return
    speed = _speed_arg(args)

    def at_first_instruction(g):
        from .codepages import map_at_boot
        map_at_boot(g)      # first: the hooks and vs.py put their code there
        if not args.save:
            from .save import write_nosave
            write_nosave(g)
        if args.unlock:
            from .menu import write_unlock
            write_unlock(g)
        if args.vs:
            from .vs import write_vs
            write_vs(g)
        if not args.run or speed is not None:
            install_at_boot(g, freeze=not args.run)

    pid = azahar.start(on_halt=at_first_instruction)
    print(f"Azahar running, pid {pid}, gdb stub on port {azahar.gdb_port()}")
    print(f"console output: {paths.rel(azahar.CONSOLE_FILE)}")
    if args.unlock:
        print("everything unlocked until the game restarts (patched before the game ran)")
    if args.vs:
        print("VS mode: the single-player menu offers Grand Prix and VS; time trials and battles are off")
    if not args.save:
        print("saving disabled: the game writes no files in this run (`--save` to allow it)")
    if args.run and speed is None:
        return
    mem = RpcClient(title_id=TITLE_ID)
    try:
        hooks = Hooks(mem)
        if args.run:
            if not hooks.poll(lambda h: h.frame() >= 1, timeout=60):
                raise SystemExit("the game did not reach its first frame")
        elif not hooks.wait_frozen(1, timeout=60):
            raise SystemExit("the game did not reach its first frame")
        if speed is not None:
            hooks.set_speed(speed)
    finally:
        mem.close()
    print(_speed_text(speed))
    if not args.run:
        print("game frozen at frame 1 (boot logo, before the menu scene is built)")


def _speed_arg(args) -> int | None:
    """The speed `start` and `speed` ask for: a percent, 0 unthrottled, None Azahar's own frame limit."""
    if args.speed in ("default", "azahar"):
        return None
    if args.speed in ("unlimited", "max"):
        return 0
    try:
        return int(args.speed)
    except ValueError:
        raise SystemExit(f"speed is a percent, 0 / unlimited, or default, not {args.speed!r}")


def _speed_text(speed: int | None) -> str:
    if speed is None:
        return "speed: Azahar's frame limit"
    return "speed: unthrottled (as fast as the host emulates)" if speed == 0 else f"speed: {speed}%"


def cmd_speed(args):
    speed = _speed_arg(args)
    with _Connected() as s:
        s.hooks.set_speed(speed)
    print(_speed_text(speed))


def cmd_stop(args):
    print("stopped" if azahar.stop() else "Azahar is not running (started by `mk7 emu start`)")


def cmd_status(args):
    pid = azahar.running_pid()
    print(f"Azahar: {'pid ' + str(pid) if pid else 'not started by mk7 emu'}")
    with _Connected() as s:
        st = s.hooks.state()
        print(f"frame {st['frame']}  {'frozen' if st['frozen'] else 'running'}")
        if not st["frozen"]:
            _print_fps(s.mem.perf_stats())
        print(f"scene id {s.game.scene_id()}")
        from .save import saving_disabled
        print("saving disabled (no file writes)" if saving_disabled(s.mem) else "saving ENABLED: the game writes its files")
        from .menu import Menu
        from .vs import vs_on
        if vs_on(s.mem):
            print("VS mode: single-player VS instead of time trials and battles")
        from .driver import player_mode
        mode = player_mode(s)
        if mode != "normal":
            print(f"player: {mode} (`player normal` to give the kart back to the pad)")
        for info in s.game.running_sections():
            if info["name"] not in ("Page_Bg", "Page_Timer", "Page_UpBarControl", "Page_CommonSystemDialog",
                                    "Page_Fader"):
                print(f"  {info['type']} {info['name']} ({info['class']})")


def _rpc():
    from .game import TITLE_ID
    from .rpc import RpcClient, RpcError
    try:
        return RpcClient(title_id=TITLE_ID)
    except RpcError as e:
        raise SystemExit(f"{e}; is Azahar running (`mk7 emu start`)?")


def _print_fps(stats):
    if stats is None:
        print("no performance figures yet")
        return
    print(f"{stats['game_fps']:.1f} FPS (game), {stats['system_fps']:.1f} FPS (system), "
          f"speed {stats['emulation_speed'] * 100:.0f}%")


def cmd_screenshot(args):
    from .rpc import RpcError
    out = Path(args.path) if args.path else paths.LOCAL_DIR / "azahar" / time.strftime("shot-%Y%m%d-%H%M%S.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.window:
        azahar.window_screenshot(out)
    else:
        try:
            azahar.screenshot(out, args.scale)
        except RpcError as e:
            raise SystemExit(f"{e}; is Azahar running (`mk7 emu start`)?")
    print(paths.rel(out))


def cmd_stats(args):
    mem = _rpc()
    try:
        if args.interval > 0:
            mem.perf_stats(reset=True)
            time.sleep(args.interval)
            stats = mem.perf_stats(reset=True)
        else:
            stats = mem.perf_stats()
    finally:
        mem.close()
    _print_fps(stats)
    if stats:
        print("  ms per frame: " + ", ".join(f"{k.removeprefix('time_')} {stats[k] * 1000:.2f}" for k in
                                             ("time_vblank_interval", "time_hle_svc", "time_hle_ipc", "time_gpu",
                                              "time_swap", "time_remaining")))


# ---- time ------------------------------------------------------------------
def cmd_freeze(args):
    with _Connected() as s:
        print(f"frozen at frame {s.freeze()}")


def cmd_run(args):
    with _Connected() as s:
        s.hooks.unfreeze()
        print("running")


def cmd_step(args):
    with _Connected() as s:
        print(f"frame {s.step(args.frames)}")


# ---- sequence ------------------------------------------------------------------
def cmd_pages(args):
    with _Connected() as s:
        _print_tree(s.game.sequence_tree(only_active=not args.all))


def cmd_wait(args):
    with _Connected() as s:
        if not s.wait_section(args.section, args.state, args.timeout):
            raise SystemExit(f"{args.section} did not reach {args.state} within {args.timeout} s")
        print(f"{args.section} {args.state}, frozen at frame {s.frame}")


# ---- memory ------------------------------------------------------------------
def cmd_read(args):
    if args.gdb:
        g = _gdb()
        try:
            data = g.read(args.address, args.size)
        finally:
            g.detach()
    else:
        mem = _rpc()
        try:
            data = mem.read(args.address, args.size)
        finally:
            mem.close()
    if args.format == "hex":
        for off in range(0, len(data), 16):
            row = data[off:off + 16]
            print(f"{args.address + off:08x}  {row.hex(' ')}")
        return
    code = {"u32": "I", "s32": "i", "f32": "f", "u16": "H", "s16": "h", "u8": "B"}[args.format]
    size = struct.calcsize(code)
    for i in range(len(data) // size):
        v = struct.unpack_from("<" + code, data, i * size)[0]
        print(f"{args.address + i * size:08x}  {v:#x}" if code in "IHB" else f"{args.address + i * size:08x}  {v}")


def cmd_write(args):
    data = bytes.fromhex(args.hex)
    mem = _rpc()
    try:
        mem.write(args.address, data)
    finally:
        mem.close()
    print(f"wrote {len(data)} bytes at {args.address:#x}")


def cmd_call(args):
    with _Connected() as s:
        print(f"r0 = {s.call(args.function, *args.args):#x}")


def register(sub):
    p = sub.add_parser("emu", help="drive the game running in Azahar through its RPC server and gdb stub (docs/tooling/EMULATOR.md)")
    actions = p.add_subparsers(dest="action", required=True, metavar="action")

    def add(name, func, help):
        q = actions.add_parser(name, help=help)
        q.set_defaults(func=func)
        return q

    q = add("start", cmd_start, "launch Azahar with the game, frozen at its first frame")
    q.add_argument("--unlock", action="store_true", help="patch every cup, character and kart part to count as "
                   "unlocked before the game runs (as `unlock`; the save is not changed)")
    q.add_argument("--vs", action="store_true", help="single-player VS for this run: the single-player menu's "
                   "Time Trials button leads to VS, time trials and battles are off (vs.py)")
    q.add_argument("--run", action="store_true", help="let the game boot freely instead (the hooks are installed "
                   "by the next command)")
    q.add_argument("--save", action="store_true", help="let the game write its save and other files (by default "
                   "they are patched to do nothing, so every run starts from the same save)")
    q.add_argument("--speed", default="unlimited", help="emulation speed for this run, set by the game through "
                   "svcKernelSetState: unlimited (default, as fast as the host emulates), a percent, or default "
                   "(Azahar's own frame limit)")
    add("stop", cmd_stop, "close the Azahar started by `start`")
    q = add("speed", cmd_speed, "change the emulation speed of this run (as `start --speed`)")
    q.add_argument("speed", help="unlimited (0), a percent (100 = real time), or default (Azahar's frame limit)")
    add("status", cmd_status, "frame, frozen or running, scene and running pages")
    q = add("screenshot", cmd_screenshot, "save the next frame Azahar renders (both screens) as a PNG")
    q.add_argument("path", nargs="?", help="PNG to write (default: mk7-llm-research/local/azahar/shot-*.png)")
    q.add_argument("--scale", type=int, default=0, help="resolution scale 1..10 (default: Azahar's internal "
                   "resolution)")
    q.add_argument("--window", action="store_true", help="grab the Azahar window from the screen instead (it "
                   "must be visible and not covered)")
    q = add("stats", cmd_stats, "Azahar's frame rate and emulation speed")
    q.add_argument("--interval", type=float, default=1.0, help="measure over this many seconds (default 1; 0: "
                   "the figures Azahar's status bar last showed)")

    add("freeze", cmd_freeze, "park the game thread at the start of the next frame")
    add("run", cmd_run, "let the game run freely")
    q = add("step", cmd_step, "run exactly N frames, then freeze")
    q.add_argument("frames", type=int, nargs="?", default=1)

    q = add("pages", cmd_pages, "the sequence tree: sections, classes, states and codes")
    q.add_argument("--all", action="store_true", help="also list free (unused) sections")
    q = add("wait", cmd_wait, "run until a section reaches a state, then freeze")
    q.add_argument("section")
    q.add_argument("--state", default="running")
    q.add_argument("--timeout", type=float, default=120.0, help="seconds (default 120)")

    q = add("read", cmd_read, "read memory of the game (any address, live through the RPC server)")
    q.add_argument("address", type=_int)
    q.add_argument("size", type=_int, nargs="?", default=0x40)
    q.add_argument("--gdb", action="store_true", help="read through the gdb stub instead (halts the game "
                   "briefly): reports unmapped memory as an error, where RPC returns zeros")
    q.add_argument("-f", "--format", choices=["hex", "u32", "s32", "f32", "u16", "s16", "u8"], default="hex")
    q = add("write", cmd_write, "write bytes (hex) to the game's memory; code patches take effect at once")
    q.add_argument("address", type=_int)
    q.add_argument("hex")
    q = add("call", cmd_call, "call a game function with up to 4 arguments on the game thread")
    q.add_argument("function", type=_int)
    q.add_argument("args", type=_int, nargs="*")

    from . import cmd_emu_menu, cmd_emu_race     # here: they import this module
    cmd_emu_menu.register(add)
    cmd_emu_race.register(add)
