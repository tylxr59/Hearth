/* Original single-threaded fault instrumentation; diagnostic RAM process only. */
#ifndef HEARTH_SETTINGS_FAULTS_H
#define HEARTH_SETTINGS_FAULTS_H
#include "../tls_probe/abi.h"
enum fault { NORMAL, FILE_OPEN, HEADER_WRITE, ENTRY_ERROR, ENTRY_SHORT,
    FOOTER_WRITE, FILE_SYNC, FILE_CLOSE, RENAME, DIR_OPEN, DIR_SYNC, DIR_CLOSE };
struct counts { int injected, file_opens, dir_opens, writes, file_syncs, dir_syncs, renames; };
extern struct counts observed;
int fault_load(void);
void fault_begin(enum fault mode, const char *directory, const char *destination, const char *temporary);
void fault_disarm(void);
void *PR_Open(const char *, int, int);
int PR_Write(void *, const void *, int), PR_Sync(void *), PR_Close(void *);
int rename(const char *, const char *);
#endif
