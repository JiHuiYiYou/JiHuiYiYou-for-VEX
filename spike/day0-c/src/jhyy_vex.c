/* jhyy_vex.c —— JHYY 绑定面的 C 实现（见 include/jhyy_vex.h）
 *
 * 这个 .o 由 clang 产出，**A 路与 B 路链的是同一个**。
 * 两路的差别只在「JHYY 自己那部分代码怎么来」，
 * 到了调用 VEX API 这一层，走的是同一个符号、同一条指令序列。
 */

#include "jhyy_vex.h"

void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text)
{
    /* "%s" —— text 是**数据**不是格式串，所以 text 里带 '%' 也不会出事。 */
    vexDisplayPrintf(xpos, ypos, 0, "%s", text);
}
