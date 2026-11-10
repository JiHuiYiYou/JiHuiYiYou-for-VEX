/* v5.h —— **host 侧的 v5.h**（只声明绑定面用到的那些 SDK 类型）
 *
 * ⚠️ **这不是 SDK 的头文件**，是给**桌面 mock**用的最小替身：
 *   生成的 C 里 `#include "v5.h"` ⇒ 在 host 上编译时用 `-I spike/vex-mock`
 *   把它解析到这个文件 ⇒ **生成的 C 一个字都不用改**。
 *
 * ★ 类型名与 SDK **逐字相同** ⇒ 生成的原型不用改一个字就能编过。
 *   （枚举成员的**值**也逐字相同 —— 事实基线 § 9.2.2 的序号表。）
 *
 * ⚠️ 只覆盖**绑定面表**里的 13 个函数用到的类型；
 *    需要更多时按 SDK 的 `v5_apitypes.h` 补（值要一致）。
 */

#ifndef VEX_MOCK_V5_H
#define VEX_MOCK_V5_H

#include <stdint.h>
#include <stdbool.h>

/* 设备：host 侧就是 mock 的假电机（见 vex_mock.c） */
typedef struct _V5_Device {
    int32_t port;
    int32_t cmd_velocity;
    double  velocity;
    double  position;
    int32_t brake_mode;
    int32_t enc_units;
    int32_t gear;
    int32_t rev_flag;
} V5_Device;

typedef V5_Device *V5_DeviceT;

/* 枚举（**值与 SDK 逐字相同**，事实基线 § 9.2.2） */
typedef enum {
    kMotorGearSet_36 = 0,
    kMotorGearSet_18 = 1,
    kMotorGearSet_06 = 2
} V5MotorGearset;

typedef enum {
    kV5MotorBrakeModeCoast = 0,
    kV5MotorBrakeModeBrake = 1,
    kV5MotorBrakeModeHold = 2
} V5MotorBrakeMode;

typedef enum {
    kMotorEncoderDegrees = 0,
    kMotorEncoderRotations = 1,
    kMotorEncoderCounts = 2
} V5MotorEncoderUnits;

#endif /* VEX_MOCK_V5_H */
