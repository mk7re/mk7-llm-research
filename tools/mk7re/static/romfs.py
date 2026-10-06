"""RomFS extraction: the game's data files, unpacked so they can be read next to the code.

Each archive of an image (images.json, `romfs`: mount name -> RomFS file) is
extracted to local/romfs/<image>/<mount name>/. Every `X.szs` in it is kept and
also unpacked to a folder `X.szs.d` beside it, so that anything ending in
`.szs.d` is unpacked archive contents and every other folder is the RomFS's own.

An .szs is a Yaz0-compressed SARC. MK7's SARCs store no file names, only their
hashes, so names come from a lookup table (data/HashTable.saht). The formats
follow EveryFileExplorer (3DS/SARC.cs, 3DS/SARCHashTable.cs).
"""
import hashlib
import json
import shutil
import struct
from pathlib import Path

from .. import paths

STAMP_NAME = ".mk7-romfs.json"
STAMP_FORMAT = 2
UNPACKED_SUFFIX = ".d"           # X.szs is unpacked to X.szs.d
# Tried as "<szs name><suffix>" for hashes the table does not know (as EveryFileExplorer does).
SZS_NAME_SUFFIXES = ("_map.bclim", "_map2.bclim", ".div", ".kcl", ".kmp", ".bcmdl", ".bclgt", ".bcfog",
                     "_ch0.bclgt", "_ch1.bclgt", "_ch2.bclgt", "_ch3.bclgt", "_ch4.bclgt", "_ch5.bclgt")


# ---- formats ----------------------------------------------------------------
def load_hash_table(path: Path) -> dict[int, str]:
    """SAHT: 'SAHT', u32 file size, u32 data offset, u32 count, then {u32 hash, name\\0, pad to 0x10}."""
    data = Path(path).read_bytes()
    if data[:4] != b"SAHT":
        raise SystemExit(f"{paths.rel(path)} is not a SARC hash table (no SAHT signature)")
    _size, pos, count = struct.unpack_from("<3I", data, 4)
    table = {}
    for _ in range(count):
        (name_hash,) = struct.unpack_from("<I", data, pos)
        end = data.index(b"\0", pos + 4)
        table[name_hash] = data[pos + 4:end].decode("ascii", "replace")
        pos = (end + 0x10) & ~0xF
    return table


def name_hash(name: str, multiplier: int = 0x65) -> int:
    value = 0
    for ch in name.encode("ascii", "replace"):
        value = (ch + value * multiplier) & 0xFFFFFFFF
    return value


def yaz0_decompress(data: bytes) -> bytes:
    if data[:4] != b"Yaz0":
        raise ValueError("no Yaz0 signature")
    (size,) = struct.unpack_from(">I", data, 4)
    out = bytearray(size)
    src, dst = 16, 0
    while dst < size:
        code = data[src]
        src += 1
        for bit in range(8):
            if dst >= size:
                break
            if code & (0x80 >> bit):
                out[dst] = data[src]
                src += 1
                dst += 1
                continue
            b1, b2 = data[src], data[src + 1]
            src += 2
            back = dst - (((b1 & 0xF) << 8 | b2) + 1)
            length = b1 >> 4
            if length == 0:
                length = data[src] + 0x12
                src += 1
            else:
                length += 2
            for _ in range(min(length, size - dst)):
                out[dst] = out[back]
                dst += 1
                back += 1
    return bytes(out)


def sarc_entries(data: bytes) -> tuple[int, list[tuple[int, bytes]]]:
    """(hash multiplier, [(name hash, file data)]) of a SARC."""
    if data[:4] != b"SARC":
        raise ValueError("no SARC signature")
    endian = "<" if data[6:8] == b"\xff\xfe" else ">"
    header_size, _bom, _file_size, data_offset = struct.unpack_from(endian + "HHII", data, 4)
    if data[header_size:header_size + 4] != b"SFAT":
        raise ValueError("no SFAT section")
    sfat_size, count, multiplier = struct.unpack_from(endian + "HHI", data, header_size + 4)
    entries = []
    pos = header_size + sfat_size
    for _ in range(count):
        file_hash, _name_offset, start, end = struct.unpack_from(endian + "4I", data, pos)
        entries.append((file_hash, data[data_offset + start:data_offset + end]))
        pos += 0x10
    return multiplier, entries


