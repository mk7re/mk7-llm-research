"""KMP course data files (`DMDC`): parsing and text dumps for reading by hand or by an agent.

A KMP is a header (`DMDC`, u32 file size, u16 section count, u16 header size, u32 version, then one
u32 offset per section, relative to the end of the header) followed by the sections. Each section
starts with its magic, a u16 entry count and a u16 extra value, then the entries. The magic is
stored reversed (`TPTK` for KTPT); sections are named here the way the research names them (KTPT,
ENPT, ...), and both spellings are accepted wherever a section is selected.

Where the name of each field comes from, best first (`SOURCES`; `mk7 kmp fields` shows it per field):
  - the template/ files (Field/Entry/*.hpp: the `Field::Mapdata*Data` structs the game reads);
  - research that template/ does not have yet, named by its subject (the topic folders may be renamed);
  - the game's code, read for this tool where neither has the field (the note names the function);
  - community tools, as hints only (KMPExpander, EveryFileExplorer, the mk3ds.com wiki): shown as `name~`.
A field nobody has named is shown as `unk_0x<offset>`, with its value in hex.

The enumerators of `eMapdataGeoObjID`, `eMapdataAreaShape`, `eMapdataAreaType` and `ObjPresenceFlags`
are read from template/, so the dump follows the templates as they change.
"""
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .. import paths
from . import templates

MAGIC = b"DMDC"
CURRENT_VERSION = 0xC1C

T = "template"
F_ENEMY = "enemy AI research"
F_CKPT = "checkpoint research"
CODE = "code"
C = "community"
SOURCES = {
    T: "template/ (Field/Entry/*.hpp)",
    F_ENEMY: "the research on enemy AI behaviour and enemy points (ENPT, ENPH), not in template/ yet",
    F_CKPT: "the research on ghost checkpoints (CKPT), not in template/ yet",
    CODE: "the game's code (eur2), read for this tool; the note names the function",
    C: "community tools, hints only: KMPExpander, EveryFileExplorer, mk3ds.com wiki (shown as name~)",
}

# Built-in flag names: the enemy AI research (EnemyPointFlags; the names are made up there).
BUILTIN_FLAGS = {
    "EnemyPointFlags": {
        0x01: "CORNERING", 0x02: "HEIGHT_REROUTE", 0x04: "PRECISE", 0x08: "NO_TRICK",
        0x10: "HOLD_DRIFT", 0x20: "KILLER_FOLLOW_HEIGHT", 0x40: "KILLER_NO_END", 0x80: "FORCE_BASE_SPEED",
    },
}

_SCALAR = {"u8": "B", "s8": "b", "u16": "H", "s16": "h", "u32": "I", "s32": "i", "f32": "f"}


@dataclass(frozen=True)
class Field:
    off: int
    type: str           # u8 s8 u16 s16 u32 s32 f32 vec2 vec3, or "<scalar>[n]"
    name: str = ""      # "" = unknown, shown as unk_0x<off>
    src: str = ""       # key of SOURCES
    show: str = ""      # "" | "hex" | "enum:<name>" | "flags:<name>" | "links" (index list; all-ones = none)
    note: str = ""

    @property
    def scalar(self) -> str:
        return self.type.split("[")[0]

    @property
    def count(self) -> int:
        if self.type == "vec2":
            return 2
        if self.type == "vec3":
            return 3
        return int(self.type.split("[")[1].rstrip("]")) if "[" in self.type else 1

    @property
    def fmt(self) -> str:
        base = "f" if self.type.startswith("vec") else _SCALAR[self.scalar]
        return "<" + base * self.count

    @property
    def size(self) -> int:
        return struct.calcsize(self.fmt)

    @property
    def label(self) -> str:
        if not self.name:
            return f"unk_0x{self.off:X}"
        return self.name + ("~" if self.src == C else "")


@dataclass(frozen=True)
class Spec:
    name: str           # as the research names it; the file stores it reversed
    title: str
    struct: str         # what the game reads it as (template/)
    size: int           # entry size; 0 = unknown, entries are shown as raw bytes
    fields: tuple = ()
    points: str = ""    # path section: the point section it groups
    path: str = ""      # point section: the path section grouping it
    extra: str = ""     # meaning of the u16 after the entry count
    sizes: tuple = ()   # (version, entry size) for files older than CURRENT_VERSION

    @property
    def magic(self) -> str:
        return self.name[::-1]

    def entry_size(self, version: int) -> int:
        for v, s in self.sizes:
            if version <= v:
                return s
        return self.size


