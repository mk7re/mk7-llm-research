"""Single-player VS races (eur2), a mode the retail game only offers in local
and online multiplayer. `mk7 emu start --vs` writes these patches at the
game's first instruction; they last until the game restarts.

The single-player mode page (`Page_SingleMode`, MenuSingle_Mode) keeps Grand
Prix (button 0) and turns Time Trials (button 1) into VS. Balloon Battle and
Coin Runners (buttons 2 and 3) do nothing: the patches below break time trials
and battles, so they must not be started.

VS, play mode 0 (single player), rule mode 2 (VS), goes through the pages of
`Seq_Single` in `MenuScene-Default.bss`:

    Page_SingleMode Next01 -> MenuModeSetterTask Versus -> Page_SingleChara -> Page_SingleKart
    -> Page_SingleSetting (built with the VS settings, as MenuMulti_VSSetting is)
    -> courses Choose or In order: Page_SingleCup -> Seq_TAChart (Page_SingleCourse, without the ghost
       page; a course opens the page's start dialog) -> exit Battle (In order: the first course, the
       next ones in cup order)
    -> courses Random: OK opens the page's start dialog -> exit Battle (as for a battle)
    -> Seq_Title VS_TA_Battle -> RaceScene

`Seq_Single` runs `Seq_TAChart` directly instead of `Para_TAChart`, which shows
the time trial record chart (`Page_SingleTAChart`) next to it on the top screen.

The course of each race is chosen by BasePage::loadNextCourse, from the rule
mode (MenuData+0x1DC), the course order setting (MenuData+0x669: choose,
random, in order), the race number (+0x670) and the courses already run
(+0x674): the course chosen on the course page, a random one not run yet, or
the next one in cup order. BaseMenuPage::applySetting_Battle calls it; for a
battle the settings page calls it when it starts the race (Random, In order),
the battle course page when it completes (Choose).

Code patches (CODE_PATCHES):
- MenuSingle_Mode::buttonHandler_OK gives button 1 rule mode 2 (VS) instead of 1.
- MenuSingle_Mode::onPageEnter and ::buttonHandler_SelectOn show the VS text
  and movie for button 1, as they do in local multiplayer (where MenuMulti_Mode
  reuses the page).
- At the end of MenuSingle_Mode::initControl (`mode_hook`, for MenuSingle_Mode
  itself, not MenuMulti_Mode): button 1 gets the VS label, icon and caption as
  MenuMulti_Mode::initControl gives them; buttons 2 and 3 get the return code -1
  (a press does nothing), are hidden (their control sight's root pane) and their
  cursor items are disabled.
- The MenuSingle_Setting constructor leaves +0x295 (battle settings) at 0, so
  Page_SingleSetting builds the VS settings (as the MenuMulti_VSSetting
  constructor does); +0x294 (multiplayer) stays 0.
- MenuSingle_Setting::onPageEnter gives the 7 CPUs their drivers
  (applySetting_CPU_(7, 1, player's driver)) for VS too, not only for battle.
- CPU off: nothing in single player removed those CPUs, so they raced with
  the setting off, without teams (shuffleTeam deals them only while the setting is on). When a run
  starts, MenuSingle_Setting::onPageComplete now calls `cpu_off_hook` (from
  a nop after initRaceNo): with MenuSingle_Setting::isCOM() 0 it clears every
  kart but the player's (BasePage::clearEnemy, as a time trial does: body
  0x12, driver 0x13, player type 6, team 3). CRaceInfo::update then counts
  one kart (calcPlayerNum), and the race has the player alone.
- One kart starts as in a time trial: Field::FieldDirector::calcStartTag
  puts every start slot on start point 0 plus (0, 0, 8) when the rule mode is
  1 (time trial), else lays out the 8-kart grid; `grid_hook` takes the time
  trial's way for m_kart_num 1 too. Before it the player alone started on
  grid slot 8 in the first race (race rank 8) and slot 1 in the next ones.
- BaseMenuPage::applySetting_Battle no longer sets 50cc and no mirror (only
  battle pages call it): the class setting of the VS page stays.
- MenuSingle_Course::onPageComplete calls applySetting_Battle when a course was
  chosen (`course_hook`), as MenuSingle_CourseBattle::onPageComplete does.
- The MenuSingle_Course constructor sets +0x2BC to 1 (`course_ctor_hook`), as
  the MenuMulti_Course constructor does: MenuSingle_CourseBase::initControl
  then builds the start dialog (RaceDialogButton, option 4) and gives the
  course buttons -2 (open the dialog), and onPageComplete fades out
  (StartFadeout) when the page completes forward. Its buttonHandler_OK (vtable
  slot, `course_button_hook`) also moves the garage as the battle course page
  does: a course OK (0xF), the dialog's OK the end (0x10), the dialog closed
  the course state again (0xC).
- MenuSingle_Setting::onPageComplete gives every kart race rank 0 when the run
  starts; the race then puts all eight karts at the same point (measured:
  (-1, 0, 0) on Mario Circuit). The ranks are now those a Grand Prix starts
  with (BaseMenuPage::applySetting_GP: the player 8th, total rank 1), the
  CPUs 7th to 1st.

Garage (Menu3D::GarageDirector, the 3D scene behind the menus):
GarageDirector::onUpdateState_ picks what a state does by scene (+0x63: 0
single player, 1 multiplayer, 2 online) and mode (+0x64: the rule mode). The
single-player scene has nothing for VS (mode 2), so the driver, kart, rules,
cup and course states did nothing (the lights and the shutter stayed as the
previous state left them). For those states the scene is taken as multiplayer,
whose VS states do what the single-player ones of the other modes do
(`garage_hook`).

Cup page after a race (courses Choose): Back asks "quit?" (Yes/No) and Yes
leads to the title, as on the battle course page after a battle
(MenuSingle_CourseBattle::onPageEnter, buttonHandler_OK, onPagePreStep: a race
already run is GetRaceNo() >= 0). MenuSingle_Cup gets 0xC more bytes (its
constructSection allocates 0x320): +0x314 its Back button (stored by
`cup_back_hook` in MenuSingle_CupBase::initControl), +0x318 "Back asks",
+0x319 the dialog is open. In its vtable: onPageEnter (`cup_enter_hook`) gives
the Back button the code -4 (nothing; the handler gets option 8) after a race,
buttonHandler_OK (`cup_button_hook`) opens the dialog for option 8 (message
0x2397, "Are you sure you want to quit?", as BaseRacePage::buttonHandler_OK),
onPagePreStep (`cup_prestep_hook`) completes the page with Next01 on Yes,
after the fade-out, the reserved fade-in and the scene BGM stop of the battle
course page's Yes (MenuSingle_CourseBattle::onPageComplete; the page
finishes once the fade is over, BasePage::canFinishFadeout), which the flow
(BSEQ_PATCHES) leads out of
Seq_Single with SDError: Seq_Title SingleError, MenuScene SingleError, then
ProductMain ClearRaceInfoTask Title_Top loads the menu scene again, at the
title (as Quit on the race page does). Seq_Single's Back (the title page in
the same scene, as the battle course page's Yes) left the garage's kart model
hidden: the character page then waited for the turntable for good.

CPU groups in team races: Enemy::AIRankManager::init sorts the CPUs into
the rank groups (top, middle, last) with decideAllGroupTeamMode_ when teams
are on. It takes the number of CPUs of each team in each group from a table
by the number of human karts (AIManager+0x1C, 0 to 4) and a row from 0 to
that number, the humans on red (one human: red 2 / blue 1 in the top group
with the human on blue, 1 / 2 on red). The row it reads is AIManager+0x20,
which AIManager::initTeamMemberAndOrder sets to every kart on red: 4 with 7
CPUs, past the two rows of one human, so the counts came from stack garbage
and the loops ran for 26 s of the race scene's load (the first race and each
Next Race, measured unthrottled). `team_group_hook` gives the row as the
humans on red (an AI of team 0 whose kart has VehicleBase+0x99 0); +0x20 is
left as it is (AIBattleManager::init takes it).

Race page (RacePage::initControl picks the set-up by play mode and rule mode;
play mode 0 has none for VS, so the page had no HUD controls and the race
crashed):
- play mode 0 (and 4, replay) with rule mode 2 runs initControl_MultiVS
  (`race_hook`): VS results (genResult, genResultTeam with teams), pause menu,
  Next / Change Course buttons (IsLastRace: MenuData+0x66C races).
- initControl_MultiVS ends in a tail call (0x004D7C2C) that fills an object at
  page+0x394 from the network player data (Net::NetworkPlayerDataManager,
  NetworkStationBufferManager); in play mode 0 it returns instead (`vs_tail_hook`).

After a race (VS is 4 races, MenuData+0x66C): BaseRacePage::complete adds the
race's points and loads the next course for its own codes, but for the VS ones
(0x12 Next, 0x13 Change Course, 0x15 Trophy) it does nothing, as local
multiplayer does that through network tasks. In play mode 0 they get the cases
of a battle (`complete_hook`): Next applyPoint + loadNextCourse, the others
applyPoint. The flows:

    Next (courses Random, In order): MultiVS_Next -> Page_MMenCheck -> RaceScene again (no
        MenuNetworkSelectMenuTask, Task_CourseDecide, Page_RaceCourseDL)
    Next (courses Choose): MultiVS_Course -> ClearRaceInfoTask MultiVS_Course -> MenuScene
        SingleTA_Course -> Seq_Single TA_ChangeCourse -> Page_SingleCup (instead of Seq_Multi)
    Quit, and after the trophy: Title_Top instead of Multi_Top

TrophyPage::enter takes the enter codes MultiGP, MultiVS and MultiBT for
multiplayer (+0x3339), and then waits for NetworkEngine::isFinishSyncFinished
before it lets the scene go on; in play mode 0 the flag stays 0 (`trophy_hook`).

The flow of a scene is data, read from its `.bss` each time the scene starts
(scene-sequence-bseq Finding 7). A hook in Sequence::SequenceResource::create,
right after UI::LoadUI returned the file, rewrites flow entries of the files
it knows (BSEQ_PATCHES), by the root section ID at +0x04 of the file. A field
is written only while it still holds its original value.

The hooks and the BSEQ table are in two slots of the code pages that
`mk7 emu start` maps after the game's .bss (codepages.py): SOURCE at
VS_CODE, SOURCE_MENU at MENU_CODE.
"""
import struct

