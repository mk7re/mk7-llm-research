"""Whole-game sequences of Mario Kart 7 (eur2) in the running game: a Grand
Prix from the title menu through its races, the winning run, the trophy, the
ending and back to the title, a battle or a time trial, with the results
chosen; and the menus of the race page (pause, replay, results).

`Flow(session)` combines `Menu` (menu pages, through their buttons) and
`Race` (races, the course intro and the result screens). The scene order is
that of `Root-Default.brs` (ProductMain): MenuScene -GP-> DemoScene (course
intro) -> RaceScene; RaceScene -SingleGP_Next-> DemoScene, -SingleGP_Trophy->
WinningRunScene (Task_WinningRunSelectTask: only in the top 3) -> TrophyScene
-SingleGPEnding-> EndingScene -> ThankyouScene -> MenuScene (title).

A run does not have to be finished at once: `resume` carries a run on from
wherever it is (a race in its countdown or under way, paused, at the goal,
on the result menu, in a replay), finishing each race at once (instant=True)
or waiting for it to end by itself (instant=False), so that research can stop
in a race, look, and then let the run go on.
"""
from .courses import course_name
from .game import Session
from .hooks import PAD_A
from .menu import Menu
from .race import Race

# The pages of the scenes after a Grand Prix, in order. They read the pad, not page buttons: A (UI::tstDemoButton)
# completes them once they run. Page_Ending takes it only once the ending has been seen
# (System::Flag::IsOpen(ESequenceOpenFlag 0 or 6), which `unlock` opens); otherwise it runs to its end.
CEREMONY = ("Page_WinningRun", "Page_Trophy", "Page_Ending", "Page_Thankyou", "Page_Title")

# The options of the race page's menus, by what they do, and the codes their buttons return (`Menu.buttons`).
# Measured on 2026-10-03:
#   time trial pause: Continue, Restart, Change Course, Change Character, Quit
#   time trial results: Retry, Change Course, Change Character, Replay, Quit
#   time trial replay (A): Continue Replay, Retry, Change Course, Change Character, Restart Replay, Quit
#   Grand Prix pause: Continue, Quit (then "Yes"/"No")
#   Grand Prix results: Next Race (or Trophy after the last race), Replay, Quit
#   Grand Prix replay (A): Continue Replay, Next Race, Restart Replay, Quit
#   battle pause: Continue, Quit; battle results: Change Course, Quit
#   VS (`start --vs`, vs.py; 2026-10-05) results: Next Race (MultiVS_Next with the stage at random or in order,
#   MultiVS_Course with it at choose: the cup page), or Trophy after the 4th race; Quit
# "continue" closes the menu (ECompleteNextMode -3). The Grand Prix Quit returns -4: it opens a Yes/No dialog on
# Page_CommonSystemDialog, answered Yes (cursor 2). "replay" is also Restart Replay in a replay.
MENU_OPTIONS = {
    "continue": ("close menu",),
    "restart": ("SingleTA_Retry",),
    "course": ("SingleTA_Course", "SingleBB_Course", "SingleBC_Course", "MultiVS_Course"),
    "character": ("SingleTA_Chara",),
    "replay": ("SingleGP_Replay", "SingleTA_Replay"),
    "next": ("SingleGP_Next", "MultiVS_Next"),
    "trophy": ("SingleGP_Trophy", "MultiVS_Trophy"),
    "quit": ("SingleTA_Exit", "SingleBT_Exit", "mode -4"),
}
DIALOG_YES = 2          # Page_CommonSystemDialog: cursor 1 is No / Cancel (B), 2 Yes / OK


