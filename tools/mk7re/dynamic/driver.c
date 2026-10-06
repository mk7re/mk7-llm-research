/* The simulated player: drives the local player's kart from inside the game
 * (eur2). Compiled by driver.py with devkitARM's gcc into the code pages
 * (codepages.py: DRIVER_CODE, control block DRIVER_CTRL, working memory
 * DRIVER_RAM); driver.py explains how it is hooked in and driven.
 *
 * drive_frame runs once per frame for every KDPadInputer, right after
 * KDPadInputer::calcInput has filled the pad's KDPadDataOnFrame from the
 * console pad. While a mode is on and the race runs, it replaces that data
 * with its own buttons and stick, in the format a human's input has there
 * (game button bits, stick in steps 0..14 with 7 the centre), so the kart,
 * the ghost recorder and the replay see a human's input. Menus read the
 * console pad and the UI pads, never this data.
 *
 * Everything is decided here, every frame: the route search, following it,
 * re-routes, back-ups, drifts and tricks. The behaviour follows the CPUs'
 * as the research on enemy AI behaviour and enemy points describes it, with
 * inputs a human could give instead of the AI's own steering.
 *
 * No globals: the state lives in the control block, which the host reads and
 * writes through RPC, and in the working memory.
 */
typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;
typedef float f32;

#define U32(a) (*(volatile u32 *)(a))
#define S32(a) (*(volatile s32 *)(a))
#define U16(a) (*(volatile u16 *)(a))
#define S16(a) (*(volatile s16 *)(a))
#define U8(a) (*(volatile u8 *)(a))
#define F32(a) (*(volatile f32 *)(a))

#define ROOT_SYSTEM 0x006789B8u   /* System::RootSystem */
#define ENGINE_KEY 0x75F1B26Bu     /* System::EngineHolder::ENGINE_KEY */
#define DRIVE_PARAM 0x00665508u    /* the parameter block of VehicleMove::isMiniTurbo_OverLv1 / Lv2 */

/* RaceSys::ModeManagerBase::RaceState */
#define RACE_STATE_COUNTDOWN 1
#define RACE_STATE_RACE 2

/* KDPad::ButtonInputEnum, the bits of KDPadDataOnFrame::m_buttons */
#define BUTTON_A 0x1
#define BUTTON_B 0x2
#define BUTTON_R 0x20

/* VehicleMove::StatusFlags (+0xC30) */
#define VS_JUGEM (0x20 | 0x40)      /* jugem_recover, jugem_recover_ai_oob */
#define VS_WING 0x80                /* wing_open: gliding */
#define VS_GLIDER_PAD 0x100
#define VS_ACCIDENT 0x10000         /* accident_1 */
#define VS_KILLER 0x400000          /* Bullet Bill: the game drives the kart */
#define VS_HANG 0x800000            /* Lakitu holds the kart */

/* MapdataEnemyPointData flags (+0x13) */
#define PT_CORNERING 0x01
#define PT_HEIGHT_REROUTE 0x02
#define PT_PRECISE 0x04
#define PT_NO_TRICK 0x08
#define PT_HOLD_DRIFT 0x10
#define PT_JUMP 0x80                /* battle: hop at every trick chance */

#define POINTS_MAX 4096           /* route points the working memory holds */
#define ROUTE_STEPS_MAX 16        /* route points passed in one frame at most */
#define FILL_MIN 48               /* race mode: entries kept ahead of the kart */
#define LOST_WAIT 30              /* frames between two re-routes of a kart far from the route */
#define SEARCH_XZ_SQ 250000.0f    /* findNearEnemyPoint: within 500 units horizontally */
#define SEARCH_Y_DEFAULT 75.0f    /*   height limit of a point whose max search Y offset is negative */
#define SHORTCUT_PENALTY 1.0e6f   /* added to the length of a way through a mushroom shortcut */
#define INF 3.0e38f

enum { MODE_OFF, MODE_GOTO, MODE_ROUTE, MODE_RACE };
enum {
    ST_IDLE, ST_NO_RACE, ST_WAIT, ST_DRIVE, ST_TURN, ST_BRAKE, ST_BACKUP, ST_REACHED, ST_ENDED, ST_LAKITU,
    ST_KILLER, ST_DRIFT, ST_NO_WAY, ST_TOO_MANY, ST_NO_ROUTE
};
#define OPT_FORWARD_ONLY 0x1      /* route: only along the next links, as CPUs drive */
#define OPT_NO_DRIFT 0x2
#define OPT_NO_TRICK 0x4

/* the control block; offsets mirrored in driver.py */
struct DriveCtrl {
    u32 magic, version;         /* 0x00 */
    u32 mode;                   /* 0x08 MODE_*, set by the host */
    u32 status;                 /* 0x0C ST_*, written every frame */
    f32 target[3];              /* 0x10 goto, route */
    f32 radius;                 /* 0x1C reached when nearer than this (horizontally) */
    u32 options;                /* 0x20 OPT_* */
    u32 generation;             /* 0x24 the host adds 1 when it sets a mode: start it afresh */
    /* what the driver does, for the host */
    u32 frames;                 /* 0x28 frames driven since the mode was set */
    u32 vehicle;                /* 0x2C the kart driven */
    f32 pos[3];                 /* 0x30 */
    f32 dist;                   /* 0x3C horizontal distance to the target */
    f32 angle;                  /* 0x40 angle from the heading to the aim, radians, + right */
    f32 speed;                  /* 0x44 horizontal speed, units per frame */
    u32 buttons;                /* 0x48 the input given */
    f32 stick;                  /* 0x4C */
    u32 accessor;               /* 0x50 the route's MapdataEnemyPointAccessor */
    u32 point_count;            /* 0x54 its points */
    u32 route_count;            /* 0x58 entries of the route list */
    u32 route_pos;              /* 0x5C the entry the kart heads to */
    s32 target_point;           /* 0x60 its point index */
    s32 aim_point;              /* 0x64 the point aimed at */
    u32 reroutes;               /* 0x68 counts */
    u32 backups;                /* 0x6C */
    u32 drifts;                 /* 0x70 */
    u32 tricks;                 /* 0x74 */
    u32 advances;               /* 0x78 */
    u32 lakitus;                /* 0x7C */
    u32 plans;                  /* 0x80 route searches */
    /* the driver's own state */
    u32 seen_generation;        /* 0x84 */
    u32 race_state;             /* 0x88 last frame's */
    u32 is_battle;              /* 0x8C */
    u32 replan;                 /* 0x90 search (route) or start (race) the route before driving on */
    u32 slow_frames;            /* 0x94 AIStuck::m_slow_frames */
    u32 no_advance;             /* 0x98 AIStuck::m_no_advance_frames */
    u32 wall_frames;            /* 0x9C AIEngine::m_wall_frames */
    u32 backup_phase;           /* 0xA0 0 none, 1 reversing, 2 back toward the route */
    u32 backup_frames;          /* 0xA4 */
    u32 drift;                  /* 0xA8 1 while drifting */
    u32 drift_frames;           /* 0xAC */
    s32 drift_dir;              /* 0xB0 +1 right, -1 left */
    u32 drift_rest;             /* 0xB4 frames before the next drift may start */
    u32 pad1;                   /* 0xB8 */
    u32 hop_frames;             /* 0xBC frames since the last trick hop */
    u32 prev_buttons;           /* 0xC0 */
    u32 away;                   /* 0xC4 Lakitu or Bullet Bill had the kart: re-route when it is back */
    u32 rand;                   /* 0xC8 */
    s32 last_point;             /* 0xCC the point last reached */
    u32 lost_wait;              /* 0xD0 frames before the next re-route of a kart far from the route */
    u32 drift_chain;            /* 0xD4 the last drift ended charged in a corner that goes on: drift again */
    u32 pad0[10];               /* 0xD8 */
    /* tuning, written by driver.py */
    f32 full_steer_angle;       /* 0x100 angle that gives the full stick */
    f32 turn_angle;             /* 0x104 above it: brake, then turn in place */
    f32 slow_speed;             /* 0x108 below it the kart counts as stopped (turn in place, brake at the target) */
    f32 lookahead;              /* 0x10C aim at the route point this far ahead, measured along the route */
    f32 lookahead_speed;        /* 0x110   plus this many times the speed */
    f32 lost_dist;              /* 0x114 farther than this from the route: re-route */
    f32 corner_shift;           /* 0x118 share of the half-width a drifting kart cuts to the inside */
    f32 drift_gain;             /* 0x11C drifting: scale on the curvature the aim asks for (above 1 cuts tighter) */
    u32 slow_limit;             /* 0x120 AIStuck: back up above this many slow frames (a wall counts 3) */
    u32 reverse_frames;         /* 0x124 back-up: reverse this long (half in battle) */
    u32 reroute_frames;         /* 0x128 AIStuck: re-route after this many frames without reaching a point */
    u32 wall_reroute_frames;    /* 0x12C AIEngine: re-route after this many frames against a wall */
    f32 drift_start_dist;       /* 0x130 a drift starts this near its corner point */
    f32 corridor;               /* 0x134 share of the half-width the line to the aim may leave the route by */
    u32 start_frame;            /* 0x138 race mode: hold A from this countdown frame on (0: never) */
    f32 drift_behind;           /* 0x13C end a drift when the aim is this far inside the direction of travel */
    f32 brake_dist;             /* 0x140 corners within this distance along the route (+ brake_dist_speed x speed) */
    f32 brake_dist_speed;       /* 0x144 */
    f32 coast_turn;             /*   turning more than this: release A above coast_ratio of the top speed */
    f32 coast_ratio;            /* 0x14C */
    f32 brake_turn;             /*   turning more than this: brake above brake_ratio */
    f32 brake_ratio;            /* 0x154 */
    f32 corridor_slack;         /* units added to the corridor */
    f32 kart_room;              /* 0x15C share of the half-width the kart may be off its stretch before it aims at
                                   the next point only */
    f32 brake_angle;            /* 0x160 the aim this far off the direction of travel: brake above brake_ratio */
    f32 precise_corridor;       /* the corridor at points with flag 0x04 (no slack) */
    u32 chain_rest;             /* 0x168 frames between a drift ended charged and the next one in the same corner */
    f32 drift_room;             /* 0x16C drifting: hold the stick inward while the kart is farther out than this
                                   share of the half-width inside the route */
    f32 drift_bend;             /* 0x170 end a drift when the route bends less than this toward its side over */
    f32 drift_bend_dist;        /* 0x174   this many units ahead (+ 20 x speed) */
};

