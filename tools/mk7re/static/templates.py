"""Index of the data structures described by the template/ files.

The repository's own process.py is reused for parsing, so the layout shown
here is exactly what `make` would generate (same offsets, same gap members).
"""
import importlib.util
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import paths

_spec = importlib.util.spec_from_file_location("mk7_process", paths.REPO / "process.py")
process = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(process)

_NAMESPACE_RE = re.compile(r"BEGIN_NAMESPACE\(\s*([\w:]+)\s*\)")
_PP_IF_RE = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b")
_PP_ENDIF_RE = re.compile(r"^\s*#\s*endif\b")
_FUNC_PTR_RE = re.compile(r"\(\s*(?:[\w:]+::)?\*\s*(\w+)\s*\)")  # also pointer-to-member
_DECL_RE = re.compile(r"^(?P<type>.*?)(?P<name>\w+)\s*(?P<array>(\[[^\]]*\]\s*)*)(?P<bits>:\s*\d+)?$")


@dataclass
class Member:
    decl: str           # declaration text as written in the template
    type: str
    name: str
    offset: int
    size: int
    kind: str           # "member" | "unknown" | "gap"
    comment: str = ""
    conditional: bool = False   # declared inside a preprocessor conditional
    bitfield: bool = False

    @property
    def end(self) -> int:
        return self.offset + self.size


@dataclass
class Class:
    name: str           # unqualified
    qualname: str       # Namespace::Outer::Name
    keyword: str        # "class" | "struct"
    size: int
    base: str | None
    base_size: int
    has_vtable: bool
    template: str | None
    file: Path
    line: int
    conditional: bool
    members: list[Member] = field(default_factory=list)

    @property
    def known_bytes(self) -> int:
        return sum(m.size for m in self.members if m.kind == "member")

    @property
    def gap_bytes(self) -> int:
        return sum(m.size for m in self.members if m.kind == "gap")

    @property
    def unknown_bytes(self) -> int:
        return sum(m.size for m in self.members if m.kind == "unknown")

    def member_at(self, offset: int) -> Member | None:
        for m in self.members:
            if m.offset <= offset < m.end:
                return m
        return None


def _split_decl(decl: str) -> tuple[str, str, bool]:
    decl = decl.strip()
    fp = _FUNC_PTR_RE.search(decl)
    if fp:
        return decl, fp.group(1), False
    m = _DECL_RE.match(decl)
    if not m:
        return decl, decl, False
    typ = (m.group("type").strip() + (" " + m.group("array").strip() if m.group("array") else "")).strip()
    return typ, m.group("name"), m.group("bits") is not None


class _DepthTracker:
    """Tracks preprocessor conditional nesting across plain template lines."""

    def __init__(self):
        self.depth = 0

    def feed(self, text: str):
        if _PP_IF_RE.match(text):
            self.depth += 1
        elif _PP_ENDIF_RE.match(text):
            self.depth = max(0, self.depth - 1)


def _line_numbers(path: Path) -> dict[str, list[int]]:
    """Map class name -> line numbers of its START_ commands, in file order."""
    out: dict[str, list[int]] = {}
    for no, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.search(r"/START_(?:CLASS|STRUCT)/.*?NAME@([^/]+)/", text, re.I)
        if m:
            out.setdefault(m.group(1), []).append(no)
    return out


def _collect(cp, scope: str, path: Path, pp: _DepthTracker, lines: dict, out: list[Class]):
    header = cp.elements[1 if cp.template is not None else 0].line
    keyword = "struct" if re.match(r"\s*struct\b", header) else "class"
    qual = f"{scope}::{cp.name}" if scope else cp.name
    line_list = lines.get(cp.name, [0])
    cls = Class(
        name=cp.name, qualname=qual, keyword=keyword, size=cp.size, base=cp.base,
        base_size=cp.base_size, has_vtable=cp.hasvtable, template=cp.template,
        file=path, line=line_list.pop(0) if line_list else 0, conditional=pp.depth > 0,
    )
    out.append(cls)
    outer_depth = pp.depth
    cp._calcElements()  # inserts the gap members, exactly as the generator does
    for el in cp.elements:
        if isinstance(el, process.ClassParser.Member):
            if el.isGap:
                kind, decl = "gap", el.name
            elif el.unknown:
                kind, decl = "unknown", f"{el.name} unk_0x{el.offset:X}"
            else:
                kind, decl = "member", el.name
            typ, name, bits = _split_decl(decl)
            cls.members.append(Member(
                decl=decl, type=typ, name=name, offset=el.offset, size=el.size, kind=kind,
                comment=el.comment.strip(), conditional=pp.depth > outer_depth, bitfield=bits,
            ))
        elif isinstance(el, process.ClassParser):
            _collect(el, qual, path, pp, lines, out)
        elif isinstance(el, process.Line):
            pp.feed(el.line)


