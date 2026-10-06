"""Client of Azahar's RPC server: live memory reads and writes, screenshots and
performance figures.

The server (`src/core/rpc/` in Azahar, demo client
`dist/scripting/AzaharRPC.py`) listens on UDP port 45987 when
`enable_rpc_server=true` is set in Azahar's qt-config.ini; the setting takes
effect when a game boots. A request is a header of four u32 (version 2, id,
type, data size) and at most 32 KiB of data; the reply repeats the header.
Requests: read memory (address, size), write memory (address, size, bytes),
list processes, get or select the process that reads and writes go to, take
a screenshot and read it back in chunks, performance statistics.

What it means for the tools (azahar PR 2631, measured on Azahar d8b2ad0):
- Every request except reading back a screenshot runs on the emulation
  thread, between CPU slices (Azahar's default build, ENABLE_SCRIPTING_SYNC),
  so reads and writes are in step with the emulated CPU and GPU: any address,
  VRAM included, is safe. A request takes about 0.2 ms, a 1 MB read 10 ms, and
  the game does not have to be halted; while a request runs, emulation waits.
- Writes invalidate the JIT cache of the range on every core: code written
  through RPC runs at once.
- Reads and writes still work while gdb halts the game.
- Reads of unmapped memory return zeros (Azahar logs an error); writes outside
  the process image and the heaps are ignored. Neither is reported.
- A screenshot is the next frame Azahar renders, both screens as laid out in
  its window, whether the window is visible or not.
- Azahar logs two lines per request at the Info level (`RPC_Server`), so long
  polling makes its log grow; `log_filter=*:Info RPC_Server:Warning` in
  qt-config.ini silences them.
"""
import socket
import struct

from .memio import MemoryAccessError, MemoryIO

RPC_PORT = 45987
VERSION = 2
MAX_DATA = 32 * 1024
READ_MEMORY, WRITE_MEMORY, PROCESS_LIST, SET_GET_PROCESS = 1, 2, 3, 4
TAKE_SCREENSHOT, READ_SCREENSHOT, GET_PERF_STATS = 5, 6, 7
SCREENSHOT_SECONDARY_WINDOW, SCREENSHOT_RAW_RGB = 1, 2
SCREENSHOT_RESULTS = {1: "unsupported by the renderer", 2: "busy (another screenshot is being taken)",
                      3: "timeout (no frame rendered within 10 s)", 4: "PNG encoding failed",
                      5: "invalid argument"}
PERF_STATS_FIELDS = ("system_fps", "game_fps", "time_vblank_interval", "time_hle_svc", "time_hle_ipc",
                     "time_gpu", "time_swap", "time_remaining", "emulation_speed", "artic_transmitted",
                     "artic_events")


class RpcError(MemoryAccessError):
    pass


