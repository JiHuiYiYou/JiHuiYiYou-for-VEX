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
extern int32_t vexDeviceAbsEncVelocityGet(V5_DeviceT device);
extern void vexDelay(uint32_t timems);
extern void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);
int main(void) {
    V5_DeviceT dev = vexDeviceGetByIndex(0);
    vexDeviceMotorGearingSet(dev, 1);
    vexDeviceMotorBrakeModeSet(dev, 1);
    vexDeviceMotorEncoderUnitsSet(dev, 0);
    vexDeviceMotorVelocitySet(dev, 50);
    vexDelay(((uint32_t)500));
    int32_t v = vexDeviceAbsEncVelocityGet(dev);
    V5MotorBrakeMode brake = vexDeviceMotorBrakeModeGet(dev);
    vexDeviceMotorVelocitySet(dev, 0);
    if (((v > 20) || (v < (-(20))))) {
        jhyy_vex_display_puts(1, 1, ((char *)"MOTOR MOVED"));
    }
    else {
        jhyy_vex_display_puts(1, 1, ((char *)"MOTOR DID NOT MOVE"));
    }
    if (brake == 1) {
        jhyy_vex_display_puts(1, 20, ((char *)"BRAKE READBACK OK"));
    }
    else {
        jhyy_vex_display_puts(1, 20, ((char *)"BRAKE READBACK BAD"));
    }
    while (1 != 0) {
        vexDelay(((uint32_t)100));
    }
    return 0;
}
