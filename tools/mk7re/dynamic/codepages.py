"""Memory for the tooling's own ARM code (eur2): pages mapped right after the
game's .bss before the game runs, so no code of the game is overwritten to
hold it.

`nninitRegion` (0x00100024, the first call of `__ctr_start`) zeroes the .bss,
0x00676FA0 up to 0x006BE508, and the kernel maps the image up to the end of
that page; the game never maps anything at 0x006BF000. `map_at_boot` maps
SIZE bytes there, read/write/execute, while the gdb stub holds the CPU at the
game's first instruction (0x00100000, see azahar.start): it writes a small
loader over the start of `__ctr_start`, lets the main thread run it up to its
last instruction, then puts the game's code and registers back as they were,
so the game then starts from its first instruction as if nothing had run.
`mk7 emu start` does this first, before any other patch is written.

The loader, through Azahar's HLE kernel (src/core/hle/kernel/svc.cpp):
1. svcCreateMemoryBlock(address 0): the kernel allocates the block from the
   linear memory of the BASE region, or of the application's region when the
   exheader asks for shared device memory. Measured with Azahar's New 3DS
   setting: physical address 0x2E004000, inside the BASE region (the last
   0x2000000 bytes of the FCRAM), so the game does not ask for it. The handle
   stays open for the whole run, which keeps the block allocated.
2. svcMapMemoryBlock maps it for a moment at TEMP, in the heap range, the
   only range where Azahar maps memory blocks.
3. svcMapProcessMemoryEx (0xA0, Luma3DS's custom call, which Azahar
   implements) maps the same memory a second time at BASE, read/write/execute;
   Azahar checks no address range for its destination.
4. svcUnmapMemoryBlock removes the mapping at TEMP again.

Why not svcControlMemory: Azahar ignores its region bits (it logs "ControlMemory
with specified region not supported") and commits the memory from the
application's region, charged to the game's Commit limit. The SDK sizes the
game's device memory as the application memory minus the Commit already used
(`sub_001011b4`, from `nnMain`), so the game would get less of it. Measured on
2026-10-05: device memory 0x3801000 bytes without the loader and with this
one, 0x37FD000 after a ControlMemory commit of 0x4000 (with region BASE
asked for).

What the game sees of it: one handle more in its handle table, one memory
block more counted in its resource limit, and the mapping itself.

The pages are split into fixed slots (below), one per piece of code; each
module checks that its code fits its slot (`check_fits`). Code is assembled
with devkitARM (`assemble_source`; C with `compile_c`) and written through
Azahar's RPC server, or through the stub at boot.
"""
import subprocess
import tempfile
from pathlib import Path

from .. import paths
from .gdbrsp import CPSR, PC, GdbError

ENTRY = 0x00100000          # __ctr_start, the game's first instruction
ENTRY_ORIG = 0xEB000007     # bl nninitRegion
BSS_START, BSS_END = 0x00676FA0, 0x006BE508   # the range nninitRegion zeroes
BASE = 0x006BF000           # the first page after the .bss
SIZE = 0x20000
TEMP = 0x0FF00000           # where the block is mapped while the loader runs (heap range, unused by the game)
CURRENT_PROCESS = 0xFFFF8001
PERM_DONTCARE = 0x10000000

# slots: (start, end)
HOOKS_CTRL = (BASE, BASE + 0x100)                   # hooks.py control block
HOOKS_CODE = (BASE + 0x100, BASE + 0x800)           # hooks.py code (kernel_set_state first)
VS_CODE = (BASE + 0x800, BASE + 0x1000)             # vs.py SOURCE: race and flow hooks, the BSEQ table
VS_MENU_CODE = (BASE + 0x1000, BASE + 0x1800)       # vs.py SOURCE_MENU: menu hooks
DRIVER_CTRL = (BASE + 0x1800, BASE + 0x2000)        # driver.py control block
DRIVER_CODE = (BASE + 0x2000, BASE + 0x8000)        # driver.py: the input hook and driver.c
DRIVER_RAM = (BASE + 0x8000, BASE + 0x18000)        # driver.c working memory (route search, route list)
# BASE + 0x18000 .. BASE + SIZE: free

LOADER = r"""
    .arm
    .syntax unified
    .global loader, done
    .text
loader:
    mov     r0, #{PERM_DONTCARE:#x}  @ other processes' permission
    mov     r1, #0                  @ address 0: the kernel allocates the block
    ldr     r2, ={SIZE:#x}
    mov     r3, #3                  @ read/write
    mov     r5, #1
    svc     0x1E                    @ svcCreateMemoryBlock -> r1 handle
    movs    r7, r0
    bmi     done
    mov     r6, r1
    mov     r0, r6
    ldr     r1, ={TEMP:#x}
    mov     r2, #3
    mov     r3, #{PERM_DONTCARE:#x}
    mov     r5, #2
    svc     0x1F                    @ svcMapMemoryBlock(handle, TEMP)
    movs    r7, r0
    bmi     done
    ldr     r0, ={CURRENT_PROCESS:#x}
    ldr     r1, ={BASE:#x}
    ldr     r2, ={CURRENT_PROCESS:#x}
    ldr     r3, ={TEMP:#x}
    ldr     r4, ={SIZE:#x}
    mov     r5, #3
    svc     0xA0                    @ svcMapProcessMemoryEx(self, BASE, self, TEMP, SIZE)
    movs    r7, r0
    bmi     done
    mov     r0, r6
    ldr     r1, ={TEMP:#x}
    mov     r5, #4
    svc     0x20                    @ svcUnmapMemoryBlock(handle, TEMP)
    mov     r7, r0
done:
    b       done
    .ltorg
"""
STEPS = {1: "svcCreateMemoryBlock", 2: "svcMapMemoryBlock", 3: "svcMapProcessMemoryEx", 4: "svcUnmapMemoryBlock"}


