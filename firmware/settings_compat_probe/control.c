/* This original test DSO is placed BELOW the candidate in LD_PRELOAD order.
 * Never deploy it. Faults apply only inside the single-threaded synthetic helper.
 */
#include "control.h"
static int allocation_kind, fail_ordinal, allocation_count, allocation_injected, old_freed;
static const void *old_pointer;
static void *(*allocate_real)(size_t);
static void (*release_real)(void *);
static void *(*add_real)(void *, const void *, void *);
void fault_snapshot(struct counts *copy) { *copy = observed; }
void allocation_begin(int kind, int ordinal, const void *old_value)
{
    allocation_kind = kind; fail_ordinal = ordinal; allocation_count = 0;
    allocation_injected = 0; old_freed = 0; old_pointer = old_value;
}
void allocation_end(void) { allocation_kind = 0; old_pointer = 0; }
void allocation_snapshot(int *injected, int *freed)
{ *injected = allocation_injected; *freed = old_freed; }
void *nlMALLOC(size_t size)
{
    if (!allocate_real) allocate_real = (void *(*)(size_t))dlsym((void *)-1L, "nlMALLOC");
    if (!allocate_real) _exit(126);
    if (allocation_kind == 1 && ++allocation_count == fail_ordinal) {
        allocation_injected++; return 0;
    }
    return allocate_real(size);
}
void nlFREE(void *pointer)
{
    if (!release_real) release_real = (void (*)(void *))dlsym((void *)-1L, "nlFREE");
    if (!release_real) _exit(126);
    if (old_pointer && pointer == old_pointer) old_freed++;
    release_real(pointer);
}
void *PL_HashTableAdd(void *table, const void *key, void *value)
{
    if (!add_real) add_real = (void *(*)(void *, const void *, void *))dlsym((void *)-1L, "PL_HashTableAdd");
    if (!add_real) _exit(126);
    if (allocation_kind == 2 && !allocation_injected) { allocation_injected++; return 0; }
    return add_real(table, key, value);
}