#define CTRL ((struct DriveCtrl *)DRIVE_CTRL)
#define RAM_DIST ((f32 *)DRIVE_RAM)                                   /* f32[POINTS_MAX] */
#define RAM_PREV ((s16 *)(DRIVE_RAM + 4 * POINTS_MAX))                /* s16[POINTS_MAX] */
#define RAM_HEAP ((u16 *)(DRIVE_RAM + 6 * POINTS_MAX))                /* u16[POINTS_MAX] */
#define RAM_HEAP_POS ((u16 *)(DRIVE_RAM + 8 * POINTS_MAX))            /* u16[POINTS_MAX] */
#define RAM_ROUTE ((u16 *)(DRIVE_RAM + 10 * POINTS_MAX))              /* u16[POINTS_MAX] */
#define RAM_SHORTCUT ((u8 *)(DRIVE_RAM + 12 * POINTS_MAX))            /* u8[256] by path index */
#define HEAP_NONE 0xFFFF
#define HEAP_DONE 0xFFFE

/* ---- small helpers ---------------------------------------------------------- */

static f32 absf(f32 x) { return x < 0 ? -x : x; }
static f32 clampf(f32 x, f32 lo, f32 hi) { return x < lo ? lo : x > hi ? hi : x; }
static f32 sqrtf_(f32 x) { return __builtin_sqrtf(x); }

static f32 atan2_approx(f32 y, f32 x)
{
    f32 ax = absf(x), ay = absf(y);
    f32 mx = ax > ay ? ax : ay, mn = ax > ay ? ay : ax;
    if (mx == 0.0f)
        return 0.0f;
    f32 a = mn / mx, s = a * a;
    f32 r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
    if (ay > ax)
        r = 1.57079637f - r;
    if (x < 0)
        r = 3.14159274f - r;
    return y < 0 ? -r : r;
}

static u32 rand_u32(u32 n)
{
    struct DriveCtrl *c = CTRL;
    c->rand = c->rand * 1103515245u + 12345u;
    return ((c->rand >> 16) * n) >> 16;            /* 0 .. n-1, without a division (n < 65536) */
}

/* ---- the game --------------------------------------------------------------- */

static u32 engine(u32 owner, u32 kind)
{
    u32 info = owner + 0x1E0 + 4 + 0xC * kind;     /* EngineHolder::EngineManager::SEngineInfo */
    return U8(info + 4) ? U32(info) ^ ENGINE_KEY : 0;
}

/* the director list of the race scene, 0 elsewhere */
static u32 director_list(void)
{
    u32 manager = U32(ROOT_SYSTEM + 0x4);          /* RootSystem::m_scene_manager */
    u32 scene = manager ? U32(manager + 0x4) : 0;  /* SceneManager::m_game_scene */
    u32 chara = scene ? engine(scene, 0) : 0;      /* CharacterEngine */
    return chara ? U32(chara + 0x1C) : 0;          /* CharacterEngine::m_director_list */
}

/* the vehicle whose VehicleControl::m_player_pad is `pad` */
static u32 find_vehicle(u32 dl, u32 pad)
{
    u32 kd = U32(dl + 0x10);                       /* SDirectorList::m_kart_director */
    if (!kd)
        return 0;
    s32 count = S32(kd + 0x28);                    /* Kart::Director::m_units (sead::Buffer) */
    u32 units = U32(kd + 0x2C);
    for (s32 i = 0; i < count && i < 8; i++) {
        u32 unit = U32(units + 4 * i);
        u32 v = unit ? U32(unit + 0x2C) : 0;       /* Kart::Unit::m_vehicle */
        if (v && U32(v + 0xE0) == pad)             /* VehicleControl::m_player_pad */
            return v;
    }
    return 0;
}

static u32 race_director(u32 dl) { return U32(dl + 0x1C); }   /* SDirectorList::m_race_director */

static u32 race_state(u32 dl)
{
    u32 rd = race_director(dl);
    u32 mm = rd ? U32(rd + 0x1BC) : 0;             /* RaceDirector::m_mode_manager */
    return mm ? U8(mm + 0x48) : 0xFF;              /* ModeManagerBase race state, current */
}

/* frames the race has been in its current state (ModeManagerBase +0x5C) */
static u32 race_state_frames(u32 dl)
{
    u32 rd = race_director(dl);
    u32 mm = rd ? U32(rd + 0x1BC) : 0;
    return mm ? U32(mm + 0x5C) : 0;
}

static u32 is_battle_race(u32 dl)
{
    u32 rd = race_director(dl);
    u32 rule = rd ? U32(rd + 0x2C + 0x168) : 0;    /* CRaceInfo::m_race_mode.m_rule_mode */
    return rule == 3 || rule == 7;                 /* Battle, DemoBattle */
}

/* The route: in a race the enemy points as re-sampled for races
 * (AIPathManager::m_race_point_accessor, embedded at +0x28), in a battle the
 * KMP's (Field::GetEnemyPointAccessor). */
static u32 route_accessor(u32 dl, u32 battle)
{
    if (!battle) {
        u32 kd = U32(dl + 0x10);
        u32 ai = kd ? U32(kd + 0x58) : 0;          /* Kart::Director: AIManager */
        u32 apm = ai ? U32(ai + 0x4) : 0;          /* AIManager::m_ai_path_manager */
        if (apm && S32(apm + 0x28 + 0xC) > 0)
            return apm + 0x28;
    }
    u32 fd = U32(dl + 0x14);                       /* SDirectorList::m_field_director */
    u32 info = fd ? U32(fd + 0x38) : 0;            /* FieldDirector::m_course_info */
    return info ? U32(info + 0x14) : 0;            /* CourseInfo::m_enemy_point_accessor */
}

