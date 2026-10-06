"""ARM disassembly (via devkitARM objdump) with symbol and literal annotation."""
import re
import struct
import subprocess
from dataclasses import dataclass, field

from .. import paths
from .image import Image

_LINE_RE = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f]{8}) \t(\S+)(?:\t([^\t@;]*))?(?:\s*[@;] ?(.*))?$")
_PC_MEM_RE = re.compile(r"\[pc(?:, #(-?\d+))?\]")
_REG_ALIASES = {"sl": "r10", "fp": "r11", "ip": "r12", "sb": "r9"}


@dataclass
class Insn:
    addr: int
    word: int
    mnemonic: str
    operands: str
    is_literal: bool = False      # a literal-pool word, not an instruction
    target: int | None = None     # branch target
    literal_addr: int | None = None   # address read by a pc-relative load
    literal_size: int = 4
    note: str = ""
    jump_case: bool = False           # a jump-table entry (is_literal is set too)
    jump_targets: list = field(default_factory=list)   # for the instruction that indexes a jump table

    @property
    def cond(self) -> int:
        return self.word >> 28

    @property
    def conditional(self) -> bool:
        return self.cond < 0xE

    @property
    def is_bl(self) -> bool:
        return self.word & 0x0F000000 == 0x0B000000 and self.cond != 0xF

    @property
    def is_b(self) -> bool:
        return self.word & 0x0F000000 == 0x0A000000 and self.cond != 0xF

    @property
    def base_mnemonic(self) -> str:
        """Mnemonic without the condition suffix."""
        m = self.mnemonic
        return m[:-2] if self.conditional and len(m) > 2 else m

    @property
    def is_return(self) -> bool:
        if self.word & 0x0FFFFFFF == 0x012FFF1E:      # bx lr
            return True
        m = self.base_mnemonic
        if m in ("pop", "ldm", "ldmfd", "ldmia") and "pc}" in self.operands.replace(" ", ""):
            return True
        return m in ("mov", "ldr") and self.operands.startswith("pc,")

    def text(self) -> str:
        if self.is_literal:
            return f".word\t0x{self.word:08x}"
        return f"{self.mnemonic}\t{_hex_immediates(self.operands)}".rstrip()


def _hex_immediates(operands: str) -> str:
    """objdump prints immediates in decimal; struct offsets read better in hex."""
    def repl(m):
        v = int(m.group(1))
        return f"#{'-' if v < 0 else ''}0x{abs(v):x}" if abs(v) >= 10 else m.group(0)
    return re.sub(r"#(-?\d+)\b(?!\.)", repl, operands)


def norm_reg(name: str) -> str:
    name = name.strip().lower()
    return _REG_ALIASES.get(name, name)


