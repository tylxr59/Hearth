/* Original file-action lifecycle (MIT). All hardware/filesystem work is supplied
 * by a separately reviewed adapter. No device access in this interface. */
#ifndef HEARTH_FILE_ACTION_LIFECYCLE_H
#define HEARTH_FILE_ACTION_LIFECYCLE_H
#include "../file_install/transaction.h"
struct hfa_ops {
    int (*preflight)(void *);
    int (*open_window)(void *);
    int (*remount_rw)(void *,unsigned int);
    void (*transact)(void *,struct hearth_install_result *);
    int (*release)(void *);
    int (*unmount)(void *,unsigned int);
    int (*seal)(void *);
    int (*verify_readonly)(void *,int);
};
struct hfa_result {
    int stage_error,window_opened,transaction_called;
    unsigned int rw_attempted,unmount_errors;
    int release_error,seal_error,verified,safe_to_restart,complete;
    struct hearth_install_result transaction;
};
/* Invoked only after the owner-timed commit token. Preflight is repeated before
 * opening the gate; every exit attempts release/unmount/seal. */
struct hfa_result hfa_run(const struct hfa_ops *,void *,int);
/* Finish a read-only preflight without accepting a commit or remounting RW. */
struct hfa_result hfa_cancel(const struct hfa_ops *,void *);
#endif
