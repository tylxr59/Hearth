/* Original Linux adapter; used only after separate mount/backup authorization.
 * No command-line entry point. Host tests use caller-created temporary roots.
 * ARM syscall constants/layout below are checked against the pinned kernel.
 */
#ifdef HEARTH_NETWORK_ADAPTER
#include "../network_update/posix.h"
#else
#include "posix.h"
#endif
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
#ifndef HEARTH_NETWORK_ADAPTER
#include "targets.h"
#endif
static const char suffix[] = ".hearth-new";
static const char restore_suffix[] = ".hearth-restore";
static const char *recovery_name(struct hearth_posix_context *c,char name[96])
{
    static const char hex[]="0123456789abcdef",prefix[]=".hearth-rollback-";
    unsigned int i,n=0,present=0;
    if(!c->archive_layout) return ".hearth-rollback";
    if(c->archive_layout!=1) return 0;
    for(i=0;prefix[i];i++) name[n++]=prefix[i];
    for(i=0;i<32;i++) { present|=c->plan_id[i];name[n++]=hex[c->plan_id[i]>>4];name[n++]=hex[c->plan_id[i]&15]; }
    name[n]=0;return present?name:0;
}
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
    const char *path=hearth_target_paths[target];
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
static int no_attributes(int fd)
{
    long count=flistxattr(fd,0,0);
#ifdef HEARTH_RAM_LAB
    return count==0||(count<0&&*__errno_location()==95) ? 0 : -1;
#else
    return count==0 ? 0 : -1;
#endif
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
    /* Production requires observable attributes; only the explicit synthetic
     * RAM build accepts EOPNOTSUPP from a RAM filesystem. */
    if(no_attributes(fd)) goto done;
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
static int valid_change(struct hearth_posix_context *c,unsigned int index)
{
    const struct hearth_file_change *f;unsigned int n;
    if(!c||!c->changes||!c->count||c->count>HEARTH_FILE_LIMIT||index>=c->count||c->archive_layout>1) return -1;
    f=&c->changes[index];
    if(f->target>=HEARTH_TARGET_COUNT||f->replacement.size>HEARTH_FILE_BYTES||!f->replacement.size||
       !f->replacement.data||f->original.size>HEARTH_FILE_BYTES||
       (f->original.size&&!f->original.data)||f->original_mode&~0777U||f->replacement_mode&~0777U||
       (f->existed!=0&&f->existed!=1)) return -1;
    for(n=0;n<index;n++) if(c->changes[n].target>=f->target) return -1;
#ifdef HEARTH_NETWORK_ADAPTER
    {
        static const unsigned int limits[4]={6U*1048576U,1048576U,65536U,65536U};
        if(c->count!=4||c->archive_layout!=1||!f->existed||!f->original.size||
           f->original.size!=f->replacement.size||f->original.size>limits[f->target]||
           f->original_mode!=f->replacement_mode||(f->original_mode&0022U)) return -1;
    }
#else
    if(!f->existed&&(f->target!=HEARTH_STORAGE_LIBRARY&&f->target!=HEARTH_LAUNCHER)) return -1;
    if(!f->existed&&(f->original.size||f->original_mode)) return -1;
    if((f->target==HEARTH_SETTINGS||f->target==HEARTH_CLIENT_CONFIG)&&f->replacement_mode!=0600) return -1;
    if(f->target==HEARTH_LAUNCHER&&f->replacement_mode!=0750) return -1;
    if(f->target==HEARTH_STARTUP&&f->replacement_mode!=f->original_mode) return -1;
    if(f->target==HEARTH_STORAGE_LIBRARY&&f->replacement_mode!=0444) return -1;
    if((f->target==HEARTH_CA||f->target==HEARTH_CRL)&&f->replacement_mode!=0644) return -1;
    if((f->target==HEARTH_WEB_LIBRARY||f->target==HEARTH_NTP)&&f->replacement_mode!=f->original_mode) return -1;
#endif
    return 0;
}
static int preflight(void *opaque,unsigned int index)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f;
    char name[128],archive[96];const char *saved;int directory,result=-1;
    if(valid_change(c,index)||c->recovery!=-1) return -1;
    f=&c->changes[index];
    saved=recovery_name(c,archive);
    if(!saved||local_root(c,c->roots[0])||local_root(c,c->roots[1])||absent(c->roots[1],saved)!=1) return -1;
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
    char archive[96];const char *saved=recovery_name(c,archive);
    if(!saved) return -1;
    if(c->recovery<0) {
        if(phase!=HEARTH_PREPARING||mkdirat(c->roots[1],saved,0700)) return -1;
        c->recovery=openat(c->roots[1],saved,H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
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
static int restore_checked(void *opaque,unsigned int index,int allow_missing)
{
    struct hearth_posix_context *c=opaque;const struct hearth_file_change *f=&c->changes[index];
    char name[128],temporary[128],backup[16];unsigned int i;int directory=parent(c,f->target,name),result=-1;
    if(directory<0) return -1;
    if(!check_original(c,index,directory,name)) { result=0;goto done; }
    if(!(allow_missing&&f->existed&&absent(directory,name)==1)&&
       contents(directory,name,f->replacement,f->replacement_mode,c)) goto done;
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
static int restore(void *opaque,unsigned int index)
{ return restore_checked(opaque,index,0); }
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

/* A post-crash process never inherits created[] provenance. Reconstruct only
 * exact known bytes or a bounded prefix with the expected metadata. Everything
 * else remains untouched for private/manual inspection. */
static int recover_temporary(struct hearth_posix_context *c,unsigned int index,
    int directory,const char *name,struct hearth_file_bytes expected,
    unsigned int mode,unsigned int flag)
{
    struct metadata m;int status=entry(directory,name,&m);
    if(status==1) return 0;
    if(status||m.size>expected.size||(m.mode&0170000)!=0100000||
       m.links!=1||m.owner!=c->owner||m.group!=c->group||
       ((m.mode&07777)!=mode&&(m.mode&07777)!=0600)) return -1;
    expected.size=(hearth_file_size)m.size;
    if(contents(directory,name,expected,m.mode&07777,c)) return -1;
    c->created[index]|=flag;
    return 0;
}
static int recovery_journal(struct hearth_posix_context *c,unsigned int *saved_phase,unsigned int *saved_mask)
{
    unsigned char record[48];hearth_file_size at=0;int fd,result=-1;
    struct metadata m;unsigned int phase,mask,count,i;
    if(entry(c->recovery,"journal",&m)||(m.mode&0170000)!=0100000||m.size!=sizeof(record)) return -1;
    fd=openat(c->recovery,"journal",H_RDONLY|H_NONBLOCK|H_NOFOLLOW|H_CLOEXEC);
    if(fd<0) return -1;
    while(at<sizeof(record)) {
        long n=read(fd,record+at,sizeof(record)-at);
        if(n<0&&*__errno_location()==4) continue;
        if(n<=0||(hearth_file_size)n>sizeof(record)-at) goto done;
        at+=(hearth_file_size)n;
    }
    if(contents(c->recovery,"journal",(struct hearth_file_bytes){record,sizeof(record)},0600,c)) goto done;
    if(record[0]!='H'||record[1]!='F'||record[2]!='I'||record[3]!='1') goto done;
    phase=(unsigned int)record[4]|(unsigned int)record[5]<<8|
        (unsigned int)record[6]<<16|(unsigned int)record[7]<<24;
    mask=(unsigned int)record[8]|(unsigned int)record[9]<<8|
        (unsigned int)record[10]<<16|(unsigned int)record[11]<<24;
    count=(unsigned int)record[12]|(unsigned int)record[13]<<8|
        (unsigned int)record[14]<<16|(unsigned int)record[15]<<24;
    if(count!=c->count||phase<HEARTH_PREPARING||phase>HEARTH_RESTORE_FAILED||mask&~((1U<<count)-1)) goto done;
    if((phase==HEARTH_PREPARING||phase==HEARTH_STAGED)&&mask) goto done;
    if(phase==HEARTH_COMMITTED&&mask!=((1U<<count)-1)) goto done;
    if(phase==HEARTH_COMMITTING&&(!mask||(mask&(mask+1)))) goto done;
    for(i=0;i<32;i++) if(record[16+i]!=c->plan_id[i]) goto done;
    *saved_phase=phase;*saved_mask=mask;result=0;
done:
    if(close(fd)) result=-1;
    return result;
}
static int restore_preflight(struct hearth_posix_context *c,unsigned int missing_restored)
{
    struct metadata m;unsigned int i,phase=0,mask=0;char name[128],temporary[128],backup[16];
    char archive[96];const char *saved;
    if(!c||c->recovery!=-1||!c->count||c->count>HEARTH_FILE_LIMIT||
       (missing_restored&~(1U<<HEARTH_SETTINGS))) return HEARTH_INVALID_PLAN;
    for(i=0;i<c->count;i++) if(valid_change(c,i)) return HEARTH_INVALID_PLAN;
    saved=recovery_name(c,archive);if(!saved) return HEARTH_INVALID_PLAN;
    if(local_root(c,c->roots[0])||local_root(c,c->roots[1])) goto invalid;
    c->recovery=openat(c->roots[1],saved,H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
    if(c->recovery<0||local_root(c,c->recovery)||metadata(c->recovery,&m)||
       (m.mode&07777)!=0700||m.group!=c->group||no_attributes(c->recovery)||recovery_journal(c,&phase,&mask)) goto invalid;
    /* Ignore old in-memory flags; recovery accepts only reconstructed evidence. */
    for(i=0;i<HEARTH_FILE_LIMIT;i++) c->created[i]=0;
    c->journal_temporary=0;
    for(i=0;i<c->count;i++) {
        const struct hearth_file_change *f=&c->changes[i];unsigned int j;
        int directory=parent(c,f->target,name),status=-1;
        if(directory<0) goto invalid;
        if(check_original(c,i,directory,name)) {
            if(f->existed&&absent(directory,name)==1&&
               ((phase==HEARTH_COMMITTING||phase==HEARTH_RESTORING)||
                (phase==HEARTH_RESTORED&&(missing_restored&(1U<<i))&&mask==((1U<<c->count)-1)))&&
               (mask&(1U<<i))) {
                /* An interrupted filesystem rename may leave the old name
                 * absent. Only durable intent plus an exact backup permits
                 * reconstructing that specific existing target. */
                c->created[i]|=8U;
            } else if(contents(directory,name,f->replacement,f->replacement_mode,c)) goto checked;
            if(f->existed) {
                backup_name(i,backup);
                if(contents(c->recovery,backup,f->original,0600,c)) goto checked;
            }
        }
        for(j=0;(temporary[j]=name[j]);j++) {}
        if(append(temporary,suffix)||recover_temporary(c,i,directory,temporary,
            f->replacement,f->replacement_mode,2)) goto checked;
        for(j=0;(temporary[j]=name[j]);j++) {}
        if(append(temporary,restore_suffix)) goto checked;
        if(f->existed) {
            if(recover_temporary(c,i,directory,temporary,f->original,f->original_mode,4)) goto checked;
        } else if(absent(directory,temporary)!=1) goto checked;
        status=0;
checked:
        if(close(directory)) status=-1;
        if(status) goto invalid;
    }
    return 0;
invalid:
    return HEARTH_PREFLIGHT_FAILED;
}
int hearth_posix_restore_preflight(struct hearth_posix_context *c)
{ return restore_preflight(c,0); }
struct hearth_install_result hearth_posix_restore_files(struct hearth_posix_context *c)
{
    struct hearth_install_result r={0,0,0,0,0,0,0};unsigned int i;
    r.error=hearth_posix_restore_preflight(c);
    if(r.error) return r;
    /* Conservatively cover every target: a durable journal may precede an
     * interrupted update of journal.new. Exact current bytes, not old masks,
     * decide whether each original already exists or needs restoration. */
    r.attempted=(1U<<c->count)-1;
    if(journal(c,HEARTH_RESTORING,r.attempted)) r.journal_error=1;
    for(i=c->count;i;i--) {
        unsigned int index=i-1,staged=c->created[index]&2U;
        /* Only clear a verified interrupted restore temporary before retry.
         * Retain replacement staging until all originals are restored. */
        c->created[index]&=~2U;
        if(discard(c,index)) r.cleanup_error=1;
        c->created[index]|=staged;
        if(restore_checked(c,index,(c->created[index]&8U)!=0)) r.rollback_error=1;
        else r.restored|=1U<<index;
    }
    if(journal(c,r.rollback_error?HEARTH_RESTORE_FAILED:HEARTH_RESTORED,r.restored)) r.journal_error=1;
    if(!r.rollback_error) for(i=c->count;i;i--) if(discard(c,i-1)) r.cleanup_error=1;
    if(r.rollback_error) r.error=HEARTH_ROLLBACK_FAILED;
    return r;
}