from . import codepages
from .codepages import assemble_source
from .menu import write_patches

NOP = 0xE320F000
# (address, original, patched)
CODE_PATCHES = (
    (0x004923D4, 0xE3A01001, 0xE3A01002),   # MenuSingle_Mode::buttonHandler_OK, button 1: `mov r1, #1` (TT) -> #2 (VS)
    # MenuSingle_Mode::onPageEnter: the description of the button under the cursor is message 0x898 + cursor, or
    # 0x89C (VS) for cursor 1 in local multiplayer (a NetworkEngine test); make that test pass
    (0x0049218C, 0x0A000003, 0xE3520001),   # beq (not multiplayer) -> cmp r2, #1
    (0x00492190, 0xE5D11503, 0x03A02004),   # ldrb r1, [r1, #0x503] -> moveq r2, #4
    (0x00492194, 0xE3510000, 0xEA000001),   # cmp r1, #0 -> b 0x004921A0
    (0x004924A8, 0xE3A07000, 0xE3A07001),   # MenuSingle_Mode::buttonHandler_SelectOn: multiplayer = 0 -> 1 (VS movie, text)
    (0x004AD318, 0xE5C46295, 0xE5C45295),   # MenuSingle_Setting(): strb r6 (1) -> strb r5 (0), [r4, #0x295]
    (0x004AC2AC, 0x0A000014, NOP),          # MenuSingle_Setting::onPageEnter: beq (not battle) -> CPUs for VS too
    (0x00473324, 0xEB0186F5, NOP),          # BaseMenuPage::applySetting_Battle: bl BasePage::setMirror(false)
    (0x0047333C, 0xEB018453, NOP),          # BaseMenuPage::applySetting_Battle: bl BasePage::setCC(50cc)
    # MenuSingle_Setting::onPageComplete, the loop over the karts r4 = 0..7 that starts the run: `mov r1, #0`
    # before setRaceRank, setTotalRank and setUniqTotalRank
    (0x004AC928, 0xE3A01000, 0xE2641008),   # race rank: rsb r1, r4, #8 (the player 8th, the CPUs 7th to 1st)
    (0x004AC934, 0xE3A01000, 0xE3A01001),   # total rank: 1
    (0x004AC940, 0xE3A01000, 0xE2641008),   # unique total rank: as the race rank
    # ExecutableSectionClassInfo<MenuSingle_Cup>::constructSection: operator new(0x314) -> 0x320 (cup_ctor_hook)
    (0x005D9B40, 0xE3A00FC5, 0xE3A00FC8),
)

