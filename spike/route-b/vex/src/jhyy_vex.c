/* jhyy_vex.c —— **共享**绑定面：与 `spike/day0-c` 是同一份实现
 *
 * ⚠️ 同 `include/jhyy_vex.h`：绑定面只有一份真相（事实基线 § 9.2）。
 *    ⇒ 编译出来的 `jhyy_vex_display_puts` 与黄金参考**逐字节相同**
 *    （A 路、C 路、B 路三条路的 `.o` 都是同一份字节）。
 *
 * 被引用的原件：`spike/day0-c/src/jhyy_vex.c`
 */
#include "../../../day0-c/src/jhyy_vex.c"
