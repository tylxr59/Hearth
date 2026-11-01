/* Original syscall-only ARM adapter, reused from the protected snapshot (MIT). */
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
