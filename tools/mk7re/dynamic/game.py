"""Mario Kart 7 (eur2) seen through Azahar's RPC server and gdb stub.

Memory, code included, is read and written live through Azahar's RPC server
(rpc.py), while the game runs; the gdb stub is only connected for what needs
it: breakpoints, watchpoints and single steps (`Session.gdb`). The addresses and offsets are those of the v1.2
build (`eur2`) and come from the templates or from the research documents
named next to them. `Session` freezes the game at frame boundaries and runs it
frame by frame on request, through the hooks of hooks.py; state read while
frozen belongs to one frame.
"""
import struct
import time
from contextlib import contextmanager

from .hooks import PAD_A, Hooks
from .gdbrsp import GdbClient
from .memio import MemoryIO
from .rpc import RPC_PORT, RpcClient

# ---- addresses (eur2) -------------------------------------------------------
TITLE_ID = 0x0004000000030700   # Mario Kart 7 EUR
ROOT_SYSTEM = 0x006789B8        # System::RootSystem instance (RootScene::sceneCalc, GetLapRankChecker)
ENGINE_KEY = 0x75F1B26B         # System::EngineHolder::ENGINE_KEY

# Object::EEngineType
ENGINE = {"Character": 0, "Camera": 1, "Render": 2, "System": 3, "Sequence": 4,
          "Mii": 5, "Sound": 6, "Network": 7, "Effect": 8}

# Sequence::SequenceResource::SectionBlock::m_section_type
SECTION_TYPES = {0: "page", 1: "task", 2: "data", 3: "serial", 4: "crossfade", 5: "parallel",
                 6: "delegate", 7: "proxy", 8: "root"}
# Sequence::Section::EState (scene-sequence-bseq Finding 5)
SECTION_STATES = {1: "free", 2: "ready", 3: "entering", 4: "standby", 5: "running", 6: "completed",
                  7: "finishing", 8: "exited"}
# System::SceneID as used by Scene::m_scene_id (template/System/SceneID.hpp)


