"""Menus of Mario Kart 7 (eur2) in the running game: the buttons of the pages
and the input path that presses them (scene-sequence-bseq Finding 13).

`Menu(session)` reads the pages' manipulators and buttons and presses
buttons through their handlers, as the game's own input does, with no pad
input. A page records the choice exactly as with real input.
"""
import struct

from .courses import battle_button, cup_and_course
from .game import Session
from .hooks import PAD_DOWN, PAD_L, PAD_LEFT, PAD_R, PAD_RIGHT, PAD_UP

BASE_PAGE_COMPLETE_NEXT = 0x004D2ECC   # Sequence::BasePage::completeNext(page, code)
# Page buttons and the input path that presses them (scene-sequence-bseq Finding 13):
SEQ_IS_FADE = 0x004D0F4C               # Sequence::IsFade()
SEQ_IS_TIME_UP = 0x004D6408            # Sequence::IsTimeUp()
BUTTON_CAN_MANIPULATE = 0x00170EB8     # UI::BaseMenuButtonControl::canManipulate()
MANIPULATOR_SET_CURSOR = 0x0014C314    # UI::Manipulator::setCursor(int)
CLASS_INFO_CONVERT_RETURN_CODE = 5     # vtable slot of ExecutableSectionClassInfo<T>::convertReturnCode(int)
# invoke() of sead::Delegate2<UI::BaseMenuButtonControl, int, UI::EKeyID / const sead::Vector2f & / int>: the
# handler delegates of a manipulator item that call a UI::BaseMenuButtonControl
BUTTON_DELEGATE_INVOKES = (0x005CE7DC, 0x005CE834, 0x005CE88C)
# UI::BaseMenuButtonControl::ECompleteNextMode, the negative return codes of a button
BUTTON_MODES = {-1: "none", -2: "open menu", -3: "close menu", -4: "mode -4"}
# RaceSys::EDriverID, EBodyID, ETireID, EWingID (template/RaceSys)
DRIVERS = ["Bowser", "Daisy", "DonkeyKong", "HoneyQueen", "KoopaTroopa", "Lakitu", "Luigi", "Mario", "MetalMario",
           "MiiMale", "MiiFemale", "Peach", "Rosalina", "ShyGuy", "Toad", "Wario", "Wiggler", "Yoshi"]
BODIES = ["Standard", "BoltBuggy", "BirthdayGirl", "Egg1", "BDasher", "Zucchini", "KoopaClown", "TinyTug", "BumbleV",
          "CactX", "Bruiser", "PipeFrame", "BarrelTrain", "Cloud9", "BlueSeven", "SodaJet", "GoldStandard"]
TIRES = ["Standard", "Monster", "Roller", "Slick", "Slim", "Sponge", "GoldTires", "Wood", "RedMonster", "Mushroom"]
WINGS = ["SuperGlider", "Paraglider", "PeachParasol", "FlowerGlider", "Swooper", "BeastGlider", "GoldGlider"]
CHARA_PAGE_DRIVERS = 0x2B0      # MenuSingle_Chara: EDriverID per cursor slot (17; 0x13 = locked), set by sub_00498610
KART_PAGE_REELS = {"body": (0x2A8, BODIES), "tire": (0x2A4, TIRES), "wing": (0x2AC, WINGS)}   # MenuSingle_Kart: UI::SlotSelect
SLOT_CURRENT, SLOT_FIRST, SLOT_LAST, SLOT_ENTRIES = 0x7C, 0x80, 0x84, 0x41C   # UI::SlotSelect (selectBody): entries 0x1C, id +0x14
# The rule settings page (Sequence::MenuSingle_Setting, Page_SingleSetting): UI::LRSelect controls in a
# sead::PtrArray (+0x298 count, +0x2A0 data); initControl builds 4 for battle (+0x295 set), 5 for VS. Each
# LRSelect has its value at +0x7C (BaseMenuInputControl::m_option, from +0x80 to +0x84) and its
# ESettingType at +0x40C; LRSelect::apply writes the value where the type says. Measured on the battle page
# (2026-10-04) and the VS page (`start --vs`, vs.py; class and cpu-on, 2026-10-05), names as the page shows them:
SETTING_SELECTS = 0x298         # MenuSingle_Setting: count, capacity +0x29C, data +0x2A0
SETTING_OPTION, SETTING_MIN, SETTING_MAX, SETTING_TYPE = 0x7C, 0x80, 0x84, 0x40C   # UI::LRSelect
SETTINGS = {     # UI::LRSelect::ESettingType -> (name, value names from the minimum on; None: not measured)
    0: ("class", ("50cc", "100cc", "150cc")),                          # SELECT_ENGINE_CLASS: setCC / setMirror
    1: ("cpu-on", ("off", "on")),                                      # SELECT_ENABLE_CPU: MenuData+0x668 = 0 / 2
    2: ("cpu", ("easy", "normal", "hard")),                            # SELECT_CPU_LEVEL: MenuData+0x668 = 1..3
    3: ("stage", ("choose", "random", "in-order")),                    # SELECT_COURSE_ORDER: MenuData+0x669
    4: ("items", ("all", "shells", "bananas", "mushrooms", "bob-ombs")),   # SELECT_ITEM_PATTERN: setItemPattern
    5: ("teams", ("off", "on")),                                       # SELECT_ENABLE_TEAMS: setTeamMode
}
TEAMS = ("red", "blue")         # RaceSys::ETeamType; CKartInfo::m_team_type (+0x18) in the menu's race info
CRACEINFO_DETAIL_KART = 0x184   # RaceSys::CRaceInfo::m_detail_kart_id: the local player


def _enum(value, names, what) -> int:
    if isinstance(value, int):
        return value
    if value not in names:
        raise ValueError(f"unknown {what} {value!r}; one of {', '.join(names)}")
    return names.index(value)