def assemble_source(src: str, base: int, names: tuple[str, ...]) -> tuple[bytes, dict[str, int]]:
    """Assemble ARM source with devkitARM, linked at `base`: the machine code
    and the addresses of the global symbols in `names`."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "code.s").write_text(src)
        run = lambda *a: subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True)
        try:
            run(paths.arm_tool("as"), "-mcpu=mpcore", "-o", tmp / "code.o", tmp / "code.s")
            run(paths.arm_tool("ld"), "-Ttext=%#x" % base, "-e", names[0], "-o", tmp / "code.elf", tmp / "code.o")
            run(paths.arm_tool("objcopy"), "-O", "binary", "-j", ".text", tmp / "code.elf", tmp / "code.bin")
            syms = run(paths.arm_tool("nm"), tmp / "code.elf").stdout
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"assembling failed:\n{e.stderr}")
        code = (tmp / "code.bin").read_bytes()
    entries = {}
    for line in syms.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in names:
            entries[parts[2]] = int(parts[0], 16)
    return code, entries


C_FLAGS = ("-mcpu=mpcore", "-marm", "-mfloat-abi=hard", "-mfpu=vfp", "-Os", "-ffreestanding", "-nostdlib",
           "-fno-math-errno", "-fno-common", "-fno-pic", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
           "-fno-exceptions", "-Wall", "-Werror")
LINK_SCRIPT = """
SECTIONS {{
    . = {base:#x};
    .text : {{ *(.text.entry) *(.text*) *(.rodata*) }}
    .data : {{ *(.data*) *(.bss*) *(COMMON) }}
    /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.attributes) *(.comment) *(.note*) }}
}}
ASSERT(SIZEOF(.data) == 0, "the code pages' C code must not have globals: keep state in its control block")
"""


def compile_c(c_src: Path, asm_src: str, base: int, names: tuple[str, ...],
              defines: dict[str, int]) -> tuple[bytes, dict[str, int]]:
    """Compile a C file and ARM source (its section `.text.entry` first) with
    devkitARM's gcc, linked at `base` with no library: the machine code
    (`.text` and the constants) and the addresses of the global symbols in
    `names`. `defines` become `-D` macros of both."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "entry.s").write_text(asm_src)
        (tmp / "link.ld").write_text(LINK_SCRIPT.format(base=base))
        dflags = ["-D%s=%#x" % kv for kv in defines.items()]
        run = lambda *a: subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True)
        try:
            run(paths.arm_tool("gcc"), *C_FLAGS, *dflags, "-c", "-o", tmp / "c.o", c_src)
            run(paths.arm_tool("as"), "-mcpu=mpcore", "-mfloat-abi=hard", "-o", tmp / "entry.o", tmp / "entry.s")
            run(paths.arm_tool("ld"), "-T", tmp / "link.ld", "-e", names[0], "-o", tmp / "code.elf",
                tmp / "entry.o", tmp / "c.o")
            run(paths.arm_tool("objcopy"), "-O", "binary", "-j", ".text", tmp / "code.elf", tmp / "code.bin")
            syms = run(paths.arm_tool("nm"), tmp / "code.elf").stdout
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"compiling {c_src.name} failed:\n{e.stderr}")
        code = (tmp / "code.bin").read_bytes()
    entries = {}
    for line in syms.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in names:
            entries[parts[2]] = int(parts[0], 16)
    return code, entries


def check_fits(slot: tuple[int, int], code: bytes, what: str):
    if slot[0] + len(code) > slot[1]:
        raise SystemExit(f"{what} ({len(code)} bytes) does not fit in its slot of the code pages "
                         f"({slot[0]:#x}-{slot[1]:#x}, codepages.py)")


def mapped_gdb(g) -> bool:
    """Whether the pages are mapped (the stub reports unmapped memory)."""
    try:
        g.read(BASE, 4)
        return True
    except GdbError:
        return False


def map_at_boot(g):
    """Map the pages through a GdbClient that holds the game at its first
    instruction (no instruction of the game has run yet)."""
    if g.read_register(PC) != ENTRY or g.u32(ENTRY) != ENTRY_ORIG:
        raise SystemExit("the game is not at its first instruction (or not the eur2 build); "
                         "the code pages can only be mapped at boot")
    if mapped_gdb(g):
        return
    code, entries = assemble_source(LOADER.format(PERM_DONTCARE=PERM_DONTCARE, SIZE=SIZE, TEMP=TEMP, BASE=BASE,
                                                  CURRENT_PROCESS=CURRENT_PROCESS), ENTRY, ("loader", "done"))
    regs = {r: g.read_register(r) for r in list(range(16)) + [CPSR]}
    orig = g.read(ENTRY, len(code))
    g.write(ENTRY, code)
    try:
        stop = g.run_to(entries["done"], timeout=10)
        if stop.pc != entries["done"]:
            raise SystemExit(f"the loader of the code pages stopped at {stop.pc} ({stop.packet})")
        step, result = g.read_register(5), g.read_register(7)
    finally:
        g.write(ENTRY, orig)
        for r, v in regs.items():
            g.write_register(r, v)
    if result & 0x80000000:
        raise SystemExit(f"mapping the code pages failed: {STEPS.get(step, step)} returned {result:#010x}")
    if not mapped_gdb(g):
        raise SystemExit(f"the code pages at {BASE:#x} are not mapped after the loader ran")
