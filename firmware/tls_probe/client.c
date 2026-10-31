/* Original bounded TLS laboratory. Runs ONLY in the experimental RAM image.
 * Loads owner-provided native libraries, never nlclient/osm or a control API.
 * All peers are loopback and all certificates/keys are synthetic fixtures.
 * Public API constants are pinned in sources.json by the preparation tooling.
 */
#include "abi.h"

static void *(*ctx_new)(const void *);
static const void *(*server_method)(void);
static int (*ctx_cert)(void *, const char *), (*ctx_key)(void *, const char *, int);
static void *(*ssl_new)(void *);
static int (*ssl_fd)(void *, int), (*ssl_accept)(void *);
static int (*ssl_read)(void *, void *, int), (*ssl_write)(void *, const void *, int);
static void (*ssl_free)(void *), (*ctx_free)(void *);
static int (*ssl_shutdown)(void *);
static void *(*easy_init)(void);
static int (*easy_setopt)(void *, int, ...), (*easy_perform)(void *);
static void (*easy_cleanup)(void *);
static void *hook;

static const char *const cases[] = {
    "valid", "wrong_ca", "wrong_host", "expired_cert", "future_cert",
    "missing_issuer_crl", "expired_crl", "future_crl", "revoked_cert"
};

static int emit(const char *variant, const char *name, int code, int passed)
{
    char line[256];
    int size = snprintf(line, sizeof(line),
        "{\"type\":\"tls_case\",\"variant\":\"%s\",\"case\":\"%s\","
        "\"curl_code\":%d,\"passed\":%s}\n",
        variant, name, code, passed ? "true" : "false");
    return size > 0 && size < (int)sizeof(line) && write(1, line, size) == size;
}

static size_t discard(char *data, size_t size, size_t count, void *context)
{
    (void)data; (void)context;
    return size * count;
}

static int load(const char *variant)
{
    void *ssl = dlopen("/lib/libssl.so.1.0.0", 1);
    void *curl = dlopen("/lib/libcurl.so.4", 1);
    void *native = dlopen(strcmp(variant, "original") == 0 ?
        "/lib/libnlwebservice.so" : "/lib/libnlwebservice.review.so", 1);
    int (*library_init)(void);
    int (*global_init)(long);
    int ordinal = 0;
    if (!ssl || !curl || !native) {
        char line[640], *error = dlerror();
        int i, n = 0;
        static const char prefix[] = "{\"type\":\"tls_loader_error\",\"detail\":\"";
        for (i = 0; i < (int)sizeof(prefix) - 1; i++) line[n++] = prefix[i];
        for (i = 0; error && error[i] && i < 256; i++) {
            unsigned char c = error[i];
            if (c == '"' || c == '\\') line[n++] = '\\';
            line[n++] = c >= 32 && c < 127 ? c : '?';
        }
        line[n++] = '"'; line[n++] = '}'; line[n++] = '\n';
        write(1, line, n); /* retained privately on failure; never a success report */
        return !ssl ? -101 : (!curl ? -102 : -103);
    }
#define LOAD(destination, handle, name) \
    do { ordinal++; (destination) = (__typeof__(destination))dlsym(handle, name); if (!(destination)) return -110 - ordinal; } while (0)
    LOAD(library_init, ssl, "SSL_library_init");
    LOAD(server_method, ssl, "TLSv1_2_server_method");
    LOAD(ctx_new, ssl, "SSL_CTX_new");
    LOAD(ctx_cert, ssl, "SSL_CTX_use_certificate_chain_file");
    LOAD(ctx_key, ssl, "SSL_CTX_use_PrivateKey_file");
    LOAD(ssl_new, ssl, "SSL_new"); LOAD(ssl_fd, ssl, "SSL_set_fd");
    LOAD(ssl_accept, ssl, "SSL_accept"); LOAD(ssl_read, ssl, "SSL_read");
    LOAD(ssl_write, ssl, "SSL_write"); LOAD(ssl_shutdown, ssl, "SSL_shutdown");
    LOAD(ssl_free, ssl, "SSL_free"); LOAD(ctx_free, ssl, "SSL_CTX_free");
    LOAD(global_init, curl, "curl_global_init"); LOAD(easy_init, curl, "curl_easy_init");
    LOAD(easy_setopt, curl, "curl_easy_setopt"); LOAD(easy_perform, curl, "curl_easy_perform");
    LOAD(easy_cleanup, curl, "curl_easy_cleanup");
    hook = dlsym(native, "_Z9sslctxfunPvS_S_");
    if (!hook) return -140;
    if (library_init() != 1) return -141;
    if (global_init(3) != 0) return -142;
    return 1;
#undef LOAD
}

