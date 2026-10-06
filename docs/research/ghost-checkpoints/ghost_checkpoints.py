#!/usr/bin/env python3
"""Render the "ghost checkpoints" and checkpoint jumps of a Mario Kart 7 course.

Run it on an extracted course .szs directory (the folder holding the .kmp, the
*_map2.bclim map and UIMapPos.bin):

    python3 ghost_checkpoints.py path/to/Gctr_WuhuIsland1 -o wuhu.png

It re-implements the game's checkpoint search (Field::FindSector and
Field::FindRecursiveSector of the v1.2 game, see README.md next to this file)
and reports:

- ghost areas: positions outside every checkpoint quad where the search still
  returns a checkpoint. The search is started at every checkpoint, as for a
  kart that was in that checkpoint's quad and got there by leaving the track,
  or by a teleport or speed glitch. For each ghost checkpoint it lists the
  checkpoints it is found from, and whether that is a respawn glitch.
  --mode viable keeps only the respawn glitches; --mode practical keeps only
  the respawn glitches a kart gets by leaving that checkpoint's quad, without
  a teleport. Several modes can be given at once (--mode full viable
  practical): the searches run once and one image is written per mode.
- jumps: places where a kart moving from a real quad into the next position
  gets a checkpoint far away along the course, either a ghost or another quad
  that overlaps. If the game accepts the jump, a respawn afterwards uses the
  far checkpoint's respawn point: that is a respawn shortcut (or a respawn
  that sends the kart back).
- overlaps: areas inside two quads that are far apart along the course.

Each image comes with a text report of the same name (.txt).

Only X and Z matter: the game's search is 2D. Section-based courses (Maka Wuhu)
use different acceptance rules that are not modelled. Offline, the game also
accepts some jumps across key checkpoint sections (see accept_jump).

Requires Python 3.10+ and Pillow.
"""

import argparse
import colorsys
import glob
import math
import multiprocessing
import os
import struct
import sys
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('This tool needs Pillow: python3 -m pip install Pillow')

NONE8 = 0xFF


# ---------------------------------------------------------------------------
# KMP

def read_kmp_sections(data):
    if data[:4] != b'DMDC':
        raise ValueError('not a KMP file (no DMDC signature)')
    _, _, count, header_size, _ = struct.unpack_from('<4sIHHI', data, 0)
    offsets = struct.unpack_from('<%dI' % count, data, 0x10)
    sections = {}
    for off in offsets:
        pos = header_size + off
        sig = data[pos:pos + 4].decode('ascii', 'replace')
        num, = struct.unpack_from('<H', data, pos + 4)
        sections[sig] = (pos + 8, num)
    return sections


class Kmp:
    def __init__(self, data):
        sec = read_kmp_sections(data)
        pos, num = sec['TPKC']                      # CKPT, 0x18 bytes each
        self.ckpt = [struct.unpack_from('<4f8B', data, pos + i * 0x18) for i in range(num)]
        pos, num = sec['HPKC']                      # CKPH, 0x10 bytes each
        self.ckph = [struct.unpack_from('<2B6B6B', data, pos + i * 0x10) for i in range(num)]
        self.jgpt = []                              # JGPT, 0x1C bytes each
        if 'TPGJ' in sec:
            pos, num = sec['TPGJ']
            self.jgpt = [struct.unpack_from('<3f3fhh', data, pos + i * 0x1C) for i in range(num)]


# ---------------------------------------------------------------------------
# Checkpoints, as set up by the game

class CheckPoint:
    __slots__ = ('index', 'left', 'right', 'jugem', 'type', 'prev_id', 'next_id', 'byte15', 'forward',
                 'nexts', 'prevs', 'edges', 'key', 'path')


def build_checkpoints(kmp):
    cps = []
    for i, (lx, lz, rx, rz, jugem, typ, prev_id, next_id, _, byte15, _, _) in enumerate(kmp.ckpt):
        c = CheckPoint()
        c.index, c.left, c.right = i, (lx, lz), (rx, rz)
        c.jugem = jugem
        c.type = typ if typ < 0x80 else typ - 0x100      # s8, -1 = not a key checkpoint
        c.prev_id, c.next_id = prev_id, next_id
        c.byte15 = byte15                                # CKPT byte 0x15, see accept_jump
        # MapdataCheckPoint constructor: normal of the checkpoint line
        fx, fz = rz - lz, lx - rx
        length = math.hypot(fx, fz) or 1.0
        c.forward = (fx / length, fz / length)
        cps.append(c)
    n = len(cps)
    paths = kmp.ckph

    def owning_path(i):                                  # MapdataPathDataBase::isInclude
        for p in paths:
            if p[0] <= i <= p[0] + p[1] - 1:
                return p
        return None

    # MapdataCheckPoint::setupLink
    for c in cps:
        p = owning_path(c.index)
        c.path = paths.index(p) if p else -1
        if c.prev_id != NONE8:
            c.prevs = [c.prev_id] if c.prev_id < n else []
        else:
            c.prevs = []
            if p:
                for q in p[2:8]:
                    if q != NONE8 and q < len(paths):
                        end = (paths[q][0] + paths[q][1] - 1) & 0xFF
                        if end < n:
                            c.prevs.append(end)
        if c.next_id != NONE8:
            c.nexts = [c.next_id] if c.next_id < n else []
        else:
            c.nexts = []
            if p:
                for q in p[8:14]:
                    if q != NONE8 and q < len(paths) and paths[q][0] < n:
                        c.nexts.append(paths[q][0])
        # SNextInfo: next checkpoint and the two side edges towards it
        c.edges = []
        for j in c.nexts:
            m = cps[j]
            c.edges.append((m, m.left[0] - c.left[0], m.left[1] - c.left[1],
                            m.right[0] - c.right[0], m.right[1] - c.right[1]))

    # MapdataCheckPointAccessor::setup + MapdataCheckPoint::setupChechPointGroup:
    # the key id of the last key checkpoint before each checkpoint, walking from the finish line.
    finish = 0
    for c in cps:
        if c.type == 0:
            finish = c.index
    for c in cps:
        c.key = None
    sys.setrecursionlimit(max(1000, 4 * n + 100))

    def group(c, g):
        c.key = c.type if c.type != -1 else g
        for j in c.nexts:
            if cps[j].key is None:
                group(cps[j], c.key)
    if cps:
        group(cps[finish], 0)
    for c in cps:
        if c.key is None:
            c.key = 0
    return cps, finish


def check(c, x, z):
    """MapdataCheckPoint::checkSectorAndDistanceRatio. Returns (result, ratio or None).

    2: inside the quad; 1: between the side lines of a quad but not between its
    checkpoint lines; 0: outside. ratio is stored whenever the side tests pass."""
    rx, rz = c.right
    dx, dz = x - rx, z - rz
    res, ratio = 0, None
    for m, e1x, e1z, e2x, e2z in c.edges:
        vx, vz = x - m.left[0], z - m.left[1]
        if e1x * vz - e1z * vx < 0:
            continue
        if e2z * dx - e2x * dz < 0:
            continue
        a = c.forward[0] * dx + c.forward[1] * dz
        b = m.forward[0] * vx + m.forward[1] * vz
        den = a - b
        ratio = a / den if den != 0 else (math.inf if a > 0 else -math.inf if a < 0 else math.nan)
        if 0 <= ratio <= 1.0:
            return 2, ratio
        res = 1
    return res, ratio


# ---------------------------------------------------------------------------
# The search: Field::FindSector / Field::FindRecursiveSector