class RpcClient(MemoryIO):
    def __init__(self, host="127.0.0.1", port=RPC_PORT, title_id: int | None = None, timeout=1.0):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for option in (socket.SO_SNDBUF, socket.SO_RCVBUF):     # room for a full 32 KiB packet
            if self.sock.getsockopt(socket.SOL_SOCKET, option) < 2 * (16 + MAX_DATA):
                self.sock.setsockopt(socket.SOL_SOCKET, option, 2 * (16 + MAX_DATA))
        self.timeout = timeout
        self.next_id = 1
        self.pid = self.select_process(title_id) if title_id is not None else None

    def close(self):
        self.sock.close()

    def _request(self, kind: int, data: bytes, retries=3, timeout=None) -> bytes:
        self.sock.settimeout(timeout or self.timeout)
        for _ in range(retries):
            rid = self.next_id
            self.next_id = (self.next_id + 1) & 0xFFFFFFFF
            self.sock.sendto(struct.pack("<4I", VERSION, rid, kind, len(data)) + data, self.addr)
            try:
                while True:         # drop late replies to earlier requests
                    reply = self.sock.recv(16 + MAX_DATA)
                    version, reply_id, reply_kind, size = struct.unpack_from("<4I", reply)
                    if reply_id == rid and reply_kind == kind and size == len(reply) - 16:
                        return reply[16:]
            except TimeoutError:
                continue
            except ConnectionRefusedError:
                break
        raise RpcError(f"no answer from Azahar's RPC server on UDP port {self.addr[1]} "
                       "(enable_rpc_server=true in qt-config.ini, effective from the next boot)")

    # ---- processes ---------------------------------------------------------
    def processes(self) -> dict[int, tuple[int, str]]:
        """process id -> (title id, name)."""
        out, start = {}, 0
        while True:
            reply = self._request(PROCESS_LIST, struct.pack("<II", start, 0x7FFFFFFF))
            count = struct.unpack_from("<I", reply)[0] if reply else 0
            if not count:
                return out
            for i in range(count):
                pid, tid, name = struct.unpack_from("<IQ8s", reply, 4 + 0x14 * i)
                out[pid] = (tid, name.rstrip(b"\0").decode("ascii", "replace"))
            start += count

    def select_process(self, title_id: int) -> int:
        """Direct reads and writes to the process of this title (the server's
        default is the process that happens to run)."""
        for pid, (tid, _) in self.processes().items():
            if tid == title_id:
                self._request(SET_GET_PROCESS, struct.pack("<II", 1, pid))
                return pid
        raise RpcError(f"no process of title {title_id:016x} is running")

    # ---- memory ----------------------------------------------------------------
    def read(self, addr: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            n = min(size, MAX_DATA)
            chunk = self._request(READ_MEMORY, struct.pack("<II", addr, n))
            if len(chunk) != n:
                raise RpcError(f"read {addr:#x}+{n:#x}: {len(chunk)} bytes returned")
            out += chunk
            addr += n
            size -= n
        return bytes(out)

    def write(self, addr: int, data: bytes):
        for off in range(0, len(data), MAX_DATA - 8):
            chunk = data[off:off + MAX_DATA - 8]
            self._request(WRITE_MEMORY, struct.pack("<II", addr + off, len(chunk)) + chunk)

    # ---- screen and performance ------------------------------------------------
    def screenshot(self, scale=0, raw=False, secondary=False) -> tuple[int, int, bytes]:
        """The next frame Azahar renders: (width, height, PNG bytes), or raw
        RGB888 pixels with raw=True (no PNG encoding in Azahar, faster). The
        layout is that of the window (both screens); scale 0 is the internal
        resolution. Not resent: a lost reply would leave the server busy."""
        flags = (SCREENSHOT_RAW_RGB if raw else 0) | (SCREENSHOT_SECONDARY_WINDOW if secondary else 0)
        reply = self._request(TAKE_SCREENSHOT, struct.pack("<II", scale, flags), retries=1, timeout=15.0)
        if len(reply) < 16:
            raise RpcError("screenshot: empty reply")
        result, width, height, size = struct.unpack_from("<4I", reply)
        if result:
            raise RpcError(f"screenshot: {SCREENSHOT_RESULTS.get(result, result)}")
        data = bytearray()
        while len(data) < size:
            chunk = self._request(READ_SCREENSHOT, struct.pack("<II", len(data), min(size - len(data), MAX_DATA)))
            if not chunk:
                raise RpcError(f"screenshot: read at {len(data):#x} of {size:#x} returned nothing")
            data += chunk
        return width, height, bytes(data)

    def perf_stats(self, reset=False) -> dict | None:
        """Azahar's performance figures (PERF_STATS_FIELDS; times in seconds):
        by default those the frontend last computed (the Qt status bar updates
        them every few seconds); reset=True computes them since the previous
        reset and starts a new interval. None when there are none yet."""
        reply = self._request(GET_PERF_STATS, struct.pack("<II", 1 if reset else 0, 0))
        if len(reply) < 0x54:
            return None
        return dict(zip(PERF_STATS_FIELDS, struct.unpack_from("<10dI", reply)))
