/* main.cpp —— VEXcode GUI 工程的入口
 *
 * 探针本体是**纯 C**（`src/probe.c`），这里只做一件事：把入口接到 GUI 工程上。
 *
 * ⚠️ 为什么要有这一层：
 *    - VEXcode Pro V5 的工程入口是 `src/main.cpp`（C++）；
 *    - 而第 0 步的探针要保持"纯 C、零 JHYY 变量"（A 路 = JHYY → C → clang）；
 *    ⇒ C 那边的入口改名成 `probe_main`，这里用 `extern "C"` 接上。
 *
 * ⚠️ 链接期的入口符号**仍然叫 `main`、且不带修饰** ——
 *    SDK 的 `vexMain` 用 `R_ARM_ABS32 main` 取用户 main 的地址
 *    （事实基线 § 9.3）。这是硬要求，B 路也必须遵守。
 */

extern "C" void probe_main(void);

int main(void)
{
    probe_main();
    return 0;
}