def _safe_relative(name: str) -> str | None:
    """A table name as a path inside the output folder, or None if it cannot be one."""
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def sarc_names(archive_stem: str, multiplier: int, hashes: list[int], table: dict[int, str]) -> dict[int, str | None]:
    """hash -> relative path, None for the hashes no name is known for."""
    guesses = {name_hash(archive_stem + suffix, multiplier): archive_stem + suffix for suffix in SZS_NAME_SUFFIXES}
    names, used = {}, set()
    for file_hash in hashes:
        name = table.get(file_hash) or guesses.get(file_hash)
        name = _safe_relative(name) if name else None
        if name is not None and name.lower() in used:
            name = None
        if name is not None:
            used.add(name.lower())
        names[file_hash] = name
    return names


def unnamed(file_hash: int) -> str:
    return f"0x{file_hash:08X}"


# ---- extraction -------------------------------------------------------------
def _pyctr_reader():
    try:
        from pyctr.type.romfs import RomFSReader
    except ImportError as exc:
        raise SystemExit(
            f"the pyctr package is needed to read RomFS files ({exc}).\n"
            f"Create the workspace environment once, from the repository root:\n"
            f"  python3 -m venv {paths.rel(paths.VENV_DIR)}\n"
            f"  {paths.rel(paths.VENV_DIR)}/bin/python -m pip install -r mk7-llm-research/requirements.txt\n"
            f"(see mk7-llm-research/docs/tooling/SETUP.md, Requirements)")
    return RomFSReader


def extract_romfs(source: Path, dest: Path) -> int:
    """Write every file of a RomFS under dest. Returns the number of files."""
    reader_class = _pyctr_reader()
    count = 0
    with reader_class(str(source)) as reader:
        def walk(romfs_path: str, out_dir: Path):
            nonlocal count
            out_dir.mkdir(parents=True, exist_ok=True)
            for name in reader.get_info_from_path(romfs_path).contents:
                child = romfs_path.rstrip("/") + "/" + name
                info = reader.get_info_from_path(child)
                if info.type == "dir":
                    walk(child, out_dir / name)
                else:
                    with reader.open(child) as src, open(out_dir / name, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    count += 1
        walk("/", dest)
    return count


def unpack_szs(szs: Path, table: dict[int, str]) -> tuple[int, int]:
    """Unpack X.szs into the folder X.szs.d beside it. Returns (files, files without a known name)."""
    out_dir = szs.with_name(szs.name + UNPACKED_SUFFIX)
    if out_dir.exists():
        raise SystemExit(f"cannot unpack {paths.rel(szs)}: {paths.rel(out_dir)} already exists")
    data = szs.read_bytes()
    if data[:4] == b"Yaz0":
        data = yaz0_decompress(data)
    multiplier, entries = sarc_entries(data)
    names = sarc_names(szs.stem, multiplier, [h for h, _ in entries], table)
    missing = 0
    for file_hash, content in entries:
        name = names[file_hash]
        if name is None:
            name = unnamed(file_hash)
            missing += 1
        target = out_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    out_dir.mkdir(exist_ok=True)     # an empty archive still gets its folder
    return len(entries), missing


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def read_stamp(dest: Path) -> dict | None:
    try:
        return json.loads((dest / STAMP_NAME).read_text())
    except (OSError, ValueError):
        return None


def extract_archive(source: Path, dest: Path, table_path: Path, force: bool = False, log=print) -> dict:
    """Extract one RomFS and unpack its .szs files; skipped when dest is already up to date."""
    key = {"format": STAMP_FORMAT, "source_sha1": sha1_file(source), "table_sha1": sha1_file(table_path)}
    stamp = read_stamp(dest)
    if stamp and not force and all(stamp.get(k) == v for k, v in key.items()):
        log(f"{paths.rel(dest)}: up to date")
        return stamp
    if dest.exists():
        shutil.rmtree(dest)
    table = load_hash_table(table_path)
    log(f"{paths.rel(source)} -> {paths.rel(dest)}")
    files = extract_romfs(source, dest)
    archives = entries = missing = 0
    for szs in sorted(dest.rglob("*.szs")):
        n, m = unpack_szs(szs, table)
        archives += 1
        entries += n
        missing += m
    stamp = dict(key, source=str(paths.rel(source)), files=files, szs=archives,
                 szs_files=entries, szs_unnamed=missing)
    (dest / STAMP_NAME).write_text(json.dumps(stamp, indent=2) + "\n")
    log(f"  {files} files, {archives} szs unpacked ({entries} files, {missing} without a known name)")
    return stamp
