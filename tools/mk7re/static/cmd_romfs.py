"""`mk7 romfs`: extract the game's data files (see romfs.py)."""
from .. import paths
from . import romfs
from .image import default_image_name, load_registry


def _archives(args) -> tuple[str, dict]:
    """(image name, {mount name: RomFS file}) of the image the command is about."""
    registry = load_registry()
    name = args.image or default_image_name()
    if name not in registry["images"]:
        raise SystemExit(f"unknown image {name!r}; known: {', '.join(registry['images'])}")
    archives = registry["images"][name].get("romfs") or {}
    if not archives:
        raise SystemExit(f"image {name!r} has no `romfs` entry in images.json")
    return name, {mount: paths.REPO / path for mount, path in archives.items()}


def cmd_extract(args):
    name, archives = _archives(args)
    if not paths.HASH_TABLE_FILE.exists():
        raise SystemExit(f"{paths.rel(paths.HASH_TABLE_FILE)} is missing")
    failed = False
    for mount, source in archives.items():
        if not source.exists():
            print(f"{mount}: {paths.rel(source)} not found, skipped")
            failed = True
            continue
        romfs.extract_archive(source, paths.ROMFS_DIR / name / mount, paths.HASH_TABLE_FILE, force=args.force)
    return 1 if failed else 0


def cmd_status(args):
    name, archives = _archives(args)
    table_sha1 = romfs.sha1_file(paths.HASH_TABLE_FILE) if paths.HASH_TABLE_FILE.exists() else None
    for mount, source in archives.items():
        dest = paths.ROMFS_DIR / name / mount
        stamp = romfs.read_stamp(dest)
        print(f"{mount}:/  {paths.rel(source)} -> {paths.rel(dest)}")
        if not source.exists():
            print("  source file not found")
        if not stamp:
            print("  not extracted (run `mk7 romfs extract`)")
            continue
        state = "extracted"
        if stamp.get("format") != romfs.STAMP_FORMAT or stamp.get("table_sha1") != table_sha1 or (
                source.exists() and stamp.get("source_sha1") != romfs.sha1_file(source)):
            state = "out of date (run `mk7 romfs extract`)"
        print(f"  {state}   sha1 {stamp.get('source_sha1')}")
        print(f"  {stamp.get('files')} files, {stamp.get('szs')} szs unpacked "
              f"({stamp.get('szs_files')} files, {stamp.get('szs_unnamed')} without a known name)")


def register(sub):
    p = sub.add_parser("romfs", help="extract the game's data files (RomFS and the .szs archives in it)")
    actions = p.add_subparsers(dest="action", required=True, metavar="action")

    def image_opt(q):
        q.add_argument("-i", "--image", help="image name from images.json (default: the research target)")

    q = actions.add_parser("extract", help="extract every RomFS of the image and unpack its .szs files")
    q.add_argument("--force", action="store_true", help="extract again even when up to date")
    image_opt(q)
    q.set_defaults(func=cmd_extract)

    q = actions.add_parser("status", help="show what is extracted and where")
    image_opt(q)
    q.set_defaults(func=cmd_status)
