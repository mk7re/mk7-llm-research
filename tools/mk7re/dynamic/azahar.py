"""Launching Azahar (the 3DS emulator) with the game, and taking screenshots.

Paths, all overridable with environment variables:

| Variable | Default |
| --- | --- |
| `AZAHAR_APPIMAGE` | `<repo>/local/azahar/azahar.AppImage` |
| `AZAHAR_USER_DIR` | `~/.local/share/azahar-emu` |
| `MK7_TITLE` | the boot content of the installed EUR title (`0004000000030700`) under the user dir's sdmc |
| `AZAHAR_GDB_PORT` | `4000` |

The emulator's console output goes to `mk7-llm-research/local/azahar/console.txt`;
Azahar's own log stays in `<user dir>/log/azahar_log.txt`.
"""
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from .. import paths

STATE_DIR = paths.LOCAL_DIR / "azahar"
PID_FILE = STATE_DIR / "azahar.pid"
CONSOLE_FILE = STATE_DIR / "console.txt"
TITLE_ID_HIGH, TITLE_ID_LOW = "00040000", "00030700"     # Mario Kart 7 EUR


def appimage() -> Path:
    return Path(os.environ.get("AZAHAR_APPIMAGE", paths.REPO / "local" / "azahar" / "azahar.AppImage"))


def user_dir() -> Path:
    return Path(os.environ.get("AZAHAR_USER_DIR", Path.home() / ".local" / "share" / "azahar-emu"))


def gdb_port() -> int:
    return int(os.environ.get("AZAHAR_GDB_PORT", "4000"))


def title_path() -> Path:
    if "MK7_TITLE" in os.environ:
        return Path(os.environ["MK7_TITLE"])
    pattern = f"sdmc/Nintendo 3DS/*/*/title/{TITLE_ID_HIGH}/{TITLE_ID_LOW}/content/00000000.app"
    found = sorted(user_dir().glob(pattern))
    if not found:
        raise SystemExit(f"Mario Kart 7 is not installed under {user_dir()} ({pattern}); set MK7_TITLE")
    return found[0]


def running_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def start(timeout=60.0, on_halt=None) -> int:
    """Start Azahar with the game and the gdb stub, and let the game boot (the
    stub holds the CPU at the first instruction until a client continues it).
    `on_halt(client)` runs before that, with the connected GdbClient, while
    no instruction of the game has run yet. Returns the pid."""
    pid = running_pid()
    if pid:
        return pid
    exe = appimage()
    if not exe.exists():
        raise SystemExit(f"{exe} not found; set AZAHAR_APPIMAGE")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONSOLE_FILE, "w") as out:
        proc = subprocess.Popen([str(exe), "-g", str(gdb_port()), str(title_path())], stdout=out,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    PID_FILE.write_text(str(proc.pid))
    from .gdbrsp import GdbClient
    deadline = time.monotonic() + timeout
    while True:
        if proc.poll() is not None:
            raise SystemExit(f"Azahar exited with code {proc.returncode}; see {paths.rel(CONSOLE_FILE)}")
        client = None
        try:
            # the stub may accept and reset connections while the emulator starts up
            client = GdbClient("127.0.0.1", gdb_port())
            client.handshake()
            break
        except (OSError, TimeoutError):
            if client:
                client.close()
            if time.monotonic() > deadline:
                raise SystemExit("the gdb stub did not answer")
            time.sleep(0.5)
    if on_halt:
        on_halt(client)
    client.detach()
    return proc.pid


def stop(timeout=10.0) -> bool:
    pid = running_pid()
    if not pid:
        return False
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.2)
    else:
        os.killpg(pid, signal.SIGKILL)
    PID_FILE.unlink(missing_ok=True)
    return True


def window_geometry() -> tuple[int, int, int, int]:
    """(x, y, width, height) of the main Azahar window showing the game."""
    tree = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True, check=True).stdout
    for line in tree.splitlines():
        m = re.search(r'^\s*(0x[0-9a-f]+) "(Azahar[^"]*\| MARIO KART 7)":', line)
        if m:
            info = subprocess.run(["xwininfo", "-id", m.group(1)], capture_output=True, text=True,
                                  check=True).stdout
            get = lambda key: int(re.search(key + r":\s+(-?\d+)", info).group(1))
            return (get("Absolute upper-left X"), get("Absolute upper-left Y"), get("Width"), get("Height"))
    raise SystemExit("no Azahar window showing Mario Kart 7 was found")


def screenshot(path: Path, scale=0) -> Path:
    """Save the next frame Azahar renders as a PNG, through the RPC server:
    both screens as laid out in the window (400x480 at the native
    resolution; scale 0 is Azahar's internal resolution), whether the window
    is visible or not."""
    from .game import TITLE_ID
    from .rpc import RpcClient
    mem = RpcClient(title_id=TITLE_ID)
    try:
        _, _, png = mem.screenshot(scale)
    finally:
        mem.close()
    path.write_bytes(png)
    return path


def window_screenshot(path: Path) -> Path:
    """Grab the Azahar window as it is on screen (other windows covering it
    are captured too: there is no compositor to read it from)."""
    from PIL import ImageGrab
    x, y, w, h = window_geometry()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
    return path
