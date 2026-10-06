"""`mk7 emu` commands for races: the countdown, finishing a race, the result
screens, kart state and position (race.py), and whole Grand Prix runs
(flow.py, docs/tooling/EMULATOR.md)."""
from .cmd_emu import _Connected
from .courses import battle_button, course_name
from .race import Race


def cmd_race_start(args):
    with _Connected() as s:
        if not Race(s).wait_start(args.timeout):
            raise SystemExit("the race timer did not start")
        print(f"race started, frozen at frame {s.frame}")


def cmd_race(args):
    with _Connected() as s:
        r = Race(s)
        course = r.course_id()
        mode = r.race_mode()
        # battles have no lap and checkpoint state (ModeManagerBattle keeps no LapRankChecker)
        ki = None if mode["rule"] in ("Battle", "DemoBattle") else r.kart_info(args.player)
        k = r.kart(args.player)
    print(f"course {course} {course_name(course)}, {mode['rule']}")
    if ki is None:
        print(f"player {args.player}: no checkpoint state in a battle")
    else:
        print(f"player {args.player}: checkpoint prev {ki['previous_checkpoint']} cur {ki['current_checkpoint']} "
              f"last valid {ki['last_valid_checkpoint']} key {ki['key_checkpoint']}  lap {ki['lap']}  "
              f"progress {ki['race_progress']:.4f}  flags {ki['flags']:#x}")
    print(f"  pos ({k['pos'][0]:.1f}, {k['pos'][1]:.1f}, {k['pos'][2]:.1f})  "
          f"velocity ({k['velocity'][0]:.2f}, {k['velocity'][1]:.2f}, {k['velocity'][2]:.2f})  "
          f"status {k['status']:#x}")


def cmd_teleport(args):
    with _Connected() as s:
        Race(s).set_kart_pos(args.player, (args.x, args.y, args.z))


def _print_drive(st):
    if not st["installed"] or st["mode"] == "off":
        print("the simulated player is off" + (f" ({st['status']})" if st.get("status") not in (None, "idle") else ""))
        return
    t, p = st["target"], st["pos"]
    where = f", target ({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f}) radius {st['radius']:.0f}" if st["mode"] != "race" else ""
    print(f"drive {st['mode']}: {st['status']}{where}")
    print(f"  kart ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})  distance {st['dist']:.1f}  angle {st['angle']:.1f}  "
          f"speed {st['speed']:.2f}  input buttons {st['buttons']:#x} stick {st['stick']:.2f}  {st['frames']} frames")
    if st["mode"] != "goto":
        print(f"  route entry {st['route_pos']} of {st['route_count']} (point {st['target_point']}, aiming at "
              f"{st['aim_point']}; {st['point_count']} route points), {st['advances']} points reached, "
              f"{st['plans']} searches, {st['reroutes']} re-routes")
    print(f"  {st['backups']} back-ups, {st['drifts']} drifts, {st['tricks']} tricks, {st['lakitus']} times Lakitu")


def cmd_drive(args):
    from .driver import Driver
    with _Connected() as s:
        d = Driver(s)
        if args.action in ("goto", "route"):
            if len(args.xyz) != 3:
                raise SystemExit(f"{args.action} takes X Y Z")
            if args.action == "goto":
                d.go_to(args.xyz, args.radius)
            else:
                d.go_by_route(args.xyz, args.radius, forward_only=args.forward, drift=not args.no_drift,
                              trick=not args.no_trick)
            if args.wait:
                if not s.run_until(lambda _: d.ended(), args.timeout):
                    print(f"not there after {args.timeout:.0f} s")
        elif args.action == "race":
            d.race(drift=not args.no_drift, trick=not args.no_trick)
            if args.wait:
                from .race import Race
                if not Race(s).wait_goal(args.timeout):
                    print(f"no goal after {args.timeout:.0f} s")
        elif args.action == "off":
            d.off()
        if args.action != "status" and not args.wait and s.hooks.state()["frozen"]:
            print("the game is frozen: the kart drives once it runs (`mk7 emu run`, `step`)")
        _print_drive(d.status())
        print(f"frame {s.frame}")


