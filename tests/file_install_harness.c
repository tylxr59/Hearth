/* Original real-filesystem host lab. Only caller-created temporary trees. */
#ifdef HEARTH_RAM_LAB
#include "../firmware/file_install_probe/lab_abi.h"
#else
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <unistd.h>
#endif
#include "../firmware/file_install/posix.h"
static const char *const paths[] = {
    "nestlabs/lib/libnlwebservice.so","etc/ssl/certs/ca-bundle.pem",
    "etc/ssl/certs/nest-crl-bundle.pem","etc/ntp.conf",
    "nestlabs/lib/libhearth-settings-compat.so","nestlabs/sbin/hearth-nlclient",
    "etc/init.d/nestlabs","settings.config","etc/nestlabs/client.config"
};
static const unsigned char old[]="preserved original contents\n", replacement[]="checked replacement contents\n";
static const unsigned int modes[]={0644,0644,0644,0644,0,0,0750,0644,0644};
static const unsigned int new_modes[]={0644,0644,0644,0644,0444,0750,0750,0600,0600};
static struct hearth_file_change changes[HEARTH_TARGET_COUNT];
static int scenario,inject,write_started,activation;
static int suffix(const char *s,const char *tail)
{ size_t a=strlen(s),b=strlen(tail);return a>=b&&!strcmp(s+a-b,tail); }
static int fd_path(int fd,char *path)
{
    char name[64];ssize_t n;snprintf(name,sizeof(name),"/proc/self/fd/%d",fd);
    n=readlink(name,path,511);if(n<0) return 0;path[n]=0;return 1;
}
extern ssize_t __real_write(int,const void *,size_t);
ssize_t __wrap_write(int fd,const void *data,size_t size)
{
    char path[512];
    if(inject&&fd_path(fd,path)&&suffix(path,".hearth-new")) {
        if(scenario==10) return __real_write(fd,data,size>3?3:size);
        if(scenario==11) {
            if(!write_started++) return __real_write(fd,data,size>3?3:size);
            errno=EIO;return -1;
        }
    }
    return __real_write(fd,data,size);
}
extern int __real_fchmod(int,mode_t);
int __wrap_fchmod(int fd,mode_t mode)
{
    char path[512];
    if(inject&&scenario==26&&fd_path(fd,path)&&suffix(path,".hearth-new")) { inject=0;errno=EPERM;return -1; }
    return __real_fchmod(fd,mode);
}
extern int __real_fchown(int,uid_t,gid_t);
int __wrap_fchown(int fd,uid_t owner,gid_t group)
{
    char path[512];
    if(inject&&scenario==27&&fd_path(fd,path)&&suffix(path,".hearth-new")) { inject=0;errno=EPERM;return -1; }
    return __real_fchown(fd,owner,group);
}
extern int __real_fsync(int);
int __wrap_fsync(int fd)
{
    char path[512];struct stat s;
    if(inject&&scenario==28&&fd_path(fd,path)&&suffix(path,".original")) { inject=0;errno=EIO;return -1; }
    if(inject&&scenario==12&&fd_path(fd,path)&&suffix(path,".hearth-new")) {
        inject=0;errno=EIO;return -1;
    }
    if(inject&&scenario==13&&activation&&fstat(fd,&s)==0&&S_ISDIR(s.st_mode)) {
        inject=0;errno=EIO;return -1;
    }
    return __real_fsync(fd);
}
extern int __real_renameat(int,const char *,int,const char *);
int __wrap_renameat(int a,const char *b,int c,const char *d)
{
    if(inject&&scenario==14&&activation&&suffix(b,".hearth-new")) {
        inject=0;errno=EIO;return -1;
    }
    return __real_renameat(a,b,c,d);
}
static int preflight(void *c,unsigned int i)
{ return hearth_posix_file_ops.preflight(c,i); }
static int journal(void *c,enum hearth_install_phase phase,unsigned int mask)
{
    int result=hearth_posix_file_ops.journal(c,phase,mask);
    if(inject&&scenario==25&&phase==HEARTH_PREPARING) { inject=0;return -1; }
    if(inject&&scenario==15&&phase==HEARTH_COMMITTED) { inject=0;return -1; }
    if(inject&&scenario==16&&((phase==HEARTH_COMMITTING&&mask==15)||phase==HEARTH_RESTORING)) {
        /* Fail a journal update, then another during rollback: target restoration
         * must still proceed when its journal cannot be synced. */
        return -1;
    }
    return result;
}
static int stage(void *c,unsigned int i)
{
    if(scenario==17&&i==1) return -1;
    return hearth_posix_file_ops.stage(c,i);
}
static void write_file(int root,const char *name,const unsigned char *data,size_t size,unsigned int mode)
{
    int fd=openat(root,name,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);
    assert(fd>=0);assert(write(fd,data,size)==(ssize_t)size);assert(fchmod(fd,mode)==0);assert(close(fd)==0);
}
static int activate(void *opaque,unsigned int i)
{
    struct hearth_posix_context *c=opaque;int result;
    if(scenario==18&&i==2) {
        static const unsigned char other[]="unrelated concurrent change\n";
        write_file(c->roots[0],paths[i],other,sizeof(other)-1,new_modes[i]);
    }
    activation=1;result=hearth_posix_file_ops.activate(c,i);activation=0;
    if((scenario==19||scenario==21)&&i==5&&!result) return -1; /* uncertain result after a real rename */
    return result;
}
static int verify(void *c,unsigned int i)
{
    if(scenario==20&&i==8) return -1;
    return hearth_posix_file_ops.verify(c,i);
}
static int restore(void *c,unsigned int i)
{
    if(scenario==21&&i==3) return -1;
    return hearth_posix_file_ops.restore(c,i);
}
static int discard(void *c,unsigned int i)
{ return hearth_posix_file_ops.discard(c,i); }
static void mkdir_checked(int fd,const char *path)
{ assert(mkdirat(fd,path,0755)==0); }
static void check_file(int root,const char *path,const unsigned char *data,size_t size,unsigned int mode)
{
    unsigned char buffer[128];struct stat s;int fd=openat(root,path,O_RDONLY|O_NOFOLLOW);
    assert(fd>=0&&fstat(fd,&s)==0&&S_ISREG(s.st_mode));assert((s.st_mode&07777)==mode);
    assert(s.st_size==(off_t)size);assert(read(fd,buffer,sizeof(buffer))==(ssize_t)size);
    assert(!memcmp(buffer,data,size));assert(close(fd)==0);
}
static int scenario_main(int argc,char **argv)
{
    struct hearth_posix_context context;
    const struct hearth_file_ops ops={preflight,journal,stage,activate,verify,restore,discard};
    struct hearth_install_result result;
    int base,i,receipt=1;struct stat s;char journal_path[64];unsigned char record[48];
    inject=write_started=activation=0;
    assert(argc==3);scenario=atoi(argv[1]);base=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(base>=0);
    mkdir_checked(base,"root");mkdir_checked(base,"user");
    memset(&context,0,sizeof(context));context.roots[0]=openat(base,"root",O_RDONLY|O_DIRECTORY);
    context.roots[1]=openat(base,"user",O_RDONLY|O_DIRECTORY);context.recovery=-1;
    context.owner=getuid();context.group=getgid();context.count=HEARTH_TARGET_COUNT;context.changes=changes;
    { const char *dirs[]={"etc","etc/ssl","etc/ssl/certs","etc/nestlabs","etc/init.d","nestlabs","nestlabs/lib","nestlabs/sbin"};
      for(i=0;i<8;i++) mkdir_checked(context.roots[0],dirs[i]); }
    for(i=0;i<HEARTH_TARGET_COUNT;i++) {
        changes[i]=(struct hearth_file_change){(unsigned int)i,modes[i]!=0,
            {modes[i]?old:NULL,modes[i]?sizeof(old)-1:0},
            {replacement,sizeof(replacement)-1},modes[i],new_modes[i]};
        if(modes[i]) write_file(context.roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
        context.plan_id[i]=(unsigned char)(i+1);
    }
    switch(scenario) {
    case 1:receipt=0;break;
    case 2:changes[8].original.data=replacement;changes[8].original.size=sizeof(replacement)-1;break;
    case 3:
        assert(renameat(context.roots[0],"etc/ssl/certs",context.roots[0],"etc/ssl/real-certs")==0);
        assert(symlinkat("real-certs",context.roots[0],"etc/ssl/certs")==0);break;
    case 4:
        assert(linkat(context.roots[0],paths[1],context.roots[0],"hardlink",0)==0);break;
    case 5:
        assert(unlinkat(context.roots[0],paths[3],0)==0);
        write_file(base,"outside",old,sizeof(old)-1,0644);
        assert(symlinkat("../../outside",context.roots[0],paths[3])==0);break;
    case 6:
        assert(symlinkat("/dev/null",context.roots[0],"etc/ntp.conf.hearth-new")==0);break;
    case 7:
        write_file(context.roots[0],"etc/ntp.conf.hearth-restore",old,sizeof(old)-1,0600);break;
    case 8:changes[7].replacement_mode=0666;break;
    case 9:assert(mkdirat(context.roots[1],".hearth-rollback",0700)==0);break;
    case 22:
        assert(unlinkat(context.roots[0],paths[3],0)==0);
        assert(mkfifoat(context.roots[0],paths[3],0600)==0);break;
    case 23:changes[8].target=HEARTH_SETTINGS;break;
    case 24:changes[7].replacement.size=HEARTH_FILE_BYTES+1;break;
    case 29:changes[7].original_mode=0600;break;
    case 30:write_file(context.roots[0],"etc/ntp.conf.hearth-new",old,sizeof(old)-1,0600);break;
    case 31:context.owner++;break;
#ifndef HEARTH_RAM_LAB
    case 32:
        { int fd=openat(context.roots[0],paths[1],O_RDONLY|O_NOFOLLOW);int status;
          assert(fd>=0);status=fsetxattr(fd,"user.hearth_fixture","present",7,0);close(fd);
          if(status&&errno==EOPNOTSUPP) return 77;
          assert(status==0); }
        break;
#endif
    default:break;
    }
    inject=1;
    result=hearth_install_files(&ops,&context,context.count,receipt);
    inject=0;
    if(scenario==0||scenario==10) {
        assert(result.error==0&&result.committed&&!result.rollback_error&&!result.cleanup_error);
        for(i=0;i<HEARTH_TARGET_COUNT;i++) check_file(context.roots[i==HEARTH_SETTINGS],paths[i],replacement,sizeof(replacement)-1,new_modes[i]);
        for(i=0;i<HEARTH_TARGET_COUNT;i++) if(modes[i]) {
            snprintf(journal_path,sizeof(journal_path),"%d.original",i);
            check_file(context.recovery,journal_path,old,sizeof(old)-1,0600);
        }
    } else if(scenario<=9||(scenario>=22&&scenario<=24)||scenario>=29) {
        assert(result.error==(scenario==1?HEARTH_BACKUP_REQUIRED:HEARTH_PREFLIGHT_FAILED));
        assert(!result.committed&&!result.attempted&&context.recovery==-1);
        if(scenario!=9) assert(fstatat(context.roots[1],".hearth-rollback",&s,AT_SYMLINK_NOFOLLOW)<0&&errno==ENOENT);
    } else {
        assert(result.error!=0&&!result.committed);
        if(scenario==18||scenario==21) assert(result.rollback_error);
        else assert(!result.rollback_error&&result.attempted==result.restored);
        for(i=0;i<HEARTH_TARGET_COUNT;i++) {
            if((scenario==18&&i==2)||(scenario==21&&i==3)) continue;
            if(modes[i]) check_file(context.roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
            else assert(fstatat(context.roots[0],paths[i],&s,AT_SYMLINK_NOFOLLOW)<0&&errno==ENOENT);
        }
        if(scenario==18) {
            static const unsigned char other[]="unrelated concurrent change\n";
            check_file(context.roots[0],paths[2],other,sizeof(other)-1,new_modes[2]);
        }
        if(scenario==16) assert(result.journal_error&&result.attempted==7&&result.restored==7);
    }
    if(context.recovery>=0) {
        int fd=openat(context.recovery,"journal",O_RDONLY|O_NOFOLLOW);assert(fd>=0);
        assert(read(fd,record,sizeof(record))==sizeof(record));assert(close(fd)==0);
        assert(record[4]==(scenario==25?HEARTH_PREPARING:result.committed?HEARTH_COMMITTED:result.rollback_error?HEARTH_RESTORE_FAILED:HEARTH_RESTORED));
        if(result.rollback_error) check_file(context.roots[0],"etc/nestlabs/client.config.hearth-new",replacement,sizeof(replacement)-1,0600);
        assert(!memcmp(record,"HFI1",4));assert(record[12]==HEARTH_TARGET_COUNT);
        assert(!memcmp(record+16,context.plan_id,32));assert(close(context.recovery)==0);
    }
    assert(close(context.roots[0])==0&&close(context.roots[1])==0&&close(base)==0);
    return 0;
}

#ifndef HEARTH_RAM_LAB
int main(int argc,char **argv) { return scenario_main(argc,argv); }
#else
int main(int argc,char **argv)
{
    int i,n;char directory[96],number[16],line[128];char *args[4];
    assert(argc==2&&!strcmp(argv[1],"files"));
    for(i=0;i<32;i++) {
        snprintf(directory,sizeof(directory),"/state/file-case-%d",i);
        snprintf(number,sizeof(number),"%d",i);
        assert(mkdir(directory,0700)==0);
        args[0]="/file-test";args[1]=number;args[2]=directory;args[3]=0;
        assert(scenario_main(3,args)==0);
        n=snprintf(line,sizeof(line),"{\"type\":\"file_case\",\"case\":%d,\"passed\":true}\n",i);
        assert(n>0&&n<(int)sizeof(line)&&__real_write(1,line,n)==n);
    }
    return 0;
}
#endif
