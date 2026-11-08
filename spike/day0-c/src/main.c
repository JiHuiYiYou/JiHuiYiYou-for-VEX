/* Day 0 探针 —— 纯手写 C，零 JHYY 变量。
 *
 * 目的：把 VEX 侧的未知数一次性实测掉（产物格式 / 启动链 / ABI / API 面），
 *       换成 B 阶段（JHYY 直出 ARM 机器码）的规格书。
 *
 * 走的是官方 SDK 的**纯 C API**（vex*()），不是 C++ 的 vex:: 类 ——
 * 因为 JHYY 的 `extern fn` 对应的是 C ABI（C++ 类要 Itanium mangling，
 * 那是我们刻意不碰的一层）。
 *
 * 本文件只做三件事，每件都对应规格书里的一条待测项：
 *   1. 取设备句柄（确认 C API 的 device 模型是 handle 不是端口号）
 *   2. 配设备 + 转电机（确认最小绑定面够不够用）
 *   3. Brain 屏显（确认 vexDisplay* 的行为）
 *
 * ⚠️ 屏显那一行走的是 jhyy_vex_display_puts（JHYY 绑定面的非变参封装），
 *    不是直接调变参的 vexDisplayPrintf —— 理由见 include/jhyy_vex.h。
 *    A 路与 B 路调的是同一个符号，这是两路能对拍的前提之一。
 */

#include "v5.h"
#include "jhyy_vex.h"

/* C API 的 device 模型：V5_DeviceT = struct _V5_Device *（不透明指针）。
 * 索引 0 = PORT1。 */
#define MOTOR_INDEX 0

int main(void)
{
    V5_DeviceT motor = vexDeviceGetByIndex(MOTOR_INDEX);

    /* 设备配置 —— 对应 vex::motor 构造函数里做的那些事 */
    vexDeviceMotorGearingSet(motor, kMotorGearSet_18);
    vexDeviceMotorBrakeModeSet(motor, kV5MotorBrakeModeBrake);
    vexDeviceMotorEncoderUnitsSet(motor, kMotorEncoderDegrees);

    /* 转 500ms 然后停 */
    vexDeviceMotorVelocitySet(motor, 50);
    vexDelay(500);
    vexDeviceMotorVelocitySet(motor, 0);

    /* Brain 屏幕 —— 走 JHYY 绑定面的非变参封装，不直接调变参的 vexDisplayPrintf。
     * A 路与 B 路调的是同一个符号 jhyy_vex_display_puts（见 include/jhyy_vex.h）。 */
    jhyy_vex_display_puts(1, 1, "day0-c alive");

    /* 主循环必须带 wait/延时：main 是被 vexTaskAdd 注册进固件调度器的
     * 一个 task，不让出时间片会顶掉别的 task 的时间片。 */
    for (;;) {
        vexDelay(100);
    }

    return 0;
}