/* Field::MapdataEnemyPoint of point `i`, and its MapdataEnemyPointData */
static u32 point_entry(u32 acc, u32 i) { return U32(U32(acc + 0x14) + 4 * i); }
static u32 point_data(u32 acc, u32 i) { return U32(point_entry(acc, i)); }
static const volatile f32 *point_pos(u32 acc, u32 i) { return (const volatile f32 *)point_data(acc, i); }
static u32 point_flags(u32 acc, s32 i) { return i < 0 ? 0 : U8(point_data(acc, i) + 0x13); }
static u32 point_drift(u32 acc, u32 i) { return U8(point_data(acc, i) + 0x12); }
static u32 point_mushroom(u32 acc, u32 i) { return U16(point_data(acc, i) + 0x10); }
static s32 point_path(u32 acc, u32 i) { return S32(point_entry(acc, i) + 0x20); }
static f32 point_corner(u32 acc, u32 i) { return F32(point_entry(acc, i) + 0x24); }

/* 1 when `j` is one of the next points of `i` */
static u32 is_next(u32 acc, u32 i, u32 j)
{
    u32 e = point_entry(acc, i);
    s32 count = S32(e + 0x14);
    u32 links = U32(e + 0xC);
    for (s32 k = 0; k < count && k < 16 && links; k++)
        if ((u32)S32(links + 4 * k) == j)
            return 1;
    return 0;
}

static f32 dist3(const volatile f32 *p, f32 x, f32 y, f32 z)
{
    f32 dx = p[0] - x, dy = p[1] - y, dz = p[2] - z;
    return sqrtf_(dx * dx + dy * dy + dz * dz);
}

static f32 dist_pp(const volatile f32 *a, const volatile f32 *b) { return dist3(a, b[0], b[1], b[2]); }

/* distance from (x, y, z) to the segment a-b */
static f32 dist_segment(const volatile f32 *a, const volatile f32 *b, f32 x, f32 y, f32 z)
{
    f32 ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
    f32 len2 = ux * ux + uy * uy + uz * uz;
    f32 s = len2 > 0 ? ((x - a[0]) * ux + (y - a[1]) * uy + (z - a[2]) * uz) / len2 : 0;
    s = clampf(s, 0, 1);
    f32 dx = a[0] + s * ux - x, dy = a[1] + s * uy - y, dz = a[2] + s * uz - z;
    return sqrtf_(dx * dx + dy * dy + dz * dz);
}

/* The point nearest (x, y, z), searched as AIPathManager::findNearEnemyPoint
 * does: within 500 units horizontally and the point's height limit (its
 * max search Y offset, +0x16: negative 75, 0 none, positive the value), the
 * nearest in 3D. With `strict` 0 and none passing, the nearest in 3D. */
static s32 nearest_point(u32 acc, u32 n, f32 x, f32 y, f32 z, u32 strict)
{
    s32 found = -1, any = -1;
    f32 best = INF, best_any = INF;
    for (u32 i = 0; i < n; i++) {
        u32 data = point_data(acc, i);
        const volatile f32 *p = (const volatile f32 *)data;
        f32 dx = p[0] - x, dy = p[1] - y, dz = p[2] - z;
        f32 d = dx * dx + dy * dy + dz * dz;
        if (d < best_any) {
            best_any = d;
            any = (s32)i;
        }
        if (dx * dx + dz * dz > SEARCH_XZ_SQ)
            continue;
        s32 limit = S16(data + 0x16);
        f32 ady = absf(dy);
        if ((limit < 0 && ady > SEARCH_Y_DEFAULT) || (limit > 0 && ady > (f32)limit))
            continue;
        if (d < best) {
            best = d;
            found = (s32)i;
        }
    }
    return found >= 0 || strict ? found : any;
}

/* ---- the route search --------------------------------------------------------- */

static void heap_swap(u16 *heap, u16 *where, u32 a, u32 b)
{
    u16 t = heap[a];
    heap[a] = heap[b];
    heap[b] = t;
    where[heap[a]] = a;
    where[heap[b]] = b;
}

static void heap_up(u16 *heap, u16 *where, const f32 *dist, u32 k)
{
    while (k > 0) {
        u32 parent = (k - 1) >> 1;
        if (dist[heap[parent]] <= dist[heap[k]])
            break;
        heap_swap(heap, where, k, parent);
        k = parent;
    }
}

static void heap_down(u16 *heap, u16 *where, const f32 *dist, u32 size, u32 k)
{
    for (;;) {
        u32 l = 2 * k + 1, r = l + 1, m = k;
        if (l < size && dist[heap[l]] < dist[heap[m]])
            m = l;
        if (r < size && dist[heap[r]] < dist[heap[m]])
            m = r;
        if (m == k)
            break;
        heap_swap(heap, where, k, m);
        k = m;
    }
}

/* Mark the mushroom shortcuts: at a fork (a point with several next points),
 * the path of a branch whose first point has Mushroom setting 1 (race only;
 * enemy-ai-behaviour "Mushroom shortcuts"). */
static void mark_shortcuts(u32 acc, u32 n, u32 battle)
{
    u8 *shortcut = RAM_SHORTCUT;
    for (u32 i = 0; i < 256; i++)
        shortcut[i] = 0;
    if (battle)
        return;
    for (u32 i = 0; i < n; i++) {
        u32 e = point_entry(acc, i);
        s32 count = S32(e + 0x14);
        if (count < 2)
            continue;
        u32 next = U32(e + 0xC);
        for (s32 k = 0; k < count && k < 16; k++) {
            s32 j = S32(next + 4 * k);
            s32 path = j >= 0 && (u32)j < n ? point_path(acc, j) : -1;
            if (path >= 0 && path < 256 && point_mushroom(acc, j) == 1)
                shortcut[path] = 1;
        }
    }
}

static u32 is_shortcut(u32 acc, u32 j, s32 from_path)
{
    s32 path = point_path(acc, j);
    return path != from_path && path >= 0 && path < 256 && RAM_SHORTCUT[path];
}

/* Shortest way from point `from` to point `to` (Dijkstra): along the next
 * links, and also against them (the previous links of a race route) unless
 * OPT_FORWARD_ONLY; entering a mushroom shortcut costs SHORTCUT_PENALTY.
 * Writes the route list. Returns its length, 0 when there is no way. */
static u32 search_route(u32 acc, u32 n, u32 from, u32 to)
{
    struct DriveCtrl *c = CTRL;
    f32 *dist = RAM_DIST;
    s16 *prev = RAM_PREV;
    u16 *heap = RAM_HEAP, *where = RAM_HEAP_POS, *route = RAM_ROUTE;
    u32 both_ways = !(c->options & OPT_FORWARD_ONLY);
    for (u32 i = 0; i < n; i++) {
        dist[i] = INF;
        prev[i] = -1;
        where[i] = HEAP_NONE;
    }
    dist[from] = 0;
    heap[0] = from;
    where[from] = 0;
    u32 size = 1;
    c->plans++;
    while (size) {
        u32 i = heap[0];
        heap_swap(heap, where, 0, size - 1);
        size--;
        where[i] = HEAP_DONE;
        heap_down(heap, where, dist, size, 0);
        if (i == to)
            break;
        u32 e = point_entry(acc, i);
        const volatile f32 *pi = point_pos(acc, i);
        s32 path_i = S32(e + 0x20);
        for (u32 dir = 0; dir < (both_ways ? 2u : 1u); dir++) {
            s32 count = S32(e + (dir ? 0x10 : 0x14));   /* m_prev_count / m_next_count */
            u32 links = U32(e + (dir ? 0x8 : 0xC));     /* m_prev_points / m_next_points */
            if (count <= 0 || !links)
                continue;
            for (s32 k = 0; k < count && k < 16; k++) {
                s32 j = S32(links + 4 * k);
                if (j < 0 || (u32)j >= n || where[j] == HEAP_DONE)
                    continue;
                f32 d = dist[i] + dist_pp(pi, point_pos(acc, j));
                if (is_shortcut(acc, j, path_i))
                    d += SHORTCUT_PENALTY;
                if (d >= dist[j])
                    continue;
                dist[j] = d;
                prev[j] = (s16)i;
                if (where[j] == HEAP_NONE) {
                    heap[size] = j;
                    where[j] = size;
                    size++;
                }
                heap_up(heap, where, dist, where[j]);
            }
        }
    }
    if (dist[to] >= INF)
        return 0;
    u32 len = 0;
    for (s32 i = (s32)to; i >= 0 && len < POINTS_MAX; i = prev[i])
        len++;
    u32 k = len;
    for (s32 i = (s32)to; i >= 0 && k > 0; i = prev[i])
        route[--k] = (u16)i;
    return len;
}

