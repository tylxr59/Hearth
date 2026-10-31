/* Original narrow correction, preserving native writer and serialization.
 * Native object access and symbol binding are isolated in bind.c.
 * A frame belongs to one call/thread; no global sticky I/O failure state.
 */
#include "core.h"
#include "trace.h"
extern int strcmp(const char *, const char *);
extern int strncmp(const char *, const char *, hearth_size);
extern hearth_size strlen(const char *);
extern void *memcpy(void *, const void *, hearth_size);
struct hearth_storage_ops hearth_ops;
struct transaction {
    struct transaction *parent;
    void *descriptor;
    int failed;
    const char *path;
    hearth_size path_size;
};
static __thread struct transaction *active;
static __thread unsigned long suppressed;
struct setter_call {
    struct setter_call *parent;
    void *deferred[16];
    unsigned int count;
};
static __thread struct setter_call *setter;
int hearth_storage_set(void *object, const char *key, const char *value)
{
    HEARTH_PHASE("set.enter");
    struct setter_call frame;
    int result;
    frame.parent = setter; frame.count = 0; setter = &frame;
    HEARTH_PHASE("set.tls");
    result = hearth_ops.set(object,key,value);
    setter = frame.parent;
    for (unsigned int i=0;i<frame.count;i++) hearth_ops.release(frame.deferred[i]);
    return result;
}
static int aliases(const char *input, const char *old)
{
    __UINTPTR_TYPE__ pointer=(__UINTPTR_TYPE__)input, start=(__UINTPTR_TYPE__)old;
    return pointer>=start && pointer-start<=strlen(old);
}

int hearth_storage_write(void *object)
{
    HEARTH_PHASE("write.enter");
    struct transaction frame;
    const char *path = hearth_ops.filename(object);
    hearth_size size = 0;
    int result;
    if (path) {
        while (path[size] && size < 4091) size++;
        if (path[size]) return -5; /* fail before I/O if the reviewed path bound is exceeded */
    }
    frame.path = path; frame.path_size = size;
    frame.parent = active; frame.descriptor = 0; frame.failed = 0;
    active = &frame;
    HEARTH_PHASE("write.tls");
    result = hearth_ops.write(object);
    if (frame.failed || result != 0) {
        /* The native writer already unlocked. Take its lock before restoring,
         * never clear a concurrent setter's dirty flag or roll back its values. */
        hearth_ops.mark_dirty(object);
        if (result == 0) result = -103;
    }
    active = frame.parent;
    if (result != 0 && hearth_ops.failure) hearth_ops.failure(result);
    return result;
}
void *hearth_storage_open(const char *path, int flags, int mode)
{
    void *fd = hearth_ops.open(path, flags, mode);
    if (active && path && flags == 0x2a && active->path_size &&
        strncmp(path, active->path, active->path_size) == 0 &&
        strcmp(path + active->path_size, ".tmp") == 0)
        active->descriptor = fd;
    return fd;
}
static struct transaction *owner(void *fd)
{
    struct transaction *frame;
    if (!fd) return 0;
    for (frame = active; frame; frame = frame->parent)
        if (frame->descriptor == fd) return frame;
    return 0;
}
int hearth_storage_write_bytes(void *fd, const void *data, int size)
{
    int result = hearth_ops.write_bytes(fd, data, size);
    struct transaction *frame = owner(fd);
    if (frame && (size < 0 || result < 0 || result != size)) frame->failed = 1;
    return result;
}
int hearth_storage_sync(void *fd)
{
    struct transaction *frame = owner(fd);
    int result;
    /* An entry callback cannot return its failure to native Write. Make the
     * existing file-sync failure path block rename, even if later writes succeed. */
    if (frame && frame->failed) return -1;
    result = hearth_ops.sync(fd);
    if (frame && result != 0) frame->failed = 1;
    return result;
}
int hearth_storage_close(void *fd)
{
    struct transaction *frame = owner(fd);
    int result;
    if (frame) frame->descriptor = 0;
    result = hearth_ops.close(fd);
    if (frame && result != 0) frame->failed = 1;
    return result;
}
int hearth_storage_log_blocked(void)
{
    HEARTH_PHASE("log.before_tls");
    struct transaction *volatile frame = active;
    HEARTH_PHASE("log.after_tls");
    if (!frame) return 0;
    suppressed++;
    return 1;
}
unsigned long hearth_storage_suppressed_logs(void) { return suppressed; }

static int failed_add(int code)
{
    if (hearth_ops.failure) hearth_ops.failure(code);
    return code;
}
int hearth_storage_add(void *object, const char *key, const char *value)
{
    HEARTH_PHASE("add.enter");
    const char *old;
    char *copied_key = 0, *copied_value;
    hearth_size key_size, value_size;
    void *table, *entry;
    int defer;
    if (!object || !key || !value || !(table = hearth_ops.table(object))) return failed_add(-5);
    old = hearth_ops.get(object, key);
    defer = old && setter && (aliases(key,old) || aliases(value,old));
    if (defer && setter->count == 16) return failed_add(-2);
    key_size = strlen(key); value_size = strlen(value);
    if (key_size >= 0x7fffffffUL || value_size >= 0x7fffffffUL) return failed_add(-2);
    if (!old) {
        copied_key = hearth_ops.allocate(key_size+1);
        if (!copied_key) return failed_add(-2);
        memcpy(copied_key, key, key_size+1);
    }
    copied_value = hearth_ops.allocate(value_size+1);
    if (!copied_value) { if (copied_key) hearth_ops.release(copied_key); return failed_add(-2); }
    /* Copy while old is still live, including when value aliases old or its tail. */
    memcpy(copied_value, value, value_size+1);
    entry = hearth_ops.add(table, copied_key ? copied_key : key, copied_value);
    if (!entry) {
        hearth_ops.release(copied_value);
        if (copied_key) hearth_ops.release(copied_key);
        return failed_add(-2);
    }
    /* Exact-profile gate verifies pointer value comparison and a no-op
     * HT_FREE_VALUE callback: native destruction still owns key/new-value frees. */
    if (copied_key && hearth_ops.entry_key(entry) != copied_key) hearth_ops.release(copied_key);
    if (old) {
        if (defer) setter->deferred[setter->count++] = (void *)old;
        else hearth_ops.release((void *)old);
    }
    return 0;
}