def cmd_player(args):
    from .driver import set_player
    with _Connected() as s:
        set_player(s, args.mode)
    print({"normal": "the pad drives the player's kart", "cpu": "the game's AI drives the player's kart (CPU type)",
           "simulated": "the simulated player drives the player's kart (`drive race`)"}[args.mode]
          + " from the next race on, until the game restarts")


def cmd_skip_demo(args):
    with _Connected() as s:
        Race(s).skip_demo()
        print(f"course intro skipped, frame {s.frame}")


def cmd_finish(args):
    order = [int(p) for p in args.order.split(",")] if args.order else None
    with _Connected() as s:
        r = Race(s)
        r.finish(order, args.place)
        if not args.no_results:
            r.results_menu()
        print(f"finished, ranks by player id {r.race_state()['ranks']}; frame {s.frame}"
              + ("" if args.no_results else ", the race page's menu is open (`mk7 emu buttons Page_Race`)"))


def cmd_advance(args):
    from .flow import Flow
    with _Connected() as s:
        try:
            Flow(s).advance(args.page, press=not args.no_press, timeout_frames=args.frames)
        except (LookupError, TimeoutError) as e:
            raise SystemExit(str(e))


def _kart(args):
    parts = [args.body, args.tire, args.wing]
    return None if parts == [None, None, None] else tuple(parts)


def _run(func, args=None):
    """Run a Flow step, report where the game stopped. With `--player` in
    `args`, who drives the player's kart is set first (driver.set_player)."""
    from .flow import Flow
    with _Connected() as s:
        f = Flow(s)
        try:
            if getattr(args, "player", None):
                from .driver import set_player
                set_player(s, args.player, f.menu)
                print(f"player: {args.player} (until the game restarts or `player normal`)")
            func(f)
        except (LookupError, TimeoutError, ValueError, RuntimeError) as e:
            raise SystemExit(str(e))
        print(f"frozen at frame {s.frame}")


def cmd_grandprix(args):
    places = [int(p) for p in args.place.split(",")]
    if len(places) not in (1, 4):
        raise SystemExit("--place takes one place or four (one per race)")
    _run(lambda f: f.grand_prix(args.cup, args.engine, places if len(places) == 4 else places[0], args.character,
                                _kart(args), instant=not args.wait_goal, skip_demo=not args.demo, until=args.until),
         args)


def cmd_battle(args):
    settings = {name: getattr(args, name) for name in ("cpu", "stage", "items", "teams")
                if getattr(args, name) is not None}
    if args.team and "teams" not in settings:
        settings["teams"] = "on"
    try:
        course = None if args.course is None else battle_button(args.course)
    except ValueError as e:
        raise SystemExit(str(e))
    _run(lambda f: f.battle(args.kind, course, args.place, args.character, _kart(args),
                            instant=not args.wait_goal, until=args.until, settings=settings, team=args.team), args)


def cmd_vs(args):
    settings = {name: getattr(args, attr) for name, attr in (("class", "engine_class"), ("cpu-on", "cpu"),
                                                             ("stage", "stage"), ("items", "items"),
                                                             ("teams", "teams"))
                if getattr(args, attr) is not None}
    if args.team and "teams" not in settings:
        settings["teams"] = "on"
    places = [int(p) for p in args.place.split(",")]
    _run(lambda f: f.vs(args.course, places if len(places) > 1 else places[0], args.character, _kart(args),
                        instant=not args.wait_goal, until=args.until, settings=settings, team=args.team), args)


def cmd_continue(args):
    places = [int(p) for p in args.place.split(",")]
    _run(lambda f: f.resume(place=places[0], places=places if len(places) > 1 else None, instant=not args.wait_goal,
                            skip_demo=not args.demo, until=args.until, courses=args.course))


def cmd_menu(args):
    def run(f):
        if args.option is None:
            if f.race.menu_state() != 3:
                f.race.pause()
            print("options:", ", ".join(f.menu_options()))
        else:
            f.menu_option(args.option)
    _run(run)


