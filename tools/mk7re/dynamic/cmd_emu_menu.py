"""`mk7 emu` commands for the menus: page buttons, navigation, unlocking
(menu.py, docs/tooling/EMULATOR.md)."""
from .cmd_emu import _Connected
from .courses import battle_button, cup_and_course
from .menu import Menu


def cmd_complete(args):
    code = args.code if not args.code.lstrip("-").isdigit() else int(args.code)
    with _Connected() as s:
        if args.wait:
            s.wait_section(args.page, timeout=args.timeout)
        Menu(s).complete(args.page, code)
        print(f"{args.page} completed with {args.code}, frame {s.frame}")


def _button_arg(text: str) -> int | str:
    return int(text) if text.isdigit() else text


def _print_buttons(m, page):
    for b in m.buttons(page):
        cursor = f"cursor {b['cursor']}" if b["cursor"] is not None else "no cursor"
        keys = "+".join(dict.fromkeys(f"key {it['key']:#x}" for it in b["items"] if it["kind"] == "key"))
        if b["button"]:
            what = f"returns {b['return']} ({b['code']})  option {b['option']}"
        else:
            what = "not a BaseMenuButtonControl"
        why = m.press_blocked(b, calls=False)
        print(f"  [{b['id']}] {b['class']}  {what}  {cursor}{'  ' + keys if keys else ''}  "
              f"{'ready' if why is None else why}  @{b['control']:#x}")


def cmd_buttons(args):
    with _Connected() as s:
        m = Menu(s)
        if args.page:
            print(args.page)
            try:
                _print_buttons(m, args.page)
            except (LookupError, ValueError) as e:
                raise SystemExit(str(e))
            return
        for info in s.game.running_sections():
            if info["type"] == "page" and m.page_manipulators(info["addr"]):
                print(f"{info['name']} ({info['class']})")
                _print_buttons(m, info["addr"])


def cmd_click(args):
    with _Connected() as s:
        if args.wait:
            s.wait_section(args.page, timeout=args.timeout)
        try:
            r = Menu(s).click(args.page, _button_arg(args.button), select=not args.no_select, timeout=args.timeout)
        except (LookupError, ValueError, TimeoutError) as e:
            raise SystemExit(str(e))
        b = r["button"]
        print(f"{args.page}: pressed [{b['id']}] {b['class']} ({b.get('return', '-')}); frame {r['frame']}: "
              f"page {r['page_state']}, return {r['page_return']}, menu state {r['menu_state']}")


def cmd_unlock(args):
    with _Connected() as s:
        Menu(s).unlock_all(not args.off)
    print("everything locked as the save says" if args.off else "everything unlocked until the game restarts")


def cmd_timetrial(args):
    from .cmd_emu_race import _kart, _run
    try:
        cup, course = cup_and_course(args.cup, args.course)
    except ValueError as e:
        raise SystemExit(str(e))
    _run(lambda f: f.time_trial(cup, course, args.character, _kart(args), instant=not args.wait_goal,
                                until=args.until), args)


def cmd_channel(args):
    with _Connected() as s:
        m = Menu(s)
        m.open_channel()
        if not args.stay:
            m.close_channel()


def cmd_multiplayer(args):
    with _Connected() as s:
        m = Menu(s)
        m.open_multiplayer()
        if not args.stay:
            m.close_multiplayer()


def cmd_character(args):
    with _Connected() as s:
        Menu(s).choose_character(int(args.name) if args.name.isdigit() else args.name, page=args.page)


def cmd_kart(args):
    from .cmd_emu_race import _kart
    with _Connected() as s:
        Menu(s).choose_kart(*(_kart(args) or (None, None, None)), page=args.page, ok=not args.no_ok)


def cmd_tt_course(args):
    try:
        cup, course = cup_and_course(args.cup, args.course)
    except ValueError as e:
        raise SystemExit(str(e))
    with _Connected() as s:
        Menu(s).time_trial_course(cup, course)


def cmd_battle_course(args):
    try:
        course = battle_button(args.course)
    except ValueError as e:
        raise SystemExit(str(e))
    with _Connected() as s:
        Menu(s).battle_course(course)


