/* Original restartable backup init (MIT). The canonical exporter is unchanged.
 * Reboot is reachable only after the fixed two-pass export and footer succeed.
 * A fresh host-held nonce is required; no flash writes or retry interface.
 */
#define HEARTH_CAPTURE_HOST_TEST
#include "../nand_capture/init.c"
#include "session.h"
#ifndef HEARTH_HANDOFF_HOST_TEST
static long call5(long number,long a,long b,long c,long d,long e)
{
 register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r7 __asm__("r7")=number;
 __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7):"memory","cc");return r0;
}
#endif
static void __attribute__((noreturn)) idle(void)
{ long pause[2]={1,0};for(;;) call5(162,(long)pause,0,0,0,0); }
static void __attribute__((noreturn)) await_restart(long serial)
{
 unsigned char ready[40],token[40],input[64];unsigned int i,matched=0;long n,pause[2]={0,100000000};
 for(i=0;i<8;i++) { ready[i]=(unsigned char)"HNBRDY1\n"[i];token[i]=(unsigned char)"HNBRST1\n"[i]; }
 for(i=0;i<32;i++) ready[8+i]=token[8+i]=hearth_session[i];
 for(;;) {
  /* Readiness is evidence only. A closed host tty never initiates a restart. */
  call5(4,serial,(long)ready,sizeof(ready),0,0);
  n=call5(3,serial,(long)input,sizeof(input),0,0);
  for(i=0;n>0&&i<(unsigned long)n;i++) {
   matched=input[i]==token[matched]?matched+1:input[i]==token[0];
   if(matched==sizeof(token)) goto restart;
  }
  call5(162,(long)pause,0,0,0,0);
 }
restart:
 call5(88,0xfee1deadUL,672274793UL,0x01234567UL,0,0);
 idle(); /* Returned reboot syscall is never retried. */
}
void __attribute__((noreturn)) _start(void)
{
 long serial,pause[2]={0,100000000};
 if(call5(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
    call5(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
    call5(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755")) idle();
 for(;;) {
  serial=call5(5,(long)"/dev/ttyGS0",2|0400|04000,0,0,0);
  if(serial>=0) break;
  call5(162,(long)pause,0,0,0,0);
 }
 if(wait_start(serial)||export_once(serial)) {
  static const unsigned char failure[]="HEARTH_RAW_CAPTURE_FAILED_V1\n";
  send_all(serial,failure,sizeof(failure)-1);call5(6,serial,0,0,0,0);idle();
 }
 await_restart(serial);
}
