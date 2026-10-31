/* Original filesystem write-window registration, GPL-2.0-or-later. */
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include "io.h"
/* Only these two named views are registered. All other flash regions remain
 * inaccessible to filesystems, and master guards also enforce these bounds. */
static struct mtd_partition hfw_partitions[]={
    { .name="root0", .offset=12ULL*1048576, .size=46ULL*1048576 },
    { .name="user-config", .offset=116ULL*1048576, .size=8ULL*1048576 }
};
static int hfw_shape(struct mtd_info *mtd)
{
    struct nand_chip *chip=mtd->priv;unsigned int i;
    if(mtd!=hfw_master||mtd->size!=268435456ULL||mtd->erasesize!=131072||
       mtd->writesize!=2048||mtd->oobsize!=64||mtd->flags||
       !(chip->options&NAND_ROM)||!(chip->options&NAND_SKIP_BBTSCAN)||
       chip->options&(NAND_USE_FLASH_BBT|BBT_AUTO_REFRESH)||chip->bbt||
       !(chip->options&NAND_BUSWIDTH_16)||chip->badblockpos||chip->numchips!=1||
       chip->ecc.mode!=NAND_ECC_HW||chip->ecc.size!=2048||chip->ecc.steps!=1||
       chip->ecc.bytes!=28||chip->ecc.total!=28||!chip->ecc.layout||
       chip->ecc.layout->eccbytes!=28||chip->ecc.layout->oobfree[0].offset!=2||
       chip->ecc.layout->oobfree[0].length!=34||chip->block_markbad!=hearth_deny_markbad||
       mtd->block_markbad!=hearth_deny_markbad||mtd->panic_write!=hearth_deny_write||
       mtd->writev!=hearth_deny_writev||mtd->unlock!=hearth_deny_lock||
       mtd->lock!=hearth_deny_lock||mtd->write_user_prot_reg!=hearth_deny_prot_write||
       mtd->lock_user_prot_reg!=hearth_deny_prot_lock||
       mtd->write!=hfw_write||mtd->erase!=hfw_erase||mtd->write_oob!=hfw_oob) return -EINVAL;
    for(i=0;i<28;i++) if(chip->ecc.layout->eccpos[i]!=36+i) return -EINVAL;
    return 0;
}
static ssize_t hfw_show(struct device *dev,struct device_attribute *attr,char *buffer)
{
    int length;mutex_lock(&hfw_mutex);
    length=scnprintf(buffer,PAGE_SIZE,"phase=%u protected=%u program=%u erase=%u marker=%u failed=%u\n",
        hfw_window.phase,hearth_wp_is_asserted(hfw_master),hfw_window.attempted[0],
        hfw_window.attempted[1],hfw_window.attempted[2],hfw_window.failed);
    mutex_unlock(&hfw_mutex);return length;
}
static ssize_t hfw_store(struct device *dev,struct device_attribute *attr,const char *buffer,size_t length)
{
    struct hfw_request r;int result=-EINVAL;
    memset(&r,0,sizeof(r));r.mtd=hfw_master;
    mutex_lock(&hfw_mutex);
    if(length==72&&!memcmp(buffer,"HFWOPEN1",8)&&!hfw_shape(hfw_master)) {
        result=hf_open(&hfw_window,(const unsigned char *)buffer+8,
                       (const unsigned char *)buffer+40,hearth_wp_is_asserted(hfw_master));
        if(!result) { hfw_parts[0]->flags|=MTD_WRITEABLE;hfw_parts[1]->flags|=MTD_WRITEABLE; }
    } else if(length==8&&!memcmp(buffer,"HFWCLOSE",8)) {
        hfw_flags_readonly();result=hf_close(&hfw_window,&hfw_io,&r);
    }
    mutex_unlock(&hfw_mutex);return result ? -EIO : length;
}
static DEVICE_ATTR(hearth_file_control,0200,NULL,hfw_store);
static DEVICE_ATTR(hearth_file_status,0400,hfw_show,NULL);
static int hfw_save(struct mtd_info *mtd)
{
    if(hfw_master) return -EBUSY;
    hfw_master=mtd;hfw_saved_write=mtd->write;hfw_saved_erase=mtd->erase;
    hfw_saved_oob=mtd->write_oob;hfw_saved_read=mtd->read;
    hfw_saved_read_oob=mtd->read_oob;hfw_saved_bad=mtd->block_isbad;hfw_saved_sync=mtd->sync;
    hf_init(&hfw_window,hearth_expected_plan,hearth_expected_receipt);
    return 0;
}
static int hfw_install(struct mtd_info *mtd)
{
    if(!hfw_saved_write||!hfw_saved_erase||!hfw_saved_oob||!hfw_saved_read||
       !hfw_saved_read_oob||!hfw_saved_bad||!hfw_saved_sync) return -EINVAL;
    mtd->write=hfw_write;mtd->erase=hfw_erase;mtd->write_oob=hfw_oob;
    mtd->read=hfw_read;mtd->read_oob=hfw_read_oob;mtd->block_isbad=hfw_bad;mtd->sync=hfw_sync;
    return hfw_shape(mtd);
}
static int hfw_register(struct device *dev)
{
    int result;unsigned int i;
    hfw_parts[0]=get_mtd_device_nm("root0");hfw_parts[1]=get_mtd_device_nm("user-config");
    for(i=0;i<2;i++) {
        if(IS_ERR(hfw_parts[i])) { hfw_parts[i]=NULL;result=-ENODEV;goto fail; }
        if(hfw_parts[i]->flags||hfw_parts[i]->size!=(i?8ULL:46ULL)*1048576||
           hfw_parts[i]->index!=i||hfw_parts[i]->erasesize!=131072||
           hfw_parts[i]->writesize!=2048||hfw_parts[i]->oobsize!=64) { result=-EINVAL;goto fail; }
    }
    result=device_create_file(dev,&dev_attr_hearth_file_status);if(result) goto fail;
    result=device_create_file(dev,&dev_attr_hearth_file_control);
    if(!result) return 0;
    device_remove_file(dev,&dev_attr_hearth_file_status);
fail:
    for(i=0;i<2;i++) {
        if(hfw_parts[i]&&!IS_ERR(hfw_parts[i])) put_mtd_device(hfw_parts[i]);
        hfw_parts[i]=NULL;
    }
    return result;
}
static void hfw_remove(struct device *dev)
{
    struct hfw_request r;unsigned int i;
    memset(&r,0,sizeof(r));r.mtd=hfw_master;mutex_lock(&hfw_mutex);
    hfw_flags_readonly();hf_close(&hfw_window,&hfw_io,&r);mutex_unlock(&hfw_mutex);
    device_remove_file(dev,&dev_attr_hearth_file_control);device_remove_file(dev,&dev_attr_hearth_file_status);
    for(i=0;i<2;i++) if(hfw_parts[i]) { put_mtd_device(hfw_parts[i]);hfw_parts[i]=NULL; }
}
