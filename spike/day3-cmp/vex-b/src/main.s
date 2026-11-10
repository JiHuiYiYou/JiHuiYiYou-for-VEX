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
    sub sp, sp, #16
    movw r0, #0
    movt r0, #0
    push {r0}
    pop {r0}
    bl vexDeviceGetByIndex
    str r0, [sp, #0]
    ldr r0, [sp, #0]
    push {r0}
    movw r0, #1
    movt r0, #0
    push {r0}
    pop {r1}
    pop {r0}
    bl vexDeviceMotorGearingSet
    ldr r0, [sp, #0]
    push {r0}
    movw r0, #1
    movt r0, #0
    push {r0}
    pop {r1}
    pop {r0}
    bl vexDeviceMotorBrakeModeSet
    ldr r0, [sp, #0]
    push {r0}
    movw r0, #0
    movt r0, #0
    push {r0}
    pop {r1}
    pop {r0}
    bl vexDeviceMotorEncoderUnitsSet
    ldr r0, [sp, #0]
    push {r0}
    movw r0, #50
    movt r0, #0
    push {r0}
    pop {r1}
    pop {r0}
    bl vexDeviceMotorVelocitySet
    movw r0, #500
    movt r0, #0
    push {r0}
    pop {r0}
    bl vexDelay
    ldr r0, [sp, #0]
    push {r0}
    pop {r0}
    bl vexDeviceAbsEncVelocityGet
    str r0, [sp, #4]
    ldr r0, [sp, #0]
    push {r0}
    pop {r0}
    bl vexDeviceMotorBrakeModeGet
    and r0, r0, #0xff
    str r0, [sp, #8]
    ldr r0, [sp, #0]
    push {r0}
    movw r0, #0
    movt r0, #0
    push {r0}
    pop {r1}
    pop {r0}
    bl vexDeviceMotorVelocitySet
    ldr r0, [sp, #4]
    push {r0}
    movw r0, #20
    movt r0, #0
    pop {r1}
    cmp r0, r1
    mov r0, #0
    movgt r0, #1
    cmp r0, #0
    bne .L2_true
    ldr r0, [sp, #4]
    push {r0}
    movw r0, #20
    movt r0, #0
    rsb r0, r0, #0
    pop {r1}
    cmp r0, r1
    mov r0, #0
    movlt r0, #1
    cmp r0, #0
    bne .L2_true
    mov r0, #0
    b .L3_end
.L2_true:
    mov r0, #1
.L3_end:
    cmp r0, #0
    beq .L4_else
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #1
    movt r0, #0
    push {r0}
    ldr r0, =str0
    push {r0}
    pop {r2}
    pop {r1}
    pop {r0}
    bl jhyy_vex_display_puts
    b .L5_endif
.L4_else:
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #1
    movt r0, #0
    push {r0}
    ldr r0, =str1
    push {r0}
    pop {r2}
    pop {r1}
    pop {r0}
    bl jhyy_vex_display_puts
.L5_endif:
    ldr r0, [sp, #8]
    push {r0}
    movw r0, #1
    movt r0, #0
    pop {r1}
    cmp r0, r1
    mov r0, #0
    moveq r0, #1
    cmp r0, #0
    beq .L6_else
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #20
    movt r0, #0
    push {r0}
    ldr r0, =str2
    push {r0}
    pop {r2}
    pop {r1}
    pop {r0}
    bl jhyy_vex_display_puts
    b .L7_endif
.L6_else:
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #20
    movt r0, #0
    push {r0}
    ldr r0, =str3
    push {r0}
    pop {r2}
    pop {r1}
    pop {r0}
    bl jhyy_vex_display_puts
.L7_endif:
.L8_while:
    movw r0, #1
    movt r0, #0
    push {r0}
    movw r0, #0
    movt r0, #0
    pop {r1}
    cmp r0, r1
    mov r0, #0
    movne r0, #1
    cmp r0, #0
    beq .L9_endwhile
    movw r0, #100
    movt r0, #0
    push {r0}
    pop {r0}
    bl vexDelay
    b .L8_while
.L9_endwhile:
    movw r0, #0
    movt r0, #0
    ldm sp!, {r4-r11, pc}
    mov r0, #0
    ldm sp!, {r4-r11, pc}
    .size main, .-main
    .section .rodata
str0:
    .ascii "MOTOR MOVED"
    .byte 0
str1:
    .ascii "MOTOR DID NOT MOVE"
    .byte 0
str2:
    .ascii "BRAKE READBACK OK"
    .byte 0
str3:
    .ascii "BRAKE READBACK BAD"
    .byte 0
    .ltorg