MENU_SCENE = 1530824276     # root section ID of MenuScene-Default.bss (`MenuScene`)
RACE_SCENE = 1534509281     # RaceScene-Default.bss (`RaceScene`)
ROOT = 350570726            # Root-Default.brs (its root sequence)
# (root section ID, file offset, original u16, patched u16, what). Flow entries are s16 source child, u16 source
# return code, s16 destination child (-1: the sequence itself), u16 destination code (its enter code, or the
# sequence's return code); child indices and codes as in the file (`bseq_flow_graph.py`).
BSEQ_PATCHES = (
    (MENU_SCENE, 0x223E, 2, 3, "Seq_Single: Page_SingleMode Next01 -> MenuModeSetterTask[5] TimeTrial -> Versus"),
    (MENU_SCENE, 0x22DC, 11, 17, "Seq_Single: Page_SingleKart[15] Next00 -> Page_SingleCup[11] -> Page_SingleSetting[17]"),
    (MENU_SCENE, 0x2304, 12, 11, "Seq_Single: Page_SingleSetting Next00 -> Page_SingleCourseBattle[12] -> Page_SingleCup[11]"),
    (MENU_SCENE, 0x2314, 19, 15, "Seq_Single: Page_SingleSetting Back -> Page_SingleKart[19] -> [15]"),
    (MENU_SCENE, 0x229C, 15, 17, "Seq_Single: Page_SingleCup Back -> Page_SingleKart[15] -> Page_SingleSetting[17]"),
    (MENU_SCENE, 0x21AC, 0xBE4A, 0xC024, "Seq_Single: child 16 Para_TAChart (0x5B1EBE4A) -> Seq_TAChart (0x5B1EC024)"),
    (MENU_SCENE, 0x22EC, 20, 0xFFFF, "Seq_Single: Para_TAChart Next00 -> Page_SingleGhostLoad[20] -> exit"),
    (MENU_SCENE, 0x22EE, 1, 6, "Seq_Single: [16] Next00 -> TimeAttack (GhostLoad's) -> Battle"),
    (MENU_SCENE, 0x2678, 1, 0xFFFF, "Seq_TAChart: Page_SingleCourse Next00 -> Page_SingleGhost[1] -> exit Next00"),
    (MENU_SCENE, 0x2226, 2, 3, "Seq_Single: TA_ChangeCourse's MenuModeSetterTask[6] TimeTrial -> Versus"),
    (RACE_SCENE, 0x43C, 4, 1, "Seq_Race: Page_Race MultiVS_Next -> MenuNetworkSelectMenuTask[4] -> Page_MMenCheck[1]"),
    (RACE_SCENE, 0x43E, 6, 20, "Seq_Race: Page_Race MultiVS_Next -> Multi_Course -> Enter19 (Return19: MultiVS_Next)"),
    (ROOT, 0x5E6, 7, 2, "ProductMain: ClearRaceInfoTask MultiVS_Course -> MenuScene MultiVS_Course -> SingleTA_Course"),
    (ROOT, 0x726, 17, 7, "ProductMain: RaceScene MultiVS_Exit -> ClearRaceInfoTask Multi_Top -> Title_Top"),
    (ROOT, 0x7C6, 17, 7, "ProductMain: TrophyScene MultiVS -> ClearRaceInfoTask Multi_Top -> Title_Top"),
    (MENU_SCENE, 0x22A8, 12, 11, "Seq_Single: Page_SingleCourseBattle[12] Next01 -> exit: from Page_SingleCup[11]"
     " (Yes to quit after a race)"),
    (MENU_SCENE, 0x22AE, 7, 9, "Seq_Single: [11] Next01 -> exit Back -> SDError (the menu scene is loaded again,"
     " at the title)"),
)

