/* jhyy_vex.h —— **复用** day0-c 里那一份绑定面，不复制第二份
 *
 * 为什么要共享：绑定面是「改一处 = 改两路」的东西（事实基线 § 9.2）。
 * 两份拷贝必然漂移 —— 所以这里直接引 day0-c 的那一份。
 *
 * 被引用的原件：
 *   - 头文件：`spike/day0-c/include/jhyy_vex.h`
 *   - 实现：  `spike/day0-c/src/jhyy_vex.c`
 */

#include "../../day0-c/include/jhyy_vex.h"
