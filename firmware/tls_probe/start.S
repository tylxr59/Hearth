/* Original ARM EABI entry: pass the initial argv and loader finalizer to libc.
 * The helper has no executable/shared-library constructors of its own. */
.syntax unified
.arm
.text
.global _start
.type _start, %function
_start:
    mov fp, #0
    mov lr, #0
    mov r5, r0
    ldr r1, [sp], #4
    mov r2, sp
    bic sp, sp, #7
    sub sp, sp, #16
    mov r3, #0
    str r3, [sp]
    str r5, [sp, #4]
    str r2, [sp, #8]
    ldr r0, =main
    bl __libc_start_main
    mov r7, #248
    mov r0, #127
    svc #0
.size _start, .-_start
.section .note.GNU-stack,"",%progbits
