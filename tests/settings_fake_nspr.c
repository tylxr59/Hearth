/* Original host test double for documented NSPR file operations; no native code. */
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
struct handle { int fd; };
void *PR_Open(const char *path, int flags, int mode)
{
    int bits = flags == 1 ? O_RDONLY : O_WRONLY | O_CREAT | O_TRUNC;
    struct handle *h = malloc(sizeof(*h));
    if (!h) return NULL;
    h->fd = open(path, bits, mode);
    if (h->fd < 0) { free(h); return NULL; }
    return h;
}
int PR_Write(void *fd, const void *buffer, int amount) { return write(((struct handle *)fd)->fd, buffer, amount); }
int PR_Sync(void *fd) { return fsync(((struct handle *)fd)->fd); }
int PR_Close(void *fd)
{
    int result = close(((struct handle *)fd)->fd); free(fd); return result;
}
void PR_SetError(int code, int os) { (void)code; (void)os; }
