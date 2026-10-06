"""Courses of Mario Kart 7 (eur2): `RaceSys::ECourseID`, the name of each
course's `.szs` archive, and where the menus offer it.

The menus number courses by button, not by ECourseID: the cup page's buttons
are `Sequence::ECup` (0..7), the course page's buttons the slots of the cup
(0..3), the battle course page's buttons 0..5. The tables below are the
game's own; the functions turn an `.szs` name into those buttons.
"""

# RaceSys::ECourseID order, which is also the order of RaceSys::GetCourseName's table (0x00678D88, filled by
# sub_0054BB98 with these strings): the .szs archive of each course is Course/<name>.szs (docs/tooling/GAME_DATA.md).
COURSES = [
    "Gctr_MarioCircuit", "Gctr_RallyCourse", "Gctr_MarineRoad", "Gctr_GlideLake", "Gctr_ToadCircuit",
    "Gctr_SandTown", "Gctr_AdvancedCircuit", "Gctr_DKJungle", "Gctr_WuhuIsland1", "Gctr_WuhuIsland2",
    "Gctr_IceSlider", "Gctr_BowserCastle", "Gctr_UnderGround", "Gctr_RainbowRoad", "Gctr_WarioShip",
    "Gctr_MusicPark", "Gwii_CoconutMall", "Gwii_KoopaCape", "Gwii_MapleTreeway", "Gwii_MushroomGorge",
    "Gds_LuigisMansion", "Gds_AirshipFortress", "Gds_DKPass", "Gds_WaluigiPinball", "Ggc_DinoDinoJungle",
    "Ggc_DaisyCruiser", "Gn64_LuigiCircuit", "Gn64_KalimariDesert", "Gn64_KoopaTroopaBeach", "Gagb_BowserCastle1",
    "Gsfc_MarioCircuit2", "Gsfc_RainbowRoad", "Bctr_WuhuIsland3", "Bctr_HoneyStage", "Bctr_IceRink",
    "Bds_PalmShore", "Bn64_BigDonut", "Bagb_BattleCourse1", "Gctr_WinningRun",
]
CUPS = ["Mushroom", "Flower", "Star", "Special", "Shell", "Banana", "Leaf", "Lightning"]   # Sequence::ECup
# Sequence::GetGPCourse(ECup, slot): the table at 0x00694648, written by a static initializer (sub_00560800,
# 0x00564350). The time trial and Grand Prix course pages load GetGPCourse(GetRaceCup(), button)
# (MenuSingle_CourseBase::buttonHandler_OK).
GP_COURSES = [
    [4, 3, 2, 5], [8, 0, 15, 1], [12, 14, 6, 9], [7, 10, 11, 13],
    [26, 29, 19, 20], [28, 30, 16, 23], [27, 22, 25, 18], [17, 24, 21, 31],
]
# Sequence::GetBattleCourse(button): the table at 0x006946C8, written by the same initializer. The battle course
# page loads it for its button (MenuSingle_CourseBattle::buttonHandler_OK).
BATTLE_COURSES = [37, 36, 35, 33, 34, 32]


def course_name(course_id: int) -> str:
    """The .szs name of an ECourseID, or "ECourseID <n>" outside the table."""
    return COURSES[course_id] if 0 <= course_id < len(COURSES) else f"ECourseID {course_id}"


def course_id(name: str) -> int:
    """The ECourseID of an .szs name (case ignored, ".szs" optional)."""
    key = name.lower().removesuffix(".szs")
    for i, n in enumerate(COURSES):
        if n.lower() == key:
            return i
    raise ValueError(f"unknown course {name!r}; one of {', '.join(COURSES)}")


def is_name(value) -> bool:
    """Whether a menu argument is a course name rather than a button number."""
    return isinstance(value, str) and not value.isdigit()


def race_buttons(name: str) -> tuple[int, int]:
    """The cup button and the course button of a race course (.szs name)."""
    cid = course_id(name)
    for cup, slots in enumerate(GP_COURSES):
        if cid in slots:
            return cup, slots.index(cid)
    what = "a battle course (battle, battle-course)" if cid in BATTLE_COURSES else "in no cup"
    raise ValueError(f"{COURSES[cid]} is {what}, not a race course")


def battle_button(course) -> int:
    """The battle course page's button of a battle course: an .szs name, or
    the button number itself."""
    if not is_name(course):
        return int(course)
    cid = course_id(course)
    if cid not in BATTLE_COURSES:
        raise ValueError(f"{COURSES[cid]} is not a battle course; one of "
                         f"{', '.join(COURSES[c] for c in BATTLE_COURSES)}")
    return BATTLE_COURSES.index(cid)


def cup_and_course(cup, course=None) -> tuple[int, int]:
    """(cup button, course button) from either the two button numbers or a
    race course's .szs name alone (in `cup`, with `course` None)."""
    if course is None:
        if not is_name(cup):
            raise ValueError("give the cup and course buttons (two numbers) or the course's .szs name")
        return race_buttons(cup)
    if is_name(cup) or is_name(course):
        raise ValueError("give the cup and course buttons (two numbers) or the course's .szs name alone")
    return int(cup), int(course)
