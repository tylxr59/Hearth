/* Original bounded final-diagnostic window; no heap, I/O or firmware. */
#ifndef HEARTH_COMPAT_TAIL_H
#define HEARTH_COMPAT_TAIL_H
static int capture_diagnostic_tail(const unsigned char *data, long count)
{
    long discarded, keep, i;
    if (count < 0 || count > SETTINGS_DIAGNOSTIC_LIMIT) return 0;
    discarded = diagnostics_used + count - SETTINGS_DIAGNOSTIC_LIMIT;
    if (discarded < 0) discarded = 0;
    if (discarded > SETTINGS_DROPPED_LIMIT - diagnostics_dropped) return 0;
    keep = diagnostics_used - discarded;
    for (i = 0; i < keep; i++) child_diagnostics[i] = child_diagnostics[i + discarded];
    for (i = 0; i < count; i++) child_diagnostics[keep + i] = data[i];
    diagnostics_used = keep + count;
    diagnostics_dropped += discarded;
    return 1;
}
#endif
