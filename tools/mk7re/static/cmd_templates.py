"""CLI commands that only need the template/ files."""
import re
import sys

from .. import paths
from . import templates, verify


def _rel(path):
    return paths.rel(path)


def _pick(index: templates.Index, name: str) -> templates.Class:
    found = index.find(name)
    if not found:
        close = [c.qualname for c in index.classes if name.lower() in c.qualname.lower()]
        hint = f"; did you mean: {', '.join(close[:12])}" if close else ""
        raise SystemExit(f"no class named {name!r} in template/{hint}")
    if len({c.qualname for c in found}) > 1:
        raise SystemExit(f"{name!r} is ambiguous: {', '.join(sorted({c.qualname for c in found}))}")
    if len(found) > 1:
        print(f"note: {found[0].qualname} is declared {len(found)} times (version variants): "
              + ", ".join(f"{_rel(c.file)}:{c.line}" for c in found) + "; showing the first", file=sys.stderr)
    return found[0]


def _print_members(members, show_owner=False, only=None):
    for owner, m in members:
        if only and m.kind not in only:
            continue
        mark = {"member": " ", "unknown": "?", "gap": "-"}[m.kind]
        flags = " [conditional]" if m.conditional else ""
        own = f"  <{owner.name}>" if show_owner else ""
        comment = f"  // {m.comment}" if m.comment else ""
        print(f"  {mark} 0x{m.offset:04X}  0x{m.size:<4X} {m.decl}{flags}{own}{comment}")


def cmd_struct(args):
    index = templates.Index()
    cls = _pick(index, args.name)
    chain = index.chain(cls)
    print(f"{cls.keyword} {cls.qualname}   size 0x{cls.size:X}   {_rel(cls.file)}:{cls.line}")
    if cls.template:
        print(f"  {cls.template}")
    if cls.base:
        resolved = "" if len(chain) > 1 else "   (base not described by a template)"
        print(f"  base: {cls.base}   (0x{cls.base_size:X} bytes){resolved}")
    if len(chain) > 1:
        print("  chain: " + " -> ".join(c.qualname for c in chain))
    if cls.has_vtable:
        print("  has vtable" + ("" if cls.base else " (vptr at 0x0)"))
    total = cls.size - cls.base_size
    print(f"  own bytes: 0x{total:X}  named 0x{cls.known_bytes:X}  unknown 0x{cls.unknown_bytes:X}  "
          f"gap 0x{cls.gap_bytes:X}" + (f"  ({100 * cls.gap_bytes // total}% unexplored)" if total else ""))
    print("  legend: ' ' named   '?' typed but unnamed (/U/)   '-' gap")
    only = {"gap", "unknown"} if args.gaps else None
    if args.flat:
        _print_members(index.flat_members(cls), show_owner=True, only=only)
    else:
        _print_members([(cls, m) for m in cls.members], only=only)
    nested = [c for c in index.classes if c.qualname.startswith(cls.qualname + "::") and c.file == cls.file]
    if nested:
        print("  nested: " + ", ".join(f"{c.name} (0x{c.size:X})" for c in nested))
    derived = [c for c in index.classes if index.resolve_base(c) is cls]
    if derived:
        print("  derived: " + ", ".join(c.qualname for c in derived))


def cmd_field(args):
    index = templates.Index()
    cls = _pick(index, args.name)
    offset = int(args.offset, 0)
    if not 0 <= offset < cls.size:
        raise SystemExit(f"offset 0x{offset:X} is outside {cls.qualname} (size 0x{cls.size:X})")
    chain = index.chain(cls)
    for c in chain:
        m = c.member_at(offset)
        if m:
            inner = f" +0x{offset - m.offset:X}" if offset != m.offset else ""
            print(f"{c.qualname} +0x{offset:X} -> {m.kind}: {m.decl}{inner}   "
                  f"(O:0x{m.offset:X}, S:0x{m.size:X})   {_rel(c.file)}:{c.line}")
            if m.comment:
                print(f"  // {m.comment}")
            # Descend into by-value members whose type is itself a known class.
            sub = index.find(m.type) if m.kind == "member" and "*" not in m.type and "[" not in m.type else []
            if len(sub) == 1 and sub[0].size == m.size:
                inner_m = sub[0].member_at(offset - m.offset)
                if inner_m:
                    print(f"  inside {sub[0].qualname} +0x{offset - m.offset:X} -> {inner_m.kind}: {inner_m.decl}")
            return
    last = chain[-1]
    if last.base and offset < last.base_size:
        print(f"{cls.qualname} +0x{offset:X} is inside base {last.base}, which has no template "
              f"(look in vendor/ or the hand-written headers)")
    elif last.has_vtable and offset < 4:
        print(f"{cls.qualname} +0x{offset:X} is the vtable pointer of {last.qualname}")
    else:
        print(f"{cls.qualname} +0x{offset:X}: nothing declared")


