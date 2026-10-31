/* Original minimal ARM declarations for the synthetic-only file harness. */
#ifndef HEARTH_FILE_LAB_ABI_H
#define HEARTH_FILE_LAB_ABI_H
#include "../tls_probe/abi.h"
typedef long ssize_t;
typedef long long off_t;
typedef unsigned int mode_t,uid_t,gid_t;
struct stat { unsigned int st_mode; long long st_size; };
extern int open(const char *,int,...),openat(int,const char *,int,...);
extern int mkdir(const char *,unsigned int),mkdirat(int,const char *,unsigned int);
extern int fchmod(int,mode_t),fchown(int,uid_t,gid_t),fsync(int);
extern int fchmodat(int,const char *,mode_t,int);
extern int renameat(int,const char *,int,const char *),unlinkat(int,const char *,int);
extern int linkat(int,const char *,int,const char *,int),symlinkat(const char *,int,const char *);
extern int mkfifoat(int,const char *,mode_t);
extern ssize_t read(int,void *,size_t),readlink(const char *,char *,size_t);
extern uid_t getuid(void);extern gid_t getgid(void);
extern int *__errno_location(void),atoi(const char *);
extern size_t strlen(const char *);
extern int memcmp(const void *,const void *,size_t);
extern void *memset(void *,int,size_t);
extern long syscall(long,...);
#define NULL ((void *)0)
#define errno (*__errno_location())
#define EPERM 1
#define ENOENT 2
#define EIO 5
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 64
#define O_TRUNC 512
#define O_DIRECTORY 16384
#define O_NOFOLLOW 32768
#define AT_SYMLINK_NOFOLLOW 256
#define S_ISREG(mode) (((mode)&0170000)==0100000)
#define S_ISDIR(mode) (((mode)&0170000)==0040000)
static unsigned int lab_word(const unsigned char *b)
{ return b[0]|(unsigned int)b[1]<<8|(unsigned int)b[2]<<16|(unsigned int)b[3]<<24; }
static int lab_stat(long nr,int fd,const char *path,struct stat *s,int flags)
{
    unsigned long long buffer[16];unsigned char *b=(unsigned char *)buffer;long result;
    result=nr==197?syscall(nr,fd,buffer):syscall(nr,fd,path,buffer,flags);
    if(result) return -1;
    s->st_mode=lab_word(b+16);s->st_size=(long long)((unsigned long long)lab_word(b+48)|(unsigned long long)lab_word(b+52)<<32);
    return 0;
}
#define fstat(fd,s) lab_stat(197,fd,0,s,0)
#define fstatat(fd,path,s,flags) lab_stat(327,fd,path,s,flags)
static void __attribute__((noreturn)) lab_fail(int line)
{
    char message[64];int n=snprintf(message,sizeof(message),"FILE_LAB_ASSERT %d\n",line);
    if(n>0&&n<(int)sizeof(message)) write(2,message,n);
    _exit(130);
}
#define assert(condition) ((condition)?(void)0:lab_fail(__LINE__))
#endif