/* Race mode: the next point after `i` (reached from `from`, -1 if none), as
 * a CPU chooses it (enemy-ai-behaviour Finding 8): never straight back, not
 * a mushroom shortcut when there is another branch, else at random. In a
 * battle the links go both ways and a path is driven on in the direction it
 * was entered. */
static s32 choose_next(u32 acc, u32 n, u32 i, s32 from)
{
    u32 e = point_entry(acc, i);
    s32 count = S32(e + 0x14);
    u32 links = U32(e + 0xC);
    if (count <= 0 || !links)
        return -1;
    s32 choice[16], normal = 0, other = -1;
    s32 path_i = S32(e + 0x20);
    u32 inside = CTRL->is_battle && from >= 0 && point_path(acc, from) == path_i;
    for (s32 k = 0; k < count && k < 16; k++) {
        s32 j = S32(links + 4 * k);
        if (j < 0 || (u32)j >= n || j == from)
            continue;
        if (inside && point_path(acc, j) == path_i)
            return j;                              /* inside a battle path: on in the same direction */
        if (other < 0)
            other = j;
        if (is_shortcut(acc, j, path_i))
            continue;
        choice[normal++] = j;
    }
    if (normal)
        return choice[rand_u32(normal)];
    return other >= 0 ? other : from;              /* only shortcuts; or a dead end: back the way it came */
}

/* Race mode: keep FILL_MIN entries ahead of the kart in the route list. */
static void fill_route(u32 acc, u32 n)
{
    struct DriveCtrl *c = CTRL;
    u16 *route = RAM_ROUTE;
    if (c->route_count + FILL_MIN >= POINTS_MAX && c->route_pos > 4) {   /* drop what lies behind */
        u32 drop = c->route_pos - 4;
        for (u32 k = drop; k < c->route_count; k++)
            route[k - drop] = route[k];
        c->route_count -= drop;
        c->route_pos -= drop;
    }
    while (c->route_count && c->route_count < c->route_pos + FILL_MIN && c->route_count < POINTS_MAX) {
        u32 last = route[c->route_count - 1];
        s32 from = c->route_count > 1 ? route[c->route_count - 2] : -1;
        s32 j = choose_next(acc, n, last, from);
        if (j < 0)
            break;
        route[c->route_count++] = (u16)j;
    }
}

/* Start the route at point `start`: search the way to the target (route), or
 * go on along the links (race), from the first point more than 180 units
 * ahead of the kart, as AIControlRace::onAIFall does. */
static void start_route(u32 acc, u32 n, s32 start, f32 px, f32 py, f32 pz)
{
    struct DriveCtrl *c = CTRL;
    c->route_pos = 0;
    c->route_count = 0;
    if (start < 0)
        return;
    if (c->mode == MODE_ROUTE) {
        s32 goal = nearest_point(acc, n, c->target[0], c->target[1], c->target[2], 0);
        c->route_count = goal >= 0 ? search_route(acc, n, (u32)start, (u32)goal) : 0;
        return;
    }
    RAM_ROUTE[0] = (u16)start;
    c->route_count = 1;
    fill_route(acc, n);
    if (!c->is_battle)
        while (c->route_pos + 1 < c->route_count
               && dist3(point_pos(acc, RAM_ROUTE[c->route_pos]), px, py, pz) < 180.0f)
            c->route_pos++;
}

/* ---- inputs --------------------------------------------------------------- */

static void give_input(u32 data, u32 buttons, f32 stick)
{
    struct DriveCtrl *c = CTRL;
    s32 q = (s32)(stick * 7.0f + (stick < 0 ? -0.5f : 0.5f)) + 7;
    q = q < 0 ? 0 : q > 14 ? 14 : q;
    U16(data + 0x0) = buttons;                     /* KDPadDataOnFrame::m_buttons */
    U8(data + 0x2) = q;                            /* m_stick_x */
    U8(data + 0x3) = 7;                            /* m_stick_y */
    c->buttons = buttons;
    c->stick = stick;
}

/* the kart this frame */
struct Kart {
    u32 v;
    f32 fx, fz;                 /* the kart's facing (horizontal part of the forward axis) */
    f32 hx, hz;                 /* the heading steered by: the direction of travel while drifting forward (a
                                   drifting kart faces well inside it), else the facing: a kart that grips
                                   again goes where it faces */
    f32 tx, tz;                 /* the direction of travel (the facing when slow): where the kart is going decides
                                   when to brake for a corner */
    f32 px, py, pz;
    f32 speed, forward;         /* horizontal speed; speed along the heading */
    u32 status;                 /* VehicleMove::m_status_flags */
    u32 wall;                   /* touching a wall */
    f32 speed_ratio;            /* VehicleMove::m_forward_speed_ratio */
};

static void read_kart(u32 v, struct Kart *k)
{
    k->v = v;
    k->fx = F32(v + 0x18);                         /* Rigid::m_kd_mtx: columns side, up, forward, position */
    k->fz = F32(v + 0x20);
    k->px = F32(v + 0x24);
    k->py = F32(v + 0x28);
    k->pz = F32(v + 0x2C);
    f32 sx = F32(v + 0xC60), sz = F32(v + 0xC68); /* VehicleMove::m_xyz_speed_vec */
    k->speed = sqrtf_(sx * sx + sz * sz);
    k->forward = sx * k->fx + sz * k->fz;
    k->hx = k->fx;
    k->hz = k->fz;
    k->tx = k->fx;
    k->tz = k->fz;
    if (k->forward > 1.5f) {
        k->tx = sx / k->speed;
        k->tz = sz / k->speed;
        if (U8(v + 0xEF4) & 0x18) {                /* VehicleMove::m_drift_state: drifting */
            k->hx = k->tx;
            k->hz = k->tz;
        }
    }
    k->status = U32(v + 0xC30);
    k->wall = U32(v + 0xC94) & 1;                  /* m_col_checks[1].m_collision_result: COLLIDING_WITH_WALL */
    k->speed_ratio = F32(v + 0xF30);
}

/* angle from the kart's facing (not its direction of travel) to (x, z) */
static f32 facing_angle_to(const struct Kart *k, f32 x, f32 z)
{
    f32 dx = x - k->px, dz = z - k->pz;
    return atan2_approx(dz * k->fx - dx * k->fz, dx * k->fx + dz * k->fz);
}

static f32 angle_to(const struct Kart *k, f32 x, f32 z)
{
    f32 dx = x - k->px, dz = z - k->pz;
    return atan2_approx(dz * k->hx - dx * k->hz, dx * k->hx + dz * k->hz);   /* right: along heading x up */
}

/* VehicleControlAI::calcSmallJumpTimingAI: a trick hop would count now */
static u32 trick_chance(u32 v)
{
    if (U8(v + 0xFE8))
        return 1;
    if ((U32(v + 0xC30) & VS_GLIDER_PAD) && S32(v + 0xD50) > 2)   /* m_ground_frames */
        return 1;
    return S32(v + 0xFF0) != 0;                    /* m_trick_frames */
}

/* Turn toward `angle` (+ right) and drive: A held, the stick proportional;
 * with the aim behind the kart (more than turn_angle off the heading), brake,
 * then turn in place with A+B. */
