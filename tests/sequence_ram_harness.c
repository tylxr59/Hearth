/* Original real-filesystem RAM sharing test with mocked ARM syscall numbers.
 * Test paths are under one temporary host folder. No mount, USB or flash call.
 */
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define HEARTH_SEQUENCE_HOST_TEST
#define _start sequence_start
#include "../firmware/install_sequence/init.c"
#undef _start
static const char *test_root;
static unsigned int links,moves;
static unsigned int children,gates;
static jmp_buf finished;
static void path(char *out,const char *name)
{ assert(snprintf(out,4096,"%s%s",test_root,name)>0); }
static long call(long nr,long a,long b,long c,long d,long e)
{
 char old[4096],target[4096];
 (void)c;(void)e;
 if(nr==21) { assert(d!=4096);return 0; } /* Rootfs bind mounts are forbidden. */
 if(nr==2) { children++;return 42; }
 if(nr==114) { assert(a==42);*(int *)b=0;return 42; }
 if(nr==5) {
  assert(!strcmp((const char *)a,"/sys/bus/platform/devices/omap2-nand.0/hearth_file_control"));
  return 99;
 }
 if(nr==4) {
  assert(a==99&&c==72&&!memcmp((const void *)b,"HFWNEXT1",8));
  gates++;assert(gates==children&&gates<=2);
  assert(!memcmp((const unsigned char *)b+8,hearth_sequence_plans[gates],32));
  return c;
 }
 if(nr==6) { assert(a==99);return 0; }
 if(nr==162) { assert(children==3&&gates==2);longjmp(finished,1); }
 if(nr==9||nr==38) {
  path(old,(const char *)a);path(target,(const char *)b);
  if(nr==9) { links++;return link(old,target); }
  moves++;return rename(old,target);
 }
 assert(!"unexpected syscall in RAM setup");return -1;
}
static void check(const char *name,unsigned int count,unsigned int mode)
{
 char file[4096];struct stat s;path(file,name);
 assert(!stat(file,&s)&&s.st_nlink==count&&(s.st_mode&0777)==mode);
}
int main(int argc,char **argv)
{
 unsigned int i;char name[80],old[4096];
 assert(argc==2);test_root=argv[1];
 assert(!libraries()&&links==6);
 check("/lib/libc.so.6",4,0444);check("/lib/ld-linux-armhf.so.3",4,0555);
 check("/capacity/lib/libc.so.6",4,0444);
 assert(!originals(0)&&moves==3);
 for(i=0;i<3;i++) {
  snprintf(name,sizeof(name),"/capacity/originals/%u",i);check(name,1,0400);
  snprintf(name,sizeof(name),"/originals/%u",i);path(old,name);assert(access(old,F_OK));
 }
 assert(!originals(1)&&moves==6);
 for(i=0;i<3;i++) {
  snprintf(name,sizeof(name),"/cleanup/originals/%u",i);check(name,1,0400);
  snprintf(name,sizeof(name),"/capacity/originals/%u",i);path(old,name);assert(access(old,F_OK));
 }
 /* Reset only these temporary RAM-fixture paths, then exercise the complete
  * parent setup/order. Every mount syscall is checked against legacy rootfs
  * restrictions; any reintroduced MS_BIND aborts before a child can run. */
 for(i=0;i<3;i++) {
  char target[4096];
  snprintf(name,sizeof(name),"/cleanup/originals/%u",i);path(old,name);
  snprintf(name,sizeof(name),"/originals/%u",i);path(target,name);assert(!rename(old,target));
 }
 {
  const char *phases[3]={"capacity","commissioning","cleanup"};unsigned int j;
  for(i=0;i<3;i++) for(j=0;j<2;j++) {
   snprintf(name,sizeof(name),"/%s/lib/%s",phases[i],j?"ld-linux-armhf.so.3":"libc.so.6");
   path(old,name);assert(!unlink(old));
  }
 }
 links=moves=0;
 if(!setjmp(finished)) sequence_start();
 assert(links==6&&moves==6&&children==3&&gates==2);
 check("/cleanup/originals/0",1,0400);
 return 0;
}
