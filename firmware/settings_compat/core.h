/* Original storage-only compatibility experiment. No control/HVAC interfaces. */
#ifndef HEARTH_STORAGE_CORE_H
#define HEARTH_STORAGE_CORE_H
typedef __SIZE_TYPE__ hearth_size;
struct hearth_storage_ops {
    int (*write)(void *);
    const char *(*filename)(void *);
    void (*mark_dirty)(void *);
    void *(*open)(const char *, int, int);
    int (*write_bytes)(void *, const void *, int);
    int (*sync)(void *), (*close)(void *);
    const char *(*get)(const void *, const char *);
    void *(*table)(void *);
    void *(*add)(void *, const void *, void *);
    void *(*allocate)(hearth_size);
    void (*release)(void *);
    void (*failure)(int);
    int (*set)(void *, const char *, const char *);
    const void *(*entry_key)(const void *);
    int (*private_mode)(void *);
};
extern struct hearth_storage_ops hearth_ops;
int hearth_storage_write(void *);
int hearth_storage_set(void *, const char *, const char *);
int hearth_storage_add(void *, const char *, const char *);
void *hearth_storage_open(const char *, int, int);
int hearth_storage_write_bytes(void *, const void *, int);
int hearth_storage_sync(void *), hearth_storage_close(void *);
int hearth_storage_log_blocked(void);
unsigned long hearth_storage_suppressed_logs(void);
#endif
