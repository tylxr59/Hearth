/* Original startup-only ARM adapter for the exact privately reviewed ABI.
 * Experimental helper preload only. No apply/installer or native app launch.
 */
#include "core.h"
extern void *dlsym(void *, const char *);
extern void *memcpy(void *, const void *, hearth_size);
_Static_assert(sizeof(void *) == 4 && sizeof(int) == 4, "exact ARM32 object ABI required");
extern void _exit(int) __attribute__((noreturn));
static int ready, initializing;
static const char *(*string_bytes)(const void *);
static void (*lock)(void *);
static int (*unlock)(void *);
static void *real_log, *pointer_compare, *configuration_init;
static int (*original_add)(void *,const char *,const char *);
static int supported_table(void *object)
{
    void *hash, *compare, *allocation, *free_entry;
    if (!object) return 0;
    memcpy(&hash,(unsigned char *)object+4,sizeof(hash));
    if (!hash) return 0;
    memcpy(&compare,(unsigned char *)hash+20,sizeof(compare));
    memcpy(&allocation,(unsigned char *)hash+24,sizeof(allocation));
    if (!allocation) return 0;
    memcpy(&free_entry,(unsigned char *)allocation+12,sizeof(free_entry));
    return compare == pointer_compare && (__UINTPTR_TYPE__)free_entry ==
        (__UINTPTR_TYPE__)configuration_init - 0x1bda4 + 0x1bd14;
}
static void notice(int code)
{
    ((void (*)(int, const char *, const char *, ...))real_log)(4, 0, "Hearth storage operation failed (%d)", code);
}
static void dirty(void *object)
{
    unsigned char *bytes = object;
    void *mutex; int one = 1;
    memcpy(&mutex,bytes+8,sizeof(mutex));
    lock(mutex); memcpy(bytes+12,&one,sizeof(one)); unlock(mutex);
}
static const char *filename(void *object) { return string_bytes((unsigned char *)object+20); }
static void *table(void *object)
{ void *value; memcpy(&value,(unsigned char *)object+4,sizeof(value)); return value; }
static const void *entry_key(const void *entry)
{ const void *value; memcpy(&value,(const unsigned char *)entry+8,sizeof(value)); return value; }
static void initialize(void)
{
    if (ready) return;
    if (initializing) _exit(117);
    initializing = 1;
#define LOAD(p, n) do { p = (__typeof__(p))dlsym((void *)-1L, n); if (!p) _exit(118); } while (0)
    LOAD(hearth_ops.write, "_ZN10nlSettings5WriteEv");
    LOAD(original_add, "_ZN8nlConfig8AddEntryEPKcS1_");
    LOAD(pointer_compare, "PL_CompareValues");
    LOAD(configuration_init, "_ZN8nlConfig4InitEv");
    LOAD(hearth_ops.set, "_ZN10nlSettings8SetValueEPKcS1_");
    LOAD(hearth_ops.open, "PR_Open"); LOAD(hearth_ops.write_bytes, "PR_Write");
    LOAD(hearth_ops.sync, "PR_Sync"); LOAD(hearth_ops.close, "PR_Close");
    LOAD(hearth_ops.get, "_ZNK8nlConfig8GetValueEPKc");
    LOAD(hearth_ops.add, "PL_HashTableAdd");
    LOAD(hearth_ops.allocate, "nlMALLOC"); LOAD(hearth_ops.release, "nlFREE");
    LOAD(string_bytes, "_ZNK8nlString13GetAsUTFArrayEv");
    LOAD(lock, "PR_Lock"); LOAD(unlock, "PR_Unlock");
    LOAD(real_log, "nlLogWithComponent");
#undef LOAD
    hearth_ops.filename = filename; hearth_ops.mark_dirty = dirty; hearth_ops.table = table; hearth_ops.failure = notice; hearth_ops.entry_key = entry_key;
    ready = 1;
}
static void __attribute__((constructor)) startup(void) { initialize(); }
int native_write(void *) __asm__("_ZN10nlSettings5WriteEv");
int native_write(void *object) { initialize(); return hearth_storage_write(object); }
int native_set(void *, const char *, const char *) __asm__("_ZN10nlSettings8SetValueEPKcS1_");
int native_set(void *object, const char *key, const char *value)
{ initialize(); return hearth_storage_set(object,key,value); }
int native_add(void *, const char *, const char *) __asm__("_ZN8nlConfig8AddEntryEPKcS1_");
int native_add(void *object, const char *key, const char *value)
{ initialize(); return supported_table(object) ? hearth_storage_add(object, key, value) : original_add(object,key,value); }
void *PR_Open(const char *path, int flags, int mode)
{ initialize(); return hearth_storage_open(path, flags, mode); }
int PR_Write(void *fd, const void *data, int size)
{ initialize(); return hearth_storage_write_bytes(fd, data, size); }
int PR_Sync(void *fd) { initialize(); return hearth_storage_sync(fd); }
int PR_Close(void *fd) { initialize(); return hearth_storage_close(fd); }
void *hearth_settings_log_target(void)
{
    /* Variadic arguments are forwarded untouched by the assembly tail stub. */
    initialize();
    return hearth_storage_log_blocked() ? 0 : real_log;
}
unsigned long hearth_settings_suppressed_logs(void) { return hearth_storage_suppressed_logs(); }