def cmd_settings(args):
    with _Connected() as s:
        m = Menu(s)
        try:
            m.apply_settings({n: getattr(args, n) for n in ("cpu", "stage", "items", "teams")
                              if getattr(args, n) is not None}, args.team)
        except (LookupError, TimeoutError, ValueError, RuntimeError) as e:
            raise SystemExit(str(e))
        for name, st in m.settings().items():
            print(f"{name}: {st['name'] or st['value']}  (value {st['value']}, {st['min']}..{st['max']})")
        team = m.player_team()
        print(f"player team: {team or 'none (teams off)'}; frame {s.frame}")


def add_course_args(q):
    """A race course: its .szs name alone, or the cup and course buttons (courses.py)."""
    q.add_argument("cup", help="the course's .szs name (Gn64_KalimariDesert, ...), or the cup button: 0..3 new "
                   "cups (Mushroom, Flower, Star, Special), 4..7 retro cups (Shell, Banana, Leaf, Lightning)")
    q.add_argument("course", type=int, nargs="?", help="with a cup button: 0..3, the course's button in the cup "
                   "(not ECourseID)")


def register(add):
    from .cmd_emu_race import add_battle_setting_args
    q = add("settings", cmd_settings, "the battle settings page (Page_SingleSetting): set rules and the player's "
            "team as a player does, then list them")
    add_battle_setting_args(q)
    q = add("character", cmd_character, "press a character on the character page (by EDriverID name or number)")
    q.add_argument("name")
    q.add_argument("--page", default="Page_SingleChara")
    q = add("kart", cmd_kart, "turn the kart page's reels to the parts given (as a player: Up/Down), then OK")
    from .cmd_emu_race import add_driver_args
    add_driver_args(q, parts_only=True)
    q.add_argument("--page", default="Page_SingleKart")
    q.add_argument("--no-ok", action="store_true", help="do not press OK")
    q = add("tt-course", cmd_tt_course, "from the time trial cup page (after Change Course or Change Character) "
            "to the race")
    add_course_args(q)
    q = add("battle-course", cmd_battle_course, "from the battle course page (after Change Course) into the battle")
    q.add_argument("course", help="the battle course: its .szs name (Bn64_BigDonut, ...) or its button 0..5 "
                   "(not ECourseID)")
    q = add("channel", cmd_channel, "from the title menu into the Mario Kart Channel and back (SpotPass dialog: Cancel)")
    q.add_argument("--stay", action="store_true", help="stay on the channel's top page")
    q = add("multiplayer", cmd_multiplayer, "from the title menu into the local multiplayer group list and back")
    q.add_argument("--stay", action="store_true", help="stay on the group list")
    q = add("buttons", cmd_buttons, "the buttons of a running page (default: of every running page with input)")
    q.add_argument("page", nargs="?")
    q = add("click", cmd_click, "press a page's button through its handler, as the manipulator does")
    q.add_argument("page")
    q.add_argument("button", help="id from `buttons`, the name of the code it returns (Next01, Back) or its "
                   "class (OKButton)")
    q.add_argument("--no-select", action="store_true", help="do not move the cursor onto the button first")
    q.add_argument("--wait", action="store_true", help="wait for the page to be running first")
    q.add_argument("--timeout", type=float, default=120.0)

    q = add("complete", cmd_complete, "complete a running page with a return code, as its buttons do")
    q.add_argument("page")
    q.add_argument("code", help="return code enum of the page: 0..7, Next00..Next07, Back")
    q.add_argument("--wait", action="store_true", help="wait for the page to be running first")
    q.add_argument("--timeout", type=float, default=120.0)

    q = add("unlock", cmd_unlock, "make every cup, character and kart part count as unlocked (save not changed)")
    q.add_argument("--off", action="store_true", help="restore the game's checks")
    q = add("timetrial", cmd_timetrial, "from the title menu straight to a time trial on any race course")
    add_course_args(q)
    q.add_argument("--until", default="race", choices=("race", "results", "Page_Title"),
                   help="stop on the race page (default), or finish the run at once and stop at the menu after "
                        "the results or back at the title")
    q.add_argument("--wait-goal", action="store_true", help="with --until results/Page_Title: wait for the run to "
                   "end by itself instead of finishing it at once")
    from .cmd_emu_race import add_driver_args
    add_driver_args(q)
