/* Original synthetic-host tests of the separately scoped reused transaction. */
#ifdef HEARTH_RAM_LAB
#include "../firmware/file_install_probe/lab_abi.h"
extern void *malloc(size_t),*memcpy(void *,const void *,size_t);
extern void free(void *);
extern char *strstr(const char *,const char *);
#define EINTR 4
#define ENOSPC 28
#define O_EXCL 128
#define AT_REMOVEDIR 512
#else
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
#include "../firmware/network_update/posix.h"
static int scenario,armed,injected,renamed,writes;
extern ssize_t __real_write(int,const void *,size_t),__real_read(int,void *,size_t);
extern int __real_fsync(int),__real_renameat(int,const char *,int,const char *),__real_fchmod(int,mode_t),__real_fchown(int,uid_t,gid_t);
ssize_t __wrap_write(int fd,const void *p,size_t n)
{
 if(armed) {
  writes++;
  if(scenario==1&&!injected++) { errno=EINTR;return -1; }
  if(scenario==2&&n>65535) n=65535;
  if(scenario==3&&!injected++) { errno=EIO;return -1; }
  if(scenario==4&&n>48) { errno=ENOSPC;return -1; }
 }
 return __real_write(fd,p,n);
}
ssize_t __wrap_read(int fd,void *p,size_t n)
{
 ssize_t result=__real_read(fd,p,n);
 if(armed&&scenario==9&&writes>1&&result>0&&!injected++) ((unsigned char *)p)[0]^=1;
 return result;
}
int __wrap_renameat(int a,const char *b,int c,const char *d)
{
 int result;
 if(armed&&scenario==5&&strstr(b,".hearth-new")&&!injected++) { errno=EIO;return -1; }
 result=__real_renameat(a,b,c,d);
 if(armed&&!result&&(strstr(b,".hearth-new")||strstr(b,".hearth-restore"))) renamed=1;
 return result;
}
int __wrap_fsync(int fd)
{
 struct stat st;
 if(armed&&(scenario==6||scenario==17)&&renamed&&!injected&&fstat(fd,&st)==0&&S_ISDIR(st.st_mode)) {
  injected=1;errno=EIO;return -1;
 }
 return __real_fsync(fd);
}
int __wrap_fchmod(int fd,mode_t mode)
{ if(armed&&scenario==7&&!injected++) { errno=EPERM;return -1; }return __real_fchmod(fd,mode); }
int __wrap_fchown(int fd,uid_t owner,gid_t group)
{ if(armed&&scenario==8&&!injected++) { errno=EPERM;return -1; }return __real_fchown(fd,owner,group); }
static void check_file(int root,const char *name,const unsigned char *bytes,unsigned int size)
{
 unsigned char b[4096];unsigned int at=0;int fd=openat(root,name,O_RDONLY|O_NOFOLLOW);assert(fd>=0);
 while(at<size) { unsigned int amount=size-at;if(amount>sizeof(b)) amount=sizeof(b);assert(read(fd,b,amount)==(ssize_t)amount);assert(!memcmp(b,bytes+at,amount));at+=amount; }
 assert(read(fd,b,1)==0);assert(close(fd)==0);
}
static void reset(struct hearth_posix_context *c)
{
 unsigned int i;
 if(c->recovery>=0) assert(close(c->recovery)==0);
 c->recovery=-1;c->journal_temporary=0;for(i=0;i<HEARTH_FILE_LIMIT;i++) c->created[i]=0;
}
#if defined(HEARTH_RAM_LAB) || defined(HEARTH_CLEAN_FIXTURE)
static void remove_known(int root,const char *name,int flags)
{ int result=unlinkat(root,name,flags);assert(result==0||errno==ENOENT); }
static void clean_fixture(int root,const char *const *dirs)
{
 static const char prefix[]=".hearth-rollback-";char archive[96],name[128];unsigned int i,n=0;int fd;
 for(i=0;prefix[i];i++) archive[n++]=prefix[i];
 for(i=0;i<32;i++) { archive[n++]='2';archive[n++]='a'; }archive[n]=0;
 fd=openat(root,archive,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
 if(fd>=0) {
  for(i=0;i<4;i++) { snprintf(name,sizeof(name),"%u.original",i);remove_known(fd,name,0); }
  remove_known(fd,"journal",0);remove_known(fd,"journal.new",0);assert(close(fd)==0);
  remove_known(root,archive,AT_REMOVEDIR);
 } else assert(errno==ENOENT);
 for(i=0;i<4;i++) {
  remove_known(root,hearth_target_paths[i],0);
  snprintf(name,sizeof(name),"%s.hearth-new",hearth_target_paths[i]);remove_known(root,name,0);
  snprintf(name,sizeof(name),"%s.hearth-restore",hearth_target_paths[i]);remove_known(root,name,0);
 }
 for(i=7;i;i--) remove_known(root,dirs[i-1],AT_REMOVEDIR);
}
#endif
int main(int argc,char **argv)
{
 const char *dirs[]={"nestlabs","nestlabs/sbin","usr","usr/sbin","etc","etc/connman","etc/nestlabs"};
 struct hearth_posix_context c;struct hearth_file_change changes[4];struct hearth_install_result result;
 unsigned char *original,*replacement;unsigned int i,length=2U*1048576U+17U;int fd,root,status;
 assert(argc==3);scenario=atoi(argv[1]);root=open(argv[2],O_RDONLY|O_DIRECTORY);assert(root>=0);
 original=malloc(length);replacement=malloc(length);assert(original&&replacement);
 for(i=0;i<length;i++) original[i]=(unsigned char)i;
 memcpy(replacement,original,length);for(i=4090;i<4130;i++) replacement[i]^=0x5a;
 for(i=0;i<7;i++) assert(mkdirat(root,dirs[i],0755)==0);
 for(i=0;i<4;i++) {
  unsigned int size=i?31:length,mode=i==3?0600:0755;
  changes[i]=(struct hearth_file_change){i,1,{original,size},{replacement,size},mode,mode};
  /* Ensure every small file changes too. */
  if(i) changes[i].replacement.data=replacement+4090;
  fd=openat(root,hearth_target_paths[i],O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
  assert(write(fd,original,size)==(ssize_t)size);assert(fchmod(fd,mode)==0);assert(close(fd)==0);
 }
 memset(&c,0,sizeof(c));c.roots[0]=root;c.roots[1]=openat(root,".",O_RDONLY|O_DIRECTORY);assert(c.roots[1]>=0);
 c.recovery=-1;c.owner=getuid();c.group=getgid();c.count=4;c.changes=changes;c.archive_layout=1;
 memset(c.plan_id,42,sizeof(c.plan_id));
 if(scenario==10) changes[1].original.size=changes[1].replacement.size=1048577;
 if(scenario==11) changes[1].target=0;
 if(scenario==12) changes[0].replacement_mode=0644;
 if(scenario==13) { fd=openat(root,hearth_target_paths[0],O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0); }
 if(scenario==18) c.count=5;
 if(scenario==19) c.archive_layout=0;
 armed=scenario<14||scenario>=18;
 result=hearth_install_files(&hearth_posix_file_ops,&c,4,1);armed=0;
 if((scenario>=3&&scenario<=13)||scenario>=18) {
  assert(result.error!=0);
  if(scenario>=10) assert(writes==0);
  if(scenario!=13) for(i=0;i<4;i++) check_file(root,hearth_target_paths[i],original,i?31:length);
 } else {
  assert(result.committed&&result.error==0);
  for(i=0;i<4;i++) check_file(root,hearth_target_paths[i],changes[i].replacement.data,i?31:length);
  reset(&c);
  if(scenario==15) {
   fd=openat(root,hearth_target_paths[0],O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0);
   status=hearth_posix_restore_preflight(&c);assert(status!=0);goto done;
  }
  if(scenario==16) {
   fd=openat(root,"nestlabs/sbin/nlclient.hearth-restore",O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
   assert(write(fd,original,53)==53);assert(close(fd)==0);
  }
  assert(hearth_posix_restore_preflight(&c)==0);reset(&c);
  injected=0;renamed=0;armed=scenario==17;
  result=hearth_posix_restore_files(&c);armed=0;
  if(scenario==17) { assert(result.error!=0);reset(&c);result=hearth_posix_restore_files(&c); }
  assert(!result.error&&result.restored==15);
  for(i=0;i<4;i++) check_file(root,hearth_target_paths[i],original,i?31:length);
 }
done:
 reset(&c);assert(close(c.roots[1])==0);
#if defined(HEARTH_RAM_LAB) || defined(HEARTH_CLEAN_FIXTURE)
 clean_fixture(root,dirs);
#endif
 assert(close(root)==0);free(original);free(replacement);return 0;
}
