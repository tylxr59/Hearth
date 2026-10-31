/* Original Hearth fixed scratch transaction, GPL-2.0-or-later.
 * No NAND driver or execution adapter is supplied by this interface.
 */
#ifndef HEARTH_SCRATCH_CORE_H
#define HEARTH_SCRATCH_CORE_H

#define HS_BLOCK 1312u
#define HS_OFFSET 171966464u
#define HS_DATA 2048u
#define HS_OOB 64u
#define HS_RECORD (HS_DATA + HS_OOB)
#define HS_PAGES 64u
#define HS_BYTES (HS_RECORD * HS_PAGES)
#define HS_TEST_PAGE 1u
#define HS_DIGEST 32u

enum hs_state { HS_EMPTY, HS_PREPARING, HS_READY, HS_RUNNING, HS_FAILED, HS_DONE };
enum hs_error {
    HS_OK, HS_BAD_STATE, HS_GUARD, HS_PROTECTION, HS_READ, HS_CHANGED,
    HS_NOT_EMPTY, HS_HASH, HS_ACK, HS_PROGRAM, HS_ERASE, HS_MARKER, HS_RESTORE
};

/* Adapter callbacks have no writable address/range argument. A future adapter
 * must bind program/erase/marker to this exact block and test page, keep all
 * public mutation interfaces denied, and report full-length I/O only as zero.
 * guard checks geometry/bounds/bus/ECC/no-BBT state, irrespective of WP state.
 * protected returns exactly 1 asserted, 0 writable, or a negative error.
 * writable must verify actual hardware status, not merely set a control bit.
 */
struct hs_ops {
    int (*guard)(void *);
    int (*protected)(void *);
    int (*read)(void *, unsigned int, int, unsigned char *);
    int (*writable)(void *, int);
    int (*program)(void *, const unsigned char *);
    int (*erase)(void *);
    int (*marker)(void *, const unsigned char *);
    int (*hash)(void *, const unsigned char *, unsigned int, unsigned char *);
};

struct hs_report {
    enum hs_error error;
    unsigned int program_attempted, erase_attempted, marker_attempted;
    unsigned int program_data_match, restored, final_protected;
    int program_result, erase_result, marker_result;
};

/* Allocate outside the kernel stack. Initialized once; never reset/reuse it
 * during a boot. Cached bytes/digests are private and must not enter logs.
 */
struct hs_tx {
    enum hs_state state;
    struct hs_report report;
    unsigned char original[HS_BYTES], final[HS_BYTES];
    unsigned char page[HS_RECORD], programmed_raw[HS_RECORD];
    unsigned char programmed_normal[HS_RECORD], pattern[HS_DATA];
    unsigned char digest[HS_DIGEST], final_digest[HS_DIGEST];
};

int hs_prepare(struct hs_tx *, const struct hs_ops *, void *);
int hs_execute(struct hs_tx *, const struct hs_ops *, void *, const unsigned char *);
int hs_canonical(const unsigned char *);

#endif
