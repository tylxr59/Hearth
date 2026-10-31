/* Original Hearth contract-metadata RAM userspace (MIT). No libc, shell or commands.
 * Reads one fixed read-only sysfs attribute; never opens a flash device or file.
 */
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

static char report[1536];
static unsigned int append(unsigned int offset, const char *value)
{
    while (*value && offset < sizeof(report) - 1)
        report[offset++] = *value++;
    return offset;
}

static unsigned int make_report(void)
{
    unsigned int offset;
    long fd, count;
    char value[1024];
    offset = append(0, "HEARTH_NAND_CONTRACT_V1\n");
    fd = call5(5, (long)"/sys/class/mtd/mtd0/hearth_contract", 0, 0, 0, 0);
    count = -1;
    if (fd >= 0) {
        count = call5(3, fd, (long)value, sizeof(value)-1, 0, 0);
        call5(6, fd, 0, 0, 0, 0);
    }
    if (count > 0 && count < (long)sizeof(value)-1) {
        value[count] = 0;
        offset = append(offset, value);
    }

    return append(offset, "END_HEARTH_NAND_CONTRACT\n");
}

void __attribute__((noreturn)) _start(void)
{
    long fd, written;
    unsigned int offset, length;
    long interval[2] = { 1, 0 };
    call5(21, (long)"proc", (long)"/proc", (long)"proc", 10, 0);
    call5(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 10, 0);
    call5(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10,
          (long)"mode=0755");
    for (;;) {
        length = make_report();
        fd = call5(5, (long)"/dev/ttyGS0", 1 | 0400 | 04000, 0, 0, 0);
        if (fd >= 0) {
            offset = 0;
            while (offset < length) {
                written = call5(4, fd, (long)(report + offset), length - offset, 0, 0);
                if (written <= 0)
                    break;
                offset += written;
            }
            call5(6, fd, 0, 0, 0, 0);
        }
        call5(162, (long)interval, 0, 0, 0, 0);
    }
}