class Search:
    def __init__(self, cps, x, z, online, table=None):
        self.cps, self.x, self.z, self.online = cps, x, z, online
        self.table = table                                # check() of every checkpoint at (x, z), if known
        self.visited = set()
        self.ratio = 0.0                                  # initial value in calcLapPosition_
        self.bridged = False

    def test(self, c):
        res, r = self.table[c.index] if self.table else check(c, self.x, self.z)
        if r is not None:
            self.ratio = r
        return res

    def recursive(self, depth, backward, c, flags):
        limit = 16 if flags & 4 else 8
        if depth >= 0 and depth > limit:
            return -1
        res = 0 if c.index in self.visited else self.test(c)
        self.visited.add(c.index)
        if res == 2:
            return c.index
        # v1.1: with disable_ghost_checkpoints, bridging only at depth <= 1. The main walk enters depth 1 with flags bit 0
        # clear, so it never bridges; only the fallback walk (depth -1) still can
        gate = (not self.online) or depth <= 1
        nd = depth + 1 if depth >= 0 else -1
        cps = self.cps
        if backward:
            if gate and (flags & 1) and res == 1 and self.ratio > 1.0:
                self.ratio = 1.0
                self.bridged = True
                return c.index
            if not (flags & 2) and c.type >= 0:
                return -1
            f2 = flags | 1 if (res == 1 and self.ratio < 0) else flags & ~1
            first, first_back, second, second_back = c.prevs, True, c.nexts, False
        else:
            if gate and (flags & 1) and res == 1 and self.ratio < 0:
                self.ratio = 0.0
                self.bridged = True
                return c.index
            if not (flags & 2) and c.type >= 0:
                return -1
            f2 = flags | 1 if (res == 1 and self.ratio > 1.0) else flags & ~1
            first, first_back, second, second_back = c.nexts, False, c.prevs, True
        for j in first:
            r = self.recursive(nd, first_back, cps[j], f2)
            if r != -1:
                return r
        r = -1
        for j in second:
            if j in self.visited:
                continue
            r = self.recursive(nd, second_back, cps[j], f2)
            if r != -1:
                return r
        return r

    def find(self, start, full=True, skip_global=False):
        cps = self.cps
        c = cps[start]
        res = self.test(c)
        self.visited.add(c.index)
        flags = 6 if full else 0
        out = -1

        def nexts_prevs():            # the other prevs of each next (inner loop breaks, outer does not)
            nonlocal out
            for j in c.nexts:
                for k in cps[j].prevs:
                    if k != c.index:
                        out = self.recursive(1, True, cps[k], flags)
                        if out != -1:
                            break
            return out != -1

        def prevs_nexts():
            nonlocal out
            for j in c.prevs:
                for k in cps[j].nexts:
                    if k != c.index:
                        out = self.recursive(1, False, cps[k], flags)
                        if out != -1:
                            break
            return out != -1

        def nexts():
            nonlocal out
            for j in c.nexts:
                out = self.recursive(1, False, cps[j], flags)
                if out != -1:
                    return True
            return False

        def prevs():
            nonlocal out
            for j in c.prevs:
                out = self.recursive(1, True, cps[j], flags)
                if out != -1:
                    return True
            return False

        if res == 2:
            return c.index
        if res == 0:
            done = nexts_prevs() or prevs_nexts() or nexts() or prevs()
        else:
            if self.ratio <= 0.5:
                done = prevs() or prevs_nexts() or nexts_prevs() or nexts()
            else:
                done = nexts() or nexts_prevs() or prevs_nexts() or prevs()
        if not done:
            for j in c.nexts:
                out = self.recursive(-1, False, cps[j], 0)
                if out != -1:
                    done = True
                    break
        if not done:
            for j in c.prevs:
                out = self.recursive(-1, True, cps[j], 0)
                if out != -1:
                    done = True
                    break
        if full and out == -1 and not skip_global:
            for d in cps:                                  # last resort: every checkpoint in order
                if d.index in self.visited:
                    continue
                self.visited.add(d.index)
                if check(d, self.x, self.z)[0] == 2:
                    return d.index
        return out


def find_sector(cps, x, z, start, online, skip_global=False, table=None):
    s = Search(cps, x, z, online, table)
    r = s.find(start, skip_global=skip_global)
    return r, s.bridged


REJECT_SECTION, REJECT_NOT_NEXT = 'section', 'not next'


def accept_jump(cps, paths, finish, laps, before, after, net_send=False):
    """RaceSys::LapRankChecker::calcLapPosition_ for courses without sections: does the kart's current
    (respawn) checkpoint become `after` when the kart's current checkpoint is `before`?
    Returns (accepted, reason for a rejection).

    A jump across key checkpoint sections sets Force_No_Lap_Completion and leaves the key id alone, but the
    last tests (neighbours, 3 laps and CKPT byte 0x15 == 1) still run when VehicleBase::m_is_net_send is clear,
    which it is for every kart offline (measured), and then set the current checkpoint anyway. `net_send`
    (--online: set on the karts a console sends to the others, the player's own among them) skips them after such a
    jump."""
    n = len(cps)
    max_key = max((c.type for c in cps), default=0)
    before_finish = (n - 1 + finish) % n                 # LapRankChecker::m_max_checkpoint_id
    d = cps[after].key - cps[before].key
    if d in (-1, 1):                                     # next or previous key checkpoint section
        return True, None
    if d == -max_key and after == finish:                # lap completed
        return True, None
    if d == max_key and after == before_finish:          # lap undone
        return True, None
    if d != 0 and net_send:
        return False, REJECT_SECTION
    reject = REJECT_SECTION if d != 0 else REJECT_NOT_NEXT
    # the last tests: a checkpoint next to the current one
    if cps[after].path < 0 or cps[before].path < 0:
        return False, reject
    start, num = paths[cps[after].path][:2]
    end = (start + num - 1) & 0xFF
    if start <= before <= end:
        if abs(after - before) <= 1:
            return True, None
        if (after == 0 and before == before_finish) or (after == before_finish and before == 0):
            return True, None
    else:
        p = paths[cps[after].path]
        for q in p[2:8]:                                 # current checkpoint ends a previous group
            if q == NONE8:
                break
            if q == cps[before].path:
                if before == (paths[q][0] + paths[q][1] - 1) & 0xFF:
                    return True, None
                break
        for q in p[8:14]:                                # current checkpoint starts a next group
            if q == NONE8:
                break
            if q == cps[before].path:
                if before == paths[q][0]:
                    return True, None
                break
    if laps == 3 and cps[after].byte15 == 1:             # LapRankChecker+0x12 is "the course has 3 laps"
        return True, None
    return False, reject


def skips_section(cps, finish, before, after):
    """True for a jump that accept_jump() can only accept through its last tests: the key id stays and
    Force_No_Lap_Completion is set."""
    n = len(cps)
    max_key = max((c.type for c in cps), default=0)
    d = cps[after].key - cps[before].key
    return d not in (-1, 0, 1) and not (d == -max_key and after == finish) and \
        not (d == max_key and after == (n - 1 + finish) % n)


JUMP_RESPAWN, JUMP_SAME_RESPAWN, JUMP_REJECTED = 0, 1, 2
RED, ORANGE = (255, 0, 0, 255), (255, 150, 0, 255)
JUMP_STYLE = {                                  # colour, width: red is a respawn glitch, orange has no effect
    JUMP_RESPAWN: (RED, 4),
    JUMP_SAME_RESPAWN: (ORANGE, 2),
    JUMP_REJECTED: (ORANGE, 2),
}


def jump_kind(cps, before, after, accepted):
    """What a jump does to the kart's respawn."""
    if not accepted:
        return JUMP_REJECTED
    if cps[after].jugem == cps[before].jugem:
        return JUMP_SAME_RESPAWN
    return JUMP_RESPAWN


def is_glitch(cps, paths, finish, laps, prog, max_skip, before, after, net_send=False):
    """True when a kart whose current checkpoint is `before` and that gets `after` from the search ends up
    with another respawn point, and `after` is more than max_skip checkpoints away along the course."""
    dist = course_distance(prog, before, after)
    if dist is not None and abs(dist) <= max_skip:
        return False
    ok, _ = accept_jump(cps, paths, finish, laps, before, after, net_send)
    return jump_kind(cps, before, after, ok) == JUMP_RESPAWN


