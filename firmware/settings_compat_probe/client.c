/* Original RAM-only native settings measurement. No nlclient, real settings,
 * network, control/lifecycle methods or device paths. All values are synthetic.
 * Opaque C++ ABI is specific to the privately reviewed Display-2.6 library.
 */
#include "control.h"
#include "../settings_compat/trace.h"
extern void *malloc(size_t);
extern void free(void *);
extern int mkdir(const char *, unsigned int), open(const char *, int, ...);
extern unsigned int umask(unsigned int);
static const char *variant;
static unsigned long (*suppressed_logs)(void);
static void (*construct)(void *), (*destroy)(void *);
static int (*initialize)(void *, const char *), (*save)(void *);
static int (*set)(void *, const char *, const char *);
static const char *(*get)(void *, const char *);
static const char *const names[] = {"normal", "file_open", "header_write", "entry_error",
    "entry_short", "footer_write", "file_sync", "file_close", "rename", "dir_open",
    "dir_sync", "dir_close"};
static const char *const keys[] = {"hearth_probe_id", "hearth_probe_secret"};
static const char *const old_values[] = {"synthetic_id_old", "synthetic_secret_old"};
static const char *const new_values[] = {"synthetic_id_new", "synthetic_secret_new"};
static unsigned int *create(const char *path, int *result)
{
    unsigned int *object = malloc(64);
    int n;
    if (!object) _exit(101);
    for (n = 0; n < 16; n++) object[n] = 0x5ac39e71;
    construct(object);
    HEARTH_PHASE("helper.constructed");
    *result = initialize(object, path);
    HEARTH_PHASE("helper.initialized");
    return object;
}
static int canary(const unsigned int *object)
{
    int n;
    for (n = 12; n < 16; n++) if (object[n] != 0x5ac39e71) return 0;
    return 1;
}
static int release(unsigned int *object)
{
    int ok = canary(object);
    destroy(object); ok = ok && canary(object); free(object);
    return ok;
}
static void reload(const char *path, int *result, int *updated, int *old, int *guard)
{
    unsigned int *object = create(path, result);
    int n;
    *updated = *old = 0;
    for (n = 0; n < 2; n++) {
        const char *value = get(object, keys[n]);
        if (value && strcmp(value, new_values[n]) == 0) *updated |= 1 << n;
        if (value && strcmp(value, old_values[n]) == 0) *old |= 1 << n;
    }
    *guard = release(object) && *guard;
}
static int baseline(const char *path)
{
    static const char xml[] = "<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n<settings>\n"
        "<s key=\"hearth_probe_id\" value=\"synthetic_id_old\"/>\n"
        "<s key=\"hearth_probe_secret\" value=\"synthetic_secret_old\"/>\n</settings>\n";
    int fd = open(path, 1 | 64 | 128, 0600), ok;
    if (fd < 0) return 0;
    ok = write(fd, xml, sizeof(xml)-1) == sizeof(xml)-1;
    return close(fd) == 0 && ok;
}
static int run_case(int index)
{
    char directory[96], destination[128], temporary[132], line[768];
    unsigned int *object;
    struct counts first, second;
    int init, first_result, second_result, reload1, reload2, new1, new2, old1, old2;
    int i, size, guard = 1;
    snprintf(directory, sizeof(directory), "/state/%s-%s", variant, names[index]);
    snprintf(destination, sizeof(destination), "%s/settings.xml", directory);
    snprintf(temporary, sizeof(temporary), "%s.tmp", destination);
    if (mkdir(directory, 0700) != 0 || !baseline(destination)) return 0;
    object = create(destination, &init);
    HEARTH_PHASE("helper.created");
    if (init != 0) { release(object); return 0; }
    for (i = 0; i < 2; i++) {
        const char *value = get(object, keys[i]);
        if (!value || strcmp(value, old_values[i]) != 0) { release(object); return 0; }
    }
    for (i = 0; i < 2; i++)
        if (set(object, keys[i], new_values[i]) != 0) { release(object); return 0; }
    fault_begin((enum fault)index, directory, destination, temporary);
    first_result = save(object); fault_snapshot(&first); fault_disarm();
    HEARTH_PHASE("helper.saved");
    reload(destination, &reload1, &new1, &old1, &guard);
    fault_begin(NORMAL, directory, destination, temporary);
    second_result = save(object); fault_snapshot(&second); fault_disarm();
    reload(destination, &reload2, &new2, &old2, &guard);
    guard = release(object) && guard;
    size = snprintf(line, sizeof(line),
        "{\"type\":\"compat_case\",\"variant\":\"%s\",\"case\":\"%s\",\"injected\":%d,"
        "\"first_result\":%d,\"first_file_opens\":%d,\"first_renames\":%d,"
        "\"first_reload_result\":%d,\"first_new\":%d,\"first_old\":%d,"
        "\"retry_result\":%d,\"retry_file_opens\":%d,\"retry_renames\":%d,"
        "\"retry_reload_result\":%d,\"retry_new\":%d,\"retry_old\":%d,\"canary_ok\":%s}\n",
        variant, names[index], first.injected, first_result, first.file_opens, first.renames,
        reload1, new1, old1, second_result, second.file_opens, second.renames,
        reload2, new2, old2, guard ? "true" : "false");
    if (size <= 0 || size >= (int)sizeof(line) || write(1, line, size) != size) return 0;
    if (!guard || first.injected != (index != 0)) return 0;
    return index != 0 || (first_result == 0 && reload1 == 0 && new1 == 3 &&
        second_result == 0 && second.file_opens == 0 && reload2 == 0 && new2 == 3);
}
static int allocation_case(int index)
{
    static const char *const names[] = {"update_allocation", "new_key_allocation", "new_value_allocation", "hash_insertion", "aliased_value"};
    char directory[96], path[128], line[384];
    int init, first, retry, injected, freed, preserved, restored, guard, n;
    unsigned int *object;
    const char *key = index == 0 || index == 4 ? keys[1] : "hearth_probe_extra";
    const char *old;
    snprintf(directory, sizeof(directory), "/state/%s-%s", variant, names[index]);
    snprintf(path, sizeof(path), "%s/settings.xml", directory);
    if (mkdir(directory, 0700) || !baseline(path)) return 0;
    object = create(path, &init);
    if (init) { release(object); return 0; }
    old = get(object, key);
    if (index == 4) {
        first = set(object, key, old+1);
        injected = freed = 0;
        preserved = first == 0 && strcmp(get(object,key), "ynthetic_secret_old") == 0;
        retry = set(object,key,new_values[1]);
    } else {
        allocation_begin(index == 3 ? 2 : 1, index == 2 ? 2 : 1, old);
        first = set(object,key,"synthetic_secret_extra_new");
        allocation_snapshot(&injected,&freed);
        allocation_end();
        preserved = index == 0 ? get(object,key) == old && strcmp(old,old_values[1]) == 0 : get(object,key) == 0;
        retry = set(object,key,"synthetic_secret_extra_new");
    }
    restored = retry == 0 && get(object,key) && strcmp(get(object,key),index == 4 ? new_values[1] : "synthetic_secret_extra_new") == 0;
    guard = release(object);
    n = snprintf(line,sizeof(line),
        "{\"type\":\"compat_allocation\",\"variant\":\"candidate\",\"case\":\"%s\",\"first_result\":%d,\"injected\":%d,\"old_freed_on_failure\":%d,\"preserved\":%s,\"retry_result\":%d,\"restored\":%s,\"canary_ok\":%s}\n",
        names[index],first,injected,freed,preserved?"true":"false",retry,restored?"true":"false",guard?"true":"false");
    if (n<=0 || n>=(int)sizeof(line) || write(1,line,n)!=n) return 0;
    return preserved && restored && guard && first == (index == 4 ? 0 : -2) && injected == (index != 4) && !freed;
}
static int file_mode(const char *path)
{
    /* ARM EABI stat64: syscall 195, mode at byte 16 in the pinned kernel ABI.
     * Deliberately avoid the host/glibc stat structure. The kernel writes into
     * an aligned 128-byte buffer, larger than its 104-byte ARM stat64 result. */
    unsigned long long buffer[16] = {0};
    register long r0 __asm__("r0") = (long)path;
    register long r1 __asm__("r1") = (long)buffer;
    register long r7 __asm__("r7") = 195;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r1), "r"(r7) : "memory", "cc");
    if (r0) return -1;
    return (((unsigned char *)buffer)[16] | ((unsigned char *)buffer)[17] << 8) & 07777;
}
static int permission_case(int index)
{
    static const char *const names[] = {"new_temporary", "existing_temporary", "unrelated_open", "chmod_failure"};
    char directory[96], path[128], temporary[132], line[512];
    unsigned int *object, previous_mask;
    void *(*pr_open)(const char *, int, int);
    int (*pr_close)(void *);
    void *descriptor;
    int init, result, retry = 0, calls, injected, mode, retry_mode, guard = 1;
    int readback, updated, old, values_ok, n, fd;
    snprintf(directory, sizeof(directory), "/state/%s-permissions-%s", variant, names[index]);
    snprintf(path, sizeof(path), "%s/settings.xml", directory);
    snprintf(temporary, sizeof(temporary), "%s.tmp", path);
    if (mkdir(directory,0700) || !baseline(path) || file_mode(path) != 0600) return 0;
    object = create(path,&init);
    if (init) { release(object); return 0; }
    previous_mask = umask(0);
    if (index == 1) {
        fd = open(temporary,1|64|128,0644);
        if (fd < 0 || close(fd) || file_mode(temporary) != 0644) return 0;
    }
    permission_begin(index == 3);
    if (index == 2) {
        pr_open = (void *(*)(const char *,int,int))dlsym(0,"PR_Open");
        pr_close = (int (*)(void *))dlsym(0,"PR_Close");
        if (!pr_open || !pr_close) return 0;
        descriptor = pr_open(temporary,0x2a,0666);
        if (!descriptor || pr_close(descriptor)) return 0;
        result = 0; mode = file_mode(temporary);
    } else {
        if (set(object,keys[0],new_values[0]) || set(object,keys[1],new_values[1])) return 0;
        result = save(object); mode = file_mode(path);
    }
    permission_snapshot(&calls,&injected); permission_end();
    reload(path,&readback,&updated,&old,&guard);
    values_ok = readback == 0 && ((index == 2 || index == 3) ? old == 3 : updated == 3);
    if (index == 3) {
        retry = save(object);
        reload(path,&readback,&updated,&old,&guard);
        values_ok = values_ok && readback == 0 && updated == 3;
    }
    retry_mode = file_mode(index == 2 ? temporary : path);
    umask(previous_mask);
    guard = release(object) && guard;
    n = snprintf(line,sizeof(line),
        "{\"type\":\"compat_permissions\",\"variant\":\"%s\",\"case\":\"%s\",\"first_result\":%d,\"mode\":%d,\"fchmod_calls\":%d,\"failure_injected\":%d,\"values_ok\":%s,\"retry_result\":%d,\"retry_mode\":%d,\"canary_ok\":%s}\n",
        variant,names[index],result,mode,calls,injected,values_ok?"true":"false",retry,retry_mode,guard?"true":"false");
    return n>0 && n<(int)sizeof(line) && write(1,line,n)==n && guard && values_ok;
}
int main(int argc,char **argv)
{
    HEARTH_PHASE("helper.main");
    void *library,*candidate;
    void (*logger)(int,const char *,const char *,...);
    int i, n;
    char line[192];
    if (argc != 2 || (strcmp(argv[1],"original") && strcmp(argv[1],"candidate"))) return 109;
    variant = argv[1];
    umask(077); alarm(90);
    library = dlopen("/lib/libnlappcore.so",2|0x100);
    if (!library || !fault_load()) return 110;
    HEARTH_PHASE("helper.library");
#define LOAD(p,n) do { p = (__typeof__(p))dlsym(library,n); if (!p) return 111; } while (0)
    LOAD(construct,"_ZN10nlSettingsC1Ev"); LOAD(destroy,"_ZN10nlSettingsD1Ev");
    LOAD(initialize,"_ZN10nlSettings4InitEPKc"); LOAD(set,"_ZN10nlSettings8SetValueEPKcS1_"); LOAD(get,"_ZNK10nlSettings8GetValueEPKc");
#undef LOAD
    save = (int (*)(void *))dlsym(0,"_ZN10nlSettings5WriteEv");
    set = (int (*)(void *,const char *,const char *))dlsym(0,"_ZN10nlSettings8SetValueEPKcS1_");
    logger = (void (*)(int,const char *,const char *,...))dlsym(0,"nlLogWithComponent");
    if (!save || !set || !logger) return 111;
    suppressed_logs = (unsigned long (*)(void))dlsym(0,"hearth_settings_suppressed_logs");
    if (strcmp(variant,"candidate") == 0) {
        candidate = dlopen("/lib/libhearth-settings-compat.so",2);
        if (!candidate || !suppressed_logs || (void *)set != dlsym(candidate,"_ZN10nlSettings8SetValueEPKcS1_") || (void *)save != dlsym(candidate,"_ZN10nlSettings5WriteEv") || dlsym(0,"_ZN8nlConfig8AddEntryEPKcS1_") != dlsym(candidate,"_ZN8nlConfig8AddEntryEPKcS1_")) return 112;
    } else if (suppressed_logs || (void *)save != dlsym(library,"_ZN10nlSettings5WriteEv")) return 112;
    HEARTH_PHASE("helper.bindings");
    for (i=0;i<12;i++) if (!run_case(i)) return 113;
    if (suppressed_logs) for (i=0;i<5;i++) if (!allocation_case(i)) return 114;
    for (i=0;i<(suppressed_logs?4:3);i++) if (!permission_case(i)) return 116;
    logger(4,0,"HEARTH_COMPAT_LOG_PASSTHROUGH %d %s %d %d %d %.1f",17,"probe",23,29,31,1.5);
    n = snprintf(line,sizeof(line),"{\"type\":\"compat_helper\",\"variant\":\"%s\",\"bindings_verified\":true,\"suppressed_logs\":%lu}\n",variant,suppressed_logs?suppressed_logs():0UL);
    return n>0 && n<(int)sizeof(line) && write(1,line,n)==n ? 0 : 115;
}
