#!/usr/bin/env python3
"""Draw a scene and menu flow made of BSEQ files (`.brs` / `.bss`) as one PNG image.

Starts at the root file (`<name>-<mode>.brs`), follows every sequence and every scene proxy
(`<proxy name>-<proxy mode>.bss`), and draws one panel per sequence: its children are boxes, the flow list entries are
arrows labelled with `source code -> destination code`. A box that is itself a sequence or a scene points to the panel
that draws it (`see [n]`). Panels are grouped in frames, one per file: the root file runs in the permanent root scene,
every `.bss` in a game scene pushed above it.

Everything drawn comes from the files, except what a game profile adds (`--profile`, a JSON file): the root file name,
the root enter codes the game produces, the scene name -> scene ID table and its default, and the registered page / task /
data holder classes. Without a profile, scenes are shown by name, tasks are not split into instant and lasting, and
unregistered classes are not detected. `mk7_eur2_profile.json` next to this file is the profile of Mario Kart 7 (EUR v1.2).

Usage (from the repository root):

    mk7-llm-research/local/venv/bin/python <this file> [--dir DIR] [--profile JSON] [--root NAME-MODE] [--out PNG] [--all]

    --dir      the folder with the BSEQ files (default: mk7-llm-research/local/romfs/eur2/rom/UI/common.szs.d)
    --profile  game profile (JSON); see mk7_eur2_profile.json for the format
    --root     root file as NAME-MODE (default: from the profile, else the only .brs file of the folder)
    --out      output image (default: game_flow.png next to this file)
    --all      also draw the BSEQ files that the drawn flow never loads

Files whose name is not known (stored by hash in the archive) are found by the SARC hash of `<name>-<mode>.<ext>`.
Needs Pillow. Uses DejaVu Sans when the system has it, Pillow's default font otherwise.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------------------------------------------
# Game knowledge that is not in the files: given by a profile (--profile)

class Profile:
    """Read from a JSON file; every part is optional (see mk7_eur2_profile.json)."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        rf = data.get("root_file") or {}
        self.root_file = (rf["name"], rf["mode"]) if rf.get("name") else None
        rc = data.get("root_enter_codes") or {}
        self.root_codes: set[str] | None = set(rc["produced"]) if rc.get("produced") else None
        self.root_notes: list[str] = list(rc.get("notes", []))
        sc = data.get("scenes") or {}
        self.scene_ids: dict[str, int] = dict(sc.get("ids", {}))
        self.default_scene: str | None = sc.get("default")
        cl = data.get("classes")
        self.classes = None if cl is None else {
            k: set(cl.get(k, [])) for k in ("pages", "instant_tasks", "lasting_tasks", "data_holders")}

    def scene_text(self, name: str) -> str:
        if not self.scene_ids:
            return f"scene {name}"
        if name in self.scene_ids:
            return f"scene {name} (ID {self.scene_ids[name]})"
        d = self.default_scene
        if d in self.scene_ids:
            return f"scene {name}: not a scene name, falls back to {d} (ID {self.scene_ids[d]})"
        return f"scene {name}: not a scene name"


PROFILE = Profile()

SECTION_TYPES = {0: "page", 1: "task", 2: "data holder", 3: "serial", 4: "cross fade", 5: "parallel",
                 6: "delegate", 7: "scene proxy", 8: "root"}


def sarc_hash(name: str) -> int:
    h = 0
    for c in name.encode():
        h = (h * 0x65 + c) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------------------------------------------------------
# BSEQ parsing

@dataclass
class Table:
    default: int
    entries: list[tuple[int, str]]

    def name(self, code_id: int) -> str:
        """Name of an ID the way the game resolves it: unknown IDs fall back to the default entry (marked with ?)."""
        for i, n in self.entries:
            if i == code_id:
                return n
        for i, n in self.entries:
            if i == self.default:
                return n + "?"
        return f"#{code_id}?"


@dataclass
class Block:
    index: int
    section_type: int
    sid: int
    name: str
    enter: Table
    ret: Table
    block_type: int
    # practical
    instances: int = 0
    class_name: str = ""
    modes: Table | None = None
    # sequence, cross fade, proxy
    mode_id: int = 0
    mode_name: str = ""
    subs: list[tuple[int, int]] = field(default_factory=list)
    flows: list[tuple[int, int, int, int, int]] = field(default_factory=list)
    scene_name: str = ""


class Bseq:
    def __init__(self, path: Path, display_name: str):
        self.path = path
        self.display_name = display_name
        d = path.read_bytes()
        if d[:4] != b"BSEQ":
            raise ValueError(f"{path}: not a BSEQ file")
        u16 = lambda o: struct.unpack_from("<H", d, o)[0]
        u32 = lambda o: struct.unpack_from("<I", d, o)[0]
        strings = u32(0x30)

        def cstr(off: int) -> str:
            o = strings + off
            return d[o:d.index(b"\0", o)].decode("ascii", "replace")

        def table(o: int) -> Table:
            return Table(u16(o + 2), [(u16(o + 4 + 4 * i), cstr(u16(o + 6 + 4 * i))) for i in range(u16(o))])

        self.root_id = u32(0x04)
        self.root_mode = u16(0x08)
        ec = u32(0x2C)
        self.engines = [(cstr(u16(ec + 4 * i)), cstr(u16(ec + 4 * i + 2))) for i in range(u16(0x1E))]
        self.blocks: list[Block] = []
        for i in range(u16(0x1C)):
            o = u32(0x34 + 4 * i)
            b = Block(i, d[o], u32(o + 4), cstr(u16(o + 8)), table(o + u16(o + 0xA)), table(o + u16(o + 0xC)),
                      u16(o + 0xE))
            p = o + u16(o + 0x10)
            if b.block_type < 2:
                b.instances, b.class_name = u16(p), cstr(u16(p + 2))
                b.modes = table(p + u16(p + 4))
            else:
                b.mode_id, b.mode_name = u16(p), cstr(u16(p + 2))
                if b.block_type in (2, 3):
                    sl, fl = p + u16(p + 4), p + u16(p + 6)
                    b.subs = [(u32(sl + 4 + 8 * k), u16(sl + 8 + 8 * k)) for k in range(u16(sl))]
                    size = 8 if b.block_type == 2 else 12
                    for k in range(u16(fl)):
                        e = fl + 4 + size * k
                        s, sc, t, tc = struct.unpack_from("<hHhH", d, e)
                        b.flows.append((s, sc, t, tc, d[e + 8] if size == 12 else 0))
                elif b.block_type == 4:
                    b.scene_name = cstr(u16(p + 4))
            self.blocks.append(b)

    # SequenceResource::searchSectionType / searchPracticalSectionBlock / searchSequenceBlock
    def section_type(self, sid: int) -> int:
        if sid == self.root_id:
            return 5
        return next((b.section_type for b in self.blocks if b.sid == sid), -1)

    def practical(self, sid: int) -> Block | None:
        return next((b for b in self.blocks if b.sid == sid and b.section_type < 3), None)

    def sequence(self, sid: int, mode: int) -> Block | None:
        return next((b for b in self.blocks if b.sid == sid and b.block_type in (2, 3, 4) and b.mode_id == mode), None)

    def root(self) -> Block | None:
        return self.sequence(self.root_id, self.root_mode)


