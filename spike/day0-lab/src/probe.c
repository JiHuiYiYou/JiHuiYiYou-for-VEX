/* probe.c —— 实机测量探针（事实基线 § 13 五条缺口，一次跑完）
 *
 * 入口：`probe_main()` —— 由 `src/main.cpp`（VEXcode GUI 工程的 C++ 入口）调用。
 * ⚠️ 链接期的入口符号仍然叫 `main` 且不带修饰（SDK 用 `R_ARM_ABS32 main` 取地址，
 *    事实基线 § 9.3）—— 那一层在 main.cpp 里。
 *
 * ★ 这个探针**自己记录**：
 *   - 所有能自动测的量（电机 / tick / 堆 / 场控 / 设备）⇒ 写进 SD 卡的日志文件
 *   - 只有人才能回答的（屏显语义 / 电机转向 / 场控开关）
 *     ⇒ **在控制器上出题、你按键作答，程序把答案也写进日志**
 *   ⇒ 你只需要：插卡 → GUI 点下载 → 看一眼 Brain 屏 → 按几下键 → 拔卡给电脑
 *
 *   日志格式 = 一行一个 `key=value`（人可读、机器可解析）
 *   解析脚本：`scripts/parse-lab-log.py`
 *
 * 测什么（事实基线 § 13）：
 *   M1 电机实机行为 + 速度/位置的数量级与符号   → 阻塞 验收线 § 1③「实机可跑」
 *   M2 屏显坐标与 bOpaque 语义（出题 + 作答）   → 阻塞 绑定面封装的 bOpaque 取值
 *   M3 vexDelay 的真实耗时 ⇒ 调度 tick 粒度     → 阻塞 验收线 § 1⑧（八项里最后一条）
 *   M4 堆：_sbrk 的 break 位置 ⇒ 真实可用堆      → 阻塞 JHYY mem/arena 的用量设计
 *   M5 vexCompetitionStatus 的原始位            → 绑定面「场控状态」的读法
 *
 * ⚠️ 这个探针**不是** JHYY 绑定面，它直接调 VEX 的 C API 是**故意的**：
 *    屏显坐标 / 不透明语义正是要**测**的东西；
 *    绑定面封装把 bOpaque 固定成 0，正是因为这个语义还没测出来。
 *    —— 但绑定面**本身**也要在实机上被验证（它是 B 路要调的**同一个符号**），
 *    所以 M2 的相位 A 走 jhyy_vex_display_puts（实现直接引用 day0-c 里那一份）。
 *
 * ⚠️ 这里**不写 __DATE__ / __TIME__**：那会让产物不再逐字节可复现，
 * 而「哈希清单」是本仓的留存口径（事实基线 § 2.1）。
 */

#include "v5.h"
#include "jhyy_vex.h"

#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

/* ── 堆原语 ─────────────────────────────────────────────────────────────
 *
 * ⚠️ stdlib_0.lib **没有** malloc / free / calloc / realloc / sbrk
 *    （nm 全量扫描，一个分配器都没有）—— newlib 子集里**根本没有分配器**。
 *    唯一的堆原语是 libv5rt.a(v5_startup.c.obj) 里的 **_sbrk**（弱符号）：
 *    它在 _heap_start.._heap_end 之间推进一个 break，越界返回 -1。
 * ⇒ 想量堆，只能直接调 _sbrk。
 */
extern void *_sbrk(int incr);
extern char  _heap_start[];
extern char  _heap_end[];

#define MOTOR_INDEX 0
#define N_DEV       4        /* PORT1..PORT4 */
#define N_DELAY     50       /* 每次延时循环的次数 */
#define LOG_NAME    "day0lab.txt"
#define LOG_KEEP    48       /* 屏幕回放：最多留多少行 */
#define LOG_LINE    88       /* 屏幕回放：每行最长多少字符 */

