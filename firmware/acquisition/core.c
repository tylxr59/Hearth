/* Original shared read-only walker, with full-file installer acquisition bounds.
 * A separate translation unit retains the tested log-reader defaults unchanged.
 */
#include "../startup_diagnostic/logs.h"
#undef HFD_FILES
#undef HFD_TAIL
#define HFD_FILES 256U
#define HFD_TAIL (8U*1024U*1024U)
/* Dependency resolution uses direct filenames/SONAMEs in these four folders.
 * Kernel modules, locale trees and other subdirectories are outside the kit. */
#define HFD_RECURSE 0
#include "../startup_diagnostic/logs.c"
