/* ABI 探针 —— 量「JHYY 要绑的东西」的真实布局与传参约定。
 *
 * 为什么用「全局数组长度」编码测量值：
 *   编译期常量（sizeof / alignof / offsetof）在 .o 里没有字面量，
 *   但把它们当数组长度，符号表里就带着这个尺寸 ⇒ `nm -S` 能直接读回来。
 *   比 printf 可靠：不需要实机，结果进 ELF 符号表，可被脚本复核。
 *
 * 编译（不链接，只要 .o）：
 *   scripts/measure-abi.sh
 *
 * 测完读：
 *   arm-none-eabi-nm -S --size-sort <o>    → 各 m_* 符号的 size = 测量值
 *   arm-none-eabi-objdump -d <o>           → 按值传参的调用点长什么样
 */

#include "v5.h"
#include <stddef.h>

/* ── 1. 指针宽度 ─────────────────────────────────────────────────────────
 * V5_DeviceT 是 struct _V5_Device * ⇒ 4 字节（32 位 ARM）。
 * ⚠️ JHYY 当前的指针宽度是 8 字节（ABI v4.0.0 § 9 锁死「指针宽度 64 位」，
 * 且四个目标全是 amd64）⇒ 绑 V5_DeviceT 需要 ARM 目标先把指针宽度定成 4。
 */
char m_ptr_V5_DeviceT[sizeof(V5_DeviceT)];
char m_ptr_align[__alignof__(V5_DeviceT)];

/* ── 2. packed struct：V5_DeviceMotorPid ─────────────────────────────────
 * v5_apitypes.h:299  typedef struct __attribute__((__packed__)) _V5_DeviceMotorPid
 * 字段：kf kp ki kd filter pad1 (u8×6) / limit (u16) / threshold (u8) /
 *       loopspeed (u8) / pad2[2] (u8×2)
 * ⇒ 12 字节，align 1，limit 落在偏移 6（u16 跨过了 8 字节对齐位）。
 */
char m_pid_size[sizeof(V5_DeviceMotorPid)];
char m_pid_align[__alignof__(V5_DeviceMotorPid)];
char m_pid_off_limit[offsetof(V5_DeviceMotorPid, limit)];
char m_pid_off_threshold[offsetof(V5_DeviceMotorPid, threshold)];
char m_pid_off_loopspeed[offsetof(V5_DeviceMotorPid, loopspeed)];
char m_pid_off_pad2[offsetof(V5_DeviceMotorPid, pad2)];

/* ── 3. 按值传参的 struct：V5_DeviceVisionRgb ────────────────────────────
 * v5_apitypes.h:381  packed，4 × u8 ⇒ 4 字节，align 1。
 * 这是整个 C API 里**唯一**按值传的 struct 参数（见事实基线 § 8.1）。
 */
char m_rgb_size[sizeof(V5_DeviceVisionRgb)];
char m_rgb_align[__alignof__(V5_DeviceVisionRgb)];
char m_rgb_off_red[offsetof(V5_DeviceVisionRgb, red)];
char m_rgb_off_brightness[offsetof(V5_DeviceVisionRgb, brightness)];

/* ── 4. 非 packed struct：V5_TouchStatus ────────────────────────────────
 * v5_apitypes.h:579  无 packed ⇒ 有 padding，align 跟 int32 走。
 * 用来对照：不是所有 SDK struct 都是 packed。
 */
char m_touch_size[sizeof(V5_TouchStatus)];
char m_touch_align[__alignof__(V5_TouchStatus)];
char m_touch_off_lastXpos[offsetof(V5_TouchStatus, lastXpos)];
char m_touch_off_pressCount[offsetof(V5_TouchStatus, pressCount)];

/* ── 5. enum 宽度（-fshort-enums 生效）──────────────────────────────────
 * § 9 最小绑定面里有 vexControllerGet(V5_ControllerId, V5_ControllerIndex)
 * 和 vexDeviceMotorModeSet(dev, V5MotorControlMode) ⇒ enum 的实际宽度要量。
 */
char m_enum_DeviceType[sizeof(V5_DeviceType)];
char m_enum_ControllerId[sizeof(V5_ControllerId)];
char m_enum_ControllerIndex[sizeof(V5_ControllerIndex)];
char m_enum_MotorControlMode[sizeof(V5MotorControlMode)];
char m_enum_LedColor[sizeof(V5_DeviceLedColor)];

/* ── 6. 按值传参 / 按值返回的调用点（给反汇编看）─────────────────────────
 * probe_call_by_value：struct 作实参 ⇒ 看它落在哪个寄存器。
 * probe_ret_by_value：struct 作返回值 ⇒ 看它从哪个寄存器回来。
 */
void probe_call_by_value(V5_DeviceT dev)
{
    V5_DeviceVisionRgb c;
    c.red = 0x11;
    c.green = 0x22;
    c.blue = 0x33;
    c.brightness = 0x44;
    vexDeviceVisionWhiteBalanceSet(dev, c);
}

V5_DeviceVisionRgb probe_ret_by_value(V5_DeviceT dev)
{
    return vexDeviceVisionWhiteBalanceGet(dev);
}

/* ── 7. enum 实参怎么传（-fshort-enums 让 enum 只有 1 字节宽）───────────
 * § 9 最小绑定面里的 vexControllerGet(id, index) 与
 * vexDeviceMotorModeSet(dev, mode) 都收 enum 实参。
 * 问题：enum 宽 1 字节，但整型提升后是 4 字节 —— 寄存器里放的是哪个宽度？
 *
 * 用**变量**而不是常量当实参：常量会被折进寄存器，看不出转换过程。
 * g_index / g_mode 是 1 字节的全局量 ⇒ 必须 ldrb 出来 ⇒ 提升过程可见。
 */
V5_ControllerIndex g_index;
V5MotorControlMode g_mode;

int32_t probe_call_enum(V5_ControllerId id)
{
    return vexControllerGet(id, g_index);
}

void probe_call_enum_one(V5_DeviceT dev)
{
    vexDeviceMotorModeSet(dev, g_mode);
}

/* 让 main 存在（VEX 的用户 main 会被 vexTaskAdd 注册成 task），
 * 但本探针**不烧录**、不转电机 —— 它只负责产出可测的 .o。 */
int main(void)
{
    return 0;
}