/* ── 日志 ────────────────────────────────────────────────────────────────
 *
 * ⚠️ 走 newlib 的 fopen/fwrite —— 这条路是**SDK 自己走的**：
 *    `vex::brain::sdcard::savefile` 的实现就是
 *    `vexFileDriveStatus(0)` + `std::ofstream(name)` ⇒ plain 文件名落在 SD 卡上。
 *
 * ★ **三条记录通道，同一份内容**（卡不一定能用 ⇒ 不能只押一条）：
 *   ① SD 卡文件 `day0lab.txt`（有卡才有）
 *   ② Brain 控制台（vex_printf）—— VEXcode 的终端窗格能看见
 *   ③ Brain 屏 / 控制器屏**分页回放**（拍照即可）
 *   三条都是 `key=value` 文本 ⇒ `scripts/parse-lab-log.py` 一份脚本全吃。
 */
static FILE *g_log;
static char  g_log_path[64];
static char  g_lines[LOG_KEEP][LOG_LINE];
static int   g_nlines;

/* 7 道题的作答（按题目顺序）—— 收尾时**直接打在 DONE 屏上**，
 * 这样"最后一张照片"就能带走全部答案，不必翻日志页。 */
static const char *g_ans[8];
static int         g_nans;

static void lab_log(const char *fmt, ...)
{
    char buf[LOG_LINE];
    va_list ap;

    va_start(ap, fmt);
    (void)vex_vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    if (g_log) {
        (void)fwrite(buf, 1, strlen(buf), g_log);
        (void)fflush(g_log);
    }
    (void)vex_printf("%s\n", buf);

    if (g_nlines < LOG_KEEP) {
        (void)vex_snprintf(g_lines[g_nlines], LOG_LINE, "%s", buf);
        g_nlines++;
    }
}

/* 依次试几个路径写法 —— 探针自己找得到能用的那个 */
static void lab_log_open(void)
{
    static const char *cands[] = {
        LOG_NAME,
        "0:/" LOG_NAME,
        "/" LOG_NAME,
        NULL
    };
    int i;

    for (i = 0; cands[i] != NULL; i++) {
        FILE *f = fopen(cands[i], "a");
        if (f != NULL) {
            g_log = f;
            (void)vex_snprintf(g_log_path, sizeof(g_log_path), "%s", cands[i]);
            return;
        }
    }
    g_log_path[0] = '\0';
}

/* ── 屏幕小工具 ───────────────────────────────────────────────────────── */

static void ctrl(int line, const char *s)
{
    (void)vexControllerTextSet(kControllerMaster, (uint32_t)line, 0, s);
}

static void brain(int line, const char *s)
{
    (void)vexDisplayString((int32_t)line, "%s", s);
}

/* ── 屏幕分页回放 ───────────────────────────────────────────────────────
 *
 * SD 卡不一定能用 ⇒ 日志同时在屏上**分页轮播**（每页 6 行，5 秒一页）。
 * 拍一段视频 / 几张照片就等于把整份日志带走。
 */
#define PAGE_LINES 6
#define PAGE_MS    5000

static void show_pages(void)
{
    int i, p, pages;

    pages = (g_nlines + PAGE_LINES - 1) / PAGE_LINES;
    if (pages <= 0)
        pages = 1;

    for (p = 0; p < pages; p++) {
        for (i = 0; i < PAGE_LINES; i++) {
            int idx = p * PAGE_LINES + i;
            const char *s = (idx < g_nlines) ? g_lines[idx] : "";
            brain(i, s);
            ctrl(i, s);
        }
        vexDelay(PAGE_MS);
    }
}

/* ── M1 电机 ─────────────────────────────────────────────────────────── */

static void config_motor(V5_DeviceT dev)
{
    vexDeviceMotorGearingSet(dev, kMotorGearSet_18);
    vexDeviceMotorBrakeModeSet(dev, kV5MotorBrakeModeBrake);
    vexDeviceMotorEncoderUnitsSet(dev, kMotorEncoderDegrees);
}

/* 转 1 秒并读回。
 *
 * ⚠️ **方向不靠人判断**：顺/逆时针取决于**从哪头看**、电机装在左边还是右边
 *    —— 那是**安装姿态**，不是 API 的属性。
 *    ⇒ 符号语义由程序用「+50 / -50 / 反转标志」三组实验自己测出来；
 *    人只需要回答"转没转"（验收线 § 1③ 要的那一条）。
 */
