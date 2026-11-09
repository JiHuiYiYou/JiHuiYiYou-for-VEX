/* jhyy_vex.c —— 直接编译 day0-c 里那一份实现（不复制第二份）
 *
 * 被引用的原件：`spike/day0-c/src/jhyy_vex.c`
 *
 * ⚠️ 为什么这个探针要用绑定面，而不是直接调 vexDisplayPrintf：
 *    `jhyy_vex_display_puts` 是**两路要调的同一个符号**（事实基线 § 9.4）。
 *    探针在实机上跑它 ⇒ B 阶段才知道这个符号在 Brain 上真的能用。
 */

#include "../../day0-c/src/jhyy_vex.c"
