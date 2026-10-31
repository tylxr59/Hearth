/* Original host-only sysfs fixture. No firmware/driver or MMIO is executed. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#define MTD_NANDFLASH 4
#define S_IRUSR 0400
/* Distinct fixture bits; the actual kernel build uses its pinned own headers. */
#define NAND_BUSWIDTH_16 1
#define NAND_BBT_SCAN2NDPAGE 2
#define NAND_BBT_SCANLASTPAGE 4
#define NAND_BBT_SCANBYTE1AND6 8
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
struct device { int unused; };
struct device_attribute {
    unsigned int mode;
    ssize_t (*show)(struct device *,struct device_attribute *,char *);
    void *store;
};
#define DEVICE_ATTR(name,mode,show,store) struct device_attribute dev_attr_##name={mode,show,store}
struct nand_ecclayout { unsigned int eccbytes,eccpos[64]; struct { unsigned int offset,length; } oobfree[1]; };
struct nand_chip {
    unsigned int options,badblockpos;
    struct { unsigned int offs,len,options; } *badblock_pattern;
    struct { unsigned int mode,size,bytes,steps,total; struct nand_ecclayout *layout; } ecc;
};
struct mtd_info {
    struct device dev;
    unsigned int flags,type,erasesize,writesize,oobsize;
    uint64_t size;
    const char *name;
    void *priv;
};
static int protected=1;
static int hearth_wp_is_asserted(struct mtd_info *mtd) { (void)mtd;return protected; }
static int scnprintf(char *buf,size_t size,const char *format,...)
{
    va_list args;va_start(args,format);
    int n=vsnprintf(buf,size,format,args);va_end(args);
    assert(n>=0);
    return size ? (n<(int)size?n:(int)size-1):0;
}
#include "../firmware/nand_contract/contract.h"
static ssize_t call(struct mtd_info *mtd,char *data)
{
    ssize_t n=hearth_contract_show(&mtd->dev,&dev_attr_hearth_contract,data+16);
    for (int i=0;i<16;i++) assert((unsigned char)data[i]==0xa5 && (unsigned char)data[1040+i]==0xa5);
    assert(n<=1023);
    return n;
}
int main(void)
{
    struct nand_ecclayout layout={.eccbytes=28,.oobfree={{2,34}}};
    struct nand_chip chip={.options=NAND_BUSWIDTH_16|NAND_BBT_SCAN2NDPAGE,.badblockpos=0,
        .ecc={2,2048,28,1,28,&layout}};
    struct mtd_info mtd={.flags=0,.type=MTD_NANDFLASH,.size=268435456,.erasesize=131072,
        .writesize=2048,.oobsize=64,.name="omap2-nand.0",.priv=&chip};
    char data[1056]; memset(data,0xa5,sizeof(data));
    for (int i=0;i<28;i++)layout.eccpos[i]=36+i;
    assert(dev_attr_hearth_contract.mode==0400 && dev_attr_hearth_contract.store==NULL);
    ssize_t n=call(&mtd,data);assert(n>0 && n==(ssize_t)strlen(data+16));
    puts("HEARTH_NAND_CONTRACT_V1");fwrite(data+16,1,n,stdout);puts("END_HEARTH_NAND_CONTRACT");
    memset(data,0xa5,sizeof(data));
    protected=0;assert(call(&mtd,data)==-EROFS);protected=1;
    mtd.flags=1;assert(call(&mtd,data)==-EROFS);mtd.flags=0;
    mtd.type=0;assert(call(&mtd,data)==-EROFS);mtd.type=MTD_NANDFLASH;
    chip.ecc.layout=NULL;assert(call(&mtd,data)==-EINVAL);chip.ecc.layout=&layout;
    layout.eccbytes=65;assert(call(&mtd,data)==-EINVAL);
    for (int i=16;i<1040;i++)assert((unsigned char)data[i]==0xa5);
    layout.eccbytes=64;
    for (int i=0;i<64;i++)layout.eccpos[i]=UINT32_MAX;
    assert(call(&mtd,data)>0);
    return 0;
}
