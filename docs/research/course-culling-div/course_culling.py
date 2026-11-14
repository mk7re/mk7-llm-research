#!/usr/bin/env python3
"""Check Mario Kart 7 course culling data (.div, course model, KMP clip setup) against the game's rules.

The rules are those of the v1.2 game described in README.md next to this file: the quadtree of depth 3 over the
bounding box of the div areas, the leaf cells each area touches, the clip quads that hide whole cells, the view region
built from the camera, and the rule the retail div files were made with.

Commands (COURSE is one or more course names such as Gctr_MarioCircuit, or "all"):

    python3 course_culling.py check COURSE      each div area against the XZ bounding box of its index stream
    python3 course_culling.py rule COURSE       how well the retail rule (8 x 8 grid, triangle centre) explains
                                                the retail div file
    python3 course_culling.py compare COURSE    culling of the retail file and of three ways of dividing the model:
                                                the retail rule, KMPExpander's old 1000-unit split and "by span"
    python3 course_culling.py viewmask CAMERA.json
                                                the visible leaf cells for a camera, as QuadTree::update computes
                                                them (no clip ID); CAMERA.json holds "pos", "dir", "far",
                                                "corners" (8 points), "model_min", "model_max" and "rect"
                                                (min x, min z, max x, max z)

The course files are read from the extracted RomFS (mk7 romfs extract): the folder
local/romfs/eur2/rom/Course/<course>.szs.d/ of mk7-llm-research, found by going up from this file, or --course-dir.

Only the course model (the model named after the course) is read; its vertex buffer must be interleaved, as in every
retail course. Requires Python 3.8+, no other package.
"""

import argparse
import collections
import glob
import json
import math
import os
import struct
import sys

GRID = 8
LEVEL_START = [0, 1, 5, 21, 85]
FLT_EPS = 1.192093e-07


# --- Files -------------------------------------------------------------------------------------------------------

class Reader:
    def __init__(self, data):
        self.d = data

    def u8(self, o):
        return self.d[o]

    def u16(self, o):
        return struct.unpack_from("<H", self.d, o)[0]

    def u32(self, o):
        return struct.unpack_from("<I", self.d, o)[0]

    def f32(self, o):
        return struct.unpack_from("<f", self.d, o)[0]

    def ptr(self, o):
        v = self.u32(o)
        return 0 if v == 0 else o + v

    def lst(self, o):
        n, p = self.u32(o), self.ptr(o + 4)
        return [self.ptr(p + 4 * i) for i in range(n)]

    def string(self, o):
        return self.d[o:self.d.index(b"\0", o)].decode()

    def dict(self, o):
        n = self.u32(o + 8)
        return [(self.string(self.ptr(o + 0x1C + i * 16 + 8)), self.ptr(o + 0x1C + i * 16 + 12)) for i in range(n)]