static void steer_to(u32 data, const struct Kart *k, f32 angle, u32 extra)
{
    struct DriveCtrl *c = CTRL;
    f32 side = angle < 0 ? -1.0f : 1.0f;
    if (absf(angle) > c->turn_angle) {
        if (k->forward > c->slow_speed) {          /* too fast to turn round: brake, steering in */
            c->status = ST_BRAKE;
            give_input(data, BUTTON_B, side);
        } else {                                   /* A+B at a stop turns the kart in place */
            c->status = ST_TURN;
            give_input(data, BUTTON_A | BUTTON_B, side);
        }
        return;
    }
    c->status = ST_DRIVE;
    give_input(data, BUTTON_A | extra, clampf(angle / c->full_steer_angle, -1.0f, 1.0f));
}

/* ---- a stuck kart: AIStuck, as far as a player can do it ------------------- */

/* Count slow frames (AIStuck::m_slow_frames: speed below 10 % of the top
 * speed, 3 per frame against a wall); back up above the limit. */
static void check_slow(const struct Kart *k)
{
    struct DriveCtrl *c = CTRL;
    if (c->backup_phase || (k->status & (VS_ACCIDENT | VS_HANG | VS_JUGEM))) {
        c->slow_frames = 0;
        return;
    }
    if (k->speed_ratio < 0.1f)
        c->slow_frames += k->wall ? 3 : 1;
    else
        c->slow_frames = 0;
    if (c->slow_frames > c->slow_limit) {
        c->slow_frames = 0;
        c->backup_phase = 1;
        c->backup_frames = 0;
        c->backups++;
        c->drift = 0;
    }
}

/* Back-up phase 1: reverse in a straight line, stick centred. Returns 1
 * while it lasts. */
static u32 backing_up(u32 data)
{
    struct DriveCtrl *c = CTRL;
    if (c->backup_phase != 1)
        return 0;
    u32 limit = c->is_battle ? c->reverse_frames / 2 : c->reverse_frames;
    if (++c->backup_frames >= limit) {
        c->backup_phase = 2;
        c->backup_frames = 0;
    }
    c->status = ST_BACKUP;
    give_input(data, BUTTON_B, 0.0f);
    return 1;
}

/* ---- the modes ------------------------------------------------------------ */

static void reached(u32 data, const struct Kart *k)
{
    struct DriveCtrl *c = CTRL;
    c->status = ST_REACHED;
    c->slow_frames = 0;
    c->backup_phase = 0;
    c->drift = 0;
    give_input(data, k->forward > c->slow_speed ? BUTTON_B : 0, 0.0f);
}

/* straight to the target, then stop there */
static void drive_to_target(u32 data, const struct Kart *k)
{
    struct DriveCtrl *c = CTRL;
    if (c->dist < c->radius) {
        reached(data, k);
        return;
    }
    if (backing_up(data))
        return;
    c->backup_phase = 0;
    f32 angle = angle_to(k, c->target[0], c->target[2]);
    c->angle = angle;
    steer_to(data, k, angle, 0);
    check_slow(k);
}

/* turn direction of the route at entry `k` (+1 right, -1 left, 0 straight
 * or unknown), from the route list itself so that it holds both ways */
static s32 turn_sign(u32 acc, u32 k)
{
    struct DriveCtrl *c = CTRL;
    if (k == 0 || k + 1 >= c->route_count)
        return 0;
    const volatile f32 *a = point_pos(acc, RAM_ROUTE[k - 1]);
    const volatile f32 *b = point_pos(acc, RAM_ROUTE[k]);
    const volatile f32 *d = point_pos(acc, RAM_ROUTE[k + 1]);
    f32 ix = b[0] - a[0], iz = b[2] - a[2], ox = d[0] - b[0], oz = d[2] - b[2];
    f32 cross = oz * ix - ox * iz;                 /* > 0: out turns to the right of in */
    return cross > 0 ? 1 : cross < 0 ? -1 : 0;
}

/* How much the route bends (radians, + right) over `dist` units ahead along
 * it, from the stretch the kart drives along on */
static f32 route_bend(u32 acc, f32 dist)
{
    struct DriveCtrl *c = CTRL;
    if (c->route_pos == 0)
        return 0;
    f32 bend = 0, along = 0;
    for (u32 k = c->route_pos; k + 1 < c->route_count && along < dist; k++) {
        const volatile f32 *a = point_pos(acc, RAM_ROUTE[k - 1]);
        const volatile f32 *b = point_pos(acc, RAM_ROUTE[k]);
        const volatile f32 *d = point_pos(acc, RAM_ROUTE[k + 1]);
        f32 ix = b[0] - a[0], iz = b[2] - a[2], ox = d[0] - b[0], oz = d[2] - b[2];
        bend += atan2_approx(oz * ix - ox * iz, ox * ix + oz * iz);
        along += sqrtf_(ox * ox + oz * oz);
    }
    return bend;
}

/* Re-route (AIControlRace::onAIFall): the nearest point, searched as the
 * game does; the kart only moves to it when it is on another path than its
 * target, unless `always` (a player's kart after Lakitu, a Bullet Bill or a
 * fall far from the route). */
static void reroute(u32 acc, u32 n, const struct Kart *k, u32 always)
{
    struct DriveCtrl *c = CTRL;
    s32 near = nearest_point(acc, n, k->px, k->py, k->pz, 1);
    c->no_advance = 0;
    c->wall_frames = 0;
    if (near < 0 && always)
        near = nearest_point(acc, n, k->px, k->py, k->pz, 0);
    if (near < 0)
        return;
    if (!always && c->route_pos < c->route_count
            && point_path(acc, near) == point_path(acc, RAM_ROUTE[c->route_pos]))
        return;
    c->reroutes++;
    c->drift = 0;
    start_route(acc, n, near, k->px, k->py, k->pz);
}

/* Move on along the route list: a point counts as reached within the reach
 * radius (280 in a race, 100 in a battle, 140 after a point with flag 0x04),
 * or in a race once the kart is beyond the plane through it that bisects the
 * turn there (AIPathHandler::isPassedThroughPathPoint_). */
static u32 advance(u32 acc, const struct Kart *k)
{
    struct DriveCtrl *c = CTRL;
    u16 *route = RAM_ROUTE;
    u32 moved = 0;
    while (c->route_pos < c->route_count && moved < ROUTE_STEPS_MAX) {
        u32 i = c->route_pos;
        const volatile f32 *p = point_pos(acc, route[i]);
        f32 d = dist3(p, k->px, k->py, k->pz);
        u32 precise = point_flags(acc, c->last_point) & PT_PRECISE;
        f32 reach = precise ? 140.0f : c->is_battle ? 100.0f : 280.0f;
        u32 passed = d < reach;
        if (!passed && !c->is_battle && d < c->lost_dist && i + 1 < c->route_count) {
            const volatile f32 *q = point_pos(acc, route[i + 1]);
            f32 nx = q[0] - p[0], ny = q[1] - p[1], nz = q[2] - p[2];
            f32 l = sqrtf_(nx * nx + ny * ny + nz * nz);
            if (l > 0) {
                nx /= l; ny /= l; nz /= l;
            }
            if (i > 0) {
                const volatile f32 *o = point_pos(acc, route[i - 1]);
                f32 ix = p[0] - o[0], iy = p[1] - o[1], iz = p[2] - o[2];
                f32 m = sqrtf_(ix * ix + iy * iy + iz * iz);
                if (m > 0) {
                    nx += ix / m; ny += iy / m; nz += iz / m;
                }
            }
            passed = (k->px - p[0]) * nx + (k->py - p[1]) * ny + (k->pz - p[2]) * nz >= 0;
        }
        if (!passed)
            break;
        c->last_point = route[i];
        c->route_pos++;
        c->advances++;
        moved++;
    }
    if (moved) {
        c->no_advance = 0;
        if (c->backup_phase == 2)
            c->backup_phase = 0;
    }
    return moved;
}

/* The drift, started, held and ended as AIDriftDrive and
 * AIControlBase::setBasicDriveInfo_ decide it (enemy-ai-behaviour Finding 6:
 * drift_setting, flags 0x01, 0x04, 0x10). Race only. Updates c->drift. */