static void spin_motor(V5_DeviceT dev, int32_t vel, const char *tag)
{
    long pos_x10, dir, avel_x10, vget;

    /* ⚠️ 这里**不**调 config_motor() —— 第一轮实机发现：
     *    置上反转标志后再走一遍 config（齿轮/刹车/编码器单位），
     *    读回就全变了 ⇒ 顺序必须由调用方掌握（见 measure_motor）。 */
    vexDeviceMotorPositionReset(dev);

    vexDeviceMotorVelocitySet(dev, vel);
    vexDelay(1000);

    vget     = (long)vexDeviceMotorVelocityGet(dev);
    avel_x10 = (long)(vexDeviceMotorActualVelocityGet(dev) * 10.0);
    dir      = (long)vexDeviceMotorDirectionGet(dev);
    pos_x10  = (long)(vexDeviceMotorPositionGet(dev) * 10.0);

    vexDeviceMotorVelocitySet(dev, 0);
    vexDelay(200);

    lab_log("M1.%s.vget=%ld", tag, vget);
    lab_log("M1.%s.avel_x10=%ld", tag, avel_x10);
    lab_log("M1.%s.dir=%ld", tag, dir);
    lab_log("M1.%s.pos_x10=%ld", tag, pos_x10);
}

static void measure_motor(void)
{
    V5_DeviceT dev = vexDeviceGetByIndex(MOTOR_INDEX);
    uint32_t i;

    for (i = 0; i < N_DEV; i++)
        lab_log("M1.dev%lu=%ld", (unsigned long)i,
                (vexDeviceGetByIndex(i) != (V5_DeviceT)0) ? 1L : 0L);

    if (dev == (V5_DeviceT)0) {
        lab_log("M1.note=no_device_at_index_%d", MOTOR_INDEX);
        return;
    }

    config_motor(dev);

    /* set 之后立刻 get 回来 —— 验证这几个 set 真的生效 */
    lab_log("M1.gear=%ld", (long)vexDeviceMotorGearingGet(dev));
    lab_log("M1.brake=%ld", (long)vexDeviceMotorBrakeModeGet(dev));
    lab_log("M1.enc=%ld", (long)vexDeviceMotorEncoderUnitsGet(dev));

    /* ① 正速度 → 位置/方向/速度的符号 */
    spin_motor(dev, 50, "pos50");

    /* ② 负速度 → 符号应当相反（"符号语义"的关键实验） */
    spin_motor(dev, -50, "neg50");

    /* ③ 反转标志 —— 安装姿态的表达方式（左边电机 / 右边电机）
     *
     * ⚠️ **顺序不能反**：第一轮实机里，置上标志之后又走了一遍 config_motor()
     *    （齿轮/刹车/编码器单位），读回就全变了 —— 到底是标志被清了，
     *    还是标志本来就不影响读回，**分不清**。
     *    ⇒ 现在：先 config，**再**置标志，然后 spin，
     *      并且 spin 之后**再读一次标志**，看它有没有被谁清掉。 */
    config_motor(dev);
    vexDeviceMotorReverseFlagSet(dev, true);
    lab_log("M1.revflag_on=%d", vexDeviceMotorReverseFlagGet(dev) ? 1 : 0);
    spin_motor(dev, 50, "pos50_rev");
    lab_log("M1.revflag_after_spin=%d", vexDeviceMotorReverseFlagGet(dev) ? 1 : 0);
    vexDeviceMotorReverseFlagSet(dev, false);
    lab_log("M1.revflag_off=%d", vexDeviceMotorReverseFlagGet(dev) ? 1 : 0);
}

/* ── M3 tick / 消息泵 ──────────────────────────────────────────────────
 *
 *   d1 = 50 次 vexDelay(1) 的总耗时  → 每次真实耗时 = d1/50 ms
 *   d0 = 50 次 vexDelay(0) 的总耗时  → vexDelay(0) 到底让不讓出时间片
 * 怎么读这两个数，见 README 的「怎么读」。
 */
static void measure_tick(void)
{
    uint32_t t0, t1;
    int i;

    t0 = vexSystemTimeGet();
    for (i = 0; i < N_DELAY; i++)
        vexDelay(1);
    t1 = vexSystemTimeGet();
    lab_log("M3.d1_ms=%lu", (unsigned long)(t1 - t0));

    t0 = vexSystemTimeGet();
    for (i = 0; i < N_DELAY; i++)
        vexDelay(0);
    t1 = vexSystemTimeGet();
    lab_log("M3.d0_ms=%lu", (unsigned long)(t1 - t0));

    lab_log("M3.n=%d", N_DELAY);
}

