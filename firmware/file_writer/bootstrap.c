/* Original static PID 1, MIT. Executes only original synthetic selftests first.
 * A scoped host acknowledgment is required before the root action is launched.
 * Selftests run as nobody, cannot open the root-only gate or capsule executable.
 */
#include "../settings_probe/capture.h"
#include "../settings_compat_probe/transmit.h"
#include "../settings_compat_probe/exec.h"
#include "binding.h"
#ifndef HEARTH_FILE_ACTION
#error "Explicit profile action required"
#endif
#if HEARTH_FILE_ACTION != 1 && HEARTH_FILE_ACTION != 2
#error "Unknown profile action"
#endif
static long sc(long nr,long a,long b,long c,long d,long e)
{
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r7 __asm__("r7")=nr;
    __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7):"memory","cc");
    return r0;
}
static long execute(const char *path,char *const argv[],char *const env[])
{ return sc(11,(long)path,(long)argv,(long)env,0,0); }
static void pause_short(void) { long delay[2]={0,100000000};sc(162,(long)delay,0,0,0,0); }
static long now(void) { long v[2]={0,0};return sc(263,1,(long)v,0,0,0)==0?v[0]:-1; }
static void child_fail(void)
{ sc(248,130,0,0,0,0);for(;;) pause_short(); }
static int run_selftest(void)
{
    int output[2],errors[2],pollfd[4],pid,status=-1,open_output=1,open_errors=1;
    unsigned char chunk[512];long n,started;
    char *const args[]={"/file-selftest","files",0};
    char *const env[]={"LD_LIBRARY_PATH=/lib","HOME=/nonexistent","LC_ALL=C",0};
    if(sc(42,(long)output,0,0,0,0)) return -201;
    if(sc(42,(long)errors,0,0,0,0)) { sc(6,output[0],0,0,0,0);sc(6,output[1],0,0,0,0);return -202; }
    pid=(int)sc(2,0,0,0,0,0);
    if(pid<0) {
        sc(6,output[0],0,0,0,0);sc(6,output[1],0,0,0,0);
        sc(6,errors[0],0,0,0,0);sc(6,errors[1],0,0,0,0);return -203;
    }
    if(!pid) {
        long fd;int i;
        if(sc(57,0,0,0,0,0)||sc(63,output[1],1,0,0,0)<0||sc(63,errors[1],2,0,0,0)<0) child_fail();
        fd=sc(5,(long)"/dev/null",2,0,0,0);if(fd<0||sc(63,fd,0,0,0,0)<0) child_fail();
        for(i=3;i<64;i++) sc(6,i,0,0,0,0);
        if(sc(206,0,0,0,0,0)||sc(214,65534,0,0,0,0)||sc(213,65534,0,0,0,0)) child_fail();
        hearth_exec_argv(args,env,execute);child_fail();
    }
    sc(6,output[1],0,0,0,0);sc(6,errors[1],0,0,0,0);started=now();
    while(open_output||open_errors) {
        long elapsed=now();
        if(started<0||elapsed<started||elapsed-started>120) goto stop;
        pollfd[0]=open_output?output[0]:-1;pollfd[1]=1;
        pollfd[2]=open_errors?errors[0]:-1;pollfd[3]=1;
        n=sc(168,(long)pollfd,2,1000,0,0);if(n<0) goto stop;
        if(open_output&&(pollfd[1]>>16)) {
            n=sc(3,output[0],(long)chunk,sizeof(chunk),0,0);
            if(n<=0) open_output=0;else if(!capture_output(chunk,n)) goto stop;
        }
        if(open_errors&&(pollfd[3]>>16)) {
            n=sc(3,errors[0],(long)chunk,sizeof(chunk),0,0);
            if(n<=0) open_errors=0;else if(!capture_diagnostics(chunk,n)) goto stop;
        }
    }
    goto collected;
stop:
    sc(37,-pid,9,0,0,0);sc(37,pid,9,0,0,0);
collected:
    sc(6,output[0],0,0,0,0);sc(6,errors[0],0,0,0,0);
    return sc(114,pid,(long)&status,0,0,0)==pid?status:-204;
}
static unsigned char report[16384];static unsigned int used;
static void append(const char *text)
{ while(*text&&used<sizeof(report)-1) report[used++]=(unsigned char)*text++; }
static void number(long value)
{
    char digits[16];unsigned int count=0;unsigned long magnitude;
    if(value<0) append("-");magnitude=value<0?0UL-(unsigned long)value:(unsigned long)value;
    do { digits[count++]=(char)('0'+magnitude%10);magnitude/=10; } while(magnitude);
    while(count) { char one[2]={digits[--count],0};append(one); }
}
static void put(unsigned char *p,unsigned int value)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(value>>(8*i)); }
static unsigned int crc(const unsigned char *p,unsigned int length)
{
    unsigned int value=~0U,i,j;
    for(i=0;i<length;i++) { value^=p[i];for(j=0;j<8;j++) value=(value>>1)^((0U-(value&1U))&0xedb88320U); }
    return ~value;
}
static long send_bytes(long fd,const char *data,long size) { return sc(4,fd,(long)data,size,0,0); }
void __attribute__((noreturn)) _start(void)
{
    long fd=-1,started;unsigned int i,matched=0;int setup,status;
    unsigned char ack[76],input[256];struct hearth_cached_transmit sending={0};
    char *const args[]={"/file-action",0};
    char *const env[]={"LD_LIBRARY_PATH=/lib","HOME=/nonexistent","LC_ALL=C",0};
    setup=(int)(sc(21,(long)"proc",(long)"/proc",(long)"proc",14,0)||
        sc(21,(long)"sysfs",(long)"/sys",(long)"sysfs",14,0)||
        sc(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755"));
    status=setup?-200:run_selftest();
    used=84;
    for(i=0;i<(unsigned int)output_used;i++) report[used++]=(unsigned char)child_output[i];
    if(output_used&&child_output[output_used-1]!='\n') append("\n");
    for(i=0;i<(unsigned int)diagnostics_used;) {
        static const char hex[]="0123456789abcdef";
        unsigned int end=i+128<(unsigned int)diagnostics_used?i+128:(unsigned int)diagnostics_used;
        append("{\"type\":\"file_selftest_stderr\",\"hex\":\"");
        while(i<end) {
            char pair[3]={hex[child_diagnostics[i]>>4],hex[child_diagnostics[i]&15],0};
            append(pair);i++;
        }
        append("\"}\n");
    }
    append("{\"type\":\"file_selftest_process\",\"wait_status\":");number(status);
    append(",\"stderr_bytes\":");number(diagnostics_used);
    append(",\"stderr_dropped\":");number(diagnostics_dropped);
    append(",\"stdout_bytes\":");number(output_used);append("}\n");
    for(i=0;i<8;i++) { report[i]=(unsigned char)"HFW_TST1"[i];ack[i]=(unsigned char)"HFW_ACK1"[i]; }
    for(i=0;i<32;i++) {
        report[8+i]=ack[8+i]=hearth_expected_plan[i];
        report[40+i]=ack[40+i]=hearth_expected_receipt[i];
    }
    put(report+72,HEARTH_FILE_ACTION);put(ack+72,HEARTH_FILE_ACTION);
    put(report+76,used-84);put(report+80,crc(report+84,used-84));
    for(i=0;i<8;i++) report[used++]=(unsigned char)"HFW_END1"[i];
    for(;;) { fd=sc(5,(long)"/dev/ttyGS0",2|0400|04000,0,0,0);if(fd>=0) break;pause_short(); }
    started=now();
    for(;;) {
        long n;int tx=hearth_cached_transmit_step(&sending,fd,(const char *)report,used,send_bytes);
        if(tx==HEARTH_TRANSMIT_DONE) pause_short();
        n=sc(3,fd,(long)input,sizeof(input),0,0);
        for(i=0;n>0&&i<(unsigned long)n;i++) {
            matched=input[i]==ack[matched]?matched+1:input[i]==ack[0];
            if(matched==sizeof(ack)) {
                if(!setup&&!status&&!diagnostics_used&&started>=0&&now()>=started&&now()-started<=600) goto launch;
                matched=0;
            }
        }
        pause_short();
    }
launch:
    if(sc(63,fd,1,0,0,0)<0||sc(63,fd,2,0,0,0)<0) goto failed;
    for(i=3;i<64;i++) sc(6,i,0,0,0,0);
    hearth_exec_argv(args,env,execute);
failed:
    for(;;) {
        static const char failure[]="HFW_BOOTSTRAP_FAILED_V1\n";
        sc(4,1,(long)failure,sizeof(failure)-1,0,0);pause_short();
    }
}
