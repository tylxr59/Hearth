/* Original bounded file-transaction core (MIT). No USB, mount or NAND API. */
#ifndef HEARTH_FILE_TRANSACTION_H
#define HEARTH_FILE_TRANSACTION_H
#define HEARTH_FILE_LIMIT 9

enum hearth_install_phase {
    HEARTH_PREPARING = 1, HEARTH_STAGED, HEARTH_COMMITTING,
    HEARTH_COMMITTED, HEARTH_RESTORING, HEARTH_RESTORED,
    HEARTH_RESTORE_FAILED
};
enum hearth_install_error {
    HEARTH_INSTALL_OK = 0, HEARTH_INVALID_PLAN = -1,
    HEARTH_BACKUP_REQUIRED = -2, HEARTH_PREFLIGHT_FAILED = -3,
    HEARTH_JOURNAL_FAILED = -4, HEARTH_STAGE_FAILED = -5,
    HEARTH_ACTIVATE_FAILED = -6, HEARTH_VERIFY_FAILED = -7,
    HEARTH_ROLLBACK_FAILED = -8
};
struct hearth_file_ops {
    int (*preflight)(void *, unsigned int);
    int (*journal)(void *, enum hearth_install_phase, unsigned int);
    int (*stage)(void *, unsigned int);
    int (*activate)(void *, unsigned int);
    int (*verify)(void *, unsigned int);
    int (*restore)(void *, unsigned int);
    int (*discard)(void *, unsigned int);
};
struct hearth_install_result {
    int error, rollback_error, journal_error, cleanup_error;
    unsigned int attempted, restored;
    int committed;
};
struct hearth_install_result hearth_install_files(
    const struct hearth_file_ops *, void *, unsigned int, int);
#endif
