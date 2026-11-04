/* Original fixed PID 1 for capacity/core9/cleanup3 in one RAM boot (MIT).
 * Children execute only checked bootstraps in fixed chroots. No rootfs bind
 * mounts: the pinned legacy kernel rejects them through MS_NOUSER. Libraries
 * use RAM hardlinks; originals are renamed between stages, retaining nlink 1.
 */
#include "sequence-binding.h"
#ifndef HEARTH_SEQUENCE_HOST_TEST
static long call(long nr,long a,long b,long c,long d,long e)
{
 register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r7 __asm__("r7")=nr;
 __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7):"memory","cc");return r0;
}
#else
static long call(long,long,long,long,long,long);
#endif
static void pause_short(void) { long t[2]={0,100000000};call(162,(long)t,0,0,0,0); }
static void __attribute__((noreturn)) fail(unsigned int stage,long error)
{
 static const char hex[]="0123456789abcdef";
 unsigned char report[64];unsigned int i;long fd;
 const char *prefix="HFW_BOOTSTRAP_FAILED_V1\nHSEQERR1 ";
 unsigned int used=0;
 while(prefix[used]) { report[used]=(unsigned char)prefix[used];used++; }
 for(i=0;i<8;i++) report[used++]=(unsigned char)hex[(stage>>(28-4*i))&15];
 report[used++]=' ';
 for(i=0;i<8;i++) report[used++]=(unsigned char)hex[((unsigned long)error>>(28-4*i))&15];
 report[used++]='\n';
 for(;;) {
  fd=call(5,(long)"/dev/ttyGS0",1|256|2048|32768,0,0,0);
  if(fd>=0) { call(4,fd,(long)report,used,0,0);call(6,fd,0,0,0,0); }
  pause_short();
 }
}
static int mount_at(const char *source,const char *target,const char *type,long flags,const char *data)
{ return (int)call(21,(long)source,(long)target,(long)type,flags,(long)data); }
static int child(const char *root)
{
 int pid=(int)call(2,0,0,0,0,0),status=-1;long waited;
 if(pid<0) return -1;
 if(!pid) {
  char *const argv[]={"/init",0};char *const env[]={"HOME=/nonexistent","LC_ALL=C",0};
  if(!call(61,(long)root,0,0,0,0)&&!call(12,(long)"/",0,0,0,0))
   call(11,(long)argv[0],(long)argv,(long)env,0,0);
  call(248,130,0,0,0,0);fail(90,-1);
 }
 do { waited=call(114,pid,(long)&status,0,0,0); } while(waited==-4);
 return waited==pid&&status==0?0:-1;
}
static int next(unsigned int slot)
{
 unsigned char token[72];unsigned int i;long fd,n,result;
 for(i=0;i<8;i++) token[i]=(unsigned char)"HFWNEXT1"[i];
 for(i=0;i<32;i++) { token[8+i]=hearth_sequence_plans[slot][i];token[40+i]=hearth_sequence_receipts[slot][i]; }
 fd=call(5,(long)"/sys/bus/platform/devices/omap2-nand.0/hearth_file_control",1|32768|524288,0,0,0);
 if(fd<0) return -1;
 n=call(4,fd,(long)token,sizeof(token),0,0);result=call(6,fd,0,0,0,0);
 return n==sizeof(token)&&!result?0:-1;
}
static int libraries(void)
{
 static const char *const sources[2]={"/lib/libc.so.6","/lib/ld-linux-armhf.so.3"};
 static const char *const targets[3][2]={
  {"/capacity/lib/libc.so.6","/capacity/lib/ld-linux-armhf.so.3"},
  {"/commissioning/lib/libc.so.6","/commissioning/lib/ld-linux-armhf.so.3"},
  {"/cleanup/lib/libc.so.6","/cleanup/lib/ld-linux-armhf.so.3"}};
 unsigned int i,j;
 for(i=0;i<3;i++) for(j=0;j<2;j++)
  if(call(9,(long)sources[j],(long)targets[i][j],0,0,0)) return -1;
 return 0;
}
static int originals(int cleanup)
{
 static const char *const initial[3]={"/originals/0","/originals/1","/originals/2"};
 static const char *const capacity[3]={"/capacity/originals/0","/capacity/originals/1","/capacity/originals/2"};
 static const char *const last[3]={"/cleanup/originals/0","/cleanup/originals/1","/cleanup/originals/2"};
 unsigned int i;
 for(i=0;i<3;i++) if(call(38,(long)(cleanup?capacity[i]:initial[i]),(long)(cleanup?last[i]:capacity[i]),0,0,0)) return -1;
 return 0;
}
void __attribute__((noreturn)) _start(void)
{
 int proc=mount_at("proc","/proc","proc",14,0),sys=mount_at("sysfs","/sys","sysfs",14,0);
 int dev=mount_at("devtmpfs","/dev","devtmpfs",10,"mode=0755");
 if(proc||sys||dev) fail(1,proc?proc:sys?sys:dev);
 if(libraries()) fail(2,-1);
 if(originals(0)) fail(3,-1);
 if(child("/capacity")) fail(4,-1);
 if(originals(1)) fail(5,-1);
 if(next(1)) fail(6,-1);
 if(child("/commissioning")) fail(7,-1);
 if(next(2)) fail(8,-1);
 if(child("/cleanup")) fail(9,-1);
 /* The final verified result authorizes a normal restart; PID 1 stays alive. */
 for(;;) pause_short();
}