/* ── M4 堆 ──────────────────────────────────────────────────────────────
 *
 * ⚠️ 只问 4 KB —— 撞到 _heap_end 会触发 _sbrk 的回退分支，
 *    别去问「比可用堆还大的数」（那会把 break 搅乱）。
 */
static void measure_heap(void)
{
    char *brk = (char *)_sbrk(0);
    void  *p;
    unsigned long total, freeb, ok = 0;

    total = (unsigned long)(_heap_end - _heap_start);
    freeb = (brk != (char *)0) ? (unsigned long)(_heap_end - brk) : 0UL;

    p = _sbrk(4096);
    if ((p != (void *)-1) && (p != (char *)0)) {
        *(volatile unsigned char *)p = 0x5A;
        ok = (*(volatile unsigned char *)p == 0x5A) ? 1UL : 0UL;
        (void)_sbrk(-4096);           /* 还回去 */
    }

    lab_log("M4.heap_total=%lu", total);
    lab_log("M4.heap_free=%lu", freeb);
    lab_log("M4.alloc_ok=%lu", ok);
}

/* ── 出题 ───────────────────────────────────────────────────────────────
 *
 * 只有人才能回答的量：屏显坐标语义、bOpaque 语义、电机转向、场控开关插没插。
 * 程序在 Brain 屏画图案、在控制器屏出题，你按 A/B/X/Y/L1 作答，**程序把答案写进日志**。
 */
enum {
    PAT_NONE = 0,
    PAT_PIX_00,        /* 只画 (0,0) 一个像素 */
    PAT_PIX_239,       /* 只画 (239,127) 一个像素 */
    PAT_OPAQUE_A,      /* 实心块 + 原始 API（bOpaque=0）写字 */
    PAT_OPAQUE_B,      /* 实心块 + 绑定面（现在是 bOpaque=1）写字 */
    PAT_TEXT_OFFSET,   /* T00 在 (0,0)、T52 在 (5,2) */
    PAT_RULER          /* 10x10 方块 + 文字在 (10,0) */
};

/* 颜色（0xRRGGBB；哪个字节在前都无所谓，只要**两种颜色不同**就行）
 *
 * ⚠️ **块和字必须用不同颜色** ——
 *    `vexDisplayRectFill` 用的是**前景色**（实测：默认白），
 *    文字也是前景色 ⇒ 白字画在白块上 = 看不见。
 *    （这是实测发现的：第一次跑，块出来了、字不见了。）
 */
#define COL_BLOCK 0x0000FFu   /* 块 */
#define COL_TEXT  0x00FF00u   /* 字 */
#define COL_WHITE 0x00FFFFFFu /* 默认前景色（用完还原） */

typedef struct {
    const char *key;        /* 日志里的键 */
    const char *cl1;        /* 控制器第 1 行：问题 */
    const char *cl2;        /* 控制器第 2 行：选项 A / B */
    const char *cl3;        /* 控制器第 3 行：选项 X / Y */
    const char *cl4;        /* 控制器第 4 行：选项 L1 / R1 */
    int         pattern;    /* Brain 屏画什么 */
    const char *ans[6];     /* 6 个选项的文字（= 日志里记的值） */
} q_t;

