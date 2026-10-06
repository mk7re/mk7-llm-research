"""Races of Mario Kart 7 (eur2) in the running game: the race director and
timer, the lap and checkpoint state of the karts, their position, and the
course data (KMP) the race loaded.

`Race(session)` reads these live; they exist only while a race scene runs.
"""
import struct

from .game import Session
from .hooks import PAD_A, PAD_START

CRACEINFO_COURSE_ID = 0x160     # RaceSys::CRaceInfo::m_course_id
CRACEINFO_RACE_MODE = 0x164     # RaceSys::CRaceInfo::m_race_mode (CRaceMode: play mode, rule mode, type)
CRACEINFO_KART_NUM = 0x180      # RaceSys::CRaceInfo::m_kart_num
CRACEINFO_DETAIL_KART = 0x184   # RaceSys::CRaceInfo::m_detail_kart_id: the local player
MODE_MANAGER_RACE_ALL_GOAL_PROC = 0x004643C4   # RaceSys::ModeManagerRace::allGoalProc()
PLAY_MODES = ["SinglePlayer", "MultiPlayer", "Online", "Demo", "Replay"]           # RaceSys::ERacePlayMode
RULE_MODES = ["GrandPrix", "TimeTrials", "Versus", "Battle", "Award", "CoursePreview", "DemoGrandPrix",
              "DemoBattle"]                                                         # RaceSys::ERaceRuleMode
RACE_STATES = ["sync", "countdown", "race", "goal"]   # RaceSys::ModeManagerBase::RaceState
# vtables of the battle mode managers -> (kind, KartInfo field of the score that ranks the karts: points in a
# balloon battle, coins in a coin battle; BattleBalloonManager / BattleCoinManager::calcBeforeStateFunc)
BATTLE_MANAGERS = {0x00645034: ("balloon", 0x54), 0x00644E38: ("coin", 0x46)}
PAGE_MENU_STATE = 0x8F          # Sequence::BasePage::m_menu_state: 3 while the page's menu is open
# The player's ghost recording. SystemEngine + 0x3C is the KDPadDirector; its pad table (+0x30) holds the
# KDPlayerRecordPad at +0x8, and its race list (+0x3C, count +0x34) the pads that KDPadDirector::startRace and
# finishRace (a goal delegate of ModeManagerBase::stateInitGoal) start and finish. With the player as a CPU the list
# has the kart's KDAIPad instead, so the recording is never finished, and the time trial page waits for it in
# BaseRacePage::calcSave (state 6, KDPlayerRecordPad::getRecordedBuffer) before it shows the results.
KDPAD_DIRECTOR = 0x3C           # SystemEngine -> System::KDPadDirector
KDPAD_FINISH = 0x00457B0C       # System::KDPad::finish(): KDPadRecorder::makeRecData if the pad records
RECORDER_DONE = 0x2800          # KDPadRecorder: 1 once the recorded data is made (getRecordedBuffer)


