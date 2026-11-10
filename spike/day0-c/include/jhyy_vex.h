/* jhyy_vex.h —— JHYY 的 VEX 绑定面（第 0 步实测产物）
 *
 * 这个头文件里的每个声明，都是 JHYY 侧 `extern fn` 要**逐字对应**的符号：
 * 名字、参数个数、参数类型、返回类型 —— 一一对应，不多不少。
 * 改这里 = 改绑定面 = 同时改 A 路与 B 路。
 *
 * ⚠️ 为什么需要这一层（不是"胶水"，是绑定面本身）：
 *
 *   1. VEX 的屏显 API **全是变参**（vexDisplayPrintf / vexDisplayStringAt …）。
 *      而 JHYY **不支持变参调用**（ABI v4.0.0 § 6 FFI：变参函数不支持）。
 *      ⇒ A 路（JHYY → C → clang）与 B 路（JHYY → ARM 机器码）**都不能**
 *        直接调变参函数 —— A 路能"调"只是因为 clang 帮它把变参调用展开了，
 *        那恰恰是两路会分叉的地方。
 *      ⇒ 必须有一层**非变参**封装，两路调**同一个符号**、**同一份语义**。
 *
 *   2. VEX 的 C API 里存在**按值传/返回 struct** 的函数
 *      （只有 V5_DeviceVisionRgb 一个，见事实基线 § 8.1）。
 *      JHYY 的 FFI **不支持 struct 按值跨边界** ⇒ 这类函数**不能直接绑**。
 *      ⇒ 最小绑定面里不出现它们（本来也不需要）。
 */

#ifndef JHYY_VEX_H
#define JHYY_VEX_H

#include "v5.h"

/* ⚠️ `extern "C"` 守卫：**C++ 参考程序**（Day 3 行为对照）也要调这个符号。
 *    没有守卫的话，C++ 会给 `jhyy_vex_display_puts` 加修饰
 *    （Itanium mangling）⇒ 链接时找不到 C 侧那个符号。
 *    ⚠️ 对 **C** 编译时这段是空的 ⇒ 产物（`jhyy_vex.o`）逐字节不变 ✓
 */
#ifdef __cplusplus
extern "C" {
#endif

/* Brain 屏：在 (xpos, ypos) 处画一行 text。
 *
 * 签名固定、非变参 ⇒ JHYY 侧：
 *     extern fn jhyy_vex_display_puts(xpos: i32, ypos: i32, text: *u8);
 *
 * 实现里走的是 VEX 的变参 API，但**变参只发生在 C 内部** ——
 * JHYY 从头到尾只看到一个三参数的普通函数。
 *
 * ⚠️ **坐标单位 = 像素**（实测）：屏幕 480×272（SDK 常量
 * `SYSTEM_DISPLAY_WIDTH/HEIGHT`），原点左上、x 右 y 下；
 * 文字坐标也是**像素**（不是字符格）—— 实机：字母紧接在 10 像素宽的方块右缘。
 *
 * bOpaque 固定 **1**（不透明背景，理由见实现里的注释与事实基线 § 9.6）。
 */
void jhyy_vex_display_puts(int32_t xpos, int32_t ypos, const char *text);

#ifdef __cplusplus
}
#endif

#endif /* JHYY_VEX_H */