# Sequence::SequenceResource::create: `str r0, [r4]` stores the file UI::LoadUI returned
BSEQ_SITE, BSEQ_ORIG = 0x0049FE4C, 0xE5840000
# MenuSingle_Mode::initControl: `add sp, sp, #0xCC` before its final pop
MODE_SITE, MODE_ORIG = 0x00492110, 0xE28DD0CC
MENU_SINGLE_MODE_VTABLE = 0x00647590
# MenuSingle_Course::onPageComplete: `bne` (not Back) to its final `pop {r4, pc}`
COURSE_SITE, COURSE_ORIG = 0x004A7128, 0x1A00000C
APPLY_SETTING_BATTLE = 0x00473310
# RacePage::initControl, play mode 0 or 4: `bne` (rule mode not 3) to its final `pop {r4, pc}`
RACE_SITE, RACE_ORIG = 0x004D93E8, 0x1AFFFFF7
INIT_CONTROL_MULTI_VS = 0x004D9758
# RacePage::initControl_MultiVS: its final tail call `b 0x004D7C2C`
VS_TAIL_SITE, VS_TAIL_ORIG = 0x004D98DC, 0xEAFFF8D2
MULTI_RACE_TAIL = 0x004D7C2C
# BaseRacePage::complete: its jump table by page return code (0x0047CF28 + 4 * code)
COMPLETE_TABLE = 0x0047CF28
COMPLETE_NEXT, COMPLETE_COURSE, COMPLETE_TROPHY = 0x12, 0x13, 0x15   # MultiVS_Next, _Course, _Trophy
COMPLETE_BREAK, COMPLETE_DEFAULT = 0x0047D124, 0x0047D01C            # their cases: nothing
COMPLETE_POINTS, COMPLETE_POINTS_NEXT = 0x0047D024, 0x0047D038      # applyPoint; applyPoint + loadNextCourse(true)
# TrophyPage::enter: `mov r0, #1` (a multiplayer enter code), then back to the store of +0x3339 at 0x004715A4
TROPHY_SITE, TROPHY_ORIG, TROPHY_RET = 0x0047169C, 0xE3A00001, 0x004715A4
# Menu3D::GarageDirector::onUpdateState_: `ldrb r1, [r0, #0x63]` (m_scene)
GARAGE_SITE, GARAGE_ORIG = 0x003FF458, 0xE5D01063
# MenuSingle_Course constructor (0x004A7524): `strb r5, [r4, #0x2BC]` (r5 = 0)
COURSE_CTOR_SITE, COURSE_CTOR_ORIG = 0x004A7584, 0xE5C452BC
COURSE_BUTTON_SLOT = 0x00648E98     # MenuSingle_Course vtable (0x00648D98) +0x100: buttonHandler_OK(int)
COURSE_BASE_BUTTON_OK = 0x004C223C  # MenuSingle_CourseBase::buttonHandler_OK
# ExecutableSectionClassInfo<MenuSingle_Cup>::constructSection: `strb r1, [r0, #0x2BC]` (r1 = 1)
CUP_CTOR_SITE, CUP_CTOR_ORIG = 0x005D9B60, 0xE5C012BC
# MenuSingle_CupBase::initControl: `str r0, [r1, #0x230]` right after setupControl<UI::BackButton>
CUP_BACK_SITE, CUP_BACK_ORIG = 0x004AAF24, 0xE5810230
MENU_SINGLE_CUP_VTABLE = 0x00646764
CUP_ENTER_SLOT, CUP_ENTER = 0x00646818, 0x0048690C        # +0xB4 onPageEnter: MenuSingle_Cup's
CUP_PRESTEP_SLOT, CUP_PRESTEP = 0x00646810, 0x004AB104    # +0xAC onPagePreStep: MenuSingle_CupBase's
CUP_BUTTON_SLOT, CUP_BUTTON_OK = 0x00646864, 0x004AB250   # +0x100 buttonHandler_OK(int): MenuSingle_CupBase's
# Enemy::AIRankManager::decideAllGroupTeamMode_: `ldm ip, {r0, r9}` (AIManager+0x1C, +0x20), the group table's indices
TEAM_GROUP_SITE, TEAM_GROUP_ORIG = 0x003367D0, 0xE89C0201
# MenuSingle_Setting::onPageComplete, a run starts: the first of two nops after BasePage::initRaceNo
CPU_OFF_SITE = 0x004AC90C
# Field::FieldDirector::calcStartTag: `cmp r0, #1` (rule mode time trial) before the race grid
GRID_SITE, GRID_ORIG = 0x0035540C, 0xE3500001
VS_CODE = codepages.VS_CODE[0]         # the hooks of SOURCE and the BSEQ table
MENU_CODE = codepages.VS_MENU_CODE[0]  # SOURCE_MENU