def _path_fields(t: str, n: int, src: str, unk: tuple = ()) -> tuple:
    w = 1 if t == "u8" else 2
    return (Field(0, t, "start_point", src), Field(w, t, "point_num", src),
            Field(2 * w, f"{t}[{n}]", "previous_points", src, "links", "indices into this section"),
            Field(2 * w + n * w, f"{t}[{n}]", "next_points", src, "links", "indices into this section")) + unk


_POS = Field(0x0, "vec3", "position", T)
# The only code found that reads the glider sections (eur2 0x002E2D88), called by Kart::Director::createBeforeStructure.
_WING_CTOR = "Kart::WingPathData::WingPathData"
_NOT_READ = "not read by Kart::WingPathData::WingPathData, the only reader found"

SPECS = [
    Spec("KTPT", "start points", "Field::MapdataStartPointData", 0x1C, (
        _POS, Field(0xC, "vec3", "rotation", T), Field(0x18, "s16", "kart_index", T), Field(0x1A, "u16"))),
    Spec("ENPT", "enemy points (CPU routes)", "Field::MapdataEnemyPointData", 0x18, (
        _POS,
        Field(0xC, "f32", "scale", F_ENEMY, note="lateral half-width = scale * 50"),
        Field(0x10, "u16", "mushroom_setting", F_ENEMY,
              note="0 may use a mushroom, 1 first point of a mushroom shortcut branch, other no mushroom"),
        Field(0x12, "u8", "drift_setting", F_ENEMY,
              note="0 drift allowed, 1 end drift, 2 end drift without mini-turbo, other decided by the corner"),
        Field(0x13, "u8", "flags", F_ENEMY, "flags:EnemyPointFlags"),
        Field(0x14, "s16", "path_find_options", F_ENEMY,
              note="0 normal, -1/-2 excluded from some nearest point searches, -3/-4 Mii title path, > 0 award kart number"),
        Field(0x16, "s16", "max_search_y_offset", F_ENEMY,
              note="nearest point search: 0 no height limit, < 0 75 units, > 0 value in units")),
        path="ENPH"),
    Spec("ENPH", "enemy paths", "Field::MapdataEnemyPathData", 0x48, _path_fields("u16", 16, T, (
        Field(0x44, "u32", "link_end_flags", F_ENEMY, "hex",
              "bit n: previous path n is joined at its first point, bit 16+n: next path n is joined at its last point"),
    )), points="ENPT"),
    Spec("ITPT", "item points (item routes)", "Field::MapdataItemPointData", 0x14, (
        _POS, Field(0xC, "f32", "radius", T, note="units = radius * 50"),
        Field(0x10, "u16", "fly_mode", T),
        Field(0x12, "u16", "scan_radius", T, note="0 -> 300 units, 1 -> 900 units")), path="ITPH"),
    Spec("ITPH", "item paths", "Field::MapdataItemPathData", 0x1C, _path_fields("u16", 6, T), points="ITPT"),
    Spec("CKPT", "checkpoints", "Field::MapdataCheckPointData", 0x18, (
        Field(0x0, "vec2", "sector_left", T, note="X, Z"), Field(0x8, "vec2", "sector_right", T, note="X, Z"),
        Field(0x10, "s8", "jugem_point_index", T, note="JGPT index"),
        Field(0x11, "s8", "check_point_type", T, note="key id: -1 not a key checkpoint, 0 finish line (checkpoint research)"),
        Field(0x12, "s8", "check_point_prev", T, note="previous CKPT in the path, -1 for the first"),
        Field(0x13, "s8", "check_point_next", T, note="next CKPT in the path, -1 for the last"),
        Field(0x14, "u8", "clip_id", C),
        Field(0x15, "s8", "section", F_CKPT,
              note="-1 mostly; 1-lap courses: start of a section; 3-lap courses: 1 lets the kart change to this checkpoint "
                   "from any other"),
        Field(0x16, "u16")), path="CKPH"),
    Spec("CKPH", "checkpoint paths", "Field::MapdataCheckPathData", 0x10,
         _path_fields("u8", 6, T, (Field(0xE, "u16"),)), points="CKPT"),
    Spec("GOBJ", "objects", "Field::MapdataGeoObjData", 0x40, (
        Field(0x0, "u16", "id", T, "enum:eMapdataGeoObjID"),
        Field(0x2, "u16", "id_index", T, note="eMapdataGeoObjIDIndex in template/"),
        Field(0x4, "vec3", "position", T), Field(0x10, "vec3", "rotation", T), Field(0x1C, "vec3", "scale", T),
        Field(0x28, "s16", "route_id", T, note="POTI route, -1 none"),
        Field(0x2A, "u16[8]", "settings", T, note="settings[7] (0x38) also selects how enemy_route links (enemy AI research)"),
        Field(0x3A, "u16", "presence_flags", T, "flags:ObjPresenceFlags"),
        Field(0x3C, "s16", "enemy_route", T, note="ENPH path the object is linked to, -1 none"),
        Field(0x3E, "s16")), sizes=((0xBB8, 0x3C),)),
    Spec("POTI", "routes (objects, cameras)", "Field::MapdataPathData / Field::MapdataPathPoint", 0,
         extra="total number of points"),
    Spec("AREA", "areas", "Field::MapdataAreaData", 0x30, (
        Field(0x0, "u8", "shape", T, "enum:eMapdataAreaShape"),
        Field(0x1, "u8", "type", T, "enum:eMapdataAreaType"),
        Field(0x2, "s8", "came_index", T, note="CAME index"),
        Field(0x3, "u8", "priority", C),
        Field(0x4, "vec3", "position", T), Field(0x10, "vec3", "rotation", T), Field(0x1C, "vec3", "scale", T),
        Field(0x28, "u16", "setting1", T), Field(0x2A, "u16", "setting2", T),
        Field(0x2C, "s8", "route_id", T, note="POTI route"), Field(0x2D, "s8", "enemy_id", T),
        Field(0x2E, "u16"))),
    Spec("CAME", "cameras", "Field::MapdataCamera::SData", 0x48, (
        Field(0x0, "u8", "type", C), Field(0x1, "s8", "next", C, note="CAME index, -1 none"),
        Field(0x2, "u8", "video_next", C), Field(0x3, "s8", "route_id", C, note="POTI route, -1 none"),
        Field(0x4, "u16", "point_speed", C), Field(0x6, "u16", "fov_speed", C),
        Field(0x8, "u16", "viewpoint_speed", C), Field(0xA, "u8", "start_flag", C), Field(0xB, "u8", "video_flag", C),
        Field(0xC, "vec3", "position", C), Field(0x18, "vec3", "rotation", C),
        Field(0x24, "f32", "fov_begin", C), Field(0x28, "f32", "fov_end", C),
        Field(0x2C, "vec3", "viewpoint_begin", C), Field(0x38, "vec3", "viewpoint_end", C),
        Field(0x44, "f32", "duration", C)), extra="0xFFFF in every retail file"),
    Spec("JGPT", "Jugem points (respawn points)", "Field::MapdataJugemPointData", 0x1C, (
        _POS, Field(0xC, "vec3", "rotation", C), Field(0x18, "u16", "index", C),
        Field(0x1A, "s16", "check_point_index", F_CKPT, note="CKPT the kart is put in after respawning, when > 0"))),
    Spec("CNPT", "cannon points", "Field::MapdataCannonPointData", 0x1C),
    Spec("MSPT", "mission points", "Field::MapdataMissionPointData", 0x1C),
    Spec("STGI", "stage info", "Field::MapdataStageData", 0xC, (
        Field(0x0, "u8", "lap_count", C),
        Field(0x1, "u8", note="0 mirrors and shifts the CPU start lanes (enemy AI research)"),
        Field(0x2, "u8"), Field(0x3, "u8"), Field(0x4, "u32"), Field(0x8, "u32"))),
    Spec("CORS", "course sections?", "", 0),
    Spec("GLPT", "glider points", "Field::MapdataGlidePoint::SData", 0x18, (
        Field(0x0, "vec3", "position", CODE, note=f"read by {_WING_CTOR}"),
        Field(0xC, "f32", "scale", CODE, note=f"{_WING_CTOR}: raised to at least 0.1, then * 50"),
        Field(0x10, "u32", note=_NOT_READ), Field(0x14, "u32", note=_NOT_READ)),
         path="GLPH"),
    Spec("GLPH", "glider paths", "Field::MapdataGlidePath::SData", 0x16, (
        Field(0x0, "u8", "start_point", CODE, note="Field::MapdataGlidePath::getStartPoint"),
        Field(0x1, "u8", "point_num", CODE, note="Field::MapdataGlidePath::getPointNum"),
        Field(0x2, "u8[6]", "previous_points", C, "links", _NOT_READ),
        Field(0x8, "u8[6]", "next_points", C, "links", _NOT_READ),
        Field(0xE, "u8", note=f"{_WING_CTOR}: != 0 -> WingPathData +4; VehicleMove::startWingReady: "
                              "VehicleMove +0xE80 = (0xE or 0xF), read by Kart::Camera::calcApply"),
        Field(0xF, "u8", note=f"{_WING_CTOR}: != 0 -> WingPathData +5; VehicleMove +0xE81 (glider, camera, sound, "
                              "Driver::calcDrive, ObjectWiiCannon); WingPath::startCur: from the first segment, "
                              "WingPath +0x64 = FLT_MAX. Set only on the cannon courses (Airship Fortress, Waluigi "
                              "Pinball, Maple Treeway)"),
        Field(0x10, "s16", note=f"{_WING_CTOR}: > 0 -> WingPathData +6; VehicleMove +0xE82, read by "
                                "Kart::Vehicle::calcApply"),
        Field(0x12, "u32", note=_NOT_READ)), points="GLPT"),
]
SPEC_BY_NAME = {s.name: s for s in SPECS} | {s.magic: s for s in SPECS}

