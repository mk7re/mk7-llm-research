"""CLI commands that work on the game binaries in local/code/."""
import difflib
import re
import struct
from collections import Counter

from .. import paths
from . import disasm, ghidra, port, templates, xref
from .image import Image, load_registry


def _img(args) -> Image:
    return Image(getattr(args, "image", None))


def _sym_line(img: Image, s) -> str:
    size = f"0x{s.size:<5X}" if s.size else "       "
    origin = f"   [{s.confidence}]" if s.inferred else (f"   [{s.source}]" if s.source != "xmap" else "")
    return f"{s.addr:08x}  {size} {img.label(s)}{origin}"


# ---- images -----------------------------------------------------------------
def cmd_images(args):
    registry = load_registry()
    for name in registry["images"]:
        img = Image(name)
        default = " (default)" if name == registry["default"] else ""
        role = registry["images"][name].get("role")
        default = (f" [{role}]" if role else "") + default
        counts = Counter(s.source for s in img.symbols)
        syms = ", ".join(f"{n} {k}" for k, n in counts.items()) or "none"
        print(f"{name}{default}: {img.path.relative_to(paths.REPO)}")
        print(f"  version {img.version or 'unknown'}   sha1 {img.digest}")
        print(f"  mapped 0x{img.base:08x}-0x{img.end:08x}   .text ends 0x{img.text_end:08x}   .bss starts 0x{img.end:08x}")
        print(f"  symbols: {syms}")
        if img.cfg.get("note"):
            print(f"  {img.cfg['note']}")


# ---- sym --------------------------------------------------------------------
def cmd_sym(args):
    img = _img(args)
    q = args.query
    if re.fullmatch(r"(0x)?[0-9a-fA-F]{5,8}", q):
        addr = int(q, 16)
        print(f"0x{addr:08x}: {img.segment(addr)}   {img.describe(addr)}")
        if img.in_text(addr):
            start, end = img.function_bounds(addr)
            s = img.symbol_at(start)
            print(f"  function 0x{start:08x}-0x{end:08x} (0x{end - start:X} bytes)" + (f"   {_sym_line(img, s)}" if s else "   no name"))
        elif img.contains(addr):
            print(f"  value 0x{img.u32(addr & ~3):08x}")
        return
    found = img.find_symbols(q, regex=args.regex)
    for s in found[:args.limit]:
        print(_sym_line(img, s))
    if len(found) > args.limit:
        print(f"... {len(found) - args.limit} more (raise --limit)")
    if not found:
        print(f"no symbol matching {q!r} in image {img.name!r}")
        return 1


# ---- dis --------------------------------------------------------------------
def cmd_dis(args):
    img = _img(args)
    addr = img.resolve(args.target)
    if args.length:
        start, end = addr, addr + int(args.length, 0)
        insns = disasm.disassemble(img, start, end)
    else:
        start, end, insns = disasm.function_insns(img, addr)
    s = img.symbol_at(start)
    exact = img.has_full_symbols or (s is not None and s.size)
    print(f"; {img.name}  {img.describe(start)}  0x{start:08x}-0x{end:08x}  ({(end - start) // 4} words)"
          + ("" if exact or args.length else "  [end is the next known entry point; may include a following function]"))
    if s and s.inferred:
        print(f"; name carried over: {s.confidence}")
    print(disasm.format_listing(img, insns, (start, end)))


# ---- xref -------------------------------------------------------------------
def cmd_xref(args):
    img = _img(args)
    addr = img.resolve(args.target)
    refs = xref.find_refs(img, addr)
    print(f"{len(refs)} reference(s) to 0x{addr:08x} {img.describe(addr)} in {img.name}")
    for r in refs[:args.limit]:
        if r.kind == "data":
            start = xref.table_start(img, r.addr)
            slot = (r.addr - start) // 4
            where = f"pointer table 0x{start:08x} slot {slot} (+0x{r.addr - start:X})" if slot or len(xref.vtable_at(img, start)) > 1 else "data word"
        else:
            where = img.describe(r.addr)
        print(f"  {r.addr:08x}  {r.kind:<7} {where}")
    if len(refs) > args.limit:
        print(f"  ... {len(refs) - args.limit} more (raise --limit)")


