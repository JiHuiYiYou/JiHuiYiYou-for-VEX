/* vex_mock.c —— **VEX API 的 host mock**（实现，见 vex_mock.h）
 *
 * ★ 它实现的**正好是绑定面表里的那 13 个函数**
 *   （spike/binding/binding_surface.py —— 唯一真相源）
 *   ⇒ JHYY 程序**一个字都不用改**就能在 host 上跑。
 *
 * ⚠️ **植物模型刻意很粗**（这是设计，不是偷懒）：
 *   速度一阶趋近命令（时间常数 100 ms）、位置 = 速度积分（°/s = RPM×6）。
 *   ⇒ 只要**确定**就行 —— 比的是两个实现，不是机器人的真实动力学。
 *
 * ⚠️ **不实现变参**（`vexDisplayPrintf`）—— 绑定面里本来就没有它
 *   （屏显走 `jhyy_vex_display_puts` 这个非变参封装，事实基线 § 9.4）。
 */

#include "vex_mock.h"
#include "jhyy_vex.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── 单例 ─────────────────────────────────────────────────────────── */
static VexMock g_mock;

double vex_mock_max_ms = 5000.0;

VexMock *vex_mock(void) { return &g_mock; }

/* 到点了就结束程序（轨迹 + 屏上文字由 atexit 打出） */
static void dump_on_exit(void)
{
    vex_mock_dump(stdout);
    fflush(stdout);
    vex_mock_dump_screen(stderr);
    fflush(stderr);
}

void vex_mock_reset(void)
{
    memset(&g_mock, 0, sizeof g_mock);
    for (int i = 0; i < 8; i++) {
        g_mock.motor[i].port = i;
        g_mock.motor[i].enc_units = 0;   /* Degrees */
        g_mock.motor[i].brake_mode = 0;   /* Coast */
        g_mock.motor[i].gear = 0;        /* 36:1 */
    }
    atexit(dump_on_exit);
}

/* ── 轨迹 ─────────────────────────────────────────────────────────── */
static void rec(const char *fn, int32_t a, int32_t b, int32_t c)
{
    VexMock *m = &g_mock;
    if (m->trace.n >= m->trace.cap) {
        int32_t cap = m->trace.cap ? m->trace.cap * 2 : 256;
        VexMockCall *p = (VexMockCall *)realloc(m->trace.calls,
                                                (size_t)cap * sizeof(VexMockCall));
        if (!p) { fprintf(stderr, "vex_mock: out of memory\n"); exit(2); }
        m->trace.calls = p;
        m->trace.cap = cap;
    }
    VexMockCall *c2 = &m->trace.calls[m->trace.n++];
    c2->fn = fn; c2->a = a; c2->b = b; c2->c = c;
}

const VexMockTrace *vex_mock_trace(void) { return &g_mock.trace; }

void vex_mock_dump(FILE *out)
{
    for (int32_t i = 0; i < g_mock.trace.n; i++) {
        const VexMockCall *c = &g_mock.trace.calls[i];
        fprintf(out, "%04d %s %d %d %d\n", i, c->fn, c->a, c->b, c->c);
    }
}

void vex_mock_dump_screen(FILE *out)
{
    fwrite(g_mock.screen, 1, (size_t)g_mock.screen_len, out);
    fputc('\n', out);
}

/* ── 假电机：命令 → 状态 ───────────────────────────────────────────── */
static int32_t dev_index(V5_DeviceT dev)
{
    if (!dev) return -1;
    return dev->port;
}

static void advance(double dt_ms)
{
    /* 时间常数 100 ms ⇒ alpha = dt / (dt + 100) */
    double alpha = dt_ms / (dt_ms + 100.0);
    for (int i = 0; i < 8; i++) {
        V5_Device *m = &g_mock.motor[i];
        double target = (double)m->cmd_velocity;
        /* ⚠️ **反转标志会翻转命令方向**（SDK 文档：inverts the motor commands）
         *    ⇒ 不建模的话，mock 会给出与真机**相反**的结论（REVF SAME vs FLIP）*/
        if (m->rev_flag) target = -target;
        /* 刹车：速度命令为 0 时按刹车模式处理（Brake/Hold ⇒ 直接停住） */
        if (target == 0.0 && (m->brake_mode == 1 || m->brake_mode == 2)) {
            m->velocity = 0.0;
        } else {
            m->velocity += (target - m->velocity) * alpha;
        }
        /* 速度 RPM → 位置度：°/s = RPM × 6（事实基线 § 9.7 实测） */
        m->position += m->velocity * 6.0 * (dt_ms / 1000.0);
    }
    g_mock.now_ms += dt_ms;
    /* 到上限就结束（VEX 程序末尾是死循环 ⇒ 必须有边界） */
    if (g_mock.now_ms > vex_mock_max_ms) {
        exit(0);
    }
}

