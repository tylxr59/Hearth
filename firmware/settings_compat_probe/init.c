/* Original static ARM PID 1 for a single synthetic native-settings run.
 * No shell, storage mount, native application, HVAC interface or command API.
 * The only accepted USB input is a fixed start token. Results are cached in RAM.
 */
#include "../settings_probe/capture.h"
#include "scan.h"

static long sc(long nr, long a, long b, long c, long d, long e)
{
    register long r0 __asm__("r0") = a, r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c, r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e, r7 __asm__("r7") = nr;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r7) : "memory", "cc");
    return r0;
}
static void pause_one(void)
{
    long ts[2] = {1, 0}; sc(162, (long)ts, 0, 0, 0, 0);
}
static long now(void)
{
    long ts[2] = {0, 0};
    if (sc(263, 1, (long)ts, 0, 0, 0) != 0) return -1;
    return ts[0];
}
static char report[32768];
static struct stream_scan secrets, passthrough;
static long used;
static void append(const char *s)
{
    while (*s && used < (long)sizeof(report) - 1) report[used++] = *s++;
}
static void number(long value)
{
    char digits[16]; long count = 0;
    unsigned long magnitude = value < 0 ? 0UL - (unsigned long)value : (unsigned long)value;
    if (value < 0) append("-");
    do { digits[count++] = '0' + magnitude % 10; magnitude /= 10; } while (magnitude);
    while (count) { char digit[2] = {digits[--count], 0}; append(digit); }
}
static void child_failure(const char *stage, long code, long status)
{
    long begin = used;
    append("{\"type\":\"compat_launch_error\",\"stage\":\""); append(stage);
    append("\",\"code\":"); number(code); append("}\n");
    sc(4, 1, (long)(report + begin), used - begin, 0, 0);
    sc(248, status, 0, 0, 0, 0);
    for (;;) pause_one();
}
static int run(const char *variant, int candidate)
{
    int pipefd[2], errors[2], status = -1, pid, pfd[4];
    int output_open = 1, error_open = 1;
    long size, started, elapsed;
    unsigned char diagnostic[128], output_chunk[512];
    char *const argv[] = {"/settings-test", (char *)variant, 0};
    char *const env[] = {"LD_LIBRARY_PATH=/lib", "HOME=/nonexistent", "LC_ALL=C", candidate ?
        "LD_PRELOAD=/lib/libhearth-settings-compat.so:/lib/libhearth-settings-faults.so" :
        "LD_PRELOAD=/lib/libhearth-settings-faults.so", 0};
    output_used = diagnostics_used = diagnostics_dropped = 0;
    if (!scan_init(&secrets,"synthetic_secret_") || !scan_init(&passthrough,"HEARTH_COMPAT_LOG_PASSTHROUGH 17 probe 23 29 31 1.5")) return -211;
    if (sc(42, (long)pipefd, 0, 0, 0, 0) != 0) return -201;
    if (sc(42, (long)errors, 0, 0, 0, 0) != 0) {
        sc(6, pipefd[0], 0, 0, 0, 0); sc(6, pipefd[1], 0, 0, 0, 0); return -201;
    }
    pid = sc(2, 0, 0, 0, 0, 0);
    if (pid < 0) {
        sc(6, pipefd[0], 0, 0, 0, 0); sc(6, pipefd[1], 0, 0, 0, 0);
        sc(6, errors[0], 0, 0, 0, 0); sc(6, errors[1], 0, 0, 0, 0); return -202;
    }
    if (!pid) {
        long fd, n;
        sc(57, 0, 0, 0, 0, 0); /* isolated process group for the deadline */
        sc(63, pipefd[1], 1, 0, 0, 0);
        sc(63, errors[1], 2, 0, 0, 0);
        fd = sc(5, (long)"/dev/null", 2, 0, 0, 0);
        if (fd < 0) child_failure("null", fd, 120);
        sc(63, fd, 0, 0, 0, 0);
        for (n = 3; n < 64; n++) sc(6, n, 0, 0, 0, 0);
        n = sc(206, 0, 0, 0, 0, 0); if (n) child_failure("groups", n, 121);
        n = sc(214, 65534, 0, 0, 0, 0); if (n) child_failure("gid", n, 121);
        n = sc(213, 65534, 0, 0, 0, 0); if (n) child_failure("uid", n, 121);
        n = sc(11, (long)"/settings-test", (long)argv, (long)env, 0, 0);
        child_failure("exec", n, 122);
    }
    sc(6, pipefd[1], 0, 0, 0, 0);
    sc(6, errors[1], 0, 0, 0, 0);
    started = now();
    while (output_open || error_open) {
        elapsed = now();
        if (started < 0 || elapsed < started || elapsed - started > 120) {
            sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0);
            break;
        }
        pfd[0] = output_open ? pipefd[0] : -1; pfd[1] = 1;
        pfd[2] = error_open ? errors[0] : -1; pfd[3] = 1;
        size = sc(168, (long)pfd, 2, 1000, 0, 0);
        if (size < 0) {
            sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0);
            break;
        }
        if (size == 0) continue;
        if (output_open && (pfd[1] >> 16)) {
            size = sc(3, pipefd[0], (long)output_chunk, sizeof(output_chunk), 0, 0);
            if (size <= 0) output_open = 0;
            else if (!capture_output(output_chunk, size)) {
                sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0); break;
            }
        }
        if (error_open && (pfd[3] >> 16)) {
            size = sc(3, errors[0], (long)diagnostic, sizeof(diagnostic), 0, 0);
            if (size <= 0) error_open = 0;
            else {
                scan_bytes(&secrets,diagnostic,size); scan_bytes(&passthrough,diagnostic,size);
                if (!capture_diagnostics(diagnostic, size)) {
                sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0); break;
                }
            }
        }
    }
    sc(6, pipefd[0], 0, 0, 0, 0);
    sc(6, errors[0], 0, 0, 0, 0);
    if (sc(114, pid, (long)&status, 0, 0, 0) != pid) return -205;
    return status;
}
static void append_captured(const char *variant)
{
    static const char hex[] = "0123456789abcdef";
    long i, end;
    _Static_assert(2 * (SETTINGS_OUTPUT_LIMIT + 2 * SETTINGS_DIAGNOSTIC_LIMIT + 16 * 96 + 512) + 1024 < sizeof(report),
        "child output, hex diagnostics and metadata must fit independently");
    for (i = 0; i < output_used; i++) report[used++] = child_output[i];
    if (output_used && child_output[output_used - 1] != '\n') append("\n");
    for (i = 0; i < diagnostics_used;) {
        append("{\"type\":\"compat_stderr\",\"variant\":\""); append(variant); append("\",\"hex\":\"");
        end = i + 128 < diagnostics_used ? i + 128 : diagnostics_used;
        while (i < end) {
            char pair[3] = {hex[child_diagnostics[i] >> 4], hex[child_diagnostics[i] & 15], 0};
            append(pair); i++;
        }
        append("\"}\n");
    }
    if (diagnostics_dropped) {
        append("{\"type\":\"compat_stderr_truncated\",\"variant\":\""); append(variant); append("\",\"bytes_dropped\":");
        number(diagnostics_dropped); append("}\n");
    }
}
static void process_result(const char *variant, long status)
{
    append("{\"type\":\"compat_process\",\"variant\":\""); append(variant);
    append("\",\"wait_status\":"); number(status);
    append(",\"synthetic_secret_log_matches\":"); number(secrets.matches);
    append(",\"passthrough_log_matches\":"); number(passthrough.matches); append("}\n");
}
void __attribute__((noreturn)) _start(void)
{
    static const char token[] = "BEGIN_SETTINGS_COMPAT_V1\n";
    static const char ready[] = "HEARTH_SETTINGS_COMPAT_READY_V1\n";
    unsigned int tty[9];
    char input[64];
    long fd = -1, n, i, matched = 0, offset;
    int original, candidate;
    sc(21, (long)"proc", (long)"/proc", (long)"proc", 15, 0);
    sc(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 15, 0);
    sc(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10, (long)"mode=0755");
    for (;;) {
        fd = sc(5, (long)"/dev/ttyGS0", 2 | 0400 | 04000, 0, 0, 0);
        if (fd >= 0 && sc(54, fd, 0x5401, (long)tty, 0, 0) == 0) {
            tty[0] = 0; tty[1] = 0; tty[3] = 0;
            if (sc(54, fd, 0x5402, (long)tty, 0, 0) == 0) break;
        }
        if (fd >= 0) sc(6, fd, 0, 0, 0, 0);
        pause_one();
    }
    for (;;) {
        sc(4, fd, (long)ready, sizeof(ready) - 1, 0, 0);
        n = sc(3, fd, (long)input, sizeof(input), 0, 0);
        for (i = 0; i < n; i++) {
            if (input[i] == token[matched]) matched++;
            else matched = input[i] == token[0];
            if (matched == sizeof(token) - 1) goto begin;
        }
        pause_one();
    }
begin:
    append("HEARTH_SETTINGS_COMPAT_V1\n");
    original = run("original",0);
    append_captured("original"); process_result("original",original);
    candidate = run("candidate",1);
    append_captured("candidate"); process_result("candidate",candidate);
    append(original == 0 && candidate == 0 ?
        "{\"type\":\"compat_complete\",\"passed\":true}\n" :
        "{\"type\":\"compat_complete\",\"passed\":false}\n");
    append("END_HEARTH_SETTINGS_COMPAT\n");
    for (;;) {
        offset = 0;
        while (offset < used) {
            n = sc(4, fd, (long)(report + offset), used - offset, 0, 0);
            if (n <= 0) break;
            offset += n;
        }
        pause_one();
    }
}