class Flow:
    """Single-player runs and the scenes after them, for a Session."""

    def __init__(self, session: Session):
        self.s = session
        self.menu = Menu(session)
        self.race = Race(session)

    def advance(self, target: str, press=True, timeout_frames=36000, log=print) -> int:
        """Press A every 30 frames (press=False: only run) until the section
        `target` runs, then stay frozen there. Logs every change of the
        running pages. Returns the frame."""
        seen = None
        for i in range(0, timeout_frames, 30):
            names = tuple(info["name"] for info in self.s.game.running_sections())
            if names != seen:
                log(f"frame {self.s.frame}, scene {self.s.game.scene_id()}: "
                    + ", ".join(n for n in names if n.startswith("Page_")))
                seen = names
            if target in names:
                return self.s.frame
            if "Page_Title" in names:       # back at the title: A would choose a mode there
                raise LookupError(f"back at the title menu without reaching {target}")
            if press and (i // 30) % 2 == 0:
                self.s.press(PAD_A)
                self.s.step(25)
            else:
                self.s.step(30)
        raise TimeoutError(f"{target} did not start within {timeout_frames} frames")

    # ---- the race page's menus --------------------------------------------------
    def menu_options(self) -> dict[str, dict]:
        """The options of the race page's open menu, by name (MENU_OPTIONS):
        the buttons that its active manipulator holds."""
        active = self.menu.active_manipulator()
        out = {}
        for b in self.menu.buttons("Page_Race"):
            if b["button"] and any(it["manipulator"] == active for it in b["items"]):
                for name, returns in MENU_OPTIONS.items():
                    if b["return"] in returns:
                        out.setdefault(name, b)
        return out

    def menu_option(self, name: str, log=print):
        """Choose an option of the race page's menu: opens the pause or
        replay menu first if none is open (or, at the goal, presses through
        the results to their menu), and answers Yes to the Grand Prix's
        "quit?" dialog. The page then goes on as with real input."""
        if self.race.menu_state() != 3:
            if self.race.race_state()["state"] == "goal" and self.race.race_mode()["play"] != "Replay":
                self.race.results_menu()
            else:
                self.race.pause()
        options = self.menu_options()
        if name not in options:
            raise LookupError(f"no {name!r} in this menu; it has: {', '.join(options) or 'nothing'}")
        button = options[name]
        self.menu.click("Page_Race", button)
        log(f"Page_Race: {name} ({button['return']})")
        if button["code"] == -4:
            self.menu.click("Page_CommonSystemDialog", DIALOG_YES)
            log("Page_CommonSystemDialog: Yes")

    # ---- runs ---------------------------------------------------------------------
    def resume(self, place=1, places=None, instant=True, skip_demo=True, until="Page_Title", courses=None,
               log=print):
        """Carry the single-player run on from where it is, then freeze:

        - a race (or battle) in its countdown waits for the start; under way,
          it is finished at once (instant=True: `Race.finish` or
          `finish_battle`, the player at `place`, or at the next entry of
          `places` for each race in turn) or left to end by itself
          (instant=False, `Race.wait_goal`); a pause menu is closed first;
        - at the goal it presses through the results to their menu;
        - from the results (or a replay) of a Grand Prix it goes to the next
          race, after the last one to the trophy and the scenes after it
          (CEREMONY); a time trial or battle is quit to the title;
        - from the results of a VS race (`start --vs`) it goes to the next
          race, through the cup and course pages with the next entry of
          `courses` (an .szs name or (cup, course) buttons, Menu.vs_course)
          when the stage setting is at choose; after the 4th race to the
          trophy and the title.

        `until`: "race" stops on the next race page (before its countdown
        ends), "results" at the next result menu, or a page name
        (Page_WinningRun, Page_Trophy, Page_Ending, Page_Thankyou,
        Page_Title) after the run."""
        queue = list(places or [])
        course_queue = list(courses or [])
        raced = False
        while True:
            if self.s.find_section("Page_Race") is None:
                running = {info["name"] for info in self.s.game.running_sections()}
                if running & set(CEREMONY):                  # after the last race: the trophy and what follows
                    self.advance(until if until not in ("race", "results") else "Page_Title", log=log)
                    return
                self.race.wait_race_page(skip_demo)          # course intro, scene loads
                continue
            mode = self.race.race_mode()
            state = self.race.race_state()["state"]
            menu = self.race.menu_state()
            if mode["play"] == "Replay":
                self.menu_option("next" if mode["rule"] == "GrandPrix" else "quit", log)
                if mode["rule"] != "GrandPrix":
                    return self._to_title(until, log)
                continue
            if state in ("sync", "countdown"):
                if until == "race" and raced:
                    return
                if not self.race.wait_start():
                    raise TimeoutError("the countdown did not end")
                continue
            if state == "race":
                if menu == 3:
                    self.menu_option("continue", log)
                if self.race.menu_state() != 0:
                    self.s.step(10)
                    continue
                p = queue.pop(0) if queue else place
                if not instant:
                    log("waiting for the race to end by itself")
                    self.race.wait_goal()
                elif mode["rule"] == "Battle":
                    self.race.finish_battle(place=p)
                else:
                    self.race.finish(place=p)
                log(f"course {course_name(self.race.course_id())}: " + ("finished" if not instant else f"finished at place {p}"))
                raced = True
                continue
            # the goal
            raced = True
            if menu != 3:
                self.race.results_menu()
                if until == "results":
                    return
                continue
            options = self.menu_options()
            if "next" in options:
                self.menu_option("next", log)
            elif mode["rule"] == "Versus" and "course" in options:
                if not course_queue:
                    raise LookupError("the VS stage setting is choose: give the course of every race (courses)")
                c = course_queue.pop(0)
                self.menu_option("course", log)
                self.menu.vs_course(*(c if isinstance(c, tuple) else (c,)), log=log)
            elif "trophy" in options:
                self.menu_option("trophy", log)
                self.advance(until if until not in ("race", "results") else "Page_Title", log=log)
                return
            else:
                self.menu_option("quit", log)
                return self._to_title(until, log)

    def _to_title(self, until, log):
        self.advance("Page_Title", press=False, log=log)
        if until not in ("Page_Title", "race", "results"):
            raise LookupError(f"the run ended at the title without reaching {until}")

    def grand_prix(self, cup: int, engine=0, places=1, character=None, kart=None, instant=True, skip_demo=True,
                   until="Page_Title", log=print):
        """A Grand Prix from the title menu (Menu.grand_prix: cup 0..7, engine
        class 0..3, character and kart as for Menu.choose_driver_and_kart),
        then `resume`: `places` is the player's place in every race, or a
        list of them, one per race. until="race" stops on the first race
        page. What follows the last race depends on the result: the winning
        run only in the top 3 (WinningRunSelectTask), the ending only for the
        Special and Lightning cups (cups 3 and 7) with a trophy
        (TrophyPage::selectNextScene), so a stop page that the run does not
        reach raises LookupError at the title."""
        self.menu.grand_prix(cup, engine, character, kart, log)
        self.race.wait_race_page(skip_demo)
        if until == "race":
            return
        if isinstance(places, int):
            self.resume(place=places, instant=instant, skip_demo=skip_demo, until=until, log=log)
        else:
            self.resume(places=places, instant=instant, skip_demo=skip_demo, until=until, log=log)

    def battle(self, kind: str, course: int | str | None, place=1, character=None, kart=None, instant=True,
               until="Page_Title", settings=None, team=None, log=print):
        """A single-player battle from the title menu (Menu.battle: rule
        `settings` and the player's `team` as there), then `resume`. until:
        "race", "results" or "Page_Title"."""
        self.menu.battle(kind, course, character, kart, settings, team, log)
        self.race.wait_race_page()
        if until != "race":
            self.resume(place=place, instant=instant, until=until, log=log)

    def vs(self, courses=None, places=1, character=None, kart=None, instant=True, until="Page_Title",
           settings=None, team=None, log=print):
        """A single-player VS run from the title menu (`start --vs`;
        Menu.vs: rule `settings` and the player's `team` as there), then
        `resume` through its 4 races: `courses` lists the course of each
        race (an .szs name or (cup, course) buttons) when the stage setting
        is choose, the default when courses are given; `places` is the
        player's place in every race, or a list, one per race. until:
        "race" (the first race page), "results" or "Page_Title"."""
        courses = list(courses or [])
        self.menu.vs(courses.pop(0) if courses else None, character, kart, settings, team, log)
        self.race.wait_race_page()
        if until == "race":
            return
        if isinstance(places, int):
            self.resume(place=places, instant=instant, until=until, courses=courses, log=log)
        else:
            self.resume(places=places, instant=instant, until=until, courses=courses, log=log)

    def time_trial(self, cup: int | str, course: int | None = None, character=None, kart=None, instant=True, until="Page_Title",
                   log=print):
        """A time trial from the title menu (Menu.time_trial: cup and course
        buttons, or a race course's .szs name in `cup`), then `resume`.
        until: "race", "results" or "Page_Title"."""
        self.menu.time_trial(cup, course, character, kart, log)
        if until != "race":
            self.resume(instant=instant, until=until, log=log)
