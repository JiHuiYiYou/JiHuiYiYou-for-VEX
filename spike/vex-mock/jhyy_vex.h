/* jhyy_vex.h —— **host 侧的绑定面声明**（= mock 实现的那 13 个函数）
 *
 * ⚠️ 真 SDK 那份在 `spike/day0-c/include/jhyy_vex.h`（只有屏显封装一个函数）。
 *    这份是**桌面 mock**用的：把**绑定面表里的 13 个函数**全部声明出来，
 *    让**生成的 C 一个字都不用改**就能在 host 上编、跑。
 *
 * ★ 原型与 SDK **逐字相同**（事实基线 § 9.2）⇒ 生成的 C 里的原型不会冲突。
 */

#ifndef VEX_MOCK_JHYY_VEX_H
#define VEX_MOCK_JHYY_VEX_H

#include "v5.h"

V5_DeviceT vexDeviceGetByIndex(uint32_t index);
void vexDeviceMotorGearingSet(V5_DeviceT device, V5MotorGearset value);
void vexDeviceMotorBrakeModeSet(V5_DeviceT device, V5MotorBrakeMode mode);
void vexDeviceMotorEncoderUnitsSet(V5_DeviceT device, V5MotorEncoderUnits units);
void vexDeviceMotorVelocitySet(V5_DeviceT device, int32_t velocity);
V5MotorBrakeMode vexDeviceMotorBrakeModeGet(V5_DeviceT device);
V5MotorEncoderUnits vexDeviceMotorEncoderUnitsGet(V5_DeviceT device);
V5MotorGearset vexDeviceMotorGearingGet(V5_DeviceT device);
void vexDeviceMotorReverseFlagSet(V5_DeviceT device, bool value);
bool vexDeviceMotorReverseFlagGet(V5_DeviceT device);
int32_t vexDeviceAbsEncVelocityGet(V5_DeviceT device);
void vexDelay(uint32_t timems);
void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);

#endif /* VEX_MOCK_JHYY_VEX_H */
