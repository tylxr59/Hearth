/* Original fixed private RAM data mapping/guard contract (MIT). */
#ifndef HEARTH_NETWORK_WRITER_DATA_H
#define HEARTH_NETWORK_WRITER_DATA_H
#include "../network_update/posix.h"
extern struct hearth_file_change hn_changes[4];
extern unsigned int hn_memory_free,hn_space_available,hn_space_required,hn_data_diagnostic;
int hn_data_load(int);
int hn_data_release(void);
int hn_memory_guard(void);
int hn_space_guard(int,int);
int hn_exact_readback(struct hearth_posix_context *,int);
#endif