# ---- vtable -----------------------------------------------------------------
def cmd_vtable(args):
    img = _img(args)
    addr = int(args.addr, 16)
    if args.containing:
        addr = xref.table_start(img, addr)
    slots = xref.vtable_at(img, addr)
    if not slots:
        print(f"0x{addr:08x} does not hold a pointer into .text (value 0x{img.u32(addr):08x})" if img.contains(addr) else "address outside image")
        return 1
    users = [r for r in xref.find_refs(img, addr) if r.kind == "literal"]
    print(f"pointer table at 0x{addr:08x} in {img.name}: {len(slots)} slots"
          + (f"; address loaded by {', '.join(sorted({img.describe(r.addr).split('+')[0] for r in users})[:6])}" if users else ""))
    for i, target in enumerate(slots):
        print(f"  [{i:3}] +0x{i * 4:03X}  {target:08x}  {img.describe(target)}")


# ---- read -------------------------------------------------------------------
def cmd_read(args):
    img = _img(args)
    addr = img.resolve(args.addr) & ~3
    for i in range(args.count):
        a = addr + i * 4
        if not img.contains(a):
            print(f"  {a:08x}  (outside the file: .bss or unmapped)")
            break
        v = img.u32(a)
        f = struct.unpack("<f", struct.pack("<I", v))[0]
        note = disasm.value_note(img, v)
        text = img.cstring(a) if not img.in_text(a) else None
        extra = f"  str {text[:40]!r}" if text and len(text) >= 4 else ""
        print(f"  {a:08x}  {v:08x}  {f:<14g} {note}{extra}")


# ---- strings ----------------------------------------------------------------
def cmd_strings(args):
    img = _img(args)
    rx = re.compile(args.pattern.encode(), re.I)
    seen = 0
    for m in rx.finditer(img.data):
        # Expand to the whole NUL-terminated string around the hit.
        start = img.data.rfind(b"\0", 0, m.start()) + 1
        addr = img.base + start
        text = img.cstring(addr, 400)
        if text is None:
            continue
        refs = xref.find_refs(img, addr)
        users = ", ".join(sorted({img.describe(r.addr).split("+")[0] for r in refs})[:5])
        print(f"  {addr:08x}  {text[:100]!r}" + (f"   <- {users}" if users else ""))
        seen += 1
        if seen >= args.limit:
            print("  ... (raise --limit)")
            break
    if not seen:
        print("no matches (only 8-bit strings are searched)")


# ---- access -----------------------------------------------------------------
def _methods_of(img: Image, qualname: str) -> list:
    prefix = qualname + "::"
    out = []
    for s in img.symbols:
        head = s.name.split("(")[0]
        if head.startswith(prefix) and "::" not in head[len(prefix):] and img.in_text(s.addr):
            out.append(s)
    return out


def _hint(sizes: set, is_float: bool, deref: bool) -> str:
    if deref:
        return "ptr"
    if is_float:
        return "f64" if 8 in sizes else "f32"
    real = sorted(x for x in sizes if x)
    if not real:
        return "addr"
    return {1: "u8/bool", 2: "u16", 4: "u32", 8: "u64"}.get(real[0], f"{real[0]}b") + ("+" if len(real) > 1 else "")


def _where(index, cls, path: tuple, offset: int) -> str:
    """Describe this(->path...)+offset in terms of the templates."""
    if cls is None:
        return ""
    cur = cls
    for p in path:
        hit = index.lookup(cur, p)
        if hit is None:
            return ""
        owner, member, inner = hit
        nxt = index.pointee(owner, member) if inner == 0 else None
        if nxt is None:
            return f"(pointee of {member.decl} is not described)" if member.kind != "gap" else "(pointer lives in a gap)"
        cur = nxt
    hit = index.lookup(cur, offset)
    prefix = "" if cur is cls else f"{cur.qualname}: "
    if hit is None:
        if offset >= cur.size:
            return f"{prefix}OUTSIDE (size is 0x{cur.size:X})"
        chain = index.chain(cur)
        if chain[-1].base and offset < chain[-1].base_size:
            return f"{prefix}in base {chain[-1].base.split('<')[0]}"
        return f"{prefix}vtable pointer" if offset < 4 and chain[-1].has_vtable else f"{prefix}undeclared"
    owner, member, inner = hit
    own = "" if owner is cur else f"{owner.name}::"
    if member.kind == "gap":
        return f"{prefix}GAP {own}0x{member.offset:X}..0x{member.end:X}"
    return f"{prefix}{own}{member.decl}" + (f" +0x{inner:X}" if inner else "")


