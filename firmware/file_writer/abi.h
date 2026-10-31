/* Original minimal Linux ARM/glibc declarations, no native firmware headers. */
#ifndef HEARTH_FILE_ACTION_ABI_H
#define HEARTH_FILE_ACTION_ABI_H
typedef __SIZE_TYPE__ size_t;
extern int open(const char *,int,...),openat(int,const char *,int,...),close(int);
extern long read(int,void *,size_t),write(int,const void *,size_t);
extern int mount(const char *,const char *,const char *,unsigned long,const void *);
extern int umount2(const char *,int),nanosleep(const void *,void *);
extern unsigned int getuid(void),getgid(void),umask(unsigned int);
extern int *__errno_location(void),snprintf(char *,size_t,const char *,...);
extern int sscanf(const char *,const char *,...);
extern int memcmp(const void *,const void *,size_t);
extern void *memset(void *,int,size_t);
extern long syscall(long,...);
#define errno (*__errno_location())
#define O_RDONLY 0
#define O_WRONLY 1
#define O_RDWR 2
#define O_NONBLOCK 2048
#define O_DIRECTORY 16384
#define O_NOFOLLOW 32768
#define O_CLOEXEC 524288
#endif
