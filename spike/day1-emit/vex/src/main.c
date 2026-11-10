/* 由 spike/day1-emit/emit_c.py 从 `jhyy dump` 的 AST 生成 —— 不要手改。
 * 探针，不是产品（验收线 § 3.1）。
 */
#include "v5.h"
#include "jhyy_vex.h"
#include <stdint.h>
#include <stdbool.h>

extern void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);
extern void vexDelay(uint32_t timems);
int main(void) {
    char * msg = ((char *)"jhyy on vex\n");
    jhyy_vex_display_puts(1, 1, msg);
    vexDelay(((uint32_t)500));
    return 0;
}