def cmd_access(args):
    img = _img(args)
    index = templates.Index()
    cls = None
    if args.cls:
        found = index.find(args.cls)
        cls = found[0] if found else None
        qual = cls.qualname if cls else args.cls
        funcs = _methods_of(img, qual)
        if args.match:
            rx = re.compile(args.match)
            funcs = [s for s in funcs if rx.search(s.name)]
        if not funcs:
            raise SystemExit(f"no functions named {qual}::* in image {img.name!r}")
        targets = [(s.addr, s.name.split("(")[0].rsplit("::", 1)[-1]) for s in funcs]
        title = f"{qual}" + (f" (size 0x{cls.size:X})" if cls else " (not in template/)")
    else:
        targets = []
        for t in args.targets:
            addr = img.resolve(t)
            targets.append((addr, img.describe(addr)))
        if args.as_class:
            found = index.find(args.as_class)
            if not found:
                raise SystemExit(f"no class named {args.as_class!r} in template/")
            cls = found[0]
        title = ", ".join(name for _, name in targets)
    if not targets:
        raise SystemExit("nothing to analyze: pass function names/addresses or --class")

    agg: dict[tuple, dict] = {}
    for addr, name in targets:
        _start, _end, insns = disasm.function_insns(img, addr)
        for a in disasm.field_accesses(insns, args.reg):
            e = agg.setdefault((a.path, a.offset), {"sizes": set(), "kinds": set(), "float": False, "funcs": Counter(), "insns": []})
            e["sizes"].add(a.size)
            e["kinds"].add(a.kind)
            e["float"] |= a.is_float
            e["funcs"][name] += 1
            e["insns"].append(a.insn)
    derefs = {path for (path, _off) in agg if path}
    print(f"field accesses through {args.reg} in {len(targets)} function(s) of {title}  [image {img.name}]")
    print("heuristic dataflow: confirm anything surprising with `mk7 dis`; static functions add noise")
    for path in sorted({p for p, _ in agg}):
        if path:
            chain = "this" + "".join(f"->[0x{p:X}]" for p in path)
            print(f"\n{chain}   {_where(index, cls, path[:-1], path[-1])}")
        else:
            print("\nthis")
        rows = sorted((off, e) for (p, off), e in agg.items() if p == path)
        for off, e in rows:
            is_ptr = (path + (off,)) in derefs
            rw = ("r" if e["kinds"] & {"load", "loadm"} else "") + ("w" if e["kinds"] & {"store", "storem"} else "")
            rw = rw or ("&" if "addr" in e["kinds"] else "[]")
            where = _where(index, cls, path, off)
            if args.gaps and cls is not None and "GAP" not in where and "OUTSIDE" not in where and "undeclared" not in where:
                continue
            users = ", ".join(f"{n}" + (f"({c})" if c > 1 else "") for n, c in e["funcs"].most_common(4))
            more = f" +{len(e['funcs']) - 4}" if len(e["funcs"]) > 4 else ""
            sign = "-" if off < 0 else ""
            print(f"  {sign}0x{abs(off):04X}  {rw:<2} {_hint(e['sizes'], e['float'], is_ptr):<8} {where:<44}  {users}{more}"
                  + (f"  @{e['insns'][0]:08x}" if args.addresses else ""))


