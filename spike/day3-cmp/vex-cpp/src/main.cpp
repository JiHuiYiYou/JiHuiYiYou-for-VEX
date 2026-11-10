/* main.cpp —— **C++ 参考**（Day 3 行为对照的第三份程序）
 *
 * 同一段逻辑的**另一种写法**：
 *   - A 路：JHYY 源 `cmp.jhyy` → AST → C → clang
 *   - B 路：JHYY 源 `cmp.jhyy` → AST → ARM 汇编 → clang   ← **与 A 路同一份源码**
 *   - C++：  这个文件（C++ / `vex::` 类）—— 像 7262A 那样写
 *
 * ⇒ 三条路在 Brain 上跑出**同样的屏显** + **同样的电机动作**。
 *
 * ⚠️ **为什么屏显要走 `jhyy_vex_display_puts`**（而不是直接调变参的
 *    `vexDisplayPrintf`）：三条路调**同一个符号**、**同一份语义**
 *    ⇒ 屏显有差异就一定是**编译**的差异，不是 API 层的差异。
 *
 * ⚠️ **为什么配置用 `vex::` 类**（像 7262A 那样）：因为这一路要回答的是
 *    「同一段逻辑，换个语言、换个 API 层写法，行为是不是一样」。
 *    而**读回**（刹车/编码器单位/齿轮组）统一走纯 C 的 `vexDevice*` ——
 *    JHYY 绑的就是它 ⇒ 三条路读的是**同一个**状态。
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
     *    ⚠️ 顺序：配置**必须在**置反转标志之前（反了标志可能被清）
     */
    vex::motor motor(vex::PORT1, vex::gearSetting::ratio18_1);
    motor.setBrake(vex::brakeType::brake);
    vexDeviceMotorEncoderUnitsSet(dev, kMotorEncoderDegrees);

    /* ③ 读回三个配置（★ enum 返回 ⇒ 高位未定义；JHYY 的 B 路要掩码 0xff） */
    int32_t brake = (int32_t)vexDeviceMotorBrakeModeGet(dev);
    int32_t enc   = (int32_t)vexDeviceMotorEncoderUnitsGet(dev);
    int32_t gear  = (int32_t)vexDeviceMotorGearingGet(dev);

    /* ④ 转 500 ms，读**实测**速度（绝对编码器，RPM）—— 与 JHYY 源**同一个** API */
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(500);
    int32_t v = vexDeviceAbsEncVelocityGet(dev);
    vexDeviceMotorVelocitySet(dev, 0);

    /* ⑤ 反转标志实验：置上 → **再读一次** → 再转一次 → 看方向反没反
     *    ⚠️ 这正是上一轮探针测不出结论的原因（探针自己有 bug：置完标志又
     *       config 了一遍，把标志清了）⇒ 这里 config 在前、spin 后再读标志。 */
    vexDeviceMotorReverseFlagSet(dev, true);
    bool flag = vexDeviceMotorReverseFlagGet(dev);
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(500);
    int32_t v2 = vexDeviceAbsEncVelocityGet(dev);
    vexDeviceMotorVelocitySet(dev, 0);
    vexDeviceMotorReverseFlagSet(dev, false);   // 复位，别把机器人留在反的

    /* ⑥ 四行结论 —— 与 JHYY 源**逐字相同** */
    if (v > 20 || v < -20) {
        jhyy_vex_display_puts(1, 1, "MOTOR MOVED");
    } else {
        jhyy_vex_display_puts(1, 1, "MOTOR NO MOVE");
    }
    if (brake == 1 && enc == 0 && gear == 1) {
        jhyy_vex_display_puts(1, 20, "CONFIG OK");
    } else {
        jhyy_vex_display_puts(1, 20, "CONFIG BAD");
    }
    if (flag) {
        if (v2 < 0) {
            jhyy_vex_display_puts(1, 40, "REVF FLIP");
        } else {
            jhyy_vex_display_puts(1, 40, "REVF SAME");
        }
    } else {
        jhyy_vex_display_puts(1, 40, "REVF NA");
    }
    jhyy_vex_display_puts(1, 60, "JHY CMP DONE");

    /* main 是被 vexTaskAdd 注册进固件调度器的**一个 task** ⇒ 必须让出时间片 */
    for (;;) {
        vexDelay(100);
    }

    return 0;
}
