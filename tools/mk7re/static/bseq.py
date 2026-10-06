"""BSEQ scene and menu sequence files (`.brs` / `.bss` in UI/common.szs): parsing and text dumps.

The format and the names follow the research on scene and menu sequencing (BSEQ) (template/
still has some older names, for example `field_0x08` for `m_root_mode_id`). In short, all little endian:

    header (0x34 bytes), u32 section_block_offsets[num_section_block]  (offsets from the start of the file)
    section blocks: SectionBlock (0x14) with an enter and a return code table, and a type-specific block
        practical (block type 0/1): u16 num_instances, u16 class_name, u16 mode_table, u16 pad
        sequence / cross fade (2/3): u16 mode_id, u16 mode_name, u16 subsection_list, u16 flow_list
        scene proxy (4):             u16 mode_id, u16 mode_name, u16 scene_name, u16 pad
    engine creator table: num_engine_creator x {u16 creator class name, u16 mode name}
    string table: NUL-terminated strings, referenced by u16 offsets from its start

Offsets inside a block are from the start of the structure holding them. A code table is
{u16 count, u16 default_id} then count x {u16 id, u16 name}; the game resolves an unknown ID to the
entry of default_id. A flow entry is {s16 src_index, u16 src_code, s16 dst_index, u16 dst_code}
(+ u16 cross_fade_type, u16 pad in cross fade blocks); an index is a subsection index, -1 the
sequence itself. How each sequence class reads the flows is in Finding 5 of the research.
"""
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .. import paths
from .romfs import name_hash

MAGIC = b"BSEQ"
HEADER_SIZE = 0x34
SECTION_TYPES = {0: "page", 1: "task", 2: "data holder", 3: "serial", 4: "cross fade", 5: "parallel",
                 6: "delegate", 7: "scene proxy", 8: "brs root"}
BLOCK_TYPES = {0: "practical", 1: "practical", 2: "sequence", 3: "cross fade", 4: "scene proxy"}
# DashSceneIDConverter::defineSceneIDDictionary; any other name gives 1 (Boot). Research on BSEQ, Finding 7.
SCENE_IDS = {"Boot": 1, "Menu": 2, "Race": 3, "Trophy": 4, "Thankyou": 5, "Ending": 6, "Demo": 7}
HEADER_FIELDS = (  # (offset, struct format, name)
    (0x04, "I", "sequence_id"), (0x08, "H", "root_mode_id"), (0x0A, "H", "field_0x0A"), (0x0C, "H", "field_0x0C"),
    (0x0E, "H", "num_sections"), (0x10, "H", "num_serial_sequences"), (0x12, "H", "num_cross_fade_sequences"),
    (0x14, "H", "num_parallel_sequences"), (0x16, "H", "num_delegate_sequences"),
    (0x18, "H", "num_scene_sequence_proxy"), (0x1A, "H", "num_layers"), (0x1C, "H", "num_section_block"),
    (0x1E, "H", "num_engine_creator"), (0x20, "I", "field_0x20"), (0x24, "I", "field_0x24"),
    (0x28, "I", "first_section_block_offset"), (0x2C, "I", "engine_creator_table_offset"),
    (0x30, "I", "nametable_offset"),
)


@dataclass
class Table:
    offset: int
    default: int
    entries: list               # (id, name)

    def code(self, code_id: int) -> str:
        """`Name(id)`, or how the game resolves an ID that is not in the table (`#id?->Default(id)`)."""
        for i, n in self.entries:
            if i == code_id:
                return f"{n}({i})"
        for i, n in self.entries:
            if i == self.default:
                return f"#{code_id}?->{n}({i})"
        return f"#{code_id}?"

    def text(self) -> str:
        items = ", ".join(f"{i} {n}" for i, n in self.entries) or "-"
        return f"(default {self.default}) {items}"


@dataclass
class Sub:
    offset: int
    sid: int
    mode: int
    pad: int


@dataclass
class Flow:
    offset: int
    src: int
    src_code: int
    dst: int
    dst_code: int
    cross_fade: int | None = None
    pad: int = 0


