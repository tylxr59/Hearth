/* Original one-shot Linux warm-reset experiment (MIT).
 * No flash mounts, native executable, memory mapping, arbitrary command or
 * boot-register edits. One fresh nonce permits exactly one reboot syscall.
 */
#include "session.h"
static long call(long nr,long a,long b,long c,long d,long e)
{
 register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r7 __asm__("r7")=nr;
 __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7):"memory","cc");return r0;
}
static void pause_short(void) { long t[2]={0,100000000};call(162,(long)t,0,0,0,0); }
void __attribute__((noreturn)) _start(void)
{
 unsigned char ready[40],token[40],input[64];unsigned int i,matched=0;long fd,n;
 if(call(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755")) for(;;) pause_short();
 for(i=0;i<8;i++) { ready[i]=(unsigned char)"HROMRDY1"[i];token[i]=(unsigned char)"HROMRST1"[i]; }
 for(i=0;i<32;i++) ready[8+i]=token[8+i]=hearth_session[i];
 for(;;) { fd=call(5,(long)"/dev/ttyGS0",2|256|2048|32768,0,0,0);if(fd>=0) break;pause_short(); }
 for(;;) {
  call(4,fd,(long)ready,sizeof(ready),0,0);
  n=call(3,fd,(long)input,sizeof(input),0,0);
  for(i=0;n>0&&i<(unsigned long)n;i++) {
   matched=input[i]==token[matched]?matched+1:input[i]==token[0];
   if(matched==sizeof(token)) goto restart;
  }
  pause_short();
 }
restart:
 /* ARM Linux reboot(RESTART). Normal kernel shutdown, one warm reset. */
 call(88,0xfee1deadUL,672274793UL,0x01234567UL,0,0);
 for(;;) pause_short(); /* Returned syscall never retries. */
}
