/* Original synthetic-only shared instrumentation control API. */
#ifndef HEARTH_COMPAT_CONTROL_H
#define HEARTH_COMPAT_CONTROL_H
#include "../settings_probe/faults.h"
void fault_snapshot(struct counts *);
void allocation_begin(int kind, int ordinal, const void *old_value);
void allocation_end(void);
void allocation_snapshot(int *injected, int *old_freed);
#endif
