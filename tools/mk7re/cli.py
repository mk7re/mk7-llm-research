"""mk7 - research helper for reversing Mario Kart 7 data structures."""
import argparse
import os
import sys

from . import paths
from .dynamic import cmd_emu
from .static import cmd_binary, cmd_gamedata, cmd_romfs, cmd_templates


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mk7", description=__doc__)
    parser.add_argument("--templates", metavar="DIR", default=os.environ.get("MK7_TEMPLATES"),
                        help="use this copy of the templates instead of <repo>/template; its headers are "
                             "generated into the `include` folder next to it (also: MK7_TEMPLATES)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    cmd_templates.register(sub)
    cmd_binary.register(sub)
    cmd_romfs.register(sub)
    cmd_gamedata.register(sub)
    cmd_emu.register(sub)
    args = parser.parse_args(argv)
    if args.templates:
        paths.use_templates(args.templates)
        print(f"[templates: {paths.rel(paths.TEMPLATE_DIR)}]", file=sys.stderr)
    try:
        return args.func(args) or 0
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
