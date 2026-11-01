/* Original write lifecycle, MIT. Remount attempts count as potentially persistent
 * even when the syscall fails: the filesystem may have started background GC. */
#include "lifecycle.h"
#ifndef HEARTH_FILE_MASK
#define HEARTH_FILE_MASK 511U
#endif
#if HEARTH_FILE_MASK != 511U && HEARTH_FILE_MASK != 15U
#error "Only the reviewed nine-file and four-file scopes are supported"
#endif
static int valid(const struct hfa_ops *ops,void *context)
{
    return context&&ops&&ops->preflight&&ops->open_window&&ops->remount_rw&&
        ops->transact&&ops->release&&ops->unmount&&ops->seal&&ops->verify_readonly;
}
static void finish(const struct hfa_ops *ops,void *context,struct hfa_result *r)
{
    if(ops->release(context)) r->release_error=1;
    if(ops->unmount(context,1)) r->unmount_errors|=2;
    if(ops->unmount(context,0)) r->unmount_errors|=1;
    /* Protection must be attempted even after a cleanup error. */
    if(ops->seal(context)) r->seal_error=1;
    if(!r->release_error&&!r->unmount_errors&&!r->seal_error) {
        if(r->rw_attempted)
            r->verified=ops->verify_readonly(context,
                r->transaction_called&&r->transaction.committed)==0;
        r->safe_to_restart=!r->rw_attempted||r->verified;
    }
}
struct hfa_result hfa_run(const struct hfa_ops *ops,void *context,int restoring)
{
    struct hfa_result r={0};unsigned int i;
    r.transaction.error=HEARTH_BACKUP_REQUIRED;
    if(!valid(ops,context)||(restoring!=0&&restoring!=1)) { r.stage_error=1;return r; }
    if(ops->preflight(context)) { r.stage_error=2;goto done; }
    if(ops->open_window(context)) { r.stage_error=3;goto done; }
    r.window_opened=1;
    for(i=0;i<2;i++) {
        r.rw_attempted|=1U<<i;
        if(ops->remount_rw(context,i)) { r.stage_error=4+i;goto done; }
    }
    r.transaction_called=1;
    ops->transact(context,&r.transaction);
done:
    finish(ops,context,&r);
    if(r.transaction_called&&r.safe_to_restart&&!r.stage_error&&!r.transaction.error&&
       !r.transaction.rollback_error&&!r.transaction.journal_error&&!r.transaction.cleanup_error) {
        if(restoring) r.complete=!r.transaction.committed&&r.transaction.attempted==HEARTH_FILE_MASK&&r.transaction.restored==HEARTH_FILE_MASK;
        else r.complete=r.transaction.committed==1;
    }
    return r;
}
struct hfa_result hfa_cancel(const struct hfa_ops *ops,void *context)
{
    struct hfa_result r={0};r.transaction.error=HEARTH_BACKUP_REQUIRED;
    if(!valid(ops,context)) { r.stage_error=1;return r; }
    finish(ops,context,&r);
    return r;
}