# System::Flag::IsOpen* answer from the save's unlock bits; `unlock_all` makes every test pass, for this run
# only (the save is not changed). (address, original, patched):
NOP = 0xE320F000
UNLOCK_PATCHES = (
    (0x00452B10, 0x0A000000, NOP),          # IsOpen(RaceSys::EGrandPrixID): `beq` past `mov r0, #1` (cups)
    (0x00452C80, 0x13A00001, 0xE3A00001),   # IsOpen(System::ESequenceOpenFlag): `movne r0, #1` -> `mov`
    (0x00453A58, 0x0A000000, NOP),          # IsOpen_(RaceSys::EBodyID, u16)
    (0x00453A98, 0x0A000000, NOP),          # IsOpen_(RaceSys::ETireID, u16)
    (0x00453AD8, 0x0A000000, NOP),          # IsOpen_(RaceSys::EWingID, u16)
    (0x00453B18, 0x0A000000, NOP),          # IsOpen_(RaceSys::EDriverID, u16)
    # the save-based tests that the menus use (sub_004d1b08 for the character page, ...): a bit per entry in the
    # save's unlock masks; `ands r0, r1, r0, lsl ip` -> `mov r0, #1`
    (0x00452B60, 0xE0110C10, 0xE3A00001),   # sub_00452b20: body open (save +0x4E90+0x78)
    (0x00452BB0, 0xE0110C10, 0xE3A00001),   # sub_00452b70: tire open (+0x7C)
    (0x00452C00, 0xE0110C10, 0xE3A00001),   # sub_00452bc0: glider open (+0x80)
    (0x00452C50, 0xE0110C10, 0xE3A00001),   # sub_00452c10: driver open (+0x72)
)


def write_patches(g, patches, on=True):
    """Write code patches (address, original, patched), or restore the
    original code (on=False), through `g` (a GdbClient or an RpcClient)."""
    for addr, orig, patched in patches:
        if g.u32(addr) not in (orig, patched):
            raise RuntimeError(f"unexpected code at {addr:#x}; not the eur2 build?")
    for addr, orig, patched in patches:
        g.w32(addr, patched if on else orig)


def write_unlock(g, on=True):
    """Write the unlock patches (or restore the code, on=False) through `g`
    (a GdbClient or an RpcClient). `mk7 emu start --unlock` calls it at the
    game's first instruction, through the stub, before anything has run."""
    write_patches(g, UNLOCK_PATCHES, on)


# The player as a CPU: RaceSys::EPlayerType CPU (1) instead of Master (0) for the local player makes
# Kart::Unit build its kart as a CPU's (VehicleBase +0x99..+0x9B set: AI path and pad control), and the
# AIManager drives it like the other CPUs (AIRankManager::registerAI puts it in the CPU list). The single-player
# menus only ever give the player Master: the character page (MenuSingle_Chara::buttonHandler_OK ->
# setDriver(player, driver, Master)) and the race page when it is left (BaseRacePage::complete ->
# BasePage::setPlayerType(player, Master) for the next race, retry, change course or character; Master_Replay
# for a replay). These patches make both give CPU. (address, original, patched):
CPU_PLAYER_PATCHES = (
    (0x0049910C, 0xE3A01000, 0xE3A01001),   # MenuSingle_Chara::buttonHandler_OK: `mov r1, #0` -> `#1` (CPU)
    # BasePage::setPlayerType keeps the type on the stack; keep it in r3 instead and store CPU for Master:
    (0x004D32C4, 0xE24DD004, NOP),          # sub sp, sp, #4
    (0x004D32F4, 0xE58D1000, 0xE1A03001),   # str r1, [sp]  -> mov r3, r1
    (0x004D3308, 0xE59D0000, 0xE3530000),   # ldr r0, [sp]  -> cmp r3, #0  (Master)
    (0x004D330C, 0xE5820014, 0x03A03001),   # str r0, [r2, #0x14] -> moveq r3, #1 (CPU)
    (0x004D3310, 0xE28DD004, 0xE5823014),   # add sp, sp, #4 -> str r3, [r2, #0x14]
)
PLAYER_TYPE_MASTER, PLAYER_TYPE_CPU = 0, 1   # RaceSys::EPlayerType