def read_course_model(path, name):
    """Shapes of the model `name` of a CGFX file: a list (one per shape) of lists (one per index stream, in the
    order of the primitive sets and primitives) of triangles ((x, y, z) * 3)."""
    r = Reader(open(path, "rb").read())
    if r.d[:4] != b"CGFX":
        raise ValueError("%s: not a CGFX file" % path)
    data = r.u16(6)
    models = dict(r.dict(r.ptr(data + 0xC)))
    if name not in models:
        raise ValueError("%s: no model named %s" % (path, name))
    m = models[name]
    shapes = []
    for sh in r.lst(m + 0xC4):
        offset = struct.unpack_from("<3f", r.d, sh + 0x20)
        pos = None
        for vb in r.lst(sh + 0x38):
            if r.u32(vb) == 0x40000002 and r.u32(vb + 4) == 0x15:       # interleaved vertex buffer
                raw, size, stride = r.ptr(vb + 0x18), r.u32(vb + 0x14), r.u32(vb + 0x24)
                for at in r.lst(vb + 0x28):
                    if r.u32(at + 4) == 0:                                # usage: position
                        pos = (raw, size, stride, r.u32(at + 0x24), r.u32(at + 0x28), r.f32(at + 0x2C), r.u32(at + 0x30))
        if pos is None:
            raise ValueError("%s: a shape has no interleaved positions" % path)
        raw, size, stride, fmt, _, scale, at_off = pos
        fc = {0x1400: "b", 0x1401: "B", 0x1402: "h", 0x1403: "H", 0x1406: "f"}[fmt]
        verts = []
        for i in range(size // stride):
            v = struct.unpack_from("<" + fc * 3, r.d, raw + i * stride + at_off)
            verts.append(tuple(v[k] * scale + offset[k] for k in range(3)))
        streams = []
        for ps in r.lst(sh + 0x2C):
            for pr in r.lst(ps + 0xC):
                for ist in r.lst(pr):
                    fmt_i, mode, length, face = r.u32(ist), r.u8(ist + 4), r.u32(ist + 8), r.ptr(ist + 0xC)
                    idx = list(r.d[face:face + length]) if fmt_i == 0x1401 else list(struct.unpack_from("<%dH" % (length // 2), r.d, face))
                    streams.append([tuple(verts[i] for i in t) for t in triangles(mode, idx)])
        shapes.append(dict(streams=streams, vertex_num=len(verts)))
    return shapes


def triangles(mode, idx):
    if mode == 0:
        return [tuple(idx[i:i + 3]) for i in range(0, len(idx) - 2, 3)]
    if mode == 1:                                                         # strip
        out = []
        for i in range(len(idx) - 2):
            a, b, c = idx[i:i + 3]
            if a != b and b != c and a != c:
                out.append((a, b, c) if i % 2 == 0 else (b, a, c))
        return out
    raise ValueError("primitive mode %d" % mode)


def read_div(path):
    """The div file: a list (one per shape) of (vertex count, [(min x, min z, max x, max z), ...])."""
    r = Reader(open(path, "rb").read())
    if r.d[:4] != b"BADC" or r.d[0x10:0x14] != b"PAHS":
        raise ValueError("%s: not a div file" % path)
    off, out = 0x18, []
    for _ in range(r.u16(0x14)):
        n, vn = r.u16(off + 4), r.u16(off + 6)
        out.append((vn, [struct.unpack_from("<4f", r.d, off + 8 + 16 * j) for j in range(n)]))
        off += 8 + 16 * n
    return out


def read_kmp(path):
    """What culling needs from a KMP: the clip objects (clip ID, route) in GOBJ order, the routes' XZ points and each
    checkpoint's clip ID."""
    r = Reader(open(path, "rb").read())
    if r.d[:4] != b"DMDC":
        raise ValueError("%s: not a KMP" % path)
    nsec, hlen, version = r.u16(8), r.u16(0xA), r.u32(0xC)
    sections = {}
    for i in range(nsec):
        o = hlen + r.u32(0x10 + 4 * i)
        sections[r.d[o:o + 4].decode()] = o
    clips, routes, ckpt = [], {}, []
    if "JBOG" in sections:
        o = sections["JBOG"]
        stride = 0x3C if version == 0xBB8 else 0x40
        for i in range(r.u16(o + 4)):
            e = o + 8 + i * stride
            if r.u16(e) == 30:
                clips.append((struct.unpack_from("<h", r.d, e + 0x2A)[0], struct.unpack_from("<h", r.d, e + 0x28)[0]))
    if "ITOP" in sections:
        o = sections["ITOP"]
        e = o + 8
        for i in range(r.u16(o + 4)):
            n = r.u16(e)
            routes[i] = [struct.unpack_from("<3f", r.d, e + 4 + 16 * j) for j in range(n)]
            e += 4 + 16 * n
    if "TPKC" in sections:
        o = sections["TPKC"]
        for i in range(r.u16(o + 4)):
            ckpt.append(struct.unpack_from("<b", r.d, o + 8 + i * 0x18 + 0x14)[0])
    return clips, routes, ckpt


# --- The game's rules --------------------------------------------------------------------------------------------

def bounds(rects):
    return (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))


def rect_of(tris):
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), min(zs), max(xs), max(zs))


def leaves(rect):
    """The 64 leaf cells (min x, min z, max x, max z), indexed by Morton code (bit 0 X)."""
    x0, z0, x1, z1 = rect
    w, h = (x1 - x0) / GRID, (z1 - z0) / GRID
    out = []
    for code in range(GRID * GRID):
        ix = sum(((code >> (2 * b)) & 1) << b for b in range(3))
        iz = sum(((code >> (2 * b + 1)) & 1) << b for b in range(3))
        out.append((x0 + ix * w, z0 + iz * h, x0 + (ix + 1) * w, z0 + (iz + 1) * h))
    return out


def leaf_mask(area, cells):
    """QuadTree::getFlag: the leaf cells the area touches, edges included."""
    return sum(1 << i for i, c in enumerate(cells) if area[0] <= c[2] and c[0] <= area[2] and area[1] <= c[3] and c[1] <= area[3])


def rect_inside_quad(rect, quad):
    """QuadCell::checkWholeInside for a clip quad (4 XZ points, edges 0-1, 1-2, 2-3, 3-0)."""
    cx, cz = (rect[0], rect[2], rect[0], rect[2]), (rect[1], rect[1], rect[3], rect[3])
    for i in range(4):
        j = (i + 1) % 4
        k = next(k for k in range(4) if k not in (i, j))
        nx, nz = quad[j][1] - quad[i][1], quad[i][0] - quad[j][0]
        if nx * (quad[k][0] - quad[i][0]) + nz * (quad[k][1] - quad[i][1]) > 0:
            nx, nz = -nx, -nz
        if any((cx[c] - quad[i][0]) * nx + (cz[c] - quad[i][1]) * nz > 0 for c in range(4)):
            return False
    return True


def clip_quads(clips, routes, clip_id):
    """The quads of the clip objects with this clip ID: only the first 32 clip objects, IDs 0 to 31."""
    if not 0 <= clip_id < 32:
        return []
    return [[(p[0], p[2]) for p in routes[r][:4]] for cid, r in clips[:32] if cid == clip_id and len(routes.get(r, [])) >= 4]


FRUSTUM_EDGES = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]