# ---- port -------------------------------------------------------------------
def cmd_port(args):
    src, dst = Image(args.src), Image(args.dst)
    if args.all:
        result = port.port_all(src, dst)
        st = result["stats"]
        print(f"{st['matched']}/{st['source_functions']} functions of {src.name} located in {dst.name} "
              f"({st['exact']} exact, {st['call']} by call position, {st['table']} by table slot); "
              f"{st['body_differs']} of them have a different body; {st['data_addresses']} data addresses paired")
        print(f"written to {port.ported_path(dst).relative_to(paths.REPO)}; image {dst.name!r} now shows these names with a ~ prefix")
        return
    doc = port.load_ported(dst)
    if doc is None or doc["source_digest"] != src.digest or doc["target_digest"] != dst.digest:
        raise SystemExit("no up-to-date port map; run `mk7 port --all` first")
    if args.changed is not None:
        rx = re.compile(args.changed, re.I)
        rows = [e for e in doc["functions"] if e["score"] < 1.0 and rx.search(e["name"])]
        rows.sort(key=lambda e: (-e["score"], e["name"]))
        print(f"{len(rows)} function(s) matching /{args.changed}/ whose body differs between {src.name} and {dst.name} "
              f"(share of equal words; near 100% usually means one changed constant)")
        for e in rows[:args.limit]:
            print(f"  {e['score']:>6.1%}  {src.name}:{e['src']:08x} -> {dst.name}:{e['addr']:08x}  {e['how']:<5} {e['name']}")
        if len(rows) > args.limit:
            print(f"  ... {len(rows) - args.limit} more (raise --limit)")
        return
    if args.missing is not None:
        rx = re.compile(args.missing, re.I)
        have = {e["src"] for e in doc["functions"]}
        rows = [s for s in src.symbols if src.in_text(s.addr) and s.addr not in have and rx.search(s.name)]
        print(f"{len(rows)} function(s) matching /{args.missing}/ of {src.name} with no counterpart found in {dst.name}")
        for s in rows[:args.limit]:
            print(f"  {_sym_line(src, s)}")
        if len(rows) > args.limit:
            print(f"  ... {len(rows) - args.limit} more (raise --limit)")
        return
    if not args.target:
        raise SystemExit("give a function (name or address in the source image), --changed, --missing or --all")
    addr = src.resolve(args.target)
    if not src.in_text(addr):
        hit = [d for d in doc["data"] if d["src"] == addr]
        if hit:
            print(f"data {src.name}:0x{addr:08x} -> {dst.name}:0x{hit[0]['dst']:08x}  ({hit[0]['votes']} literal pool(s) agree)")
        else:
            near = [d for d in doc["data"] if 0 < addr - d["src"] <= 0x400]
            msg = f"no direct pairing for {src.name}:0x{addr:08x}"
            if near:
                d = max(near, key=lambda d: d["src"])
                msg += (f"; nearest paired address below is 0x{d['src']:08x} -> 0x{d['dst']:08x}, "
                        f"so a guess is 0x{d['dst'] + addr - d['src']:08x} (unverified)")
            print(msg)
        return
    start, end = src.function_bounds(addr)
    name = src.describe(start)
    hit = [e for e in doc["functions"] if e["src"] == start]
    if hit:
        e = hit[0]
        verdict = "identical body" if e["score"] == 1.0 else f"body differs ({e['score']:.0%} of words equal) - try `mk7 diff`"
        print(f"{name}\n  {src.name}:0x{start:08x} -> {dst.name}:0x{e['addr']:08x}   matched by {e['how']}; {verdict}")
        if e.get("aliases"):
            print("  same target also matched by: " + ", ".join(e["aliases"]))
        return
    print(f"{name} ({src.name}:0x{start:08x}) has no confirmed counterpart in {dst.name}. Closest bodies:")
    cands = port.candidates(src, dst, start, end - start)
    for daddr, score, k in cands:
        print(f"  {dst.name}:0x{daddr:08x}  {score:.0%} of words equal  (first {k} words identical)  {dst.describe(daddr)}")
    if not cands:
        print("  none: the first instructions do not occur in the target (function removed, or rewritten)")


# ---- diff -------------------------------------------------------------------
def _diff_text(img: Image, ins, data_name) -> str:
    """Instruction text with everything that only depends on link addresses normalized."""
    def value_text(v: int) -> str:
        if img.in_text(v):
            return img.describe(v).lstrip("~")
        if img.contains(v) or img.segment(v) == "bss?":
            return data_name(v)
        return f"0x{v:x}"

    if ins.jump_case:
        return ".word  case"
    if ins.is_literal:
        return f".word  {value_text(ins.word)}"
    if ins.target is not None:
        return f"{ins.mnemonic}  {img.describe(ins.target).lstrip('~') if ins.is_bl else 'loc'}"
    if ins.literal_addr is not None and img.contains(ins.literal_addr):
        reg = ins.operands.split(",")[0]
        if ins.base_mnemonic.startswith("vldr"):
            return f"{ins.mnemonic}  {reg}, ={ins.note.lstrip('= ')}"
        return f"{ins.mnemonic}  {reg}, ={value_text(img.u32(ins.literal_addr))}"
    return f"{ins.mnemonic}  {disasm._hex_immediates(ins.operands)}"


