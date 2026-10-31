/* Original Hearth fixed scratch transaction, GPL-2.0-or-later. */
#include "core.h"
#ifdef __KERNEL__
#include <linux/string.h>
#else
#include <string.h>
#endif

static const unsigned char cleanmarker[8] = {0x85, 0x19, 0x03, 0x20, 8, 0, 0, 0};

int hs_canonical(const unsigned char *block)
{
    unsigned int p, i;
    for (p = 0; p < HS_PAGES; ++p) {
        for (i = 0; i < HS_RECORD; ++i) {
            unsigned char expected = 0xff;
            if (p == 0 && i >= HS_DATA + 2 && i < HS_DATA + 10)
                expected = cleanmarker[i - HS_DATA - 2];
            if (block[p * HS_RECORD + i] != expected)
                return 0;
        }
    }
    return 1;
}

static int fail(struct hs_tx *tx, enum hs_error error)
{
    tx->report.error = error;
    tx->state = HS_FAILED;
    return -(int)error;
}

static int guarded(const struct hs_ops *ops, void *ctx)
{
    return ops->guard(ctx) == 0 && ops->protected(ctx) == 1;
}

int hs_prepare(struct hs_tx *tx, const struct hs_ops *ops, void *ctx)
{
    unsigned int p;
    if (tx->state != HS_EMPTY)
        return -(int)HS_BAD_STATE;
    tx->state = HS_PREPARING;
    if (!guarded(ops, ctx))
        return fail(tx, HS_GUARD);
    for (p = 0; p < HS_PAGES; ++p) {
        if (!guarded(ops, ctx) || ops->read(ctx, p, 0, tx->original + p * HS_RECORD))
            return fail(tx, HS_READ);
    }
    for (p = 0; p < HS_PAGES; ++p) {
        if (!guarded(ops, ctx) || ops->read(ctx, p, 0, tx->page))
            return fail(tx, HS_READ);
        if (memcmp(tx->page, tx->original + p * HS_RECORD, HS_RECORD))
            return fail(tx, HS_CHANGED);
    }
    if (!hs_canonical(tx->original))
        return fail(tx, HS_NOT_EMPTY);
    if (ops->hash(ctx, tx->original, HS_BYTES, tx->digest))
        return fail(tx, HS_HASH);
    if (!guarded(ops, ctx))
        return fail(tx, HS_GUARD);
    tx->report.final_protected = 1;
    tx->state = HS_READY;
    return 0;
}

/* One hardware operation per call. Always try to reassert protection even if
 * enabling it failed. A protection failure stops cleanup too: do not pretend a
 * safe state exists or issue further writes after losing the guard.
 */
static enum hs_error mutate(struct hs_tx *tx, const struct hs_ops *ops, void *ctx,
                            unsigned int operation, int *attempted, int *result)
{
    int enabled, protected_result;
    enum hs_error error = HS_OK;
    *attempted = 0;
    if (!guarded(ops, ctx))
        return HS_GUARD;
    enabled = ops->writable(ctx, 1);
    if (enabled || ops->protected(ctx) != 0 || ops->guard(ctx)) {
        error = HS_PROTECTION;
    } else {
        *attempted = 1;
        if (operation == 0)
            *result = ops->program(ctx, tx->pattern);
        else if (operation == 1)
            *result = ops->erase(ctx);
        else
            *result = ops->marker(ctx, cleanmarker);
    }
    protected_result = ops->writable(ctx, 0);
    tx->report.final_protected = ops->protected(ctx) == 1;
    if (protected_result || !tx->report.final_protected)
        return HS_PROTECTION;
    if (ops->guard(ctx))
        return HS_GUARD;
    return error;
}