POTI_ROUTE = (Field(0x0, "u16", "point_num", T), Field(0x2, "u8", "route_setting_1", T),
              Field(0x3, "u8", "route_setting_2", T))
POTI_POINT = (Field(0x0, "vec3", "position", T),
              Field(0xC, "u16", "route_point_setting_1", T, note="speed according to the community tools"),
              Field(0xE, "u16", "route_point_setting_2", T))


def spec(name: str) -> Spec:
    s = SPEC_BY_NAME.get(name.upper())
    if not s:
        raise SystemExit(f"unknown KMP section {name!r}; known: {', '.join(s.name for s in SPECS)}")
    return s


# ---- parsing -----------------------------------------------------------------
@dataclass
class Entry:
    index: int
    offset: int                 # in the file
    values: dict                # Field -> value (tuple for vectors and arrays)
    raw: bytes = b""            # entries of sections without a layout
    points: list = field(default_factory=list)  # POTI: the route's points


@dataclass
class Section:
    spec: Spec
    offset: int                 # of the section header, in the file
    count: int
    extra: int
    stride: int
    end: int                    # end of the bytes the section owns (next section or end of file)
    entries: list = field(default_factory=list)
    problems: list = field(default_factory=list)


class Kmp:
    def __init__(self, data: bytes, path: Path | None = None):
        if data[:4] != MAGIC:
            raise SystemExit(f"{path or 'data'}: not a KMP file (no DMDC signature)")
        self.data = data
        self.path = path
        self.file_size, n, self.header_size, self.version = struct.unpack_from("<IHHI", data, 4)
        self.offsets = list(struct.unpack_from(f"<{n}I", data, 0x10))
        self.sections: dict[str, Section] = {}
        self.unknown_sections: list[tuple[str, int]] = []
        self.covered: list[tuple[int, int, str]] = [(0, 0x10 + 4 * n, "header")]
        starts = sorted(self.header_size + o for o in self.offsets)
        for rel_off in self.offsets:
            off = self.header_size + rel_off
            magic = data[off:off + 4].decode("ascii", "replace")
            s = SPEC_BY_NAME.get(magic)
            if not s or s.magic != magic:
                self.unknown_sections.append((magic, off))
                continue
            end = next((x for x in starts if x > off), len(data))
            count, extra = struct.unpack_from("<HH", data, off + 4)
            sec = Section(s, off, count, extra, s.entry_size(self.version), end)
            self.covered.append((off, off + 8, f"{s.name} header"))
            if s.name == "POTI":
                self._read_poti(sec)
            else:
                self._read_entries(sec)
            self.sections[s.name] = sec

    def _read_entries(self, sec: Section):
        stride = sec.stride
        if not stride and sec.count:
            stride = (sec.end - sec.offset - 8) // sec.count
            sec.stride = stride
            sec.problems.append(f"no known entry size; assumed 0x{stride:X} from the section length")
        pos = sec.offset + 8
        if pos + sec.count * stride > len(self.data):
            sec.problems.append("entries run past the end of the file; truncated")
        for i in range(sec.count):
            if pos + stride > len(self.data):
                break
            values = {f: _unpack(self.data, pos + f.off, f) for f in sec.spec.fields if f.off + f.size <= stride}
            raw = b"" if sec.spec.fields else self.data[pos:pos + stride]
            sec.entries.append(Entry(i, pos, values, raw))
            pos += stride
        self.covered.append((sec.offset + 8, pos, sec.spec.name))

    def _read_poti(self, sec: Section):
        pos, total = sec.offset + 8, 0
        for i in range(sec.count):
            route = Entry(i, pos, {f: _unpack(self.data, pos + f.off, f) for f in POTI_ROUTE})
            pos += 4
            for k in range(route.values[POTI_ROUTE[0]]):
                route.points.append(Entry(total, pos, {f: _unpack(self.data, pos + f.off, f) for f in POTI_POINT}))
                pos, total = pos + 0x10, total + 1
            sec.entries.append(route)
        if total != sec.extra:
            sec.problems.append(f"the header says {sec.extra} points, the routes hold {total}")
        self.covered.append((sec.offset + 8, pos, "POTI"))

    def point_owners(self, point_section: str) -> dict[int, tuple[int, int]]:
        """Point index -> (path index, index inside the path), from the path section grouping it."""
        s = SPEC_BY_NAME[point_section]
        paths_ = self.sections.get(s.path)
        out: dict[int, tuple[int, int]] = {}
        if not paths_:
            return out
        for e in paths_.entries:
            start, num = e.values[paths_.spec.fields[0]], e.values[paths_.spec.fields[1]]
            for k in range(num):
                out.setdefault(start + k, (e.index, k))
        return out

    def uncovered(self) -> list[tuple[int, int]]:
        """Byte ranges of the file that no header or entry accounts for."""
        out, pos = [], 0
        for start, end, _ in sorted(self.covered):
            if start > pos:
                out.append((pos, start))
            pos = max(pos, end)
        if pos < len(self.data):
            out.append((pos, len(self.data)))
        return out


