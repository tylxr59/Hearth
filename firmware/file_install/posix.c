/* Original Linux adapter; used only after separate mount/backup authorization.
 * No command-line entry point. Host tests use caller-created temporary roots.
 * ARM syscall constants/layout below are checked against the pinned kernel.
 */
#include "posix.h"
#if defined(HEARTH_HOST_LAB) && defined(HEARTH_RAM_LAB)
#error "Host fixture and ARM RAM-only modes must never be combined"
#endif
#ifdef HEARTH_HOST_LAB
#include <stdio.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <sys/xattr.h>
#include <fcntl.h>
#include <unistd.h>
#else
extern int openat(int,const char *,int,...),close(int),fsync(int);
extern int fchmod(int,unsigned int),fchown(int,unsigned int,unsigned int);
extern int mkdirat(int,const char *,unsigned int);
extern int renameat(int,const char *,int,const char *),unlinkat(int,const char *,int);
extern long read(int,void *,hearth_file_size),write(int,const void *,hearth_file_size);
extern long syscall(long,...);
extern long flistxattr(int,char *,hearth_file_size);
#endif
extern int *__errno_location(void);
#define H_RDONLY 0
#define H_RDWR 2
#define H_CREAT 64
#define H_EXCL 128
#define H_NONBLOCK 2048
#define H_DIRECTORY 16384
#define H_NOFOLLOW 32768
#define H_CLOEXEC 524288
/* O_DIRECTORY/O_NOFOLLOW are architecture dependent (unlike these interfaces).
 * Use host headers for host tests; ARM values are from the pinned ARM fcntl.h. */
