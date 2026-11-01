/* Original trusted-host fault harness. Only synthetic temporary files. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <unistd.h>
#include "../firmware/network_snapshot/reader.h"
static int scenario,inject,calls;
extern ssize_t __real_read(int,void *,size_t);
ssize_t __wrap_read(int fd,void *buffer,size_t n)
{
 if(inject) {
  calls++;
  if(scenario==12&&calls==1) { errno=EINTR;return -1; }
  if(scenario==13&&calls==1) return 0;
  if(scenario==14) return __real_read(fd,buffer,n>2?2:n);
  if(scenario==15&&calls==3) { ssize_t k=__real_read(fd,buffer,n);if(k>0) ((unsigned char *)buffer)[0]^=1;return k; }
  if(scenario==16&&calls==1) { errno=EIO;return -1; }
 }
 return __real_read(fd,buffer,n);
}
int main(int argc,char **argv)
{
 const char *dirs[]={"nestlabs","nestlabs/sbin","usr","usr/sbin","etc","etc/connman","etc/nestlabs"};
 const unsigned char data[]="synthetic binary\000tail";
 unsigned char *buffer;struct hns_file result;unsigned int i,target=0,owner=getuid(),group=getgid();
 unsigned int capacity=hns_limits[0],length=sizeof(data);int root,fd,status;
 assert(argc==3);scenario=atoi(argv[1]);root=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(root>=0);
 for(i=0;i<7;i++) assert(mkdirat(root,dirs[i],0755)==0);
 for(i=0;i<4;i++) {
  fd=openat(root,hns_paths[i],O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
  assert(write(fd,data,sizeof(data))==(ssize_t)sizeof(data));assert(fchmod(fd,0644)==0);assert(close(fd)==0);
 }
 switch(scenario) {
 case 1: assert(unlinkat(root,hns_paths[0],0)==0);break;
 case 2: assert(unlinkat(root,hns_paths[0],0)==0);assert(symlinkat("/etc/passwd",root,hns_paths[0])==0);break;
 case 3: assert(renameat(root,"nestlabs/sbin",root,"nestlabs/real")==0);assert(symlinkat("real",root,"nestlabs/sbin")==0);break;
 case 4: assert(linkat(root,hns_paths[0],root,"alias",0)==0);break;
 case 5: assert(fchmodat(root,"nestlabs",0777,0)==0);break;
 case 6: owner++;break;
 case 7: group++;break;
 case 8: assert(unlinkat(root,hns_paths[0],0)==0);assert(mkfifoat(root,hns_paths[0],0600)==0);break;
 case 9:
  fd=openat(root,hns_paths[0],O_RDONLY);assert(fd>=0);status=fsetxattr(fd,"user.hearth","present",7,0);assert(close(fd)==0);
  if(status&&errno==EOPNOTSUPP) return 77;
  assert(status==0);break;
 case 10: assert(fchmodat(root,hns_paths[0],04755,0)==0);break;
 case 11: target=HNS_COUNT;break;
 case 17: capacity=3;break;
 case 18:
  fd=openat(root,hns_paths[0],O_WRONLY);assert(fd>=0);length=2U*1048576U+17U;
  assert(ftruncate(fd,length)==0);assert(close(fd)==0);break;
 case 19:
  fd=openat(root,hns_paths[0],O_WRONLY);assert(fd>=0);assert(ftruncate(fd,6U*1048576U+1U)==0);assert(close(fd)==0);break;
 case 20:
  fd=openat(root,hns_paths[0],O_WRONLY|O_TRUNC);assert(fd>=0);assert(close(fd)==0);break;
 case 21: assert(fchmodat(root,hns_paths[0],0666,0)==0);break;
 default:break;
 }
 buffer=malloc(capacity);assert(buffer);memset(buffer,0xa5,capacity);memset(&result,0xa5,sizeof(result));inject=1;
 status=hns_capture_file(root,owner,group,target,buffer,capacity,&result);inject=0;
 if(scenario==0||scenario==12||scenario==14||scenario==18) {
  assert(!status&&result.target==0&&result.existed==1&&result.mode==0644&&result.size==length);
  assert(result.owner==owner&&result.group==group&&!memcmp(buffer,data,sizeof(data)));
  if(scenario==18) for(i=sizeof(data);i<length;i++) assert(buffer[i]==0);
  for(i=1;i<4;i++) {
   assert(hns_capture_file(root,owner,group,i,buffer,128,&result)==0);
   assert(result.target==i&&result.size==sizeof(data)&&!memcmp(buffer,data,sizeof(data)));
  }
 } else {
  unsigned char empty[sizeof(result)];memset(empty,0,sizeof(empty));assert(status==-1&&!memcmp(empty,&result,sizeof(result)));
  for(i=0;i<capacity;i++) assert(buffer[i]==0);
 }
 free(buffer);assert(close(root)==0);return 0;
}