def _unpack(data: bytes, off: int, f: Field):
    v = struct.unpack_from(f.fmt, data, off)
    return v if f.count > 1 or f.type.startswith("vec") else v[0]


# ---- formatting ----------------------------------------------------------------
def fmt_float(x: float) -> str:
    """Shortest text that reads back as the same 32-bit float."""
    packed = struct.pack("<f", x)
    for digits in range(6, 10):
        text = f"{x:.{digits}g}"
        if struct.pack("<f", float(text)) == packed:
            break
    if "e" not in text and "." not in text and "n" not in text:
        text += ".0"
    return text


class Names:
    """Enumerator names for the `enum:` and `flags:` fields, read once from template/."""

    def __init__(self):
        self.cache: dict[str, dict[int, str]] = {}

    def get(self, name: str) -> dict[int, str]:
        if name not in self.cache:
            self.cache[name] = BUILTIN_FLAGS.get(name) or templates.read_enum(name)
        return self.cache[name]


def fmt_value(f: Field, v, names: Names) -> str:
    if f.type.startswith("vec"):
        return "(" + ", ".join(fmt_float(x) for x in v) + ")"
    if f.scalar == "f32":
        return fmt_float(v)
    width = int(f.scalar[1:]) // 4
    hexed = not f.name or f.show == "hex"
    if f.show == "links":
        none = (1 << (width * 4)) - 1
        items = list(v)
        while items and items[-1] == none:
            items.pop()
        return "[" + ", ".join("-" if x == none else str(x) for x in items) + "]"
    if isinstance(v, tuple):
        return "[" + ", ".join(f"0x{x & ((1 << width * 4) - 1):0{width}X}" if hexed else str(x) for x in v) + "]"
    if f.show.startswith("enum:"):
        return f"{v} ({names.get(f.show[5:]).get(v, '?')})"
    if f.show.startswith("flags:"):
        table, parts, rest = names.get(f.show[6:]), [], v
        for bit, n in sorted(table.items()):
            if bit and v & bit == bit:
                parts.append(n)
                rest &= ~bit
        if rest:
            parts.append(f"0x{rest:X}")
        return f"0x{v:0{width}X} ({'|'.join(parts) or '-'})"
    if hexed:
        return f"0x{v & ((1 << width * 4) - 1):0{width}X}"
    return str(v)


