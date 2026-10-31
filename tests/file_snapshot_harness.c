/* Original trusted-host capture tests. Never opens a device mount. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <unistd.h>
#include "../firmware/file_install/snapshot.h"
#include "../firmware/file_install/targets.h"
static int scenario,inject,calls;
extern ssize_t __real_read(int,void *,size_t);
ssize_t __wrap_read(int fd,void *buffer,size_t n)
{
    if(inject) {
        calls++;
        if(scenario==12&&calls==1) { errno=EINTR;return -1; }
        if(scenario==13&&calls==1) return 0;
        if(scenario==14) return __real_read(fd,buffer,n>2?2:n);
        if(scenario==15&&calls==3) {
            ssize_t result=__real_read(fd,buffer,n);
            if(result>0) ((unsigned char *)buffer)[0]^=1;
            return result;
        }
        if(scenario==16&&calls==1) { errno=EIO;return -1; }
    }
    return __real_read(fd,buffer,n);
}
int main(int argc,char **argv)
{
    const char *dirs[]={"etc","etc/ssl","etc/ssl/certs","etc/nestlabs","etc/init.d",
        "nestlabs","nestlabs/lib","nestlabs/sbin"};
    const unsigned char data[]="synthetic original\000with binary tail";
    unsigned char buffer[128];struct hearth_snapshot_file result;
    int base,roots[2],fd,status;unsigned int i,target=HEARTH_CA,owner=getuid(),group=getgid();
    assert(argc==3);scenario=atoi(argv[1]);
    base=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(base>=0);
    assert(mkdirat(base,"root",0755)==0);assert(mkdirat(base,"user",0755)==0);
    roots[0]=openat(base,"root",O_RDONLY|O_DIRECTORY);roots[1]=openat(base,"user",O_RDONLY|O_DIRECTORY);
    assert(roots[0]>=0&&roots[1]>=0);
    for(i=0;i<8;i++) assert(mkdirat(roots[0],dirs[i],0755)==0);
    for(i=0;i<HEARTH_TARGET_COUNT;i++) {
        if(i==HEARTH_STORAGE_LIBRARY||i==HEARTH_LAUNCHER) continue;
        fd=openat(roots[i==HEARTH_SETTINGS],hearth_target_paths[i],O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
        assert(write(fd,data,sizeof(data))==(ssize_t)sizeof(data));assert(fchmod(fd,i==HEARTH_SETTINGS?0600:0644)==0);assert(close(fd)==0);
    }
    switch(scenario) {
    case 1: assert(unlinkat(roots[0],hearth_target_paths[target],0)==0);break;
    case 2:
        assert(unlinkat(roots[0],hearth_target_paths[target],0)==0);
        assert(symlinkat("/etc/passwd",roots[0],hearth_target_paths[target])==0);break;
    case 3:
        assert(renameat(roots[0],"etc/ssl/certs",roots[0],"etc/ssl/real")==0);
        assert(symlinkat("real",roots[0],"etc/ssl/certs")==0);break;
    case 4: assert(linkat(roots[0],hearth_target_paths[target],roots[0],"alias",0)==0);break;
    case 5: assert(fchmodat(roots[0],"etc/ssl",0777,0)==0);break;
    case 6: owner++;break;
    case 7: group++;break;
    case 8:
        assert(unlinkat(roots[0],hearth_target_paths[target],0)==0);
        assert(mkfifoat(roots[0],hearth_target_paths[target],0600)==0);break;
    case 9:
        fd=openat(roots[0],hearth_target_paths[target],O_RDONLY);assert(fd>=0);
        status=fsetxattr(fd,"user.hearth","present",7,0);close(fd);
        if(status&&errno==EOPNOTSUPP) return 77;
        assert(status==0);break;
    case 10: assert(fchmodat(roots[0],hearth_target_paths[target],04755,0)==0);break;
    case 11: target=HEARTH_TARGET_COUNT;break;
    default:break;
    }
    memset(buffer,0xa5,sizeof(buffer));memset(&result,0xa5,sizeof(result));inject=1;
    status=hearth_snapshot_file(roots,owner,group,target,buffer,scenario==17?3:sizeof(buffer),&result);
    inject=0;
    if(scenario==0||scenario==12||scenario==14) {
        assert(status==0&&result.existed==1&&result.size==sizeof(data)&&result.mode==0644);
        assert(result.target==target&&result.owner==owner&&result.group==group&&!memcmp(buffer,data,sizeof(data)));
        for(i=0;i<HEARTH_TARGET_COUNT;i++) {
            assert(hearth_snapshot_file(roots,owner,group,i,buffer,sizeof(buffer),&result)==0);
            assert(result.target==i);
            if(i==HEARTH_STORAGE_LIBRARY||i==HEARTH_LAUNCHER) assert(!result.existed&&!result.size&&!result.mode);
            else assert(result.existed&&result.size==sizeof(data)&&!memcmp(buffer,data,sizeof(data)));
        }
    } else {
        unsigned char empty[sizeof(result)];memset(empty,0,sizeof(empty));
        assert(status==-1&&!memcmp(empty,&result,sizeof(result)));
        for(i=0;i<(scenario==17?3:sizeof(buffer));i++) assert(buffer[i]==0);
    }
    assert(close(roots[0])==0&&close(roots[1])==0&&close(base)==0);
    return 0;
}
