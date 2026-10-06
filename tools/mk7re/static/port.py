"""Carry function names from an image that has a linker map to one that has not.

Two builds of the game share most of their code byte for byte once the things
that depend on link addresses are ignored: branch displacements and the
literal-pool words that hold addresses. Functions are matched in two passes:

  1. exact   - the masked body occurs exactly once in the target.
  2. call    - the function is called (or tail-called, or referenced from a
               literal pool) at the same position of an already matched pair.
               This resolves bodies that are too short or duplicated to be
               unique, and bodies that differ between builds.
  3. table   - the function sits in the same slot of a pointer table (vtable,
               state table) whose address is known in both images.

A `call`/`table` match whose body is not identical is the interesting kind for struct
research: the code changed between builds, often because a layout did.
"""
import array
import json
from collections import Counter

from .. import paths
from .image import Image

_WILD = -1
_MIN_EXACT_WORDS = 3
_PROPAGATE_MIN_SCORE = 0.95
_BSS_SPAN = 0x2000000
_TABLE_WALK_LIMIT = 512


def _norm(w: int) -> int:
    """Drop the displacement of B/BL: it depends on where things were linked."""
    if w & 0x0E000000 == 0x0A000000 and w >> 28 != 0xF:
        return w & 0xFF000000
    return w


def _literal_indexes(words, n: int, addr: int) -> set[int]:
    """Indexes (within the n-word function at addr) of literal-pool and jump-table words."""
    lits = set()
    for i in range(n):
        w = words[i]
        if w & 0x0FFFF000 == 0x079FF000:                 # ldr pc, [pc, rX, lsl #2]: inline jump table
            j = i + 2
            while j < n and not words[j] & 3 and addr <= words[j] < addr + n * 4:
                lits.add(j)
                j += 1
            continue
        if w & 0x0F7F0000 == 0x051F0000:                 # ldr rX, [pc, #imm]
            off = w & 0xFFF
            j = i + 2 + ((off if w & 0x00800000 else -off) >> 2)
            if 0 <= j < n:
                lits.add(j)
        elif w & 0x0F3F0E00 == 0x0D1F0A00:               # vldr sX/dX, [pc, #imm]
            off = (w & 0xFF) * 4
            j = i + 2 + ((off if w & 0x00800000 else -off) >> 2)
            if 0 <= j < n:
                lits.add(j)
                if w & 0x100 and j + 1 < n:              # double
                    lits.add(j + 1)
    return lits


def _is_address(img: Image, value: int) -> bool:
    return img.base <= value < img.end + _BSS_SPAN


class Func:
    """A source function prepared for matching."""

    def __init__(self, img: Image, addr: int, size: int):
        self.addr = addr
        self.n = size // 4
        i0 = (addr - img.base) // 4
        self.words = img.words[i0:i0 + self.n]
        self.lits = _literal_indexes(self.words, self.n, addr)
        self.masked = [
            _WILD if (j in self.lits and _is_address(img, w)) else _norm(w)
            for j, w in enumerate(self.words)
        ]

    def anchor(self) -> bytes:
        """Longest wildcard-free prefix, as bytes to search for."""
        k = 0
        while k < self.n and self.masked[k] != _WILD:
            k += 1
        return array.array("I", self.masked[:k]).tobytes()

    def matches_at(self, tnorm, ti: int) -> bool:
        if ti + self.n > len(tnorm):
            return False
        return all(m == _WILD or m == tnorm[ti + j] for j, m in enumerate(self.masked))

    def score_at(self, tnorm, ti: int) -> float:
        if ti < 0 or ti + self.n > len(tnorm) or not self.n:
            return 0.0
        same = sum(1 for j, m in enumerate(self.masked) if m == _WILD or m == tnorm[ti + j])
        return same / self.n