class Library:
    """The BSEQ files of one unpacked common.szs, by name (resolving hash-named files)."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.cache: dict[str, Bseq | None] = {}

    def load(self, name: str, mode: str, ext: str) -> Bseq | None:
        fname = f"{name}-{mode}.{ext}"
        if fname not in self.cache:
            path = self.dir / fname
            if not path.exists():
                path = self.dir / f"0x{sarc_hash(fname):08X}"
            self.cache[fname] = Bseq(path, fname) if path.exists() else None
        return self.cache[fname]

    def all_files(self) -> list[Path]:
        out = []
        for p in sorted(self.dir.iterdir()):
            if p.is_file():
                with p.open("rb") as f:
                    if f.read(4) == b"BSEQ":
                        out.append(p)
        return out


# ---------------------------------------------------------------------------------------------------------------
# Panels: one per sequence block, found by walking from the root

@dataclass
class Child:
    index: int
    sid: int
    name: str
    kind: str              # page, instant, lasting, task, dummy, holder, serial, parallel, crossfade, delegate, proxy, missing
    lines: list[str]
    enter: Table | None
    ret: Table | None
    panel: "Panel | None" = None


@dataclass
class Panel:
    number: int
    bseq: Bseq
    block: Block
    kind: str
    is_file_root: bool
    children: list[Child] = field(default_factory=list)
    used_by: list["Panel"] = field(default_factory=list)
    scene_name: str = ""                   # scene a .bss root is run in (from the proxy that loads it)
    depth: int = 0                         # nesting depth inside its file (0: the file's root)
    parent: "Panel | None" = None          # panel that holds this one inside the same file
    path: list[str] = field(default_factory=list)


class Walker:
    def __init__(self, lib: Library):
        self.lib = lib
        self.panels: list[Panel] = []
        self.by_key: dict[tuple, Panel] = {}

    def panel_for(self, bseq: Bseq, block: Block, kind: str, is_root: bool, parent: "Panel | None",
                  scene_name: str = "") -> Panel:
        key = (bseq.display_name, block.sid, block.mode_id)
        if key in self.by_key:
            p = self.by_key[key]
            if parent is not None and parent not in p.used_by:
                p.used_by.append(parent)
            return p
        p = Panel(len(self.panels) + 1, bseq, block, kind, is_root, scene_name=scene_name)
        if parent is not None:
            p.used_by.append(parent)
        self.panels.append(p)
        self.by_key[key] = p
        for i, (sid, mode) in enumerate(block.subs):
            p.children.append(self.child(bseq, p, i, sid, mode))
        return p

    def child(self, bseq: Bseq, parent: Panel, i: int, sid: int, mode: int) -> Child:
        st = bseq.section_type(sid)
        if st in (0, 1, 2):
            b = bseq.practical(sid)
            if b is None:
                return Child(i, sid, f"0x{sid:08X}", "missing", ["no block with this ID"], None, None)
            cls = b.class_name
            mode_name = b.modes.name(mode) if b.modes else "?"
            known = PROFILE.classes
            if known is None:
                kind, what = {0: "page", 1: "task", 2: "holder"}[st], f"{SECTION_TYPES[st]} {cls}"
            elif st == 0:
                kind, what = ("page", f"page {cls}") if cls in known["pages"] else ("dummy", f"page {cls} (unregistered)")
            elif st == 1:
                if cls in known["instant_tasks"]:
                    kind, what = "instant", f"instant task {cls}"
                elif cls in known["lasting_tasks"]:
                    kind, what = "lasting", f"lasting task {cls}"
                else:
                    kind, what = "dummy", f"task {cls} (unregistered)"
            else:
                kind, what = (("holder", f"data holder {cls}") if cls in known["data_holders"]
                              else ("dummy", f"data holder {cls} (unregistered)"))
            lines = [what] + ([f"mode {mode_name}"] if mode_name != "Default" else [])
            return Child(i, sid, b.name, kind, lines, b.enter, b.ret)
        b = bseq.sequence(sid, mode)
        if b is None:
            return Child(i, sid, f"0x{sid:08X}", "missing", [f"no block for mode {mode}"], None, None)
        if st == 7:
            c = Child(i, sid, b.name, "proxy", [], b.enter, b.ret)
            scene = PROFILE.scene_text(b.scene_name)
            target = self.lib.load(b.name, b.mode_name, "bss")
            fname = f"{b.name}-{b.mode_name}.bss"
            if target is None or target.root() is None:
                c.lines = [scene, f"{fname} (missing)"]
            else:
                c.panel = self.panel_for(target, target.root(), "parallel", True, parent, b.scene_name)
                c.lines = [scene, fname]
            return c
        kind = {3: "serial", 4: "crossfade", 5: "parallel", 6: "delegate"}.get(st, "missing")
        c = Child(i, sid, b.name, kind, [f"{SECTION_TYPES.get(st, '?')} sequence"], b.enter, b.ret)
        if b.mode_name != "Default":
            c.lines.append(f"mode {b.mode_name}")
        c.panel = self.panel_for(bseq, b, kind, False, parent)
        return c


# ---------------------------------------------------------------------------------------------------------------
# Drawing

def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                 "/usr/share/fonts/truetype/dejavu/" + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


F_NODE = load_font(13)
F_NODE_B = load_font(14, True)
F_LABEL = load_font(12)
F_TITLE = load_font(20, True)
F_GROUP = load_font(26, True)
F_SUB = load_font(13)
ARROW = "→"
BACK_ARROW = "←"

BAND = 10                                   # width of the side band of sequence boxes
BAND_KINDS = ("serial", "parallel", "crossfade", "delegate")
STACK = 4                                   # offset of the stacked outlines of scene proxy boxes
GROUP_COLORS = {"root": ("#eef1f5", "#1d2833"), "game": ("#fbf1f1", "#b33b3b"), "unused": ("#f2f2f2", "#8a8a8a")}
PANEL_FRAME = {"parallel": "#6d45a3", "serial": "#3c8a32", "crossfade": "#9a8a1f", "delegate": "#9a8a1f"}
COLORS = {
    "page": ("#d6e6ff", "#3b6db3"), "instant": ("#ffe6bf", "#b8761a"), "lasting": ("#ffcf99", "#a65a00"),
    "dummy": ("#e4e4e4", "#888888"), "serial": ("#d7f2d2", "#3c8a32"), "parallel": ("#e8dbf7", "#6d45a3"),
    "crossfade": ("#f6f1c9", "#9a8a1f"), "delegate": ("#f6f1c9", "#9a8a1f"), "proxy": ("#ffd6d6", "#b33b3b"),
    "missing": ("#ffffff", "#ff0000"), "io": ("#3a3a3a", "#000000"),
    "task": ("#ffdcae", "#a66a1c"), "holder": ("#eaf3e3", "#6b8a55"),
}
# normal/back: taken when the source ends with that code (a player choice, a task's result, ...)
# auto/default: taken automatically when the sequence is entered (default = parallel child started without an entry)
# dead: root enter codes that eur2 never produces
EDGE_COLORS = {"normal": "#33475b", "back": "#d9730d", "auto": "#0f8b8d", "default": "#0f8b8d", "dead": "#c4c4c4"}
DASHED = ("default", "dead")
BG = "#ffffff"
PANEL_BG = "#fbfbfb"

PAD = 8
LINE_H = 16
LABEL_LINE_H = 15
NODE_GAP_Y = 22
LABEL_GAP_Y = 8
LABEL_MARGIN_X = 46
PORT_GAP = 10                               # vertical distance between arrow ends on the side of a box
DOT_R = 3.5
TITLE_H = 58
PANEL_MARGIN = 24


def text_w(font, s: str) -> float:
    return font.getlength(s)


@dataclass
class Node:
    key: object
    lines: list[tuple[str, object]]        # (text, font)
    kind: str
    w: float = 0
    h: float = 0
    layer: int = 0
    x: float = 0
    y: float = 0                           # top
    dummy: bool = False

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Edge:
    src: object
    dst: object
    codes: list[tuple[str, str]]           # (source code, destination code) of each flow entry
    style: str
    reversed: bool = False
    chain: list[object] = field(default_factory=list)
    label_seg: int = 0                     # segment of the chain that carries the label (next to the real source)
    label_box: tuple[float, float, float, float] | None = None

    @property
    def labels(self) -> list[str]:
        """Label lines read in the direction of the arrow: `from -> to`, or `to <- from` on arrows pointing left."""
        return [f"{a} {m} {b}" for a, m, b in self.columns]

    @property
    def columns(self) -> list[tuple[str, str, str]]:
        """(left, arrow, right) of each label line. Exit codes stay on the side of the source box, enter codes on the
        side of the destination box."""
        if self.reversed:
            return [(d, BACK_ARROW, s) for s, d in self.codes]
        return [(s, ARROW, d) for s, d in self.codes]

    def label_width(self) -> float:
        cols = self.columns
        return (max(text_w(F_LABEL, a) for a, _, _ in cols) + text_w(F_LABEL, f" {ARROW} ")
                + max(text_w(F_LABEL, b) for _, _, b in cols) + 2 * 6)


class PanelLayout:
    def __init__(self, panel: Panel):
        self.panel = panel
        blk = panel.block
        self.nodes: dict[object, Node] = {}
        enter_lines = [("ENTER", F_NODE_B)]
        if self.is_game_root() and PROFILE.root_codes:
            enter_lines.append(("game starts with", F_NODE))
            enter_lines.append((" / ".join(sorted(PROFILE.root_codes)), F_NODE))
            enter_lines += [(f"({note})", F_NODE) for note in PROFILE.root_notes]
        self.enter_ctx, self.return_ctx = self.context()
        self.add_node("IN", enter_lines + self.enter_ctx, "io")
        loops: dict[int, list[str]] = {}
        for c in panel.children:
            lines = [(c.name, F_NODE_B)] + [(s, F_NODE) for s in c.lines]
            if c.panel is not None:
                lines.append((f"see [{c.panel.number}]", F_NODE_B))
            self.add_node(c.index, lines, c.kind)
        self.add_node("OUT", [("RETURN", F_NODE_B)] + self.return_ctx, "io")

        def code_name(table: Table | None, cid: int) -> str:
            return table.name(cid) if table else f"#{cid}"

        agg: dict[tuple, Edge] = {}
        has_in: set[int] = set()
        for s, sc, t, tc, cf in blk.flows:
            src = "IN" if s == -1 else s
            dst = "OUT" if t == -1 else t
            sname = code_name(blk.enter, sc) if s == -1 else code_name(self.child(s).ret, sc)
            dname = code_name(blk.ret, tc) if t == -1 else code_name(self.child(t).enter, tc)
            if blk.block_type == 3:
                dname += f" (fade {cf})"
            if src == dst:
                loops.setdefault(src, []).append(f"{sname} {ARROW} {dname}")
                continue
            if src == "IN" and dst != "OUT":
                has_in.add(dst)
            style = "auto" if src == "IN" else "normal"
            if src == "IN" and self.is_game_root() and PROFILE.root_codes and sname not in PROFILE.root_codes:
                style = "dead"
            key = (src, dst, style)
            if key not in agg:
                agg[key] = Edge(src, dst, [], style)
            agg[key].codes.append((sname, dname))
        if panel.kind == "parallel":
            # every child of a parallel sequence is started; without an entry it gets its default enter code
            for c in panel.children:
                if c.index not in has_in:
                    dflt = c.enter.name(c.enter.default) if c.enter else "?"
                    agg[("IN", c.index, "default")] = Edge("IN", c.index, [("(always)", dflt)], "default")
        for k, lines in loops.items():
            n = self.nodes[k]
            n.lines.append(("self:", F_NODE_B))
            n.lines += [(s, F_NODE) for s in lines]
        self.edges = list(agg.values())
        for n in self.nodes.values():
            self.measure(n)
        self.layout()

    def context(self) -> tuple[list, list]:
        """Lines for the ENTER and RETURN boxes: the panels that hold this sequence, i.e. where it is entered from and
        where it returns to (for a file root: the panel holding its proxy)."""
        me = self.panel
        parents = [p for p in me.used_by if any(c.panel is me for c in p.children)]
        enter = [(f"from [{p.number}] {p.block.name}", F_NODE) for p in parents]
        ret = [(f"to [{p.number}] {p.block.name}", F_NODE) for p in parents]
        if not parents:
            ret = [("ends the flow", F_NODE)]
        return enter, ret

    def is_game_root(self) -> bool:
        return self.panel.is_file_root and not self.panel.used_by and self.panel.bseq.display_name.endswith(".brs")

    def child(self, i: int) -> Child:
        return self.panel.children[i]

    def add_node(self, key, lines, kind):
        self.nodes[key] = Node(key, list(lines), kind)

    @staticmethod
    def measure(n: Node):
        if n.dummy:
            n.w, n.h = 0, 6
            return
        n.w = max(110, max(text_w(f, s) for s, f in n.lines) + 2 * PAD + text_offset(n.kind))
        n.h = len(n.lines) * LINE_H + 2 * PAD

    # -- layering -------------------------------------------------------------------------------------------
    def layout(self):
        keys = list(self.nodes)
        succ: dict[object, list[Edge]] = {k: [] for k in keys}
        for e in self.edges:
            succ[e.src].append(e)
        # back edges: DFS from IN, then from anything not reached
        state: dict[object, int] = {}
        order: list[object] = []

        def dfs(start):
            stack = [(start, iter(succ[start]))]
            state[start] = 1
            order.append(start)
            while stack:
                node, it = stack[-1]
                for e in it:
                    v = e.dst
                    if state.get(v) == 1:
                        e.reversed = True
                    elif v not in state:
                        state[v] = 1
                        order.append(v)
                        stack.append((v, iter(succ[v])))
                        break
                else:
                    state[node] = 2
                    stack.pop()

        dfs("IN")
        for k in keys:
            if k not in state and k != "OUT":
                dfs(k)
        if "OUT" not in state:
            order.append("OUT")
        # longest path on the DAG (reversed back edges)
        dag = [(e.dst, e.src) if e.reversed else (e.src, e.dst) for e in self.edges]
        layer = {k: 0 for k in keys}
        for _ in range(len(keys) + 1):
            changed = False
            for u, v in dag:
                if v != "OUT" and layer[v] < layer[u] + 1:
                    layer[v] = layer[u] + 1
                    changed = True
            if not changed:
                break
        for k in keys:
            if k not in ("IN", "OUT") and layer[k] == 0:
                layer[k] = 1
        layer["OUT"] = max([layer[k] for k in keys if k != "OUT"] + [0]) + 1
        for k, n in self.nodes.items():
            n.layer = layer[k]
        # local ENTER / RETURN boxes instead of long edges from ENTER and to RETURN
        partner: dict[object, object] = {}
        for e in self.edges:
            if e.src == "IN" and layer[e.dst] > 1:
                sk = ("IN", e.dst)
                if sk not in self.nodes:
                    self.add_node(sk, [("ENTER", F_NODE_B)] + self.enter_ctx, "io")
                    self.measure(self.nodes[sk])
                    self.nodes[sk].layer = layer[sk] = layer[e.dst] - 1
                    partner[sk] = e.dst
                e.src = sk
            elif e.dst == "OUT" and layer[e.src] < layer["OUT"] - 1:
                sk = ("OUT", e.src)
                if sk not in self.nodes:
                    self.add_node(sk, [("RETURN", F_NODE_B)] + self.return_ctx, "io")
                    self.measure(self.nodes[sk])
                    self.nodes[sk].layer = layer[sk] = layer[e.src] + 1
                    partner[sk] = e.src
                e.dst = sk
        if not any(e.dst == "OUT" for e in self.edges) and any(k[0] == "OUT" for k in partner):
            del self.nodes["OUT"]
        # dummy nodes for long edges
        dcount = 0
        for e in self.edges:
            a, b = (e.dst, e.src) if e.reversed else (e.src, e.dst)
            chain = [a]
            for lyr in range(self.nodes[a].layer + 1, self.nodes[b].layer):
                dk = ("dummy", dcount)
                dcount += 1
                self.nodes[dk] = Node(dk, [], "dummy", layer=lyr, dummy=True)
                self.measure(self.nodes[dk])
                chain.append(dk)
            chain.append(b)
            e.chain = chain
            e.label_seg = len(chain) - 2 if e.reversed else 0
        nl = max(n.layer for n in self.nodes.values()) + 1
        self.layers: list[list[object]] = [[] for _ in range(nl)]
        rank = {k: i for i, k in enumerate(order)}
        for sk, k in partner.items():
            rank[sk] = rank.get(k, 10**6) + 0.5
        for k, n in sorted(self.nodes.items(), key=lambda kv: (rank.get(kv[0], 10**6), str(kv[0]))):
            self.layers[n.layer].append(k)
        # neighbours between adjacent layers
        self.up: dict[object, list[object]] = {k: [] for k in self.nodes}
        self.down: dict[object, list[object]] = {k: [] for k in self.nodes}
        for e in self.edges:
            for a, b in zip(e.chain, e.chain[1:]):
                self.down[a].append(b)
                self.up[b].append(a)
        # arrows end at their own point on the side of a box: make crowded boxes tall enough
        for k, nd in self.nodes.items():
            if not nd.dummy:
                nd.h = max(nd.h, (max(len(self.down[k]), len(self.up[k])) + 1) * PORT_GAP)
        self.order_layers()
        self.place()

    def crossings(self, li: int) -> int:
        """Number of edge crossings between layer li and li + 1."""
        if li < 0 or li + 1 >= len(self.layers):
            return 0
        pos_b = {k: i for i, k in enumerate(self.layers[li + 1])}
        segs = [(i, pos_b[b]) for i, a in enumerate(self.layers[li]) for b in self.down[a] if b in pos_b]
        c = 0
        for i in range(len(segs)):
            ai, bi = segs[i]
            for aj, bj in segs[i + 1:]:
                if (ai - aj) * (bi - bj) < 0:
                    c += 1
        return c

    def total_crossings(self) -> int:
        return sum(self.crossings(li) for li in range(len(self.layers) - 1))

    def order_layers(self):
        """Barycentre sweeps, keeping the best order seen, then swaps of neighbouring boxes while that removes crossings."""
        pos = {}
        for lst in self.layers:
            for i, k in enumerate(lst):
                pos[k] = i
        best = [list(lst) for lst in self.layers]
        best_c = self.total_crossings()
        for it in range(24):
            rng = range(1, len(self.layers)) if it % 2 == 0 else range(len(self.layers) - 2, -1, -1)
            for li in rng:
                nb = self.up if it % 2 == 0 else self.down
                lst = self.layers[li]
                bary = {}
                for k in lst:
                    ps = [pos[x] for x in nb[k]]
                    bary[k] = sum(ps) / len(ps) if ps else pos[k]
                lst.sort(key=lambda k: (bary[k], pos[k]))
                for i, k in enumerate(lst):
                    pos[k] = i
            c = self.total_crossings()
            if c < best_c:
                best, best_c = [list(lst) for lst in self.layers], c
        self.layers = best
        improved = True
        while improved:
            improved = False
            for li, lst in enumerate(self.layers):
                for i in range(len(lst) - 1):
                    before = self.crossings(li - 1) + self.crossings(li)
                    lst[i], lst[i + 1] = lst[i + 1], lst[i]
                    if self.crossings(li - 1) + self.crossings(li) < before:
                        improved = True
                    else:
                        lst[i], lst[i + 1] = lst[i + 1], lst[i]

    # -- coordinates ----------------------------------------------------------------------------------------
    def place(self):
        n = self.nodes
        # initial stacking
        for lst in self.layers:
            y = 0.0
            for k in lst:
                n[k].y = y
                y += n[k].h + NODE_GAP_Y
        for it in range(8):
            down = it % 2 == 0
            rng = range(1, len(self.layers)) if down else range(len(self.layers) - 2, -1, -1)
            nb = self.up if down else self.down
            for li in rng:
                lst = self.layers[li]
                desired = []
                for k in lst:
                    ps = [n[x].cy for x in nb[k]]
                    desired.append(sum(ps) / len(ps) - n[k].h / 2 if ps else n[k].y)
                self.pack(lst, desired)
        top = min(nd.y for nd in n.values())
        for nd in n.values():
            nd.y += TITLE_H - top
        # x: columns and label gaps
        lab_font_w = {}
        for e in self.edges:
            lab_font_w[id(e)] = e.label_width()
        colw = [max([n[k].w for k in lst] + [0]) for lst in self.layers]
        gapw = []
        for li in range(len(self.layers) - 1):
            ws = [lab_font_w[id(e)] for e in self.edges if n[e.chain[e.label_seg]].layer == li]
            gapw.append((max(ws) if ws else 0) + 2 * LABEL_MARGIN_X)
        x = PANEL_MARGIN
        self.col_x = []
        for li, lst in enumerate(self.layers):
            self.col_x.append(x)
            for k in lst:
                n[k].x = x + (colw[li] - n[k].w) / 2
            x += colw[li]
            if li < len(gapw):
                x += gapw[li]
        self.colw = colw
        self.width = x + PANEL_MARGIN
        # labels in the gap after the first node of each edge
        bottom = max(nd.y + nd.h for nd in n.values())
        for li in range(len(self.layers) - 1):
            es = [e for e in self.edges if n[e.chain[e.label_seg]].layer == li]
            items = []
            for e in es:
                a, b = n[e.chain[e.label_seg]], n[e.chain[e.label_seg + 1]]
                h = len(e.labels) * LABEL_LINE_H + 6
                items.append((a.cy * 0.5 + b.cy * 0.5 - h / 2, h, e))
            items.sort(key=lambda t: t[0])
            # where the other edges cross the middle of this gap: label boxes keep clear of those heights
            blocked = []
            for e in self.edges:
                for i in range(len(e.chain) - 1):
                    a, b = n[e.chain[i]], n[e.chain[i + 1]]
                    if a.layer == li and i != e.label_seg:
                        mid, spread = (a.cy + b.cy) / 2, abs(a.cy - b.cy) * 0.3 + 6
                        blocked.append((mid - spread, mid + spread))
            gx0 = self.col_x[li] + colw[li] + LABEL_MARGIN_X
            # biggest labels first; each takes the free height nearest to where it wants to be
            for want, h, e in sorted(items, key=lambda t: -t[1]):
                want = max(want, TITLE_H)
                cands = [want] + [b1 + LABEL_GAP_Y for _, b1 in blocked] + [b0 - h - LABEL_GAP_Y for b0, _ in blocked]
                free = [c for c in cands if c >= TITLE_H and all(c >= b1 or c + h <= b0 for b0, b1 in blocked)]
                y = min(free, key=lambda c: abs(c - want))
                blocked.append((y - LABEL_GAP_Y / 2, y + h + LABEL_GAP_Y / 2))
                w = lab_font_w[id(e)]
                e.label_box = (gx0, y, gx0 + w, y + h)
                bottom = max(bottom, y + h)
        self.height = bottom + PANEL_MARGIN
        self.assign_ports()

    def assign_ports(self):
        """Give every arrow its own end point on the side of a box, ordered by where the arrow goes."""
        n = self.nodes
        sides: dict[tuple, list] = {}
        for e in self.edges:
            lc = (e.label_box[1] + e.label_box[3]) / 2
            for i in range(len(e.chain) - 1):
                a, b = e.chain[i], e.chain[i + 1]
                sides.setdefault((a, "out"), []).append((lc if i == e.label_seg else n[b].cy, (id(e), i, "out")))
                sides.setdefault((b, "in"), []).append((lc if i == e.label_seg else n[a].cy, (id(e), i, "in")))
        self.ports: dict[tuple, float] = {}
        for (k, _), items in sides.items():
            nd = n[k]
            items.sort(key=lambda t: t[0])
            for j, (_, key) in enumerate(items):
                self.ports[key] = nd.cy if nd.dummy else nd.y + nd.h * (j + 1) / (len(items) + 1)

    def pack(self, lst, desired):
        """Place the nodes of a layer in their order, as close to `desired` (tops) as possible without overlap."""
        n = self.nodes
        ys = list(desired)
        for i in range(1, len(lst)):
            ys[i] = max(ys[i], ys[i - 1] + n[lst[i - 1]].h + NODE_GAP_Y)
        # pull the block back up to share the displacement
        shift = sum(ys[i] - desired[i] for i in range(len(lst))) / max(1, len(lst))
        ys2 = [y - shift for y in ys]
        for i in range(len(lst) - 2, -1, -1):
            ys2[i] = min(ys2[i], ys2[i + 1] - n[lst[i]].h - NODE_GAP_Y)
        for i in range(1, len(lst)):
            ys2[i] = max(ys2[i], ys2[i - 1] + n[lst[i - 1]].h + NODE_GAP_Y)
        for k, y in zip(lst, ys2):
            n[k].y = y

    # -- drawing --------------------------------------------------------------------------------------------
    def draw(self, img: Image.Image, ox: float, oy: float, total_w: float):
        d = ImageDraw.Draw(img)
        p = self.panel
        frame = PANEL_FRAME.get(p.kind, "#9aa5b1")
        d.rounded_rectangle((ox, oy, ox + total_w, oy + self.height), 10, fill=PANEL_BG, outline=frame, width=3)
        kind = "parallel sequence (root of the file)" if p.is_file_root else f"{p.kind} sequence"
        d.text((ox + 14, oy + 8), f"[{p.number}]  {p.block.name}", font=F_TITLE, fill="#1d2833")
        sub = f"{kind}, mode {p.block.mode_name}  \u2022  " + "  \u203a  ".join(p.path)
        users = [u for u in p.used_by if u.bseq is p.bseq]
        if users:
            sub += "  \u2022  drawn as a box in " + ", ".join(f"[{u.number}]" for u in users)
        d.text((ox + 14, oy + 33), sub, font=F_SUB, fill="#4a5662")
        n = self.nodes
        for e in self.edges:
            self.draw_edge(d, e, ox, oy)
        for e in self.edges:
            x0, y0, x1, y1 = e.label_box
            col = EDGE_COLORS[e.style if not e.reversed or e.style != "normal" else "back"]
            d.rectangle((ox + x0, oy + y0, ox + x1, oy + y1), fill="#ffffff", outline=col, width=1)
            cols = e.columns
            ax = ox + x0 + 6 + max(text_w(F_LABEL, a) for a, _, _ in cols)
            for i, (a, m, b) in enumerate(cols):
                ty = oy + y0 + 3 + i * LABEL_LINE_H
                d.text((ox + x0 + 6, ty), a, font=F_LABEL, fill=col)
                d.text((ax, ty), f" {m} ", font=F_LABEL, fill=col)
                d.text((ox + x1 - 6 - text_w(F_LABEL, b), ty), b, font=F_LABEL, fill=col)
            lc = oy + (y0 + y1) / 2
            for x in (ox + x0, ox + x1):
                dot(d, x, lc, col)
        for nd in n.values():
            if nd.dummy:
                continue
            draw_box(d, (ox + nd.x, oy + nd.y, ox + nd.x + nd.w, oy + nd.y + nd.h), nd.kind)
            color = "#ffffff" if nd.kind == "io" else ("#7a0000" if nd.kind in ("dummy", "missing") else "#111111")
            tx = ox + nd.x + PAD + text_offset(nd.kind)
            for i, (s, f) in enumerate(nd.lines):
                d.text((tx, oy + nd.y + PAD + i * LINE_H), s, font=f, fill=color)

    def draw_edge(self, d: ImageDraw.ImageDraw, e: Edge, ox: float, oy: float):
        n = self.nodes
        style = e.style
        col = EDGE_COLORS["back" if e.reversed and style == "normal" else style]
        width = 2 if style != "dead" else 1
        first, last = n[e.chain[0]], n[e.chain[-1]]
        # (exit point of chain[i], entry point of chain[i + 1]) for every segment; dummies are crossed horizontally
        exits, entries = [], []
        for i, k in enumerate(e.chain):
            nd = n[k]
            y_in = self.ports.get((id(e), i - 1, "in"), nd.cy)
            y_out = self.ports.get((id(e), i, "out"), nd.cy)
            if nd.dummy:
                cx0 = self.col_x[nd.layer]
                entries.append((cx0, nd.cy))
                exits.append((cx0 + self.colw[nd.layer], nd.cy))
            else:
                entries.append((nd.x, y_in))
                exits.append((nd.x + nd.w, y_out))
        segs = []
        for i in range(len(e.chain) - 1):
            a, b = exits[i], entries[i + 1]
            if i == e.label_seg:
                x0, y0, x1, y1 = e.label_box
                lc = (y0 + y1) / 2
                segs += [(a, (x0, lc)), ((x0, lc), (x1, lc)), ((x1, lc), b)]
            else:
                segs.append((a, b))
            if i + 1 < len(e.chain) - 1:
                segs.append((entries[i + 1], exits[i + 1]))
        for a, b in segs:
            pts = bezier(a, b) if abs(a[1] - b[1]) > 1 else [a, b]
            pts = [(ox + x, oy + y) for x, y in pts]
            if style in DASHED:
                dashed(d, pts, col, width)
            else:
                d.line(pts, fill=col, width=width, joint="curve")
        if e.reversed:
            arrow(d, ox + exits[0][0], oy + exits[0][1], -1, col)
        else:
            arrow(d, ox + entries[-1][0], oy + entries[-1][1], 1, col)


def text_offset(kind: str) -> int:
    return BAND if kind in BAND_KINDS else 0


def draw_box(d, box, kind):
    """A section box. Scene proxies look like a stack of cards (they push a scene); sequences have a side band:
    solid for serial (one lane), striped for parallel (several lanes)."""
    x0, y0, x1, y1 = box
    fill, line = COLORS[kind]
    if kind == "proxy":
        for k in (2, 1):
            off = STACK * k
            d.rounded_rectangle((x0 + off, y0 - off, x1 + off, y1 - off), 7, fill=fill, outline=line, width=1)
    d.rounded_rectangle(box, 7, fill=fill, outline=line, width=2)
    if kind in BAND_KINDS:
        if kind == "parallel":
            for k in range(3):
                bx = x0 + 2 + k * 3.5
                d.rectangle((bx, y0 + 4, bx + 1.5, y1 - 4), fill=line)
        else:
            d.rounded_rectangle((x0 + 1, y0 + 1, x0 + BAND, y1 - 1), 6, fill=line)


def bezier(a, b, steps=24):
    (x0, y0), (x3, y3) = a, b
    dx = max(20.0, (x3 - x0) * 0.5)
    x1, y1, x2, y2 = x0 + dx, y0, x3 - dx, y3
    out = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        out.append((mt ** 3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3,
                    mt ** 3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3))
    return out


def dashed(d, pts, col, width, on=7, off=5):
    acc, draw_on = 0.0, True
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        seg = ((xb - xa) ** 2 + (yb - ya) ** 2) ** 0.5
        pos = 0.0
        while pos < seg:
            step = min((on if draw_on else off) - acc, seg - pos)
            if draw_on and seg > 0:
                t0, t1 = pos / seg, (pos + step) / seg
                d.line([(xa + (xb - xa) * t0, ya + (yb - ya) * t0), (xa + (xb - xa) * t1, ya + (yb - ya) * t1)],
                       fill=col, width=width)
            pos += step
            acc += step
            if acc >= (on if draw_on else off) - 1e-6:
                acc, draw_on = 0.0, not draw_on


def dot(d, x, y, col):
    """Round marker where an arrow's line meets its label box."""
    d.ellipse((x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R), fill=col)