def raw_disassemble(img: Image, start: int, end: int) -> list[Insn]:
    start &= ~3
    cmd = [
        paths.arm_tool("objdump"), "-D", "-b", "binary", "-marm",
        f"--adjust-vma=0x{img.base:x}", f"--start-address=0x{start:x}", f"--stop-address=0x{end:x}",
        str(img.path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    insns = []
    for line in out.splitlines():
        m = _LINE_RE.match(line)
        if m:
            insns.append(Insn(int(m.group(1), 16), int(m.group(2), 16), m.group(3), (m.group(4) or "").strip()))
    return insns


def _float_note(img: Image, addr: int, double: bool) -> str:
    if double:
        return f"{struct.unpack('<d', img.read(addr, 8))[0]:g} (f64)"
    return f"{struct.unpack('<f', img.read(addr, 4))[0]:g}f"


def value_note(img: Image, value: int) -> str:
    """What a 32-bit literal most likely is."""
    if img.contains(value) or img.segment(value) == "bss?":
        desc = img.describe(value)
        return f"-> {desc}" if desc else ""
    if value > 0xFFFF:
        f = struct.unpack("<f", struct.pack("<I", value))[0]
        if 1e-6 < abs(f) < 1e9 and float(f"{f:.6g}") == f and len(f"{f:g}") <= 9:
            return f"({f:g}f?)"
    return ""


def _adr_target(ins: Insn) -> int | None:
    from .xref import adr_target
    return adr_target(ins.addr, ins.word)


def disassemble(img: Image, start: int, end: int) -> list[Insn]:
    """Disassemble [start, end) and annotate branches, literals and pool words."""
    insns = raw_disassemble(img, start, end)
    by_addr = {i.addr: i for i in insns}
    literal_words: dict[int, int] = {}   # address -> size in bytes
    for ins in insns:
        if ins.is_b or ins.is_bl:
            off = ins.word & 0x00FFFFFF
            if off & 0x800000:
                off -= 0x1000000
            ins.target = ins.addr + 8 + off * 4
        m = _PC_MEM_RE.search(ins.operands)
        bm = ins.base_mnemonic
        if m and (bm.startswith("ldr") or bm.startswith("vldr")):
            ins.literal_addr = ins.addr + 8 + int(m.group(1) or 0)
            dreg = bm.startswith("vldr") and ins.operands.lstrip().startswith("d")
            ins.literal_size = 8 if dreg or bm.startswith("ldrd") else 4
            if start <= ins.literal_addr < end:
                literal_words[ins.literal_addr] = ins.literal_size
    # Inline jump tables: "ldr pc, [pc, rX, lsl #2]" is followed (one word later)
    # by the absolute addresses of the cases.
    for ins in insns:
        if ins.word & 0x0FFFF000 == 0x079FF000:
            a = ins.addr + 8
            while a in by_addr and not by_addr[a].word & 3 and start <= by_addr[a].word < end:
                literal_words[a] = 4
                by_addr[a].jump_case = True
                ins.jump_targets.append(by_addr[a].word)
                a += 4
    # Pool words decode as garbage instructions; mark them. Reaching a pool word
    # by fallthrough is impossible, so this cannot hide real code.
    for addr, size in literal_words.items():
        for a in range(addr, addr + size, 4):
            if a in by_addr:
                by_addr[a].is_literal = True
    for ins in insns:
        adr = None if ins.is_literal else _adr_target(ins)
        if adr is not None:
            ins.note = f"= 0x{adr:x} -> {img.describe(adr)}" if img.contains(adr) else f"= 0x{adr:x}"
            continue
        if ins.jump_case:
            ins.note = f"case -> loc_{ins.word:x}"
        elif ins.is_literal:
            ins.note = value_note(img, ins.word)
        elif ins.target is not None:
            if not (start <= ins.target < end) or ins.is_bl:
                ins.note = img.describe(ins.target) if img.in_text(ins.target) else ""
        elif ins.literal_addr is not None and img.contains(ins.literal_addr):
            if ins.base_mnemonic.startswith("vldr"):
                ins.note = "= " + _float_note(img, ins.literal_addr, ins.literal_size == 8)
            else:
                value = img.u32(ins.literal_addr)
                ins.note = f"= 0x{value:x} {value_note(img, value)}".rstrip()
    return insns


def function_insns(img: Image, addr: int) -> tuple[int, int, list[Insn]]:
    start, end = img.function_bounds(addr)
    return start, end, disassemble(img, start, end)


def format_listing(img: Image, insns: list[Insn], local: tuple[int, int] | None = None) -> str:
    labels = set()
    if local:
        labels = {i.target for i in insns if i.target is not None and not i.is_bl and local[0] <= i.target < local[1]}
        labels |= {i.word for i in insns if i.jump_case}
    lines = []
    for ins in insns:
        if ins.addr in labels:
            lines.append(f"  loc_{ins.addr:x}:")
        text = ins.text()
        if ins.target is not None and not ins.is_bl and ins.target in labels:
            text = f"{ins.mnemonic}\tloc_{ins.target:x}"
        note = f"\t; {ins.note}" if ins.note else ""
        lines.append(f"  {ins.addr:08x}  {ins.word:08x}  {text.expandtabs(8)}{note}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Field access analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Access:
    path: tuple        # offsets dereferenced from `this` to reach the object; () is this itself
    offset: int
    size: int          # bytes; 0 when only the address is taken
    kind: str          # "load" | "store" | "addr" | "loadm" | "storem"
    is_float: bool
    insn: int          # instruction address


_MEM_RE = re.compile(r"\[(\w+)(?:, #(-?\d+))?\](!)?(?:, #(-?\d+))?")
_MEM_INDEXED_RE = re.compile(r"\[(\w+), (-?\w+)(?:, [a-z]+ #\d+)?\]")
_LOADSTORE_RE = re.compile(r"^(v?)(ldr|str)(d|sb|sh|b|h)?$")
_NO_DEST_EXACT = {"b", "bl", "bx", "blx", "svc", "nop", "push", "bkpt"}
_NO_DEST_PREFIX = ("cmp", "cmn", "tst", "teq", "str", "stm", "pld", "mcr",
                   "vstr", "vcmp", "vpush", "vpop", "vmsr", "vstm", "vldm")
_TWO_DEST = ("ldrd", "umull", "smull", "umlal", "smlal")
_CORE_REG_RE = re.compile(r"^(r\d{1,2}|sl|fp|ip|sb|sp|lr|pc)$")
_CALL_CLOBBERS = ("r0", "r1", "r2", "r3", "r12", "lr")
_MAX_DEPTH = 2


def _dests(ins: Insn) -> list[str]:
    """Core registers written by an instruction (best effort, from the text)."""
    bm = ins.base_mnemonic
    ops = [o.strip() for o in ins.operands.split(",")]
    if bm in ("pop",) or bm.startswith("ldm"):
        regs = [norm_reg(r) for r in re.findall(r"[a-z]+\d*", ins.operands[ins.operands.find("{"):])]
        if bm.startswith("ldm") and "!" in ops[0]:
            regs.append(norm_reg(ops[0].rstrip("!")))
        return regs
    out = []
    # Base register writeback: "[rN, #x]!" or "[rN], #x".
    m = _MEM_RE.search(ins.operands)
    if m and (m.group(3) or m.group(4)):
        out.append(norm_reg(m.group(1)))
    if bm in _NO_DEST_EXACT or bm.startswith(_NO_DEST_PREFIX):
        return out
    if bm.startswith("v") and not (bm.startswith("vmov") or bm.startswith("vmrs")):
        return out
    count = 2 if any(bm.startswith(n) for n in _TWO_DEST) else 1
    for op in ops[:count]:
        if _CORE_REG_RE.match(op):
            out.append(norm_reg(op))
    return out


def _transfer(ins: Insn, state: dict, record=None) -> dict:
    """Apply one instruction to the alias state {reg: (path, offset)}."""
    if ins.is_literal:
        return state
    bm = ins.base_mnemonic
    ops = [o.strip() for o in ins.operands.split(",")]
    new_alias = None   # (reg, value) this instruction establishes

    m = _MEM_RE.search(ins.operands)
    ls = _LOADSTORE_RE.match(bm)
    if m and ls:
        base = norm_reg(m.group(1))
        if base in state and not m.group(4):
            path, off = state[base]
            imm = int(m.group(2) or 0)
            size = {"d": 8, "sb": 1, "b": 1, "sh": 2, "h": 2, None: 4}[ls.group(3)]
            is_float = bool(ls.group(1))
            if is_float:
                size = 8 if ops[0].startswith("d") else 4
            kind = "load" if ls.group(2) == "ldr" else "store"
            if record is not None:
                record(Access(path, off + imm, size, kind, is_float, ins.addr))
            if kind == "load" and size == 4 and not is_float and not ins.conditional and len(path) < _MAX_DEPTH:
                new_alias = (norm_reg(ops[0]), (path + (off + imm,), 0))
    elif ls is None and (bm.startswith("ldm") or bm.startswith("stm")) and norm_reg(ops[0].rstrip("!")) in state:
        path, off = state[norm_reg(ops[0].rstrip("!"))]
        n = len(re.findall(r"[a-z]+\d*", ins.operands[ins.operands.find("{"):]))
        if record is not None and bm in ("ldm", "stm", "ldmia", "stmia"):
            record(Access(path, off, 4 * n, "loadm" if bm.startswith("ldm") else "storem", False, ins.addr))
    elif ls and _MEM_INDEXED_RE.search(ins.operands):
        mi = _MEM_INDEXED_RE.search(ins.operands)
        base = norm_reg(mi.group(1))
        if base in state and record is not None:
            path, off = state[base]
            record(Access(path, off, 0, "index", False, ins.addr))

    if bm == "mov" and len(ops) == 2 and norm_reg(ops[1]) in state and not ins.conditional:
        new_alias = (norm_reg(ops[0]), state[norm_reg(ops[1])])
    elif bm in ("add", "sub") and len(ops) == 3 and norm_reg(ops[1]) in state and ops[2].startswith("#") and not ins.conditional:
        path, off = state[norm_reg(ops[1])]
        imm = int(ops[2][1:], 0)
        value = (path, off + (imm if bm == "add" else -imm))
        new_alias = (norm_reg(ops[0]), value)
        if record is not None:
            record(Access(path, value[1], 0, "addr", False, ins.addr))

    out = dict(state)
    if ins.is_bl or bm in ("blx", "svc"):
        for r in _CALL_CLOBBERS:
            out.pop(r, None)
    for r in _dests(ins):
        out.pop(r, None)
    if new_alias:
        out[new_alias[0]] = new_alias[1]
    return out


def _meet(a: dict | None, b: dict) -> dict:
    if a is None:
        return dict(b)
    return {r: v for r, v in a.items() if b.get(r) == v}


def field_accesses(insns: list[Insn], this_reg: str = "r0") -> list[Access]:
    """Memory accesses relative to the pointer passed in `this_reg`.

    A forward dataflow over the function's CFG tracks which registers hold
    `this + k` or a pointer loaded from a field of `this`, so accesses through
    copies (mov r4, r0), adjusted pointers (add r0, r4, #0x400) and one or two
    levels of member pointers are all attributed. It is an approximation:
    values saved to the stack and reloaded are lost, and a register-held `this`
    passed on to a callee is not followed.
    """
    code = [i for i in insns if not i.is_literal]
    if not code:
        return []
    index = {i.addr: n for n, i in enumerate(code)}
    lo, hi = code[0].addr, code[-1].addr + 4

    leaders = {0}
    for ins in code:
        leaders.update(index[t] for t in ins.jump_targets if t in index)
    for n, ins in enumerate(code):
        if ins.is_b and ins.target in index:
            leaders.add(index[ins.target])
        if (ins.is_b or ins.is_return or ins.operands.startswith("pc,")) and n + 1 < len(code):
            leaders.add(n + 1)
    order = sorted(leaders)
    block_end = {s: (order[k + 1] if k + 1 < len(order) else len(code)) for k, s in enumerate(order)}

    def successors(s: int) -> list[int]:
        last = code[block_end[s] - 1]
        nxt = block_end[s] if block_end[s] < len(code) else None
        succ = []
        if last.is_b:
            if last.target in index:
                succ.append(index[last.target])
            if last.conditional and nxt is not None:
                succ.append(nxt)
        elif last.is_return or last.operands.startswith("pc,"):
            if last.conditional and nxt is not None:
                succ.append(nxt)
            succ.extend(index[t] for t in last.jump_targets if t in index)
            # Jump table: "add pc, pc, rX, lsl #2" is followed by one branch per case.
            if last.base_mnemonic == "add" and nxt is not None:
                k = nxt + 1 if last.conditional else nxt
                while k < len(code) and code[k].is_b and not code[k].conditional:
                    succ.append(k)
                    k += 1
        elif nxt is not None:
            succ.append(nxt)
        return [x for x in succ if x in block_end]

    entry = {this_reg: ((), 0)}
    in_state: dict[int, dict | None] = {s: None for s in order}
    in_state[0] = entry
    work = [0]
    while work:
        s = work.pop()
        state = in_state[s]
        for ins in code[s:block_end[s]]:
            state = _transfer(ins, state)
        for t in successors(s):
            merged = _meet(in_state[t], state)
            if merged != in_state[t]:
                in_state[t] = merged
                work.append(t)

    accesses: list[Access] = []
    for s in order:
        state = in_state[s]
        if state is None:       # unreachable by the CFG we built (e.g. unusual jump table)
            continue
        for ins in code[s:block_end[s]]:
            state = _transfer(ins, state, accesses.append)
    return accesses