static void draw_pattern(int pat)
{
    vexDisplayErase();
    vexDisplayTextSize(1, 1);         /* 回到默认字号 */
    vexDisplayForegroundColor(COL_WHITE);

    switch (pat) {
    case PAT_PIX_00:
        vexDisplayPixelSet(0, 0);
        break;
    case PAT_PIX_239:
        vexDisplayPixelSet(239, 127);
        break;
    case PAT_OPAQUE_A:
        vexDisplayTextSize(3, 3);     /* 大字 ⇒ 字与字之间的空隙看得清 */
        vexDisplayForegroundColor(COL_BLOCK);
        vexDisplayRectFill(0, 0, 100, 40);
        vexDisplayForegroundColor(COL_TEXT);
        vexDisplayPrintf(0, 0, 0, "MMMM");      /* 原始 API：bOpaque = 0（透明） */
        vexDisplayForegroundColor(COL_WHITE);
        break;
    case PAT_OPAQUE_B:
        vexDisplayTextSize(3, 3);
        vexDisplayForegroundColor(COL_BLOCK);
        vexDisplayRectFill(0, 0, 100, 40);
        vexDisplayForegroundColor(COL_TEXT);
        jhyy_vex_display_puts(0, 0, "MMMM");   /* 绑定面（现在是 bOpaque = 1） */
        vexDisplayForegroundColor(COL_WHITE);
        break;
    case PAT_TEXT_OFFSET:
        jhyy_vex_display_puts(0, 0, "T00");
        jhyy_vex_display_puts(5, 2, "T52");
        break;
    case PAT_RULER:
        vexDisplayForegroundColor(COL_BLOCK);
        vexDisplayRectFill(0, 0, 9, 9);          /* 10x10 像素的方块 */
        vexDisplayForegroundColor(COL_TEXT);
        jhyy_vex_display_puts(10, 0, "T");       /* 字用另一种颜色，位置一目了然 */
        vexDisplayForegroundColor(COL_WHITE);
        break;
    default:
        break;
    }
}

/* 等一个按键；返回 0..5，超时返回 -1 */
/* 等一个按键；返回 0..5。
 *
 * ⚠️ **不设超时** —— 你要多少时间给多少时间（看一眼屏幕可能就超过 30 秒）。
 *    唯一的出口：**控制器掉线**（线松了 / 没插）⇒ 别死等，
 *    记 `controller_lost` 并停止后面的提问（自动测的那部分已经写进日志了）。
 */
static int wait_answer(void)
{
    static const V5_ControllerIndex btns[6] = {
        ButtonA, ButtonB, ButtonX, ButtonY, ButtonL1, ButtonR1
    };
    int last[6];
    uint32_t offline_since = 0UL;
    int i;

    for (i = 0; i < 6; i++)
        last[i] = 0;

    for (;;) {
        int pressed = -1;

        for (i = 0; i < 6; i++) {
            int v = (int)vexControllerGet(kControllerMaster, btns[i]);
            if ((v != 0) && (last[i] == 0))
                pressed = i;
            last[i] = v;
        }
        if (pressed >= 0)
            return pressed;

        /* 控制器掉线检测（连续 2 秒离线才算，防瞬时抖动） */
        if (vexControllerConnectionStatusGet(kControllerMaster) == kV5ControllerOffline) {
            if (offline_since == 0UL)
                offline_since = vexSystemTimeGet();
            else if ((vexSystemTimeGet() - offline_since) > 2000UL)
                return -1;              /* 控制器掉了 */
        } else {
            offline_since = 0UL;
        }

        vexDelay(100);
    }
}

/* 出题并等答案。返回 0 = 答了；-1 = 控制器掉了（后面的题别问了） */
static int ask(const q_t *q, int index, int total)
{
    char line[64];
    int pick;
    draw_pattern(q->pattern);

    (void)vex_snprintf(line, sizeof(line), "Q%d/%d  press A/B/X/Y/L1/R1", index, total);
    ctrl(0, line);
    ctrl(1, q->cl1);
    ctrl(2, q->cl2);
    ctrl(3, q->cl3);
    ctrl(4, q->cl4);
    ctrl(5, "");

    if (q->pattern == PAT_NONE) {
        brain(0, line);
        brain(1, q->cl1);
    }

    pick = wait_answer();

    if (pick < 0) {
        /* 控制器掉了 —— 记下来，交给调用者停止后面的提问 */
        lab_log("%s=controller_lost", q->key);
        ctrl(5, "-> CONTROLLER LOST");
        return -1;
    }

    lab_log("%s=%s", q->key, q->ans[pick]);
    if (g_nans < 8)
        g_ans[g_nans++] = q->ans[pick];
    ctrl(5, "-> recorded");
    vexDelay(700);
    return 0;
}

