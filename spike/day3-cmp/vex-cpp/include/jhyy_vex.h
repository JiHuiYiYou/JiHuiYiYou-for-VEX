/* jhyy_vex.h —— **共享**绑定面：与 `spike/day0-c` 是同一份实现
 *
 * ⚠️ 为什么要"引"而不是"复制"：
 *    绑定面是「改一处 = 改两路」的东西（事实基线 § 9.2）。
 *    两份拷贝必然漂移 ⇒ 这里直接引 day0-c 那份。
 *
 * 被引用的原件：`spike/day0-c/include/jhyy_vex.h`
 */
#include "../../../day0-c/include/jhyy_vex.h"
