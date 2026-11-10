/* 由 spike/route-b/asm_emit.py 从 `jhyy dump` 的 AST 生成 —— 不要手改。
 * 探针，不是产品（验收线 § 3.1）。
 * 目标：VEX V5 Brain（ARMv7-A，ARM 态）· AAPCS · 整数子集（softfp 天然满足）。
 */
    .syntax unified
    .arm
    .text
    .global main
    .type main, %function
main:
    push {r4-r11, lr}
    sub sp, sp, #8
    ldr r0, =str0
    str r0, [sp, #0]
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #1
    movt r0, #0
    push {r0}
    ldr r0, [sp, #0]
    push {r0}
    pop {r2}
    pop {r1}
    pop {r0}
    bl jhyy_vex_display_puts
    movw r0, #500
    movt r0, #0
    push {r0}
    pop {r0}
    bl vexDelay
    movw r0, #0
    movt r0, #0
    ldm sp!, {r4-r11, pc}
    mov r0, #0
    ldm sp!, {r4-r11, pc}
    .size main, .-main
    .section .rodata
str0:
    .ascii "jhyy on vex\n"
    .byte 0
    .ltorg