class Target:
    def __init__(self, img: Image):
        self.img = img
        self.text_words = (img.text_end - img.base) // 4
        self.norm = array.array("I", (_norm(w) for w in img.words[:self.text_words]))
        self.norm_bytes = self.norm.tobytes()

    def find(self, needle: bytes, limit: int = 64) -> list[int]:
        """Word indexes where needle occurs on a word boundary."""
        out = []
        pos = self.norm_bytes.find(needle)
        while pos != -1 and len(out) < limit:
            if pos % 4 == 0:
                out.append(pos // 4)
            pos = self.norm_bytes.find(needle, pos + 1)
        return out


def _branch_target(addr: int, index: int, w: int) -> int:
    off = w & 0x00FFFFFF
    if off & 0x800000:
        off -= 0x1000000
    return addr + (index + 2 + off) * 4


def port_all(src: Image, dst: Image, log=print) -> dict:
    if not src.has_full_symbols:
        raise SystemExit(f"image {src.name!r} has no linker map to port from")
    target = Target(dst)
    funcs = {s.addr: Func(src, s.addr, s.size) for s in src.symbols if src.in_text(s.addr) and s.size >= 4}
    names = {s.addr: s.name for s in src.symbols}

    matched: dict[int, tuple[int, str, float]] = {}    # src addr -> (dst addr, how, score)
    # ---- pass 1: unique exact bodies ----------------------------------------
    for addr, f in funcs.items():
        if f.n < _MIN_EXACT_WORDS:
            continue
        anchor = f.anchor()
        if len(anchor) < _MIN_EXACT_WORDS * 4:
            continue
        hits = [i for i in target.find(anchor, limit=8) if f.matches_at(target.norm, i)]
        if len(hits) == 1:
            matched[addr] = (dst.base + hits[0] * 4, "exact", 1.0)
    log(f"pass 1 (exact unique bodies): {len(matched)}/{len(funcs)} functions")

    # ---- pass 2/3: propagate through calls, literal pools and pointer tables ---
    data_votes: dict[int, Counter] = {}
    done: set[int] = set()
    walked: set[int] = set()
    twords = dst.words
    round_no = 0

    def accept(votes: dict[int, Counter], how: str) -> int:
        new = 0
        for saddr, counter in votes.items():
            if saddr in matched or saddr not in funcs or len(counter) != 1:
                continue
            (daddr, _count), = counter.items()
            if not dst.in_text(daddr):
                continue
            score = funcs[saddr].score_at(target.norm, (daddr - dst.base) // 4)
            matched[saddr] = (daddr, how, round(score, 3))
            new += 1
        return new

    while True:
        round_no += 1
        votes: dict[int, Counter] = {}
        for addr, (daddr, how, score) in matched.items():
            if addr in done or score < _PROPAGATE_MIN_SCORE:
                continue
            done.add(addr)
            f = funcs[addr]
            ti = (daddr - dst.base) // 4
            if ti + f.n > target.text_words:
                continue
            for j, w in enumerate(f.words):
                tw = twords[ti + j]
                if j in f.lits:
                    if _is_address(src, w) and _is_address(dst, tw):
                        if src.in_text(w) and dst.in_text(tw):
                            votes.setdefault(w, Counter())[tw] += 1
                        elif not src.in_text(w) and not dst.in_text(tw):
                            data_votes.setdefault(w, Counter())[tw] += 1
                elif w & 0x0E000000 == 0x0A000000 and w >> 28 != 0xF and _norm(w) == _norm(tw):
                    ts = _branch_target(addr, j, w)
                    if not addr <= ts < addr + f.n * 4:
                        votes.setdefault(ts, Counter())[_branch_target(daddr, j, tw)] += 1
        new_call = accept(votes, "call")

        # Pointer tables (vtables, state tables): once a table's address is known
        # in both images, its slots pair up one to one. Stop at the first slot
        # that disagrees with what is already established.
        votes = {}
        for s, counter in data_votes.items():
            if s in walked or len(counter) != 1:
                continue
            walked.add(s)
            (d, _count), = counter.items()
            if not (src.contains(s) and dst.contains(d)) or s & 3 or d & 3:
                continue
            for k in range(_TABLE_WALK_LIMIT):
                sa, da = s + 4 * k, d + 4 * k
                if not (src.contains(sa) and dst.contains(da)):
                    break
                sv, dv = src.u32(sa), dst.u32(da)
                s_fn, d_fn = src.in_text(sv) and not sv & 3, dst.in_text(dv) and not dv & 3
                if s_fn != d_fn:
                    break
                if not s_fn:
                    if sv != dv or k == 0:     # same non-pointer filler (0, this-adjust) may continue
                        break
                    continue
                if sv in matched and matched[sv][0] != dv:
                    break
                votes.setdefault(sv, Counter())[dv] += 1
        new_table = accept(votes, "table")
        log(f"pass 2 round {round_no}: +{new_call} via call/literal position, +{new_table} via pointer tables")
        if not new_call and not new_table:
            break

    # ---- result --------------------------------------------------------------
    by_dst: dict[int, list[int]] = {}
    for saddr, (daddr, _how, _score) in matched.items():
        by_dst.setdefault(daddr, []).append(saddr)
    functions = []
    for daddr in sorted(by_dst):
        srcs = sorted(by_dst[daddr], key=lambda a: (-matched[a][2], a))
        best = srcs[0]
        _d, how, score = matched[best]
        entry = {"addr": daddr, "name": names[best], "src": best, "how": how, "score": score,
                 "size": funcs[best].n * 4 if score == 1.0 else 0}
        if len(srcs) > 1:
            entry["aliases"] = [names[a] for a in srcs[1:]]
        functions.append(entry)
    data = [
        {"src": s, "dst": c.most_common(1)[0][0], "votes": c.most_common(1)[0][1]}
        for s, c in sorted(data_votes.items()) if len(c) == 1
    ]
    changed = sum(1 for e in functions if e["score"] < 1.0)
    result = {
        "source": src.name, "source_digest": src.digest, "target": dst.name, "target_digest": dst.digest,
        "stats": {"source_functions": len(funcs), "matched": len(matched), "target_functions_named": len(functions),
                  "exact": sum(1 for m in matched.values() if m[1] == "exact"),
                  "call": sum(1 for m in matched.values() if m[1] == "call"),
                  "table": sum(1 for m in matched.values() if m[1] == "table"),
                  "body_differs": changed, "data_addresses": len(data)},
        "functions": functions, "data": data,
    }
    paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ported_path(dst).write_text(json.dumps(result))
    return result


def ported_path(dst: Image):
    return paths.CACHE_DIR / f"{dst.name}.ported.json"


def load_ported(dst: Image) -> dict | None:
    p = ported_path(dst)
    return json.loads(p.read_text()) if p.exists() else None


def candidates(src: Image, dst: Image, addr: int, size: int, top: int = 5) -> list[tuple[int, float, int]]:
    """Fuzzy search for one function: [(dst addr, score, anchor words)] best first."""
    f = Func(src, addr, size)
    target = Target(dst)
    seen: dict[int, tuple[float, int]] = {}
    clean = 0
    while clean < f.n and f.masked[clean] != _WILD:
        clean += 1
    for k in (clean, 24, 16, 12, 8, 6, 4):
        if k > clean or k < 3:
            continue
        for ti in target.find(array.array("I", f.masked[:k]).tobytes(), limit=200):
            if ti not in seen:
                seen[ti] = (f.score_at(target.norm, ti), k)
        if len(seen) >= top and k <= 12:
            break
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    return [(dst.base + ti * 4, score, k) for ti, (score, k) in ranked[:top]]
