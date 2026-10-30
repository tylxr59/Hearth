/* Synthetic host-only producer harness (MIT); no actual syscalls, USB or NAND. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#define HEARTH_CAPTURE_HOST_TEST
#include "capture-init.c"

static unsigned char wire[32768];
static unsigned int used, reads, closes, position, start_index, bad_input;
static int fail_read, fail_write, short_read, pause_write;

static long call5(long number, long a, long b, long c, long d, long e)
{
    unsigned int amount;
    static const char token[] = "HRTHGO1\n";
    if (number == 162)
        return 0;
    if (number == 5) {
        assert(strcmp((const char *)a, "/sys/class/mtd/mtd0/hearth_raw") == 0);
        assert(b == 0); /* All NAND opens must be read-only. */
        position = 0;
        return 10;
    }
    if (number == 6) {
        assert(a == 10);
        closes++;
        return 0;
    }
    if (number == 3 && a == 9) {
        assert(c == 1);
        *(unsigned char *)b = bad_input ? 'x' : token[start_index++];
        return 1;
    }
    if (number == 3) {
        assert(a == 10 && c == SAMPLE_RECORD && position < SAMPLE_PAGES);
        if (fail_read)
            return -EIO;
        memset((void *)b, position++, c);
        reads++;
        return short_read ? c - 1 : c;
    }
    if (number == 4) {
        assert(a == 9); /* No write syscall can target NAND. */
        if (fail_write)
            return -EPIPE;
        if (pause_write) {
            pause_write--;
            return -EAGAIN;
        }
        amount = c > 127 ? 127 : c; /* Force fragmented writes. */
        assert(used + amount <= sizeof(wire));
        memcpy(wire + used, (void *)b, amount);
        used += amount;
        return amount;
    }
    assert(!"unexpected syscall");
    return -EINVAL;
}

int main(void)
{
    assert(wait_start(9) == 0 && start_index == 8 && reads == 0);
    bad_input = 1;
    assert(wait_start(9) == -1 && reads == 0);
    bad_input = 0; fail_read = 1;
    assert(export_once(9) == -1 && used == 0 && closes == 1);
    fail_read = 0; short_read = 1;
    assert(export_once(9) == -1 && used == 0 && closes == 2);
    short_read = 0; fail_write = 1;
    assert(export_once(9) == -1 && used == 0 && closes == 3);
    fail_write = 0; pause_write = 501;
    assert(send_all(9, (const unsigned char *)"x", 1) == -1 && used == 0);
    pause_write = 3; reads = closes = used = 0;
    assert(export_once(9) == 0 && reads == SAMPLE_PAGES * 2 && closes == 2);
    assert(used == SAMPLE_PAGES * 2 * (SAMPLE_RECORD + SAMPLE_HEADER) + SAMPLE_HEADER);
    assert(fwrite(wire, 1, used, stdout) == used);
    return 0;
}