def view_region(pos, direction, far, corners, model_min, model_max):
    """QuadTree::convertTo: the edges (normal, point) of the view seen from above, or None for no view culling."""
    side, best = 0, float("inf")
    for a in range(3):
        d = direction[a]
        if abs(d) < FLT_EPS:
            continue
        t, s = (model_min[a] - pos[a]) / d, -1
        if not 0 <= t < far:
            t, s = (model_max[a] - pos[a]) / d, 1
            if not 0 <= t < far:
                continue
        if t < best:
            best, side = t, (s if a == 1 else 0)
    c = [tuple(p) for p in corners]
    if side:
        plane = model_min[1] if side < 0 else model_max[1]
        for i in (0, 1, 4, 5):
            d = [c[i][k] - pos[k] for k in range(3)]
            length = math.sqrt(sum(x * x for x in d))
            d = [x / length for x in d]
            if abs(d[1]) > FLT_EPS:
                t = (plane - pos[1]) / d[1]
                if 0 <= t < length:
                    c[i] = tuple(pos[k] + d[k] * t for k in range(3))
    pts = [(p[0], p[2]) for p in c]
    rect = [(model_min[0], model_min[2]), (model_max[0], model_min[2]), (model_min[0], model_max[2]), (model_max[0], model_max[2])]
    region = []
    for a, b in FRUSTUM_EDGES:
        nx, nz = pts[b][1] - pts[a][1], pts[a][0] - pts[b][0]
        if nx == 0 and nz == 0:
            continue
        ref, one_side = None, True
        for k in range(8):
            if k in (a, b):
                continue
            dd = (pts[k][0] - pts[a][0]) * nx + (pts[k][1] - pts[a][1]) * nz
            if ref is None:
                if dd != 0:
                    ref = dd
            elif ref * dd < 0:
                one_side = False
                break
        if not one_side:
            continue
        ref = ref or 0
        if len(region) > 7:
            return None
        length = math.hypot(nx, nz)
        nx, nz = nx / length, nz / length
        if ref >= 0:
            nx, nz = -nx, -nz
        if any(abs(nx - e[0]) <= FLT_EPS and abs(nz - e[1]) <= FLT_EPS for e in region):
            continue
        p = pts[a] if ref < 0 else pts[b]
        if any(nx * (q[0] - p[0]) + nz * (q[1] - p[1]) > 0 for q in rect):
            region.append((nx, nz, p[0], p[1]))
    return region


def cell_in_view(region, cell, margin):
    if region is None:
        return True
    cx = (cell[0] - margin[0], cell[2] + margin[0], cell[0] - margin[0], cell[2] + margin[0])
    cz = (cell[1] - margin[1], cell[1] - margin[1], cell[3] + margin[1], cell[3] + margin[1])
    return not any(all((cx[k] - e[2]) * e[0] + (cz[k] - e[3]) * e[1] >= 0 for k in range(4)) for e in region)