static void drift(u32 acc, const struct Kart *k, u32 advanced, f32 ax, f32 az)
{
    struct DriveCtrl *c = CTRL;
    if (c->is_battle || (c->options & OPT_NO_DRIFT) || c->route_pos >= c->route_count) {
        c->drift = 0;
        return;
    }
    u32 v = k->v;
    u32 target = RAM_ROUTE[c->route_pos];
    u32 tflags = point_flags(acc, target);
    if (c->drift) {
        c->drift_frames++;
        u32 drifting = U8(v + 0xEF4) & 0x18;       /* VehicleMove::m_drift_state */
        f32 charge = F32(v + 0xF08);               /* VehicleMove::m_miniturbo_charge */
        u32 end = 0, charged = 0;
        if (k->status & (VS_WING | VS_KILLER))
            end = 1;
        else if (!drifting && c->drift_frames > 30)
            end = 1;                               /* the hop did not turn into a drift */
        /* on reaching a point: the route turns the other way there, at a
         * corner point (not a wiggle of the route). The game's AI also ends
         * its drift at points with drift setting 1 or 2 (2 throws the
         * mini-turbo away; isTimeToEndDrift); a player keeps a drift going
         * as long as the rules here find it safe */
        if (advanced && c->last_point >= 0 && turn_sign(acc, c->route_pos) == -c->drift_dir
                && absf(point_corner(acc, target)) <= 0.998f)
            end = 1;
        /* the corner is over: the route ahead bends less than drift_bend
         * toward the drift's side (where the game's AI has drift setting 1 or
         * 2 points to end it) */
        if (route_bend(acc, c->drift_bend_dist + 20.0f * k->speed) * (f32)c->drift_dir < c->drift_bend)
            end = 1;
        /* charged to the red mini-turbo (VehicleMove::isMiniTurbo_OverLv2):
         * let it go. The game's AI lets the blue one go after 120 frames
         * unless flag 0x10; a player holds on for the red one */
        if (drifting && charge >= F32(DRIVE_PARAM + 0x130))
            charged = 1;
        /* badly out of line: the aim far off the kart's facing
         * (AIDriftDrive::calcSteerDrift_: cosine below 0.4, 0.2 with flag
         * 0x10), or toward the outside of the direction of travel: the drift
         * turns tighter than the road (a drifting kart faces well inside its
         * travel, so the facing cannot tell; not before the hop has turned
         * into a drift, while the heading is still the facing) */
        f32 face = facing_angle_to(k, ax, az);
        f32 limit = (tflags & PT_HOLD_DRIFT) ? 1.37f : 1.16f;    /* acos(0.2), acos(0.4) */
        if (absf(face) > limit)
            end = 1;
        f32 travel = angle_to(k, ax, az);          /* from the direction of travel once drifting */
        if (drifting && travel * (f32)c->drift_dir < -0.35f)
            end = 1;
        /* falling behind the corner: the aim more than `drift_behind` off
         * the direction of travel, toward the inside; steering normally (and
         * braking) turns tighter */
        if (drifting && travel * (f32)c->drift_dir > c->drift_behind)
            end = 1;
        /* the road ahead bends the other way: a kart steered by the stick
         * cannot swing round at once as the AI does */
        if (c->aim_point >= 0 && absf(point_corner(acc, c->aim_point)) <= 0.98f) {
            u32 j = c->route_pos;
            while (j + 1 < c->route_count && RAM_ROUTE[j] != (u32)c->aim_point)
                j++;
            if (turn_sign(acc, j) == -c->drift_dir)
                end = 1;
        }
        if (end || charged) {
            /* charged and nothing else wrong: a player lets the mini-turbo go
             * and drifts again at once while the corner goes on, where the
             * game's AI would wait until it goes straight */
            c->drift_chain = !end;
            c->drift = 0;
            c->drift_rest = end ? 20 : c->chain_rest;
        }
        return;
    }
    if (c->drift_rest) {
        c->drift_rest--;
        return;
    }
    u32 chain = c->drift_chain;
    c->drift_chain = 0;
    u32 ds = point_drift(acc, target);             /* where CPUs may drift: not toward drift setting 1 or 2 */
    if (ds == 1 || ds == 2 || absf(point_corner(acc, target)) > 0.998f)
        return;
    if (dist3(point_pos(acc, target), k->px, k->py, k->pz) > c->drift_start_dist && !chain)
        return;
    if ((k->status & (VS_WING | VS_KILLER)) || k->speed_ratio < 0.6f || c->backup_phase)
        return;
    f32 align = F32(v + 0xF44) * F32(v + 0x18) + F32(v + 0xF48) * F32(v + 0x1C) + F32(v + 0xF4C) * F32(v + 0x20);
    if (align < 0.99f && !chain)                   /* VehicleMove::m_forward_dir along the heading */
        return;
    s32 dir = turn_sign(acc, c->route_pos);
    if (!dir || (chain && dir != c->drift_dir))
        return;
    c->drift = 1;
    c->drift_dir = dir;
    c->drift_frames = 0;
    c->drifts++;
}

/* horizontal distance of point p from the line through (x, z) and (ax, az),
 * measured on the segment */
static f32 off_line(const volatile f32 *p, f32 x, f32 z, f32 ax, f32 az)
{
    f32 ux = ax - x, uz = az - z;
    f32 len2 = ux * ux + uz * uz;
    f32 s = len2 > 0 ? ((p[0] - x) * ux + (p[2] - z) * uz) / len2 : 0;
    s = clampf(s, 0, 1);
    f32 dx = x + s * ux - p[0], dz = z + s * uz - p[2];
    return sqrtf_(dx * dx + dz * dz);
}

static f32 sinf_(f32 x)                        /* |x| <= pi/2 */
{
    f32 x2 = x * x;
    return x * (1.0f - x2 / 6.0f * (1.0f - x2 / 20.0f * (1.0f - x2 / 42.0f)));
}

/* What drifts turned at each stick position (1/radius of the direction of
 * travel; measured on 2026-10-06, N64 Luigi Raceway, 150cc, the menu's
 * default kart: about radius 340 fully in, 450 centred, 780 half out, 1600
 * fully out): stick -1, -0.5, 0, 0.5, 1 toward the inside. A centred stick
 * turns a drift tightly, so a wide corner needs the stick out all along. */
static const f32 DRIFT_CURV[5] = {0.6e-3f, 1.3e-3f, 2.2e-3f, 2.6e-3f, 2.9e-3f};

/* the stick toward the inside (+1 full in, -1 full out) that makes a drift
 * turn with `curv` */
static f32 drift_stick(f32 curv)
{
    if (curv <= DRIFT_CURV[0])
        return -1.0f;
    for (u32 i = 1; i < 5; i++)
        if (curv < DRIFT_CURV[i])
            return -1.0f + 0.5f * ((f32)(i - 1) + (curv - DRIFT_CURV[i - 1]) / (DRIFT_CURV[i] - DRIFT_CURV[i - 1]));
    return 1.0f;
}

/* how far the kart is to the `side` (+1 right, -1 left) of the line of the
 * stretch it drives along (route entries route_pos - 1 to route_pos),
 * horizontally */
static f32 inside_offset(u32 acc, const struct Kart *k, s32 side)
{
    struct DriveCtrl *c = CTRL;
    const volatile f32 *a = point_pos(acc, RAM_ROUTE[c->route_pos - 1]);
    const volatile f32 *b = point_pos(acc, RAM_ROUTE[c->route_pos]);
    f32 ux = b[0] - a[0], uz = b[2] - a[2];
    f32 len = sqrtf_(ux * ux + uz * uz);
    if (len <= 0)
        return 0;
    return (f32)side * ((k->pz - a[2]) * ux - (k->px - a[0]) * uz) / len;   /* right: along x up, as angle_to */
}

/* The aim: the farthest route point, up to `lookahead` ahead along the
 * route, whose straight line from the kart keeps every route point before it
 * within `corridor` of its half-width (MapdataEnemyPoint::m_width, scale x
 * 50, the room the CPUs' lanes use): the kart cuts corners only as far as the
 * road is wide. A drifting kart cuts to the inside of the corner by
 * `corner_shift` of the half-width where the point has flag 0x01 or 0x04 or a
 * sharp corner (AIPathPoint::calcNextTargetTrans). */
