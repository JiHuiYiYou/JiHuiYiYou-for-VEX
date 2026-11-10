/* main.cpp —— **C++ 参考**（Day 3 行为对照的第三份程序）
 *
 * 同一段逻辑的**另一种写法**：
 *   - A 路：JHYY 源 `cmp.jhyy` → AST → C → clang
 *   - B 路：JHYY 源 `cmp.jhyy` → AST → ARM 汇编 → clang   ← **与 A 路同一份源码**
 *   - C++：这个文件（C++ / vex:: 类）—— 像 7262A 那样写
 *
 * ⇒ 三条路在 Brain 上跑出**同样的屏显** + **同样的电机动作**。
 *
 * ⚠️ 为什么"配置"用 vex:: 类、而"测量"用 C API：
 *   - vex:: 类（`vex::motor`）是 7262A 那种**工程写法** ⇒ 拿它当参照才有意义；
 *   - 但 `vex::motor` **没有**编码器单位（encoder units）的接口，
 *     而"实测速度"必须三条路用**同一个** API 才有可比性
 *     ⇒ 这两处走纯 C 的 `vexDevice*`（JHYY 绑的就是它）。
 *   - 屏显走**同一个绑定面符号** `jhyy_vex_display_puts`（非变参封装）
 *     ⇒ 比的是「JHYY 怎么编译」，不是「屏显 API 怎么用」。
 */

#include "v5_cpp.h"
#include "jhyy_vex.h"

int main(void)
{
    /* ① 句柄（索引 0 = PORT1）—— 与 JHYY 源同一步 */
    V5_DeviceT dev = vexDeviceGetByIndex(0);

    /* ② 配置：18:1 / Brake / Degrees
     *    - 齿轮组：vex::motor 的构造函数带 gearSetting（工程里最常见的写法）
     *    - 刹车：vex::motor::setBrake
     *    - 编码器单位：vex:: 层**没有**这个接口 ⇒ 走纯 C
     */
    vex::motor motor(vex::PORT1, vex::gearSetting::ratio18_1);
    motor.setBrake(vex::brakeType::brake);
    vexDeviceMotorEncoderUnitsSet(dev, kMotorEncoderDegrees);

    /* ③ 转 500 ms（速度单位 = RPM，事实基线 § 9.7 实测） */
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(500);

    /* ④ 读**实测**速度（绝对编码器，RPM）—— 与 JHYY 源**同一个** API */
    int32_t v = vexDeviceAbsEncVelocityGet(dev);

    /* ⑤ 读回刹车模式（★ enum 返回 ⇒ 高位未定义；JHYY 的 B 路要掩码 0xff） */
    int32_t brake = (int32_t)vexDeviceMotorBrakeModeGet(dev);

    /* ⑥ 停机 */
    vexDeviceMotorVelocitySet(dev, 0);

    /* ⑦ 屏显两行 —— 与 JHYY 源**同样的字** */
    if (v > 20 || v < -20) {
        jhyy_vex_display_puts(1, 1, "MOTOR MOVED");
    } else {
        jhyy_vex_display_puts(1, 1, "MOTOR DID NOT MOVE");
    }
    if (brake == 1) {
        jhyy_vex_display_puts(1, 20, "BRAKE READBACK OK");
    } else {
        jhyy_vex_display_puts(1, 20, "BRAKE READBACK BAD");
    }

    /* main 是被 vexTaskAdd 注册进固件调度器的**一个 task** ⇒ 必须让出时间片 */
    for (;;) {
        vexDelay(100);
    }

    return 0;
}
