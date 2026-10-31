/* Original transaction ordering. Multi-file power-loss atomicity is NOT claimed. */
#include "transaction.h"

static void cleanup(const struct hearth_file_ops *ops, void *context,
                    unsigned int count, struct hearth_install_result *result)
{
    while (count) if (ops->discard(context, --count)) result->cleanup_error = 1;
}
static void rollback(const struct hearth_file_ops *ops, void *context,
                     unsigned int count, struct hearth_install_result *result)
{
    unsigned int index = count;
    /* A journal failure must never prevent an otherwise possible restoration. */
    if (ops->journal(context, HEARTH_RESTORING, result->attempted)) result->journal_error = 1;
    while (index) {
        unsigned int bit = 1U << --index;
        if (!(result->attempted & bit)) continue;
        if (ops->restore(context,index)) result->rollback_error = 1;
        else result->restored |= bit;
    }
    if (ops->journal(context, result->rollback_error ? HEARTH_RESTORE_FAILED : HEARTH_RESTORED,
                     result->restored)) result->journal_error = 1;
    if (!result->rollback_error) cleanup(ops,context,count,result);
}
struct hearth_install_result hearth_install_files(
    const struct hearth_file_ops *ops, void *context, unsigned int count,
    int host_backup_confirmed)
{
    struct hearth_install_result result = {0,0,0,0,0,0,0};
    unsigned int index;
    if (!context || !ops || !ops->preflight || !ops->journal || !ops->stage || !ops->activate ||
        !ops->verify || !ops->restore || !ops->discard || !count || count>HEARTH_FILE_LIMIT) {
        result.error = HEARTH_INVALID_PLAN; return result;
    }
    if (host_backup_confirmed != 1) { result.error = HEARTH_BACKUP_REQUIRED; return result; }
    /* Complete every read-only check before the first journal/staging mutation. */
    for (index=0;index<count;index++) if (ops->preflight(context,index)) {
        result.error = HEARTH_PREFLIGHT_FAILED; return result;
    }
    if (ops->journal(context,HEARTH_PREPARING,0)) {
        result.error = HEARTH_JOURNAL_FAILED; result.journal_error = 1; return result;
    }
    for (index=0;index<count;index++) if (ops->stage(context,index)) {
        result.error = HEARTH_STAGE_FAILED; rollback(ops,context,count,&result); return result;
    }
    if (ops->journal(context,HEARTH_STAGED,0)) {
        result.error = HEARTH_JOURNAL_FAILED; result.journal_error = 1;
        rollback(ops,context,count,&result); return result;
    }
    for (index=0;index<count;index++) {
        unsigned int next = result.attempted | (1U << index);
        /* Record intent before rename: an error may mean rename succeeded but
         * directory sync failed. Include that uncertain file in rollback. */
        if (ops->journal(context,HEARTH_COMMITTING,next)) {
            result.error = HEARTH_JOURNAL_FAILED; result.journal_error = 1;
            rollback(ops,context,count,&result); return result;
        }
        result.attempted = next;
        if (ops->activate(context,index)) {
            result.error = HEARTH_ACTIVATE_FAILED;
            rollback(ops,context,count,&result); return result;
        }
    }
    for (index=0;index<count;index++) if (ops->verify(context,index)) {
        result.error = HEARTH_VERIFY_FAILED; rollback(ops,context,count,&result); return result;
    }
    if (ops->journal(context,HEARTH_COMMITTED,result.attempted)) {
        result.error = HEARTH_JOURNAL_FAILED; result.journal_error = 1;
        rollback(ops,context,count,&result); return result;
    }
    result.committed = 1;
    /* Private originals/journal remain for later owner-reviewed rollback.
     * discard removes only staging files created by this invocation. */
    cleanup(ops,context,count,&result);
    return result;
}
