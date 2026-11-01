/* Original separate four-file contract (MIT). Legacy1MiB header is unchanged.
 * Reuses the transaction implementation with fixed root0 targets and RAM-backed
 * immutable originals/candidates. Opaque original DATA and private COW candidates are immutable after verification. */
#ifndef HEARTH_FILE_POSIX_H
#define HEARTH_FILE_POSIX_H
#include "../file_install/transaction.h"
typedef __SIZE_TYPE__ hearth_file_size;
#define HEARTH_FILE_BYTES (6U*1048576U)
#define HEARTH_TARGET_COUNT 4
/* Sentinel outside the four targets: every selected path is rooted at roots[0].
 * roots[1] is a second descriptor for the SAME root0, used only for its archive. */
#define HEARTH_SETTINGS 4
struct hearth_file_bytes { const unsigned char *data;hearth_file_size size; };
struct hearth_file_change {
 unsigned int target;int existed;
 struct hearth_file_bytes original,replacement;
 unsigned int original_mode,replacement_mode;
};
struct hearth_posix_context {
 int roots[2],recovery;
 unsigned int owner,group,count;
 const struct hearth_file_change *changes;
 unsigned int created[HEARTH_FILE_LIMIT];int journal_temporary;
 unsigned char plan_id[32];unsigned int archive_layout;
};
static const char *const hearth_target_paths[4]={"nestlabs/sbin/nlclient","usr/sbin/connmand","etc/connman/main.conf","etc/nestlabs/client.config"};
extern const struct hearth_file_ops hearth_posix_file_ops;
struct hearth_install_result hearth_posix_restore_files(struct hearth_posix_context *);
int hearth_posix_restore_preflight(struct hearth_posix_context *);
#endif