def parse_file(path: Path) -> list[Class]:
    parser = process.FileParser(None, None)
    with open(path, encoding="utf-8") as f:
        for line in f:
            parser.processLine(line)
    out: list[Class] = []
    namespace = ""
    pp = _DepthTracker()
    lines = _line_numbers(path)
    for el in parser.elements:
        if isinstance(el, process.ClassParser):
            _collect(el, namespace, path, pp, lines, out)
        elif isinstance(el, process.Line):
            pp.feed(el.line)
            m = _NAMESPACE_RE.search(el.line)
            if m:
                namespace = m.group(1)
    return out


class Index:
    def __init__(self, root: Path | None = None):
        root = root or paths.TEMPLATE_DIR
        self.classes: list[Class] = []
        self.errors: list[tuple[Path, str]] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                self.classes.extend(parse_file(path))
            except Exception as e:  # template errors are reported, not fatal
                self.errors.append((path, str(e)))

    def find(self, name: str) -> list[Class]:
        """Resolve a possibly partially-qualified class name."""
        name = strip_template_args(name).strip().lstrip(":")
        exact = [c for c in self.classes if c.qualname == name]
        if exact:
            return exact
        suffix = [c for c in self.classes if c.qualname.endswith("::" + name)]
        if suffix:
            return suffix
        low = name.lower()
        return [c for c in self.classes if c.qualname.lower() == low or c.qualname.lower().endswith("::" + low)]

    def resolve_type(self, type_name: str, scope: Class) -> Class | None:
        """Class a type name refers to when written inside `scope` (C++-like lookup)."""
        name = strip_template_args(type_name)
        name = re.sub(r"\b(const|volatile|struct|class|public)\b", "", name).replace("*", "").replace("&", "").strip()
        if not name or "[" in name:
            return None
        parts = scope.qualname.split("::")
        while True:
            cand = [c for c in self.classes if c.qualname == "::".join(parts + [name])]
            if cand:
                return cand[0]
            if not parts:
                break
            parts.pop()
        found = self.find(name)
        return found[0] if len({c.qualname for c in found}) == 1 else None

    def resolve_base(self, cls: Class) -> Class | None:
        if not cls.base:
            return None
        if "<" in cls.base.split(",")[0]:
            return None     # template instantiations are not described by templates here
        return self.resolve_type(cls.base.split(",")[0], cls)

    def lookup(self, cls: Class, offset: int) -> tuple[Class, Member, int] | None:
        """(owner, member, offset inside member) for cls+offset, through bases and by-value members."""
        for c in self.chain(cls):
            m = c.member_at(offset)
            if m is None:
                continue
            inner = offset - m.offset
            if m.kind == "member" and "*" not in m.type and "[" not in m.type:
                sub = self.resolve_type(m.type, c)
                if sub is not None and sub.size == m.size and sub is not c:
                    deeper = self.lookup(sub, inner)
                    if deeper is not None:
                        return deeper
            return c, m, inner
        return None

    def pointee(self, owner: Class, member: Member) -> Class | None:
        """Class a pointer member points to, if the templates describe it."""
        if member.kind == "gap" or member.type.count("*") != 1 or "(" in member.decl:
            return None
        return self.resolve_type(member.type, owner)

    def chain(self, cls: Class) -> list[Class]:
        """Inheritance chain, most-derived first, as far as the templates know it."""
        out = [cls]
        while (base := self.resolve_base(out[-1])) is not None and base not in out:
            out.append(base)
        return out

    def flat_members(self, cls: Class) -> list[tuple[Class, Member]]:
        out = []
        for c in reversed(self.chain(cls)):
            out.extend((c, m) for m in c.members)
        return out


def strip_template_args(name: str) -> str:
    out, depth = [], 0
    for ch in name:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()


def render(path: Path) -> str:
    """Generated header text for one template file (what `make` would write)."""
    buf = io.StringIO()
    with open(path, encoding="utf-8") as f:
        process.FileParser(f, buf).processFile()
    return buf.getvalue()


_ENUM_RE = re.compile(r"\benum\s+(?:class\s+|struct\s+)?(\w+)\s*(?::\s*[\w:]+\s*)?\{(.*?)\}", re.S)
_ENUM_BIT_RE = re.compile(r"ENUM_BIT\(\s*(\d+)\s*\)")


def read_enum(name: str, root: Path | None = None) -> dict[int, str]:
    """Value -> enumerator of the enum called `name` in the template/ files ({} when not found).

    Enumerators without an explicit value count on from the previous one. Values are integer
    literals or ENUM_BIT(n); an enumerator with any other expression is left out, and so are
    the implicit ones after it.
    """
    for path in sorted((root or paths.TEMPLATE_DIR).rglob("*.hpp")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if name not in text:
            continue
        text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
        for m in _ENUM_RE.finditer(text):
            if m.group(1) != name:
                continue
            out: dict[int, str] = {}
            value: int | None = 0
            for item in m.group(2).split(","):
                key, _, expr = item.partition("=")
                key = key.strip()
                if not key:
                    continue
                if expr.strip():
                    expr = _ENUM_BIT_RE.sub(lambda b: str(1 << int(b.group(1))), expr.strip())
                    try:
                        value = int(expr, 0)
                    except ValueError:
                        value = None
                if value is not None:
                    out.setdefault(value, key)
                    value += 1
            return out
    return {}
