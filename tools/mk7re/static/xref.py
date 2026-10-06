"""Cross references: who calls a function, who points at an address."""
import struct
from dataclasses import dataclass

from .image import Image


@dataclass(frozen=True)
class Ref:
    addr: int       # where the reference is
    kind: str       # "bl" | "b" | "adr" (add rX, pc, #n) | "literal" (pool word in .text) | "data"


def branch_index(img: Image) -> dict[int, list[tuple[int, bool]]]:
    """target -> [(source, is_link)] for every B/BL in .text."""
    def build():
        base, words, n = img.base, img.words, (img.text_end - img.base) // 4
        index: dict[int, list] = {}
        for i in range(n):
            w = words[i]
            if w & 0x0E000000 == 0x0A000000 and w >> 28 != 0xF:
                off = w & 0x00FFFFFF
                if off & 0x800000:
                    off -= 0x1000000
                index.setdefault(base + (i + 2 + off) * 4, []).append((base + i * 4, bool(w & 0x01000000)))
        return index
    return img.cached("branches", build)


def adr_target(addr: int, w: int) -> int | None:
    """Address formed by `add/sub rX, pc, #imm` (how armcc reaches strings in .text)."""
    if w & 0x0FFF0000 == 0x028F0000 or w & 0x0FFF0000 == 0x024F0000:
        rot = ((w >> 8) & 0xF) * 2
        imm = w & 0xFF
        imm = ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm
        return addr + 8 + (imm if w & 0x00800000 else -imm)
    return None


def adr_index(img: Image) -> dict[int, list[int]]:
    """target -> [source] for every pc-relative address computation in .text."""
    def build():
        base, words, n = img.base, img.words, (img.text_end - img.base) // 4
        index: dict[int, list] = {}
        for i in range(n):
            w = words[i]
            if w & 0x0F0F0000 == 0x020F0000:      # data-processing, immediate, Rn == pc
                t = adr_target(base + i * 4, w)
                if t is not None:
                    index.setdefault(t, []).append(base + i * 4)
        return index
    return img.cached("adr", build)


def find_refs(img: Image, addr: int, include_local_branches: bool = False) -> list[Ref]:
    refs = []
    if img.in_text(addr):
        start, end = img.function_bounds(addr)
        for src, link in branch_index(img).get(addr, []):
            # Plain B inside the same function is control flow, not a reference.
            if not link and start <= src < end and not include_local_branches:
                continue
            refs.append(Ref(src, "bl" if link else "b"))
    refs.extend(Ref(src, "adr") for src in adr_index(img).get(addr, []))
    needle = struct.pack("<I", addr)
    pos = img.data.find(needle)
    while pos != -1:
        if pos % 4 == 0:
            where = img.base + pos
            refs.append(Ref(where, "literal" if img.in_text(where) else "data"))
        pos = img.data.find(needle, pos + 1)
    return sorted(refs, key=lambda r: r.addr)


def vtable_at(img: Image, addr: int, limit: int = 400) -> list[int]:
    """Consecutive .text pointers starting at addr (a vtable's function slots)."""
    out = []
    a = addr
    while img.contains(a) and len(out) < limit:
        v = img.u32(a)
        if not img.in_text(v) or v & 3:
            break
        out.append(v)
        a += 4
    return out


def table_start(img: Image, addr: int) -> int:
    """Walk back from a slot to the first slot of the pointer table containing it."""
    a = addr & ~3
    while img.contains(a - 4) and not img.in_text(a - 4):
        v = img.u32(a - 4)
        if not img.in_text(v) or v & 3:
            break
        a -= 4
    return a


def find_bytes(img: Image, needle: bytes, align: int = 1) -> list[int]:
    out = []
    pos = img.data.find(needle)
    while pos != -1:
        if pos % align == 0:
            out.append(img.base + pos)
        pos = img.data.find(needle, pos + 1)
    return out