def cmd_gaps(args):
    index = templates.Index()
    rows = []
    for c in index.classes:
        if args.filter and not re.search(args.filter, c.qualname, re.I):
            continue
        own = c.size - c.base_size
        unexplored = c.gap_bytes + (c.unknown_bytes if args.unknown else 0)
        if unexplored >= args.min:
            rows.append((unexplored, own, c))
    rows.sort(key=lambda r: (-r[0], r[2].qualname))
    print(f"{'unexpl.':>8} {'own':>8}  {'%':>3}  class")
    for unexplored, own, c in rows[:args.limit]:
        pct = 100 * unexplored // own if own else 0
        print(f"0x{unexplored:>6X} 0x{own:>6X}  {pct:>3}  {c.qualname}   {_rel(c.file)}:{c.line}")
    total_own = sum(c.size - c.base_size for c in index.classes)
    total_gap = sum(c.gap_bytes for c in index.classes)
    print(f"{len(rows)} classes match; repo-wide {total_gap}/{total_own} bytes "
          f"({100 * total_gap // total_own}%) are still gaps across {len(index.classes)} classes")


def cmd_find(args):
    index = templates.Index()
    rx = re.compile(args.pattern, re.I)
    hits = 0
    for c in index.classes:
        if rx.search(c.qualname):
            print(f"class   {c.qualname}  (0x{c.size:X})  {_rel(c.file)}:{c.line}")
            hits += 1
        for m in c.members:
            if m.kind != "gap" and (rx.search(m.decl) or (args.comments and rx.search(m.comment))):
                print(f"member  {c.qualname} +0x{m.offset:X}  {m.decl}" + (f"  // {m.comment}" if m.comment else ""))
                hits += 1
    if not hits:
        print("no matches")


def cmd_gen(args):
    changed = verify.generate()
    print(f"generated headers in {paths.rel(paths.INCLUDE_DIR)} ({changed} file(s) rewritten)")


def cmd_verify(args):
    changed = verify.generate()
    print(f"generated ({changed} file(s) rewritten)")
    index = templates.Index() if args.offsets else None
    todo = verify.versions() if args.all_versions else [verify.normalize_version(args.version)]
    failed = False
    for version in todo:
        for ns in ([None, "MK7Memory"] if args.namespace else [None]):
            label = version + (" +namespace" if ns else "")
            ok, out = verify.compile_check(version, ns)
            print(f"[{'ok' if ok else 'FAIL'}] sizeof asserts, {label}")
            if not ok:
                failed = True
                print(out if args.verbose else verify.summarize(out))
                continue
            if args.offsets:
                ok, out = verify.compile_check(version, ns, offsets=True, index=index)
                print(f"[{'ok' if ok else 'FAIL'}] per-member offset/size asserts, {label}")
                if not ok:
                    failed = True
                    print(out if args.verbose else verify.summarize(out, 200))
    return 1 if failed else 0


def register(sub):
    p = sub.add_parser("struct", help="show the layout of a class from template/")
    p.add_argument("name")
    p.add_argument("--flat", action="store_true", help="include members inherited from template-described bases")
    p.add_argument("--gaps", action="store_true", help="only show gaps and unnamed members")
    p.set_defaults(func=cmd_struct)

    p = sub.add_parser("field", help="what is at CLASS+OFFSET")
    p.add_argument("name")
    p.add_argument("offset")
    p.set_defaults(func=cmd_field)

    p = sub.add_parser("gaps", help="rank classes by unexplored bytes (research targets)")
    p.add_argument("filter", nargs="?", help="regex on the qualified class name")
    p.add_argument("--min", type=lambda s: int(s, 0), default=1)
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--unknown", action="store_true", help="count /U/ members as unexplored too")
    p.set_defaults(func=cmd_gaps)

    p = sub.add_parser("find", help="regex search over class and member names")
    p.add_argument("pattern")
    p.add_argument("--comments", action="store_true", help="also search member comments")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("gen", help="generate the headers with `make` (into <repo>/include, or next to a --templates copy)")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("verify", help="generate + compile-check the headers for the 3DS ABI")
    p.add_argument("--version", default=verify.DEFAULT_VERSION, help="GAME_VERSION (default USA_REV1, like CI)")
    p.add_argument("--all-versions", action="store_true")
    p.add_argument("--namespace", action="store_true", help="also check with MK7MEMORY_NAMESPACE, like CI")
    p.add_argument("--offsets", action="store_true", help="also assert offsetof/sizeof of every member")
    p.add_argument("-v", "--verbose", action="store_true", help="full compiler output")
    p.set_defaults(func=cmd_verify)
