/* Original ELF interposition for fixed synthetic files, never production use.
 * No interception of thermostat settings, no persistent install, no threads.
 * PR_Close injection closes the real handle, then reports failure (explicit model).
 */
#include "faults.h"
extern int *__errno_location(void);
static void *(*open_real)(const char *, int, int);
static int (*write_real)(void *, const void *, int);
static int (*sync_real)(void *), (*close_real)(void *);
static int (*rename_real)(const char *, const char *);
static void (*error_real)(int, int);
static enum fault selected;
static const char *dir_path, *dest_path, *temp_path;
static void *file_fd, *dir_fd;
struct counts observed;

int fault_load(void)
{
#define LOAD(p, n) do { p = (__typeof__(p))dlsym((void *)-1L, n); if (!p) return 0; } while (0)
    LOAD(open_real, "PR_Open"); LOAD(write_real, "PR_Write");
    LOAD(sync_real, "PR_Sync"); LOAD(close_real, "PR_Close");
    LOAD(rename_real, "rename"); LOAD(error_real, "PR_SetError");
#undef LOAD
    return 1;
}
void fault_begin(enum fault mode, const char *directory, const char *destination, const char *temporary)
{
    selected = mode; dir_path = directory; dest_path = destination; temp_path = temporary;
    file_fd = dir_fd = 0;
    observed = (struct counts){0, 0, 0, 0, 0, 0, 0};
}
void fault_disarm(void)
{
    selected = NORMAL; dir_path = dest_path = temp_path = 0; file_fd = dir_fd = 0;
}
static int inject(enum fault expected)
{
    if (selected != expected || observed.injected) return 0;
    observed.injected++;
    error_real(-5991, 5); /* public PR_IO_ERROR, Linux EIO */
    *__errno_location() = 5;
    return 1;
}
void *PR_Open(const char *name, int flags, int mode)
{
    void *fd;
    int file = temp_path && strcmp(name, temp_path) == 0 && flags == 0x2a;
    int directory = dir_path && strcmp(name, dir_path) == 0 && flags == 1;
    if (!open_real && !fault_load()) _exit(100);
    if (file) { observed.file_opens++; if (inject(FILE_OPEN)) return 0; }
    if (directory) { observed.dir_opens++; if (inject(DIR_OPEN)) return 0; }
    fd = open_real(name, flags, mode);
    if (file) file_fd = fd;
    if (directory) dir_fd = fd;
    return fd;
}
int PR_Write(void *fd, const void *buffer, int amount)
{
    const char *s = buffer;
    int i, entry = 0;
    if (!write_real && !fault_load()) _exit(100);
    if (fd && fd == file_fd) {
        observed.writes++;
        for (i = 0; i + 3 < amount; i++)
            if (s[i] == '<' && s[i+1] == 's' && s[i+2] == ' ') entry = 1;
        if (observed.writes == 1 && inject(HEADER_WRITE)) return -1;
        if (entry && inject(ENTRY_ERROR)) return -1;
        if (entry && inject(ENTRY_SHORT)) return write_real(fd, buffer, amount / 2);
        if (amount >= 11 && s[0] == '<' && s[1] == '/' && inject(FOOTER_WRITE)) return -1;
    }
    return write_real(fd, buffer, amount);
}
int PR_Sync(void *fd)
{
    if (!sync_real && !fault_load()) _exit(100);
    if (fd && fd == file_fd) { observed.file_syncs++; if (inject(FILE_SYNC)) return -1; }
    if (fd && fd == dir_fd) { observed.dir_syncs++; if (inject(DIR_SYNC)) return -1; }
    return sync_real(fd);
}
int PR_Close(void *fd)
{
    int file = fd && fd == file_fd, directory = fd && fd == dir_fd;
    int result;
    if (!close_real && !fault_load()) _exit(100);
    result = close_real(fd);
    if (file) file_fd = 0;
    if (directory) dir_fd = 0;
    if ((file && inject(FILE_CLOSE)) || (directory && inject(DIR_CLOSE))) return -1;
    return result;
}
int rename(const char *from, const char *to)
{
    if (!rename_real && !fault_load()) _exit(100);
    if (temp_path && dest_path && strcmp(from, temp_path) == 0 && strcmp(to, dest_path) == 0) {
        observed.renames++;
        if (inject(RENAME)) return -1;
    }
    return rename_real(from, to);
}