def arrow(d, x, y, direction, col):
    """Arrowhead whose tip is at (x, y), pointing right (1) or left (-1)."""
    s = 9
    d.polygon([(x, y), (x - direction * s, y - s / 2), (x - direction * s, y + s / 2)], fill=col)


# ---------------------------------------------------------------------------------------------------------------
# Legend and assembly

def legend_panel(width: float) -> tuple[float, callable]:
    """Legend: every entry is `term: definition`, generic to the BSEQ system (no game-specific names)."""
    groups = [
        ("Frames", [
            ("frame", "root", "root scene: permanent scene that runs the root file"),
            ("frame", "game", "game scene: scene pushed above the root scene, runs one scene file"),
            ("frame", "unused", "not loaded: file that the drawn flow never loads"),
            ("panel", "parallel", "parallel panel: parallel sequence, indented by nesting depth"),
            ("panel", "serial", "serial panel: serial sequence, indented by nesting depth"),
        ]),
        ("Boxes", [
            ("box", "page", "page: section with a user interface"),
            ("box", "task", "task: section without a user interface"),
            ("box", "instant", "instant task: task that completes in a single step"),
            ("box", "lasting", "lasting task: task that runs until it returns a code"),
            ("box", "dummy", "dummy: unregistered class, never completes"),
            ("box", "serial", "serial sequence: runs one child at a time"),
            ("box", "parallel", "parallel sequence: runs all children at once"),
            ("box", "proxy", "scene proxy: changes scene and runs its scene file"),
            ("box", "io", "ENTER / RETURN: entry and exit of the sequence, with the panel it comes from and returns to"),
        ]),
        ("Arrows", [
            ("edge", "normal", "flow entry: a return code of the source starts the destination"),
            ("edge", "back", "backward flow entry: flow entry to an earlier column"),
            ("edge", "auto", "enter flow entry: an enter code of the sequence starts the destination"),
            ("edge", "default", "implicit start: parallel child started without a flow entry"),
            ("edge", "dead", "unused flow entry: root enter code the game never produces"),
        ]),
        ("Labels", [
            ("label", "normal", f"label: source code {ARROW} destination code"),
            ("label", "back", f"backward label: destination code {BACK_ARROW} source code"),
        ]),
        ("Markers", [
            ("dot", "normal", "dot: where an arrow passes through its label"),
            ("text", "", "self: flow entry that restarts the same child"),
            ("text", "", "see [n]: child drawn in panel n"),
            ("text", "", "?: code not in its table, resolved to the default"),
            ("text", "", "ENTER / RETURN code: enter / return code of the sequence"),
        ]),
    ]
    swatch_w, gap, row_h, head_w = 44, 36, 28, 110
    cell = max(text_w(F_NODE, t) for _, entries in groups for _, _, t in entries) + swatch_w + 8 + gap
    cols = max(1, int((width - head_w - 40) // cell))
    rows = sum((len(entries) + cols - 1) // cols for _, entries in groups)
    h = 48 + rows * row_h + (len(groups) - 1) * 8 + 16

    def swatch(d, kind, key, x, y):
        if kind == "box":
            draw_box(d, (x, y + 4, x + 30, y + 20), key)
        elif kind == "frame":
            fill, line = GROUP_COLORS[key]
            d.rounded_rectangle((x, y, x + 34, y + 20), 5, fill=fill, outline=line, width=3)
        elif kind == "panel":
            d.line([(x + 4, y), (x + 4, y + 10), (x + 12, y + 10)], fill=PANEL_FRAME[key], width=2)
            d.rounded_rectangle((x + 12, y + 2, x + 34, y + 20), 4, fill=PANEL_BG, outline=PANEL_FRAME[key], width=2)
        elif kind == "edge":
            col, pts = EDGE_COLORS[key], [(x, y + 10), (x + 34, y + 10)]
            if key in DASHED:
                dashed(d, pts, col, 2)
            else:
                d.line(pts, fill=col, width=2)
            if key == "back":
                arrow(d, x, y + 10, -1, col)
            else:
                arrow(d, x + 34, y + 10, 1, col)
        elif kind == "label":
            col = EDGE_COLORS[key]
            d.line([(x, y + 10), (x + 34, y + 10)], fill=col, width=2)
            d.rectangle((x + 8, y + 3, x + 26, y + 17), fill="#ffffff", outline=col, width=1)
            dot(d, x + 8, y + 10, col)
            dot(d, x + 26, y + 10, col)
        elif kind == "dot":
            dot(d, x + 17, y + 10, EDGE_COLORS[key])
        # text markers need no swatch: the term itself is the marker

    def draw(img, ox, oy, total_w):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((ox, oy, ox + total_w, oy + h), 10, fill="#f3f6f9", outline="#9aa5b1", width=2)
        d.text((ox + 14, oy + 8), "Scene and menu flow (BSEQ): legend", font=F_TITLE, fill="#1d2833")
        y = oy + 48
        for title, entries in groups:
            d.text((ox + 20, y + 2), title, font=F_NODE_B, fill="#1d2833")
            for i, (kind, key, text) in enumerate(entries):
                col, row = i % cols, i // cols
                x = ox + 20 + head_w + col * cell
                swatch(d, kind, key, x, y + row * row_h)
                d.text((x + swatch_w + 8, y + row * row_h + 2), text, font=F_NODE, fill="#111111")
            y += ((len(entries) + cols - 1) // cols) * row_h + 8

    return h, draw


def build(lib: Library, include_all: bool, root_file: tuple[str, str]) -> list[Panel]:
    w = Walker(lib)
    root = lib.load(root_file[0], root_file[1], "brs")
    if root is None or root.root() is None:
        sys.exit(f"{lib.dir}: {root_file[0]}-{root_file[1]}.brs not found")
    w.panel_for(root, root.root(), "parallel", True, None)
    if include_all:
        seen = {b.path.resolve() for b in lib.cache.values() if b}
        for path in lib.all_files():
            if path.resolve() in seen:
                continue
            b = Bseq(path, path.name)
            # name unnamed files after their root, as the game would look them up
            blk = b.root()
            if blk is not None:
                for ext in ("bss", "brs"):
                    cand = f"{blk.name}-{blk.mode_name}.{ext}"
                    if path.name in (cand, f"0x{sarc_hash(cand):08X}"):
                        b.display_name = cand + ("" if path.name == cand else f" ({path.name})")
                w.panel_for(b, blk, "parallel", True, None)
    return w.panels


GROUP_PAD = 18
GROUP_HEAD = 66
INDENT = 40


@dataclass
class Group:
    kind: str                              # root, game or unused
    file: str
    panels: list[Panel]

    def title(self) -> str:
        if self.kind == "root":
            return f"ROOT SCENE  \u2022  {self.file}"
        if self.kind == "unused":
            return f"NOT LOADED  \u2022  {self.file}"
        return f"GAME SCENE  \u2022  {PROFILE.scene_text(self.panels[0].scene_name or '?')}  \u2022  {self.file}"

    def subtitle(self) -> str:
        root = self.panels[0]
        if self.kind == "root":
            return "always present; runs the root sequence, which pushes one game scene at a time above it"
        if self.kind == "unused":
            return "no proxy of the drawn flow loads this file"
        users = ", ".join(f"[{u.number}]" for u in root.used_by)
        engines = ", ".join(f"{c.replace('EngineCreator', '')} {m}" for c, m in root.bseq.engines)
        return (f"pushed above the root scene by the proxy in {users}; destroyed when it ends"
                + (f"  \u2022  engines: {engines}" if engines else ""))


def group_panels(panels: list[Panel]) -> list[Group]:
    """One group per file, in the order the files are found; panels in nesting order; then renumber everything."""
    by_file: dict[str, list[Panel]] = {}
    for p in panels:
        by_file.setdefault(p.bseq.display_name, []).append(p)
    groups = []
    for name, ps in by_file.items():
        ordered: list[Panel] = []

        def visit(p: Panel, depth: int, path: list[str], parent: "Panel | None"):
            if p in ordered:
                return
            p.depth, p.path, p.parent = depth, path + [p.block.name], parent
            ordered.append(p)
            for c in p.children:
                if c.panel is not None and c.panel.bseq is p.bseq and not c.panel.is_file_root:
                    visit(c.panel, depth + 1, p.path, p)

        for root in [p for p in ps if p.is_file_root] + ps:
            visit(root, 0, [], None)
        if name.endswith(".brs") and not ordered[0].used_by:
            kind = "root"
        else:
            kind = "game" if ordered[0].used_by else "unused"
        groups.append(Group(kind, name, ordered))
    n = 0
    for g in groups:
        for p in g.panels:
            n += 1
            p.number = n
    return groups


def main():
    here = Path(__file__).resolve().parent
    repo = next((p for p in here.parents if (p / "mk7-llm-research").is_dir() and (p / "template").is_dir()), None)
    default_dir = (repo / "mk7-llm-research/local/romfs/eur2/rom/UI/common.szs.d") if repo else None
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, default=default_dir, help="folder with the BSEQ files")
    ap.add_argument("--profile", type=Path, help="game profile (JSON)")
    ap.add_argument("--root", help="root file as NAME-MODE (default: from the profile, else the only .brs file)")
    ap.add_argument("--out", type=Path, default=here / "game_flow.png", help="output PNG")
    ap.add_argument("--all", action="store_true", help="also draw the files the drawn flow never loads")
    args = ap.parse_args()
    if args.dir is None or not args.dir.is_dir():
        sys.exit("give the folder with the BSEQ files with --dir")
    global PROFILE
    if args.profile:
        PROFILE = Profile(json.loads(args.profile.read_text()))
    if args.root:
        root_file = tuple(args.root.rsplit("-", 1))
    elif PROFILE.root_file:
        root_file = PROFILE.root_file
    else:
        brs = sorted(p.stem for p in args.dir.glob("*.brs"))
        if len(brs) != 1:
            sys.exit(f"cannot choose the root file among {brs or 'no .brs files'}: give --root NAME-MODE")
        root_file = tuple(brs[0].rsplit("-", 1))
    panels = build(Library(args.dir), args.all, root_file)
    groups = group_panels(panels)
    layouts = {id(p): PanelLayout(p) for p in panels}
    width = max([max(layouts[id(p)].width + p.depth * INDENT for p in g.panels) + 2 * GROUP_PAD for g in groups]
                + [1800])
    lh, ldraw = legend_panel(width)
    gh = [GROUP_HEAD + sum(layouts[id(p)].height + PANEL_MARGIN for p in g.panels) + GROUP_PAD - PANEL_MARGIN
          for g in groups]
    height = PANEL_MARGIN + lh + PANEL_MARGIN + sum(h + PANEL_MARGIN for h in gh)
    img = Image.new("RGB", (int(width + 2 * PANEL_MARGIN), int(height)), BG)
    d = ImageDraw.Draw(img)
    y = PANEL_MARGIN
    ldraw(img, PANEL_MARGIN, y, width)
    y += lh + PANEL_MARGIN
    for g, h in zip(groups, gh):
        fill, line = GROUP_COLORS[g.kind]
        d.rounded_rectangle((PANEL_MARGIN, y, PANEL_MARGIN + width, y + h), 14, fill=fill, outline=line, width=4)
        d.text((PANEL_MARGIN + GROUP_PAD, y + 10), g.title(), font=F_GROUP, fill=line)
        d.text((PANEL_MARGIN + GROUP_PAD, y + 42), g.subtitle(), font=F_SUB, fill="#333333")
        py = y + GROUP_HEAD
        bottoms: dict[int, float] = {}
        for p in g.panels:
            l = layouts[id(p)]
            x = PANEL_MARGIN + GROUP_PAD + p.depth * INDENT
            if p.parent is not None and id(p.parent) in bottoms:
                # nesting guide: from the bottom of the parent panel, in the gutter left of its children, into this panel
                gx = x - INDENT / 2
                d.line([(gx, bottoms[id(p.parent)]), (gx, py + 22), (x, py + 22)],
                       fill=PANEL_FRAME.get(p.kind, "#9aa5b1"), width=3)
            l.draw(img, x, py, width - 2 * GROUP_PAD - p.depth * INDENT)
            bottoms[id(p)] = py + l.height
            py += l.height + PANEL_MARGIN
        y += h + PANEL_MARGIN
    img.save(args.out, optimize=True)
    print(f"{args.out}: {img.width}x{img.height}, {len(panels)} panels")


if __name__ == "__main__":
    main()