@dataclass
class Block:
    index: int
    offset: int
    section_type: int
    sid: int
    name: str
    enter: Table
    ret: Table
    block_type: int
    body: int                   # offset of the type-specific block, in the file
    padding: dict = field(default_factory=dict)  # name -> value of the bytes that are always 0
    # practical
    instances: int = 0
    class_name: str = ""
    modes: Table | None = None
    # sequence, cross fade, scene proxy
    mode_id: int = 0
    mode_name: str = ""
    subs_offset: int = 0
    subs: list = field(default_factory=list)
    flows_offset: int = 0
    flows: list = field(default_factory=list)
    scene_name: str = ""

    @property
    def practical(self) -> bool:
        return self.block_type < 2


class Bseq:
    def __init__(self, data: bytes, path: Path | None = None):
        if data[:4] != MAGIC:
            raise SystemExit(f"{path or 'data'}: not a BSEQ file")
        self.data, self.path = data, path
        self.covered: list[tuple[int, int]] = []
        self.used_strings: set[int] = set()
        self.h = {name: struct.unpack_from("<" + fmt, data, off)[0] for off, fmt, name in HEADER_FIELDS}
        self.strings_offset = self.h["nametable_offset"]
        n = self.h["num_section_block"]
        self.block_offsets = list(struct.unpack_from(f"<{n}I", data, HEADER_SIZE))
        self._cover(0, HEADER_SIZE + 4 * n)
        self.blocks = [self._block(i, o) for i, o in enumerate(self.block_offsets)]
        ec = self.h["engine_creator_table_offset"]
        self.engines = []
        for i in range(self.h["num_engine_creator"]):
            creator, mode = struct.unpack_from("<HH", data, ec + 4 * i)
            self.engines.append((ec + 4 * i, self._str(creator), self._str(mode)))
        self._cover(ec, ec + 4 * len(self.engines))
        self._cover(self.strings_offset, len(data))

    # -- reading
    def _u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.data, off)[0]

    def _cover(self, start: int, end: int):
        if end > start:
            self.covered.append((start, end))

    def _str(self, off: int) -> str:
        self.used_strings.add(off)
        o = self.strings_offset + off
        end = self.data.find(b"\0", o)
        return self.data[o:end if end >= 0 else len(self.data)].decode("ascii", "replace")

    def _table(self, off: int) -> Table:
        count, default = struct.unpack_from("<HH", self.data, off)
        entries = [(self._u16(off + 4 + 4 * i), self._str(self._u16(off + 6 + 4 * i))) for i in range(count)]
        self._cover(off, off + 4 + 4 * count)
        return Table(off, default, entries)

    def _block(self, index: int, o: int) -> Block:
        d = self.data
        stype, byte1, f02, sid, name, enter, ret, btype, body, pad12 = struct.unpack_from("<BBHIHHHHHH", d, o)
        self._cover(o, o + 0x14)
        b = Block(index, o, stype, sid, self._str(name), self._table(o + enter), self._table(o + ret), btype, o + body)
        b.padding = {"byte_0x01": byte1, "field_0x02": f02, "pad_0x12": pad12}
        p = b.body
        self._cover(p, p + 8)
        if b.practical:
            b.instances, cls, modes, pad = struct.unpack_from("<HHHH", d, p)
            b.class_name, b.modes = self._str(cls), self._table(p + modes)
            b.padding["practical_pad"] = pad
        else:
            b.mode_id, mode_name, third, fourth = struct.unpack_from("<HHHH", d, p)
            b.mode_name = self._str(mode_name)
            if btype == 4:
                b.scene_name = self._str(third)
                b.padding["proxy_pad"] = fourth
            elif btype in (2, 3):
                b.subs_offset, b.flows_offset = p + third, p + fourth
                count, pad = struct.unpack_from("<HH", d, b.subs_offset)
                b.padding["subsection_list_pad"] = pad
                for k in range(count):
                    e = b.subs_offset + 4 + 8 * k
                    b.subs.append(Sub(e, *struct.unpack_from("<IHH", d, e)))
                self._cover(b.subs_offset, b.subs_offset + 4 + 8 * count)
                count, pad = struct.unpack_from("<HH", d, b.flows_offset)
                b.padding["flow_list_pad"] = pad
                size = 8 if btype == 2 else 12
                for k in range(count):
                    e = b.flows_offset + 4 + size * k
                    f = Flow(e, *struct.unpack_from("<hHhH", d, e))
                    if size == 12:
                        f.cross_fade, f.pad = struct.unpack_from("<HH", d, e + 8)
                    b.flows.append(f)
                self._cover(b.flows_offset, b.flows_offset + 4 + size * count)
        return b

    # -- SequenceResource::searchPracticalSectionBlock / searchSequenceBlock
    def root(self) -> Block | None:
        return self.sequence(self.h["sequence_id"], self.h["root_mode_id"])

    def sequence(self, sid: int, mode: int) -> Block | None:
        return next((b for b in self.blocks if b.sid == sid and b.block_type in (2, 3, 4) and b.mode_id == mode), None)

    def child(self, sub: Sub) -> Block | None:
        practical = next((b for b in self.blocks if b.sid == sub.sid and b.section_type < 3), None)
        return practical or self.sequence(sub.sid, sub.mode)

    # -- derived
    def stored_name(self) -> str:
        return self.path.name if self.path else ""

    def file_name(self) -> str | None:
        """`<root name>-<root mode>.<brs|bss>`, as the game builds it (None when there is no root block)."""
        r = self.root()
        if not r:
            return None
        return f"{r.name}-{r.mode_name}.{'brs' if r.section_type == 8 else 'bss'}"

    def checks(self) -> list[tuple[bool, str]]:
        """The consistency rules of Findings 2 and 3 of the research."""
        h, out = self.h, []
        pools = (h["num_serial_sequences"], h["num_cross_fade_sequences"], h["num_parallel_sequences"],
                 h["num_delegate_sequences"], h["num_scene_sequence_proxy"])
        instances = sum(b.instances for b in self.blocks if b.section_type < 3)
        total = sum(pools) + instances
        out.append((h["num_sections"] == total,
                    f"num_sections {h['num_sections']} == pools {'+'.join(map(str, pools))} + instances {instances} "
                    f"= {total} (the game does not check the capacity)"))
        root_id = h["sequence_id"]
        parallel = [b for b in self.blocks if b.section_type == 5 or (b.sid == root_id and not b.practical)]
        widest = max(parallel, key=lambda b: len(b.subs), default=None)
        need = len(widest.subs) if widest else 0
        out.append((h["num_layers"] >= need, f"num_layers {h['num_layers']} >= subsections of the widest parallel "
                                             f"sequence ({widest.name if widest else '-'}: {need})"))
        first = HEADER_SIZE + 4 * h["num_section_block"]
        out.append((h["first_section_block_offset"] == first,
                    f"first_section_block_offset 0x{h['first_section_block_offset']:X} == 0x{first:X} (not read)"))
        out.append((self.root() is not None, f"a block for the root (id 0x{root_id:X}, mode {h['root_mode_id']})"))
        return out

    def unused_strings(self) -> list[tuple[int, str]]:
        out, pos = [], self.strings_offset
        while pos < len(self.data):
            end = self.data.find(b"\0", pos)
            end = len(self.data) if end < 0 else end
            off = pos - self.strings_offset
            if off not in self.used_strings and end > pos:
                out.append((off, self.data[pos:end].decode("ascii", "replace")))
            pos = end + 1
        return out

    def uncovered(self) -> list[tuple[int, int]]:
        out, pos = [], 0
        for start, end in sorted(self.covered):
            if start > pos:
                out.append((pos, start))
            pos = max(pos, end)
        return out