# --- Ways of dividing a course model -----------------------------------------------------------------------------

def cell_index(v, lo, size):
    return max(0, min(GRID - 1, math.floor((v - lo) / size))) if size > 0 else 0


def divide_retail(tris, grid_rect):
    """The retail rule: one group per grid cell of the centre of each triangle's XZ bounding box."""
    w, h = (grid_rect[2] - grid_rect[0]) / GRID, (grid_rect[3] - grid_rect[1]) / GRID
    cells = {}
    for t in tris:
        cx = (min(v[0] for v in t) + max(v[0] for v in t)) / 2
        cz = (min(v[2] for v in t) + max(v[2] for v in t)) / 2
        cells.setdefault(cell_index(cz, grid_rect[1], h) * GRID + cell_index(cx, grid_rect[0], w), []).append(t)
    return [cells[k] for k in sorted(cells)]


def divide_old_kmpexpander(tris, grid_rect):
    """KMPExpander before kmpexpander-div.patch: 1000-unit strips by minimum Z, then 1000-unit groups by minimum X."""
    tris = sorted(tris, key=lambda t: min(v[2] for v in t))
    groups, zi = [], 0
    while zi < len(tris):
        z0, strip = min(v[2] for v in tris[zi]), []
        while zi < len(tris) and min(v[2] for v in tris[zi]) - z0 <= 1000:
            strip.append(tris[zi])
            zi += 1
        strip.sort(key=lambda t: min(v[0] for v in t))
        xi = 0
        while xi < len(strip):
            x0, g = min(v[0] for v in strip[xi]), []
            while xi < len(strip) and min(v[0] for v in strip[xi]) - x0 <= 1000:
                g.append(strip[xi])
                xi += 1
            groups.append(g)
    return groups


def divide_by_span(tris, grid_rect):
    """Triangles grouped by the range of grid cells their bounding box covers."""
    w, h = (grid_rect[2] - grid_rect[0]) / GRID, (grid_rect[3] - grid_rect[1]) / GRID
    cells = collections.OrderedDict()
    for t in tris:
        k = (cell_index(min(v[0] for v in t), grid_rect[0], w), cell_index(max(v[0] for v in t), grid_rect[0], w),
             cell_index(min(v[2] for v in t), grid_rect[1], h), cell_index(max(v[2] for v in t), grid_rect[1], h))
        cells.setdefault(k, []).append(t)
    return list(cells.values())


# --- Commands ----------------------------------------------------------------------------------------------------

def find_course_dir():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, "local", "romfs", "eur2", "rom", "Course")
        if os.path.isdir(c):
            return c
        d = os.path.dirname(d)
    return None


def courses(args):
    if "all" not in args.course:
        return args.course
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(args.course_dir, "*.szs.d", "*.div")))


def load(args, course):
    base = os.path.join(args.course_dir, course + ".szs.d", course)
    return read_course_model(base + ".bcmdl", course), read_div(base + ".div"), base


def cmd_check(args):
    for course in courses(args):
        shapes, div, _ = load(args, course)
        worst, problems = 0.0, []
        if len(shapes) != len(div):
            problems.append("%d shapes, %d div blocks" % (len(shapes), len(div)))
        for si, (sh, (vn, areas)) in enumerate(zip(shapes, div)):
            if len(sh["streams"]) != len(areas):
                problems.append("shape %d: %d index streams, %d areas" % (si, len(sh["streams"]), len(areas)))
            if vn != sh["vertex_num"]:
                problems.append("shape %d: vertex count %d in the div, %d in the model" % (si, vn, sh["vertex_num"]))
            for tris, area in zip(sh["streams"], areas):
                if tris:
                    worst = max(worst, max(abs(a - b) for a, b in zip(rect_of(tris), area)))
        print("%-32s shapes=%d areas=%d largest difference=%g %s" % (course, len(shapes), sum(len(a) for _, a in div), worst,
                                                                     "; ".join(problems) or "ok"))


