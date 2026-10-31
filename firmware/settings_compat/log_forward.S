/* Original AAPCS variadic forwarding: preserve all argument registers and the
 * caller's stack, then tail-call the original logger outside a storage write. */
.syntax unified
.arm
.text
.align 2
.global nlLogWithComponent
.type nlLogWithComponent,%function
nlLogWithComponent:
    push {r0-r3, r4, lr}
    bl hearth_settings_log_target
    mov ip, r0
    pop {r0-r3, r4, lr}
    cmp ip, #0
    bxne ip
    bx lr
.size nlLogWithComponent, .-nlLogWithComponent
.section .note.GNU-stack,"",%progbits