class Race:
    """Race state of a Session."""

    def __init__(self, session: Session):
        self.s = session
        self.mem = session.mem
        self.game = session.game

    # ---- before and after the race --------------------------------------------
    def skip_demo(self, timeout=120.0):
        """Skip the course intro of a Grand Prix race (DemoScene, Page_Demo)
        as a player does: Sequence::DemoPage::onPagePreStep completes the
        page once it has run 700 frames or UI::tstDemoButton (A or Start) is
        pressed. Runs until the page runs, presses A, frozen after."""
        if not self.s.wait_section("Page_Demo", timeout=timeout):
            raise TimeoutError("the course intro (Page_Demo) did not start")
        self.s.press(PAD_A)

    def wait_race_page(self, skip_demo=True, timeout=300.0):
        """Run until the race page runs (before the countdown ends), then
        freeze. A Grand Prix race goes through the course intro first; with
        skip_demo it is skipped (skip_demo)."""
        def ready(s):
            names = {i["name"] for i in s.game.running_sections()}
            return "Page_Race" in names or (skip_demo and "Page_Demo" in names)
        while True:
            if not self.s.run_until(ready, timeout):
                raise TimeoutError("the race page did not start")
            if self.s.section_state("Page_Race") == "running":
                return
            self.skip_demo()

    def race_page(self) -> int:
        info = self.s.find_section("Page_Race")
        if info is None:
            raise LookupError("Page_Race is not running")
        return info["addr"]

    def menu_state(self) -> int:
        """Sequence::BasePage::m_menu_state of the race page: 0 closed, 3
        open (pause, replay or result menu), other values while it opens or
        closes."""
        return self.mem.u8(self.race_page() + PAGE_MENU_STATE)

    def pause(self, tries=60):
        """Open the race page's menu during a race (Start: the pause menu) or
        a replay (A: the replay menu), frozen once it is open. The page only
        takes the press while the race runs (state race) and its menu is
        fully closed (state 0)."""
        button = PAD_A if self.race_mode()["play"] == "Replay" else PAD_START
        for _ in range(tries):
            st = self.menu_state()
            if st == 3:
                return
            if st == 0 and self.race_state()["state"] == "race":
                self.s.press(button)
            self.s.step(10)
        raise TimeoutError(f"the race page's menu did not open (menu state {self.menu_state()}, "
                           f"race state {self.race_state()['state']})")

    def wait_goal(self, timeout=None) -> bool:
        """Run until the race reaches its goal state by itself (the player
        finished, or the battle clock ran out), then freeze. For the runs
        that are not finished at once: the research drives or moves the
        kart."""
        return self.s.run_until(lambda _: self.race_state()["state"] == "goal", timeout or 1e9)

    def results_menu(self, tries=60):
        """After the goal: press A through the result screens until the race
        page opens its menu (Next Race / Replay / Quit ...: `Menu.buttons
        ("Page_Race")`), frozen there. The result screens read the pad, not
        page buttons. A every 30 frames; the ones that come too early do
        nothing (about 20 presses after `finish` in a Grand Prix)."""
        page = self.race_page()
        self.finish_ghost_recording()
        for i in range(tries):
            if self.mem.u8(page + PAGE_MENU_STATE) == 3:
                return i
            self.s.press(PAD_A)
            self.s.step(25)
        raise TimeoutError(f"the race page's menu did not open after {tries} presses of A")

    def finish_ghost_recording(self) -> bool:
        """After the goal, finish the player's ghost recording if the game
        never will: with the player as a CPU its record pad is not in the pad
        director's race list (KDPAD_DIRECTOR above), and the time trial
        results would never open. Calls KDPad::finish on it as finishRace
        does for the pads in the list; the recording is empty (the pad was
        never started). Returns True if it did."""
        director = self.mem.u32(self.game.root_engine("System") + KDPAD_DIRECTOR)
        pad = self.mem.u32(self.mem.u32(director + 0x30) + 0x8)              # KDPlayerRecordPad
        recorder = self.mem.u32(self.mem.u32(pad + 0x10) + 0x8)             # KDPadRecorder
        count = self.mem.u32(director + 0x34)
        race_pads = struct.unpack(f"<{count}I", self.mem.read(self.mem.u32(director + 0x3C), 4 * count))
        if pad in race_pads or self.mem.u8(recorder + RECORDER_DONE):
            return False
        self.s.call(KDPAD_FINISH, pad)
        return True

    def wait_start(self, timeout=300.0) -> bool:
        """Run until the race timer runs (the countdown is over), then freeze."""
        return self.s.run_until(lambda _: self.race_timer()["started"], timeout)

    def course_id(self) -> int:
        """RaceSys::ECourseID of the race (template/RaceSys/ECourseID.hpp)."""
        return self.mem.u32(self.race_info() + CRACEINFO_COURSE_ID)

    def director_list(self) -> int:
        ce = self.game.scene_engine("Character")
        return self.mem.u32(ce + 0x1C) if ce else 0                    # CharacterEngine::m_director_list

    def race_director(self) -> int:
        dl = self.director_list()
        return self.mem.u32(dl + 0x1C) if dl else 0

    def race_info(self) -> int:
        rd = self.race_director()
        return rd + 0x2C if rd else 0                                # RaceDirector::m_race_info

    def race_timer(self) -> dict:
        """RaceDirector::m_race_timer (no template yet). Measured in a time
        trial: the race time is at +0x10 (u16 minutes, u16 seconds) and +0x14
        (u32 ms), and +0x24 is 1 during the countdown and 0 once it runs."""
        rd = self.race_director()
        rt = self.mem.u32(rd + 0x28) if rd else 0
        if not rt:
            return {"addr": 0, "started": False, "time": None}
        minutes, seconds, ms = struct.unpack("<HHI", self.mem.read(rt + 0x10, 8))
        return {"addr": rt, "started": self.mem.u32(rt + 0x24) == 0 and (minutes, seconds, ms) != (0, 0, 0),
                "time": (minutes, seconds, ms)}

    def race_mode(self) -> dict:
        """CRaceInfo::m_race_mode and the kart count of the race."""
        ri = self.race_info()
        play, rule, rtype = struct.unpack("<3I", self.mem.read(ri + CRACEINFO_RACE_MODE, 12))
        return {"play": PLAY_MODES[play] if play < len(PLAY_MODES) else play,
                "rule": RULE_MODES[rule] if rule < len(RULE_MODES) else rule, "type": rtype,
                "karts": self.mem.u32(ri + CRACEINFO_KART_NUM), "player": self.mem.s16(ri + CRACEINFO_DETAIL_KART)}

    def mode_manager(self) -> int:
        rd = self.race_director()
        return self.mem.u32(rd + 0x1BC) if rd else 0                   # RaceDirector::m_mode_manager

    def lap_rank_checker(self) -> int:
        mm = self.mode_manager()
        return self.mem.u32(mm + 0x504) if mm else 0                   # see RaceSys::GetLapRankChecker

    def race_state(self) -> dict:
        """ModeManagerBase: race state (its TStateObserver at +0x44), the
        ranks (m_rank_to_player_id is indexed by rank 1..8) and the goal
        order that ModeManagerRace keeps (+0x4E7 count, +0x4E8 player ids)."""
        mm = self.mode_manager()
        state = self.mem.u8(mm + 0x48)
        num = self.mem.u32(mm + 0x64 + CRACEINFO_KART_NUM)
        ranks = list(self.mem.read(mm + 0x1FD, 8))[:num]                 # m_player_id_to_rank
        goals = self.mem.u8(mm + 0x4E7)
        order = list(struct.unpack("<8H", self.mem.read(mm + 0x4E8, 16)))[:min(goals, 8)]
        return {"state": RACE_STATES[state] if state < 4 else state, "frames": self.mem.u32(mm + 0x5C),
                "ranks": ranks, "goal_order": order}

    def _finish_order(self, mode, order, place) -> list[int]:
        num = mode["karts"]
        if order is None:
            order = [p for p in range(num) if p != mode["player"]]
            order.insert((place or 1) - 1, mode["player"])
        order = list(order)
        if sorted(order) != list(range(num)):
            raise ValueError(f"order must list each of the {num} player ids once: {order}")
        return order

    def finish_battle(self, order=None, place=None):
        """End a battle at once, ranked by `order` (player ids, first place
        first; by default the local player at `place`, 1-based, default 1).
        Gives each kart a score in that order (the KartInfo field that
        BATTLE_MANAGERS names: points or coins, from the number of karts down
        to 1) and lets the battle clock run out on the next frame: the
        RaceTimer's CFrameDecWatch counts the frames left (+0x4), and
        ModeManagerBattle::calcRace ends the battle when the time is 0 and
        ranks the karts by score. Offline, after the countdown. Steps until
        the goal state (1 frame)."""
        mode = self.race_mode()
        mm = self.mode_manager()
        kind = BATTLE_MANAGERS.get(self.mem.u32(mm))
        if mode["rule"] != "Battle" or mode["play"] == "Online" or kind is None:
            raise RuntimeError(f"not an offline balloon or coin battle: {mode}")
        if self.race_state()["state"] != "race":
            raise RuntimeError(f"the race state is {self.race_state()['state']}, not race")
        order = self._finish_order(mode, order, place)
        infos = {self.mem.u16(ki + 0x44): ki for ki in self.game.ptr_array(mm + 0x4C4)}   # ModeManagerBase KartInfo
        for rank, pid in enumerate(order):
            self.mem.write(infos[pid] + kind[1], struct.pack("<H", len(order) - rank))
        rt = self.race_timer()["addr"]
        self.mem.w32(self.mem.u32(rt + 0x8) + 0x4, 1)                # RaceTimer::m_frame_watch: frames left
        for _ in range(5):                                            # the clock runs out in the next frame
            self.s.step(1)
            if self.race_state()["state"] == "goal":
                return
        raise RuntimeError(f"the battle did not end: race state {self.race_state()['state']}")

    def finish(self, order=None, place=None):
        """End a race at once: every kart that has not finished crosses the
        goal now, ranked by `order` (player ids, first place first; by default
        the local player at `place` (1-based, default 1), the others in id
        order around it), the way
        ModeManagerRace::calcRace ends a race once the local player finishes:
        `allGoalProc` finishes the karts in the order of m_player_id_to_rank
        (KartInfo::allGoal gives each an estimated time), then the race state
        goes to Goal in the same frame. Only for races (GP, VS, time trials,
        not battles), offline, after the countdown. Call it at a frame
        boundary (the game frozen); the race page then shows the results."""
        mm = self.mode_manager()
        mode = self.race_mode()
        if mode["rule"] not in ("GrandPrix", "TimeTrials", "Versus") or mode["play"] == "Online":
            raise RuntimeError(f"not an offline race: {mode}")
        st = self.race_state()
        if st["state"] != "race":
            raise RuntimeError(f"the race state is {st['state']}, not race")
        num = mode["karts"]
        order = self._finish_order(mode, order, place)
        p2r = [0] * 8
        for rank, pid in enumerate(order):
            p2r[pid] = rank + 1
        self.mem.write(mm + 0x1FD, bytes(p2r))                                 # m_player_id_to_rank
        self.mem.write(mm + 0x1F4, bytes([0] + order + [0] * (8 - num)))     # m_rank_to_player_id
        self.s.call(MODE_MANAGER_RACE_ALL_GOAL_PROC, mm)
        # what calcRace does right after allGoalProc once every kart is in: change the state to Goal. Without it
        # the next calcRace runs allGoalProc again and writes past the goal order array (+0x4E8, 8 entries)
        # into m_lap_rank_checker (+0x504).
        self.mem.write(mm + 0x48, bytes([3, self.mem.u8(mm + 0x48), 1]))   # current = Goal, previous, changed
        self.mem.w32(mm + 0x5C, 0)                                         # state counter

    def kart_info(self, player=0) -> dict:
        lrc = self.lap_rank_checker()
        count, data = self.game.buffer(lrc + 0x28)                        # LapRankChecker::m_kart_infos
        if not 0 <= player < count:
            raise IndexError(player)
        a = data + 0x44 * player
        raw = self.mem.read(a, 0x44)
        prev_cp, cur_cp, last_valid, key = struct.unpack_from("<BBhB", raw, 0xC)
        return {"addr": a, "previous_checkpoint": prev_cp, "current_checkpoint": cur_cp,
                "last_valid_checkpoint": last_valid, "key_checkpoint": key, "section": raw[0x11],
                "race_progress": struct.unpack_from("<f", raw, 0x14)[0],
                "lap": struct.unpack_from("<i", raw, 0x1C)[0],
                "flags": struct.unpack_from("<I", raw, 0x24)[0],
                "pos": struct.unpack_from("<3f", raw, 0x28)}

    def kart_units(self) -> list[int]:
        kd = self.mem.u32(self.director_list() + 0x10)                 # SDirectorList::m_kart_director
        count, data = self.game.buffer(kd + 0x28)                         # Kart::Director::m_units
        return list(struct.unpack("<%dI" % count, self.mem.read(data, 4 * count))) if count > 0 else []

    def vehicle(self, player=0) -> int:
        return self.mem.u32(self.kart_units()[player] + 0x2C)          # Kart::Unit::m_vehicle

    def kart(self, player=0) -> dict:
        v = self.vehicle(player)
        pos_ptr = self.mem.u32(v + 0x34)                               # Kart::Rigid::m_position
        return {"vehicle": v, "pos_addr": pos_ptr, "pos": self.game.vec3(pos_ptr),
                "velocity": self.game.vec3(v + 0x38),                     # Kart::Rigid::m_velocity
                "speed_vec": self.game.vec3(v + 0xC60),                   # VehicleMove::m_xyz_speed_vec
                "status": self.mem.u32(v + 0xC30)}                     # VehicleMove::m_status_flags

    def set_kart_pos(self, player, xyz, stop=True):
        k = self.kart(player)
        self.mem.write(k["pos_addr"], struct.pack("<3f", *xyz))
        if stop:
            self.mem.write(k["vehicle"] + 0x38, b"\0" * 12)
            self.mem.write(k["vehicle"] + 0xC60, b"\0" * 12)

    def _mapdata(self) -> int:
        fd = self.mem.u32(self.director_list() + 0x14)                 # SDirectorList::m_field_director
        return self.mem.u32(fd + 0x38)                                 # see Field::GetCheckPointAccessor

    def checkpoints(self) -> list[dict]:
        """MapdataCheckPoint entries as loaded (the KMP the race really uses)."""
        acc = self.mem.u32(self._mapdata() + 0x24)
        out = []
        for e in self.game.ptr_array(acc + 0xC):
            data = self.mem.u32(e)
            lx, lz, rx, rz, jugem, ctype, prev, nxt = struct.unpack("<4fbbbb", self.mem.read(data, 0x14))
            out.append({"index": self.mem.u8(e + 0xC), "key_id": self.mem.u8(e + 0xD), "left": (lx, lz),
                        "right": (rx, rz), "jugem": jugem, "type": ctype})
        return out

    def enemy_route(self) -> tuple[int, list[dict]]:
        """The CPUs' route of this race: the enemy points as re-sampled for a
        race (`AIPathManager::m_race_point_accessor`, enemy-ai-behaviour Finding
        1), a point every 75 to 150 units, also built in time trials. Returns
        the accessor's address and its points: index, position, next point
        indices, path index, half-width, and the settings each point copies
        from its enemy point (mushroom setting, flags, max search Y offset)."""
        kd = self.mem.u32(self.director_list() + 0x10)                 # SDirectorList::m_kart_director
        ai = self.mem.u32(kd + 0x58)                                   # AIManager
        apm = self.mem.u32(ai + 0x4) if ai else 0                      # AIManager::m_ai_path_manager
        if not apm:
            return 0, []
        acc = apm + 0x28                                               # AIPathManager::m_race_point_accessor
        out = []
        for e in self.game.ptr_array(acc + 0xC):
            raw = self.mem.read(e, 0x2C)                               # Field::MapdataEnemyPoint
            data, _, _, nxt, _, count, _, index, path, _, width = struct.unpack("<IIIIiiiiiff", raw)
            nexts = list(struct.unpack("<%di" % count, self.mem.read(nxt, 4 * count))) if count > 0 else []
            x, y, z, _, mushroom, _, flags, _, max_y = struct.unpack("<4fHBBhh", self.mem.read(data, 0x18))
            out.append({"index": index, "pos": (x, y, z), "next": nexts, "path": path, "width": width,
                        "mushroom": mushroom, "flags": flags, "max_search_y": max_y})
        return acc, out

    def jugem_points(self) -> list[dict]:
        acc = self.mem.u32(self._mapdata() + 0x3C)
        out = []
        for i, e in enumerate(self.game.ptr_array(acc + 0xC)):
            data = self.mem.u32(e)
            out.append({"index": i, "pos": self.game.vec3(data), "checkpoint": self.mem.u8(e + 0x28)})
        return out
