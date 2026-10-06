"""Filesystem layout of the research workspace.

Committed files live directly under mk7-llm-research. Everything machine-local or
regenerable (caches, the Ghidra project, compile-check scratch) goes under
mk7-llm-research/local, and the game binaries under <repo>/local; folders named
`local` are ignored by git.

The generated headers are NOT copied into the workspace: they are produced by
the repository's own `make` into <repo>/include and used from there.
"""
import os
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPO = WORKSPACE.parent

TEMPLATE_DIR = REPO / "template"
VENDOR_DIR = REPO / "vendor"
INCLUDE_DIR = REPO / "include"
LOCAL_CODE_DIR = REPO / "local" / "code"

LOCAL_DIR = WORKSPACE / "local"
VERIFY_DIR = LOCAL_DIR / "verify"
CACHE_DIR = LOCAL_DIR / "cache"
DECOMP_DIR = LOCAL_DIR / "decomp"
GHIDRA_PROJECT_DIR = LOCAL_DIR / "ghidra"
ROMFS_DIR = LOCAL_DIR / "romfs"
VENV_DIR = LOCAL_DIR / "venv"
DATA_DIR = WORKSPACE / "tools" / "mk7re" / "static" / "data"
HASH_TABLE_FILE = DATA_DIR / "HashTable.saht"
GHIDRA_SCRIPT_DIR = WORKSPACE / "tools" / "mk7re" / "static" / "ghidra_scripts"
IMAGES_FILE = WORKSPACE / "images.json"

DEVKITPRO = Path(os.environ.get("DEVKITPRO", "/opt/devkitpro"))
DEVKITARM = Path(os.environ.get("DEVKITARM", str(DEVKITPRO / "devkitARM")))
ARM_PREFIX = DEVKITARM / "bin" / "arm-none-eabi-"
GHIDRA_HOME = Path(os.environ.get("GHIDRA_INSTALL_DIR", str(Path.home() / "ghidra")))


def use_templates(folder: str) -> None:
    """Work on a copy of the templates instead of <repo>/template.

    The headers of a copy are generated into the `include` folder next to it,
    never into <repo>/include.
    """
    global TEMPLATE_DIR, INCLUDE_DIR
    path = Path(folder).resolve()
    if not path.is_dir():
        raise SystemExit(f"template folder {folder} does not exist")
    if path == (REPO / "template").resolve():
        return
    TEMPLATE_DIR = path
    INCLUDE_DIR = path.parent / "include"


def rel(path: Path) -> Path:
    """Path relative to the repository when inside it, for display."""
    try:
        return Path(path).relative_to(REPO)
    except ValueError:
        return Path(path)


def arm_tool(name: str) -> str:
    return str(ARM_PREFIX) + name
