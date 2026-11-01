/* Original narrowly scoped original-file encoding repair, MIT. */
#ifndef HEARTH_ORIGINAL_REENCODE_H
#define HEARTH_ORIGINAL_REENCODE_H
#include "../file_install/posix.h"
int hearth_posix_reencode_preflight(struct hearth_posix_context *);
struct hearth_install_result hearth_posix_reencode_originals(struct hearth_posix_context *);
int hearth_posix_original_encoding(struct hearth_posix_context *);
int hearth_posix_selected_encoding(struct hearth_posix_context *,int);
#endif
