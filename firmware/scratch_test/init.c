/* Original Hearth supervised scratch transaction userspace (MIT).
 * No libc, shell, executable uploads, native applications or network.
 */
#include "scratch-protocol.h"

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
static unsigned char snapshot[HS_WIRE_BYTES];
static long pause_time[2] = {0, 10000000};

/* The operation is one-shot even after errors/disconnection; no automatic retry
 * and no write occurs merely because the gadget enumerates or sends bytes.
 */
static int transfer(long fd, unsigned char *bytes, unsigned int len, int sending)
{
    unsigned int done = 0, waits = 0;
    long result;
    while (done < len && waits < 6000) {
        result = call5(sending ? 4 : 3, fd, (long)(bytes + done), len - done, 0, 0);
        if (result > 0) done += result;
        else if (result == -11 || result == -4 || (!sending && result == 0)) {
            ++waits;
            call5(162, (long)pause_time, 0, 0, 0, 0);
        } else return -1;
    }
    return done == len ? 0 : -1;
}
static long command(unsigned char *data, unsigned int len)
{
    long fd, result;
    fd = call5(5, (long)"/sys/class/mtd/mtd0/hearth_scratch_control", 1, 0, 0, 0);
    if (fd < 0) return fd;
    result = call5(4, fd, (long)data, len, 0, 0);
    call5(6, fd, 0, 0, 0, 0);
    return result;
}
static int read_snapshot(void)
{
    unsigned int done = 0, size;
    long fd, got;
    fd = call5(5, (long)"/sys/class/mtd/mtd0/hearth_scratch_snapshot", 0, 0, 0, 0);
    if (fd < 0) return -1;
    while (done < HS_WIRE_BYTES) {
        size = HS_WIRE_BYTES - done;
        if (size > 4096) size = 4096;
        got = call5(3, fd, (long)(snapshot + done), size, 0, 0);
        if (got != (long)size) {
            call5(6, fd, 0, 0, 0, 0);
            return -1;
        }
        done += got;
    }
    call5(6, fd, 0, 0, 0, 0);
    return 0;
}
static int send_snapshot(long fd, unsigned int stage)
{
    unsigned char header[HS_WIRE_HEADER];
    hs_wire_header(header, stage, snapshot);
    return transfer(fd, header, sizeof(header), 1) ||
           transfer(fd, snapshot, HS_WIRE_BYTES, 1);
}
static int equal(const unsigned char *a, const unsigned char *b, unsigned int len)
{
    unsigned int i;
    for (i = 0; i < len; ++i) if (a[i] != b[i]) return 0;
    return 1;
}
void __attribute__((noreturn)) _start(void)
{
    unsigned char token[40];
    unsigned int tries;
    long fd = -1, interval[2] = {1, 0};
    call5(21, (long)"proc", (long)"/proc", (long)"proc", 10, 0);
    call5(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 10, 0);
    call5(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10, (long)"mode=0755");
    /* Preparation reads/hash only. A failed prepare is reported if possible,
     * but can never pass the kernel's READY/digest gate for execution.
     */
    command((unsigned char *)"PREPARE\n", 8);
    if (!read_snapshot()) {
        for (tries = 0; tries < 60 && fd < 0; ++tries) {
            fd = call5(5, (long)"/dev/ttyGS0", 2 | 0400 | 04000, 0, 0, 0);
            if (fd < 0) call5(162, (long)interval, 0, 0, 0, 0);
        }
        if (fd >= 0 && !transfer(fd, token, 8, 0) &&
            equal(token, (const unsigned char *)"HSBEGIN1", 8) && !send_snapshot(fd, 1) &&
            !transfer(fd, token, 40, 0) && equal(token, (const unsigned char *)"HSACK001", 8)) {
            /* The kernel owns all checks and completes cleanup synchronously
             * before USB result transmission. Never depend on a later host
             * command to erase/restore after programming.
             */
            command(token, 40);
            if (!read_snapshot()) send_snapshot(fd, 2);
        }
        if (fd >= 0) call5(6, fd, 0, 0, 0, 0);
    }
    for (;;) call5(162, (long)interval, 0, 0, 0, 0);
}