class Menu:
    """Page buttons and menu navigation of a Session."""

    def __init__(self, session: Session):
        self.s = session
        self.mem = session.mem
        self.game = session.game
        self._class_names: dict[int, str] = {}
        self._code_names: dict[tuple, str] = {}

    def menu_data(self) -> int:
        return self.mem.u32(self.game.sequence_engine() + 0xC0)    # DashSequenceEngine::m_menu_data


    def manipulator_manager(self) -> int:
        return self.game.sequence_engine() + 0x40          # see Sequence::GetManipulatorManager

    def active_manipulator(self) -> int:
        """The manipulator that gets the input: the last one of
        ManipulatorManager::m_manipulator_array (ManipulatorManager::calc)."""
        mm = self.manipulator_manager()
        num, ptrs = self.mem.s32(mm + 0x8), self.mem.u32(mm + 0x10)
        return self.mem.u32(ptrs + 4 * (num - 1)) if num > 0 else 0

    def page_manipulators(self, page: int) -> list[int]:
        """BasePage::m_manipulator and BasePage::m_manipulators. Pages that
        are not a BasePage have none: only manipulators whose m_page is the
        page are kept."""
        out = [self.mem.u32(page + 0x64)]
        num, arr = self.mem.u32(page + 0x84), self.mem.u32(page + 0x88)
        if 0 < num <= 8 and self.game.is_ptr(arr):
            out += struct.unpack("<%dI" % num, self.mem.read(arr, 4 * num))
        return [m for m in dict.fromkeys(out) if self.game.is_ptr(m) and self.mem.u32(m + 0xD4) == page]

    def manipulator_items(self, manipulator: int) -> list[dict]:
        """Key, touch and cursor items of a UI::Manipulator, each with the
        control it belongs to and the handler delegates the manipulator calls."""
        out = []
        for kind, off in (("key", 0x8), ("touch", 0x2C), ("cursor", 0x80)):
            for item in self.game.ptr_array(manipulator + off):
                raw = self.mem.read(item, 0x30)
                w = struct.unpack("<12I", raw)
                if kind == "key":           # UI::KeyItem: delegates +0x10 (trigger) and +0x14
                    deleg = w[4] or w[5]
                    out.append({"kind": kind, "addr": item, "manipulator": manipulator, "handler": deleg,
                                "args": (w[1], w[3]), "key": w[3], "latched": bool(raw[0]),
                                "control": self.mem.u32(deleg + 4) if deleg else 0})
                elif kind == "touch":       # UI::TouchItem: m_button +0x10, handlers[TOUCH_HANDLER_UP] +0x18
                    out.append({"kind": kind, "addr": item, "manipulator": manipulator, "control": w[4],
                                "handler": 0, "touch_handler": w[6]})
                else:                       # UI::CursorItem: handlers[EVENT_KEY_HANDLER_CURSOR_A] at +0x28
                    out.append({"kind": kind, "addr": item, "manipulator": manipulator, "control": w[3],
                                "cursor": w[2], "enabled": bool(raw[0x14]), "handler": w[10],
                                "args": (w[0], w[4])})
        return out

    def button_state(self, control: int) -> dict:
        """UI::BaseMenuButtonControl fields that decide what a press does."""
        sel, hi = struct.unpack("<ii", self.mem.read(control + 0x210, 8))
        page, ret, mode = struct.unpack("<Iii", self.mem.read(control + 0x22C, 12))
        return {"page": page, "return_code": ret, "complete_mode": mode, "option": sel, "highlight": hi,
                "handlers": self.mem.u32(control + 0x7C)}

    def button_code(self, control: int) -> int:
        """The code a press uses (UI::BaseMenuButtonControl::completeNext):
        m_on_complete_next_mode while the page's menu is open and it is set,
        m_return_code otherwise. -1: the button does nothing."""
        st = self.button_state(control)
        if self.mem.u8(st["page"] + 0x8F) == 3 and st["complete_mode"] != -1:
            return st["complete_mode"]
        return st["return_code"]

    def can_manipulate(self, control: int) -> bool:
        """UI::BaseMenuButtonControl::canManipulate, read from memory: the
        button has a return code and its first two animations are neither
        in state 0 nor 5."""
        if self.button_code(control) == -1:
            return False
        anim = self.mem.u32(control + 0x64)
        num, arr = self.mem.u32(anim + 0x4), self.mem.u32(anim + 0x8)
        first, second = struct.unpack("<II", self.mem.read(arr, 8))
        states = [self.mem.s32(first + 0x14), self.mem.s32((second if num > 1 else first) + 0x14)]
        return all(s not in (0, 5) for s in states)

    def input_blocked(self, manipulator: int) -> str | None:
        """Why the game would not pass input to this manipulator this frame
        (ManipulatorManager::calc and Manipulator::manipulate), or None. The
        fade and time-up tests are game functions; press_blocked adds them."""
        if self.active_manipulator() != manipulator:
            return "another manipulator has the input"
        page = self.mem.u32(manipulator + 0xD4)                       # Manipulator::m_page
        menu = self.mem.s32(manipulator + 0xD8) >= 0                  # the manipulator of the page's menu
        if self.mem.u8(page + 0x8F) != (3 if menu else 0):            # BasePage::m_menu_state
            return "the page's menu is open" if not menu else "the page's menu is not open"
        if self.mem.read(page + 0x14, 2) != b"\x05\x05":              # Section::m_current_state, m_next_state
            return "the page is not running"
        dialog = self.mem.u32(self.menu_data() + 0x1C)                # MenuData::m_common_system_dialog
        if dialog and dialog != page:
            if self.mem.u32(dialog + 0x34C) == 1:                     # Common_SystemDialog::m_dialog_owner
                return "the system dialog has the input"
            if not self.mem.u8(self.manipulator_manager()):           # ManipulatorManager::m_0x0
                return "only the system dialog gets input (ManipulatorManager::m_0x0 is 0)"
        return None

    def system_dialog_has_input(self) -> bool:
        dialog = self.mem.u32(self.menu_data() + 0x1C)
        return bool(dialog) and self.mem.u32(dialog + 0x34C) == 1

    # ---- page buttons (scene-sequence-bseq Finding 13) ----------------------
    def class_name(self, obj: int) -> str:
        """Object::DTIClassInfo name of an Object::Actor (a UI control), asked
        from the game: virtual getDTIClassInfo (slot 0). The names have no
        namespace, and DTIClassInfo::m_parent is 0 for the controls, so it
        does not give the bases. Cached per vtable."""
        vt = self.mem.u32(obj)
        if vt not in self._class_names:
            info = self.s.call(self.mem.u32(vt), obj)
            name = self.game.cstr(self.mem.u32(info + 0x8)) if info else ""   # m_name: sead::SafeString
            self._class_names[vt] = name or f"vtable {vt:#x}"
        return self._class_names[vt]

    def return_code_name(self, page: int, code: int) -> str:
        """Name of a page's return code enum value, from the page class
        (ExecutableSectionClassInfo<T>::convertReturnCode); negative values
        are the button modes (ECompleteNextMode)."""
        if code < 0:
            return BUTTON_MODES.get(code, str(code))
        info = self.mem.u32(page + 0x44)                                      # PracticalSection::m_section_class_info
        key = (info, code)
        if key not in self._code_names:
            func = self.mem.u32(self.mem.u32(info) + 4 * CLASS_INFO_CONVERT_RETURN_CODE)
            name = self.s.call(func, info, code)
            self._code_names[key] = (self.game.cstr(name) if name else "") or f"#{code}"
        return self._code_names[key]

    def _page_addr(self, page: str | int) -> int:
        if isinstance(page, int):
            return page
        info = self.s.find_section(page)
        if info is None:
            raise LookupError(f"no running section {page!r}")
        if info["type"] != "page":
            raise ValueError(f"{page} is a {info['type']}, not a page")
        return info["addr"]

    def buttons(self, page: str | int) -> list[dict]:
        """The controls that the page's manipulators know, as they are now.

        Each entry: `id` (its position in this list: cursor items in cursor
        order first), `control`, `class`, `items` (manipulator_items
        entries), `cursor` (cursor index or None), `button` (it is a
        UI::BaseMenuButtonControl: the item delegates are of that class), and
        for those: `code` (what a press uses),
        `return` (its name for this page), `return_code`, `complete_mode`,
        `option` (passed to the page's buttonHandler_OK) and `page`.
        """
        addr = self._page_addr(page)
        found: dict[int, dict] = {}
        for m in self.page_manipulators(addr):
            for item in self.manipulator_items(m):
                if item["control"]:
                    found.setdefault(item["control"], {"control": item["control"], "items": []})["items"].append(item)
        out = []
        for b in found.values():
            cursors = [it["cursor"] for it in b["items"] if it["kind"] == "cursor"]
            b["cursor"] = cursors[0] if cursors else None
            b["class"] = self.class_name(b["control"])
            delegates = [it["handler"] or it.get("touch_handler", 0) for it in b["items"]]
            b["button"] = any(self.mem.u32(self.mem.u32(d)) in BUTTON_DELEGATE_INVOKES for d in delegates if d)
            if b["button"]:
                b.update(self.button_state(b["control"]))
                b["code"] = self.button_code(b["control"])
                b["return"] = self.return_code_name(addr, b["code"])
            out.append(b)
        out.sort(key=lambda b: (b["cursor"] is None, b["cursor"] if b["cursor"] is not None else 0))
        for i, b in enumerate(out):
            b["id"] = i
        return out

    def find_button(self, page: str | int, which: int | str) -> dict:
        """A button of the page by id (int), or by the name or number of the
        code it returns ("Next01", "Back", "1") or by its class ("OKButton").
        A name must match one button, or one of those that the active
        manipulator holds."""
        buttons = self.buttons(page)
        if isinstance(which, int):
            if not 0 <= which < len(buttons):
                raise LookupError(f"no button {which}; the page has {len(buttons)}")
            return buttons[which]
        match = [b for b in buttons if b["button"] and which in (b["return"], str(b["code"]))] or \
                [b for b in buttons if b["class"] == which]
        if len(match) > 1:
            active = self.active_manipulator()
            match = [b for b in match if any(it["manipulator"] == active for it in b["items"])] or match
        if len(match) != 1:
            raise LookupError(f"{len(match)} buttons match {which!r}; use the id (`mk7 emu buttons`)")
        return match[0]

    def cursor_button(self, page: str | int, cursor: int | None = None) -> dict:
        """The button at a cursor index, by default the one under the cursor
        (Manipulator::m_current_cursor_item_idx of its manipulator)."""
        buttons = self.buttons(page)
        if cursor is None:
            item = next((it for b in buttons for it in b["items"] if it["kind"] == "cursor"), None)
            cursor = self.mem.s32(item["manipulator"] + 0x100) if item else -1
        for b in buttons:
            if b["cursor"] == cursor:
                return b
        raise LookupError(f"no button at cursor {cursor}")

    def _press_item(self, button: dict) -> dict | None:
        """The item through which the active manipulator would press the
        button: its cursor item (A on the cursor), else its key item."""
        active = self.active_manipulator()
        for kind in ("cursor", "key"):
            for item in button["items"]:
                if item["kind"] == kind and item["handler"] and item["manipulator"] == active:
                    return item
        return None

    def press_blocked(self, button: dict, calls=True) -> str | None:
        """Why a press of the button would be ignored at this frame boundary,
        or None. Mirrors the input path: ManipulatorManager::calc,
        Manipulator::manipulate, the item, and the button's canManipulate.
        calls=False skips the game function calls (usable while running)."""
        item = self._press_item(button)
        if item is None:
            if any(it["handler"] for it in button["items"]):
                return "another manipulator has the input"
            return "nothing to press: no handler for A on the cursor nor for a key"
        why = self.input_blocked(item["manipulator"])
        if why:
            return why
        if item["kind"] == "cursor" and not self.mem.u8(item["addr"] + 0x14):        # CursorItem::m_is_enabled
            return "the cursor item is disabled"
        if item["kind"] == "key" and not self.mem.u8(item["addr"]):
            return "the key item waits for the key to be released"
        if button["button"] and not self.can_manipulate(button["control"]):
            return "the button is not ready (canManipulate)"
        if calls:
            if self.s.call(SEQ_IS_FADE):
                return "a fade is running (Sequence::IsFade)"
            if not self.system_dialog_has_input() and self.s.call(SEQ_IS_TIME_UP):
                return "time is up (Sequence::IsTimeUp)"
            if button["button"] and not self.s.call(BUTTON_CAN_MANIPULATE, button["control"]):
                return "the button is not ready (canManipulate)"
        return None

    def wait_pressable(self, button: dict, timeout=60.0, max_frames=300) -> None:
        """Run until the button would take a press, then freeze there. Runs
        freely while the memory checks fail, then frame by frame."""
        if self.press_blocked(button, calls=False):
            if not self.s.run_until(lambda _: self.press_blocked(button, calls=False) is None, timeout):
                why = self.press_blocked(button, calls=False)
                raise TimeoutError(f"button {button['id']} of the page did not become pressable in {timeout} s: {why}")
        why = None
        for _ in range(max_frames):
            why = self.press_blocked(button)
            if why is None:
                return
            self.s.step(1)
        raise TimeoutError(f"button {button['id']} of the page never became pressable: {why}")

    def click(self, page: str | int, which: int | str | dict, select=True, timeout=60.0) -> dict:
        """Press a button of a page the way the manipulator does: wait until
        the input path would accept it, move the cursor onto it (select=True,
        as the D-Pad would, one frame before), then call the handler delegate
        that the manipulator calls for A on the cursor (CursorItem handler 2,
        `keyHandlerCursorA`) or for the button's key (KeyItem handler, e.g.
        `keyHandlerB` of a back button). The button's handler runs its
        completeNext: the page's buttonHandler_OK and BasePage::completeNext.
        `which` is as for find_button, or a button from `buttons`. Returns the
        button and the page's state one frame later."""
        addr = self._page_addr(page)
        button = which if isinstance(which, dict) else self.find_button(addr, which)
        self.wait_pressable(button, timeout)
        item = self._press_item(button)
        manipulator = item["manipulator"]
        if select and item["kind"] == "cursor" and self.mem.s32(manipulator + 0x100) != item["cursor"]:
            self.s.call(MANIPULATOR_SET_CURSOR, manipulator, item["cursor"])
            self.s.step(1)
            self.wait_pressable(button, timeout)
        deleg = item["handler"]
        self.s.call(self.mem.u32(self.mem.u32(deleg)), deleg, *item["args"])     # sead::Delegate2::invoke
        frame = self.s.step(1)
        state = self.game.section(addr)
        return {"button": button, "frame": frame, "page_state": state["state"], "page_return": state["return"],
                "menu_state": self.mem.u8(addr + 0x8F)}

    def complete(self, name: str, code: int | str):
        """Complete the running page `name` with a return code, as its buttons
        do (`Sequence::BasePage::completeNext`, scene-sequence-bseq Finding 13).
        `code` is the page's return code enum (0..7 = Next00..Next07, 8 = Back
        for menu pages) or one of those names."""
        info = self.s.find_section(name)
        if info is None:
            raise LookupError(f"no running section {name!r}")
        if info["type"] != "page":
            raise ValueError(f"{name} is a {info['type']}, not a page")
        if isinstance(code, str):
            code = 8 if code == "Back" else int(code.removeprefix("Next"))
        self.s.call(BASE_PAGE_COMPLETE_NEXT, info["addr"], code)

    def unlock_all(self, on=True):
        """Every cup, mode, character and kart part counts as unlocked while
        the game runs (off restores the code). The save data is not touched.

        The cup pages decide which cups are locked when the menu scene builds
        its pages, all in one frame, 19-25 frames after boot depending on the
        run (BasePage::onGenerateControl -> MenuSingle_CupBase::initControl ->
        IsOpen(EGrandPrixID)); patching later leaves them as they were. Call
        it before that: `mk7 emu start` leaves the game frozen at frame 1, and
        `mk7 emu start --unlock` patches before the game runs at all."""
        write_unlock(self.mem, on)

    def cpu_player(self, on=True):
        """The player as a CPU (CPU_PLAYER_PATCHES), from now until the game
        restarts or it is turned off: every later pass through the character
        page or out of a race page gives the player the CPU type. The menu's
        race info is changed at once too (Master <-> CPU), so turning it on
        after the character page still counts for the next race. The race
        already built keeps its karts."""
        write_patches(self.mem, CPU_PLAYER_PATCHES, on)
        ri = self.menu_data() + 0x74
        a = ri + 0x2C * self.mem.s16(ri + CRACEINFO_DETAIL_KART) + 0x14   # CKartInfo::m_player_type
        old, new = (PLAYER_TYPE_MASTER, PLAYER_TYPE_CPU) if on else (PLAYER_TYPE_CPU, PLAYER_TYPE_MASTER)
        if self.mem.u32(a) == old:
            self.mem.w32(a, new)

    def cpu_player_on(self) -> bool:
        return all(self.mem.u32(addr) == patched for addr, _, patched in CPU_PLAYER_PATCHES)

    def open_presents(self, page, button: dict, log=print, timeout=60.0):
        """Open the present boxes that keep the input from `button`: the
        character and kart pages first show what the save has just unlocked
        (a new character after a Grand Prix trophy, ...) as a PresentBox that
        has to be opened. Runs until the button would take a press, opening
        every present box that would take one on the way."""
        def present():
            return next((c for c in self.buttons(page) if c["class"] == "PresentBox"
                         and self.press_blocked(c, calls=False) is None), None)
        while True:
            self.s.run_until(lambda _: self.press_blocked(button, calls=False) is None or present(), timeout)
            box = present()
            if box is None:
                return
            self.click(page, box)
            log(f"{page}: opened a present box")

    def choose_character(self, driver, page="Page_SingleChara", log=print):
        """Press the button of a character on the character page: `driver` an
        EDriverID (int) or its name (DRIVERS: "Mario", "MetalMario", ...;
        "MiiMale"/"MiiFemale" is the Mii button). The page keeps which
        driver each cursor slot shows (CHARA_PAGE_DRIVERS); a locked slot
        says 0x13 (`unlock` opens them all)."""
        want = _enum(driver, DRIVERS, "driver")
        if not self.s.wait_section(page):
            raise TimeoutError(f"{page} did not start")
        addr = self._page_addr(page)
        slots = struct.unpack("<17i", self.mem.read(addr + CHARA_PAGE_DRIVERS, 17 * 4))
        if want in (9, 10) and want not in slots:
            want = 9 if 9 in slots else 10          # the Mii slot holds the Mii of the save, male or female
        if want not in slots:
            raise LookupError(f"{DRIVERS[want]} is not on the page (locked? slots: {slots})")
        return self._click(page, slots.index(want), log)

    def choose_kart(self, body=None, tire=None, wing=None, page="Page_SingleKart", ok=True, log=print):
        """Turn the reels of the kart page to the parts given (EBodyID,
        ETireID, EWingID as int or name: BODIES, TIRES, WINGS; None leaves a
        reel as it is), as a player does: the cursor onto the reel, then Up
        or Down on the pad, one entry per press, the shorter way round.
        Then press OK unless ok=False."""
        if not self.s.wait_section(page):
            raise TimeoutError(f"{page} did not start")
        addr = self._page_addr(page)
        buttons = self.buttons(addr)
        for kind, value in (("body", body), ("tire", tire), ("wing", wing)):
            if value is None:
                continue
            off, names = KART_PAGE_REELS[kind]
            want = _enum(value, names, kind)
            reel = self.mem.u32(addr + off)
            first, last = self.mem.s32(reel + SLOT_FIRST), self.mem.s32(reel + SLOT_LAST)
            ids = [self.mem.s32(reel + SLOT_ENTRIES + 0x1C * i + 0x14) for i in range(first, last + 1)]
            if want not in ids:
                raise LookupError(f"{names[want]} is not on the {kind} reel (locked?)")
            button = next(b for b in buttons if b["control"] == reel)
            self.wait_pressable_cursor(button)
            target = first + ids.index(want)
            for _ in range(2 * len(ids)):
                cur = self.mem.s32(reel + SLOT_CURRENT)
                if cur == target:
                    break
                down = (cur - target) % len(ids)       # Down goes to the previous entry
                self.s.press(PAD_DOWN if down <= len(ids) - down else PAD_UP, hold=2)
                self.s.step(20)
            else:
                raise RuntimeError(f"the {kind} reel did not reach {names[want]}")
            log(f"{page}: {kind} {names[want]}")
        if ok:
            self._click(page, "OKButton", log)

    def wait_pressable_cursor(self, button: dict, timeout=60.0):
        """Run until the page's manipulator takes input, then move the cursor
        onto `button` (a control with a cursor item, e.g. a kart reel)."""
        item = next(it for it in button["items"] if it["kind"] == "cursor")
        self.s.run_until(lambda _: self.input_blocked(item["manipulator"]) is None, timeout)
        if self.mem.s32(item["manipulator"] + 0x100) != item["cursor"]:
            self.s.call(MANIPULATOR_SET_CURSOR, item["manipulator"], item["cursor"])
            self.s.step(2)

    # ---- rule settings (Page_SingleSetting) ------------------------------------
    def settings(self, page="Page_SingleSetting") -> dict[str, dict]:
        """The rule settings of the settings page, by name (SETTINGS): the
        LRSelect `control`, its `type`, `value` (raw), `name` (of the value,
        None if not known), `min` and `max`."""
        addr = self._page_addr(page)
        num, arr = self.mem.u32(addr + SETTING_SELECTS), self.mem.u32(addr + SETTING_SELECTS + 8)
        out = {}
        for i in range(num):
            c = self.mem.u32(arr + 4 * i)
            kind = self.mem.u8(c + SETTING_TYPE)
            value, low, high = struct.unpack("<3i", self.mem.read(c + SETTING_OPTION, 12))
            name, values = SETTINGS.get(kind, (f"type{kind}", None))
            out[name] = {"index": i, "control": c, "type": kind, "value": value, "min": low, "max": high,
                         "name": values[value - low] if values and low <= value <= high else None}
        return out

    def set_setting(self, name: str, value, page="Page_SingleSetting", log=print):
        """Set a rule setting as a player does: the cursor onto its LRSelect,
        then Right or Left on the pad, one value per press, the shorter way
        round (the values wrap). Each press goes through
        LRSelect::keyHandlerCursor, apply and the page's inputHandler, so
        what depends on the value follows (teams turned on are shuffled,
        ...). `value` is a value name of SETTINGS or the raw number."""
        if not self.s.wait_section(page):
            raise TimeoutError(f"{page} did not start")
        cur = self.settings(page)
        if name not in cur:
            raise LookupError(f"{page} has no {name!r} setting; it has: {', '.join(cur)}")
        st = cur[name]
        values = SETTINGS.get(st["type"], (None, None))[1]
        if isinstance(value, str) and not value.lstrip("-").isdigit():
            if not values or value not in values:
                raise ValueError(f"unknown {name} value {value!r}; one of {', '.join(values or ())} or a number")
            want = st["min"] + values.index(value)
        else:
            want = int(value)
        if not st["min"] <= want <= st["max"]:
            raise ValueError(f"{name} goes from {st['min']} to {st['max']}, not {want}")
        button = next(b for b in self.buttons(page) if b["control"] == st["control"])
        self.wait_pressable_cursor(button)
        count = st["max"] - st["min"] + 1
        for _ in range(count):
            v = self.mem.s32(st["control"] + SETTING_OPTION)
            if v == want:
                break
            right = (want - v) % count
            self.s.press(PAD_RIGHT if right <= count - right else PAD_LEFT, hold=2)
            self.s.step(20)
        else:
            raise RuntimeError(f"{name} did not reach {value}")
        log(f"{page}: {name} {value}")

    def player_team(self) -> str | None:
        """The local player's team in the menu's race info (red, blue), None
        while teams are off (ETeamType 3)."""
        ri = self.menu_data() + 0x74
        team = self.mem.u32(ri + 0x2C * self.mem.s16(ri + CRACEINFO_DETAIL_KART) + 0x18)
        return TEAMS[team] if team < len(TEAMS) else None

    def choose_team(self, team: str, page="Page_SingleSetting", log=print):
        """With teams on, put the player on team `team` ("red" or "blue") as
        a player does: L for red, R for blue (MenuSingle_Setting::
        keyHandlerCore -> moveTeam). The page keeps the teams even: with
        CPUs it moves a random kart of that team to the other one. The
        teams are dealt at random when they are turned on."""
        if team not in TEAMS:
            raise ValueError(f"team is red or blue, not {team!r}")
        if self.settings(page).get("teams", {}).get("name") != "on":
            raise RuntimeError("teams are off (`teams on` first)")
        for _ in range(3):
            if self.player_team() == team:
                log(f"{page}: team {team}")
                return
            self.s.run_until(lambda _: self.input_blocked(self.page_manipulators(self._page_addr(page))[0]) is None)
            self.s.press(PAD_L if team == "red" else PAD_R, hold=2)
            self.s.step(20)
        raise RuntimeError(f"the player is still on team {self.player_team()}")

    def apply_settings(self, settings: dict | None, team: str | None, page="Page_SingleSetting", log=print):
        """Set several settings ({name: value}, teams last), then the team."""
        settings = dict(settings or {})
        for name in sorted(settings, key=lambda n: n == "teams"):
            self.set_setting(name, settings[name], page, log)
        if team is not None:
            self.choose_team(team, page, log)

    # ---- menu macros ----------------------------------------------------------
    def _click(self, page, which, log, timeout=240.0):
        if not self.s.wait_section(page, timeout=timeout):
            raise TimeoutError(f"{page} did not start")
        if which is None or isinstance(which, int):    # a cursor index; None: the cursor's button
            b = self.cursor_button(page, which)
        else:
            b = self.find_button(page, which)
        if b["button"] and b["code"] == -1:
            raise RuntimeError(f"{page}: button [{b['id']}] does nothing (a locked cup? `unlock` has to come "
                               "before the menu scene sets up its pages: right after `start`, while the game is "
                               "frozen at boot)")
        self.open_presents(page, b, log)
        r = self.click(page, b)
        log(f"{page}: [{b['id']}] {b['class']} ({b.get('return', '-')}) -> {r['page_state']}")
        return r

    def choose_driver_and_kart(self, character=None, kart=None, log=print):
        """The character page, then the kart page: `character` as for
        choose_character (None: the one under the cursor), `kart` a tuple
        (body, tire, wing) as for choose_kart (None: as they are)."""
        if character is None:
            self._click("Page_SingleChara", None, log)
        else:
            self.choose_character(character, log=log)
        if kart is None:
            self._click("Page_SingleKart", "OKButton", log)
        else:
            self.choose_kart(*kart, log=log)

    def time_trial(self, cup: int | str, course: int | None = None, character=None, kart=None, log=print):
        """From the title menu to a time trial on cup `cup` (0..7: the four new
        cups on the top row, then the four retro cups) and its course `course`
        (0..3), or on the race course whose .szs name `cup` is (course None;
        courses.py), alone, with the character and kart given (choose_driver_and_kart;
        by default those under the cursor). Every page is left through its
        buttons (`click`), so each page records its choice as with real
        input. Stops frozen on the race page, before the countdown ends."""
        cup, course = cup_and_course(cup, course)             # a wrong name fails before any page is left
        self._click("Page_Title", "Next00", log)              # Single Player
        self._click("Page_SingleMode", "Next01", log)         # Time Trials
        self.choose_driver_and_kart(character, kart, log)
        self.time_trial_course(cup, course, log)

    def time_trial_course(self, cup: int | str, course: int | None = None, log=print):
        """From the time trial cup page (also where Change Course and Change
        Character lead) to the race page of the course (buttons or .szs name,
        as for time_trial)."""
        cup, course = cup_and_course(cup, course)
        self._click("Page_SingleCup", cup, log)
        self._click("Page_SingleCourse", course, log)
        self._click("Page_SingleGhost", "OKButton", log)      # opens the "Start Time Trial" menu
        self._click("Page_SingleGhost", "RaceDialogButton", log)
        self._wait_race(log)

    def _wait_race(self, log):
        if not self.s.wait_section("Page_Race", timeout=300):
            raise TimeoutError("the race did not start")
        log("Page_Race running")

    def battle(self, kind: str, course: int | str | None, character=None, kart=None, settings=None, team=None,
               log=print):
        """From the title menu to a single-player battle: `kind` "balloon" or
        "coin", battle course `course` (0..5, the button on
        Page_SingleCourseBattle, or its .szs name; courses.py), with the character and kart given
        (choose_driver_and_kart), the rule settings given ({name: value}:
        cpu, stage, items, teams; see SETTINGS and `set_setting`; the others
        as the page has them; the page keeps them from the previous battle)
        and the player's team (`choose_team`). A `course` sets the stage
        setting to choose unless `settings` names a stage; with the stage at
        random or in order there is no course page. Returns once the last
        menu page finishes; the race scene comes next
        (`Race.wait_race_page`)."""
        modes = {"balloon": "Next02", "coin": "Next03"}
        if kind not in modes:
            raise ValueError(f"kind is balloon or coin, not {kind!r}")
        settings = dict(settings or {})
        if course is not None:
            course = battle_button(course)
            settings.setdefault("stage", "choose")
            if settings["stage"] != "choose":
                raise ValueError(f"a course is chosen only with the stage setting at choose, not {settings['stage']}")
        self._click("Page_Title", "Next00", log)              # Single Player
        self._click("Page_SingleMode", modes[kind], log)
        self.choose_driver_and_kart(character, kart, log)
        self.apply_settings(settings, team, log=log)
        stage = self.settings()["stage"]["name"]
        self._click("Page_SingleSetting", "OKButton", log)    # then the course list, or the start dialog
        if stage == "choose":
            if course is None:
                raise ValueError("the stage setting is choose: give a course")
            self.battle_course(course, log)
        else:
            self._click("Page_SingleSetting", "RaceDialogButton", log)

    def vs(self, course=None, character=None, kart=None, settings=None, team=None, log=print):
        """From the title menu to a single-player VS race, in a run started
        with `start --vs` (vs.py): the single-player mode page's VS button,
        the character and kart (choose_driver_and_kart), the rule settings
        ({name: value}: class, cpu-on, stage, items, teams; see SETTINGS and
        `set_setting`; the others as the page has them) and the player's team
        (`choose_team`), then the first course. CPUs are on unless
        `settings` says `cpu-on: off` (the player races alone). `course` is a race course's
        .szs name or (cup, course) buttons; it sets the stage (Courses)
        setting to choose unless `settings` names a stage. With the stage at
        in order it is the first course, the next ones follow in cup order;
        at random the game chooses every course and OK opens the start dialog
        instead of the cup page (MenuSingle_Setting::buttonHandler_OK tests
        the stage value against 1). Returns once the last menu page
        finishes; the race scene comes next (`Race.wait_race_page`)."""
        from .vs import vs_on
        if not vs_on(self.mem):
            raise RuntimeError("VS is not patched in: start the run with `mk7 emu start --vs`")
        settings = dict(settings or {})
        settings.setdefault("cpu-on", "on")     # the page starts at off after a boot (MenuData+0x668 0)
        if course is not None:
            course = cup_and_course(*course) if isinstance(course, tuple) else cup_and_course(course)
            settings.setdefault("stage", "choose")
            if settings["stage"] == "random":
                raise ValueError("no course is chosen with the stage setting at random")
        self._click("Page_Title", "Next00", log)              # Single Player
        self._click("Page_SingleMode", "Next01", log)         # VS (vs.py: the Time Trials button)
        self.choose_driver_and_kart(character, kart, log)
        self.apply_settings(settings, team, log=log)
        stage = self.settings()["stage"]["name"]
        self._click("Page_SingleSetting", "OKButton", log)    # then the cup page, or the start dialog (random)
        if stage == "random":
            self._click("Page_SingleSetting", "RaceDialogButton", log)
        else:
            if course is None:
                raise ValueError(f"the stage setting is {stage}: give the first course")
            self.vs_course(*course, log=log)

    def vs_course(self, cup: int | str, course: int | None = None, log=print):
        """From the cup page of a VS run (the first race, or Next Race with
        the stage at choose) into the race: cup and course buttons, or a
        race course's .szs name (as for time_trial). vs.py takes out the
        time trial's ghost page: the course button opens the start dialog,
        whose OK starts the race."""
        cup, course = cup_and_course(cup, course)
        self._click("Page_SingleCup", cup, log)
        self._click("Page_SingleCourse", course, log)               # opens the "Start" menu
        self._click("Page_SingleCourse", "RaceDialogButton", log)

    def battle_course(self, course: int | str, log=print):
        """From the battle course page (also where Change Course after a
        battle leads) into the battle (button 0..5 or .szs name)."""
        self._click("Page_SingleCourseBattle", battle_button(course), log)   # opens the "Start" menu
        self._click("Page_SingleCourseBattle", "RaceDialogButton", log)

    def _back_to_title(self, log, timeout=120.0):
        if not self.s.wait_section("Page_Title", timeout=timeout):
            raise TimeoutError("the title menu did not come back")
        log("Page_Title running")

    def open_channel(self, log=print, timeout=120.0):
        """From the title menu into the Mario Kart Channel (Seq_CH), frozen
        once its top page (Page_ChannelTop) takes input. Its first visit asks
        "SpotPass will be activated for this software."; with saving
        disabled (save.py) every run is a first visit. The dialog is answered
        Cancel (SystemDialogButtonB), which leaves SpotPass off."""
        self._click("Page_Title", "Next03", log)
        if not self.s.wait_section("Page_ChannelTop", timeout=timeout):
            raise TimeoutError("Page_ChannelTop did not start")
        back = self.find_button("Page_ChannelTop", "MchBtnB")
        while True:
            self.s.run_until(lambda _: self.system_dialog_has_input()
                             or self.press_blocked(back, calls=False) is None, timeout)
            if not self.system_dialog_has_input():
                return
            self._click("Page_CommonSystemDialog", "SystemDialogButtonB", log)

    def close_channel(self, log=print):
        """From the channel's top page back to the title menu (its Back)."""
        self._click("Page_ChannelTop", "MchBtnB", log)
        self._back_to_title(log)

    def open_multiplayer(self, log=print):
        """From the title menu to the local multiplayer group list
        (Page_MultiGroup), frozen once its Back button takes input."""
        self._click("Page_Title", "Next01", log)
        if not self.s.wait_section("Page_MultiGroup"):
            raise TimeoutError("Page_MultiGroup did not start")
        self.wait_pressable(self.find_button("Page_MultiGroup", "BackButtonB"))

    def close_multiplayer(self, log=print):
        """From the group list back to the title menu (its Back)."""
        self._click("Page_MultiGroup", "BackButtonB", log)
        self._back_to_title(log)

    def grand_prix(self, cup: int, engine: int = 0, character=None, kart=None, log=print):
        """From the title menu to the start of a Grand Prix: cup `cup` (0..7
        as for time_trial), engine class `engine` (0..3: 50cc, 100cc, 150cc,
        mirror), with the character and kart given (choose_driver_and_kart;
        by default those under the cursor). Returns once
        the last menu page finishes; the course intro (DemoScene) comes next,
        then the race (`Race.wait_race_page` skips the intro)."""
        self._click("Page_Title", "Next00", log)              # Single Player
        self._click("Page_SingleMode", "Next00", log)         # Grand Prix
        self._click("Page_SingleClass", engine, log)
        self.choose_driver_and_kart(character, kart, log)
        self._click("Page_SingleCupGP", cup, log)             # opens the "Start" menu
        self._click("Page_SingleCupGP", "RaceDialogButton", log)