SOURCE = r"""
    .arm
    .syntax unified
    .global bseq_hook, mode_hook, course_hook, race_hook, vs_tail_hook, complete_hook, trophy_hook
    .text
@ After UI::LoadUI: r0 the BSEQ file, r4 the SequenceResource. r1-r3, r5-r7, ip and lr are free here (reloaded
@ or unused before the function returns).
bseq_hook:
    str     r0, [r4]
    cmp     r0, #0
    beq     2f
    ldr     r1, [r0, #4]            @ root section ID
    adr     r2, table
1:  ldr     r3, [r2], #4            @ entry: root ID (0 ends the table), offset, original, patched
    cmp     r3, #0
    beq     2f
    ldrh    r5, [r2], #2
    ldrh    r6, [r2], #2
    ldrh    r7, [r2], #4
    cmp     r3, r1
    bne     1b
    ldrh    r3, [r0, r5]
    cmp     r3, r6
    strheq  r7, [r0, r5]
    b       1b
2:  b       {RET:#x}

@ End of MenuSingle_Mode::initControl: r4 the page, sp its 0xCC bytes of locals (no longer used); r0-r3, r5-r11,
@ ip and lr are restored by the pop or free.
mode_hook:
    ldr     r0, [r4]
    ldr     r1, ={VTABLE:#x}
    cmp     r0, r1                  @ MenuSingle_Mode itself, not MenuMulti_Mode (which calls this initControl)
    bne     9f
    ldr     r0, [r4, #0x2C8]        @ m_menu_buttons
    ldr     r6, [r0, #4]            @ button 1
    ldr     r5, [r6, #0x68]         @ its control sight
    ldr     r0, =0x006287B0         @ a sead::SafeString: vtable, then "T_menu" (MenuMulti_Mode::initControl's)
    ldr     r1, =0x00485A8C
    str     r0, [sp, #8]
    str     r1, [sp, #0xC]
    add     r0, sp, #4
    add     r1, r6, #0x6C
    ldr     r2, =0x89C              @ "VS"
    bl      0x004E591C              @ UI::MessageDataList::getMessage(out, list, id)
    ldr     r0, [r5]
    add     r1, sp, #8
    mov     r2, #1
    ldr     r3, [r0, #0x18]
    mov     r0, r5
    blx     r3                      @ the pane named T_menu
    mov     r1, r0
    mov     r0, #0
    str     r0, [sp]
    ldr     r2, [r5]
    ldr     ip, [r2, #0x70]
    mov     r0, r5
    add     r2, sp, #4
    mov     r3, #0
    blx     ip                      @ its text
    mov     r0, r6
    mov     r1, #8
    mov     r2, #2
    bl      0x001731E8              @ UI::BaseMenuButtonControl::setTex(8, 2): the VS icon
    mov     r0, r6
    ldr     r1, [r4, #0x2DC]
    ldr     r2, =0x8A6
    bl      0x00170A7C              @ UI::BaseMenuButtonControl::setCaption(m_caption, 0x8A6)
    mov     r7, #2
3:  ldr     r0, [r4, #0x2C8]
    ldr     r6, [r0, r7, lsl #2]    @ buttons 2 and 3
    mvn     r0, #0
    str     r0, [r6, #0x230]        @ m_return_code -1: a press does nothing
    mov     r0, #0
    strb    r0, [r6, #0x144]        @ its UI::CursorItem (+0x130) disabled (+0x14)
    ldr     r0, [r6, #0x68]
    ldr     r2, [r0]
    mov     r1, #0
    ldr     r2, [r2, #0xA0]
    blx     r2                      @ control sight: root pane hidden
    add     r7, r7, #1
    cmp     r7, #4
    blo     3b
9:  add     sp, sp, #0xCC
    b       {MODE_RET:#x}

@ MenuSingle_Course::onPageComplete, a course chosen (not Back): its own return, then the course of the race
course_hook:
    pop     {{r4, lr}}
    b       {APPLY:#x}              @ BaseMenuPage::applySetting_Battle()

@ RacePage::initControl, play mode 0 or 4, rule mode in r0 not 3 (battle); {{r4, lr}} pushed, r4 the page
race_hook:
    cmp     r0, #2
    popne   {{r4, pc}}
    mov     r0, r4
    pop     {{r4, lr}}
    b       {MULTI_VS:#x}           @ RacePage::initControl_MultiVS()

@ end of RacePage::initControl_MultiVS, r0 the page: the multiplayer tail only outside play mode 0
vs_tail_hook:
    ldr     r1, [r0, #0x26C]        @ BaseRacePage: play mode
    cmp     r1, #0
    bxeq    lr
    b       {MULTI_TAIL:#x}

@ BaseRacePage::complete, r0 its return code 0x12, 0x13 or 0x15, r4 the page
complete_hook:
    ldr     r1, [r4, #0x26C]        @ play mode
    cmp     r1, #0
    bne     1f
    cmp     r0, #{NEXT:#x}
    beq     {POINTS_NEXT:#x}
    b       {POINTS:#x}
1:  cmp     r0, #{NEXT:#x}
    beq     {BREAK:#x}
    b       {DEFAULT:#x}

@ TrophyPage::enter, a multiplayer enter code; r5 the page: multiplayer only outside play mode 0
trophy_hook:
    ldr     r0, [r5, #0x26C]        @ play mode (BaseRacePage)
    cmp     r0, #0
    movne   r0, #1
    b       {TROPHY_RET:#x}

    .ltorg
    .balign 4
table:
{TABLE}
    .word   0
"""


