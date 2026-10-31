/* Original synthetic kernel-interface fixture. Runs the actual I/O adapter
 * with fake hardware and heap-freeing erase callbacks, never any device. */
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
struct mtd_info;
struct erase_info {
    struct mtd_info *mtd;unsigned long long addr,len,fail_addr;
    unsigned long priv;unsigned int state;void (*callback)(struct erase_info *);
};
struct mtd_info { unsigned int flags;unsigned long long test_offset; };
struct omap_nand_info { struct mtd_info mtd;int gpmc_cs; };
struct mtd_oob_ops { unsigned int mode;size_t len,retlen,ooblen,oobretlen,ooboffs;unsigned char *datbuf,*oobbuf; };
#define DEFINE_MUTEX(name) pthread_mutex_t name=PTHREAD_MUTEX_INITIALIZER
#define mutex_lock(p) ((void)pthread_mutex_lock(p))
#define mutex_unlock(p) ((void)pthread_mutex_unlock(p))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define MTD_WRITEABLE 0x400
#define MTD_ERASE_DONE 4
#define MTD_ERASE_FAILED 8
#define MTD_OOB_AUTO 1
#define GPMC_CONFIG_WP 1
static int protected=1,fail_on,fail_off,short_write,io_error,writes,markers,reads,callbacks;
static struct omap_nand_info info;
static struct mtd_info children[2];
static int hearth_wp_is_asserted(struct mtd_info *mtd) { assert(mtd==&info.mtd);return protected; }
static int gpmc_cs_configure(int cs,int command,int value)
{
    assert(cs==0&&command==GPMC_CONFIG_WP);
    if((value&&fail_on)||(!value&&fail_off)) return -EIO;
    protected=value;return 0;
}
static void mtd_erase_callback(struct erase_info *erase)
{
    erase->addr-=erase->mtd->test_offset;
    if(erase->callback) erase->callback(erase);
}
#include "../firmware/file_writer/io.h"
static int saved_write(struct mtd_info *mtd,loff_t at,size_t length,size_t *done,const u_char *data)
{
    assert(mtd==&info.mtd&&at==12*1048576&&data&&protected==0);writes++;
    *done=io_error?0:length-(short_write?1:0);return io_error?-EIO:0;
}
static int saved_erase(struct mtd_info *mtd,struct erase_info *erase)
{
    assert(mtd==&info.mtd&&erase->addr==12*1048576&&protected==0);
    erase->state=MTD_ERASE_DONE;mtd_erase_callback(erase);return 0;
}
static int saved_oob(struct mtd_info *mtd,loff_t at,struct mtd_oob_ops *ops)
{
    assert(mtd==&info.mtd&&at==12*1048576&&protected==0);markers++;
    ops->retlen=0;ops->oobretlen=ops->ooblen;return 0;
}
static int saved_read(struct mtd_info *mtd,loff_t at,size_t length,size_t *done,u_char *data)
{
    assert(mtd==&info.mtd&&at>=0&&protected==1);reads++;*done=length;
    if(length) data[0]=42;return 0;
}
static int saved_read_oob(struct mtd_info *mtd,loff_t at,struct mtd_oob_ops *ops)
{ assert(mtd==&info.mtd&&at>=0&&protected);reads++;ops->retlen=ops->len;return 0; }
static int saved_bad(struct mtd_info *mtd,loff_t at)
{ assert(mtd==&info.mtd&&at>=0&&protected);reads++;return 0; }
static void saved_sync(struct mtd_info *mtd) { assert(mtd==&info.mtd&&protected); }
static void completed(struct erase_info *erase)
{
    size_t done=0;u_char byte=0;
    assert(erase->mtd==&children[0]&&erase->addr==0&&erase->state==MTD_ERASE_DONE);
    assert(protected&&pthread_mutex_trylock(&hfw_mutex)==0);
    pthread_mutex_unlock(&hfw_mutex);
    assert(hfw_read(&info.mtd,12*1048576,1,&done,&byte)==0&&done==1&&byte==42);
    callbacks++;free(erase);
}
int main(int argc,char **argv)
{
    int scenario,result;size_t done=0;u_char data[2048]={0};
    assert(argc==2);scenario=atoi(argv[1]);
    hfw_master=&info.mtd;hfw_parts[0]=&children[0];hfw_parts[1]=&children[1];
    children[0].test_offset=12*1048576;children[0].flags=children[1].flags=MTD_WRITEABLE;
    hfw_saved_write=saved_write;hfw_saved_erase=saved_erase;hfw_saved_oob=saved_oob;
    hfw_saved_read=saved_read;hfw_saved_read_oob=saved_read_oob;hfw_saved_bad=saved_bad;hfw_saved_sync=saved_sync;
    hf_init(&hfw_window,hearth_expected_plan,hearth_expected_receipt);
    assert(hf_open(&hfw_window,hearth_expected_plan,hearth_expected_receipt,1)==0);
    if(scenario==2) short_write=1;
    if(scenario==3) io_error=1;
    if(scenario==4) fail_off=1;
    if(scenario==5||scenario==6) fail_on=1;
    if(scenario==1||scenario==6) {
        struct erase_info *erase=calloc(1,sizeof(*erase));assert(erase);
        erase->mtd=&children[0];erase->addr=12*1048576;erase->len=131072;
        erase->fail_addr=~0ULL;erase->callback=completed;
        result=hfw_erase(&info.mtd,erase);
        if(scenario==1) assert(result==0&&callbacks==1&&reads==1);
        else { assert(result!=0&&!callbacks&&erase->state==MTD_ERASE_FAILED);free(erase); }
    } else if(scenario>=11) {
        struct mtd_oob_ops ops;u_char marker[8]={0x85,0x19,0x03,0x20,8,0,0,0};
        memset(&ops,0,sizeof(ops));ops.mode=MTD_OOB_AUTO;ops.ooblen=8;ops.oobbuf=marker;
        if(scenario==12) ops.mode=2;
        if(scenario==13) marker[0]^=1;
        if(scenario==14) { ops.datbuf=data;ops.len=2048; }
        result=hfw_oob(&info.mtd,12*1048576,&ops);
        assert((result==0)==(scenario==11));assert(markers==(scenario==11));
    } else if(scenario==7) {
        assert(hfw_write(&info.mtd,66*1048576,2048,&done,data)!=0&&!writes);
    } else if(scenario==8) {
        hfw_window.phase=HF_SEALED;
        assert(hfw_write(&info.mtd,12*1048576,2048,&done,data)!=0&&!writes);
    } else if(scenario==9) {
        assert(hfw_write(&children[0],12*1048576,2048,&done,data)!=0&&!writes);
    } else if(scenario==10) {
        protected=0;
        assert(hfw_read(&info.mtd,12*1048576,1,&done,data)!=0&&!done&&!reads);
        assert(protected&&hfw_window.phase==HF_SEALED);
    } else {
        result=hfw_write(&info.mtd,12*1048576,2048,&done,data);
        assert((result==0)==(scenario==0));
        if(scenario==0) assert(done==2048&&writes==1);
        if(scenario==4) assert(!writes);
    }
    if(scenario==5||scenario==6) assert(!protected&&hfw_window.phase==HF_SEALED);
    else assert(protected);
    if(hfw_window.phase==HF_SEALED) assert(!children[0].flags&&!children[1].flags);
    if(scenario==0) {
        struct mtd_oob_ops ops;memset(&ops,0,sizeof(ops));
        assert(hfw_read_oob(&info.mtd,0,&ops)==0&&hfw_bad(&info.mtd,0)==0);hfw_sync(&info.mtd);
    }
    return 0;
}