/* ── 绑定面表里的 13 个函数（逐个对应）─────────────────────────────── */

/* ① */
V5_DeviceT vexDeviceGetByIndex(uint32_t index)
{
    rec("vexDeviceGetByIndex", (int32_t)index, 0, 0);
    if (index >= 8) index = 7;
    return &g_mock.motor[index];
}

/* ② */
void vexDeviceMotorGearingSet(V5_DeviceT device, V5MotorGearset value)
{
    rec("vexDeviceMotorGearingSet", dev_index(device), (int32_t)value, 0);
    if (device) device->gear = (int32_t)value;
}

/* ③ */
void vexDeviceMotorBrakeModeSet(V5_DeviceT device, V5MotorBrakeMode mode)
{
    rec("vexDeviceMotorBrakeModeSet", dev_index(device), (int32_t)mode, 0);
    if (device) device->brake_mode = (int32_t)mode;
}

/* ④ */
void vexDeviceMotorEncoderUnitsSet(V5_DeviceT device, V5MotorEncoderUnits units)
{
    rec("vexDeviceMotorEncoderUnitsSet", dev_index(device), (int32_t)units, 0);
    if (device) device->enc_units = (int32_t)units;
}

/* ⑤ */
void vexDeviceMotorVelocitySet(V5_DeviceT device, int32_t velocity)
{
    rec("vexDeviceMotorVelocitySet", dev_index(device), velocity, 0);
    if (device) device->cmd_velocity = velocity;
}

/* ⑥ */
V5MotorBrakeMode vexDeviceMotorBrakeModeGet(V5_DeviceT device)
{
    int32_t v = device ? device->brake_mode : 0;
    rec("vexDeviceMotorBrakeModeGet", dev_index(device), v, 0);
    return (V5MotorBrakeMode)v;
}

/* ⑦ */
V5MotorEncoderUnits vexDeviceMotorEncoderUnitsGet(V5_DeviceT device)
{
    int32_t v = device ? device->enc_units : 0;
    rec("vexDeviceMotorEncoderUnitsGet", dev_index(device), v, 0);
    return (V5MotorEncoderUnits)v;
}

/* ⑧ */
V5MotorGearset vexDeviceMotorGearingGet(V5_DeviceT device)
{
    int32_t v = device ? device->gear : 0;
    rec("vexDeviceMotorGearingGet", dev_index(device), v, 0);
    return (V5MotorGearset)v;
}

/* ⑨ */
void vexDeviceMotorReverseFlagSet(V5_DeviceT device, bool value)
{
    rec("vexDeviceMotorReverseFlagSet", dev_index(device), value ? 1 : 0, 0);
    if (device) device->rev_flag = value ? 1 : 0;
}

/* ⑩ */
bool vexDeviceMotorReverseFlagGet(V5_DeviceT device)
{
    int32_t v = device ? device->rev_flag : 0;
    rec("vexDeviceMotorReverseFlagGet", dev_index(device), v, 0);
    return v ? true : false;
}

/* ⑪ */
int32_t vexDeviceAbsEncVelocityGet(V5_DeviceT device)
{
    int32_t v = 0;
    if (device) {
        double x = device->velocity;
        v = (int32_t)(x + (x >= 0 ? 0.5 : -0.5));   /* 四舍五入（截断向零） */
    }
    rec("vexDeviceAbsEncVelocityGet", dev_index(device), v, 0);
    return v;
}

/* ⑫ */
void vexDelay(uint32_t timems)
{
    rec("vexDelay", (int32_t)timems, 0, 0);
    advance((double)timems);
}

/* ⑬ */
void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text)
{
    rec("jhyy_vex_display_puts", xpos, ypos, 0);
    VexMock *m = &g_mock;
    size_t n = strlen(text ? text : "");
    if (m->screen_len + (int32_t)n + 1 < (int32_t)sizeof m->screen) {
        memcpy(m->screen + m->screen_len, text ? text : "", n);
        m->screen_len += (int32_t)n;
        m->screen[m->screen_len] = 0;
    }
}