# The menu hooks (garage, course page, cup page, CPU off), the start of a race alone and the CPU groups of team
# races, at MENU_CODE
SOURCE_MENU = r"""
    .arm
    .syntax unified
    .global garage_hook, course_ctor_hook, course_button_hook
    .global cup_ctor_hook, cup_back_hook, cup_enter_hook, cup_button_hook, cup_prestep_hook, team_group_hook
    .global cpu_off_hook, grid_hook
    .text
@ GarageDirector::onUpdateState_, r0 the director: r1 the scene its states are picked by; ip is free
garage_hook:
    ldrb    r1, [r0, #0x63]         @ m_scene
    cmp     r1, #0                  @ single player
    bne     1f
    ldrb    ip, [r0, #0x64]         @ m_mode
    cmp     ip, #2                  @ VS
    bne     1f
    ldrb    ip, [r0, #0x66]         @ m_curr_state: driver, kart, rules, cup, course as in multiplayer VS
    cmp     ip, #5
    cmpne   ip, #6
    cmpne   ip, #7
    cmpne   ip, #0xB
    cmpne   ip, #0xC
    moveq   r1, #1
1:  b       {GARAGE_RET:#x}

@ the GarageDirector in r0 (as the menu pages find it); ip is used
garage:
    ldr     r0, =0x006789B8
    ldr     r0, [r0, #4]
    ldr     r0, [r0, #4]
    ldrb    ip, [r0, #0x1E8]
    cmp     ip, #0
    ldrne   r0, [r0, #0x1E4]
    ldrne   ip, =0x75F1B26B
    eorne   r0, r0, ip
    ldr     r0, [r0, #0x1C]
    ldr     r0, [r0, #0x48]
    bx      lr

@ MenuSingle_Course constructor (bl from it; it returns with pop): +0x2BC 1, the page has a start dialog. r1 is
@ loaded again after it.
course_ctor_hook:
    mov     r1, #1
    strb    r1, [r4, #0x2BC]
    bx      lr

@ MenuSingle_Course::buttonHandler_OK(page, option), as MenuMulti_Course's: the garage state of the options
@ (0-3 a course, 4 the start dialog's OK, 5 Back)
course_button_hook:
    push    {{r4, r5, r6, lr}}
    mov     r4, r0
    mov     r5, r1
    cmp     r5, #5
    bne     1f
    ldr     r0, [r4, #0x4C]
    ldr     r1, [r4, #0x5C]
    cmp     r0, r1                  @ Back to the cup page: the base's (it fades the garage)
    beq     3f
    mov     r1, #0xC                @ Back closed the start dialog: the course state again
    mov     r6, #0
    b       2f
1:  bl      {COURSE_BUTTON_OK:#x}   @ MenuSingle_CourseBase::buttonHandler_OK: options 0-3 set the course
    mov     r6, #1
    cmp     r5, #4
    movlt   r1, #0xF                @ a course: OK
    moveq   r1, #0x10               @ the start dialog's OK: the end
    popgt   {{r4, r5, r6, pc}}
2:  bl      garage
    mov     r2, r6
    bl      0x00400774              @ Menu3D::GarageDirector::requestChangeState(state, bool)
    pop     {{r4, r5, r6, pc}}
3:  mov     r0, r4
    mov     r1, r5
    pop     {{r4, r5, r6, lr}}
    b       {COURSE_BUTTON_OK:#x}

@ MenuSingle_Cup constructSection (bl from it; it returns with pop): +0x2BC as before, the added fields 0
cup_ctor_hook:
    strb    r1, [r0, #0x2BC]
    mov     r2, #0
    str     r2, [r0, #0x314]
    str     r2, [r0, #0x318]
    bx      lr

@ MenuSingle_CupBase::initControl (bl from it), r1 the Back button, r4 the page; r2 and r3 are free
cup_back_hook:
    str     r0, [r1, #0x230]
    ldr     r2, [r4]
    ldr     r3, ={CUP_VTABLE:#x}
    cmp     r2, r3
    streq   r1, [r4, #0x314]
    bx      lr

@ MenuSingle_Cup::onPageEnter: after a race, Back asks
cup_enter_hook:
    push    {{r4, lr}}
    mov     r4, r0
    bl      {CUP_ENTER:#x}
    mov     r0, #0
    strb    r0, [r4, #0x318]        @ Back asks
    strb    r0, [r4, #0x319]        @ the dialog is open
    ldr     r1, [r4, #0x314]
    cmp     r1, #0
    popeq   {{r4, pc}}
    ldr     r0, [r4, #0x5C]
    str     r0, [r1, #0x230]        @ Back: the page's back code
    bl      0x004DD42C              @ Sequence::GetRaceNo(): -1 before the first race
    cmp     r0, #0
    poplt   {{r4, pc}}
    ldr     r1, [r4, #0x314]
    mvn     r0, #3
    str     r0, [r1, #0x230]        @ -4: nothing, the handler gets the option
    mov     r0, #8
    str     r0, [r1, #0x210]
    mov     r0, #1
    strb    r0, [r4, #0x318]
    pop     {{r4, pc}}

@ MenuSingle_Cup::buttonHandler_OK(page, option)
cup_button_hook:
    cmp     r1, #8
    bne     {CUP_BUTTON_OK:#x}
    ldrb    r2, [r0, #0x318]
    cmp     r2, #0
    beq     {CUP_BUTTON_OK:#x}
    mov     r2, #1
    strb    r2, [r0, #0x319]
    push    {{r4, lr}}
    mov     r0, #1
    ldr     r1, =0x2397             @ "Are you sure you want to quit?" (the race page's quit)
    mov     r2, #0
    bl      0x0046FB70              @ Sequence::OpenDialog(1, message, nullptr)
    mov     r0, #0x10
    bl      0x004CE7F0              @ Sequence::SetDialogOKSound_YesButton
    pop     {{r4, lr}}
    mov     r0, #0x11
    b       0x004CE120              @ Sequence::SetDialogOKSound_NoButton

@ MenuSingle_Cup::onPagePreStep: Yes completes the page with Next01
cup_prestep_hook:
    push    {{r4, lr}}
    mov     r4, r0
    bl      {CUP_PRESTEP:#x}
    ldrb    r0, [r4, #0x14]         @ running
    cmp     r0, #5
    ldrbeq  r0, [r4, #0x319]
    cmpeq   r0, #1
    popne   {{r4, pc}}
    bl      0x00482630              @ Sequence::IsCloseDialog()
    cmp     r0, #0
    popeq   {{r4, pc}}
    mov     r0, #0
    strb    r0, [r4, #0x319]
    bl      0x00471DFC              @ Sequence::IsDialogYes()
    cmp     r0, #0
    popeq   {{r4, pc}}
    mov     r0, #0                  @ fade out as the battle course page's Yes does (onPageComplete, Next01)
    mov     r1, #0x1E
    mov     r2, #2
    bl      0x00480888              @ Sequence::StartFadeout(0, 30, 2): the page finishes once it is over
    mov     r0, #0
    mov     r1, #0x1E
    mov     r2, #2
    bl      0x00484688              @ Sequence::ReserveFadein(0, 30, 2)
    ldr     r0, =0x006789B8
    ldr     r0, [r0, #0x10]
    add     r0, r0, #0x1E0
    ldrsb   r1, [r0, #0x50]
    cmp     r1, #0
    ldrne   r0, [r0, #0x4C]
    ldrne   r1, =0x75F1B26B
    eorne   r0, r0, r1
    ldr     r0, [r0, #0x84]
    ldr     r0, [r0, #4]            @ the scene's Sound::SndSceneBase
    cmp     r0, #0
    movne   r1, #0x1E
    blne    0x003CFE90              @ Sound::SndSceneBase::stopSceneBgm(30)
    ldr     r0, [r4]
    ldr     r2, [r0, #0xDC]         @ Page::completePage(1): Next01
    mov     r0, r4
    mov     r1, #1
    pop     {{r4, lr}}
    bx      r2

@ MenuSingle_Setting::onPageComplete, a run starts (bl from a nop after initRaceNo), r5 the page: with the CPU
@ setting off, every kart but the player's is cleared (an empty CKartInfo), as for a time trial
cpu_off_hook:
    push    {{r4, lr}}
    mov     r0, r5
    bl      0x004ACC68              @ MenuSingle_Setting::isCOM(): the CPU control's value is not 0
    cmp     r0, #0
    popne   {{r4, pc}}
    bl      0x00471CC0              @ Sequence::GetRaceInfo(): the menu's
    add     r0, r0, #0x100
    ldrsh   r0, [r0, #0x84]         @ m_detail_kart_id: the player's kart
    pop     {{r4, lr}}
    b       0x004D2AB0              @ BasePage::clearEnemy(player)

@ Field::FieldDirector::calcStartTag, a race: `cmp r0, #1` (r0 the rule mode, r6 the race info), then `beq` to the
@ time trial's start (every slot on the one centered start); one kart takes it too
grid_hook:
    cmp     r0, #1                  @ time trial
    ldrne   r0, [r6, #0x180]        @ m_kart_num
    cmpne   r0, #1
    b       {GRID_RET:#x}

@ Enemy::AIRankManager::decideAllGroupTeamMode_, `ldm ip, {{r0, r9}}` with ip = AIManager+0x1C: r0 the human karts
@ (the group table), r9 its row, the humans on red; +0x20 is every kart on red. r6-r8 and ip are free (set after).
team_group_hook:
    ldr     r0, [ip]                @ m_player_kart_num
    sub     r6, ip, #0x1C           @ the AIManager
    ldr     r7, [r6, #0x18]         @ m_kart_num
    mov     r9, #0
1:  subs    r7, r7, #1
    blt     2f
    add     r8, r6, r7, lsl #2
    ldr     r8, [r8, #0x38]         @ m_ais[i]
    ldr     ip, [r8, #0xC]          @ its team (0 red)
    cmp     ip, #0
    bne     1b
    ldr     r8, [r8]
    ldr     r8, [r8]                @ its kart
    ldrsb   ip, [r8, #0x99]         @ 0: a human's
    cmp     ip, #0
    addeq   r9, r9, #1
    b       1b
2:  b       {TEAM_GROUP_RET:#x}
    .ltorg
"""