def course_progress(cps, finish):
    """Checkpoints from the finish line along the course (shortest way), so that the
    checkpoints of parallel routes at the same point of the course get the same value."""
    prog, q = {finish: 0}, deque([finish])
    while q:
        i = q.popleft()
        for j in cps[i].nexts:
            if j not in prog:
                prog[j] = prog[i] + 1
                q.append(j)
    return prog


def course_distance(prog, a, b):
    """Signed number of checkpoints from a to b along the course (forward > 0), None if not connected."""
    if a not in prog or b not in prog:
        return None
    lap = max(prog.values()) + 1
    d = (prog[b] - prog[a]) % lap
    return d - lap if d > lap // 2 else d


def jugem_check_points(cps, kmp):
    """FieldDirector::createBeforeStructure: checkpoint each respawn point puts the kart in."""
    out = []
    for j, e in enumerate(kmp.jgpt):
        forced = e[7]
        if forced > 0:
            out.append(forced & 0xFF)
            continue
        found = None
        for c in reversed([c for c in cps if c.jugem == j]):
            if check(c, e[0], e[2])[0] == 2:
                found = c.index
                break
        out.append(found)
    return out


# ---------------------------------------------------------------------------
# BCLIM

TILE_ORDER = [0, 1, 4, 5, 2, 3, 6, 7, 8, 9, 12, 13, 10, 11, 14, 15]
ETC1_MOD = [(2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183)]


def _clamp(v):
    return 0 if v < 0 else 255 if v > 255 else v


def _decode_etc1(data, w, h, has_alpha):
    px = bytearray(w * h * 4)
    off = 0
    ext = lambda v: (v << 3) | ((v & 0x1C) >> 2)
    sgn = lambda v: v - 8 if v & 4 else v
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            for i in (0, 4):
                for j in (0, 4):
                    alpha = 0xFFFFFFFFFFFFFFFF
                    if has_alpha:
                        alpha, = struct.unpack_from('<Q', data, off)
                        off += 8
                    d, = struct.unpack_from('<Q', data, off)
                    off += 8
                    if (d >> 33) & 1:
                        r, g, b = (d >> 59) & 31, (d >> 51) & 31, (d >> 43) & 31
                        c1 = (ext(r), ext(g), ext(b))
                        r += sgn((d >> 56) & 7)
                        g += sgn((d >> 48) & 7)
                        b += sgn((d >> 40) & 7)
                        c2 = (ext(r & 31), ext(g & 31), ext(b & 31))
                    else:
                        c1 = (((d >> 60) & 15) * 17, ((d >> 52) & 15) * 17, ((d >> 44) & 15) * 17)
                        c2 = (((d >> 56) & 15) * 17, ((d >> 48) & 15) * 17, ((d >> 40) & 15) * 17)
                    t1, t2, flip = (d >> 37) & 7, (d >> 34) & 7, (d >> 32) & 1
                    for y3 in range(4):
                        yy = y + i + y3
                        if yy >= h:
                            continue
                        for x3 in range(4):
                            xx = x + j + x3
                            if xx >= w:
                                continue
                            k = x3 * 4 + y3
                            first = (y3 < 2) if flip else (x3 < 2)
                            m = ETC1_MOD[t1 if first else t2][(d >> k) & 1]
                            if (d >> (k + 16)) & 1:
                                m = -m
                            c = c1 if first else c2
                            p = (yy * w + xx) * 4
                            px[p:p + 4] = bytes((_clamp(c[0] + m), _clamp(c[1] + m), _clamp(c[2] + m),
                                                 ((alpha >> (k * 4)) & 15) * 17))
    return px