static int run_case(int index)
{
    static const char reply[] =
        "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok";
    const char *cert = "/fixtures/valid.pem", *ca = "/fixtures/ca.pem";
    const char *crl = "/fixtures/good.crl";
    struct address address = {2, 0xfb20, 0x0100007f, {0}}; /* 127.0.0.1:8443, LE ARM */
    int fd = -1, peer = -1, pid, result = -1, status, one = 1, configured = 1;
    void *ctx = 0, *connection = 0, *client = 0;
    char request[1024];
    if (index == 1) ca = "/fixtures/other-ca.pem";
    if (index == 2) cert = "/fixtures/wrong-host.pem";
    if (index == 3) cert = "/fixtures/expired.pem";
    if (index == 4) cert = "/fixtures/future.pem";
    if (index == 5) crl = "/fixtures/other.crl";
    if (index == 6) crl = "/fixtures/expired.crl";
    if (index == 7) crl = "/fixtures/future.crl";
    if (index == 8) crl = "/fixtures/revoked.crl";
    ctx = ctx_new(server_method());
    if (!ctx || ctx_cert(ctx, cert) != 1 || ctx_key(ctx, "/fixtures/server.key", 1) != 1)
        goto done;
    fd = socket(2, 1, 0);
    if (fd < 0 || setsockopt(fd, 1, 2, &one, sizeof(one)) != 0 ||
        bind(fd, &address, sizeof(address)) != 0 || listen(fd, 1) != 0) goto done;
    pid = fork();
    if (pid < 0) goto done;
    if (pid == 0) {
        alarm(10);
        peer = accept(fd, 0, 0);
        if (peer < 0) _exit(20);
        close(fd);
        connection = ssl_new(ctx);
        if (!connection || ssl_fd(connection, peer) != 1) _exit(21);
        if (ssl_accept(connection) != 1) _exit(22);
        if (ssl_read(connection, request, sizeof(request)) < 1) _exit(23);
        if (ssl_write(connection, reply, sizeof(reply) - 1) != sizeof(reply) - 1) _exit(24);
        ssl_shutdown(connection); ssl_free(connection); close(peer); ctx_free(ctx);
        _exit(0);
    }
    close(fd); fd = -1;
    client = easy_init();
    if (client) {
#define SET(option, value) do { if (easy_setopt(client, option, value) != 0) configured = 0; } while (0)
        SET(10002, "https://127.0.0.1:8443/"); /* URL */
        SET(10065, ca); SET(10169, crl);       /* CAINFO, CRLFILE */
        SET(64, 1L); SET(81, 2L);             /* VERIFYPEER, VERIFYHOST */
        SET(32, 6L);                         /* TLSv1_2 */
        SET(99, 1L); SET(13, 5L); SET(78, 3L);/* NOSIGNAL, bounded timeouts */
        SET(20108, hook);                    /* exact native SSL-context hook */
        SET(20011, discard);                 /* no response-body logging */
        if (configured) result = easy_perform(client);
        easy_cleanup(client);
#undef SET
    }
    if (waitpid(pid, &status, 0) != pid) result = -2;
    if (result == 0 && status != 0) result = -3;
done:
    if (fd >= 0) close(fd);
    if (ctx) ctx_free(ctx);
    return result;
}

int main(int argc, char **argv)
{
    int index, code, expected, failures = 0, candidate;
    const char *variant;
    if (argc != 2 || (strcmp(argv[1], "original") && strcmp(argv[1], "candidate"))) return 2;
    variant = argv[1]; candidate = strcmp(variant, "candidate") == 0;
    signal(13, (void (*)(int))1); /* SIGPIPE ignored, never a test success */
    code = time(0) < 1893456000L || time(0) > 1893456300L ? -150 : load(variant);
    if (code != 1) {
        emit(variant, "setup", code, 0);
        return 3;
    }
    for (index = 0; index < 9; index++) {
        expected = index == 0 || (!candidate && (index == 4 || index == 5 || index == 6 || index == 7));
        code = run_case(index);
        /* A connection/setup failure cannot count as certificate rejection. */
        /* curl 7.49.1 uses 51 for hostname mismatch and 60 for CA-chain errors. */
        if (code != (expected ? 0 : (index == 2 ? 51 : 60))) failures++;
        if (!emit(variant, cases[index], code, code == (expected ? 0 : (index == 2 ? 51 : 60)))) return 4;
    }
    return failures ? 1 : 0;
}