# ---- formatting ----------------------------------------------------------------
def describe(b: Block | None) -> str:
    if not b:
        return "(no block in this file)"
    kind = SECTION_TYPES.get(b.section_type, f"type {b.section_type}")
    return f"{b.name} [{kind}{', class ' + b.class_name if b.practical else ''}]"


def flow_text(bseq: Bseq, b: Block, f: Flow) -> str:
    """One flow entry, with every code resolved against the table it is looked up in (Finding 5)."""
    def child(i: int) -> Block | None:
        return bseq.child(b.subs[i]) if 0 <= i < len(b.subs) else None

    if f.src == -1:
        src = f"enter {b.enter.code(f.src_code)}"
    else:
        c = child(f.src)
        src = f"[{f.src}] {c.name if c else '?'} returns {c.ret.code(f.src_code) if c else f'#{f.src_code}'}"
    if f.dst == -1:
        dst = f"return {b.ret.code(f.dst_code)}"
    else:
        c = child(f.dst)
        dst = f"[{f.dst}] {c.name if c else '?'} enter {c.enter.code(f.dst_code) if c else f'#{f.dst_code}'}"
    raw = f"({f.src}, {f.src_code}, {f.dst}, {f.dst_code}"
    raw += f", cross_fade_type {f.cross_fade}" + (f", pad 0x{f.pad:X}" if f.pad else "") + ")" if f.cross_fade is not None else ")"
    return f"{src} -> {dst}   {raw}"