/* ── 没有控制器时的退路：显示图案让人拍屏，然后也进分页回放 ───────────── */
static void fallback_cycle(void)
{
    static const int pats[] = {
        PAT_OPAQUE_A, PAT_OPAQUE_B, PAT_PIX_00, PAT_PIX_239,
        PAT_TEXT_OFFSET, PAT_RULER, PAT_NONE
    };
    int i;

    for (i = 0; i < (int)(sizeof(pats) / sizeof(pats[0])); i++) {
        draw_pattern(pats[i]);
        if (pats[i] == PAT_NONE) {
            brain(0, "day0-lab: NO CONTROLLER");
            brain(1, "PHOTOS STILL WORK");
        }
        vexDelay(4000);
    }

    /* 电机至少转一次 —— 让人知道电机是活的 */
    {
            V5_DeviceT d = vexDeviceGetByIndex(MOTOR_INDEX);
            if (d != (V5_DeviceT)0) config_motor(d);
            spin_motor(d, 50, "watch");
        }

    /* 然后同样进分页回放：数据照样能带走 */
    for (;;)
        show_pages();
}

/* ── 入口 ────────────────────────────────────────────────────────────── */

void probe_main(void)
{
    static const q_t questions[] = {
        { "Q1.motor_dir",
          "DID THE MOTOR MOVE? (FROM THE OUTPUT-SHAFT END)",
          "A=YES  B=NO IT DID NOT MOVE",
          "", "",
          PAT_NONE,
          { "moved", "did_not_move", "na", "na", "na", "na" } },

        { "Q2.pix_0_0",
          "ONE DOT ON BRAIN SCREEN: WHERE IS IT?",
          "A=TOP-LEFT  B=TOP-RIGHT",
          "X=BOT-LEFT  Y=BOT-RIGHT",
          "L1=MIDDLE/OTHER  R1=NOT SEEN",
          PAT_PIX_00,
          { "top_left", "top_right", "bottom_left", "bottom_right",
            "middle_or_other", "not_seen" } },

        { "Q3.pix_239_127",
          "ONE DOT ON BRAIN SCREEN: WHERE IS IT?",
          "A=TOP-LEFT  B=TOP-RIGHT",
          "X=BOT-LEFT  Y=BOT-RIGHT",
          "L1=MIDDLE/OTHER  R1=NOT SEEN",
          PAT_PIX_239,
          { "top_left", "top_right", "bottom_left", "bottom_right",
            "middle_or_other", "not_seen" } },

        { "Q4.opaque_plain_api",
          "PLAIN API (bOpaque=0): IS THE BLOCK STILL VISIBLE BETWEEN LETTERS?",
          "A=YES(block visible)  B=NO(block erased)",
          "", "",
          PAT_OPAQUE_A,
          { "block_visible", "block_erased", "na", "na", "na", "na" } },

        { "Q5.opaque_binding_surface",
          "JHYY WRAPPER: IS THE BLOCK STILL VISIBLE BETWEEN THE LETTERS?",
          "A=YES(block visible)  B=NO(block erased)",
          "", "",
          PAT_OPAQUE_B,
          { "block_visible", "block_erased", "na", "na", "na", "na" } },

        { "Q6.text_offset",
          "WHERE IS 'T52' RELATIVE TO 'T00'?",
          "A=RIGHT  B=BELOW  X=BOTTOM-RIGHT",
          "", "L1=SOMEWHERE ELSE",
          PAT_TEXT_OFFSET,
          { "right", "below", "bottom_right", "na", "somewhere_else", "na" } },

        { "Q7.text_unit",
          "DOES THE LETTER START RIGHT AT THE BLOCK EDGE?",
          "A=YES(exactly)  B=NO(far away)  X=ON THE BLOCK",
          "", "L1=SOMEWHERE ELSE",
          PAT_RULER,
          { "exactly", "far_away", "on_the_block", "na", "somewhere_else", "na" } }
    };
    const int nq = (int)(sizeof(questions) / sizeof(questions[0]));
    int i;
    bool have_ctrl;
    unsigned long conn_status;
    int mount_fr;
    int drive0;
    int had_log;

    (void)vex_printf("=== day0-lab-01 ===\n");

    /* ── 先挂载 SD 卡，再开日志（顺序不能反：没挂载就写不进文件） ── */
    mount_fr = (int)vexFileMountSD();
    drive0 = vexFileDriveStatus(0) ? 1 : 0;
    lab_log_open();

    lab_log("# JHYY-for-VEX day0-lab log  schema=1");
    lab_log("log.path=%s", (g_log_path[0] != '\0') ? g_log_path : "NONE");
    lab_log("log.opened=%d", (g_log != NULL) ? 1 : 0);
    lab_log("sd.drive0=%d", drive0);
    lab_log("sd.mount_fr=%d", mount_fr);
    lab_log("boot_ms=%lu", (unsigned long)vexSystemTimeGet());
    /* 版本号按**十六进制**打（第一轮按十进制打，读起来费劲 —— 已修） */
    lab_log("fw.system=0x%lx", (unsigned long)vexSystemVersion());
    lab_log("fw.sdk=0x%lx", (unsigned long)vexSdkVersion());

    /* ── 自动测量 ── */
    brain(0, "day0-lab: MEASURING");
    ctrl(0, "day0-lab MEASURING...");
    ctrl(1, "wait a moment");

    measure_motor();
    measure_tick();
    measure_heap();

    lab_log("M2.disp_w=%ld", (long)vexDisplayStringWidthGet("MMMMMMMMMM"));
    lab_log("M2.disp_h=%ld", (long)vexDisplayStringHeightGet("MMMMMMMMMM"));
    lab_log("M2.fg=0x%lx", (unsigned long)vexDisplayForegroundColorGet());
    lab_log("M2.bg=0x%lx", (unsigned long)vexDisplayBackgroundColorGet());
    lab_log("M5.cstat=0x%lx", (unsigned long)vexCompetitionStatus());

    /* ── 出题（只有人才能答的） ── */
    /* ⚠️ V5_ControllerStatus: 0=offline 1=tethered(USB) 2=vexnet(无线)
     *    —— 0 才是"没插"，所以判据是「非 0」。 */
    conn_status = (unsigned long)vexControllerConnectionStatusGet(kControllerMaster);
    have_ctrl = (conn_status != 0UL);
    lab_log("controller.status=%lu", conn_status);
    lab_log("controller.present=%d", have_ctrl ? 1 : 0);

    if (have_ctrl) {
        /* ★ 先正转一遍再问 Q1 —— 保证用户**看见了**电机动
         *   （只问"动了没"，不问顺/逆时针：那是安装姿态，不是 API 属性） */
        ctrl(0, "Q1: WATCH THE MOTOR NOW");
        ctrl(1, "it spins for 1 second");
        brain(0, "WATCH THE MOTOR");
        brain(1, "it spins for 1 second");
        vexDelay(1500);
        {
            V5_DeviceT d = vexDeviceGetByIndex(MOTOR_INDEX);
            if (d != (V5_DeviceT)0) config_motor(d);
            spin_motor(d, 50, "watch");
        }
        vexDelay(500);

        for (i = 0; i < nq; i++) {
            if (ask(&questions[i], i + 1, nq) != 0) {
                lab_log("note=questions_stopped_at_Q%d", i + 1);
                break;
            }
        }
    } else {
        lab_log("note=no_controller_questions_skipped");
        fallback_cycle();
        return;                   /* fallback_cycle 不返回 */
    }

    /* ── 收尾 ── */
    lab_log("done=1");
    had_log = (g_log != NULL);
    if (g_log) {
        (void)fclose(g_log);
        g_log = NULL;
    }

    /* ★ 答案**直接打在 DONE 屏上** ——
     *   第一轮实机（2026-11-09）就是这样丢了一页：日志页轮播 9 页，
     *   最后一页（Q3~Q7 + done）没拍到 ⇒ 那 5 道题的答案全没了。
     *   ⇒ 收尾屏必须**自带全部答案**，一张照片就够。 */
    {
        static const char *qk[8] = {
            "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"
        };
        char line[64];

        vexDisplayErase();
        brain(0, "day0-lab: DONE");
        for (i = 0; i < g_nans && i < 7; i++) {
            (void)vex_snprintf(line, sizeof(line), "%s=%s", qk[i], g_ans[i]);
            ctrl((int)i + 1, line);
        }
        ctrl(0, "day0-lab DONE - ANSWERS");
        ctrl(8, had_log ? "log saved to SD card"
                        : "no SD card - log is on the screens");
    }
    vexDelay(20000);           /* 停 20 秒 —— 足够拍一张 */

    /* 日志在屏上分页轮播 —— 拍照 / 录像就能带走全部数据 */
    for (;;)
        show_pages();
}
