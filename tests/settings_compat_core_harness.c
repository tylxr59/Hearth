/* Original host fixtures; use installed HOST NSPR, never firmware or private code. */
#include <assert.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <plhash.h>
#include "../firmware/settings_compat/core.h"
struct object;
struct descriptor { struct object *object; int kind; };
struct object {
    PLHashTable *table;
    pthread_mutex_t mutex;
    int dirty, fault, renames, file_syncs, restored;
    const char *path;
    char callback_value[128];
    struct descriptor file, directory, decoy;
    pthread_barrier_t *barrier;
    struct object *nested;
};
static __thread int allocation_fail, allocation_calls, entry_fail;
static __thread struct object *opening;
static void notice(int code) { assert(code == -103 || code == -2 || code == -5); }
static void *allocate(hearth_size size)
{
    allocation_calls++;
    if (allocation_fail && allocation_calls == allocation_fail) return NULL;
    return malloc(size);
}
static void *allocate_table(void *pool, PRSize size) { (void)pool; return malloc(size); }
static void free_table(void *pool, void *table) { (void)pool; free(table); }
static PLHashEntry *allocate_entry(void *pool, const void *key)
{
    (void)pool; (void)key;
    return entry_fail ? NULL : malloc(sizeof(PLHashEntry));
}
static void free_entry(void *pool, PLHashEntry *entry, PRUintn flag)
{
    (void)pool;
    if (flag == HT_FREE_ENTRY) { free((void *)entry->key); free(entry->value); free(entry); }
}
static const PLHashAllocOps allocation_ops = {allocate_table, free_table, allocate_entry, free_entry};
static const char *get(const void *object, const char *key)
{ return PL_HashTableLookupConst(((const struct object *)object)->table, key); }
static const void *entry_key(const void *entry) { return ((const PLHashEntry *)entry)->key; }
static int setter_fixture(void *object,const char *key,const char *value)
{
    int result=hearth_storage_add(object,key,value);
    /* Model the native DidSetValue callback AFTER AddEntry returns. */
    snprintf(((struct object *)object)->callback_value,128,"%s",value);
    return result;
}
static void *table(void *object) { return ((struct object *)object)->table; }
static void *add(void *hash, const void *key, void *value) { return PL_HashTableAdd(hash, key, value); }
static const char *filename(void *object) { return ((struct object *)object)->path; }
static void dirty(void *pointer)
{
    struct object *object = pointer;
    pthread_mutex_lock(&object->mutex); object->dirty = 1; object->restored++; pthread_mutex_unlock(&object->mutex);
}
static void *open_file(const char *path, int flags, int mode)
{
    (void)mode;
    if (!path) return NULL;
    if (strcmp(path, "/decoy") == 0) return &opening->decoy;
    return flags == 0x2a ? (void *)&opening->file : (void *)&opening->directory;
}
static int write_bytes(void *handle, const void *data, int size)
{
    struct descriptor *descriptor = handle;
    if (descriptor->kind == 2) return -1;
    if (descriptor->object->fault == 1 && strcmp(data, "entry") == 0) return -1;
    if (descriptor->object->fault == 2 && strcmp(data, "entry") == 0) return size/2;
    return size;
}
static int sync_file(void *handle)
{
    struct descriptor *descriptor = handle;
    if (!descriptor->kind) descriptor->object->file_syncs++;
    return descriptor->kind == 1 && descriptor->object->fault == 3 ? -1 : 0;
}
static int close_file(void *handle) { (void)handle; return 0; }
static int native_writer_fixture(void *pointer)
{
    struct object *object = pointer, *previous = opening;
    char path[128];
    void *file, *directory, *decoy;
    int result = 0;
    if (!object->dirty) return 0;
    pthread_mutex_lock(&object->mutex);
    opening = object;
    snprintf(path, sizeof(path), "%s.tmp", object->path);
    file = hearth_storage_open(path, 0x2a, 0666);
    assert(file && hearth_storage_log_blocked());
    decoy = hearth_storage_open("/decoy", 0x2a, 0666);
    assert(hearth_storage_write_bytes(decoy, "ignored", 7) == -1);
    if (object->nested) assert(hearth_storage_write(object->nested) == 0);
    assert(hearth_storage_write_bytes(file, "header", 6) == 6);
    (void)hearth_storage_write_bytes(file, "entry", object->fault == 4 ? -1 : 5); /* native bug: result ignored */
    if (object->barrier) pthread_barrier_wait(object->barrier);
    assert(hearth_storage_write_bytes(file, "footer", 6) == 6);
    if (hearth_storage_sync(file) != 0) result = -103;
    assert(hearth_storage_close(file) == 0);
    if (!result) {
        object->renames++;
        directory = hearth_storage_open(object->path, 1, 0);
        if (hearth_storage_sync(directory) != 0) result = -103;
        assert(hearth_storage_close(directory) == 0);
        object->dirty = 0; /* native bug: even a failed directory sync clears dirty */
    }
    opening = previous;
    pthread_mutex_unlock(&object->mutex);
    return result;
}
static void initialize(struct object *object, const char *path, int fault)
{
    memset(object, 0, sizeof(*object));
    assert(pthread_mutex_init(&object->mutex, NULL) == 0);
    object->table = PL_NewHashTable(16, PL_HashString, PL_CompareStrings, PL_CompareValues, &allocation_ops, NULL);
    assert(object->table);
    object->path = path; object->dirty = 1; object->fault = fault;
    object->file = (struct descriptor){object, 0}; object->directory = (struct descriptor){object, 1}; object->decoy = (struct descriptor){object, 2};
}
static void destroy(struct object *object)
{ PL_HashTableDestroy(object->table); assert(pthread_mutex_destroy(&object->mutex) == 0); }
static void *write_thread(void *pointer)
{
    struct object *object = pointer;
    int result = hearth_storage_write(object);
    assert(result == (object->fault ? -103 : 0));
    assert(!hearth_storage_log_blocked());
    return NULL;
}
int main(void)
{
    struct object object, other;
    hearth_ops = (struct hearth_storage_ops){native_writer_fixture, filename, dirty, open_file,
        write_bytes, sync_file, close_file, get, table, add, allocate, free, notice, setter_fixture, entry_key};
    assert(!hearth_storage_log_blocked());
    assert(hearth_storage_open(NULL,0x2a,0600)==NULL);
    for (int mode = 0; mode <= 4; mode++) {
        initialize(&object, "/state/settings", mode);
        assert(hearth_storage_write(&object) == (mode ? -103 : 0));
        assert(object.renames == (mode == 1 || mode == 2 || mode == 4 ? 0 : 1));
        assert(object.dirty == (mode != 0));
        if (mode == 1 || mode == 2 || mode == 4) assert(!object.file_syncs);
        object.fault = 0;
        assert(hearth_storage_write(&object) == 0 && !object.dirty);
        assert(!hearth_storage_log_blocked());
        destroy(&object);
    }
    /* Native hash ownership, failed allocations/hash insertion and aliased input. */
    initialize(&object, "/state/allocation", 0);
    assert(hearth_storage_add(&object, "key", "synthetic_secret_old") == 0);
    const char *old = get(&object, "key");
    allocation_calls = 0; allocation_fail = 1;
    assert(hearth_storage_add(&object, "key", "synthetic_secret_new") == -2);
    assert(get(&object, "key") == old && strcmp(old, "synthetic_secret_old") == 0);
    for (int failure = 1; failure <= 2; failure++) {
        allocation_calls = 0; allocation_fail = failure;
        assert(hearth_storage_add(&object, "new_key", "value") == -2 && !get(&object, "new_key"));
    }
    allocation_fail = 0; entry_fail = 1;
    assert(hearth_storage_add(&object, "new_key", "value") == -2 && !get(&object, "new_key"));
    entry_fail = 0;
    assert(hearth_storage_add(&object, "key", old+1) == 0);
    assert(strcmp(get(&object, "key"), "ynthetic_secret_old") == 0);
    assert(hearth_storage_add(&object, "key", get(&object, "key")) == 0);
    assert(hearth_storage_add(&object, "new_key", "value") == 0);
    assert(strcmp(get(&object, "new_key"), "value") == 0);
    old=get(&object,"key");
    assert(hearth_storage_set(&object,"key",old+1)==0);
    assert(strcmp(object.callback_value,"nthetic_secret_old")==0);
    old=get(&object,"key");
    assert(hearth_storage_set(&object,"key",old)==0);
    assert(strcmp(object.callback_value,"nthetic_secret_old")==0);
    char *empty_key=malloc(10); strcpy(empty_key,"empty_key");
    assert(PL_HashTableAdd(object.table,empty_key,NULL));
    assert(hearth_storage_add(&object,"empty_key","filled")==0);
    assert(strcmp(get(&object,"empty_key"),"filled")==0);
    destroy(&object);
    /* Overlapping writes on separate threads must not share failure/log scope. */
    pthread_t first, second; pthread_barrier_t barrier;
    assert(pthread_barrier_init(&barrier, NULL, 2) == 0);
    initialize(&object, "/state/first", 1); initialize(&other, "/state/second", 0);
    object.barrier = other.barrier = &barrier;
    assert(pthread_create(&first, NULL, write_thread, &object) == 0);
    assert(pthread_create(&second, NULL, write_thread, &other) == 0);
    pthread_join(first, NULL); pthread_join(second, NULL);
    assert(object.renames == 0 && other.renames == 1);
    assert(pthread_barrier_destroy(&barrier) == 0);
    destroy(&object); destroy(&other);
    /* Nested writer restoration and unrelated descriptor errors stay scoped. */
    initialize(&object, "/state/outer", 1); initialize(&other, "/state/inner", 0);
    object.nested = &other;
    assert(hearth_storage_write(&object) == -103 && !object.renames && other.renames == 1);
    destroy(&object); destroy(&other);
    assert(!hearth_storage_log_blocked());
    return 0;
}
