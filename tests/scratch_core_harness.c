/* Original synthetic NAND model, GPL-2.0-or-later. No firmware is executed. */
#include "../firmware/scratch_test/core.h"
#include <assert.h>
#include <openssl/sha.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct fake {
    unsigned char before[16], block[HS_BYTES], after[16];
    int wp, bad_guard, reads, fault_read, change_read, hash_error;
    int enable_error, disable_error, wrong_wp, failed_protection_call, disables;
    int programs, erases, markers, program_error, erase_error, marker_error;
    int false_erase, corrupt_program, corrupt_restore;
    int enables, guard_after_program;
};

static struct hs_tx tx;
static struct fake f;
static const unsigned char marker[8] = {0x85, 0x19, 3, 0x20, 8, 0, 0, 0};

static int guard(void *c)
{
    struct fake *m = c;
    if (m->bad_guard || (m->guard_after_program && m->programs)) return -1;
    assert(m->before[0] == 0x17 && m->after[15] == 0x81);
    return 0;
}
static int protected(void *c) { return ((struct fake *)c)->wp; }
static int read_page(void *c, unsigned int page, int normal, unsigned char *out)
{
    struct fake *m = c;
    assert(page < HS_PAGES && m->wp == 1);
    assert(normal == 0 || (normal == 1 && page == HS_TEST_PAGE && m->programs));
    ++m->reads;
    if (m->reads == m->fault_read) return -1;
    memcpy(out, m->block + page * HS_RECORD, HS_RECORD);
    if (m->reads == m->change_read) out[1] ^= 1;
    return 0;
}
static int writable(void *c, int enabled)
{
    struct fake *m = c;
    if (enabled) {
        assert(m->wp == 1);
        ++m->enables;
        if (m->enable_error) return -1;
        m->wp = m->wrong_wp ? 1 : 0;
        return 0;
    }
    ++m->disables;
    if (m->disable_error || m->disables == m->failed_protection_call) return -1;
    m->wp = 1;
    return 0;
}
static int program(void *c, const unsigned char *data)
{
    struct fake *m = c;
    unsigned int i;
    assert(m->wp == 0 && m->programs == 0 && m->erases == 0);
    ++m->programs;
    for (i = 0; i < (m->program_error ? HS_DATA / 2 : HS_DATA); ++i)
        m->block[HS_TEST_PAGE * HS_RECORD + i] &= data[i];
    /* A fake ECC code is intentionally insufficient for a hardware/ECC pass. */
    memset(m->block + HS_TEST_PAGE * HS_RECORD + HS_DATA + 36, 0x42, 28);
    if (m->corrupt_program) m->block[HS_TEST_PAGE * HS_RECORD] ^= 1;
    return m->program_error ? -1 : 0;
}
static int erase(void *c)
{
    struct fake *m = c;
    assert(m->wp == 0 && m->programs == 1 && m->erases == 0);
    ++m->erases;
    if (m->erase_error) return -1;
    if (!m->false_erase) memset(m->block, 0xff, HS_BYTES);
    return 0;
}
static int restore_marker(void *c, const unsigned char *data)
{
    struct fake *m = c;
    unsigned int i;
    assert(m->wp == 0 && m->erases == 1 && m->markers == 0);
    ++m->markers;
    for (i = 0; i < 8; ++i) m->block[HS_DATA + 2 + i] &= data[i];
    if (m->corrupt_restore) m->block[HS_DATA + 3] ^= 1;
    return m->marker_error ? -1 : 0;
}
static int hash(void *c, const unsigned char *data, unsigned int bytes, unsigned char *out)
{
    struct fake *m = c;
    assert(bytes == HS_BYTES);
    if (m->hash_error) return -1;
    return SHA256(data, bytes, out) ? 0 : -1;
}
static const struct hs_ops ops = {guard, protected, read_page, writable,
                                 program, erase, restore_marker, hash};
