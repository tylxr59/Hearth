/* Original static ARM PID 1 for a single synthetic, loopback-only TLS run.
 * No shell, storage mount, native application, HVAC interface or command API.
 * The only accepted USB input is a fixed start token. Results are cached in RAM.
 */
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
static char report[16384];
static long used;
static void append(const char *s)
{
    while (*s && used < (long)sizeof(report) - 1) report[used++] = *s++;
}
static int loopback(void)
{
    struct { char name[16]; unsigned char value[16]; } req = {"lo", {0}};
    long fd = sc(281, 2, 2, 0, 0, 0), result;
    if (fd < 0) return 0;
    req.value[0] = 2; /* sockaddr_in: AF_INET, 127.0.0.1 */
    req.value[4] = 127; req.value[7] = 1;
    result = sc(54, fd, 0x8916, (long)&req, 0, 0); /* SIOCSIFADDR */
    req.value[0] = 0x49; req.value[1] = 0; /* UP | LOOPBACK | RUNNING */
    if (!result) result = sc(54, fd, 0x8914, (long)&req, 0, 0);
    sc(6, fd, 0, 0, 0, 0);
    return result == 0;
}
static int run(const char *variant)
{
    int pipefd[2], status = -1, pid, pfd[2];
    long size, started, elapsed;
    char *const argv[] = {"/tls-test", (char *)variant, 0};
    char *const env[] = {"LD_LIBRARY_PATH=/lib", "HOME=/nonexistent", "LC_ALL=C", 0};
    if (sc(42, (long)pipefd, 0, 0, 0, 0) != 0) return 0;
    pid = sc(2, 0, 0, 0, 0, 0);
    if (pid < 0) { sc(6, pipefd[0], 0, 0, 0, 0); sc(6, pipefd[1], 0, 0, 0, 0); return 0; }
    if (!pid) {
        long fd, n;
        sc(57, 0, 0, 0, 0, 0); /* isolated process group for the deadline */
        sc(63, pipefd[1], 1, 0, 0, 0);
        fd = sc(5, (long)"/dev/null", 2, 0, 0, 0);
        if (fd < 0) sc(248, 120, 0, 0, 0, 0);
        sc(63, fd, 0, 0, 0, 0); sc(63, fd, 2, 0, 0, 0);
        for (n = 3; n < 64; n++) sc(6, n, 0, 0, 0, 0);
        if (sc(206, 0, 0, 0, 0, 0) || sc(214, 65534, 0, 0, 0, 0) || sc(213, 65534, 0, 0, 0, 0))
            sc(248, 121, 0, 0, 0, 0);
        sc(11, (long)"/tls-test", (long)argv, (long)env, 0, 0);
        sc(248, 122, 0, 0, 0, 0);
        for (;;) pause_one();
    }
    sc(6, pipefd[1], 0, 0, 0, 0);
    started = now();
    for (;;) {
        elapsed = now();
        if (started < 0 || elapsed < started || elapsed - started > 120 || used >= (long)sizeof(report) - 256) {
            sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0);
            break;
        }
        pfd[0] = pipefd[0]; pfd[1] = 1; /* struct pollfd: POLLIN */
        size = sc(168, (long)pfd, 1, 1000, 0, 0);
        if (size < 0) {
            sc(37, -pid, 9, 0, 0, 0); sc(37, pid, 9, 0, 0, 0);
            break;
        }
        if (size == 0) continue;
        size = sc(3, pipefd[0], (long)(report + used), sizeof(report) - 256 - used, 0, 0);
        if (size <= 0) break;
        used += size;
    }
    sc(6, pipefd[0], 0, 0, 0, 0);
    sc(114, pid, (long)&status, 0, 0, 0);
    return status == 0;
}
void __attribute__((noreturn)) _start(void)
{
    static const char token[] = "BEGIN_TLS_TEST_V1\n";
    static const char ready[] = "HEARTH_TLS_READY_V1\n";
    unsigned int tty[9];
    char input[64];
    long fd = -1, n, i, matched = 0, offset;
    long tv[2] = {1893456000L, 0}; /* synthetic RAM clock: 2030-01-01 UTC */
    int setup, original, candidate;
    sc(21, (long)"proc", (long)"/proc", (long)"proc", 15, 0);
    sc(21, (long)"sysfs", (long)"/sys", (long)"sysfs", 15, 0);
    sc(21, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 10, (long)"mode=0755");
    setup = loopback() && sc(79, (long)tv, 0, 0, 0, 0) == 0;
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
    append("HEARTH_TLS_PROBE_V1\n");
    original = setup && run("original");
    candidate = setup && run("candidate");
    append(original && candidate ?
        "{\"type\":\"tls_complete\",\"passed\":true}\n" :
        "{\"type\":\"tls_complete\",\"passed\":false}\n");
    append("END_HEARTH_TLS_PROBE\n");
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