def add_driver_args(q, parts_only=False):
    """--character, --body, --tire, --wing (Menu.choose_character / choose_kart; names or ids) and --player.
    parts_only: only the kart parts (the kart page cannot choose the character)."""
    from .menu import BODIES, DRIVERS, TIRES, WINGS
    if not parts_only:
        q.add_argument("--character", type=_enum_arg, help="EDriverID name or number: " + ", ".join(DRIVERS))
    q.add_argument("--body", type=_enum_arg, help="EBodyID: " + ", ".join(BODIES))
    q.add_argument("--tire", type=_enum_arg, help="ETireID: " + ", ".join(TIRES))
    q.add_argument("--wing", type=_enum_arg, help="EWingID: " + ", ".join(WINGS))
    if parts_only:
        return
    q.add_argument("--player", choices=("normal", "cpu", "simulated"),
                   help="who drives the player's kart from now on (`player`): the pad, the game's AI, or the "
                        "simulated player (`drive race`)")


def add_battle_setting_args(q):
    """The rules of the battle settings page (Menu.set_setting); left out: as the page has them."""
    from .menu import SETTINGS
    for kind in (2, 3, 4, 5):
        name, values = SETTINGS[kind]
        q.add_argument(f"--{name}", choices=values, help=f"the {name} setting")
    q.add_argument("--team", choices=("red", "blue"), help="the player's team (turns teams on)")


def _enum_arg(text):
    return int(text) if text is not None and text.isdigit() else text


