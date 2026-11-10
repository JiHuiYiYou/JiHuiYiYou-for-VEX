/* runner.c —— host 侧的 runner：跑 JHYY 程序（生成的 C）+ 打轨迹
 *
 * 用法：
 *   gcc -Dmain=jhyy_main -I spike/vex-mock \
 *       生成的主机.c spike/vex-mock/vex_mock.c spike/vex-mock/runner.c -o prog
 *   ./prog > trace.txt
 *
 * ⚠️ 生成的 C 的 `main` 被 `-Dmain=jhyy_main` 改名 ⇒ 这里由 runner 提供真 main。
 */

#include "vex_mock.h"
#include <stdio.h>
#include <stdlib.h>

extern int jhyy_main(void);      /* 生成的 C 的 main（改名后） */

int main(int argc, char **argv)
{
    /* 模拟时钟上限：默认 5000 ms；命令行第一个参数可改（毫秒） */
    if (argc > 1) vex_mock_max_ms = atof(argv[1]);

    vex_mock_reset();
    int rc = jhyy_main();        /* 正常情况下走不到（程序末尾是死循环） */
    fprintf(stderr, "[runner] 程序自己返回了 rc=%d\n", rc);
    vex_mock_dump_screen(stderr);
    return 0;
}
