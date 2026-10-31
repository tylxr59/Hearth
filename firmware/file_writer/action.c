/* Original fixed-plan file action, MIT. Runs only inside a reviewed private RAM
 * image. No shell, arbitrary paths, network, firmware execution or raw MTD API.
 * Starts read-only and waits for one exact owner-timed commit/abort frame. */
#include "abi.h"
#include "lifecycle.h"
#include "../file_install/posix.h"
#include "../file_install/snapshot.h"
#include "../settings_compat_probe/transmit.h"
#include "capsule.h"
#include "binding.h"
#ifndef HEARTH_FILE_ACTION
#error "Explicit install=1 or restore=2 build required"
#endif
#if HEARTH_FILE_ACTION != 1 && HEARTH_FILE_ACTION != 2
#error "Unsupported file action"
#endif
static const char *const roots[2]={"/native","/user"};
static const char control[]="/sys/bus/platform/devices/omap2-nand.0/hearth_file_control";
static const char status_path[]="/sys/bus/platform/devices/omap2-nand.0/hearth_file_status";
static unsigned char scratch[HEARTH_FILE_BYTES],report[8192];
static unsigned char snapshot[9U*(HEARTH_FILE_BYTES+24U)+100U];
static unsigned int snapshot_size;
static int tty=-1;
struct action_context {
    struct hearth_posix_context files;
    unsigned int mounted;
    int preflight_target;
    unsigned int phase,protected,programs,erases,markers,failed;
};
static void put(unsigned char *p,unsigned int value)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(value>>(8*i)); }
static unsigned int word(const unsigned char *p)
{ return p[0]|(unsigned int)p[1]<<8|(unsigned int)p[2]<<16|(unsigned int)p[3]<<24; }
static void pause_short(void) { long delay[2]={0,100000000};nanosleep(delay,0); }
static long monotonic(void)
{ long value[2]={0,0};return syscall(263,1,value)==0?value[0]:-1; }
static int read_status(struct action_context *c)
{
    char data[256];long n;int used=-1,fields,fd=open(status_path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0) return -1;
    n=read(fd,data,sizeof(data)-1);
    if(close(fd)||n<=0||n>=(long)sizeof(data)-1) return -1;
    data[n]=0;
    fields=sscanf(data,"phase=%u protected=%u program=%u erase=%u marker=%u failed=%u\n%n",
        &c->phase,&c->protected,&c->programs,&c->erases,&c->markers,&c->failed,&used);
    return fields==6&&used==n ? 0 : -1;
}
static int send_control(const unsigned char *data,unsigned int length)
{
    long n;int fd=open(control,O_WRONLY|O_NOFOLLOW|O_CLOEXEC),result=-1;
    if(fd<0) return -1;
    n=write(fd,data,length);if(n==(long)length) result=0;
    if(close(fd)) result=-1;
    return result;
}
static int release_roots(void *opaque)
{
    struct action_context *c=opaque;unsigned int i;int result=0;
    if(c->files.recovery>=0) { if(close(c->files.recovery)) result=-1;c->files.recovery=-1; }
    for(i=0;i<2;i++) if(c->files.roots[i]>=0) {
        if(close(c->files.roots[i])) result=-1;c->files.roots[i]=-1;
    }
    return result;
}
static int unmount_root(void *opaque,unsigned int i)
{
    struct action_context *c=opaque;
    if(!(c->mounted&(1U<<i))) return 0;
    if(umount2(roots[i],0)) return -1;
    c->mounted&=~(1U<<i);return 0;
}
static int seal(void *opaque)
{
    struct action_context *c=opaque;
    if(send_control((const unsigned char *)"HFWCLOSE",8)||read_status(c)||
       c->phase!=2||c->protected!=1) return -1;
    return 0;
}
static int readonly_roots(struct action_context *c)
{
    unsigned int i;
    for(i=0;i<2;i++) {
        unsigned long long data[16];
        if(mount(i?"mtd:user-config":"mtd:root0",roots[i],"jffs2",1039,0)) return -1;
        c->mounted|=1U<<i;
        c->files.roots[i]=open(roots[i],O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if(c->files.roots[i]<0||syscall(100,c->files.roots[i],data)||
           word((const unsigned char *)data)!=0x72b6||!(word((const unsigned char *)data+44)&1U)) return -1;
    }
    return 0;
}
static int preflight(void *opaque)
{
    struct action_context *c=opaque;unsigned int i;
    if(c->files.recovery!=-1||c->mounted!=3||read_status(c)||c->phase!=0||
       c->protected!=1||c->programs||c->erases||c->markers||c->failed) return -1;
    if(HEARTH_FILE_ACTION==2) {
        int result=hearth_posix_restore_preflight(&c->files);
        if(c->files.recovery>=0) { if(close(c->files.recovery)) result=-1;c->files.recovery=-1; }
        return result;
    }
    for(i=0;i<9;i++) {
        c->preflight_target=(int)i;
        if(hearth_posix_file_ops.preflight(&c->files,i)) return -1;
    }
    c->preflight_target=-1;return 0;
}
static int open_window(void *opaque)
{
    struct action_context *c=opaque;unsigned char token[72];unsigned int i;
    for(i=0;i<8;i++) token[i]=(unsigned char)"HFWOPEN1"[i];
    for(i=0;i<32;i++) { token[8+i]=hearth_capsule_plan_id[i];token[40+i]=hearth_expected_receipt[i]; }
    if(send_control(token,sizeof(token))||read_status(c)||c->phase!=1||c->protected!=1) return -1;
    return 0;
}
static int remount_rw(void *opaque,unsigned int i)
{
    struct action_context *c=opaque;unsigned long long data[16];
    if(mount(0,roots[i],0,1070,0)||syscall(100,c->files.roots[i],data)||
       word((const unsigned char *)data)!=0x72b6||(word((const unsigned char *)data+44)&1U)) return -1;
    return 0;
}
static void transact(void *opaque,struct hearth_install_result *result)
{
    struct action_context *c=opaque;
    if(HEARTH_FILE_ACTION==2) *result=hearth_posix_restore_files(&c->files);
    else *result=hearth_install_files(&hearth_posix_file_ops,&c->files,9,1);
}
static int verify_readonly(void *opaque,int replacement)
{
    struct action_context *c=opaque;unsigned int i;int result=-1;
    if(c->mounted||readonly_roots(c)) goto done;
    for(i=0;i<9;i++) {
        const struct hearth_file_change *change=&hearth_capsule_changes[i];
        struct hearth_snapshot_file observed;
        struct hearth_file_bytes expected=replacement?change->replacement:change->original;
        unsigned int mode=replacement?change->replacement_mode:change->original_mode;
        if(hearth_snapshot_file(c->files.roots,0,0,i,scratch,sizeof(scratch),&observed)||
           observed.existed!=(replacement?1U:(unsigned int)change->existed)||
           observed.mode!=mode||observed.size!=expected.size||
           (expected.size&&memcmp(scratch,expected.data,expected.size))) goto done;
    }
    result=0;
done:
    if(release_roots(c)) result=-1;
    if(unmount_root(c,1)) result=-1;
    if(unmount_root(c,0)) result=-1;
    if(read_status(c)||c->phase!=2||c->protected!=1||c->failed) result=-1;
    return result;
}
static const struct hfa_ops action_ops={preflight,open_window,remount_rw,transact,
    release_roots,unmount_root,seal,verify_readonly};
static void binding_frame(unsigned char *out,const char *magic)
{
    unsigned int i;for(i=0;i<8;i++) out[i]=(unsigned char)magic[i];
    for(i=0;i<32;i++) { out[8+i]=hearth_capsule_plan_id[i];out[40+i]=hearth_expected_receipt[i]; }
    put(out+72,HEARTH_FILE_ACTION);
}
static long transmit(long fd,const char *data,long size)
{ long n=write((int)fd,data,(size_t)size);return n<0?-errno:n; }
static unsigned int crc(const unsigned char *data,unsigned int length)
{
    unsigned int value=~0U,i,j;
    for(i=0;i<length;i++) { value^=data[i];for(j=0;j<8;j++) value=(value>>1)^((0U-(value&1U))&0xedb88320U); }
    return ~value;
}
static void capture_changed_preflight(struct action_context *c)
{
    unsigned int i,j,at=92;struct hearth_snapshot_file observed;
    if(c->mounted!=3) return;
    put(snapshot+84,0);put(snapshot+88,9);
    for(i=0;i<9;i++) {
        if(hearth_snapshot_file(c->files.roots,0,0,i,scratch,sizeof(scratch),&observed)) return;
        put(snapshot+at,i);put(snapshot+at+4,observed.existed);put(snapshot+at+8,observed.mode);
        put(snapshot+at+12,observed.owner);put(snapshot+at+16,observed.group);put(snapshot+at+20,observed.size);
        at+=24;
        for(j=0;j<observed.size;j++) snapshot[at++]=scratch[j];
    }
    binding_frame(snapshot,"HFW_SNP1");put(snapshot+76,at-84);put(snapshot+80,crc(snapshot+84,at-84));
    for(i=0;i<8;i++) snapshot[at++]=(unsigned char)"HFW_END1"[i];
    snapshot_size=at;
}
static int await_commit(void)
{
    unsigned char ready[76],commit[76],abort[76],input[256];unsigned int a=0,b=0,i;
    long started=monotonic(),last=-1;
    struct hearth_cached_transmit sending={0};
    binding_frame(ready,"HFW_RDY1");binding_frame(commit,"HFW_RUN1");binding_frame(abort,"HFW_STOP");
    for(;;) {
        long now=monotonic(),n;
        if(started<0||now<started||now-started>600) return 0;
        if(now!=last) {
            int sent=hearth_cached_transmit_step(&sending,tty,(const char *)ready,sizeof(ready),transmit);
            if(sent==HEARTH_TRANSMIT_DONE) last=now;
            else if(sent==HEARTH_TRANSMIT_ERROR) return 0;
        }
        n=read(tty,input,sizeof(input));
        if(n<0&&errno!=11&&errno!=4) return 0;
        for(i=0;n>0&&i<(unsigned long)n;i++) {
            a=input[i]==commit[a]?a+1:input[i]==commit[0];
            b=input[i]==abort[b]?b+1:input[i]==abort[0];
            if(a==sizeof(commit)) return 1;
            if(b==sizeof(abort)) return 0;
        }
        pause_short();
    }
}
int main(void)
{
    struct action_context c;struct hfa_result result;int initial=0,committed=0,n;
    unsigned int i,length,part=0;struct hearth_cached_transmit sending={0};
    memset(&c,0,sizeof(c));c.files.roots[0]=c.files.roots[1]=c.files.recovery=-1;c.preflight_target=-1;
    c.files.owner=0;c.files.group=0;c.files.count=9;c.files.changes=hearth_capsule_changes;
    for(i=0;i<32;i++) { c.files.plan_id[i]=hearth_capsule_plan_id[i];if(hearth_capsule_plan_id[i]!=hearth_expected_plan[i]) initial=1; }
    if(getuid()!=0||getgid()!=0||hearth_capsule_count!=9) initial=1;
    umask(077);
    for(;;) { tty=open("/dev/ttyGS0",O_RDWR|256|O_NONBLOCK|O_CLOEXEC);if(tty>=0) break;pause_short(); }
    if(!initial&&(read_status(&c)||c.phase!=0||c.protected!=1||readonly_roots(&c)||preflight(&c))) initial=2;
    /* If stock startup changed a selected file, preserve a fresh read-only
     * snapshot in this same RAM session. It never authorizes changing the old
     * compiled plan; a new reviewed capsule/image is still required. */
    if(initial==2) capture_changed_preflight(&c);
    if(!initial) committed=await_commit();
    if(committed) result=hfa_run(&action_ops,&c,HEARTH_FILE_ACTION==2);
    else result=hfa_cancel(&action_ops,&c);
    n=snprintf((char *)report+84,sizeof(report)-92,
        "{\"type\":\"file_action\",\"action\":%u,\"initial_error\":%d,\"preflight_target\":%d,"
        "\"commit_received\":%d,\"stage_error\":%d,\"window_opened\":%d,\"rw_attempted\":%u,"
        "\"transaction_called\":%d,\"error\":%d,\"rollback_error\":%d,\"journal_error\":%d,"
        "\"cleanup_error\":%d,\"attempted\":%u,\"restored\":%u,\"committed\":%d,"
        "\"release_error\":%d,\"unmount_errors\":%u,\"seal_error\":%d,\"verified\":%d,"
        "\"safe_to_restart\":%d,\"complete\":%d,\"phase\":%u,\"protected\":%u,"
        "\"program\":%u,\"erase\":%u,\"marker\":%u,\"failed\":%u,\"snapshot_available\":%u}\n",
        HEARTH_FILE_ACTION,initial,c.preflight_target,committed,result.stage_error,result.window_opened,
        result.rw_attempted,result.transaction_called,result.transaction.error,result.transaction.rollback_error,
        result.transaction.journal_error,result.transaction.cleanup_error,result.transaction.attempted,
        result.transaction.restored,result.transaction.committed,result.release_error,result.unmount_errors,
        result.seal_error,result.verified,result.safe_to_restart,result.complete,c.phase,c.protected,
        c.programs,c.erases,c.markers,c.failed,snapshot_size?1U:0U);
    if(n<=0||(unsigned int)n>=sizeof(report)-92) for(;;) pause_short();
    binding_frame(report,"HFW_RES1");put(report+76,(unsigned int)n);put(report+80,crc(report+84,(unsigned int)n));
    length=84+(unsigned int)n;
    for(i=0;i<8;i++) report[length++]=(unsigned char)"HFW_END1"[i];
    for(;;) {
        const unsigned char *bytes=snapshot_size&&!part?snapshot:report;
        unsigned int count=snapshot_size&&!part?snapshot_size:length;
        int status=hearth_cached_transmit_step(&sending,tty,(const char *)bytes,count,transmit);
        if(status==HEARTH_TRANSMIT_DONE) {
            if(snapshot_size&&!part) part=1;
            else { long delay[2]={1,0};part=0;nanosleep(delay,0); }
        }
        else pause_short();
    }
}