static void aim_ahead(u32 acc, const struct Kart *k, f32 *ax, f32 *az)
{
    struct DriveCtrl *c = CTRL;
    f32 ahead = c->lookahead + c->lookahead_speed * k->speed;
    if (point_flags(acc, c->last_point) & PT_PRECISE)
        ahead *= 0.5f;
    u32 j = c->route_pos;
    const volatile f32 *aim = point_pos(acc, RAM_ROUTE[j]);
    f32 along = dist3(aim, k->px, k->py, k->pz);
    /* the kart already outside its share of the road around the stretch it
     * drives along: aim at the next point only, to come back firmly */
    u32 last = c->route_count;
    if (j > 0) {
        const volatile f32 *o = point_pos(acc, RAM_ROUTE[j - 1]);
        f32 room = (point_flags(acc, RAM_ROUTE[j]) & PT_PRECISE)
                   ? F32(point_entry(acc, RAM_ROUTE[j]) + 0x28)
                   : c->kart_room * F32(point_entry(acc, RAM_ROUTE[j]) + 0x28) + c->corridor_slack;
        f32 ux = aim[0] - o[0], uz = aim[2] - o[2];
        f32 len = sqrtf_(ux * ux + uz * uz);
        if (len > 0 && absf((k->px - o[0]) * uz - (k->pz - o[2]) * ux) / len > room)
            last = j + 1;                          /* off the stretch's line by more than its room */
    }
    while (j + 1 < c->route_count && j + 1 < last && along < ahead) {
        const volatile f32 *q = point_pos(acc, RAM_ROUTE[j + 1]);
        u32 inside = 1;
        for (u32 i = c->route_pos; i <= j && inside; i++) {
            u32 e = point_entry(acc, RAM_ROUTE[i]);
            f32 room = (point_flags(acc, RAM_ROUTE[i]) & PT_PRECISE)          /* where cutting sends CPUs off */
                       ? c->precise_corridor * F32(e + 0x28)
                       : c->corridor * F32(e + 0x28) + c->corridor_slack;     /* m_width */
            inside = off_line((const volatile f32 *)U32(e), k->px, k->pz, q[0], q[2]) <= room;
        }
        if (!inside)
            break;
        along += dist_pp(aim, q);
        aim = q;
        j++;
    }
    u32 point = RAM_ROUTE[j];
    c->aim_point = point;
    *ax = aim[0];
    *az = aim[2];
    if (!c->drift || c->is_battle)
        return;
    u32 e = point_entry(acc, point);
    f32 corner = F32(e + 0x24);
    if (!((point_flags(acc, point) & (PT_CORNERING | PT_PRECISE)) || absf(corner) <= 0.98f))
        return;
    if (!(U32(e + 0x50) & 1))                      /* m_internal_flags: m_side_axis valid */
        return;
    f32 sx = F32(e + 0x38), sz = F32(e + 0x40);   /* m_side_axis: right of the route's own direction */
    f32 sl = sqrtf_(sx * sx + sz * sz);
    if (sl <= 0)
        return;
    f32 own = (j + 1 < c->route_count && !is_next(acc, point, RAM_ROUTE[j + 1])) ? -1.0f : 1.0f;
    f32 shift = c->corner_shift * F32(e + 0x28) * (f32)c->drift_dir * own;   /* m_width: the half-width */
    *ax += sx / sl * shift;
    *az += sz / sl * shift;
}

/* How much the route turns (radians, horizontally) between the kart's
 * direction of travel and the route `dist` units ahead along it: a measure
 * of the corner the kart has to take next. */
static f32 turn_ahead(u32 acc, const struct Kart *k, f32 dist)
{
    struct DriveCtrl *c = CTRL;
    u32 j = c->route_pos;
    const volatile f32 *p = point_pos(acc, RAM_ROUTE[j]);
    f32 along = dist3(p, k->px, k->py, k->pz);
    f32 worst = 0;
    while (j + 1 < c->route_count && along < dist) {
        const volatile f32 *q = point_pos(acc, RAM_ROUTE[j + 1]);
        f32 dx = q[0] - p[0], dz = q[2] - p[2];
        f32 a = absf(atan2_approx(dz * k->tx - dx * k->tz, dx * k->tx + dz * k->tz));
        if (a > worst)
            worst = a;
        along += dist_pp(p, q);
        p = q;
        j++;
    }
    return worst;
}

