/* Original bounded JFFS2 snapshot supervisor (MIT), no native firmware executed.
 * Writes only RAM, virtual mount state and the USB tty; no writable flash mount.
 */
#include "snapshot.h"
#include "session.h"
/* GCC may lower automatic aggregate initialization to memset even when the
 * translation unit is freestanding. Supply only our original byte loop. */
void *memset(void *memory,int value,hearth_file_size length)
{
    unsigned char *p=memory;hearth_file_size i;
    for(i=0;i<length;i++) p[i]=(unsigned char)value;
    return memory;
}
static long raw(long number,long a,long b,long c,long d,long e)
{
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r7 __asm__("r7")=number;
    __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7):"memory","cc");
    return r0;
}
static int error_number;
int *__errno_location(void) { return &error_number; }
static long checked(long n) { if(n<0) { error_number=(int)-n;return -1; }return n; }
int openat(int fd,const char *p,int flags,...) { return (int)checked(raw(322,fd,(long)p,flags,0,0)); }
int close(int fd) { return (int)checked(raw(6,fd,0,0,0,0)); }
long read(int fd,void *b,hearth_file_size n) { return checked(raw(3,fd,(long)b,(long)n,0,0)); }
long lseek(int fd,long off,int whence) { return checked(raw(19,fd,off,whence,0,0)); }
long flistxattr(int fd,char *b,hearth_file_size n) { return checked(raw(234,fd,(long)b,(long)n,0,0)); }
long syscall(long number,...)
{
    __builtin_va_list v;long a,b,c=0,d=0;
    __builtin_va_start(v,number);a=__builtin_va_arg(v,long);b=__builtin_va_arg(v,long);
    if(number==327) { c=__builtin_va_arg(v,long);d=__builtin_va_arg(v,long); }
    __builtin_va_end(v);
    if(number!=197&&number!=100&&number!=327) return checked(-22);
    return checked(raw(number,a,b,c,d,0));
}
#define CAPACITY (9U*(HEARTH_FILE_BYTES+24U)+8U)
static unsigned char payload[CAPACITY],scratch[HEARTH_FILE_BYTES];
static unsigned int size;
static void put(unsigned char *p,unsigned int n)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(n>>(i*8)); }
static unsigned int crc(const unsigned char *p,unsigned int n)
{
    unsigned int value=~0U,i,j;
    for(i=0;i<n;i++) { value^=p[i];for(j=0;j<8;j++) value=(value>>1)^((0U-(value&1U))&0xedb88320U); }
    return ~value;
}
static int capture(void)
{
    int roots[2]={-1,-1},status=-1;unsigned int i,j;
    struct hearth_snapshot_file f;
    /* Fixed named source; this does not claim root0 is the native active root. */
    if(raw(39,(long)"/native",0700,0,0,0)||raw(39,(long)"/user",0700,0,0,0)) return -1;
    if(raw(21,(long)"mtd:root0",(long)"/native",(long)"jffs2",1039,0)||
       raw(21,(long)"mtd:user-config",(long)"/user",(long)"jffs2",1039,0)) return -1;
    roots[0]=openat(-100,"/native",16384|32768|524288);
    roots[1]=openat(-100,"/user",16384|32768|524288);
    if(roots[0]<0||roots[1]<0) goto done;
    put(payload,0);put(payload+4,9);size=8;
    for(i=0;i<9;i++) {
        if(hearth_snapshot_file(roots,0,0,i,scratch,sizeof(scratch),&f)) goto done;
        put(payload+size,f.target);put(payload+size+4,f.existed);put(payload+size+8,f.mode);
        put(payload+size+12,f.owner);put(payload+size+16,f.group);put(payload+size+20,f.size);size+=24;
        for(j=0;j<f.size;j++) payload[size++]=scratch[j];
    }
    status=0;
done:
    for(i=0;i<sizeof(scratch);i++) scratch[i]=0;
    if(roots[0]>=0&&close(roots[0])) status=-1;
    if(roots[1]>=0&&close(roots[1])) status=-1;
    return status;
}
static int send_all(long fd,const unsigned char *data,unsigned int count)
{
    unsigned int at=0,retries=0;long pause[2]={0,10000000};
    while(at<count) {
        long n=raw(4,fd,(long)(data+at),count-at,0,0);
        if(n>0&&(unsigned long)n<=count-at) { at+=(unsigned int)n;retries=0; }
        else if((n==-11||n==-4)&&retries++<500) raw(162,(long)pause,0,0,0,0);
        else return -1;
    }
    return 0;
}
void __attribute__((noreturn)) _start(void)
{
    unsigned char header[48]={'H','F','S','N','A','P','1','\n'};
    static const unsigned char footer[]="HFSEND1\n",failure[]="HEARTH_SNAPSHOT_FAILED_V1\n";
    long pause[2]={1,0};int failed;unsigned int i;
    failed=raw(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
           raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
           raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755");
    if(!failed) failed=capture();
    for(i=0;i<32;i++) header[8+i]=hearth_session[i];
    put(header+40,size);put(header+44,crc(payload,size));
    for(;;) {
        long fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
        if(fd>=0) {
            if(failed) send_all(fd,failure,sizeof(failure)-1);
            else if(!send_all(fd,header,sizeof(header))&&!send_all(fd,payload,size))
                send_all(fd,footer,sizeof(footer)-1);
            raw(6,fd,0,0,0,0);
        }
        raw(162,(long)pause,0,0,0,0);
    }
}
