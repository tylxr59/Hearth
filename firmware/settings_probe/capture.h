/* Original bounded, separate child-output/diagnostic caches. No I/O or firmware. */
#ifndef HEARTH_SETTINGS_CAPTURE_H
#define HEARTH_SETTINGS_CAPTURE_H
#define SETTINGS_OUTPUT_LIMIT 8192
#define SETTINGS_DIAGNOSTIC_LIMIT 2048
#define SETTINGS_DROPPED_LIMIT 1048576
static unsigned char child_output[SETTINGS_OUTPUT_LIMIT];
static unsigned char child_diagnostics[SETTINGS_DIAGNOSTIC_LIMIT];
static long output_used, diagnostics_used, diagnostics_dropped;
static int capture_output(const unsigned char *data, long count)
{
    long i;
    if (count < 0 || count > SETTINGS_OUTPUT_LIMIT - output_used) return 0;
    for (i = 0; i < count; i++) child_output[output_used++] = data[i];
    return 1;
}
static int capture_diagnostics(const unsigned char *data, long count)
{
    long i;
    if (count < 0 || count > SETTINGS_DROPPED_LIMIT - diagnostics_dropped) return 0;
    for (i = 0; i < count; i++) {
        if (diagnostics_used < SETTINGS_DIAGNOSTIC_LIMIT) child_diagnostics[diagnostics_used++] = data[i];
        else diagnostics_dropped++;
    }
    return 1;
}
#endif