def assemble() -> tuple[bytes, bytes, dict[str, int]]:
    """The machine code of SOURCE (at VS_CODE) and of SOURCE_MENU (at
    MENU_CODE), and the addresses of their hooks."""
    table = "\n".join(f"    .word   {root:#x}\n    .hword  {off:#x}, {orig:#x}, {new:#x}, 0"
                      for root, off, orig, new, _ in BSEQ_PATCHES)
    src = SOURCE.format(RET=BSEQ_SITE + 4, MODE_RET=MODE_SITE + 4, VTABLE=MENU_SINGLE_MODE_VTABLE,
                        APPLY=APPLY_SETTING_BATTLE, MULTI_VS=INIT_CONTROL_MULTI_VS, MULTI_TAIL=MULTI_RACE_TAIL,
                        NEXT=COMPLETE_NEXT, POINTS_NEXT=COMPLETE_POINTS_NEXT, POINTS=COMPLETE_POINTS,
                        BREAK=COMPLETE_BREAK, DEFAULT=COMPLETE_DEFAULT, TROPHY_RET=TROPHY_RET, TABLE=table)
    code, entries = assemble_source(src, VS_CODE, ("bseq_hook", "mode_hook", "course_hook", "race_hook",
                                                   "vs_tail_hook", "complete_hook", "trophy_hook"))
    codepages.check_fits(codepages.VS_CODE, code, "the VS code")
    src = SOURCE_MENU.format(GARAGE_RET=GARAGE_SITE + 4, COURSE_BUTTON_OK=COURSE_BASE_BUTTON_OK,
                             CUP_VTABLE=MENU_SINGLE_CUP_VTABLE, CUP_ENTER=CUP_ENTER, CUP_PRESTEP=CUP_PRESTEP,
                             CUP_BUTTON_OK=CUP_BUTTON_OK, TEAM_GROUP_RET=TEAM_GROUP_SITE + 4, GRID_RET=GRID_SITE + 4)
    menu_code, menu_entries = assemble_source(src, MENU_CODE, (
        "garage_hook", "course_ctor_hook", "course_button_hook", "cup_ctor_hook", "cup_back_hook",
        "cup_enter_hook", "cup_button_hook", "cup_prestep_hook", "team_group_hook", "cpu_off_hook", "grid_hook"))
    codepages.check_fits(codepages.VS_MENU_CODE, menu_code, "the VS menu code")
    return code, menu_code, entries | menu_entries