def _decode_tiled(data, w, h, bpp, to_rgba):
    px = bytearray(w * h * 4)
    step = bpp // 8 if bpp >= 8 else 0
    off = 0
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            for i in range(64):
                x2, y2 = i % 8, i // 8
                pos = TILE_ORDER[x2 % 4 + y2 % 4 * 4] + 16 * (x2 // 4) + 32 * (y2 // 4)
                if bpp >= 8:
                    raw = data[off + pos * step: off + pos * step + step]
                else:                                       # 4 bpp
                    byte = data[off + pos // 2]
                    raw = (byte >> 4) if pos & 1 else (byte & 15)
                if x + x2 < w and y + y2 < h:
                    p = ((y + y2) * w + x + x2) * 4
                    px[p:p + 4] = bytes(to_rgba(raw))
            off += 64 * bpp // 8
    return px


def _u16(b):
    return b[0] | (b[1] << 8)


FORMATS = {
    0: (8, lambda b: (b[0], b[0], b[0], 255)),                                  # L8
    1: (8, lambda b: (255, 255, 255, b[0])),                                    # A8
    2: (8, lambda b: ((b[0] >> 4) * 17,) * 3 + ((b[0] & 15) * 17,)),            # LA4
    3: (16, lambda b: (b[1], b[1], b[1], b[0])),                                # LA8
    5: (16, lambda b: (((_u16(b) >> 11) & 31) * 255 // 31, ((_u16(b) >> 5) & 63) * 255 // 63,
                       (_u16(b) & 31) * 255 // 31, 255)),                       # RGB565
    6: (24, lambda b: (b[2], b[1], b[0], 255)),                                 # RGB8
    7: (16, lambda b: (((_u16(b) >> 11) & 31) * 255 // 31, ((_u16(b) >> 6) & 31) * 255 // 31,
                       ((_u16(b) >> 1) & 31) * 255 // 31, 255 if _u16(b) & 1 else 0)),  # RGBA5551
    8: (16, lambda b: (((_u16(b) >> 12) & 15) * 17, ((_u16(b) >> 8) & 15) * 17,
                       ((_u16(b) >> 4) & 15) * 17, (_u16(b) & 15) * 17)),       # RGBA4
    9: (32, lambda b: (b[3], b[2], b[1], b[0])),                                # RGBA8
    12: (4, lambda v: (v * 17, v * 17, v * 17, 255)),                           # L4
    13: (4, lambda v: (255, 255, 255, v * 17)),                                 # A4
}


def load_bclim(path):
    data = open(path, 'rb').read()
    tail = data[-0x28:]
    if tail[:4] != b'CLIM' or tail[0x14:0x18] != b'imag':
        raise ValueError('not a BCLIM file')
    w, h, fmt = struct.unpack_from('<HHI', tail, 0x1C)
    fmt &= 0xFF                 # some custom maps have stray bits above the format byte (0x0080000A for ETC1)
    # the texture is stored at the next power of two in each dimension; the image is its top-left w x h
    # (EveryFileExplorer, 3DS/GPU/Textures.cs, ToBitmap)
    pw, ph = (max(8, 1 << (v - 1).bit_length()) for v in (w, h))
    if fmt in (10, 11):
        px = _decode_etc1(data, pw, ph, fmt == 11)
    elif fmt in FORMATS:
        bpp, conv = FORMATS[fmt]
        px = _decode_tiled(data, pw, ph, bpp, conv)
    else:
        raise ValueError('unsupported BCLIM format %d' % fmt)
    return Image.frombytes('RGBA', (pw, ph), bytes(px)).crop((0, 0, w, h))


def load_ui_map_pos(path):
    """UIMapPos.bin: two rectangles (bottom-left X/Z, top-right X/Z) and a byte.
    The large map (*_map2.bclim) covers the second rectangle, stretched over the whole texture."""
    v = struct.unpack('<8fB', open(path, 'rb').read(0x21))
    return v[4:8]


# ---------------------------------------------------------------------------
# Grid analysis (runs in worker processes)

G = {}


def _init_worker(cps, online, xs, zs):
    G.update(cps=cps, online=online, xs=xs, zs=zs, reach=search_reach(cps))


def _inside_row(iz):
    cps, xs, z = G['cps'], G['xs'], G['zs'][iz]
    return [[c.index for c in cps if check(c, x, z)[0] == 2] for x in xs]


def search_reach(cps):
    """For each start, the checkpoints that FindSector can test: those up to 17 links away (FindRecursiveSector
    starts at depth 1 up to two links from the start and stops past depth 16), and those the fallback walk
    reaches without going through a key checkpoint."""
    def links(c):
        return c.nexts + c.prevs
    out = []
    for s in cps:
        seen, ring = {s.index}, [s.index]
        for _ in range(17):
            ring = [j for i in ring for j in links(cps[i]) if j not in seen]
            seen.update(ring)
        todo = list(links(s))
        walk = set(todo)
        while todo:
            c = cps[todo.pop()]
            if c.type >= 0:
                continue
            for j in links(c):
                if j not in walk:
                    walk.add(j)
                    todo.append(j)
        out.append(frozenset(seen | walk))
    return out


def _ghost_row(task):
    """Ghosts of the outside cells of a row, for a kart whose search starts at any checkpoint (a kart that
    gets there by leaving a quad, or by a teleport or a speed glitch). Returns [(ix, {start: ghost})]."""
    iz, outside = task
    cps, z, reach = G['cps'], G['zs'][iz], G['reach']
    out = []
    for ix in outside:
        x = G['xs'][ix]
        table = [check(c, x, z) for c in cps]
        # a bridge returns a checkpoint between its side lines, entered from a linked one that is too
        candidates = {c.index for c in cps if table[c.index][0] == 1
                      and any(table[j][0] == 1 for j in c.nexts + c.prevs)}
        if not candidates:
            continue
        found = {}
        for c in cps:
            if reach[c.index].isdisjoint(candidates):
                continue
            r, bridged = find_sector(cps, x, z, c.index, G['online'], skip_global=True, table=table)
            if bridged:
                found[c.index] = r
        if found:
            out.append((ix, found))
    return iz, out


def _jump_task(task):
    ia, ib, start = task
    (ixa, iza), (ixb, izb) = ia, ib
    r, bridged = find_sector(G['cps'], G['xs'][ixb], G['zs'][izb], start, G['online'])
    return ia, ib, start, r, bridged


MODE_FULL, MODE_VIABLE, MODE_PRACTICAL = 'full', 'viable', 'practical'
MODES = {
    MODE_FULL: 'all ghost candidates',
    MODE_VIABLE: 'only respawn glitches, also after a teleport',
    MODE_PRACTICAL: 'only respawn glitches next to the quad the kart leaves',
}


def analyse(cps, paths, finish, laps, bounds, step, online, jobs, max_skip):
    """The searches over the grid, for every mode at once. select() then keeps what one mode shows."""
    prog = course_progress(cps, finish)
    x0, z0, x1, z1 = bounds
    nx, nz = int((x1 - x0) / step) + 1, int((z1 - z0) / step) + 1
    xs = [x0 + (i + 0.5) * step for i in range(nx)]
    zs = [z0 + (i + 0.5) * step for i in range(nz)]
    pool = multiprocessing.Pool(jobs, initializer=_init_worker, initargs=(cps, online, xs, zs))
    try:
        inside = pool.map(_inside_row, range(nz), chunksize=4)          # inside[iz][ix] = [cp...]

        # jumps: a kart in a real quad moves to a neighbouring cell
        tasks = []
        for iz in range(nz):
            for ix in range(nx):
                here = inside[iz][ix]
                if not here:
                    continue
                for jx, jz in ((ix + 1, iz), (ix - 1, iz), (ix, iz + 1), (ix, iz - 1)):
                    if 0 <= jx < nx and 0 <= jz < nz:
                        there = inside[jz][jx]
                        for s in here:
                            if s not in there:
                                tasks.append(((ix, iz), (jx, jz), s))
        jumps = []
        for ia, ib, s, r, bridged in pool.imap_unordered(_jump_task, tasks, chunksize=64):
            if r < 0 or r == s:
                continue
            dist = course_distance(prog, s, r)
            if dist is not None and abs(dist) <= max_skip:
                continue
            ok, why = accept_jump(cps, paths, finish, laps, s, r, net_send=online)
            jumps.append((ia, ib, s, r, bridged, dist, jump_kind(cps, s, r, ok), why))

        # ghost areas: outside cells, searched from every checkpoint. found[(ix, iz)] = {start: ghost}
        found = {}
        tasks = [(iz, [ix for ix in range(nx) if not inside[iz][ix]]) for iz in range(nz)]
        for iz, row in pool.imap_unordered(_ghost_row, tasks):
            for ix, f in row:
                found[ix, iz] = f
    finally:
        pool.close()
        pool.join()

    # overlaps: cells inside two quads far apart along the course
    overlaps = []
    for iz in range(nz):
        for ix in range(nx):
            here = inside[iz][ix]
            if len(here) > 1:
                for a in here:
                    for b in here:
                        if a < b:
                            d = course_distance(prog, a, b)
                            if d is None or abs(d) > max_skip:
                                overlaps.append((ix, iz, a, b))
    return xs, zs, inside, found, jumps, overlaps, prog


def select(cps, paths, finish, laps, max_skip, analysis, mode, online=False):
    """What one mode keeps of analyse(): which (start, ghost) pairs. MODE_FULL keeps all of them. MODE_VIABLE
    keeps the respawn glitches, found from any start (a teleport or speed glitch may be needed to get there).
    MODE_PRACTICAL keeps the respawn glitches that a kart gets by leaving the start's quad into a neighbouring
    cell."""
    xs, zs, inside, found, jumps, overlaps, prog = analysis
    next_to_quad = {(j[2], j[3]) for j in jumps if j[4]}                   # ghosts found leaving a quad
    if mode != MODE_FULL:                                                   # ghost borders without a glitch
        jumps = [j for j in jumps if not j[4] or j[6] == JUMP_RESPAWN]

    glitch = {}

    def keep(s, g):
        if (s, g) not in glitch:
            glitch[s, g] = is_glitch(cps, paths, finish, laps, prog, max_skip, s, g, online)
        if mode == MODE_FULL:
            return True
        return glitch[s, g] and (mode == MODE_VIABLE or (s, g) in next_to_quad)

    # ghost[iz][ix] = the ghosts found there; reach[g][start] = number of cells where start finds g
    ghost = [[frozenset()] * len(xs) for _ in range(len(zs))]
    reach = {}
    for (ix, iz), f in found.items():
        f = {s: g for s, g in f.items() if keep(s, g)}
        if not f:
            continue
        ghost[iz][ix] = frozenset(f.values())
        for start, g in f.items():
            starts = reach.setdefault(g, {})
            starts[start] = starts.get(start, 0) + 1
    return xs, zs, inside, ghost, reach, glitch, jumps, overlaps


def max_key(cps):
    return max((c.type for c in cps), default=0)


# ---------------------------------------------------------------------------
# Drawing

def colour_for(i, alpha):
    # yellow-greens to blues only, so that areas never look like the red, orange or purple markings, in
    # three tones (bright, pale, dark). i is the rank of the set of ghost checkpoints in the course.
    h = 0.20 + 0.47 * ((i * 0.61803398875) % 1.0)
    s, v = ((0.85, 1.0), (0.4, 1.0), (0.95, 0.6))[i % 3]
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255), alpha)


def light(colour):
    """The colour mixed with white, for text that has to be readable on dark backgrounds."""
    return tuple(int(v + (255 - v) * 0.45) for v in colour[:3]) + (255,)


def id_ranges(ids, colour):
    """Checkpoint ids as text pieces, consecutive ids of the same colour joined: [('107..110', colour)]."""
    out = []
    for i in sorted(ids):
        if out and out[-1][1] == i - 1 and out[-1][2] == colour(i):
            out[-1][1] = i
        else:
            out.append([i, i, colour(i)])
    return [('%d..%d' % (a, b) if b > a else '%d' % a, col) for a, b, col in out]


def ghost_regions(ghost):
    """Connected pieces (4-neighbour) of cells with the same set of ghosts: [(ghost set, [(ix, iz)])]."""
    nz, nx = len(ghost), len(ghost[0]) if ghost else 0
    seen = [[False] * nx for _ in range(nz)]
    out = []
    for iz in range(nz):
        for ix in range(nx):
            gs = ghost[iz][ix]
            if not gs or seen[iz][ix]:
                continue
            seen[iz][ix] = True
            cells, todo = [], [(ix, iz)]
            while todo:
                cx, cz = todo.pop()
                cells.append((cx, cz))
                for jx, jz in ((cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)):
                    if 0 <= jx < nx and 0 <= jz < nz and not seen[jz][jx] and ghost[jz][jx] == gs:
                        seen[jz][jx] = True
                        todo.append((jx, jz))
            out.append((gs, cells))
    return out


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def text(draw, pos, s, fnt, fill=(255, 255, 255, 255)):
    draw.text(pos, s, font=fnt, fill=fill, stroke_width=2, stroke_fill=(0, 0, 0, 255))


def _presence(mask, f):
    """Summed-area table of the non-empty pixels of an alpha mask, on a grid of f x f pixels."""
    w, h = (mask.width + f - 1) // f, (mask.height + f - 1) // f
    small = mask.point(lambda v: 255 if v else 0).resize((w, h), Image.BOX)
    data = small.tobytes()
    table = [[0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        run, row, prev = 0, table[y + 1], table[y]
        for x in range(w):
            run += 1 if data[y * w + x] else 0
            row[x + 1] = prev[x + 1] + run
    return table


def place_legend(size, important, secondary, lw, lh, margin=6, f=2):
    """Top-left corner for the legend: the place nearest to a corner of the image that covers nothing
    of `important` (lines, points, labels) and as little as possible of `secondary` (area fills). If every
    place covers something important, the one covering least. Returns (x, y, covers_something)."""
    W, H = size
    imp = _presence(important.getchannel('A'), f)
    sec = _presence(secondary.getchannel('A'), f)
    cw, ch = (lw + f - 1) // f, (lh + f - 1) // f

    def area(t, x, y):
        return t[y + ch][x + cw] - t[y][x + cw] - t[y + ch][x] + t[y][x]
    # places on a grid, plus the places touching each edge of the image
    x_max, y_max = max(margin, W - lw - margin - 1), max(margin, H - lh - margin - 1)
    xs = sorted(set(list(range(margin, x_max + 1, 4 * f)) + [x_max]))
    ys = sorted(set(list(range(margin, y_max + 1, 4 * f)) + [y_max]))
    candidates = []
    for py in ys:
        for px in xs:
            x, y = min(px // f, len(imp[0]) - 1 - cw), min(py // f, len(imp) - 1 - ch)
            corner = min(math.hypot(px - cx, py - cy) for cx in (0, W - lw) for cy in (0, H - lh))
            candidates.append((area(imp, x, y), area(sec, x, y), corner, px, py))
    candidates.sort()
    if candidates[0][0] == 0:
        return candidates[0][3], candidates[0][4], False
    # the grid is coarse: check the pixels of the most promising places
    alpha = important.getchannel('A')
    free = [c for c in candidates[:400]
            if alpha.crop((c[3], c[4], c[3] + lw + 1, c[4] + lh + 1)).getbbox() is None]
    if free:
        best = min(free, key=lambda c: (c[1], c[2]))
        return best[3], best[4], False
    return candidates[0][3], candidates[0][4], True


def draw_sample(d, sample, x, y, w, h):
    """The small picture before a legend row, in the box (x, y, w, h), drawn like on the map."""
    kind = sample[0]
    if kind == 'checkpoint':
        d.line([(x + 2, y + h - 2), (x + w - 2, y + 2)], fill=(255, 220, 60, 220), width=1)
        d.ellipse([x, y + h - 4, x + 4, y + h], fill=(40, 220, 40, 255))
        d.ellipse([x + w - 4, y, x + w, y + 4], fill=(230, 40, 40, 255))
    elif kind == 'line':
        d.line([(x + 1, y + h // 2), (x + w - 1, y + h // 2)], fill=sample[1], width=sample[2])
    elif kind == 'outline':
        d.polygon([(x + 2, y), (x + w - 6, y), (x + w, y + h), (x, y + h)], outline=(255, 255, 255, 140))
    elif kind == 'dot':
        c = (x + w // 2, y + h // 2)
        d.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], fill=(40, 90, 255, 255), outline=(255, 255, 255, 255))
    elif kind == 'fill':
        d.rectangle([x, y, x + w, y + h], fill=sample[1])
    elif kind == 'border':
        d.rectangle([x, y, x + w, y + h], fill=(255, 255, 255, 40))
        d.line([(x + w // 2, y - 1), (x + w // 2, y + h + 1)], fill=sample[1], width=sample[2])
    elif kind == 'quad':
        d.polygon([(x + 2, y), (x + w - 6, y), (x + w, y + h), (x, y + h)], fill=sample[1][:3] + (110,),
                  outline=(255, 255, 255, 140))


def render(args, name, cps, kmp, finish, map_img, map_rect, bounds, step, result, mode):
    xs, zs, inside, ghost, reach, glitch, jumps, overlaps = result
    x0, z0, x1, z1 = bounds
    if map_img is not None:
        scale = map_img.width / abs(map_rect[2] - map_rect[0])
    else:
        scale = 1400 / max(x1 - x0, z1 - z0)
    scale *= args.scale
    W, H = int((x1 - x0) * scale) + 1, int((z1 - z0) * scale) + 1
    P = lambda x, z: ((x - x0) * scale, (z - z0) * scale)            # +Z is down, like the map

    img = Image.new('RGBA', (W, H), (40, 40, 48, 255))
    if map_img is not None:
        blx, blz, trx, trz = map_rect
        (px0, pz0), (px1, pz1) = P(min(blx, trx), min(blz, trz)), P(max(blx, trx), max(blz, trz))
        m = map_img
        if trx < blx:
            m = m.transpose(Image.FLIP_LEFT_RIGHT)
        if trz > blz:                                    # top row of the texture is the top-right Z
            m = m.transpose(Image.FLIP_TOP_BOTTOM)
        m = m.resize((max(1, int(px1 - px0)), max(1, int(pz1 - pz0))), Image.BILINEAR)
        img.alpha_composite(m, (int(px0), int(pz0)))
        img = Image.blend(img, Image.new('RGBA', img.size, (40, 40, 48, 255)), 0.25)

    # fills: lightly red or orange the quads of the checkpoints from which some ghost is found, and the ghost
    # areas. A region is the cells where the same set of ghosts is found (from different starts); each
    # set has its own colour, and each region one outline, drawn just inside its cells where the set
    # changes, so that the outlines of neighbouring regions lie side by side.
    cell = step * scale
    rank = {gs: i for i, gs in enumerate(sorted({gs for row in ghost for gs in row if gs}, key=sorted))}
    colour = lambda gs, alpha: colour_for(rank[gs], alpha)
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for s in sorted({s for starts in reach.values() for s in starts}):    # red when any of them is a glitch
        bad = any(glitch[s, g] for g, starts in reach.items() if s in starts)
        for m, *_ in cps[s].edges:
            ld.polygon([P(*cps[s].left), P(*m.left), P(*m.right), P(*cps[s].right)],
                       fill=(RED if bad else ORANGE)[:3] + (50,))
    for iz, row in enumerate(ghost):
        for ix, gs in enumerate(row):
            if gs:
                cx, cz = P(xs[ix] - step / 2, zs[iz] - step / 2)
                ld.rectangle([cx, cz, cx + cell, cz + cell], fill=colour(gs, 140))
    for ix, iz, a, b in overlaps:
        cx, cz = P(xs[ix] - step / 2, zs[iz] - step / 2)
        ld.rectangle([cx, cz, cx + cell, cz + cell], fill=(200, 0, 255, 110))
    nz, nx = len(ghost), len(ghost[0]) if ghost else 0
    for iz in range(nz):
        for ix in range(nx):
            gs = ghost[iz][ix]
            if not gs:
                continue
            cx, cz = P(xs[ix] - step / 2, zs[iz] - step / 2)
            col = colour(gs, 255)
            if ix + 1 >= nx or ghost[iz][ix + 1] != gs:
                ld.line([(cx + cell - 1, cz), (cx + cell - 1, cz + cell)], fill=col, width=2)
            if ix == 0 or ghost[iz][ix - 1] != gs:
                ld.line([(cx + 1, cz), (cx + 1, cz + cell)], fill=col, width=2)
            if iz + 1 >= nz or ghost[iz + 1][ix] != gs:
                ld.line([(cx, cz + cell - 1), (cx + cell, cz + cell - 1)], fill=col, width=2)
            if iz == 0 or ghost[iz - 1][ix] != gs:
                ld.line([(cx, cz + 1), (cx + cell, cz + 1)], fill=col, width=2)
    img.alpha_composite(layer)

    # everything else goes on its own layer, which also tells where the legend must not go
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    small, mid, big = font(max(9, int(11 * args.scale))), font(max(11, int(14 * args.scale))), font(18)

    # quads and checkpoint lines
    for c in cps:
        for m, *_ in c.edges:
            d.polygon([P(*c.left), P(*m.left), P(*m.right), P(*c.right)], outline=(255, 255, 255, 70))
    for c in cps:
        key = c.type >= 0
        d.line([P(*c.left), P(*c.right)], fill=(0, 230, 255, 255) if key else (255, 220, 60, 220),
               width=3 if key else 1)
        for pt, col in ((c.left, (40, 220, 40, 255)), (c.right, (230, 40, 40, 255))):
            x, y = P(*pt)
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=col)
    label_boxes = []
    if not args.no_labels:
        # a checkpoint label goes above, below, left or right of one of the two ends of its checkpoint: the place
        # that covers the least of the labels already placed and of the end points (respawn labels and points
        # first, since they cannot move), and of the area of the quads, so that it stays off the track
        track = Image.new('L', img.size, 0)
        td = ImageDraw.Draw(track)
        for c in cps:
            for m, *_ in c.edges:
                td.polygon([P(*c.left), P(*m.left), P(*m.right), P(*c.right)], fill=255)
        placed, points = [], []
        for j, e in enumerate(kmp.jgpt):
            x, y = P(e[0], e[2])
            placed.append(d.textbbox((x + 6, y - 7), 'R%d' % j, font=small, stroke_width=2))
            points.append((x - 5, y - 5, x + 5, y + 5))
        for c in cps:
            for pt in (c.left, c.right):
                x, y = P(*pt)
                points.append((x - 3, y - 3, x + 3, y + 3))

        def overlap(box, boxes):
            return sum(max(0, min(box[2], p[2]) - max(box[0], p[0])) * max(0, min(box[3], p[3]) - max(box[1], p[1]))
                       for p in boxes)

        def on_track(box):
            l, t, r, b = (int(round(v)) for v in box)
            return track.crop((l, t, r, b)).histogram()[255] if r > l and b > t else 0

        def off_image(box):
            return max(0, -box[0]) + max(0, -box[1]) + max(0, box[2] - W) + max(0, box[3] - H)
        gap = 4
        for c in cps:
            key = c.type >= 0
            label = str(c.index) + ('K%d' % c.type if key else '')
            l, t, r, b = d.textbbox((0, 0), label, font=small, stroke_width=2)
            w, h = r - l, b - t
            boxes = []
            for ex, ez in (P(*c.left), P(*c.right)):
                boxes += [(ex - w / 2, ez - gap - h), (ex + gap, ez - h / 2),     # top, right
                          (ex - w / 2, ez + gap), (ex - gap - w, ez - h / 2)]     # bottom, left
            boxes = [(x, y, x + w, y + h) for x, y in boxes]
            best = min(range(len(boxes)), key=lambda k: (
                4 * overlap(boxes[k], placed) + 4 * overlap(boxes[k], points) + on_track(boxes[k])
                + 1000 * off_image(boxes[k]) + k))
            box = boxes[best]
            placed.append(box)
            text(d, (box[0] - l, box[1] - t), label, small, (0, 230, 255, 255) if key else (255, 255, 255, 255))
        label_boxes = placed

    # jumps: the border crossed by the kart
    for (ixa, iza), (ixb, izb), s, r, bridged, dist, kind, why in sorted(jumps, key=lambda j: -j[6]):
        ax, az = P(xs[ixa], zs[iza])
        bx, bz = P(xs[ixb], zs[izb])
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        if ixa != ixb:
            seg = [(mx, mz - cell / 2), (mx, mz + cell / 2)]
        else:
            seg = [(mx - cell / 2, mz), (mx + cell / 2, mz)]
        col, width = JUMP_STYLE[kind]
        d.line(seg, fill=col, width=width)

    # respawn points
    for j, e in enumerate(kmp.jgpt):
        x, y = P(e[0], e[2])
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(40, 90, 255, 255), outline=(255, 255, 255, 255))
        if not args.no_labels:
            text(d, (x + 6, y - 7), 'R%d' % j, small, (150, 190, 255, 255))

    # ghost area labels: one for the largest piece of each set of ghosts found in the same cells, naming all
    # of them, so that an area shared by several ghosts shows every one. Small pieces whose ghosts are all
    # labelled elsewhere are left out. Labels move up or down when they would cover an earlier one.
    pieces = {}                                          # ghost set -> its largest connected piece
    for gs, cl in ghost_regions(ghost):
        if len(cl) > len(pieces.get(gs, ())):
            pieces[gs] = cl
    placed, named = list(label_boxes), set()       # avoid the checkpoint and respawn labels too
    for gs, cl in sorted(pieces.items(), key=lambda kv: (-len(kv[1]), sorted(kv[0]))):
        if len(cl) * cell * cell < 150 and gs <= named:
            continue
        named |= gs
        ix = sorted(c[0] for c in cl)[len(cl) // 2]
        iz = sorted(c[1] for c in cl)[len(cl) // 2]
        best = min(cl, key=lambda c: (c[0] - ix) ** 2 + (c[1] - iz) ** 2)
        x, y = P(xs[best[0]], zs[best[1]])
        by_respawn = []                                  # 'ghost 118, 119 - R32, 120 - R33'
        for g in sorted(gs):
            if by_respawn and by_respawn[-1][1] == cps[g].jugem:
                by_respawn[-1][0].append(g)
            else:
                by_respawn.append(([g], cps[g].jugem))
        label = 'ghost ' + ', '.join('%s - R%d' % (', '.join(map(str, ids)), j) for ids, j in by_respawn)
        l, t, r, b = d.textbbox((0, 0), label, font=mid, stroke_width=2)
        tw, th = r - l, b - t
        x = min(max(x - tw / 2, 2 - l), W - 2 - r)       # centred on the cell, kept inside the image
        for k in (0, 1, -1, 2, -2, 3, -3, 4, -4):
            ty = min(max(y - th / 2 + k * (th + 2), 2 - t), H - 2 - b)
            box = (x + l, ty + t, x + r, ty + b)
            if not any(box[0] < p[2] and p[0] < box[2] and box[1] < p[3] and p[1] < box[3] for p in placed):
                break
        placed.append(box)
        text(d, (x, ty), label, mid, light(colour(gs, 255)))

    img.alpha_composite(over)

    # legend, in sections: mode, the course, overlapping quads, ghost checkpoints, the list of ghosts.
    # A row is (pieces of coloured text, font, sample): the sample, drawn before the text, shows what the row
    # is about; a row without a sample but after one is a continuation and is indented like its text.
    WHITE, GREY, ORANGE_TEXT = (255, 255, 255, 255), (200, 200, 200, 255), (255, 170, 40, 255)
    head = font(15)
    full = mode == MODE_FULL
    title = '%s  (%s)' % (name, 'online: ghost fix on' if args.online else 'offline / v1.0')
    mode_text = {
        MODE_FULL: ['Mode full: every ghost checkpoint found'],
        MODE_VIABLE: ['Mode viable: only the ghost checkpoints that are respawn glitches,',
                      'also those reached by a teleport or speed glitch'],
        MODE_PRACTICAL: ['Mode practical: only the ghost checkpoints that are respawn',
                         'glitches, reached by driving out of a quad'],
    }[mode]
    rows = [([(title, WHITE)], big, None)] + [([(t, WHITE)], mid, None) for t in mode_text]

    def section(name):
        rows.append(None)                                # a gap
        rows.append(([(name, WHITE)], head, None))

    def item(sample, *lines, colour=WHITE):
        rows.append(([(lines[0], colour)], mid, sample))
        rows.extend(([(t, colour)], mid, 'cont') for t in lines[1:])

    def note(t):
        rows.append(([(t, GREY)], mid, None))

    section('Course')
    item(('checkpoint',), 'checkpoint and its number, left end green, right end red')
    item(('line', (0, 230, 255, 255), 3), 'key checkpoint, labelled <number>K<key id>')
    item(('outline',), 'quad, the area between a checkpoint and the next one')
    item(('dot',), 'respawn point, labelled R<respawn id>')

    section('Overlapping quads (far apart along the course)')
    if overlaps or any(not j[4] for j in jumps):
        item(('fill', (200, 0, 255, 110)), 'intersection of two quads far apart along the course')
        item(('border', RED, 4), 'limit where a kart leaving a quad gets the other one: the game',
             'accepts it and the respawn point changes (respawn glitch)')
        item(('border', ORANGE, 2), 'limit where a kart leaving a quad gets the other one: the game',
             'rejects it or the respawn point stays the same')
    else:
        note('none on this course')

    section('Ghost checkpoints')
    if reach:
        item(('fill', colour_for(0, 140)), 'ghost checkpoint area, one colour per set of ghosts found,',
             'labelled "ghost <checkpoints> - R<respawn point>"')
        item(('border', RED, 4), 'limit where a kart leaving a quad gets a ghost: the game accepts it',
             'and the respawn point changes (respawn glitch)')
        if full:
            item(('border', ORANGE, 2), 'limit where a kart leaving a quad gets a ghost: the game rejects it',
                 'or the respawn point stays the same')
        item(('quad', RED), 'a quad from which a ghost that is a respawn glitch is found')
        if full:
            item(('quad', ORANGE), 'a quad from which only ghosts that are not respawn glitches are found')

        section('Ghost list')
        note('"ghost <X> - R<Y>: <Z>": the ghost of checkpoint X, which respawns the kart at')
        note('respawn point Y, and the checkpoint ranges Z it is reached from: in red where')
        if full:
            note('it is a respawn glitch, in orange where the game rejects it or the respawn')
            note('point stays the same')
        else:
            note('it is a respawn glitch')
    else:
        note('none' + ('' if full else ' in this mode'))
    sample_w = 34
    wrap = max(d.textlength(r[0][0][0], font=r[1]) for r in rows[1:] if r) + sample_w
    for g in sorted(reach):
        pieces = [('ghost %d - R%d:' % (g, cps[g].jugem), WHITE)]
        pieces += id_ranges(reach[g], lambda s: RED if glitch[s, g] else ORANGE_TEXT)
        line, width = [], 0
        for t, col in pieces:                            # wrap between ids, indent the next lines
            w = d.textlength(' ' + t, font=mid)
            if line and width + w > wrap:
                rows.append((line, mid, None))
                line, width = [('   ', WHITE)], d.textlength('   ', font=mid)
            line.append((' ' + t if line else t, col))
            width += w
        rows.append((line, mid, None))

    def indent(r):
        return sample_w if r[2] else 0
    lw = int(max(indent(r) + sum(d.textlength(t, font=r[1]) for t, _ in r[0]) for r in rows if r)) + 16
    heights = [8 if r is None else 24 if r[1] is big else 20 for r in rows]
    lh = 12 + sum(heights)
    lx, ly, covered = place_legend(img.size, over, layer, lw, lh)
    if covered:                     # no free place: put the legend in a panel right of the map
        wide = Image.new('RGBA', (W + lw + 12, max(H, lh + 12)), (40, 40, 48, 255))
        wide.paste(img, (0, 0))
        img, lx, ly = wide, W + 6, 6
    legend = Image.new('RGBA', img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(legend)
    gd.rectangle([lx, ly, lx + lw, ly + lh], fill=(0, 0, 0, 170))
    y = ly + 4
    for r, h in zip(rows, heights):
        if r is not None:
            pieces, f, sample = r
            x = lx + 6
            if sample and sample != 'cont':
                draw_sample(gd, sample, x, y + 3, sample_w - 8, 12)
            x += indent(r)
            for t, col in pieces:
                text(gd, (x, y), t, f, col)
                x += d.textlength(t, font=f)
        y += h
    img.alpha_composite(legend)
    return img.convert('RGB')


# ---------------------------------------------------------------------------

ONE_LAP_COURSES = ('Gctr_WuhuIsland1', 'Gctr_WuhuIsland2', 'Gctr_RainbowRoad')   # course ids 8, 9, 13
SECTION_COURSES = ('Gctr_WuhuIsland2',)                                          # course id 9


def find_one(directory, pattern):
    hits = sorted(glob.glob(os.path.join(directory, pattern)))
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('directory', help='extracted course .szs directory')
    ap.add_argument('--kmp', help='KMP to use instead of the one in the directory')
    ap.add_argument('-o', '--output',
                    help='output PNG; a text report with the same name and .txt is written next to it. {mode} is '
                         'replaced by the mode; with several modes and no {mode}, _<mode> is added before the '
                         'extension (default: <directory name>_ghosts.png)')
    ap.add_argument('--laps', type=int,
                    help='laps of the course slot (default: 1 for Wuhu Loop, Maka Wuhu and Rainbow Road, '
                         'guessed from the directory name; 3 otherwise). Field::GetCurrentCourseLapNum. Only '
                         'whether it is 3 changes the result (LapRankChecker::m_course_lap_amount)')
    ap.add_argument('--online', action='store_true',
                    help='model an online race of v1.1+ for the player\'s kart (disable_ghost_checkpoints and '
                         'm_is_net_send set: a jump across key checkpoint sections is never accepted)')
    ap.add_argument('--mode', nargs='+', choices=list(MODES), default=[MODE_FULL],
                    help='which ghost candidates to show: full = all of them (default); viable = only respawn '
                         'glitches (red), from any checkpoint, also after a teleport or speed glitch; practical = '
                         'only respawn glitches that a kart gets by leaving the quad of that checkpoint, without '
                         'a teleport. Several modes can be given: the searches run once and one image and report '
                         'is written per mode')
    ap.add_argument('--step', type=float,
                    help='grid step: in map pixels (default 4), or in world units when no map is used '
                         '(default: 1/300 of the course size)')
    ap.add_argument('--scale', type=float, default=1.0, help='image scale relative to the map (default 1)')
    ap.add_argument('--max-skip', type=int, default=2,
                    help='changes of checkpoint up to this many checkpoints apart are normal (default 2)')
    ap.add_argument('--margin', type=float, default=0.08, help='extra border around the course (fraction)')
    ap.add_argument('--no-map', action='store_true', help='do not draw the course map')
    ap.add_argument('--no-labels', action='store_true', help='do not label checkpoints and respawn points')
    ap.add_argument('--jobs', type=int, default=os.cpu_count(), help='worker processes')
    args = ap.parse_args()

    directory = args.directory.rstrip('/\\')
    name = os.path.basename(directory)
    for suffix in ('.szs.d', '.szs', '.d'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    kmp_path = args.kmp
    if not kmp_path:
        hits = find_one(directory, '*.kmp')
        if len(hits) != 1:
            sys.exit('expected one .kmp in %s, found %d; use --kmp' % (directory, len(hits)))
        kmp_path = hits[0]
    kmp = Kmp(open(kmp_path, 'rb').read())
    cps, finish = build_checkpoints(kmp)
    laps = args.laps or (1 if name in ONE_LAP_COURSES else 3)
    if laps < 1:
        sys.exit('--laps must be at least 1')
    notes = []
    if name in SECTION_COURSES:
        notes.append('warning: %s uses sections; the game accepts checkpoint changes differently there, '
                     'so accepted/rejected is not reliable for this course' % name)
    if not cps:
        sys.exit('the KMP has no checkpoints')

    map_img = map_rect = None
    if not args.no_map:
        maps = find_one(directory, '*_map2.bclim')
        pos = [p for p in find_one(directory, '*') if os.path.basename(p) == 'UIMapPos.bin'
               or (os.path.isfile(p) and os.path.getsize(p) == 0x21)]
        if maps and pos:
            try:
                map_img = load_bclim(maps[0])
                map_rect = load_ui_map_pos(pos[0])
            except ValueError as e:
                notes.append('map not used: %s' % e)
                map_img = None
        else:
            notes.append('map not used: *_map2.bclim or UIMapPos.bin not found')

    xs_ = [c.left[0] for c in cps] + [c.right[0] for c in cps] + [e[0] for e in kmp.jgpt]
    zs_ = [c.left[1] for c in cps] + [c.right[1] for c in cps] + [e[2] for e in kmp.jgpt]
    if map_img is not None:
        xs_ += [map_rect[0], map_rect[2]]
        zs_ += [map_rect[1], map_rect[3]]
    x0, x1, z0, z1 = min(xs_), max(xs_), min(zs_), max(zs_)
    mx, mz = (x1 - x0) * args.margin, (z1 - z0) * args.margin
    bounds = (x0 - mx, z0 - mz, x1 + mx, z1 + mz)
    if map_img is not None:
        step = (args.step or 4) * abs(map_rect[2] - map_rect[0]) / map_img.width
    else:
        step = args.step or max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 300

    modes = list(dict.fromkeys(args.mode))
    out = args.output or '%s_ghosts.png' % name
    if '{mode}' not in out and len(modes) > 1:
        base, ext = os.path.splitext(out)
        out = base + '_{mode}' + (ext or '.png')
    for note in notes:
        print(note)
    print('%s: grid step %.0f units, %s, modes %s' % (name, step, kmp_path, ', '.join(modes)))
    analysis = analyse(cps, kmp.ckph, finish, laps, bounds, step, args.online, max(1, args.jobs), args.max_skip)
    for mode in modes:
        result = select(cps, kmp.ckph, finish, laps, args.max_skip, analysis, mode, args.online)
        lines = notes + report(args, name, cps, kmp, laps, step, result, mode)
        png = out.replace('{mode}', mode)
        render(args, name, cps, kmp, finish, map_img, map_rect, bounds, step, result, mode).save(png)
        txt = os.path.splitext(png)[0] + '.txt'
        with open(txt, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        if len(modes) == 1:
            print('\n'.join(lines[len(notes):]))
        print('\nwrote %s and %s' % (png, txt))


def report(args, name, cps, kmp, laps, step, result, mode):
    """The text report of one mode, as a list of lines."""
    xs, zs, inside, ghost, reach, glitch, jumps, overlaps = result
    finish = ([c.index for c in cps if c.type == 0] or [0])[-1]        # as build_checkpoints
    out = []
    line = out.append
    line('%s: %d checkpoints, %d key checkpoints, %d respawn points, %d lap(s), grid step %.0f units, %s, mode %s (%s)'
          % (name, len(cps), max_key(cps) + 1, len(kmp.jgpt), laps, step,
             'online (ghost fix on)' if args.online else 'offline / v1.0 (ghost fix off)', mode, MODES[mode]))

    area = step * step
    counts = {}
    for row in ghost:
        for gs in row:
            for g in gs:
                counts[g] = counts.get(g, 0) + 1
    line('\nGhost areas (outside every quad, the search still returns a checkpoint; found from the checkpoint '
          'the kart was in, also after a teleport or speed glitch):')
    if not counts:
        line('  none')
    for g in sorted(counts):
        line('  checkpoint %3d (key id %d, respawn point %d): about %.0f square units'
              % (g, cps[g].key, cps[g].jugem, counts[g] * area))
        for label, bad in (('respawn glitch from', True), ('no respawn glitch from', False)):
            ids = [s for s in reach[g] if glitch[s, g] == bad]
            if ids:
                line('      %s: %s' % (label, ', '.join(t for t, _ in id_ranges(ids, lambda s: 0))))

    line('\nJumps (a kart leaving quad A gets checkpoint B, more than %d checkpoints away):' % args.max_skip)
    groups = {}
    for ia, ib, s, r, bridged, dist, kind, why in jumps:
        k = (s, r, bridged, dist, kind, why)
        g = groups.setdefault(k, [0, [], []])
        g[0] += 1
        g[1].append(xs[ib[0]])
        g[2].append(zs[ib[1]])
    if not groups:
        line('  none')
    for (s, r, bridged, dist, kind, why), (n, gx, gz) in sorted(groups.items(), key=lambda kv: (kv[0][4], kv[0][0], kv[0][1])):
        how = 'ghost' if bridged else 'overlapping quad'
        forced = ' (the key id stays, Force_No_Lap_Completion is set)' \
            if kind != JUMP_REJECTED and skips_section(cps, finish, s, r) else ''
        skip = '%+d checkpoints' % dist if dist is not None else 'not connected'
        verdict = {
            JUMP_RESPAWN: 'ACCEPTED: a respawn now uses respawn point %d instead of %d' % (cps[r].jugem, cps[s].jugem),
            JUMP_SAME_RESPAWN: 'accepted, same respawn point %d (no effect on respawning)' % cps[r].jugem,
            JUMP_REJECTED: 'rejected: ' + {
                REJECT_SECTION: 'skips a whole key checkpoint section (sets Force_No_Lap_Completion until the kart is back)',
                REJECT_NOT_NEXT: 'same key checkpoint section, not next to the current checkpoint (the current checkpoint stays)',
            }.get(why, ''),
        }[kind]
        line('  %3d (key %d) -> %3d (key %d), %s, %s, %d cells, around x %.0f..%.0f z %.0f..%.0f: %s%s'
              % (s, cps[s].key, r, cps[r].key, how, skip, n, min(gx), max(gx), min(gz), max(gz), verdict, forced))

    pairs = {}
    for ix, iz, a, b in overlaps:
        pairs[(a, b)] = pairs.get((a, b), 0) + 1
    line('\nOverlapping quads far apart along the course:')
    if not pairs:
        line('  none')
    for (a, b), n in sorted(pairs.items()):
        line('  quads %d and %d: about %.0f square units' % (a, b, n * area))

    jcp = jugem_check_points(cps, kmp)
    missing = [j for j, c in enumerate(jcp) if c is None]
    if missing:
        line('\nRespawn points not inside any quad that names them (the kart keeps a default checkpoint): %s'
              % ', '.join(map(str, missing)))

    return out


if __name__ == '__main__':
    main()
