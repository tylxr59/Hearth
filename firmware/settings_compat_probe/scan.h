/* Original bounded streaming matcher, including bytes discarded from diagnostics. */
#ifndef HEARTH_COMPAT_SCAN_H
#define HEARTH_COMPAT_SCAN_H
struct stream_scan {
    const char *pattern;
    unsigned int size, matched, matches, prefix[64];
};
static int scan_init(struct stream_scan *scan, const char *pattern)
{
    unsigned int n = 0, i, j = 0;
    while (pattern[n] && n < 64) n++;
    if (!n || n >= 64) return 0;
    scan->pattern = pattern; scan->size = n; scan->matched = scan->matches = 0;
    scan->prefix[0] = 0;
    for (i = 1; i < n; i++) {
        while (j && pattern[i] != pattern[j]) j = scan->prefix[j-1];
        if (pattern[i] == pattern[j]) j++;
        scan->prefix[i] = j;
    }
    return 1;
}
static void scan_bytes(struct stream_scan *scan, const unsigned char *data, long count)
{
    for (long i = 0; i < count; i++) {
        while (scan->matched && data[i] != (unsigned char)scan->pattern[scan->matched]) scan->matched = scan->prefix[scan->matched-1];
        if (data[i] == (unsigned char)scan->pattern[scan->matched]) scan->matched++;
        if (scan->matched == scan->size) { scan->matches++; scan->matched = scan->prefix[scan->matched-1]; }
    }
}
#endif