static void reset(void)
{
    memset(&tx, 0, sizeof(tx));
    memset(&f, 0, sizeof(f));
    memset(f.before, 0x17, sizeof(f.before));
    memset(f.after, 0x81, sizeof(f.after));
    memset(f.block, 0xff, sizeof(f.block));
    memcpy(f.block + HS_DATA + 2, marker, 8);
    f.wp = 1;
}
static void ready(void) { reset(); assert(hs_prepare(&tx, &ops, &f) == 0); }
static int run(void) { return hs_execute(&tx, &ops, &f, tx.digest); }
static void untouched(void)
{
    assert(f.programs == 0 && f.erases == 0 && f.markers == 0 && f.enables == 0);
    assert(f.wp == 1 && hs_canonical(f.block));
}
static void restored_failure(enum hs_error expected)
{
    assert(run() < 0 && tx.report.error == expected);
    assert(f.programs == 1 && f.erases == 1 && f.markers == 1);
    assert(tx.report.restored && tx.report.final_protected && f.wp == 1);
    assert(hs_canonical(f.block));
    assert(run() == -HS_BAD_STATE && f.programs == 1);
}
int main(void)
{
    unsigned int p, offset;
    ready(); assert(run() == 0 && tx.state == HS_DONE);
    assert(tx.report.restored && tx.report.program_data_match && f.wp == 1);
    assert(f.programs == 1 && f.erases == 1 && f.markers == 1 && f.enables == 3);
    assert(!memcmp(tx.original, tx.final, HS_BYTES));
    assert(!memcmp(tx.digest, tx.final_digest, HS_DIGEST));
    assert(run() == -HS_BAD_STATE && hs_prepare(&tx, &ops, &f) == -HS_BAD_STATE);

    reset(); assert(run() == -HS_BAD_STATE); untouched();
    ready(); assert(hs_execute(&tx, &ops, &f, NULL) == -HS_ACK); untouched();
    ready(); memset(tx.final_digest, 0x13, HS_DIGEST);
    assert(hs_execute(&tx, &ops, &f, tx.final_digest) == -HS_ACK); untouched();
    assert(run() == -HS_BAD_STATE);
    reset(); f.bad_guard = 1; assert(hs_prepare(&tx, &ops, &f) == -HS_GUARD); untouched();
    reset(); f.hash_error = 1; assert(hs_prepare(&tx, &ops, &f) == -HS_HASH); untouched();
    reset(); f.fault_read = 70; assert(hs_prepare(&tx, &ops, &f) == -HS_READ); untouched();
    reset(); f.change_read = 120; assert(hs_prepare(&tx, &ops, &f) == -HS_CHANGED); untouched();
    ready(); f.change_read = f.reads + 25; assert(run() == -HS_CHANGED); untouched();
    ready(); f.fault_read = f.reads + 1; assert(run() == -HS_READ); untouched();
    ready(); f.bad_guard = 1; assert(run() == -HS_GUARD); untouched();

    /* Alter every data/OOB byte in every page, one at a time. In particular
     * factory marker bytes, marker padding, ECC and later pages must refuse. */
    for (p = 0; p < HS_PAGES; ++p) {
        for (offset = 0; offset < HS_RECORD; ++offset) {
            f.block[p * HS_RECORD + offset] ^= 1;
            assert(!hs_canonical(f.block));
            f.block[p * HS_RECORD + offset] ^= 1;
        }
    }
    reset(); f.block[HS_RECORD + HS_DATA] = 0;
    assert(hs_prepare(&tx, &ops, &f) == -HS_NOT_EMPTY && f.enables == 0);
    ready(); f.block[HS_BYTES - 1] = 0;
    assert(run() == -HS_CHANGED && f.enables == 0);

    ready(); f.enable_error = 1; assert(run() == -HS_PROTECTION);
    assert(f.programs == 0 && f.disables == 1 && f.wp == 1);
    ready(); f.wrong_wp = 1; assert(run() == -HS_PROTECTION);
    assert(f.programs == 0 && f.disables == 1 && f.wp == 1);
    ready(); f.disable_error = 1; assert(run() == -HS_PROTECTION);
    assert(f.programs == 1 && f.erases == 0 && f.markers == 0);
    ready(); f.guard_after_program = 1; assert(run() == -HS_GUARD);
    assert(f.wp == 1 && f.erases == 0);
    ready(); f.program_error = 1; restored_failure(HS_PROGRAM);
    ready(); f.corrupt_program = 1; restored_failure(HS_PROGRAM);
    ready(); f.fault_read = f.reads + HS_PAGES + 1; restored_failure(HS_READ);
    ready(); f.erase_error = 1; assert(run() == -HS_ERASE);
    assert(f.erases == 1 && f.markers == 0 && f.wp == 1);
    ready(); f.false_erase = 1; assert(run() == -HS_ERASE);
    assert(f.erases == 1 && f.markers == 0 && f.wp == 1);
    ready(); f.failed_protection_call = 2; assert(run() == -HS_PROTECTION);
    assert(f.erases == 1 && f.markers == 0);
    ready(); f.marker_error = 1; restored_failure(HS_MARKER);
    ready(); f.failed_protection_call = 3; assert(run() == -HS_PROTECTION);
    assert(f.markers == 1 && !tx.report.final_protected);
    ready(); f.hash_error = 1; assert(run() == -HS_HASH);
    assert(hs_canonical(f.block) && f.wp == 1);
    ready(); f.corrupt_restore = 1; assert(run() == -HS_RESTORE);
    assert(!tx.report.restored && f.markers == 1 && f.wp == 1);
    assert(f.before[0] == 0x17 && f.after[15] == 0x81);
    puts("scratch state/fault model passed; no device or ECC qualification");
    return 0;
}
