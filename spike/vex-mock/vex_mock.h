/* vex_mock.h —— **VEX API 的 host mock**（桌面侧副产物，验收线 § 5）
 *
 * ★ **它解决什么问题**：
 *   「同一段逻辑的两种写法」要在**没有机器人**的情况下证明等价。
 *   ⇒ 真 VEX API 不存在于 host ⇒ 用这个 mock 顶替 ⇒ 两边各跑一遍 ⇒
 *   **比调用轨迹** ⇒ 语义等价 ⇒ 轨迹逐条相同。
 *
 * ⚠️ **mock 的植物模型不需要准**（这是关键）：
 *   比的是**两个实现**，不是机器人的真实动力学 ⇒
 *   mock 只要 **① 确定 ② 两边一模一样** 就有意义 ⇒
 *   ⇒ 任何"更真实的电机模型"都是浪费。
 *
 * ⚠️ **它不能替代真机**：
 *   B 路（JHYY → ARM 机器码）的产物是**裸机码** ⇒ host 上跑不了
 *   ⇒ **只有 B 路的行为必须上机验**（见 docs/第1步-上机清单.md）。
 *
 * 用法：
 *   1. 把 `vex_mock.c` 编进 host 程序（替掉真 VEX API）
 *   2. 跑完读 `vex_mock_trace()` ⇒ 一串「函数名 + 参数」
 *   3. 两份轨迹 `diff` ⇒ 相同 ⇒ 两个实现语义等价
 */

#ifndef VEX_MOCK_H
#define VEX_MOCK_H

#include <stdint.h>
#include <stdio.h>
#include "v5.h"

/* ── 轨迹记录 ──────────────────────────────────────────────────────────
 * 每次 API 调用记一条：函数名 + 最多 3 个整数参数。
 * （够用：绑定面里所有函数的参数都能塞进 3 个 int。）
 */
typedef struct {
    const char *fn;      /* 函数名（C 符号名） */
    int32_t a, b, c;      /* 参数（没有的填 0） */
} VexMockCall;

typedef struct {
    VexMockCall *calls;
    int32_t      n;
    int32_t      cap;
} VexMockTrace;

/* ── 假设备状态（一台电机）──────────────────────────────────────────── */
/* ⚠️ 直接用 SDK 的 `V5_Device`（v5.h 里定义）⇒ mock 与生成的 C **同一个类型**
 *    ⇒ 指针类型天然一致，不会有 cast。 */
/* ── 假控制器 ──────────────────────────────────────────────────────── */
typedef struct {
    int32_t axis[4];       /* Axis1..Axis4 的值（-100..100） */
    int32_t button[12];    /* 按钮按下状态 */
} VexMockController;

/* ── 全局状态 ──────────────────────────────────────────────────────── */
typedef struct {
    VexMockTrace   trace;
    V5_Device      motor[8];      /* 索引 0..3 = PORT1..4 */
    VexMockController ctrl[2];    /* 索引 0 = Controller1 */
    double          now_ms;       /* 模拟时钟 */
    char           screen[4096];  /* 屏上文字（拼接） */
    int32_t        screen_len;
} VexMock;

/* 取全局 mock（单例） */
VexMock *vex_mock(void);

/* 模拟时钟上限（毫秒）—— 超过就结束程序并把轨迹打出来。
 * ⚠️ VEX 程序末尾是 `while 1 != 0 { vexDelay(100); }`（让出时间片）⇒
 *    **不设上限就跑不完** ⇒ 默认 5000 ms，runner 可改。 */
extern double vex_mock_max_ms;

/* 清空轨迹 + 复位设备状态（每个程序开始前调一次） */
void vex_mock_reset(void);

/* 读轨迹 */
const VexMockTrace *vex_mock_trace(void);

/* 把轨迹打印成文本（每行一条 ⇒ 直接 diff） */
void vex_mock_dump(FILE *out);

/* 把屏上的文字打印出来 */
void vex_mock_dump_screen(FILE *out);

#endif /* VEX_MOCK_H */
