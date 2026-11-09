/* robot-config.h —— VEXcode 生成的设备配置头（空壳）
 *
 * 本工程**不添加任何 VEXcode 设备对象** —— 探针直接用纯 C API
 * （`vexDeviceGetByIndex` 等），刻意不碰 C++ 的 `vex::` 类那一层
 * （事实基线 § 8：绑定面只对纯 C API）。
 *
 * 所以这里只有 VEXcode 固定的那一段。
 */

using namespace vex;

/**
 * Used to initialize code/tasks/devices added using tools in VEXcode Pro.
 *
 * This should be called at the start of your int main function.
 */
void  vexcodeInit( void );
