/* Original synthetic process-interruption recovery lab. No device access. */
#ifndef HEARTH_RAM_LAB
#include <sys/wait.h>
#else
typedef int pid_t;
#define WIFEXITED(status) (((status)&0x7f)==0)
#define WEXITSTATUS(status) (((status)>>8)&255)
#endif
#define main original_file_lab_main
#define __wrap_write original_write_wrapper
#include "file_install_harness.c"
#undef main
#undef __wrap_write
static int recovery_case;
static int recovery_write_fault;
ssize_t __wrap_write(int fd,const void *data,size_t size)
{
    char path[512];
    if(recovery_write_fault&&fd_path(fd,path)&&suffix(path,"etc/ntp.conf.hearth-restore")) {
        if(recovery_write_fault--==2) return __real_write(fd,data,size>3?3:size);
        errno=EIO;return -1;
    }
    return original_write_wrapper(fd,data,size);
}
static int crash_journal(void *opaque,enum hearth_install_phase phase,unsigned int mask)
{
    int status=hearth_posix_file_ops.journal(opaque,phase,mask);
    assert(status==0);
    if((recovery_case==1&&phase==HEARTH_PREPARING)||
       (recovery_case==2&&phase==HEARTH_STAGED)||
       (recovery_case==3&&phase==HEARTH_COMMITTING&&mask==1)||
       (recovery_case==4&&phase==HEARTH_COMMITTING&&mask==3)||
       (recovery_case==5&&phase==HEARTH_COMMITTING&&mask==511)||
       (recovery_case==6&&phase==HEARTH_COMMITTED)||
       ((recovery_case==17||recovery_case==19)&&phase==HEARTH_COMMITTING&&mask==3)) _exit(99);
    return status;
}
static void setup(int base,struct hearth_posix_context *c)
{
    const char *dirs[]={"etc","etc/ssl","etc/ssl/certs","etc/nestlabs","etc/init.d",
        "nestlabs","nestlabs/lib","nestlabs/sbin"};unsigned int i;
    assert(mkdirat(base,"root",0755)==0);assert(mkdirat(base,"user",0755)==0);
    memset(c,0,sizeof(*c));c->roots[0]=openat(base,"root",O_RDONLY|O_DIRECTORY);
    c->roots[1]=openat(base,"user",O_RDONLY|O_DIRECTORY);c->recovery=-1;
    c->owner=getuid();c->group=getgid();c->count=9;c->changes=changes;
    assert(c->roots[0]>=0&&c->roots[1]>=0);
    for(i=0;i<8;i++) assert(mkdirat(c->roots[0],dirs[i],0755)==0);
    for(i=0;i<9;i++) {
        changes[i]=(struct hearth_file_change){i,modes[i]!=0,
            {modes[i]?old:NULL,modes[i]?sizeof(old)-1:0},
            {replacement,sizeof(replacement)-1},modes[i],new_modes[i]};
        if(modes[i]) write_file(c->roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
        c->plan_id[i]=(unsigned char)(i+1);
    }
}
static int recovery_scenario_main(int argc,char **argv)
{
    int base,status,fd;unsigned int i;pid_t child;
    struct hearth_posix_context c;struct hearth_install_result r;
    struct hearth_file_ops operations=hearth_posix_file_ops;
    assert(argc==3);recovery_case=atoi(argv[1]);scenario=0;inject=0;
    base=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(base>=0);setup(base,&c);
    operations.journal=crash_journal;
    child=fork();assert(child>=0);
    if(child==0) {
        r=hearth_install_files(&operations,&c,9,1);
        assert(r.error==0&&r.committed&&!r.cleanup_error&&!r.journal_error);
        _exit(0);
    }
    assert(waitpid(child,&status,0)==child&&WIFEXITED(status));
    assert(WEXITSTATUS(status)==((recovery_case>=1&&recovery_case<=6)||recovery_case==17||recovery_case==19?99:0));
    /* The parent has no child-created fd/flags. Reopen the tree and use only
     * the exact plan and persisted evidence, like a later recovery process. */
    close(c.roots[0]);close(c.roots[1]);
    c.roots[0]=openat(base,"root",O_RDONLY|O_DIRECTORY);c.roots[1]=openat(base,"user",O_RDONLY|O_DIRECTORY);
    assert(c.recovery==-1);
    if(recovery_case==7) c.plan_id[0]^=1;
    if(recovery_case==8) write_file(c.roots[0],paths[8],(const unsigned char *)"unexpected",10,0600);
    if(recovery_case==9) write_file(c.roots[1],".hearth-rollback/journal",(const unsigned char *)"bad",3,0600);
    if(recovery_case==10) {
        assert(unlinkat(c.roots[1],".hearth-rollback/0.original",0)==0);
        assert(symlinkat("/dev/null",c.roots[1],".hearth-rollback/0.original")==0);
    }
    if(recovery_case==11) write_file(c.roots[0],"etc/ntp.conf.hearth-restore",old,3,0600);
    if(recovery_case==12) write_file(c.roots[0],"etc/ntp.conf.hearth-restore",(const unsigned char *)"bad",3,0600);
    if(recovery_case==13) write_file(c.roots[1],".hearth-rollback/journal.new",(const unsigned char *)"partial",7,0600);
#ifndef HEARTH_RAM_LAB
    if(recovery_case==14) {
        fd=openat(c.roots[1],".hearth-rollback/journal",O_RDONLY);assert(fd>=0);
        status=fsetxattr(fd,"user.hearth_fixture","present",7,0);close(fd);
        if(status&&errno==EOPNOTSUPP) return 77;
        assert(status==0);
    }
#endif
    if(recovery_case==15) assert(fchmodat(c.roots[1],".hearth-rollback",0755,0)==0);
    if(recovery_case==16) write_file(c.roots[0],"etc/ntp.conf.hearth-new",replacement,5,0600);
    if(recovery_case==17||recovery_case==18) assert(unlinkat(c.roots[0],paths[0],0)==0);
    if(recovery_case==19) assert(unlinkat(c.roots[0],paths[8],0)==0);
    if(recovery_case>=20&&recovery_case<=22) {
        unsigned char record[48];
        fd=openat(c.roots[1],".hearth-rollback/journal",O_RDONLY);assert(fd>=0);
        assert(read(fd,record,sizeof(record))==(ssize_t)sizeof(record));assert(close(fd)==0);
        if(recovery_case==20) { record[4]=HEARTH_COMMITTING;record[8]=2;record[9]=0; }
        if(recovery_case==21) record[12]=10;
        if(recovery_case==22) record[4]=0;
        write_file(c.roots[1],".hearth-rollback/journal",record,sizeof(record),0600);
    }
    if(recovery_case==23) {
        write_file(c.roots[0],"etc/ntp.conf.hearth-new",replacement,5,0600);
        recovery_write_fault=2;
    }
    r=hearth_posix_restore_files(&c);
    if(recovery_case==23) {
        assert(r.error==HEARTH_ROLLBACK_FAILED&&r.rollback_error&&!r.committed&&!r.journal_error);
        check_file(c.roots[0],"etc/ntp.conf.hearth-new",replacement,5,0600);
        check_file(c.roots[0],"etc/ntp.conf.hearth-restore",old,3,modes[3]);
        close(c.recovery);c.recovery=-1;
        r=hearth_posix_restore_files(&c);
    }
    if(recovery_case==7||recovery_case==8||recovery_case==9||recovery_case==10||
       recovery_case==12||recovery_case==14||recovery_case==15||recovery_case==18||
       recovery_case==19||(recovery_case>=20&&recovery_case<=22)) {
        assert(r.error==HEARTH_PREFLIGHT_FAILED&&!r.attempted&&!r.restored);
        /* A bad late target must not trigger earlier restoration. */
        if(recovery_case==18) {
            struct stat s;assert(fstatat(c.roots[0],paths[0],&s,AT_SYMLINK_NOFOLLOW)==-1&&errno==ENOENT);
        } else check_file(c.roots[0],paths[0],replacement,sizeof(replacement)-1,new_modes[0]);
    } else {
        assert(r.error==0&&!r.rollback_error&&!r.cleanup_error&&r.restored==511&&!r.committed);
        assert(r.journal_error==(recovery_case==13));
        for(i=0;i<9;i++) {
            struct stat s;
            if(modes[i]) check_file(c.roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
            else assert(fstatat(c.roots[0],paths[i],&s,AT_SYMLINK_NOFOLLOW)==-1&&errno==ENOENT);
        }
        close(c.recovery);c.recovery=-1;
        r=hearth_posix_restore_files(&c); /* Idempotent after original readback. */
        assert(r.error==0&&!r.rollback_error&&r.restored==511);
    }
    if(c.recovery>=0) assert(close(c.recovery)==0);
    assert(close(c.roots[0])==0&&close(c.roots[1])==0&&close(base)==0);
    return 0;
}
#ifndef HEARTH_RAM_LAB
int main(int argc,char **argv) { return recovery_scenario_main(argc,argv); }
#else
int main(int argc,char **argv)
{
    int i,n;char directory[96],number[16],line[128];char *args[4];
    assert(original_file_lab_main(argc,argv)==0);
    for(i=0;i<24;i++) {
        if(i==14) continue; /* Positive xattr storage requires a host fixture. */
        snprintf(directory,sizeof(directory),"/state/recovery-case-%d",i);
        snprintf(number,sizeof(number),"%d",i);assert(mkdir(directory,0700)==0);
        args[0]="/file-test";args[1]=number;args[2]=directory;args[3]=0;
        assert(recovery_scenario_main(3,args)==0);
        n=snprintf(line,sizeof(line),"{\"type\":\"recovery_case\",\"case\":%d,\"passed\":true}\n",i);
        assert(n>0&&n<(int)sizeof(line)&&__real_write(1,line,n)==n);
    }
    return 0;
}
#endif
