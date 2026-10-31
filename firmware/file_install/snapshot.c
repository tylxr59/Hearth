/* Original bounded read-only filesystem capture (MIT).
 * Production refuses writable mounts, non-JFFS2, attributes and unsafe paths.
 * No file bytes or identifiers are logged. No write-capable syscall is used.
 */
#include "snapshot.h"
#include "targets.h"
#ifdef HEARTH_RAM_LAB
#error "Snapshot production guards must not use the writable RAM lab adapter"
#endif
#ifdef HEARTH_HOST_LAB
#include <sys/stat.h>
#include <sys/vfs.h>
#include <sys/xattr.h>
#include <fcntl.h>
#include <unistd.h>
#define H_DIRECTORY O_DIRECTORY
#define H_NOFOLLOW O_NOFOLLOW
#define H_CLOEXEC O_CLOEXEC
#else
extern int openat(int,const char *,int,...),close(int);
extern long read(int,void *,hearth_file_size),lseek(int,long,int);
extern long syscall(long,...),flistxattr(int,char *,hearth_file_size);
#define H_DIRECTORY 16384
#define H_NOFOLLOW 32768
#define H_CLOEXEC 524288
#endif
extern int *__errno_location(void);
struct captured_stat {
    unsigned int mode,links,owner,group;
    unsigned long long size;
};
static void clear(void *p,hearth_file_size n)
{ volatile unsigned char *b=p; while(n--) *b++=0; }
#ifndef HEARTH_HOST_LAB
static unsigned int word(const unsigned char *b)
{ return b[0]|(unsigned int)b[1]<<8|(unsigned int)b[2]<<16|(unsigned int)b[3]<<24; }
#endif
static int metadata(int fd,struct captured_stat *m)
{
#ifdef HEARTH_HOST_LAB
    struct stat s;
    if(fstat(fd,&s)) return -1;
    m->mode=s.st_mode;m->links=s.st_nlink;m->owner=s.st_uid;
    m->group=s.st_gid;m->size=(unsigned long long)s.st_size;
#else
    unsigned long long data[16];unsigned char *b=(unsigned char *)data;
    if(syscall(197,fd,data)) return -1;
    m->mode=word(b+16);m->links=word(b+20);m->owner=word(b+24);m->group=word(b+28);
    m->size=(unsigned long long)word(b+48)|(unsigned long long)word(b+52)<<32;
#endif
    return 0;
}
static int directory(int fd,unsigned int owner,unsigned int group)
{
    struct captured_stat m;
    if(metadata(fd,&m)||(m.mode&0170000)!=0040000||m.owner!=owner||m.group!=group||(m.mode&0022)) return -1;
#ifndef HEARTH_HOST_LAB
    { unsigned long long data[16];unsigned char *b=(unsigned char *)data;
      /* ARM statfs: type at 0, flags at 44; ST_RDONLY is bit zero. */
      if(syscall(100,fd,data)||word(b)!=0x72b6||!(word(b+44)&1)) return -1;
    }
#endif
    /* Metadata must be observable, including ACLs; no silent attr loss. */
    return flistxattr(fd,0,0)==0 ? 0 : -1;
}
static int regular_entry(int fd,const char *name)
{
#ifdef HEARTH_HOST_LAB
    struct stat s;
    if(fstatat(fd,name,&s,AT_SYMLINK_NOFOLLOW)) return *__errno_location()==2 ? 1 : -1;
    return (s.st_mode&0170000)==0100000 ? 0 : -1;
#else
    unsigned long long data[16];
    if(syscall(327,fd,name,data,256)) return *__errno_location()==2 ? 1 : -1;
    return (word((unsigned char *)data+16)&0170000)==0100000 ? 0 : -1;
#endif
}
int hearth_snapshot_file(const int roots[2],unsigned int owner,unsigned int group,
    unsigned int target,unsigned char *buffer,hearth_file_size capacity,
    struct hearth_snapshot_file *result)
{
    const char *path;char name[96];unsigned int n=0;
    int parent=-1,fd=-1,status=-1;struct captured_stat m,after;
    hearth_file_size at=0;unsigned char check[1024];
    if(result) clear(result,sizeof(*result));
    if(buffer&&capacity<=HEARTH_FILE_BYTES) clear(buffer,capacity);
    if(!roots||!buffer||!result||!capacity||capacity>HEARTH_FILE_BYTES||target>=HEARTH_TARGET_COUNT) return -1;
    if(directory(roots[0],owner,group)||directory(roots[1],owner,group)) goto done;
    parent=openat(roots[target==HEARTH_SETTINGS],".",H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
    if(parent<0) goto done;
    path=hearth_target_paths[target];
    for(;;path++) {
        if(*path=='/'||!*path) {
            int next;
            if(!n) goto done;
            name[n]=0;
            if(!*path) break;
            next=openat(parent,name,H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
            if(close(parent)) { parent=next;goto done; }
            parent=next;n=0;
            if(parent<0||directory(parent,owner,group)) goto done;
        } else { if(n>=sizeof(name)-1) goto done;name[n++]=*path; }
    }
    { int entry=regular_entry(parent,name);
      if(entry==1&&(target==HEARTH_STORAGE_LIBRARY||target==HEARTH_LAUNCHER)) {
          result->target=target;status=0;goto done;
      }
      if(entry) goto done;
    }
    /* Recheck after open; O_NONBLOCK avoids a substituted FIFO blocking. */
    fd=openat(parent,name,2048|H_NOFOLLOW|H_CLOEXEC);
    if(fd<0) goto done;
    if(metadata(fd,&m)||(m.mode&0170000)!=0100000||m.links!=1||m.owner!=owner||m.group!=group||
       (m.mode&07000)||m.size>capacity||flistxattr(fd,0,0)!=0) goto done;
    while(at<(hearth_file_size)m.size) {
        long count=read(fd,buffer+at,(hearth_file_size)m.size-at);
        if(count<0&&*__errno_location()==4) continue;
        if(count<=0||(hearth_file_size)count>(hearth_file_size)m.size-at) goto done;
        at+=(hearth_file_size)count;
    }
    if(read(fd,check,1)!=0||lseek(fd,0,0)!=0) goto done;
    at=0;
    while(at<(hearth_file_size)m.size) {
        hearth_file_size amount=(hearth_file_size)m.size-at,i;long count;
        if(amount>sizeof(check)) amount=sizeof(check);
        count=read(fd,check,amount);
        if(count<0&&*__errno_location()==4) continue;
        if(count<=0||(hearth_file_size)count>amount) goto done;
        for(i=0;i<(hearth_file_size)count;i++) if(check[i]!=buffer[at+i]) goto done;
        at+=(hearth_file_size)count;
    }
    if(read(fd,check,1)!=0||metadata(fd,&after)||m.mode!=after.mode||m.links!=after.links||
       m.owner!=after.owner||m.group!=after.group||m.size!=after.size||flistxattr(fd,0,0)!=0) goto done;
    result->target=target;result->existed=1;result->mode=m.mode&0777;
    result->owner=m.owner;result->group=m.group;result->size=(hearth_file_size)m.size;status=0;
done:
    if(fd>=0&&close(fd)) status=-1;
    if(parent>=0&&close(parent)) status=-1;
    clear(check,sizeof(check));
    if(status) { clear(buffer,capacity);clear(result,sizeof(*result)); }
    return status;
}
