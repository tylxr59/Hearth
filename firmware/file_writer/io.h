/* Original bounded JFFS2 NAND adapter, GPL-2.0-or-later with the Linux driver.
 * Only a separately reviewed private writer profile may include this file.
 * No MTD char/block interface is enabled. Master flags stay read-only forever.
 */
#include "binding.h"
#include "core.c"
static DEFINE_MUTEX(hfw_mutex);
static struct hf_window hfw_window;
static struct mtd_info *hfw_master,*hfw_parts[2];
static int (*hfw_saved_write)(struct mtd_info *,loff_t,size_t,size_t *,const u_char *);
static int (*hfw_saved_erase)(struct mtd_info *,struct erase_info *);
static int (*hfw_saved_oob)(struct mtd_info *,loff_t,struct mtd_oob_ops *);
static int (*hfw_saved_read)(struct mtd_info *,loff_t,size_t,size_t *,u_char *);
static int (*hfw_saved_read_oob)(struct mtd_info *,loff_t,struct mtd_oob_ops *);
static int (*hfw_saved_bad)(struct mtd_info *,loff_t);
static void (*hfw_saved_sync)(struct mtd_info *);
struct hfw_request {
    struct mtd_info *mtd;loff_t offset;size_t length,*done;
    const u_char *data;struct mtd_oob_ops *oob;struct erase_info *erase;
    int erase_completed;
};
static int hfw_protected(void *opaque)
{ return hearth_wp_is_asserted(((struct hfw_request *)opaque)->mtd); }
static int hfw_protect(void *opaque,int enabled)
{
    struct hfw_request *r=opaque;
    struct omap_nand_info *info=container_of(r->mtd,struct omap_nand_info,mtd);
    int result=gpmc_cs_configure(info->gpmc_cs,GPMC_CONFIG_WP,enabled?1:0);
    return result||hearth_wp_is_asserted(r->mtd)!=enabled ? -EIO : 0;
}
static void hfw_erase_deferred(struct erase_info *proxy)
{
    struct hfw_request *r=(void *)proxy->priv;
    r->erase_completed=1;
}
static int hfw_perform(void *opaque,enum hf_operation operation,void *request)
{
    struct hfw_request *r=opaque;
    int result;
    (void)request;
    if(operation==HF_PROGRAM) {
        result=hfw_saved_write(r->mtd,r->offset,r->length,r->done,r->data);
        return result||*r->done!=r->length ? -EIO : 0;
    }
    if(operation==HF_CLEANMARKER) {
        result=hfw_saved_oob(r->mtd,r->offset,r->oob);
        return result||r->oob->retlen||r->oob->oobretlen!=8 ? -EIO : 0;
    }
    if(operation==HF_ERASE) {
        /* JFFS2's completion callback frees its erase_info. Defer it using a
         * separate proxy so final WP failure can still return an ordinary
         * error without callers touching or freeing an already-freed request.
         * A master mtd on the proxy prevents partition offset conversion until
         * the real callback is delivered exactly once after protection. */
        struct erase_info proxy=*r->erase;
        proxy.mtd=r->mtd;proxy.callback=hfw_erase_deferred;
        proxy.priv=(unsigned long)r;r->erase_completed=0;
        result=hfw_saved_erase(r->mtd,&proxy);
        r->erase->fail_addr=proxy.fail_addr;
        return result||!r->erase_completed||proxy.state!=MTD_ERASE_DONE ? -EIO : 0;
    }
    return -EINVAL;
}
static const struct hf_io hfw_io={hfw_protected,hfw_protect,hfw_perform};
static void hfw_flags_readonly(void)
{
    unsigned int i;for(i=0;i<2;i++) if(hfw_parts[i]) hfw_parts[i]->flags&=~MTD_WRITEABLE;
}
static int hfw_read_ready(struct mtd_info *mtd)
{
    struct hfw_request r;
    if(mtd!=hfw_master) return -ENODEV;
    if(hearth_wp_is_asserted(mtd)) return 0;
    memset(&r,0,sizeof(r));r.mtd=mtd;
    hfw_flags_readonly();hf_close(&hfw_window,&hfw_io,&r);
    return -EIO;
}
static int hfw_read(struct mtd_info *mtd,loff_t at,size_t length,size_t *done,u_char *data)
{
    int result;mutex_lock(&hfw_mutex);
    result=hfw_read_ready(mtd);
    if(!result) result=hfw_saved_read(mtd,at,length,done,data);
    else if(done) *done=0;
    mutex_unlock(&hfw_mutex);return result;
}
static int hfw_read_oob(struct mtd_info *mtd,loff_t at,struct mtd_oob_ops *ops)
{
    int result;mutex_lock(&hfw_mutex);result=hfw_read_ready(mtd);
    if(!result) result=hfw_saved_read_oob(mtd,at,ops);
    else if(ops) ops->retlen=ops->oobretlen=0;
    mutex_unlock(&hfw_mutex);return result;
}
static int hfw_bad(struct mtd_info *mtd,loff_t at)
{
    int result;mutex_lock(&hfw_mutex);result=hfw_read_ready(mtd);
    if(!result) result=hfw_saved_bad(mtd,at);
    mutex_unlock(&hfw_mutex);return result;
}
static void hfw_sync(struct mtd_info *mtd)
{
    mutex_lock(&hfw_mutex);
    if(!hfw_read_ready(mtd)) hfw_saved_sync(mtd);
    mutex_unlock(&hfw_mutex);
}
static int hfw_run(struct hfw_request *r,enum hf_operation operation,unsigned int length)
{
    int result;
    if(r->mtd!=hfw_master) return -ENODEV;
    result=hf_run(&hfw_window,&hfw_io,r,operation,(unsigned long long)r->offset,length,r);
    if(hfw_window.phase==HF_SEALED) hfw_flags_readonly();
    return result ? -EIO : 0;
}
static int hfw_write(struct mtd_info *mtd,loff_t at,size_t length,size_t *done,const u_char *data)
{
    struct hfw_request r;int result;
    if(!done||!data) return -EINVAL;
    *done=0;memset(&r,0,sizeof(r));r.mtd=mtd;r.offset=at;r.length=length;r.done=done;r.data=data;
    mutex_lock(&hfw_mutex);result=hfw_run(&r,HF_PROGRAM,(unsigned int)length);
    mutex_unlock(&hfw_mutex);return result;
}
static int hfw_erase(struct mtd_info *mtd,struct erase_info *erase)
{
    struct hfw_request r;int result;
    if(!erase||erase->len>0xffffffffULL) return -EINVAL;
    memset(&r,0,sizeof(r));r.mtd=mtd;r.offset=erase->addr;r.erase=erase;
    mutex_lock(&hfw_mutex);result=hfw_run(&r,HF_ERASE,(unsigned int)erase->len);
    if(result) erase->state=MTD_ERASE_FAILED;
    else erase->state=MTD_ERASE_DONE;
    mutex_unlock(&hfw_mutex);
    /* Never call filesystem code while holding the device mutex. It may
     * acquire locks held by another filesystem thread waiting for this mutex.
     * The callback may free erase; there is no access after this call. */
    if(!result) mtd_erase_callback(erase);
    return result;
}
static int hfw_oob(struct mtd_info *mtd,loff_t at,struct mtd_oob_ops *ops)
{
    static const unsigned char marker[8]={0x85,0x19,0x03,0x20,8,0,0,0};
    struct hfw_request r;int result;
    if(!ops) return -EINVAL;
    ops->retlen=ops->oobretlen=0;
    if(ops->mode!=MTD_OOB_AUTO||ops->datbuf||ops->len||ops->ooboffs||
       ops->ooblen!=8||!ops->oobbuf||memcmp(ops->oobbuf,marker,8)) return -EROFS;
    memset(&r,0,sizeof(r));r.mtd=mtd;r.offset=at;r.oob=ops;
    mutex_lock(&hfw_mutex);result=hfw_run(&r,HF_CLEANMARKER,8);
    mutex_unlock(&hfw_mutex);return result;
}