def cmd_rule(args):
    total = collections.Counter()
    for course in courses(args):
        shapes, div, _ = load(args, course)
        grid = bounds([a for _, areas in div for a in areas])
        w, h = (grid[2] - grid[0]) / GRID, (grid[3] - grid[1]) / GRID
        n = ok = keys = streams = 0
        for sh in shapes:
            all_keys = set()
            for tris in sh["streams"]:
                if not tris:
                    continue
                k = collections.Counter(cell_index((min(v[2] for v in t) + max(v[2] for v in t)) / 2, grid[1], h) * GRID +
                                        cell_index((min(v[0] for v in t) + max(v[0] for v in t)) / 2, grid[0], w) for t in tris)
                ok += k.most_common(1)[0][1]
                n += len(tris)
                streams += 1
                all_keys |= set(k)
            keys += len(all_keys)
        total.update(dict(n=n, ok=ok, keys=keys, streams=streams))
        print("%-32s streams=%4d (shape, cell) pairs=%4d triangles=%6d in their stream's main cell=%6.2f%%" % (
            course, streams, keys, n, 100.0 * ok / n))
    if "all" in args.course:
        print("total: streams=%d pairs=%d triangles=%d in their stream's main cell=%.2f%%" % (
            total["streams"], total["keys"], total["n"], 100.0 * total["ok"] / total["n"]))


def cmd_compare(args):
    for course in courses(args):
        shapes, div, base = load(args, course)
        clips, routes, ckpt = read_kmp(base + ".kmp")
        retail = [s["streams"] for s in shapes]
        grid = bounds([rect_of(t) for st in retail for t in st if t])
        cells = leaves(grid)
        ids = sorted(set(c for c in ckpt if 0 <= c < 32))
        hidden_leaves = {cid: {i for i, c in enumerate(cells) if any(rect_inside_quad(c, q) for q in clip_quads(clips, routes, cid))}
                         for cid in ids}
        print("%s: leaf cell %.0f x %.0f, %d checkpoints, clip IDs %s" % (course, (grid[2] - grid[0]) / GRID,
                                                                         (grid[3] - grid[1]) / GRID, len(ckpt), ids or "none"))
        ways = [("retail file", retail)] + [(name, [f([t for st in s["streams"] for t in st], grid) for s in shapes])
                                            for name, f in (("retail rule", divide_retail), ("old KMPExpander", divide_old_kmpexpander),
                                                            ("by span", divide_by_span))]
        for name, division in ways:
            groups = [(rect_of(g), len(g)) for st in division for g in st if g]
            tri_num = sum(n for _, n in groups)
            touched = sum(bin(leaf_mask(r, cells)).count("1") * n for r, n in groups) / tri_num
            hidden = 0.0
            for cid in ckpt:
                hl = hidden_leaves.get(cid, set())
                hidden += sum(n for r, n in groups if hl and all(i in hl for i in range(64) if leaf_mask(r, cells) >> i & 1)) / tri_num
            hidden = hidden / len(ckpt) if ckpt else 0.0
            print("  %-16s areas=%4d leaf cells touched per triangle=%.2f hidden by clip IDs (average over checkpoints)=%.1f%%" % (
                name, len(groups), touched, 100 * hidden))


def cmd_viewmask(args):
    cam = json.load(open(args.camera))
    rect = cam["rect"]
    cells = leaves(rect)
    margin = ((rect[2] - rect[0]) / GRID * 0.025, (rect[3] - rect[1]) / GRID * 0.025)
    region = view_region(cam["pos"], cam["dir"], cam["far"], cam["corners"], cam["model_min"], cam["model_max"])
    mask = sum(1 << i for i, c in enumerate(cells) if cell_in_view(region, c, margin))
    print("view edges: %s" % ("none (no view culling)" if region is None else len(region)))
    for e in region or []:
        print("  normal (%.4f, %.4f) through (%.1f, %.1f)" % e)
    print("visible leaf cells: 0x%016X" % mask)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course-dir", default=find_course_dir(), help="folder holding the <course>.szs.d folders")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "rule", "compare"):
        p = sub.add_parser(name)
        p.add_argument("course", nargs="+", help='course names, or "all"')
    p = sub.add_parser("viewmask")
    p.add_argument("camera")
    args = ap.parse_args()
    if args.cmd in ("check", "rule", "compare") and not args.course_dir:
        sys.exit("no extracted RomFS found; give --course-dir")
    {"check": cmd_check, "rule": cmd_rule, "compare": cmd_compare, "viewmask": cmd_viewmask}[args.cmd](args)


if __name__ == "__main__":
    main()
