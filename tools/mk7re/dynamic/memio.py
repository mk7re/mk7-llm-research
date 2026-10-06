"""Typed accessors shared by the two ways of reaching the game's memory:
`gdbrsp.GdbClient` (the gdb stub) and `rpc.RpcClient` (Azahar's RPC server).
A subclass provides `read(addr, size)` and `write(addr, data)`."""
import struct


class MemoryAccessError(Exception):
    pass


class MemoryIO:
    def read(self, addr: int, size: int) -> bytes:
        raise NotImplementedError

    def write(self, addr: int, data: bytes):
        raise NotImplementedError

    def u8(self, addr): return self.read(addr, 1)[0]
    def u16(self, addr): return struct.unpack("<H", self.read(addr, 2))[0]
    def u32(self, addr): return struct.unpack("<I", self.read(addr, 4))[0]
    def s8(self, addr): return struct.unpack("<b", self.read(addr, 1))[0]
    def s16(self, addr): return struct.unpack("<h", self.read(addr, 2))[0]
    def s32(self, addr): return struct.unpack("<i", self.read(addr, 4))[0]
    def f32(self, addr): return struct.unpack("<f", self.read(addr, 4))[0]
    def w8(self, addr, v): self.write(addr, struct.pack("<B", v & 0xFF))
    def w16(self, addr, v): self.write(addr, struct.pack("<H", v & 0xFFFF))
    def w32(self, addr, v): self.write(addr, struct.pack("<I", v & 0xFFFFFFFF))
    def wf32(self, addr, v): self.write(addr, struct.pack("<f", v))
