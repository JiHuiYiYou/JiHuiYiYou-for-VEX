/* 由 spike/day1-emit/emit_c.py 从 `jhyy dump` 的 AST 生成 —— 不要手改。
 * 探针，不是产品（验收线 § 3.1）。
 */
#include "v5.h"
#include "jhyy_vex.h"
#include <stdint.h>
#include <stdbool.h>

extern V5_DeviceT vexDeviceGetByIndex(uint32_t index);
extern void vexDeviceMotorGearingSet(V5_DeviceT device, V5MotorGearset value);
extern void vexDeviceMotorBrakeModeSet(V5_DeviceT device, V5MotorBrakeMode mode);
extern void vexDeviceMotorEncoderUnitsSet(V5_DeviceT device, V5MotorEncoderUnits units);
extern void vexDeviceMotorVelocitySet(V5_DeviceT device, int32_t velocity);
extern V5MotorBrakeMode vexDeviceMotorBrakeModeGet(V5_DeviceT device);
extern V5MotorEncoderUnits vexDeviceMotorEncoderUnitsGet(V5_DeviceT device);
extern V5MotorGearset vexDeviceMotorGearingGet(V5_DeviceT device);
extern void vexDeviceMotorReverseFlagSet(V5_DeviceT device, bool value);
extern bool vexDeviceMotorReverseFlagGet(V5_DeviceT device);
extern int32_t vexDeviceAbsEncVelocityGet(V5_DeviceT device);
extern void vexDelay(uint32_t timems);
extern void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);
int main(void) {
    V5_DeviceT dev = vexDeviceGetByIndex(0);
    vexDeviceMotorGearingSet(dev, 1);
    vexDeviceMotorBrakeModeSet(dev, 1);
    vexDeviceMotorEncoderUnitsSet(dev, 0);
    V5MotorBrakeMode brake = vexDeviceMotorBrakeModeGet(dev);
    V5MotorEncoderUnits enc = vexDeviceMotorEncoderUnitsGet(dev);
    V5MotorGearset gear = vexDeviceMotorGearingGet(dev);
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(((uint32_t)500));
    int32_t v = vexDeviceAbsEncVelocityGet(dev);
    vexDeviceMotorVelocitySet(dev, 0);
    vexDeviceMotorReverseFlagSet(dev, true);
    bool flag = vexDeviceMotorReverseFlagGet(dev);
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(((uint32_t)500));
    int32_t v2 = vexDeviceAbsEncVelocityGet(dev);
    vexDeviceMotorVelocitySet(dev, 0);
    vexDeviceMotorReverseFlagSet(dev, false);
    if (((v > 20) || (v < (-(20))))) {
        jhyy_vex_display_puts(1, 1, ((char *)"MOTOR MOVED"));
    }
    else {
        jhyy_vex_display_puts(1, 1, ((char *)"MOTOR NO MOVE"));
    }
    if ((((brake == 1) && (enc == 0)) && (gear == 1))) {
        jhyy_vex_display_puts(1, 20, ((char *)"CONFIG OK"));
    }
    else {
        jhyy_vex_display_puts(1, 20, ((char *)"CONFIG BAD"));
    }
    if (flag) {
        if ((v2 < 0)) {
            jhyy_vex_display_puts(1, 40, ((char *)"REVF FLIP"));
        }
        else {
            jhyy_vex_display_puts(1, 40, ((char *)"REVF SAME"));
        }
    }
    else {
        jhyy_vex_display_puts(1, 40, ((char *)"REVF NA"));
    }
    jhyy_vex_display_puts(1, 60, ((char *)"JHY CMP DONE"));
    while (1 != 0) {
        vexDelay(((uint32_t)100));
    }
    return 0;
}