class Game:
    """Readers and writers of game structures, through `mem` (live: the game may run)."""

    def __init__(self, mem: MemoryIO):
        self.mem = mem
        self._str_cache: dict[int, str] = {}
        self._section_cache: dict[tuple, dict] = {}

    # ---- helpers ------------------------------------------------------
    @staticmethod
    def is_ptr(addr: int) -> bool:
        """In the process image, the heap or the linear heap (old and new
        3DS); reads elsewhere give zeros through RPC."""
        return (0x00100000 <= addr < 0x04000000 or 0x08000000 <= addr < 0x10000000
                or 0x14000000 <= addr < 0x1C000000 or 0x30000000 <= addr < 0x40000000)

    def cstr(self, addr: int, limit=128) -> str:
        if addr in self._str_cache:
            return self._str_cache[addr]
        raw = self.mem.read(addr, limit).split(b"\0")[0].decode("latin-1")
        self._str_cache[addr] = raw
        return raw

    def vec3(self, addr):
        return struct.unpack("<3f", self.mem.read(addr, 12))

    def buffer(self, addr):
        """sead::Buffer<T>: (count, data pointer)."""
        return self.mem.s32(addr), self.mem.u32(addr + 4)

    def ptr_array(self, addr):
        """sead::PtrArray<T>: list of pointers."""
        num, ptrs = self.mem.s32(addr), self.mem.u32(addr + 8)
        if num <= 0 or not ptrs:
            return []
        return list(struct.unpack("<%dI" % num, self.mem.read(ptrs, 4 * num)))

    # ---- engines ------------------------------------------------------
    def _engine(self, holder_owner: int, kind: str) -> int:
        info = holder_owner + 0x1E0 + 4 + 0xC * ENGINE[kind]   # EngineHolder::EngineManager::SEngineInfo
        if not self.mem.u8(info + 4):
            return 0
        return self.mem.u32(info) ^ ENGINE_KEY

    def root_scene(self) -> int:
        return self.mem.u32(ROOT_SYSTEM + 0x10)            # RootSystem::m_root_scene

    def game_scene(self) -> int:
        manager = self.mem.u32(ROOT_SYSTEM + 0x4)          # RootSystem::m_scene_manager
        return self.mem.u32(manager + 0x4) if manager else 0   # SceneManager::m_game_scene

    def root_engine(self, kind: str) -> int:
        return self._engine(self.root_scene(), kind)

    def scene_engine(self, kind: str) -> int:
        scene = self.game_scene()
        return self._engine(scene, kind) if scene else 0

    def scene_id(self) -> int | None:
        scene = self.game_scene()
        return self.mem.u8(scene + 0x1D8) if scene else None   # System::Scene::m_scene_id

    def sequence_engine(self) -> int:
        return self.root_engine("Sequence")

    # ---- sequence (scene-sequence-bseq) -------------------------------
    def _code_table(self, block: int, which: str):
        off = self.mem.u16(block + (0xA if which == "enter" else 0xC))
        return block + off

    def code_names(self, section: int, which: str) -> dict[int, str]:
        res, block = self.mem.u32(section + 0x8), self.mem.u32(section + 0x10)
        strings = self.mem.u32(res + 0x8)
        table = self._code_table(block, which)
        count = self.mem.u16(table)
        raw = self.mem.read(table + 4, 4 * count) if count else b""
        out = {}
        for i in range(count):
            cid, name = struct.unpack_from("<HH", raw, 4 * i)
            out[cid] = self.cstr(strings + name)
        return out

    def section(self, addr: int, is_root=False) -> dict:
        """Name, class and state of a Sequence::Section.

        The root of a file is always a ParallelSequence, whatever the type
        byte of its block says (7 in the .bss files, 8 in Root-Default.brs).
        What comes from the resource (name, class, code tables) is cached per
        section object and block header, so a walk mostly reads the state and
        the two codes.
        """
        raw = self.mem.read(addr, 0x24)
        res, block = struct.unpack_from("<I4xI", raw, 0x8)
        state = SECTION_STATES.get(raw[0x14], raw[0x14])
        info = {"addr": addr, "name": "?", "class": "", "type": "?", "state": state}
        if not res or not block:
            return info
        head = self.mem.read(block, 0x14)
        key = (addr, res, block, head, is_root)     # the header too: a later file may load at the same address
        static = self._section_cache.get(key)
        if static is None:
            self._str_cache.clear()
            strings = self.mem.u32(res + 0x8)
            stype = head[0]
            static = {"type": "parallel" if is_root else SECTION_TYPES.get(stype, stype), "root": is_root,
                      "name": self.cstr(strings + struct.unpack_from("<H", head, 0x8)[0]), "class": "",
                      "enter_names": self.code_names(addr, "enter"), "return_names": self.code_names(addr, "return")}
            if stype < 3:
                practical = block + struct.unpack_from("<H", head, 0x10)[0]
                static["class"] = self.cstr(strings + self.mem.u16(practical + 0x2))
            self._section_cache[key] = static
        enter, ret = struct.unpack_from("<HH", raw, 0x1E)
        info.update({k: v for k, v in static.items() if not k.endswith("_names")})
        info["enter"] = static["enter_names"].get(enter, f"#{enter}")
        info["return"] = static["return_names"].get(ret, f"#{ret}")
        return info

    def children(self, addr: int, info: dict) -> list[int]:
        """Sections currently attached below a sequence section."""
        t = info["type"]
        if t in ("parallel", "delegate"):
            num, layers = self.mem.u32(addr + 0x34), self.mem.u32(addr + 0x3C)   # LayeredSequence
            out = []
            for i in range(min(num, 32)):
                layer = self.mem.u32(layers + 4 * i)
                child = self.mem.u32(layer) if layer else 0             # SequenceLayer::m_section
                if child:
                    out.append(child)
            return out
        if t == "serial":
            child = self.mem.u32(addr + 0x34)                          # SerialSequence::m_next_section
            return [child] if child else []
        if t == "proxy":
            scene_seq = self.mem.u32(addr + 0x40)                      # SceneSequenceProxy::m_scene_sequence
            root = self.mem.u32(scene_seq + 0x18) if scene_seq else 0  # SceneSequence::m_section
            return [root] if root else []
        return []

    def sequence_tree(self, only_active=True) -> list[tuple[int, dict]]:
        brs = self.mem.u32(self.sequence_engine() + 0x8)              # SequenceEngine::m_brs_scene_sequence
        root = self.mem.u32(brs + 0x18)
        out = []

        def walk(addr, depth, seen, is_root=False):
            if not addr or addr in seen or depth > 16:
                return
            seen.add(addr)
            info = self.section(addr, is_root)
            if only_active and info["state"] in ("free",):
                return
            out.append((depth, info))
            for child in self.children(addr, info):
                walk(child, depth + 1, seen, info["type"] == "proxy")

        walk(root, 0, set(), True)
        return out

    def active_pages(self) -> list[dict]:
        """SequenceEngine::m_active_pages (sead::FixedPtrArray<Page, 5> at +0x88)."""
        return [self.section(p) for p in self.ptr_array(self.sequence_engine() + 0x88)]

    def running_sections(self) -> list[dict]:
        return [info for _, info in self.sequence_tree() if info["type"] in ("page", "task")
                and info["state"] == "running"]


