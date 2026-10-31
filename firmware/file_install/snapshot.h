/* Original read-only capture API (MIT). No mount, USB or mutation operations. */
#ifndef HEARTH_FILE_SNAPSHOT_H
#define HEARTH_FILE_SNAPSHOT_H
#include "posix.h"
struct hearth_snapshot_file {
    unsigned int target, existed, mode, owner, group;
    hearth_file_size size;
};
/* Both roots must be read-only JFFS2 mounts in the production build. A caller
 * supplies bounded RAM storage. On error, metadata and the entire buffer are
 * cleared. No receipt or permission to mutate follows from a successful read. */
int hearth_snapshot_file(const int roots[2], unsigned int owner, unsigned int group,
    unsigned int target, unsigned char *buffer, hearth_file_size capacity,
    struct hearth_snapshot_file *result);
#endif
