/* Original bounded Linux file adapter. No mount, USB or NAND operations. */
#ifndef HEARTH_FILE_POSIX_H
#define HEARTH_FILE_POSIX_H
#include "transaction.h"
typedef __SIZE_TYPE__ hearth_file_size;
#define HEARTH_FILE_BYTES (1024U*1024U)
enum hearth_file_target {
    HEARTH_WEB_LIBRARY, HEARTH_CA, HEARTH_CRL, HEARTH_NTP,
    HEARTH_STORAGE_LIBRARY, HEARTH_LAUNCHER, HEARTH_STARTUP,
    HEARTH_SETTINGS, HEARTH_CLIENT_CONFIG, HEARTH_TARGET_COUNT
};
struct hearth_file_bytes { const unsigned char *data; hearth_file_size size; };
struct hearth_file_change {
    unsigned int target;
    int existed;
    struct hearth_file_bytes original, replacement;
    unsigned int original_mode, replacement_mode;
};
struct hearth_posix_context {
    int roots[2], recovery;
    unsigned int owner, group, count;
    const struct hearth_file_change *changes;
    unsigned int created[HEARTH_FILE_LIMIT];
    int journal_temporary;
    /* Fixed 32-byte public plan identifier, not a credential. */
    unsigned char plan_id[32];
};
extern const struct hearth_file_ops hearth_posix_file_ops;
/* Explicit interrupted-install restoration from an exact caller-supplied plan.
 * Reads/validates the whole journal/current tree before mutation. Caller closes
 * context.recovery if >=0, including on failure. No mount or device launcher. */
struct hearth_install_result hearth_posix_restore_files(struct hearth_posix_context *);
/* Read-only recovery inspection. Leaves recovery fd open on success; close and
 * reset it before calling restore_files, which repeats the full inspection. */
int hearth_posix_restore_preflight(struct hearth_posix_context *);
#endif
