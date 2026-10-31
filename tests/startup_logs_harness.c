/* Original trusted-host filesystem adapter for the read-only log core (MIT). */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "../firmware/startup_diagnostic/logs.h"
static int h_open(int fd,const char *p) { return openat(fd,p,O_RDONLY|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC); }
static int h_close(int fd) { return close(fd); }
static int h_meta(int fd,struct hfd_stat *out)
{ struct stat s;if(fstat(fd,&s)||s.st_size<0||s.st_size>0x7fffffff) return -1;out->mode=s.st_mode;out->owner=s.st_uid;out->group=s.st_gid;out->size=s.st_size;return 0; }
static int h_dir(int fd) { struct stat s;return fstat(fd,&s)||!S_ISDIR(s.st_mode); }
static long h_entries(int fd,unsigned char *p,unsigned int n) { return syscall(SYS_getdents64,fd,p,n); }
static long h_read(int fd,unsigned char *p,unsigned int n) { return read(fd,p,n); }
static long h_seek(int fd,unsigned int n) { return lseek(fd,n,SEEK_SET); }
static const struct hfd_ops ops={h_open,h_close,h_meta,h_dir,h_entries,h_read,h_seek};
static unsigned char output[HFD_LIMIT];
int main(int argc,char **argv)
{ unsigned int n;int fd;if(argc!=2) return 1;fd=open(argv[1],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0) return 2;n=hfd_capture(&ops,fd,output,sizeof(output));if(close(fd)||n<16||fwrite(output,1,n,stdout)!=n) return 3;return 0; }
