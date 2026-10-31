/* Original Hearth bounded normal-ECC sampling userspace (MIT). No libc or commands. */
#include "sample-protocol.h"

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

static unsigned char samples[SAMPLE_PASSES][SAMPLE_PAGES][SAMPLE_RECORD];
static unsigned int failure_stage, failure_pass, failure_page;
static long failure_code;

static int capture(void)
{
    unsigned int pass, page;
    long fd, count;
    for (pass = 0; pass < SAMPLE_PASSES; pass++) {
        failure_stage=1; failure_pass=pass; failure_page=0;
        fd = call5(5, (long)"/sys/class/mtd/mtd0/hearth_ecc_sample", 0, 0, 0, 0);
        if (fd < 0) {
            failure_code=fd;
            return -1;
        }
        for (page = 0; page < SAMPLE_PAGES; page++) {
            failure_stage=2; failure_page=page;
            count = call5(3, fd, (long)samples[pass][page], SAMPLE_RECORD, 0, 0);
            if (count != SAMPLE_RECORD) {
                failure_code=count;
                call5(6, fd, 0, 0, 0, 0);
                return -1;
            }
        }
        call5(6, fd, 0, 0, 0, 0);
    }
    return 0;
}

static int send_all(long fd, const unsigned char *data, unsigned int size)
{
    unsigned int offset = 0, retries = 0;
    long result, pause[2] = { 0, 10000000 };
    while (offset < size) {
        result = call5(4, fd, (long)(data + offset), size - offset, 0, 0);
        if (result > 0) {
            offset += result;
        } else if ((result == -11 || result == -4) && retries++ < 500) {
            call5(162, (long)pause, 0, 0, 0, 0);
        } else {
            return -1;
        }
    }
    return 0;
}

static int send_capture(long fd)
{
    unsigned char header[SAMPLE_HEADER];
    unsigned int pass, page;
    for (pass = 0; pass < SAMPLE_PASSES; pass++) {
        for (page = 0; page < SAMPLE_PAGES; page++) {
            sample_header(header, pass, page, samples[pass][page]);
            if (send_all(fd, header, sizeof(header)) ||
                send_all(fd, samples[pass][page], SAMPLE_RECORD))
                return -1;
        }
    }
    return 0;
}

void __attribute__((noreturn)) _start(void)
{
    unsigned char error[SAMPLE_HEADER];
    long fd, interval[2] = { 1, 0 };
    int failed;
    call5(21, (long)"proc", (long)"/proc", (long)"proc", 10, 0);
    call5(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 10, 0);
    call5(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10,
          (long)"mode=0755");
    /* Exactly two bounded reads, then retransmit only the cached RAM bytes. */
    failed = capture();
    if (failed)
        sample_failure_header(error,failure_stage,failure_pass,failure_page,(int)failure_code);
    for (;;) {
        fd = call5(5, (long)"/dev/ttyGS0", 1 | 0400 | 04000, 0, 0, 0);
        if (fd >= 0) {
            if (failed)
                send_all(fd, error, sizeof(error));
            else
                send_capture(fd);
            call5(6, fd, 0, 0, 0, 0);
        }
        call5(162, (long)interval, 0, 0, 0, 0);
    }
}