def cmd_diff(args):
    src, dst = Image(args.src), Image(args.dst)
    doc = port.load_ported(dst)
    if doc is None:
        raise SystemExit("run `mk7 port --all` first")
    saddr = src.resolve(args.target)
    sstart, send = src.function_bounds(saddr)
    hit = [e for e in doc["functions"] if e["src"] == sstart]
    if args.at:
        dstart = int(args.at, 16)
    elif hit:
        dstart = hit[0]["addr"]
    else:
        raise SystemExit(f"{src.describe(sstart)} has no counterpart in the port map; run `mk7 port` on it and pass --at ADDR")
    _known, dend = dst.function_bounds(dstart)
    sym = dst.symbol_at(dstart)
    end_known = dst.has_full_symbols or bool(sym and sym.size)
    if not end_known:
        # The end is only "the next known entry point"; do not drag in a whole neighbour.
        dend = min(dend, dstart + (send - sstart) + 0x100)
    # Data addresses differ between builds by construction; name paired ones alike.
    s2d = {d["src"]: d["dst"] for d in doc["data"]}
    paired_dst = set(s2d.values())
    a = disasm.disassemble(src, sstart, send)
    b = disasm.disassemble(dst, dstart, max(dend, dstart + 4))
    ta = [_diff_text(src, i, lambda v: f"data_{s2d[v]:08x}" if v in s2d else "<unpaired address>") for i in a]
    tb = [_diff_text(dst, i, lambda v: f"data_{v:08x}" if v in paired_dst else "<unpaired address>") for i in b]
    print(f"{src.describe(sstart)}\n  {src.name}:0x{sstart:08x} ({len(a)} words)  vs  {dst.name}:0x{dstart:08x}"
          + (f" ({len(b)} words)" if end_known else " (end unknown)") + f"   data addresses shown as in {dst.name}")
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if not end_known and i1 == len(a) and tag == "insert":
            continue    # whatever follows the function in the target image
        changed += 1
        print(f"  @@ {src.name}:0x{a[i1].addr if i1 < len(a) else send:08x} / {dst.name}:0x{b[j1].addr if j1 < len(b) else dend:08x}")
        for i in range(i1, i2):
            print(f"    - {ta[i]}")
        for j in range(j1, j2):
            print(f"    + {tb[j]}")
    if not changed:
        print("  no differences apart from link addresses")


# ---- ghidra / decomp --------------------------------------------------------
def cmd_ghidra(args):
    img = _img(args)
    if args.action == "status":
        for name in load_registry()["images"]:
            i = Image(name)
            state = "analyzed" if ghidra.program_exists(i) else "not imported (run `mk7 ghidra setup -i %s`)" % name
            print(f"{name}: {state}")
        print(f"project: {paths.GHIDRA_PROJECT_DIR.relative_to(paths.REPO)}/{ghidra.PROJECT_NAME}.gpr "
              f"(open it with {paths.GHIDRA_HOME}/ghidraRun; close it before using mk7 decomp)")
        return 0
    if args.action == "setup":
        print(f"importing and analyzing {img.name} headlessly; this takes several minutes "
              f"(log: local/ghidra/{img.name}.setup.log)", flush=True)
        rc = ghidra.setup(img)
        print("done" if rc == 0 else f"FAILED; read local/ghidra/{img.name}.setup.log")
        return rc
    rc = ghidra.sync(img)
    print("symbols re-applied; cached decompilations are stale, use `mk7 decomp --refresh`" if rc == 0
          else f"FAILED; read local/ghidra/{img.name}.sync.log")
    return rc


_PARAM_SCALE = {"undefined4": 4, "int": 4, "uint": 4, "float": 4, "undefined2": 2, "short": 2, "ushort": 2,
                "char": 1, "byte": 1, "undefined1": 1, "undefined": 1, "bool": 1}


def _decomp_offsets(code: str, param: str) -> set[int]:
    """Offsets from `param` that the decompiled text dereferences."""
    offsets = set()
    for m in re.finditer(rf"\b{param} \+ (0x[0-9a-f]+|\d+)\b", code):
        offsets.add(int(m.group(1), 0))
    decl = re.search(rf"(\w+) \*{param}\b", code)
    scale = _PARAM_SCALE.get(decl.group(1)) if decl else None
    if scale:
        for m in re.finditer(rf"\b{param}\[(0x[0-9a-f]+|\d+)\]", code):
            offsets.add(int(m.group(1), 0) * scale)
        if re.search(rf"\*{param}\b(?! *[,)])", code):
            offsets.add(0)
    return offsets


