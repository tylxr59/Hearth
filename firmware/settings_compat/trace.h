/* Original fixed, value-free phase markers for the single-threaded RAM lab.
 * Disabled in the standalone candidate build. Never a production logging API.
 * No TLS, allocation, formatting or native logging is needed to emit a marker.
 */
#ifndef HEARTH_STORAGE_TRACE_H
#define HEARTH_STORAGE_TRACE_H
#ifdef HEARTH_STORAGE_TRACE
extern long write(int, const void *, __SIZE_TYPE__);
#define HEARTH_PHASE(label) do { \
    static unsigned int emitted; \
    if (!emitted) { \
        emitted = 1; \
        (void)write(2, "HEARTH_STORAGE_PHASE " label "\n", \
                    sizeof("HEARTH_STORAGE_PHASE " label "\n")-1); \
    } \
} while (0)
#else
#define HEARTH_PHASE(label) ((void)0)
#endif
#endif
