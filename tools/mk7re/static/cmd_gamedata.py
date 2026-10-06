"""`mk7 kmp`, `mk7 bseq`: read the game's data files (see kmp.py, bseq.py)."""
import sys

from .. import paths
from . import bseq, kmp
from .image import default_image_name


def _write(lines: list[str], out: str | None):
    text = "\n".join(lines) + "\n"
    if not out:
        sys.stdout.write(text)
        return
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {len(lines)} lines to {out}", file=sys.stderr)


def _common(q):
    q.add_argument("-i", "--image", help="image name from images.json (default: the research target)")
    q.add_argument("-o", "--output", metavar="FILE", help="write to this file instead of stdout")


def cmd_kmp_dump(args):
    path, origin = kmp.resolve(args.target, args.image or default_image_name(), args.base)
    data = kmp.Kmp(path.read_bytes(), path)
    selection = [kmp.parse_selection(s) for s in args.section] if args.section else None
    _write(kmp.dump(data, selection, origin), args.output)


def cmd_kmp_list(args):
    image = args.image or default_image_name()
    courses = kmp.course_files(image)
    if not courses:
        raise SystemExit(f"no KMP files under {paths.rel(paths.ROMFS_DIR / image)}; run `mk7 romfs extract -i {image}`")
    names = [s.name for s in kmp.SPECS]
    lines = [f"{'course':30} {'from':4} {'ver':5} " + " ".join(f"{n:>4}" for n in names)]
    for course, found in courses.items():
        for where in ("pat1", "rom") if args.base else ("pat1",) if "pat1" in found else ("rom",):
            if where not in found:
                continue
            k = kmp.Kmp(found[where].read_bytes(), found[where])
            counts = [k.sections[n].count if n in k.sections else "-" for n in names]
            lines.append(f"{course:30} {where:4} {k.version:<5X} " + " ".join(f"{c:>4}" for c in counts))
    lines.append("")
    lines.append("from: pat1 = the v1.2 override in pat1:/Patch/Course (what the game uses), rom = rom:/Course/<c>.szs"
                 + ("" if args.base else "; --base also lists the original of every overridden course"))
    _write(lines, args.output)


def cmd_kmp_fields(args):
    _write(kmp.field_table([kmp.spec(s) for s in args.section]), args.output)


def cmd_bseq_dump(args):
    image = args.image or default_image_name()
    path = bseq.resolve(args.target, image)
    data = bseq.Bseq(path.read_bytes(), path)
    origin = bseq.origin_of(path, image) if path.is_relative_to(paths.ROMFS_DIR) else ""
    name = data.file_name()
    if name and name != path.name:
        origin = f"{origin}, which is {name}".lstrip(", ")
    _write(bseq.dump(data, args.section, origin), args.output)


def cmd_bseq_list(args):
    image = args.image or default_image_name()
    found = bseq.files(image)
    if not found:
        raise SystemExit(f"no BSEQ files under {paths.rel(paths.ROMFS_DIR / image)}; run `mk7 romfs extract -i {image}`")
    lines = [f"{'stored as':28} {'name (from the root)':32} {'size':>6} {'blocks':>6} {"engines":13} checks"]
    for stored, path in sorted(found.items(), key=lambda kv: (bseq.Bseq(kv[1].read_bytes()).file_name() or kv[0])):
        b = bseq.Bseq(path.read_bytes(), path)
        name = b.file_name() or "?"
        shown = "" if name == stored else name
        engines = ",".join(sorted({m for _, _, m in b.engines})) or "-"
        failed = [t.split()[0] for ok, t in b.checks() if not ok]
        where = " (pat1)" if "pat1" in path.parts else ""
        lines.append(f"{stored + where:28} {shown:32} {len(b.data):6} {len(b.blocks):6} {engines:13} "
                     f"{'ok' if not failed else 'FAIL ' + ','.join(failed)}")
    lines.append("")
    lines.append("name: <root section>-<root mode>.<brs|bss>, shown when the archive stores the file by hash only; "
                 "engines: the modes of the engine creators")
    _write(lines, args.output)


def register(sub):
    p = sub.add_parser("kmp", help="dump KMP course data files (start points, CPU/item routes, checkpoints, objects, ...)")
    actions = p.add_subparsers(dest="action", required=True, metavar="action")
    sections = ", ".join(s.name for s in kmp.SPECS)

    q = actions.add_parser("dump", help="dump a KMP, whole or by section, as text",
                           description="Dump a KMP as text: one line per entry, `name=value` pairs. A course name "
                                       "picks the file the v1.2 game uses (the pat1:/Patch override when there is "
                                       f"one). Sections: {sections} (the reversed magics work too).")
    q.add_argument("target", help="course name (Gctr_DKJungle, or a unique part of it) or a .kmp path")
    q.add_argument("-s", "--section", action="append", metavar="SEC[:N[-M]]",
                   help="only this section, optionally only entries N..M (repeatable); default: the whole file, "
                        "with a check that every byte is accounted for")
    q.add_argument("--base", action="store_true", help="use rom:/Course/<c>.szs even when pat1:/Patch overrides it")
    _common(q)
    q.set_defaults(func=cmd_kmp_dump)

    q = actions.add_parser("list", help="every course KMP of the image, with its entry count per section")
    q.add_argument("--base", action="store_true", help="also list the original of the overridden courses")
    _common(q)
    q.set_defaults(func=cmd_kmp_list)

    q = actions.add_parser("fields", help="the layout of each section and where each field name comes from")
    q.add_argument("section", nargs="*", help="only these sections")
    q.add_argument("-o", "--output", metavar="FILE", help="write to this file instead of stdout")
    q.set_defaults(func=cmd_kmp_fields)

    p = sub.add_parser("bseq", help="dump the BSEQ scene and menu sequence files (.brs/.bss of UI/common.szs)")
    actions = p.add_subparsers(dest="action", required=True, metavar="action")
    q = actions.add_parser("dump", help="dump a BSEQ file, whole or in parts, as text",
                           description="Dump a BSEQ file as text: the header with the consistency checks, every "
                                       "section block with its code tables, subsections and flows (codes resolved "
                                       "to names), the engine creators and the strings nothing refers to.")
    q.add_argument("target", help="a file of UI/common.szs (Root-Default.brs, 0xB070E39E), a name whose file is "
                                  "stored by hash (BootScene-Default), or a path")
    q.add_argument("-s", "--section", action="append", metavar="PART",
                   help=f"only this part ({', '.join(bseq.PARTS)}), block (by name) or block index (#N) "
                        "(repeatable); default: everything, with a check that every byte is accounted for")
    _common(q)
    q.set_defaults(func=cmd_bseq_dump)

    q = actions.add_parser("list", help="every BSEQ file of UI/common.szs, with its name and checks")
    _common(q)
    q.set_defaults(func=cmd_bseq_list)
