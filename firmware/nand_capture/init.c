/* Original Hearth fixed whole-chip raw export (MIT). No shell or flash writes. */
#include "sample-protocol.h"

#ifdef HEARTH_CAPTURE_HOST_TEST
static long call5(long number, long a, long b, long c, long d, long e);
#else
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
#endif

static unsigned char data[SAMPLE_RECORD];

static int send_all(long fd, const unsigned char *bytes, unsigned int size)
{
    unsigned int offset = 0, retries = 0;
    long result, pause[2] = { 0, 10000000 };
    while (offset < size) {
        result = call5(4, fd, (long)(bytes + offset), size - offset, 0, 0);
        if (result > 0)
            offset += result;
        else if ((result == -11 || result == -4) && retries++ < 500)
            call5(162, (long)pause, 0, 0, 0, 0);
        else
            return -1;
    }
    return 0;
}

static int wait_start(long fd)
{
    static const unsigned char start[8] = { 'H','R','T','H','G','O','1','\n' };
    unsigned int matched = 0, ticks = 0, received = 0;
    unsigned char byte;
    long result, pause[2] = { 0, 10000000 };
    while (ticks < 30000 && received < 4096) {
        result = call5(3, fd, (long)&byte, 1, 0, 0);
        if (result == 1) {
            received++;
            matched = byte == start[matched] ? matched + 1 : (byte == start[0] ? 1 : 0);
            if (matched == sizeof(start))
                return 0;
        } else if (result == -11 || result == -4) {
            ticks++;
            call5(162, (long)pause, 0, 0, 0, 0);
        } else {
            return -1;
        }
    }
    return -1;
}

static int export_once(long serial)
{
    unsigned int pass, page, i;
    unsigned char header[SAMPLE_HEADER];
    static const unsigned char end[8] = { 'H','R','T','H','E','N','D','1' };
    long nand, count;
    for (pass = 0; pass < SAMPLE_PASSES; pass++) {
        nand = call5(5, (long)"/sys/class/mtd/mtd0/hearth_raw", 0, 0, 0, 0);
        if (nand < 0)
            return -1;
        for (page = 0; page < SAMPLE_PAGES; page++) {
            count = call5(3, nand, (long)data, SAMPLE_RECORD, 0, 0);
            if (count != SAMPLE_RECORD) {
                call5(6, nand, 0, 0, 0, 0);
                return -1;
            }
            sample_header(header, pass, page, data);
            if (send_all(serial, header, sizeof(header)) || send_all(serial, data, sizeof(data))) {
                call5(6, nand, 0, 0, 0, 0);
                return -1;
            }
        }
        call5(6, nand, 0, 0, 0, 0);
    }
    for (i = 0; i < sizeof(end); i++)
        header[i] = end[i];
    sample_u32(header + 8, 1);
    sample_u32(header + 12, SAMPLE_PASSES);
    sample_u32(header + 16, SAMPLE_PAGES);
    sample_u32(header + 20, SAMPLE_RECORD);
    sample_u32(header + 24, 0);
    sample_u32(header + 28, sample_crc(header, 28));
    return send_all(serial, header, sizeof(header));
}

#ifndef HEARTH_CAPTURE_HOST_TEST
void __attribute__((noreturn)) _start(void)
{
    static const unsigned char error[] = "HEARTH_RAW_CAPTURE_FAILED_V1\n";
    long serial, interval[2] = { 1, 0 };
    int result;
    call5(21, (long)"proc", (long)"/proc", (long)"proc", 10, 0);
    call5(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 10, 0);
    call5(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10, (long)"mode=0755");
    for (;;) {
        serial = call5(5, (long)"/dev/ttyGS0", 2 | 0400 | 04000, 0, 0, 0);
        if (serial >= 0) {
            result = wait_start(serial);
            if (!result) {
                result = export_once(serial);
                if (result)
                    send_all(serial, error, sizeof(error) - 1);
                call5(6, serial, 0, 0, 0, 0);
                /* One fixed two-pass acquisition per boot. No retry or extra NAND reads. */
                for (;;)
                    call5(162, (long)interval, 0, 0, 0, 0);
            }
            call5(6, serial, 0, 0, 0, 0);
        }
        call5(162, (long)interval, 0, 0, 0, 0);
    }
}
#endif