def _branch(site: int, target: int, cond=0xE, link=False) -> int:
    """`b target` (`bl` with link) at `site`, with an ARM condition (0xE always, 0x1 ne)."""
    return cond << 28 | (0x0B000000 if link else 0x0A000000) | (((target - (site + 8)) >> 2) & 0xFFFFFF)


def write_vs(g, on=True):
    """Write the VS patches (or restore the code, on=False) through `g` (a
    GdbClient at the game's first instruction, or an RpcClient). Flows of a
    scene already loaded keep what they had: only files loaded later change."""
    code, menu_code, entries = assemble()
    write_patches(g, CODE_PATCHES, on)
    if on:
        g.write(VS_CODE, code)
        g.write(MENU_CODE, menu_code)
    write_patches(g, _hook_patches(entries), on)


def _hook_patches(entries) -> tuple:
    return ((BSEQ_SITE, BSEQ_ORIG, _branch(BSEQ_SITE, entries["bseq_hook"])),
            (MODE_SITE, MODE_ORIG, _branch(MODE_SITE, entries["mode_hook"])),
            (COURSE_SITE, COURSE_ORIG, _branch(COURSE_SITE, entries["course_hook"], cond=0x1)),
            (RACE_SITE, RACE_ORIG, _branch(RACE_SITE, entries["race_hook"], cond=0x1)),
            (VS_TAIL_SITE, VS_TAIL_ORIG, _branch(VS_TAIL_SITE, entries["vs_tail_hook"])),
            (COMPLETE_TABLE + 4 * COMPLETE_NEXT, COMPLETE_BREAK, entries["complete_hook"]),
            (COMPLETE_TABLE + 4 * COMPLETE_COURSE, COMPLETE_DEFAULT, entries["complete_hook"]),
            (COMPLETE_TABLE + 4 * COMPLETE_TROPHY, COMPLETE_DEFAULT, entries["complete_hook"]),
            (TROPHY_SITE, TROPHY_ORIG, _branch(TROPHY_SITE, entries["trophy_hook"])),
            (GARAGE_SITE, GARAGE_ORIG, _branch(GARAGE_SITE, entries["garage_hook"])),
            (COURSE_CTOR_SITE, COURSE_CTOR_ORIG, _branch(COURSE_CTOR_SITE, entries["course_ctor_hook"], link=True)),
            (COURSE_BUTTON_SLOT, COURSE_BASE_BUTTON_OK, entries["course_button_hook"]),
            (CUP_CTOR_SITE, CUP_CTOR_ORIG, _branch(CUP_CTOR_SITE, entries["cup_ctor_hook"], link=True)),
            (CUP_BACK_SITE, CUP_BACK_ORIG, _branch(CUP_BACK_SITE, entries["cup_back_hook"], link=True)),
            (CUP_ENTER_SLOT, CUP_ENTER, entries["cup_enter_hook"]),
            (CUP_PRESTEP_SLOT, CUP_PRESTEP, entries["cup_prestep_hook"]),
            (CUP_BUTTON_SLOT, CUP_BUTTON_OK, entries["cup_button_hook"]),
            (TEAM_GROUP_SITE, TEAM_GROUP_ORIG, _branch(TEAM_GROUP_SITE, entries["team_group_hook"])),
            (CPU_OFF_SITE, NOP, _branch(CPU_OFF_SITE, entries["cpu_off_hook"], link=True)),
            (GRID_SITE, GRID_ORIG, _branch(GRID_SITE, entries["grid_hook"])))


def vs_on(mem) -> bool:
    return mem.u32(BSEQ_SITE) == _branch(BSEQ_SITE, VS_CODE) and all(
        mem.u32(addr) == patched for addr, _, patched in CODE_PATCHES)


def check_bseq_patches(directory) -> list[str]:
    """Compare the original values of BSEQ_PATCHES with the unpacked files
    (mk7-llm-research/local/romfs/eur2/rom/UI/common.szs.d); returns the mismatches."""
    from pathlib import Path
    files = {}
    for p in Path(directory).iterdir():
        if p.is_file():
            d = p.read_bytes()
            if d[:4] == b"BSEQ":
                files[struct.unpack_from("<I", d, 4)[0]] = d
    bad = []
    for root, off, orig, _, what in BSEQ_PATCHES:
        d = files.get(root)
        cur = struct.unpack_from("<H", d, off)[0] if d else None
        if cur != orig:
            bad.append(f"{what}: {off:#x} holds {cur}, not {orig}")
    return bad