#ifdef HEARTH_HOST_LAB
#undef H_DIRECTORY
#undef H_NOFOLLOW
#define H_DIRECTORY O_DIRECTORY
#define H_NOFOLLOW O_NOFOLLOW
#endif
struct metadata { unsigned int mode,links,owner,group; unsigned long long size; };
static const char *const paths[HEARTH_TARGET_COUNT] = {
    "nestlabs/lib/libnlwebservice.so", "etc/ssl/certs/ca-bundle.pem",
    "etc/ssl/certs/nest-crl-bundle.pem", "etc/ntp.conf",
    "nestlabs/lib/libhearth-settings-compat.so", "nestlabs/sbin/hearth-nlclient",
    "etc/init.d/nestlabs", "settings.config", "etc/nestlabs/client.config"
};
static const char suffix[] = ".hearth-new";
static const char restore_suffix[] = ".hearth-restore";
static int equal(const unsigned char *a,const unsigned char *b,hearth_file_size n)
{ hearth_file_size i; for(i=0;i<n;i++) if(a[i]!=b[i]) return 0; return 1; }
#ifndef HEARTH_HOST_LAB
static unsigned int word(const unsigned char *b)
{ return b[0]|(unsigned int)b[1]<<8|(unsigned int)b[2]<<16|(unsigned int)b[3]<<24; }
#endif
static void put(unsigned char *b,unsigned int n)
{ unsigned int i; for(i=0;i<4;i++) b[i]=(unsigned char)(n>>(i*8)); }
static int metadata(int fd,struct metadata *m)
{
#ifdef HEARTH_HOST_LAB
    struct stat s;
    if(fstat(fd,&s)) return -1;
    m->mode=s.st_mode; m->links=s.st_nlink; m->owner=s.st_uid;
    m->group=s.st_gid; m->size=(unsigned long long)s.st_size;
#else
    unsigned long long buffer[16];
    unsigned char *b=(unsigned char *)buffer;
    if(syscall(197,fd,buffer)) return -1; /* ARM fstat64 */
    m->mode=word(b+16);m->links=word(b+20);m->owner=word(b+24);m->group=word(b+28);
    m->size=(unsigned long long)word(b+48)|((unsigned long long)word(b+52)<<32);
#endif
    return 0;
}
static int local_root(struct hearth_posix_context *c,int fd)
{
    struct metadata m;
    if(metadata(fd,&m)||(m.mode&0170000)!=0040000||m.owner!=c->owner||(m.mode&0022)) return -1;
#ifndef HEARTH_HOST_LAB
    { unsigned long long buffer[16];
      if(syscall(100,fd,buffer)) return -1;
#ifdef HEARTH_RAM_LAB
      if(word((unsigned char *)buffer)!=0x858458f6U&&word((unsigned char *)buffer)!=0x01021994U) return -1;
#else
      if(word((unsigned char *)buffer)!=0x72b6) return -1;
#endif
    }
#endif
    return 0;
}
static int parent(struct hearth_posix_context *c,unsigned int target,char *name)
{
    const char *path=paths[target];
    int fd=openat(c->roots[target==HEARTH_SETTINGS],".",H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
    unsigned int n=0;
    if(fd<0) return -1;
    for(;;path++) {
        if(*path=='/'||!*path) {
            int next;
            if(!n) { close(fd); return -1; }
            name[n]=0;
            if(!*path) return fd;
            next=openat(fd,name,H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
            close(fd); fd=next; n=0;
            if(fd<0) return -1;
            if(local_root(c,fd)) { close(fd); return -1; }
        } else {
            if(n>=95) { close(fd); return -1; }
            name[n++]=*path;
        }
    }
}
static int entry(int directory,const char *name,struct metadata *m)
{
#ifdef HEARTH_HOST_LAB
    struct stat s;
    if(fstatat(directory,name,&s,AT_SYMLINK_NOFOLLOW)) return *__errno_location()==2 ? 1 : -1;
    m->mode=s.st_mode;m->links=s.st_nlink;m->owner=s.st_uid;m->group=s.st_gid;
    m->size=(unsigned long long)s.st_size;
#else
    unsigned long long buffer[16];unsigned char *b=(unsigned char *)buffer;
    if(syscall(327,directory,name,buffer,256)) return *__errno_location()==2 ? 1 : -1;
    m->mode=word(b+16);m->links=word(b+20);m->owner=word(b+24);m->group=word(b+28);
    m->size=(unsigned long long)word(b+48)|((unsigned long long)word(b+52)<<32);
#endif
    return 0;
}
static int absent(int directory,const char *name)
{
    struct metadata m;int result=entry(directory,name,&m);
    return result==1 ? 1 : result==0 ? 0 : -1;
}
static int contents(int directory,const char *name,struct hearth_file_bytes bytes,
                    unsigned int mode,struct hearth_posix_context *c)
{
    unsigned char buffer[1024]; hearth_file_size at=0; int result=-1;
    struct metadata m;
    int fd;
    if(entry(directory,name,&m)||(m.mode&0170000)!=0100000) return -1;
    fd=openat(directory,name,H_RDONLY|H_NONBLOCK|H_NOFOLLOW|H_CLOEXEC);
    if(fd<0) return -1;
    if(metadata(fd,&m)||(m.mode&0170000)!=0100000||m.links!=1||m.owner!=c->owner||
       m.group!=c->group||(m.mode&07777)!=mode||m.size!=bytes.size) goto done;
    { long attributes=flistxattr(fd,0,0);
#ifdef HEARTH_RAM_LAB
      if(attributes>0||(attributes<0&&*__errno_location()!=95)) goto done;
#else
      /* A writer must be able to observe attributes, not silently hide them
       * behind a kernel/filesystem lacking xattr support. */
      if(attributes!=0) goto done;
#endif
    }
    while(at<bytes.size) {
        hearth_file_size amount=bytes.size-at; long n;
        if(amount>sizeof(buffer)) amount=sizeof(buffer);
        n=read(fd,buffer,amount);
        if(n<0&&*__errno_location()==4) continue;
        if(n<=0||(hearth_file_size)n>amount||!equal(buffer,bytes.data+at,(hearth_file_size)n)) goto done;
        at+=(hearth_file_size)n;
    }
    { long n=read(fd,buffer,1); if(n) goto done; }
    result=0;
done:
    if(close(fd)) result=-1;
    return result;
}
static int append(char *name,const char *tail)
{
    unsigned int i=0,j=0;
    while(name[i]&&i<95) i++;
    while(tail[j]&&i<127) name[i++]=tail[j++];
    name[i]=0; return tail[j] ? -1 : 0;
}
static void backup_name(unsigned int index,char *name)
{
    unsigned int i; const char *tail=".original";
    name[0]='0'+index;
    for(i=0;tail[i];i++) name[i+1]=tail[i];
    name[i+1]=0;
}
static int create_file(struct hearth_posix_context *c,int parent_fd,const char *name,
                       struct hearth_file_bytes bytes,unsigned int mode,
                       unsigned int *created,unsigned int flag)
{
    int result=-1,fd=openat(parent_fd,name,H_RDWR|H_CREAT|H_EXCL|H_NOFOLLOW|H_CLOEXEC,0600);
    hearth_file_size at=0;
    if(fd<0) return -1;
    *created|=flag;
    if(fchown(fd,c->owner,c->group)||fchmod(fd,mode)) goto done;
    while(at<bytes.size) {
        long n=write(fd,bytes.data+at,bytes.size-at);
        if(n<0&&*__errno_location()==4) continue;
        if(n<=0||(hearth_file_size)n>bytes.size-at) goto done;
        at+=(hearth_file_size)n;
    }
    if(fsync(fd)) goto done;
    result=0;
done:
    if(close(fd)) result=-1;
    if(!result&&(contents(parent_fd,name,bytes,mode,c)||fsync(parent_fd))) result=-1;
    return result;
}
static int check_original(struct hearth_posix_context *c,unsigned int index,int directory,const char *name)
{
    const struct hearth_file_change *f=&c->changes[index];
    if(!f->existed) return absent(directory,name)==1 ? 0 : -1;
    return contents(directory,name,f->original,f->original_mode,c);
}
static int preflight(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque; const struct hearth_file_change *f;
    char name[128];int directory,result=-1;unsigned int n;
    if(!c||!c->changes||!c->count||c->count>HEARTH_FILE_LIMIT||index>=c->count||c->recovery!=-1) return -1;
    f=&c->changes[index];
    if(f->target>=HEARTH_TARGET_COUNT||f->replacement.size>HEARTH_FILE_BYTES||!f->replacement.size||
       !f->replacement.data||f->original.size>HEARTH_FILE_BYTES||
       (f->original.size&&!f->original.data)||f->original_mode&~0777U||f->replacement_mode&~0777U||
       (f->existed!=0&&f->existed!=1)) return -1;
    if(!f->existed&&(f->target!=HEARTH_STORAGE_LIBRARY&&f->target!=HEARTH_LAUNCHER)) return -1;
    if(!f->existed&&(f->original.size||f->original_mode)) return -1;
    for(n=0;n<index;n++) if(c->changes[n].target>=f->target) return -1;
    if((f->target==HEARTH_SETTINGS||f->target==HEARTH_CLIENT_CONFIG)&&f->replacement_mode!=0600) return -1;
    if(f->target==HEARTH_LAUNCHER&&f->replacement_mode!=0750) return -1;
    if(f->target==HEARTH_STARTUP&&f->replacement_mode!=f->original_mode) return -1;
    if(f->target==HEARTH_STORAGE_LIBRARY&&f->replacement_mode!=0444) return -1;
    if((f->target==HEARTH_CA||f->target==HEARTH_CRL)&&f->replacement_mode!=0644) return -1;
    if((f->target==HEARTH_WEB_LIBRARY||f->target==HEARTH_NTP)&&f->replacement_mode!=f->original_mode) return -1;
    if(local_root(c,c->roots[0])||local_root(c,c->roots[1])||absent(c->roots[1],".hearth-rollback")!=1) return -1;
    directory=parent(c,f->target,name);if(directory<0) return -1;
    if(check_original(c,index,directory,name)) goto done;
    if(append(name,suffix)||absent(directory,name)!=1) goto done;
    close(directory);directory=parent(c,f->target,name);if(directory<0) return -1;
    if(append(name,restore_suffix)||absent(directory,name)!=1) goto done;
    result=0;
done:
    close(directory); return result;
}
static int journal(void *opaque,enum hearth_install_phase phase,unsigned int mask)
{
    struct hearth_posix_context *c=opaque; unsigned char record[48];unsigned int flags=0;
    struct hearth_file_bytes bytes={record,sizeof(record)}; unsigned int i;
    if(c->recovery<0) {
        if(phase!=HEARTH_PREPARING||mkdirat(c->roots[1],".hearth-rollback",0700)) return -1;
        c->recovery=openat(c->roots[1],".hearth-rollback",H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
        if(c->recovery<0||fchmod(c->recovery,0700)||local_root(c,c->recovery)||fsync(c->roots[1])) return -1;
    }
    if(c->journal_temporary) {
        if(unlinkat(c->recovery,"journal.new",0)) return -1;
        c->journal_temporary=0;
    }
    for(i=0;i<sizeof(record);i++) record[i]=0;
    record[0]='H';record[1]='F';record[2]='I';record[3]='1';
    put(record+4,(unsigned int)phase);put(record+8,mask);put(record+12,c->count);
    for(i=0;i<32;i++) record[16+i]=c->plan_id[i];
    if(create_file(c,c->recovery,"journal.new",bytes,0600,&flags,1)) {
        c->journal_temporary=(flags&1)!=0;return -1;
    }
    c->journal_temporary=1;
    if(renameat(c->recovery,"journal.new",c->recovery,"journal")) return -1;
    c->journal_temporary=0;
    return fsync(c->recovery);
}
static int stage(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128],backup[16];int result=-1,directory=parent(c,f->target,name);
    if(directory<0||c->recovery<0) { if(directory>=0) close(directory);return -1; }
    if(check_original(c,index,directory,name)) goto done;
    if(f->existed) {
        backup_name(index,backup);
        if(create_file(c,c->recovery,backup,f->original,0600,&c->created[index],1)) goto done;
    }
    if(append(name,suffix)||create_file(c,directory,name,f->replacement,f->replacement_mode,&c->created[index],2)) goto done;
    result=0;
done:
    close(directory);return result;
}
static int verify(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128];int directory=parent(c,f->target,name),result;
    if(directory<0) return -1;
    result=contents(directory,name,f->replacement,f->replacement_mode,c);close(directory);return result;
}
static int activate(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128],temporary[128];unsigned int i;int directory=parent(c,f->target,name),result=-1;
    if(directory<0) return -1;
    for(i=0;(temporary[i]=name[i]);i++) {}
    if(check_original(c,index,directory,name)||append(temporary,suffix)||
       contents(directory,temporary,f->replacement,f->replacement_mode,c)) goto done;
    if(renameat(directory,temporary,directory,name)) goto done;
    c->created[index]&=~2U;
    if(fsync(directory)) goto done;
    result=0;
done:
    close(directory);return result;
}
static int restore(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128],temporary[128],backup[16];unsigned int i;int directory=parent(c,f->target,name),result=-1;
    if(directory<0) return -1;
    if(!check_original(c,index,directory,name)) { result=0;goto done; }
    if(contents(directory,name,f->replacement,f->replacement_mode,c)) goto done;
    if(!f->existed) {
        if(unlinkat(directory,name,0)||fsync(directory)) goto done;
    } else {
        backup_name(index,backup);
        if(contents(c->recovery,backup,f->original,0600,c)) goto done;
        for(i=0;(temporary[i]=name[i]);i++) {}
        if(append(temporary,restore_suffix)||create_file(c,directory,temporary,f->original,f->original_mode,&c->created[index],4)) goto done;
        if(renameat(directory,temporary,directory,name)) goto done;
        c->created[index]&=~4U;
        if(fsync(directory)) goto done;
    }
    if(check_original(c,index,directory,name)) goto done;
    result=0;
done:
    close(directory);return result;
}
static int discard(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128],temporary[128];unsigned int i;int directory,result=0;
    if(!(c->created[index]&6)) return 0;
    directory=parent(c,f->target,name);if(directory<0) return -1;
    for(i=0;(temporary[i]=name[i]);i++) {}
    if(c->created[index]&2) {
        if(append(temporary,suffix)||unlinkat(directory,temporary,0)) result=-1;
        else c->created[index]&=~2U;
    }
    for(i=0;(temporary[i]=name[i]);i++) {}
    if(c->created[index]&4) {
        if(append(temporary,restore_suffix)||unlinkat(directory,temporary,0)) result=-1;
        else c->created[index]&=~4U;
    }
    if(fsync(directory)) result=-1;
    close(directory);return result;
}
const struct hearth_file_ops hearth_posix_file_ops={preflight,journal,stage,activate,verify,restore,discard};