def register(add):
    q = add("battle", cmd_battle, "from the title menu to a single-player battle, ended at once at the place given")
    q.add_argument("kind", choices=("balloon", "coin"))
    q.add_argument("course", nargs="?", help="the battle course: its .szs name (Bn64_BigDonut, ...) or its button "
                   "0..5 (not ECourseID); not with --stage random or in-order")
    q.add_argument("--place", type=int, default=1, help="the player's place (default 1)")
    add_battle_setting_args(q)
    q.add_argument("--until", default="Page_Title", choices=("race", "results", "Page_Title"),
                   help="stop on the race page (before the countdown ends), at the menu after the results, or "
                        "back at the title (default)")
    q.add_argument("--wait-goal", action="store_true", help="do not end the battle at once: wait for its clock")
    add_driver_args(q)
    q = add("vs", cmd_vs, "from the title menu through a single-player VS run (`start --vs`, vs.py): 4 races, "
            "each finished at once at the place given, the trophy, back to the title")
    q.add_argument("course", nargs="*", help="the course of each race, by .szs name (sets --stage choose); with "
                   "--stage in-order only the first; none with --stage random")
    q.add_argument("--place", default="1", help="the player's place in every race, or one per race, "
                   "comma-separated")
    q.add_argument("--class", dest="engine_class", choices=("50cc", "100cc", "150cc"), help="the class setting")
    q.add_argument("--cpu", choices=("off", "on"), help="the CPU setting (default on; off: the player races alone)")
    from .menu import SETTINGS
    for kind in (3, 4, 5):
        name, values = SETTINGS[kind]
        q.add_argument(f"--{name}", choices=values, help=f"the {name} setting")
    q.add_argument("--team", choices=("red", "blue"), help="the player's team (turns teams on)")
    q.add_argument("--until", default="Page_Title", choices=("race", "results", "Page_Title"),
                   help="stop on the first race page (before the countdown ends), at the menu after the next "
                        "results, or back at the title after the trophy (default)")
    q.add_argument("--wait-goal", action="store_true", help="do not finish the races at once: wait until each ends "
                   "by itself")
    add_driver_args(q)
    q = add("grandprix", cmd_grandprix, "from the title menu through a whole Grand Prix, finishing each race at "
            "once (or stop at the first race: --until race, then `continue`)")
    q.add_argument("cup", type=int, help="0..3 new cups (Mushroom, Flower, Star, Special), 4..7 retro cups")
    q.add_argument("--engine", type=int, default=0, help="0..3: 50cc, 100cc, 150cc, mirror")
    q.add_argument("--place", default="1", help="the player's place in every race, or four comma-separated")
    q.add_argument("--until", default="Page_Title",
                   help="where to stop: race (first race page, before the countdown ends), results (menu of the "
                        "last race), or a page: Page_WinningRun, Page_Trophy, Page_Ending, Page_Thankyou, "
                        "Page_Title (default)")
    q.add_argument("--demo", action="store_true", help="watch the course intros instead of skipping them")
    q.add_argument("--wait-goal", action="store_true", help="do not finish the races at once: wait until each ends "
                   "by itself (the research drives)")
    add_driver_args(q)
    q = add("continue", cmd_continue, "carry the single-player run on from where it is (race, pause, goal, results, "
            "replay): finish the race at once, go to the next race, the trophy, or quit to the title")
    q.add_argument("--place", default="1", help="the player's place, or one per remaining race, comma-separated")
    q.add_argument("--until", default="Page_Title",
                   help="race (the next race page), results (the next result menu), or a page: Page_WinningRun, "
                        "Page_Trophy, Page_Ending, Page_Thankyou, Page_Title (default)")
    q.add_argument("--wait-goal", action="store_true", help="wait for the race to end by itself instead")
    q.add_argument("--demo", action="store_true", help="watch the course intros")
    q.add_argument("--course", action="append", help="VS with the stage at choose: the course of the next race "
                   "(.szs name), once per race left")
    q = add("menu", cmd_menu, "choose an option of the race page's menu (opens the pause or replay menu, or the "
            "result menu at the goal); without an option, list them")
    q.add_argument("option", nargs="?", choices=("continue", "restart", "course", "character", "replay", "next",
                                                 "trophy", "quit"))
    q = add("skip-demo", cmd_skip_demo, "skip the course intro of a Grand Prix race (press A on Page_Demo)")
    q = add("finish", cmd_finish, "finish the race now with chosen places, then press through the results")
    q.add_argument("--place", type=int, help="the player's place (default 1); the others keep their id order")
    q.add_argument("--order", help="player ids in finishing order, comma-separated (instead of --place)")
    q.add_argument("--no-results", action="store_true", help="stop at the goal, before the result screens")
    q = add("advance", cmd_advance, "press A every 30 frames until a page runs (result, trophy, ending screens)")
    q.add_argument("page", help="section name, e.g. Page_Trophy, Page_Ending, Page_Title")
    q.add_argument("--no-press", action="store_true", help="only let the game run")
    q.add_argument("--frames", type=int, default=36000, help="give up after this many frames")

    q = add("race-start", cmd_race_start, "run until the race timer runs (after the countdown), then freeze")
    q.add_argument("--timeout", type=float, default=300.0)

    q = add("race", cmd_race, "course, checkpoint state and kart position of a player")
    q.add_argument("-p", "--player", type=int, default=0)
    q = add("drive", cmd_drive, "the simulated player (driver.py): drive the player's kart with computed inputs")
    q.add_argument("action", choices=("goto", "route", "race", "off", "status"),
                   help="goto: straight to a point, stopping within --radius; route: along the CPUs' route to the "
                        "route point nearest it, then as goto; race: drive the race along the route, in every "
                        "race from now on; off: back to the pad; status")
    q.add_argument("xyz", nargs="*", type=float, help="goto, route: X Y Z")
    q.add_argument("--radius", type=float, default=150.0,
                   help="goto, route: stop within this distance of the point (default 150)")
    q.add_argument("--forward", action="store_true",
                   help="route: only along the route's direction, as CPUs drive (default: the shortest way, also "
                        "backwards)")
    q.add_argument("--no-drift", action="store_true", help="route, race: never drift")
    q.add_argument("--no-trick", action="store_true", help="route, race: never hop at trick chances")
    q.add_argument("--wait", action="store_true", help="run the game until the point is reached (race: the goal), "
                   "then freeze")
    q.add_argument("--timeout", type=float, default=300.0, help="--wait: give up after this many seconds")
    q = add("player", cmd_player, "who drives the player's kart from the next race on: the pad, the game's AI "
            "(player type CPU) or the simulated player")
    q.add_argument("mode", choices=("normal", "cpu", "simulated"))
    q = add("teleport", cmd_teleport, "set a kart's position and stop it")
    q.add_argument("x", type=float)
    q.add_argument("y", type=float)
    q.add_argument("z", type=float)
    q.add_argument("-p", "--player", type=int, default=0)
