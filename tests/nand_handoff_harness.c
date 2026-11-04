/* Original mocked-syscall full-export/restart ordering matrix. No real IO. */
#include <assert.h>
#include <setjmp.h>
#include <string.h>
#define HEARTH_HANDOFF_HOST_TEST
#define _start handoff_start
#include "../firmware/nand_handoff/init.c"
#undef _start
static jmp_buf stopped;
static unsigned int scenario,position,reads,starts,restarts,ready,export_ticks;
static long call5(long number,long a,long b,long c,long d,long e)
{
 unsigned int i;unsigned char *bytes=(unsigned char *)b;
 (void)d;(void)e;
 if(number==21) return 0;
 if(number==5) {
  const char *path=(const char *)a;
  if(!strcmp(path,"/dev/ttyGS0")) return 9;
  assert(!strcmp(path,"/sys/class/mtd/mtd0/hearth_raw")&&b==0);
  position=0;return 10;
 }
 if(number==6) { assert(a==9||a==10);return 0; }
 if(number==3&&a==10) {
  assert(c==SAMPLE_RECORD&&position<SAMPLE_PAGES);
  if(scenario==1) return -5;
  memset(bytes,position++,(unsigned int)c);reads++;return c;
 }
 if(number==3&&a==9) {
  if(c==1) { bytes[0]=(unsigned char)"HRTHGO1\n"[starts++];return 1; }
  assert(c==64&&reads==2*SAMPLE_PAGES);
  memcpy(bytes,"HNBRST1\n",8);
  for(i=0;i<32;i++) bytes[8+i]=scenario==2?0:hearth_session[i];
  return 40;
 }
 if(number==4) {
  assert(a==9); /* No NAND write syscall is permitted. */
  if(c==40&&!memcmp(bytes,"HNBRDY1\n",8)) { assert(reads==2*SAMPLE_PAGES);ready++; }
  return c;
 }
 if(number==88) {
  assert((unsigned long)a==0xfee1deadUL&&b==672274793UL&&c==0x01234567UL);
  assert(reads==2*SAMPLE_PAGES&&ready&&scenario!=1&&scenario!=2);
  restarts++;
  if(scenario==3) return -1;
  longjmp(stopped,1);
 }
 if(number==162) {
  long *pause=(long *)a;
  if(pause[0]==1) longjmp(stopped,1);
  if(reads==2*SAMPLE_PAGES&&++export_ticks>3) longjmp(stopped,1);
  return 0;
 }
 assert(!"unexpected syscall");return -1;
}
int main(void)
{
 for(scenario=0;scenario<4;scenario++) {
  position=reads=starts=restarts=ready=export_ticks=0;
  if(!setjmp(stopped)) handoff_start();
  assert(starts==8);
  if(scenario==1) assert(!reads&&!ready&&!restarts);
  else assert(reads==2*SAMPLE_PAGES);
  if(scenario==2) assert(ready&&!restarts);
  if(scenario==0||scenario==3) assert(restarts==1);
 }
 return 0;
}