static void drive_route(u32 data, u32 dl, const struct Kart *k)
{
    struct DriveCtrl *c = CTRL;
    u32 acc = route_accessor(dl, c->is_battle);
    u32 n = acc ? (u32)S32(acc + 0xC) : 0;
    if (!n) {
        c->status = ST_NO_ROUTE;
        return;
    }
    if (n > POINTS_MAX) {
        c->status = ST_TOO_MANY;
        return;
    }
    if (acc != c->accessor || n != c->point_count) {
        c->accessor = acc;
        c->point_count = n;
        c->replan = 1;
    }
    if (c->replan) {
        c->replan = 0;
        mark_shortcuts(acc, n, c->is_battle);
        c->last_point = -1;
        start_route(acc, n, nearest_point(acc, n, k->px, k->py, k->pz, 0), k->px, k->py, k->pz);
    }
    if (!c->route_count) {
        c->status = ST_NO_WAY;
        give_input(data, 0, 0.0f);
        return;
    }
    if (c->mode == MODE_RACE)
        fill_route(acc, n);

    /* far from the route (a fall, a cannon, a hit): re-route */
    if (c->lost_wait)
        c->lost_wait--;
    else if (c->route_pos < c->route_count) {
        const volatile f32 *p = point_pos(acc, RAM_ROUTE[c->route_pos]);
        f32 off = c->route_pos ? dist_segment(point_pos(acc, RAM_ROUTE[c->route_pos - 1]), p, k->px, k->py, k->pz)
                               : dist3(p, k->px, k->py, k->pz);
        if (off > c->lost_dist) {
            reroute(acc, n, k, 1);
            c->lost_wait = LOST_WAIT;
        }
    }
    u32 advanced = advance(acc, k);
    if (c->mode == MODE_RACE)
        fill_route(acc, n);

    if (c->route_pos >= c->route_count) {
        if (c->mode == MODE_ROUTE) {               /* past the last point: on to the target */
            drive_to_target(data, k);
            return;
        }
        c->status = ST_NO_WAY;                     /* race mode with nowhere to go */
        give_input(data, 0, 0.0f);
        return;
    }
    u32 target = RAM_ROUTE[c->route_pos];
    c->target_point = target;

    /* the game's re-routes: no new point for 7.5 s, against a wall for half a
     * second, a target steeply above or below (AIPathHandler::update) */
    if (!(k->status & (VS_ACCIDENT | VS_HANG | VS_JUGEM)))
        c->no_advance++;
    c->wall_frames = k->wall ? c->wall_frames + 1 : 0;
    const volatile f32 *tp = point_pos(acc, target);
    f32 tdx = tp[0] - k->px, tdy = tp[1] - k->py, tdz = tp[2] - k->pz;
    u32 lifted = (k->status & (VS_WING | VS_KILLER)) || F32(k->v + 0xDA4) >= 1.0f   /* m_airborne_rate */
                 || (point_flags(acc, c->last_point) & PT_HEIGHT_REROUTE);
    if (c->no_advance >= c->reroute_frames || c->wall_frames > c->wall_reroute_frames
            || (c->no_advance > 20 && lifted && tdy * tdy > 0.3f * (tdx * tdx + tdz * tdz))) {
        reroute(acc, n, k, 0);
        if (c->route_pos >= c->route_count) {
            give_input(data, 0, 0.0f);
            return;
        }
        target = RAM_ROUTE[c->route_pos];
        c->target_point = target;
    }

    if (backing_up(data))
        return;

    f32 ax, az;
    if (c->backup_phase == 2) {                    /* to the spot three points behind (one in battle) */
        u32 back = c->is_battle ? 2 : 4;
        u32 spot = c->route_pos > back ? c->route_pos - back : 0;
        const volatile f32 *s = point_pos(acc, RAM_ROUTE[spot]);
        c->aim_point = RAM_ROUTE[spot];
        if (dist3(s, k->px, k->py, k->pz) < 100.0f)
            c->backup_phase = 0;
        ax = s[0];
        az = s[2];
    } else {
        aim_ahead(acc, k, &ax, &az);
    }
    f32 angle = angle_to(k, ax, az);
    c->angle = angle;
    u32 was_drifting = c->drift;
    if (!c->backup_phase)
        drift(acc, k, advanced, ax, az);
    else
        c->drift = 0;

    /* how much the route turns close ahead: a sharp corner there makes the
     * kart ease off or brake, and skip tricks */
    f32 turn = turn_ahead(acc, k, c->brake_dist + c->brake_dist_speed * k->speed);

    /* trick hops (AIDriftDrive::calcSteerNormal_): at a trick chance unless
     * the target has flag 0x08, or, beyond the game's rules, a sharp corner
     * is close ahead (the trick's boost carried the kart off SNES Rainbow
     * Road's corners); in battle only at points with flag 0x80 */
    u32 extra = 0;
    if (!(c->options & OPT_NO_TRICK) && !(k->status & (VS_KILLER | VS_WING)) && trick_chance(k->v)) {
        u32 allowed = c->is_battle ? ((point_flags(acc, target) | point_flags(acc, c->last_point)) & PT_JUMP)
                                   : !(point_flags(acc, target) & PT_NO_TRICK) && turn <= c->coast_turn;
        if (allowed) {
            if (c->drift) {                        /* a trick needs a fresh press: end the drift first */
                c->drift = 0;
                c->drift_rest = 20;
            } else if (!(c->prev_buttons & BUTTON_R) && c->hop_frames > 20) {
                extra = BUTTON_R;
                c->tricks++;
                c->hop_frames = 0;
            }
        }
    }
    c->hop_frames++;

    if (c->drift) {
        c->status = ST_DRIFT;
        /* the full stick toward the corner until the hop has turned into a
         * drift (the game takes the drift's side from the stick on landing),
         * then the stick that turns the drift onto the arc through the aim:
         * curvature 2 sin(angle) / distance */
        f32 dir = (f32)c->drift_dir;
        f32 stick = dir;
        if (was_drifting && (U8(k->v + 0xEF4) & 0x18)) {
            f32 adx = ax - k->px, adz = az - k->pz;
            f32 curv = 2.0f * sinf_(clampf(angle * dir, -1.5f, 1.5f)) / sqrtf_(adx * adx + adz * adz + 1.0f);
            stick = dir * drift_stick(c->drift_gain * curv);
            /* the stick held inward charges the mini-turbo faster (outward
             * slower): hold it in while the kart is farther out than
             * drift_room of the half-width inside the stretch it drives along
             * and faces less than 35 degrees inside its travel (held longer,
             * the kart turned round in the drift and left it pointing off the
             * road) */
            f32 slip = atan2_approx(k->fz * k->tx - k->fx * k->tz, k->fx * k->tx + k->fz * k->tz) * dir;
            if (c->route_pos > 0 && slip < 0.61f
                    && inside_offset(acc, k, c->drift_dir) < c->drift_room * F32(point_entry(acc, target) + 0x28))
                stick = dir;
        }
        give_input(data, BUTTON_A | BUTTON_R, stick);
    } else {
        steer_to(data, k, angle, extra);
        /* a sharp corner close ahead: ease off, or brake, as a player would
         * (the AI turns its kart directly, AI::setRotateRadAI) */
        if (c->status == ST_DRIVE && !(k->status & VS_WING)) {
            f32 tdx = ax - k->px, tdz = az - k->pz;  /* the aim from the direction of travel */
            f32 off = absf(atan2_approx(tdz * k->tx - tdx * k->tz, tdx * k->tx + tdz * k->tz));
            if ((turn > c->brake_turn || off > c->brake_angle) && k->speed_ratio > c->brake_ratio) {
                c->status = ST_BRAKE;
                give_input(data, BUTTON_B | extra, c->stick);
            } else if (turn > c->coast_turn && k->speed_ratio > c->coast_ratio) {
                give_input(data, extra, c->stick);
            }
        }
    }
    check_slow(k);
}

void drive_frame(u32 inputer)
{
    struct DriveCtrl *c = CTRL;
    if (c->mode == MODE_OFF)
        return;
    u32 dl = director_list();
    u32 pad = U32(inputer + 0x20);                 /* KDPadAddBase::m_pad */
    u32 v = dl ? find_vehicle(dl, pad) : 0;
    c->vehicle = v;
    if (!v) {
        c->status = ST_NO_RACE;
        return;
    }
    u32 data = U32(inputer + 0x1C);                /* KDPadAddBase::m_data_on_frame */
    u32 state = race_state(dl);
    if (c->generation != c->seen_generation) {     /* a mode set by the host: start afresh */
        c->seen_generation = c->generation;
        c->replan = 1;
        c->frames = 0;
        c->route_count = c->route_pos = 0;
        c->slow_frames = c->no_advance = c->wall_frames = c->lost_wait = 0;
        c->backup_phase = c->drift = c->drift_rest = c->drift_chain = 0;
        c->reroutes = c->backups = c->drifts = c->tricks = c->advances = c->lakitus = c->plans = 0;
        c->away = 0;
        c->target_point = c->aim_point = c->last_point = -1;
        c->accessor = 0;
        c->race_state = state;
        c->rand ^= v ^ U32(ROOT_SYSTEM + 0x10);
    }
    if (state == RACE_STATE_COUNTDOWN && c->race_state != RACE_STATE_COUNTDOWN && c->frames) {
        /* a new race (a retry can load at the same addresses): goto and route
         * end, race mode starts over */
        if (c->mode == MODE_RACE) {
            c->replan = 1;
            c->accessor = 0;
            c->away = 0;
            c->backup_phase = c->drift = 0;
        } else {
            c->mode = MODE_OFF;
            c->status = ST_ENDED;
            c->race_state = state;
            return;
        }
    }
    c->race_state = state;
    c->is_battle = is_battle_race(dl);
    if (state != RACE_STATE_RACE) {
        c->status = ST_WAIT;
        /* race mode: the start boost, holding A from a frame of the countdown
         * on (measured: from frame 122-126 of 241 a full boost, 130-149 a
         * smaller one, 120 and earlier the wheels spin) */
        if (state == RACE_STATE_COUNTDOWN && c->mode == MODE_RACE && c->start_frame
                && race_state_frames(dl) >= c->start_frame)
            give_input(data, BUTTON_A, 0.0f);
        return;
    }
    struct Kart k;
    read_kart(v, &k);
    c->pos[0] = k.px; c->pos[1] = k.py; c->pos[2] = k.pz;
    c->speed = k.speed;
    c->frames++;
    f32 dx = c->target[0] - k.px, dz = c->target[2] - k.pz;
    c->dist = sqrtf_(dx * dx + dz * dz);

    if (k.status & (VS_JUGEM | VS_HANG | VS_KILLER)) {   /* Lakitu or the Bullet Bill has the kart */
        if (!c->away && !(k.status & VS_KILLER))
            c->lakitus++;
        c->away = 1;
        c->status = (k.status & VS_KILLER) ? ST_KILLER : ST_LAKITU;
        c->slow_frames = c->no_advance = c->wall_frames = 0;
        c->backup_phase = c->drift = 0;
        give_input(data, 0, 0.0f);
        c->prev_buttons = 0;
        return;
    }
    if (c->away) {                                 /* back on the course: find the route again */
        c->away = 0;
        if (c->mode != MODE_GOTO && c->accessor && c->point_count)
            reroute(c->accessor, c->point_count, &k, 1);
    }
    if (c->mode == MODE_GOTO)
        drive_to_target(data, &k);
    else
        drive_route(data, dl, &k);
    c->prev_buttons = c->buttons;
}
