"""Minimal client of the GDB remote serial protocol, for Azahar's gdb stub.

Used: registers (g/G/p/P), memory (m/M), breakpoints and watchpoints
(Z0..Z4 / z0..z4), continue (c), single step (s), interrupt (0x03) and
detach (D). Azahar handles the packets on the emulation thread, in step with
the emulated cores, from a reader thread that wakes it up (azahar PR 2631):
a packet is answered in well under a millisecond, a single step in 10-25 ms.

Behaviour of Azahar's stub that this client works around:
- An execute breakpoint at the current pc fires again before its
  instruction runs: `c` or `s` from a stop on it stop at once, at the same
  pc. `step` and `cont` therefore remove it, step one instruction and put it
  back.
- Watchpoints report some instructions late (JIT).

Other behaviour worth knowing:
- `D` (detach) and a closed connection both let the game run again
  (azahar PR 2633); the game cannot be left halted without a client.
- Every memory write (`M`) clears the JIT cache of all cores, so patched
  code runs at once.

Registers of the ARM11 as the stub numbers them: r0..r15 = 0..15, cpsr = 25.
"""
import socket
import struct
import time

from .memio import MemoryAccessError, MemoryIO

PC = 15
LR = 14
SP = 13
CPSR = 25

BP_SOFTWARE = 0   # execute breakpoint (exact)
BP_HARDWARE = 1
WP_WRITE = 2      # watchpoints overshoot: the JIT reports them some instructions late
WP_READ = 3
WP_ACCESS = 4

CHUNK = 0x1000    # bytes per m/M packet: the stub takes payloads up to 9996 characters


class GdbError(MemoryAccessError):
    pass


class StopReply:
    """A parsed stop packet (T05..., S05, W.., X..)."""

    def __init__(self, packet: str):
        self.packet = packet
        self.kind = packet[:1]
        self.signal = int(packet[1:3], 16) if self.kind in "TSX" and len(packet) >= 3 else None
        self.registers: dict[int, int] = {}
        self.info: dict[str, str] = {}
        if self.kind == "T":
            for item in packet[3:].split(";"):
                if ":" not in item:
                    continue
                key, value = item.split(":", 1)
                try:
                    reg = int(key, 16)
                    self.registers[reg] = struct.unpack("<I", bytes.fromhex(value[:8].ljust(8, "0")))[0]
                except ValueError:
                    self.info[key] = value

    @property
    def watch_address(self):
        for key in ("watch", "rwatch", "awatch"):
            if key in self.info:
                return int(self.info[key], 16)
        return None

    @property
    def pc(self):
        return self.registers.get(PC)

    def __repr__(self):
        return f"StopReply({self.packet!r})"