def fmt_entry(e: Entry, fields: tuple, names: Names, prefix: str = "") -> str:
    parts = [f"[{e.index}]", f"@0x{e.offset:X}"]
    if prefix:
        parts.append(prefix)
    parts += [f"{f.label}={fmt_value(f, e.values[f], names)}" for f in fields if f in e.values]
    if e.raw:
        parts.append("raw=" + e.raw.hex(" "))
    return " ".join(parts)


def parse_selection(text: str) -> tuple[Spec, range | None]:
    """`ENPT`, `ENPT:5` or `ENPT:10-20` (entry indices, inclusive)."""
    name, _, sel = text.partition(":")
    s = spec(name)
    if not sel:
        return s, None
    lo, _, hi = sel.partition("-")
    try:
        return s, range(int(lo, 0), int(hi or lo, 0) + 1)
    except ValueError:
        raise SystemExit(f"bad entry range in {text!r}; use SECTION:N or SECTION:N-M")


def dump(kmp: Kmp, selection: list[tuple[Spec, range | None]] | None = None, origin: str = "") -> list[str]:
    names = Names()
    out = [f"# KMP {paths.rel(kmp.path) if kmp.path else ''}".rstrip()]
    if origin:
        out.append(f"# {origin}")
    size_note = "" if kmp.file_size == len(kmp.data) else f" (the header says 0x{kmp.file_size:X})"
    out.append(f"# version 0x{kmp.version:X}, {len(kmp.offsets)} sections, header 0x{kmp.header_size:X} bytes, "
               f"file 0x{len(kmp.data):X} bytes{size_note}")
    out.append("# names: plain = template/, research not in template/ yet or the game's code, name~ = community tools (hints only), "
               "unk_0x<offset> = unknown (hex); `mk7 kmp fields` lists each field's source")
    if selection is None:
        out.append("")
        out.append("sections (offsets in the file):")
        for sec in kmp.sections.values():
            s = sec.spec
            stride = f"0x{sec.stride:X}" if sec.stride else "var"
            out.append(f"  {s.name} ({s.magic}) @{f'0x{sec.offset:X}':7} {sec.count:4} x {stride:5} "
                       f"extra=0x{sec.extra:04X}  {s.title}" + (f"  [{s.struct}]" if s.struct else ""))
    for magic, off in kmp.unknown_sections:
        out.append(f"  ???? ({magic}) @0x{off:X}  unknown section, not parsed")
    wanted = selection or [(s, None) for s in SPECS]
    for s, rng in wanted:
        sec = kmp.sections.get(s.name)
        out.append("")
        if not sec:
            out.append(f"== {s.name}: not in this file")
            continue
        extra = f", extra 0x{sec.extra:04X}" + (f" = {s.extra}" if s.extra else "")
        out.append(f"== {s.name} ({s.magic}) {s.title}: {sec.count} entries{extra}")
        out.extend(f"   ! {p}" for p in sec.problems)
        if rng is not None and not any(i in rng for i in range(sec.count)):
            out.append(f"   (no entry in {rng.start}..{rng.stop - 1})")
        if s.name == "POTI":
            out.extend(_dump_poti(sec, rng, names))
            continue
        owners = kmp.point_owners(s.name) if s.path else {}
        for e in sec.entries:
            if rng is not None and e.index not in rng:
                continue
            prefix = ""
            if s.path:
                p = owners.get(e.index)
                prefix = f"path {p[0]}[{p[1]}]" if p else "path -"
            elif s.points:
                start, num = e.values[s.fields[0]], e.values[s.fields[1]]
                prefix = f"points {start}..{start + num - 1}" if num else "points -"
            out.append(fmt_entry(e, s.fields, names, prefix))
    if selection is None:
        out.append("")
        gaps = kmp.uncovered()
        if not gaps:
            out.append("# every byte of the file is accounted for")
        for a, b in gaps:
            chunk = kmp.data[a:b]
            what = "zero" if not any(chunk) else chunk[:32].hex(" ") + (" ..." if b - a > 32 else "")
            out.append(f"# not accounted for: 0x{a:X}..0x{b:X} ({b - a} bytes): {what}")
    return out