int hs_execute(struct hs_tx *tx, const struct hs_ops *ops, void *ctx,
               const unsigned char *ack)
{
    enum hs_error status, failure = HS_OK;
    int attempted, result;
    unsigned int p, i;
    if (tx->state != HS_READY)
        return -(int)HS_BAD_STATE;
    /* A wrong acknowledgement consumes the prepared transaction. */
    tx->state = HS_RUNNING;
    if (!ack || memcmp(ack, tx->digest, HS_DIGEST))
        return fail(tx, HS_ACK);
    if (!guarded(ops, ctx) || !hs_canonical(tx->original))
        return fail(tx, HS_GUARD);
    /* Re-read immediately before mutation. An ACK cannot authorize a changed
     * block, even when the saved original remains canonical.
     */
    for (p = 0; p < HS_PAGES; ++p) {
        if (!guarded(ops, ctx) || ops->read(ctx, p, 0, tx->page))
            return fail(tx, HS_READ);
        if (memcmp(tx->page, tx->original + p * HS_RECORD, HS_RECORD))
            return fail(tx, HS_CHANGED);
    }
    for (i = 0; i < HS_DATA; ++i)
        tx->pattern[i] = (unsigned char)((i * 73u) ^ (i >> 8) ^ 0xa5u);
    result = 0;
    status = mutate(tx, ops, ctx, 0, &attempted, &result);
    tx->report.program_attempted = attempted;
    tx->report.program_result = result;
    if (status)
        return fail(tx, status);
    if (!attempted)
        return fail(tx, HS_PROGRAM);
    if (result)
        failure = HS_PROGRAM;
    if (!guarded(ops, ctx) || ops->read(ctx, HS_TEST_PAGE, 0, tx->programmed_raw)
        || !guarded(ops, ctx) || ops->read(ctx, HS_TEST_PAGE, 1, tx->programmed_normal)) {
        failure = HS_READ;
    } else {
        tx->report.program_data_match =
            !memcmp(tx->programmed_raw, tx->pattern, HS_DATA) &&
            !memcmp(tx->programmed_normal, tx->pattern, HS_DATA);
        if (!tx->report.program_data_match)
            failure = HS_PROGRAM;
    }
    /* Program callback errors may follow a partial write. Still perform the
     * single planned erase/marker restoration if protection and bounds hold.
     * No second program, erase retry or arbitrary recovery write is allowed.
     */
    result = 0;
    status = mutate(tx, ops, ctx, 1, &attempted, &result);
    tx->report.erase_attempted = attempted;
    tx->report.erase_result = result;
    if (status)
        return fail(tx, status);
    if (!attempted || result)
        return fail(tx, HS_ERASE);
    /* Do not trust a zero erase status before programming the marker. */
    for (p = 0; p < HS_PAGES; ++p) {
        if (!guarded(ops, ctx) || ops->read(ctx, p, 0, tx->page))
            return fail(tx, HS_READ);
        for (i = 0; i < HS_RECORD; ++i)
            if (tx->page[i] != 0xff)
                return fail(tx, HS_ERASE);
    }
    result = 0;
    status = mutate(tx, ops, ctx, 2, &attempted, &result);
    tx->report.marker_attempted = attempted;
    tx->report.marker_result = result;
    if (status)
        return fail(tx, status);
    if (!attempted || result)
        failure = HS_MARKER;
    for (p = 0; p < HS_PAGES; ++p) {
        if (!guarded(ops, ctx) || ops->read(ctx, p, 0, tx->final + p * HS_RECORD))
            return fail(tx, HS_READ);
    }
    if (ops->hash(ctx, tx->final, HS_BYTES, tx->final_digest))
        return fail(tx, HS_HASH);
    tx->report.restored = !memcmp(tx->original, tx->final, HS_BYTES) &&
                         !memcmp(tx->digest, tx->final_digest, HS_DIGEST);
    tx->report.final_protected = ops->protected(ctx) == 1;
    if (!tx->report.final_protected || ops->guard(ctx))
        return fail(tx, HS_PROTECTION);
    if (!tx->report.restored && failure == HS_OK)
        failure = HS_RESTORE;
    if (failure)
        return fail(tx, failure);
    tx->state = HS_DONE;
    return 0;
}
