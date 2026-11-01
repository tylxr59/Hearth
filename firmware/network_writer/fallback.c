/* Original inert fallback (MIT). Kernel is write-capable but this program
 * never opens its gate or mounts flash. No host command is accepted. */

static long call5(long number, long a, long b, long c, long d, long e)
{
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    register long r7 __asm__("r7") = number;
    __asm__ volatile ("svc 0" : "+r"(r0)
                      : "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r7)
                      : "memory", "cc");
    return r0;
}

static void pause_one_second(void)
{
    long interval[2] = { 1, 0 };
    call5(162, (long)interval, 0, 0, 0, 0); /* nanosleep */
}

void __attribute__((noreturn)) _start(void)
{
    static const char heartbeat[] =
        "HEARTH_NETWORK_WRITER_FALLBACK_V1\n"
        "commands=none\n"
        "writes=not_requested\n"
        "END_HEARTH_NETWORK_WRITER_FALLBACK\n";
    long fd, n, offset;

    /* Directories are part of our private initramfs. Mount only virtual RAM
     * filesystems. No filesystem from the thermostat's flash is mounted.
     * Linux ARM syscall 21 = mount. Flags: nosuid | noexec.
     */
    call5(21, (long)"proc", (long)"/proc", (long)"proc", 10, 0);
    call5(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 10, 0);
    call5(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10,
          (long)"mode=0755");

    for (;;) {
        /* open: write-only, no controlling terminal, nonblocking. A missing
         * USB host never sends us into stock startup or a flash fallback.
         */
        fd = call5(5, (long)"/dev/ttyGS0", 1 | 0400 | 04000, 0, 0, 0);
        if (fd >= 0) {
            offset = 0;
            while (offset < (long)sizeof(heartbeat) - 1) {
                n = call5(4, fd, (long)(heartbeat + offset),
                          sizeof(heartbeat) - 1 - offset, 0, 0);
                if (n > 0)
                    offset += n;
                else
                    break;
            }
            call5(6, fd, 0, 0, 0, 0); /* close */
        }
        pause_one_second();
    }
}
