/* Original fixed-plan file action, MIT. Runs only inside a reviewed private RAM
 * image. No shell, arbitrary paths, network, native app execution or raw MTD API.
 * Starts read-only and waits for one exact owner-timed commit/abort frame. */
#include "../file_writer/abi.h"
#include "../file_writer/lifecycle.h"
#include "data.h"
#include "../network_update/stream.h"
#include "../file_reencode/reencode.h"
#include "../settings_compat_probe/transmit.h"
#include "plan.h"
#define hearth_capsule_plan_id hn_plan_id
#define hearth_capsule_changes hn_changes
#define hearth_capsule_count 4
#include "binding.h"
#ifndef HEARTH_CAPSULE_ARCHIVE_LAYOUT
#define HEARTH_CAPSULE_ARCHIVE_LAYOUT 1
#endif
#ifndef HEARTH_FILE_ACTION
#error "Explicit install=1 or restore=2 build required"
#endif
#if HEARTH_FILE_ACTION != 1 && HEARTH_FILE_ACTION != 2
#error "Unsupported file action"
#endif
static const char *const roots[2]={"/native","/archive"};
static const char control[]="/sys/bus/platform/devices/omap2-nand.0/hearth_file_control";
static const char status_path[]="/sys/bus/platform/devices/omap2-nand.0/hearth_file_status";
static unsigned char report[8192];
static int tty=-1;
struct action_context {
    struct hearth_posix_context files;
    unsigned int mounted;
    int preflight_target;
    int encoding_verified;
    unsigned int diagnostic;
    int snapshot_target;
    int settings_state;
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
        c->diagnostic=10+i;
        if(mount("mtd:root0",roots[i],"jffs2",1039,0)) return -1;
        c->mounted|=1U<<i;
        c->diagnostic=20+i;
        c->files.roots[i]=open(roots[i],O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if(c->files.roots[i]<0||syscall(100,c->files.roots[i],data)||
           word((const unsigned char *)data)!=0x72b6||!(word((const unsigned char *)data+44)&1U)) return -1;
    }
    return 0;
}
static int preflight(void *opaque)
{
    struct action_context *c=opaque;unsigned int i;
    c->diagnostic=40;
    if(hn_memory_guard()||hn_space_guard(c->files.roots[0],HEARTH_FILE_ACTION==2)) return -1;
    if(c->files.recovery!=-1||c->mounted!=3||read_status(c)||c->phase!=0||
       c->protected!=1||c->programs||c->erases||c->markers||c->failed) return -1;
    if(HEARTH_FILE_ACTION!=1) {
        int result=hearth_posix_restore_preflight(&c->files);
        c->diagnostic=result?50:0;
        if(c->files.recovery>=0) { if(close(c->files.recovery)) result=-1;c->files.recovery=-1; }
        return result;
    }
    for(i=0;i<4;i++) {
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
    else *result=hearth_install_files(&hearth_posix_file_ops ,&c->files,4,1);
}
static int verify_readonly(void *opaque,int replacement)
{
    struct action_context *c=opaque;int result=-1;
    if(c->mounted||readonly_roots(c)) goto done;
    if(hn_exact_readback(&c->files,replacement)) goto done;
    result=0;
done:
    if(release_roots(c)) result=-1;
    if(unmount_root(c,1)) result=-1;
    if(unmount_root(c,0)) result=-1;
    if(read_status(c)||c->phase!=2||c->protected!=1||c->failed) result=-1;
    c->encoding_verified=result==0;
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
static int await_commit(void)
{
    unsigned char ready[76],commit[76],abort[76],input[256],info[512];unsigned int a=0,b=0,i,info_size=0,part=0;
    long started=monotonic(),last=-1;
    struct hearth_cached_transmit sending={0};
    binding_frame(ready,"HFW_RDY1");binding_frame(commit,"HFW_RUN1");binding_frame(abort,"HFW_STOP");
    {
        int length=snprintf((char *)info+84,sizeof(info)-92,
            "{\"targets\":4,\"originals_verified\":4,\"memory_free\":%u,\"space_available\":%u,\"space_required\":%u}\n",
            hn_memory_free,hn_space_available,hn_space_required);
        if(length<=0||(unsigned int)length>=sizeof(info)-92) return 0;
        binding_frame(info,"HFW_INF1");put(info+76,(unsigned int)length);put(info+80,crc(info+84,(unsigned int)length));
        info_size=84+(unsigned int)length;for(i=0;i<8;i++) info[info_size++]=(unsigned char)"HFW_END1"[i];
    }
    for(;;) {
        long now=monotonic(),n;
        if(started<0||now<started||now-started>600) return 0;
        if(now!=last) {
            const unsigned char *bytes=info_size&&!part?info:ready;
            unsigned int count=info_size&&!part?info_size:sizeof(ready);
            int sent=hearth_cached_transmit_step(&sending,tty,(const char *)bytes,count,transmit);
            if(sent==HEARTH_TRANSMIT_DONE) {
                if(info_size&&!part) part=1;
                else { part=0;last=now; }
            }
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
    unsigned int i,length;struct hearth_cached_transmit sending={0};
    memset(&c,0,sizeof(c));c.files.roots[0]=c.files.roots[1]=c.files.recovery=-1;c.preflight_target=-1;
    c.files.owner=0;c.files.group=0;c.files.count=4;c.files.changes=hearth_capsule_changes;c.snapshot_target=-1;c.settings_state=5;
    c.files.archive_layout=HEARTH_CAPSULE_ARCHIVE_LAYOUT;
    for(i=0;i<32;i++) { c.files.plan_id[i]=hearth_capsule_plan_id[i];if(hearth_capsule_plan_id[i]!=hearth_expected_plan[i]) initial=1; }
    if(getuid()!=0||getgid()!=0||hearth_capsule_count!=4) initial=1;
    umask(077);
    for(;;) { tty=open("/dev/ttyGS0",O_RDWR|256|O_NONBLOCK|O_CLOEXEC);if(tty>=0) break;pause_short(); }
    c.diagnostic=1;
    if(!initial) {
        int fd=open("/originals",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if(fd<0||hn_data_load(fd)) { initial=1;c.diagnostic=hn_data_diagnostic; }
        if(fd>=0&&close(fd)) initial=1;
    }
    if(!initial&&(read_status(&c)||c.phase!=0||c.protected!=1||readonly_roots(&c)||preflight(&c))) initial=2;
    if(!initial) committed=await_commit();
    if(committed) result=hfa_run(&action_ops,&c,HEARTH_FILE_ACTION!=1);
    else result=hfa_cancel(&action_ops,&c);
    n=snprintf((char *)report+84,sizeof(report)-92,
        "{\"type\":\"file_action\",\"action\":%u,\"initial_error\":%d,\"preflight_target\":%d,"
        "\"commit_received\":%d,\"stage_error\":%d,\"window_opened\":%d,\"rw_attempted\":%u,"
        "\"transaction_called\":%d,\"error\":%d,\"rollback_error\":%d,\"journal_error\":%d,"
        "\"cleanup_error\":%d,\"attempted\":%u,\"restored\":%u,\"committed\":%d,"
        "\"release_error\":%d,\"unmount_errors\":%u,\"seal_error\":%d,\"verified\":%d,"
        "\"safe_to_restart\":%d,\"complete\":%d,\"phase\":%u,\"protected\":%u,"
        "\"program\":%u,\"erase\":%u,\"marker\":%u,\"failed\":%u,\"snapshot_available\":%u,\"encoding_verified\":%d,\"diagnostic\":%u,\"snapshot_target\":%d,\"settings_state\":%d}\n",
        HEARTH_FILE_ACTION,initial,c.preflight_target,committed,result.stage_error,result.window_opened,
        result.rw_attempted,result.transaction_called,result.transaction.error,result.transaction.rollback_error,
        result.transaction.journal_error,result.transaction.cleanup_error,result.transaction.attempted,
        result.transaction.restored,result.transaction.committed,result.release_error,result.unmount_errors,
        result.seal_error,result.verified,result.safe_to_restart,result.complete,c.phase,c.protected,
        c.programs,c.erases,c.markers,c.failed,0U,c.encoding_verified,c.diagnostic,c.snapshot_target,c.settings_state);
    if(n<=0||(unsigned int)n>=sizeof(report)-92) for(;;) pause_short();
    binding_frame(report,"HFW_RES1");put(report+76,(unsigned int)n);put(report+80,crc(report+84,(unsigned int)n));
    length=84+(unsigned int)n;
    for(i=0;i<8;i++) report[length++]=(unsigned char)"HFW_END1"[i];
    for(;;) {
        int status=hearth_cached_transmit_step(&sending,tty,(const char *)report,length,transmit);
        if(status==HEARTH_TRANSMIT_DONE) { long delay[2]={1,0};nanosleep(delay,0); }
        else pause_short();
    }
}
