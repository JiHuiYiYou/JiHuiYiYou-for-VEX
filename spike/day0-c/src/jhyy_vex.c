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
    /* bOpaque = 1（实测定的，见事实基线 § 9.4 / § 9.6）：
     *   bOpaque=0 是**透明** —— 字框里原来的东西还在，
     *     而默认前景色是白色 ⇒ 白字压在白块上 = **看不见**（实机踩过）。
     *   bOpaque=1 会用**背景色**把字框填掉 ⇒ 白字黑底，**永远可读**，
     *     语义上也更像"打印"（终端行为）。
     *   ⇒ 绑定面选 1；想要"叠加透明版"以后另开一个函数（最小绑定面不许扩）。 */
    vexDisplayPrintf(xpos, ypos, 1, "%s", text);
}
