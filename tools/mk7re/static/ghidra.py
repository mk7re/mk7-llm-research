"""Headless Ghidra: one project under local/ghidra holding every image, used for decompilation."""
import os
import re
import subprocess
import sys

from .. import paths
from .image import Image

PROJECT_NAME = "mk7"
LANGUAGE = "ARM:LE:32:v6"      # the 3DS application core is an ARM11 MPCore (ARMv6K)
BSS_SIZE = 0x400000


def _headless() -> str:
    exe = paths.GHIDRA_HOME / "support" / "analyzeHeadless"
    if not exe.exists():
        raise SystemExit(f"Ghidra not found at {paths.GHIDRA_HOME}; set GHIDRA_INSTALL_DIR")
    return str(exe)


def _env() -> dict:
    # Keep Ghidra's settings and compiled-script cache inside the workspace too.
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(paths.GHIDRA_PROJECT_DIR / "xdg-config")
    env["XDG_CACHE_HOME"] = str(paths.GHIDRA_PROJECT_DIR / "xdg-cache")
    return env


def split_qualified(name: str) -> tuple[list[str], str]:
    """'A::B<C::D>::f(int) const' -> (['A', 'B<C::D>', 'f'], full signature)."""
    full = name
    prefix = ""
    m = re.match(r"(thunk\{[^}]*\}) to ", name)
    if m:
        prefix, name = m.group(1) + "_", name[m.end():]
    # Cut the parameter list: first '(' outside <> that is not part of "operator()".
    depth, cut = 0, len(name)
    i = 0
    while i < len(name):
        ch = name[i]
        if name.startswith("operator", i):
            i += len("operator")
            while i < len(name) and name[i] == " ":
                i += 1
            if name.startswith("()", i):
                i += 2
            elif name.startswith("<<", i) or name.startswith(">>", i) or name.startswith("->", i):
                i += 2
            elif i < len(name) and name[i] in "<>":
                i += 1
            continue
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "(" and depth == 0:
            cut = i
            break
        i += 1
    head = name[:cut]
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(head):
        if head.startswith("operator", i):
            cur += head[i:]
            break
        ch = head[i]
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if depth == 0 and head.startswith("::", i):
            parts.append(cur)
            cur = ""
            i += 2
            continue
        cur += ch
        i += 1
    parts.append(cur)
    parts = [re.sub(r"\s+", "_", p.strip()) or "_" for p in parts]
    parts[-1] = prefix + parts[-1]
    return parts, full


def write_symbol_map(img: Image):
    out = img.cache_path("ghidra.map")
    with open(out, "w", encoding="utf-8") as f:
        for s in img.symbols:
            parts, full = split_qualified(s.name)
            note = full + (f"   [{s.confidence}]" if s.inferred else "")
            f.write(f"{s.addr:x}\t{chr(0x1f).join(parts)}\t{note}\n")
    return out


def _run(cmd: list[str], log_name: str) -> int:
    paths.GHIDRA_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    log = paths.GHIDRA_PROJECT_DIR / log_name
    with open(log, "w") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=_env())
    return proc.returncode


def _script_args(img: Image) -> list[str]:
    return ["MK7ImportSymbols.java", str(write_symbol_map(img)), f"{img.text_end:x}", f"{BSS_SIZE:x}"]


def program_exists(img: Image) -> bool:
    return (paths.GHIDRA_PROJECT_DIR / f"{img.name}.done").exists()


def setup(img: Image) -> int:
    """Import, name and auto-analyze an image. Takes several minutes."""
    base = [
        _headless(), str(paths.GHIDRA_PROJECT_DIR), PROJECT_NAME,
        "-import", str(img.path), "-overwrite",
        "-loader", "BinaryLoader", "-loader-baseAddr", f"0x{img.base:x}",
        "-processor", LANGUAGE, "-cspec", "default",
        "-scriptPath", str(paths.GHIDRA_SCRIPT_DIR),
        "-preScript", *_script_args(img),
        "-analysisTimeoutPerFile", "7200",
    ]
    rc = _run(base, f"{img.name}.setup.log")
    log = (paths.GHIDRA_PROJECT_DIR / f"{img.name}.setup.log").read_text(errors="replace")
    ok = rc == 0 and "MK7ImportSymbols: named" in log and "Import failed" not in log
    marker = paths.GHIDRA_PROJECT_DIR / f"{img.name}.done"
    if ok:
        marker.write_text(img.digest)
    elif marker.exists():
        marker.unlink()
    return 0 if ok else 1


def sync(img: Image) -> int:
    """Re-apply the current symbol map to an already analyzed program."""
    cmd = [
        _headless(), str(paths.GHIDRA_PROJECT_DIR), PROJECT_NAME,
        "-process", img.path.name, "-noanalysis",
        "-scriptPath", str(paths.GHIDRA_SCRIPT_DIR),
        "-postScript", *_script_args(img),
    ]
    return _run(cmd, f"{img.name}.sync.log")


def decompile(img: Image, addrs: list[int], refresh: bool = False) -> dict[int, str]:
    if not program_exists(img):
        raise SystemExit(f"image {img.name!r} is not in the Ghidra project yet; run `mk7 ghidra setup -i {img.name}` "
                         "(several minutes) first")
    out_dir = paths.DECOMP_DIR / img.name
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [a for a in addrs if refresh or not (out_dir / f"{a:08x}.c").exists()]
    if todo:
        cmd = [
            _headless(), str(paths.GHIDRA_PROJECT_DIR), PROJECT_NAME,
            "-process", img.path.name, "-noanalysis", "-readOnly",
            "-scriptPath", str(paths.GHIDRA_SCRIPT_DIR),
            "-postScript", "MK7Decompile.java", str(out_dir), *[f"{a:x}" for a in todo],
        ]
        rc = _run(cmd, f"{img.name}.decomp.log")
        if rc != 0:
            print(f"ghidra exited with {rc}; see {paths.GHIDRA_PROJECT_DIR / (img.name + '.decomp.log')}", file=sys.stderr)
    result = {}
    for a in addrs:
        p = out_dir / f"{a:08x}.c"
        result[a] = p.read_text() if p.exists() else f"// no output for {a:08x}; see local/ghidra/{img.name}.decomp.log\n"
    return result