def cmd_decomp(args):
    img = _img(args)
    addrs = []
    for t in args.targets:
        start, _end = img.function_bounds(img.resolve(t))
        addrs.append(start)
    results = ghidra.decompile(img, addrs, refresh=args.refresh)
    cls = None
    if args.as_class:
        index = templates.Index()
        found = index.find(args.as_class)
        if not found:
            raise SystemExit(f"no class named {args.as_class!r} in template/")
        cls = found[0]
    for addr in addrs:
        code = results[addr]
        print(code.rstrip())
        if cls is not None:
            offsets = sorted(_decomp_offsets(code, args.param))
            print(f"\n// {args.param} as {cls.qualname}:")
            for off in offsets:
                print(f"//   +0x{off:X}  {_where(index, cls, (), off)}")
        print()


def register(sub):
    def image_opt(p):
        p.add_argument("-i", "--image", help="image name from images.json (default: the research target)")

    p = sub.add_parser("images", help="list the configured binaries")
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("sym", help="look up a symbol by name, or describe an address")
    p.add_argument("query")
    p.add_argument("-r", "--regex", action="store_true")
    p.add_argument("--limit", type=int, default=60)
    image_opt(p)
    p.set_defaults(func=cmd_sym)

    p = sub.add_parser("dis", help="disassemble the function at/containing a name or address")
    p.add_argument("target")
    p.add_argument("-n", "--length", help="disassemble exactly this many bytes from the address instead")
    image_opt(p)
    p.set_defaults(func=cmd_dis)

    p = sub.add_parser("xref", help="callers of a function / words that hold an address")
    p.add_argument("target")
    p.add_argument("--limit", type=int, default=80)
    image_opt(p)
    p.set_defaults(func=cmd_xref)

    p = sub.add_parser("vtable", help="dump a table of function pointers")
    p.add_argument("addr")
    p.add_argument("--containing", action="store_true", help="addr is some slot; walk back to the table start")
    image_opt(p)
    p.set_defaults(func=cmd_vtable)

    p = sub.add_parser("read", help="dump words at an address with interpretation")
    p.add_argument("addr")
    p.add_argument("count", nargs="?", type=int, default=8)
    image_opt(p)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("strings", help="regex search in strings, with the functions that reference them")
    p.add_argument("pattern")
    p.add_argument("--limit", type=int, default=40)
    image_opt(p)
    p.set_defaults(func=cmd_strings)

    p = sub.add_parser("access", help="which offsets of `this` functions read and write, mapped onto the templates")
    p.add_argument("targets", nargs="*", help="function names or addresses")
    p.add_argument("--class", dest="cls", help="analyze every method of this class")
    p.add_argument("--match", help="with --class: only methods matching this regex")
    p.add_argument("--as", dest="as_class", help="interpret `this` as this template class")
    p.add_argument("--reg", default="r0", help="register holding the object on entry (default r0)")
    p.add_argument("--gaps", action="store_true", help="only offsets the templates do not explain")
    p.add_argument("--addresses", action="store_true", help="show one instruction address per row")
    image_opt(p)
    p.set_defaults(func=cmd_access)

    p = sub.add_parser("ghidra", help="manage the headless Ghidra project used by `decomp`")
    p.add_argument("action", choices=["status", "setup", "sync"])
    image_opt(p)
    p.set_defaults(func=cmd_ghidra)

    p = sub.add_parser("decomp", help="decompile functions with Ghidra (needs `mk7 ghidra setup` once per image)")
    p.add_argument("targets", nargs="+")
    p.add_argument("--as", dest="as_class", help="map offsets off the first parameter onto this template class")
    p.add_argument("--param", default="param_1", help="parameter holding the object (default param_1)")
    p.add_argument("--refresh", action="store_true", help="ignore cached output")
    image_opt(p)
    p.set_defaults(func=cmd_decomp)

    p = sub.add_parser("port", help="find a function/data address of one image in another")
    p.add_argument("target", nargs="?")
    p.add_argument("--all", action="store_true", help="(re)build the full map")
    p.add_argument("--changed", metavar="REGEX", nargs="?", const="", help="list matched functions whose body differs")
    p.add_argument("--missing", metavar="REGEX", nargs="?", const="", help="list source functions with no counterpart")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--from", dest="src", default="dlp")
    p.add_argument("--to", dest="dst", default="eur2")
    p.set_defaults(func=cmd_port)

    p = sub.add_parser("diff", help="instruction-level differences of one function between two images")
    p.add_argument("target")
    p.add_argument("--at", help="address in the target image, overriding the port map")
    p.add_argument("--from", dest="src", default="dlp")
    p.add_argument("--to", dest="dst", default="eur2")
    p.set_defaults(func=cmd_diff)