def _dump_poti(sec: Section, rng: range | None, names: Names) -> list[str]:
    out = []
    for route in sec.entries:
        if rng is not None and route.index not in rng:
            continue
        out.append(fmt_entry(route, POTI_ROUTE, names))
        for k, p in enumerate(route.points):
            values = " ".join(f"{f.label}={fmt_value(f, p.values[f], names)}" for f in POTI_POINT)
            out.append(f"    [{route.index}.{k}] @0x{p.offset:X} point {p.index} {values}")
    return out


def field_table(specs: list[Spec] | None = None) -> list[str]:
    """The layouts this parser uses, with the source of every name."""
    out = ["Sources:"] + [f"  {k}: {v}" for k, v in SOURCES.items()]
    for s in specs or SPECS:
        out.append("")
        size = f"0x{s.size:X} bytes" if s.size else "size unknown" if s.name != "POTI" else "variable"
        older = "".join(f", 0x{sz:X} up to version 0x{v:X}" for v, sz in s.sizes)
        out.append(f"{s.name} ({s.magic} in the file) {s.title}: {size}{older}" + (f"  [{s.struct}]" if s.struct else ""))
        if s.extra:
            out.append(f"  header +0x6 u16: {s.extra}")
        groups = [("", s.fields)] if s.name != "POTI" else [("route", POTI_ROUTE), ("point", POTI_POINT)]
        for label, fields in groups:
            if label:
                out.append(f"  {label}:")
            if not fields:
                out.append("  (no layout: entries are dumped as raw bytes)")
            for f in fields:
                src = f"[{f.src}]" if f.src else "[unknown]"
                show = f" {f.show}" if f.show else ""
                note = f"  -- {f.note}" if f.note else ""
                out.append(f"  0x{f.off:02X} {f.type:8} {f.label:22} {src}{show}{note}")
    return out