class Session:
    """The running game, with the hooks installed.

    Memory goes through Azahar's RPC server (`mem`) and the game keeps
    running. `freeze` parks the game thread at the start of the next frame,
    and `step(n)` runs exactly n frames and parks it again, so state read
    between steps belongs to a frame boundary. `gdb()` connects the gdb stub
    for breakpoints, watchpoints and single steps. `close` lets the game run
    freely.
    """

    def __init__(self, host="127.0.0.1", port=4000, rpc_port=RPC_PORT):
        self.gdb_address = (host, port)
        self.mem = RpcClient(host, rpc_port, TITLE_ID)
        self.game = Game(self.mem)
        self.hooks = Hooks(self.mem)
        self.hooks.install()

    @property
    def frame(self) -> int:
        return self.hooks.frame()

    def freeze(self) -> int:
        return self.hooks.freeze()

    def step(self, frames=1) -> int:
        if not self.hooks.state()["frozen"]:
            self.hooks.freeze()
            frames -= 1
        return self.hooks.step(frames) if frames > 0 else self.frame

    def press(self, buttons=PAD_A, hold=4) -> int:
        """Hold pad buttons (hooks.PAD_*) for `hold` frames through the pad
        hook, then release them, frozen at the frame after. For the screens
        that read the pad instead of page buttons (UI::tstDemoButton and the
        like); menu pages are driven through their buttons (menu.py)."""
        self.hooks.set_pad(buttons)
        try:
            self.step(hold)
        finally:
            self.hooks.set_pad(0)
        return self.step(1)

    def wait_until(self, predicate, max_frames=600, every=5) -> bool:
        """Step `every` frames at a time until predicate(session) is true."""
        done = 0
        while not predicate(self):
            if done >= max_frames:
                return False
            self.step(every)
            done += every
        return True

    def run_until(self, predicate, timeout=120.0, interval=0.1, freeze=True) -> bool:
        """Let the game run freely and check predicate(session) while it runs
        (faster than stepping, but not frame exact). Freezes the game at the
        next frame once it is true, unless freeze=False."""
        if predicate(self):
            return True
        self.hooks.unfreeze()
        ok = self.hooks.poll(lambda h: predicate(self), timeout, interval)
        if freeze:
            self.freeze()
        return ok

    @contextmanager
    def gdb(self):
        """`with s.gdb() as g:` a GdbClient (gdbrsp.py) for breakpoints,
        watchpoints and single steps. Connecting halts the emulated CPU, which
        stops frame stepping and calls until the block ends; RPC reads,
        writes and screenshots keep working. Leaving the block removes the
        breakpoints set through it and lets the CPU run again. Only one gdb
        client can be connected."""
        for attempt in range(20):       # the stub resets connections for a while after Azahar starts
            try:
                g = GdbClient(*self.gdb_address)
                g.handshake()
                break
            except (OSError, TimeoutError):
                if attempt == 19:
                    raise
                time.sleep(0.5)
        try:
            yield g
        finally:
            g.detach()

    def section_state(self, name: str):
        for _, info in self.game.sequence_tree():
            if info["name"] == name:
                return info["state"]
        return None

    def find_section(self, name: str, state="running") -> dict | None:
        for _, info in self.game.sequence_tree():
            if info["name"] == name and (state is None or info["state"] == state):
                return info
        return None

    def wait_section(self, name: str, state="running", timeout=120.0) -> bool:
        """Run until the section with this name is in `state`, then freeze."""
        return self.run_until(lambda s: s.section_state(name) == state, timeout)

    def call(self, func: int, *args: int) -> int:
        """Call a game function on the game thread at a frame boundary."""
        return self.hooks.call(func, *args)

    def close(self, unfreeze=True):
        """Let the game run freely and close the RPC socket. With
        unfreeze=False the game thread stays parked in the frame hook, for
        the next session to pick up."""
        try:
            if unfreeze:
                self.hooks.unfreeze()
        finally:
            self.mem.close()
