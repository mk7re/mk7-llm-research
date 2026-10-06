"""Loaded view of a 3DS code.bin plus whatever symbols are known for it.

A decompressed code.bin is the .text, .rodata and .data segments back to back,
mapped at 0x00100000. .bss follows in memory but is not in the file. All code
in MK7 is ARM (no Thumb), so everything here works on aligned 32-bit words.
"""
import array
import bisect
import hashlib
import json
import pickle
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .. import paths

DEFAULT_BASE = 0x100000
PAGE = 0x1000


def load_registry() -> dict:
    if not paths.IMAGES_FILE.exists():
        raise SystemExit(f"{paths.IMAGES_FILE} is missing; see mk7-llm-research/docs/tooling/SETUP.md")
    return json.loads(paths.IMAGES_FILE.read_text())


def default_image_name() -> str:
    return load_registry()["default"]


@dataclass(frozen=True)
class Symbol:
    addr: int
    name: str
    size: int           # distance to the next symbol; 0 if unknown
    source: str         # "xmap" | "ported" | "user"
    confidence: str = ""  # for ported symbols: how the match was made

    @property
    def inferred(self) -> bool:
        return self.source == "ported"


class Image:
    def __init__(self, name: str | None = None):
        registry = load_registry()
        name = name or registry["default"]
        if name not in registry["images"]:
            raise SystemExit(f"unknown image {name!r}; known: {', '.join(registry['images'])}")
        cfg = registry["images"][name]
        self.name = name
        self.cfg = cfg
        self.path = paths.REPO / cfg["path"]
        if not self.path.exists():
            raise SystemExit(f"{self.path} not found (image {name!r} in images.json)")
        self.base = int(str(cfg.get("base", hex(DEFAULT_BASE))), 0)
        self.version = cfg.get("version")
        self.data = self.path.read_bytes()
        if len(self.data) % 4:
            self.data += b"\0" * (4 - len(self.data) % 4)
        self.end = self.base + len(self.data)

    # ---- raw access -------------------------------------------------------
    @cached_property
    def words(self) -> array.array:
        a = array.array("I")
        a.frombytes(self.data)
        return a

    def contains(self, addr: int) -> bool:
        return self.base <= addr < self.end

    def off(self, addr: int) -> int:
        if not self.contains(addr):
            raise ValueError(f"0x{addr:X} is outside {self.name} (0x{self.base:X}-0x{self.end:X})")
        return addr - self.base

    def u32(self, addr: int) -> int:
        o = self.off(addr)
        return int.from_bytes(self.data[o:o + 4], "little")

    def read(self, addr: int, size: int) -> bytes:
        o = self.off(addr)
        return self.data[o:o + size]

    def cstring(self, addr: int, limit: int = 200) -> str | None:
        """Printable NUL-terminated string at addr (ASCII/UTF-8/Shift-JIS), else None."""
        if not self.contains(addr):
            return None
        o = self.off(addr)
        end = self.data.find(b"\0", o, o + limit)
        if end <= o or end - o < 2:
            return None
        raw = self.data[o:end]
        for enc in ("utf-8", "shift_jis"):
            try:
                s = raw.decode(enc)
            except UnicodeDecodeError:
                continue
            if all(ch.isprintable() or ch in "\n\t\r" for ch in s):
                return s
        return None

    def wstring(self, addr: int, limit: int = 200) -> str | None:
        """UTF-16LE string at addr, else None."""
        if not self.contains(addr) or addr & 1:
            return None
        o = self.off(addr)
        chars = []
        while len(chars) < limit and o + 2 <= len(self.data):
            c = int.from_bytes(self.data[o:o + 2], "little")
            if c == 0:
                break
            if c < 0x20 and c not in (9, 10, 13) or 0xD800 <= c < 0xE000:
                return None
            chars.append(chr(c))
            o += 2
        s = "".join(chars)
        return s if len(s) >= 3 and sum(ch.isascii() for ch in s) >= len(s) * 0.5 else None

    # ---- segments ---------------------------------------------------------
    @cached_property
    def text_end(self) -> int:
        """End of .text, from images.json or estimated from instruction density."""
        if "text_end" in self.cfg:
            return int(str(self.cfg["text_end"]), 0)
        words = self.words
        per_page = PAGE // 4
        end = self.base
        for page in range(0, len(words), per_page):
            chunk = words[page:page + per_page]
            always = sum(1 for w in chunk if w >> 28 == 0xE)   # cond == AL
            if always < len(chunk) * 0.5:
                break
            end = self.base + (page + per_page) * 4
        return end

    def in_text(self, addr: int) -> bool:
        return self.base <= addr < self.text_end

    def segment(self, addr: int) -> str:
        if self.in_text(addr):
            return "text"
        if self.contains(addr):
            return "data"    # .rodata/.data; the boundary is not recoverable without the exheader
        if self.end <= addr < self.end + 0x2000000:
            return "bss?"
        return "-"

    # ---- cache ------------------------------------------------------------
    @cached_property
    def digest(self) -> str:
        return hashlib.sha1(self.data).hexdigest()

    def cache_path(self, kind: str) -> Path:
        paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return paths.CACHE_DIR / f"{self.name}.{self.digest[:12]}.{kind}"

    def cached(self, kind: str, build):
        p = self.cache_path(kind + ".pickle")
        if p.exists():
            with open(p, "rb") as f:
                return pickle.load(f)
        value = build()
        with open(p, "wb") as f:
            pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
        return value

    # ---- symbols ----------------------------------------------------------
    @cached_property
    def symbols(self) -> list[Symbol]:
        """All known symbols sorted by address (xmap > user > ported on conflicts)."""
        by_addr: dict[int, Symbol] = {}
        ported = paths.CACHE_DIR / f"{self.name}.ported.json"
        if ported.exists():
            doc = json.loads(ported.read_text())
            for entry in doc["functions"]:
                origin = f'{entry["how"]} {entry["score"]:.2f} from {doc["source"]}:{entry["src"]:08x}'
                by_addr[entry["addr"]] = Symbol(entry["addr"], entry["name"], entry.get("size", 0), "ported", origin)
        user = self.cfg.get("user_symbols")
        if user and (paths.REPO / user).exists():
            for addr, name in _read_map(paths.REPO / user):
                by_addr[addr] = Symbol(addr, name, 0, "user")
        if self.cfg.get("symbols"):
            for addr, name in _read_map(paths.REPO / self.cfg["symbols"]):
                by_addr[addr] = Symbol(addr, name, 0, "xmap")
        ordered = [by_addr[a] for a in sorted(by_addr)]
        # Sizes are only trustworthy when the map is a complete linker map.
        complete = bool(self.cfg.get("symbols"))
        out = []
        for i, s in enumerate(ordered):
            nxt = ordered[i + 1].addr if i + 1 < len(ordered) else self.text_end
            size = s.size
            if complete and self.in_text(s.addr) and s.source == "xmap":
                size = nxt - s.addr
            out.append(Symbol(s.addr, s.name, size, s.source, s.confidence))
        return out

    @cached_property
    def _sym_addrs(self) -> list[int]:
        return [s.addr for s in self.symbols]

    @property
    def has_full_symbols(self) -> bool:
        return bool(self.cfg.get("symbols"))

    def symbol_at(self, addr: int) -> Symbol | None:
        i = bisect.bisect_left(self._sym_addrs, addr)
        if i < len(self.symbols) and self.symbols[i].addr == addr:
            return self.symbols[i]
        return None

    def symbol_before(self, addr: int) -> Symbol | None:
        i = bisect.bisect_right(self._sym_addrs, addr) - 1
        return self.symbols[i] if i >= 0 else None

    def find_symbols(self, pattern: str, regex: bool = False) -> list[Symbol]:
        if regex:
            rx = re.compile(pattern, re.I)
            return [s for s in self.symbols if rx.search(s.name)]
        exact = [s for s in self.symbols if s.name == pattern]
        if exact:
            return exact
        # "Kart::Unit::changeToCPU" should match "Kart::Unit::changeToCPU(bool)".
        sig = [s for s in self.symbols if s.name.split("(")[0] == pattern]
        if sig:
            return sig
        low = pattern.lower()
        return [s for s in self.symbols if low in s.name.lower()]

    def resolve(self, text: str) -> int:
        """Address from hex text or from a symbol name (must be unambiguous)."""
        t = text.strip()
        if re.fullmatch(r"(0x)?[0-9a-fA-F]{5,8}", t):
            return int(t, 16)
        found = self.find_symbols(t)
        if not found:
            raise SystemExit(f"no symbol matching {text!r} in image {self.name!r}")
        if len(found) > 1:
            listing = "\n".join(f"  {s.addr:08x}  {s.name}" for s in found[:30])
            more = f"\n  ... {len(found) - 30} more" if len(found) > 30 else ""
            raise SystemExit(f"{text!r} is ambiguous in image {self.name!r}:\n{listing}{more}")
        return found[0].addr

    # ---- functions --------------------------------------------------------
    @cached_property
    def call_targets(self) -> list[int]:
        """Sorted addresses that some BL in .text calls: reliable function starts."""
        def build():
            base, words, n = self.base, self.words, (self.text_end - self.base) // 4
            targets = set()
            for i in range(n):
                w = words[i]
                if w & 0x0F000000 == 0x0B000000 and w >> 28 != 0xF:
                    off = w & 0x00FFFFFF
                    if off & 0x800000:
                        off -= 0x1000000
                    t = base + (i + 2 + off) * 4
                    if base <= t < self.text_end:
                        targets.add(t)
            return sorted(targets)
        return self.cached("calltargets", build)

    @cached_property
    def pointer_targets(self) -> list[int]:
        """Sorted .text addresses stored as words outside .text (vtables, callbacks)."""
        def build():
            words = self.words
            lo, hi = self.base, self.text_end
            start = (self.text_end - self.base) // 4
            return sorted({w for w in words[start:] if lo <= w < hi and not w & 3})
        return self.cached("ptrtargets", build)

    @cached_property
    def function_starts(self) -> list[int]:
        starts = set(self.call_targets) | set(self.pointer_targets)
        starts.update(s.addr for s in self.symbols if self.in_text(s.addr))
        return sorted(starts)

    def function_bounds(self, addr: int) -> tuple[int, int]:
        """(start, end) of the function containing addr.

        Exact when the image has a linker map. Otherwise the start is the
        nearest known entry point at or below addr and the end is the next
        one, so a function that is never called directly nor stored in a table
        is reported as the tail of its predecessor.
        """
        if not self.in_text(addr):
            raise SystemExit(f"0x{addr:X} is not in .text of {self.name} (text is 0x{self.base:X}-0x{self.text_end:X})")
        starts = self.function_starts
        i = bisect.bisect_right(starts, addr) - 1
        start = starts[i] if i >= 0 else self.base
        end = starts[i + 1] if i + 1 < len(starts) else self.text_end
        return start, end

    @staticmethod
    def label(s: Symbol) -> str:
        """Symbol name; names carried over from another image are prefixed with ~."""
        return ("~" if s.inferred else "") + s.name

    def describe(self, addr: int) -> str:
        """Short human label for an address: symbol(+off), string, or segment."""
        if self.in_text(addr):
            s = self.symbol_before(addr)
            if s and (s.addr == addr or (s.size and addr < s.addr + s.size)):
                return self.label(s) + (f"+0x{addr - s.addr:X}" if addr != s.addr else "")
            start, _ = self.function_bounds(addr)
            s = self.symbol_at(start)
            label = self.label(s) if s else f"sub_{start:08x}"
            return label + (f"+0x{addr - start:X}" if addr != start else "")
        if self.contains(addr):
            s = self.symbol_at(addr)
            if s:
                return s.name
            if not addr & 3 and self.base <= self.u32(addr) < self.end + 0x2000000:
                return f"data_{addr:08x}"       # holds a pointer; not a string
            text = self.cstring(addr)
            if text is not None and len(text) >= 4:
                return json.dumps(text[:60], ensure_ascii=False)
            wide = self.wstring(addr)
            if wide is not None:
                return "L" + json.dumps(wide[:60], ensure_ascii=False)
            return f"data_{addr:08x}"
        return self.segment(addr) if self.segment(addr) != "-" else ""


def _read_map(path: Path):
    """Yield (addr, name) from an 'hexaddr<TAB>name' map; '#' starts a comment."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            addr, _, name = line.partition("\t")
            if not name:
                addr, _, name = line.partition(" ")
            try:
                yield int(addr, 16), name.strip()
            except ValueError:
                continue