class GdbClient(MemoryIO):
    def __init__(self, host="127.0.0.1", port=4000, timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""
        self.running = False
        self.no_ack = False
        self.breakpoints: set[tuple[int, int, int]] = set()
        self._pending: StopReply | None = None

    # ---- framing -------------------------------------------------------
    @staticmethod
    def _checksum(data: bytes) -> bytes:
        return b"%02x" % (sum(data) & 0xFF)

    def _send_raw(self, data: bytes):
        self.sock.sendall(data)

    def _recv_more(self, timeout):
        # The stub sends its ack and its reply in two small writes; without an
        # immediate ACK from us, Nagle holds the reply back ~40 ms.
        if hasattr(socket, "TCP_QUICKACK"):
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        self.sock.settimeout(timeout)
        chunk = self.sock.recv(65536)
        if not chunk:
            raise GdbError("connection closed by the stub")
        self.buf += chunk

    def _read_packet(self, timeout=10.0) -> str:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            # drop acks and junk before '$'
            start = self.buf.find(b"$")
            if start < 0:
                self.buf = b""
            else:
                self.buf = self.buf[start:]
                end = self.buf.find(b"#")
                if end >= 0 and len(self.buf) >= end + 3:
                    payload = self.buf[1:end]
                    self.buf = self.buf[end + 3:]
                    if not self.no_ack:
                        self._send_raw(b"+")
                    return self._unescape(payload).decode("latin-1")
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining == 0.0:
                raise TimeoutError("no packet from the stub")
            try:
                self._recv_more(remaining)
            except socket.timeout as exc:
                raise TimeoutError("no packet from the stub") from exc

    @staticmethod
    def _unescape(payload: bytes) -> bytes:
        out = bytearray()
        i = 0
        while i < len(payload):
            c = payload[i]
            if c == 0x7D and i + 1 < len(payload):
                out.append(payload[i + 1] ^ 0x20)
                i += 2
            elif c == 0x2A and out and i + 1 < len(payload):  # run-length encoding
                out.extend(out[-1:] * (payload[i + 1] - 29))
                i += 2
            else:
                out.append(c)
                i += 1
        return bytes(out)

    def send(self, payload: str):
        data = payload.encode("latin-1")
        self._send_raw(b"$" + data + b"#" + self._checksum(data))

    def request(self, payload: str, timeout=10.0) -> str:
        if self.running:
            raise GdbError("target is running; stop it first")
        self.send(payload)
        return self._read_packet(timeout)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    # ---- session -------------------------------------------------------
    def handshake(self) -> str:
        """qSupported, and the reason the target is stopped now (`?`)."""
        self.request("qSupported:multiprocess-;swbreak+;hwbreak+")
        return self.request("?")

    def interrupt(self, timeout=10.0) -> StopReply:
        self._send_raw(b"\x03")
        reply = StopReply(self._read_packet(timeout))
        self.running = False
        return reply

    def cont(self):
        """Resume the target. When it is stopped on one of our execute
        breakpoints, that instruction is stepped first; if the step stops
        somewhere else (a watchpoint, an exception), that stop is kept for the
        next `wait`."""
        if self._at_breakpoint():
            stop = self.step()
            if stop.kind != "T" or stop.signal != 5 or "watch" in stop.packet:
                self._pending = stop
                return
        self.send("c")
        self.running = True

    def wait(self, timeout=None) -> StopReply:
        """Wait for the target to stop (after `cont`)."""
        if self._pending is not None:
            reply, self._pending = self._pending, None
            self.running = False
            return reply
        reply = StopReply(self._read_packet(timeout))
        self.running = False
        return reply

    def step(self, timeout=10.0) -> StopReply:
        """Execute exactly one instruction of the current thread (the other
        threads run meanwhile) and stop again; an execute breakpoint at the pc
        is lifted for that instruction."""
        if self.running:
            raise GdbError("target is running; stop it first")
        pc = self._at_breakpoint()
        if pc is not None:
            self.remove_break(pc)
        try:
            self.send("s")
            return StopReply(self._read_packet(timeout))
        finally:
            if pc is not None:
                self.insert_break(pc)

    def _at_breakpoint(self) -> int | None:
        """The pc, when one of our execute breakpoints is on it."""
        if not any(kind == BP_SOFTWARE for kind, _, _ in self.breakpoints):
            return None
        pc = self.read_register(PC)
        return pc if (BP_SOFTWARE, pc, 4) in self.breakpoints else None

    def poll(self, timeout=0.0):
        """A stop reply if one is pending, else None (target keeps running)."""
        try:
            return self.wait(timeout if timeout > 0 else 0.001)
        except TimeoutError:
            return None

    def detach(self):
        """Remove our breakpoints and detach: the game runs again."""
        if self.running:
            self.interrupt()
        for kind, addr, size in list(self.breakpoints):
            try:
                self.remove_break(addr, kind, size)
            except GdbError:
                pass
        try:
            self.request("D", timeout=2.0)
        except (OSError, TimeoutError, GdbError):
            pass            # closing the socket resumes the game as well
        self.close()

    # ---- registers -----------------------------------------------------
    def read_registers(self) -> list[int]:
        data = bytes.fromhex(self.request("g"))
        return list(struct.unpack("<%dI" % (len(data) // 4), data[: len(data) // 4 * 4]))

    def read_register(self, reg: int) -> int:
        reply = self.request("p%x" % reg)
        if reply.startswith("E") and len(reply) == 3:
            raise GdbError(f"p{reg:x}: {reply}")
        return struct.unpack("<I", bytes.fromhex(reply[:8]))[0]

    def write_register(self, reg: int, value: int):
        reply = self.request("P%x=%s" % (reg, struct.pack("<I", value & 0xFFFFFFFF).hex()))
        if reply != "OK":
            raise GdbError(f"P{reg:x}: {reply}")

    # ---- memory --------------------------------------------------------
    def read(self, addr: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            n = min(size, CHUNK)
            reply = self.request("m%x,%x" % (addr, n))
            if reply.startswith("E") and len(reply) == 3:
                raise GdbError(f"read {addr:#x}+{n:#x}: {reply}")
            chunk = bytes.fromhex(reply)
            if not chunk:
                raise GdbError(f"read {addr:#x}: empty reply")
            out += chunk
            addr += len(chunk)
            size -= len(chunk)
        return bytes(out)

    def write(self, addr: int, data: bytes):
        for off in range(0, len(data), CHUNK):
            chunk = data[off:off + CHUNK]
            reply = self.request("M%x,%x:%s" % (addr + off, len(chunk), chunk.hex()))
            if reply != "OK":
                raise GdbError(f"write {addr + off:#x}: {reply}")

    # ---- breakpoints ---------------------------------------------------
    def insert_break(self, addr: int, kind: int = BP_SOFTWARE, size: int = 4):
        reply = self.request("Z%d,%x,%x" % (kind, addr, size))
        if reply != "OK":
            raise GdbError(f"Z{kind} {addr:#x}: {reply!r}")
        self.breakpoints.add((kind, addr, size))

    def remove_break(self, addr: int, kind: int = BP_SOFTWARE, size: int = 4):
        reply = self.request("z%d,%x,%x" % (kind, addr, size))
        self.breakpoints.discard((kind, addr, size))
        if reply != "OK":
            raise GdbError(f"z{kind} {addr:#x}: {reply!r}")

    def run_to(self, addr: int, timeout=None) -> StopReply:
        """Continue until `addr` executes (temporary breakpoint). Other
        breakpoints that are set may stop earlier; the reply says where."""
        temp = (BP_SOFTWARE, addr, 4) not in self.breakpoints
        if temp:
            self.insert_break(addr)
        try:
            self.cont()
            return self.wait(timeout)
        finally:
            if self.running:
                self.interrupt()
            if temp:
                self.remove_break(addr)