# ---- finding the files ---------------------------------------------------------
def course_files(image: str) -> dict[str, dict[str, Path]]:
    """Course name -> {"rom": the KMP in rom:/Course/<c>.szs, "pat1": the v1.2 override in pat1:/Patch} (as found)."""
    root = paths.ROMFS_DIR / image
    out: dict[str, dict[str, Path]] = {}
    for p in sorted((root / "rom" / "Course").glob("*.szs.d/*.kmp")):
        out.setdefault(p.stem, {})["rom"] = p
    for p in sorted((root / "pat1" / "Patch" / "Course").glob("*/*.kmp")):
        out.setdefault(p.stem, {})["pat1"] = p
    return out


def resolve(target: str, image: str, base: bool = False) -> tuple[Path, str]:
    """(KMP file, a line saying where it comes from) for a course name or a path."""
    p = Path(target)
    if p.suffix.lower() == ".kmp" and p.exists():
        return p, ""
    courses = course_files(image)
    if not courses:
        raise SystemExit(f"no KMP files under {paths.rel(paths.ROMFS_DIR / image)}; run `mk7 romfs extract -i {image}`")
    name = next((c for c in courses if c.lower() == target.lower()), None)
    if not name:
        close = [c for c in courses if target.lower() in c.lower()]
        if len(close) == 1:
            name = close[0]
        else:
            hint = ", ".join(close or courses)
            raise SystemExit(f"no course {target!r} in {image}; {'did you mean' if close else 'known'}: {hint}")
    found = courses[name]
    if "pat1" in found and not base:
        return found["pat1"], (f"{image} pat1:/Patch/Course/{name}/{name}.kmp, the v1.2 override of "
                               f"rom:/Course/{name}.szs (--base for the original)")
    if "rom" not in found:
        raise SystemExit(f"{name} has no KMP in rom:/Course/{name}.szs")
    note = " (an override exists in pat1:/Patch; this is the original)" if "pat1" in found else ""
    return found["rom"], f"{image} rom:/Course/{name}.szs/{name}.kmp{note}"
