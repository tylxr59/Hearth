/* Original RAM-only native settings measurement. No nlclient, real settings,
 * network, control/lifecycle methods or device paths. All values are synthetic.
 * Opaque C++ ABI is specific to the privately reviewed Display-2.6 library.
 */
#include "faults.h"
extern void *malloc(size_t);
extern void free(void *);
extern int mkdir(const char *, unsigned int), open(const char *, int, ...);
extern unsigned int umask(unsigned int);
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
    *result = initialize(object, path);
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
    snprintf(directory, sizeof(directory), "/state/%s", names[index]);
    snprintf(destination, sizeof(destination), "%s/settings.xml", directory);
    snprintf(temporary, sizeof(temporary), "%s.tmp", destination);
    if (mkdir(directory, 0700) != 0 || !baseline(destination)) return 0;
    object = create(destination, &init);
    if (init != 0) { release(object); return 0; }
    for (i = 0; i < 2; i++) {
        const char *value = get(object, keys[i]);
        if (!value || strcmp(value, old_values[i]) != 0) { release(object); return 0; }
    }
    for (i = 0; i < 2; i++)
        if (set(object, keys[i], new_values[i]) != 0) { release(object); return 0; }
    fault_begin((enum fault)index, directory, destination, temporary);
    first_result = save(object); first = observed; fault_disarm();
    reload(destination, &reload1, &new1, &old1, &guard);
    fault_begin(NORMAL, directory, destination, temporary);
    second_result = save(object); second = observed; fault_disarm();
    reload(destination, &reload2, &new2, &old2, &guard);
    guard = release(object) && guard;
    size = snprintf(line, sizeof(line),
        "{\"type\":\"settings_case\",\"case\":\"%s\",\"injected\":%d,"
        "\"first_result\":%d,\"first_file_opens\":%d,\"first_renames\":%d,"
        "\"first_reload_result\":%d,\"first_new\":%d,\"first_old\":%d,"
        "\"retry_result\":%d,\"retry_file_opens\":%d,\"retry_renames\":%d,"
        "\"retry_reload_result\":%d,\"retry_new\":%d,\"retry_old\":%d,\"canary_ok\":%s}\n",
        names[index], first.injected, first_result, first.file_opens, first.renames,
        reload1, new1, old1, second_result, second.file_opens, second.renames,
        reload2, new2, old2, guard ? "true" : "false");
    if (size <= 0 || size >= (int)sizeof(line) || write(1, line, size) != size) return 0;
    if (!guard || first.injected != (index != 0)) return 0;
    return index != 0 || (first_result == 0 && reload1 == 0 && new1 == 3 &&
        second_result == 0 && second.file_opens == 0 && reload2 == 0 && new2 == 3);
}
int main(void)
{
    void *library;
    int i;
    umask(077);
    alarm(90);
    library = dlopen("/lib/libnlappcore.so", 2 | 0x100); /* NOW | GLOBAL for RTLD_NEXT hooks */
    if (!library || !fault_load()) return 110;
#define LOAD(p, n) do { p = (__typeof__(p))dlsym(library, n); if (!p) return 111; } while (0)
    LOAD(construct, "_ZN10nlSettingsC1Ev"); LOAD(destroy, "_ZN10nlSettingsD1Ev");
    LOAD(initialize, "_ZN10nlSettings4InitEPKc"); LOAD(save, "_ZN10nlSettings5WriteEv");
    LOAD(set, "_ZN10nlSettings8SetValueEPKcS1_"); LOAD(get, "_ZNK10nlSettings8GetValueEPKc");
#undef LOAD
    for (i = 0; i < 12; i++) if (!run_case(i)) return 112 + i;
    return 0;
}