def block_lines(bseq: Bseq, b: Block) -> list[str]:
    root = " [root of the file]" if b is bseq.root() else ""
    kind = SECTION_TYPES.get(b.section_type, "?")
    out = [f"[{b.index}] @0x{b.offset:X} {b.name}  id=0x{b.sid:X}  section_type={b.section_type} ({kind})  "
           f"block_type={b.block_type} ({BLOCK_TYPES.get(b.block_type, '?')}){root}"]
    out.append(f"    enter codes @0x{b.enter.offset:X} {b.enter.text()}")
    out.append(f"    return codes @0x{b.ret.offset:X} {b.ret.text()}")
    if b.practical:
        out.append(f"    practical @0x{b.body:X}: class {b.class_name}, instances {b.instances}")
        out.append(f"    modes @0x{b.modes.offset:X} {b.modes.text()}")
    elif b.block_type == 4:
        scene_id = SCENE_IDS.get(b.scene_name)
        scene = f"scene ID {scene_id}" if scene_id else "not a scene name, so scene ID 1 (Boot)"
        out.append(f"    scene proxy @0x{b.body:X}: mode {b.mode_id} {b.mode_name}, scene {b.scene_name} -> {scene}; "
                   f"loads {b.name}-{b.mode_name}.bss")
    elif b.block_type in (2, 3):
        out.append(f"    {BLOCK_TYPES[b.block_type]} @0x{b.body:X}: mode {b.mode_id} {b.mode_name}")
        out.append(f"    subsections @0x{b.subs_offset:X} ({len(b.subs)}):")
        parallel = b.section_type == 5 or b.sid == bseq.h["sequence_id"]
        for k, s in enumerate(b.subs):
            pad = f" pad=0x{s.pad:X}" if s.pad else ""
            c = bseq.child(s)
            note = ""
            if parallel and c and not any(f.src == -1 and f.dst == k for f in b.flows):
                note = f"  (parallel: started anyway, with enter code 0 -> {c.enter.code(0)})"
            out.append(f"      [{k}] id=0x{s.sid:X} mode {s.mode}  {describe(c)}{pad}{note}")
        out.append(f"    flows @0x{b.flows_offset:X} ({len(b.flows)}):")
        for k, f in enumerate(b.flows):
            out.append(f"      [{k}] {flow_text(bseq, b, f)}")
    else:
        out.append(f"    ! unknown block type {b.block_type}; body at 0x{b.body:X} not read")
    nonzero = {k: v for k, v in b.padding.items() if v}
    if nonzero:
        out.append("    ! nonzero bytes that are 0 in every retail file: "
                   + ", ".join(f"{k}=0x{v:X}" for k, v in nonzero.items()))
    return out


PARTS = ("header", "blocks", "engines", "strings")


def dump(bseq: Bseq, selection: list[str] | None = None, origin: str = "") -> list[str]:
    """`selection`: parts (header, blocks, engines, strings), block names or block indices (#N); None = all."""
    out = [f"# BSEQ {paths.rel(bseq.path) if bseq.path else ''}".rstrip()]
    if origin:
        out.append(f"# {origin}")
    out.append("# names follow the research on scene and menu sequencing (BSEQ); codes are Name(id), "
               "#id?->Name(id) = an ID not in the table, which the game resolves to the default entry")
    parts = set(PARTS) if not selection else {s.lower() for s in selection if s.lower() in PARTS}
    picked: list[Block] = []
    for s in selection or []:
        if s.lower() in PARTS:
            continue
        key = s[1:] if s.startswith("#") else s
        if key.isdigit():
            if int(key) >= len(bseq.blocks):
                raise SystemExit(f"no block #{key}; the file has {len(bseq.blocks)}")
            picked.append(bseq.blocks[int(key)])
            continue
        found = [b for b in bseq.blocks if b.name.lower() == s.lower()]
        if not found:
            close = sorted({b.name for b in bseq.blocks if s.lower() in b.name.lower()})
            raise SystemExit(f"no block named {s!r}" + (f"; did you mean: {', '.join(close)}" if close else
                                                        f"; parts: {', '.join(PARTS)}"))
        picked.extend(found)
    if "header" in parts:
        out += ["", "== header"]
        out.append(" ".join(f"{name}={_hex_or_dec(name, bseq.h[name])}" for _, _, name in HEADER_FIELDS))
        r = bseq.root()
        if r:
            out.append(f"root: [{r.index}] {r.name}, mode {r.mode_name}")
        name = bseq.file_name()
        if name:
            stored = bseq.stored_name()
            hashed = f"0x{name_hash(name):08X}"
            how = "the file's own name" if stored == name else \
                f"matches the stored hash {stored}" if stored.upper() == hashed.upper() else \
                f"hash {hashed}, does not match the stored name {stored or '-'}"
            out.append(f"file name from the root: {name} ({how})")
        for ok, text in bseq.checks():
            out.append(f"check {'ok  ' if ok else 'FAIL'} {text}")
    if "blocks" in parts or picked:
        blocks = picked or bseq.blocks
        out += ["", f"== blocks ({len(blocks)} of {len(bseq.blocks)})"]
        for b in blocks:
            out += block_lines(bseq, b)
    if "engines" in parts:
        out += ["", f"== engine creators @0x{bseq.h['engine_creator_table_offset']:X} ({len(bseq.engines)})"]
        out += [f"[{i}] @0x{o:X} {c} mode {m}" for i, (o, c, m) in enumerate(bseq.engines)]
    if "strings" in parts:
        unused = bseq.unused_strings()
        out += ["", f"== strings @0x{bseq.strings_offset:X}: {len(bseq.used_strings)} referenced, "
                    f"{len(unused)} not referenced by anything parsed"]
        out += [f"  +0x{o:X} {s}" for o, s in unused]
    if not selection:
        out.append("")
        gaps = bseq.uncovered()
        nonzero = [(a, e) for a, e in gaps if any(bseq.data[a:e])]
        if not gaps:
            out.append("# every byte of the file is accounted for")
        else:
            zero = sum(e - a for a, e in gaps) - sum(e - a for a, e in nonzero)
            out.append(f"# not accounted for: {len(gaps)} ranges; {zero} bytes are zero (padding)")
        for a, e in nonzero:
            chunk = bseq.data[a:e]
            out.append(f"# not accounted for: 0x{a:X}..0x{e:X} ({e - a} bytes): {chunk[:32].hex(' ')}"
                       + (" ..." if e - a > 32 else ""))
    return out


def _hex_or_dec(name: str, v: int) -> str:
    return f"0x{v:X}" if name.endswith(("_offset", "_id")) and name != "root_mode_id" else str(v)


# ---- finding the files ---------------------------------------------------------
def files(image: str) -> dict[str, Path]:
    """Stored name -> file, for every BSEQ of UI/common.szs (a pat1:/Patch/UI/common file replaces its namesake)."""
    root = paths.ROMFS_DIR / image
    out: dict[str, Path] = {}
    for folder in (root / "rom" / "UI" / "common.szs.d", root / "pat1" / "Patch" / "UI" / "common"):
        for p in sorted(folder.glob("*")) if folder.is_dir() else ():
            if p.is_file():
                with open(p, "rb") as f:
                    if f.read(4) == MAGIC:
                        out[p.name] = p
    return out


def origin_of(path: Path, image: str) -> str:
    where = "pat1:/Patch/UI/common/" if "pat1" in path.parts else "rom:/UI/common.szs/"
    return f"{image} {where}{path.name}"


def resolve(target: str, image: str) -> Path:
    """A path, a stored name (`Root-Default.brs`, `0xB070E39E`), or a name with or without extension
    (`BootScene-Default`) whose file is stored by hash."""
    p = Path(target)
    if p.is_file():
        return p
    found = files(image)
    if not found:
        raise SystemExit(f"no BSEQ files under {paths.rel(paths.ROMFS_DIR / image)}; run `mk7 romfs extract -i {image}`")
    lower = {k.lower(): v for k, v in found.items()}
    names = [target] if target.lower().endswith((".bss", ".brs")) else [target + ".bss", target + ".brs"]
    for n in [target] + names:
        if n.lower() in lower:
            return lower[n.lower()]
        hashed = f"0x{name_hash(n):08x}"
        if hashed in lower:
            return lower[hashed]
    raise SystemExit(f"no BSEQ file {target!r} in {image}; `mk7 bseq list` shows them")
