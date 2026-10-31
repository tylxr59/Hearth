/* Host-only synthetic sysfs/NAND guard harness, GPL-2.0-or-later. No USB or NAND. */
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>

struct file { int unused; };
struct kobject { int unused; };
struct device { struct kobject kobj; void *data; };
struct attribute { const char *name; int mode; };
struct bin_attribute {
    struct attribute attr;
    size_t size;
    ssize_t (*read)(struct file *, struct kobject *, struct bin_attribute *, char *, loff_t, size_t);
    void *write;
};
struct nand_ecclayout { unsigned int eccbytes,eccpos[64]; struct { unsigned int offset,length; } oobfree[1]; };
struct nand_chip { unsigned int options,badblockpos; struct { int mode; unsigned int size,bytes,steps,total; struct nand_ecclayout *layout; } ecc; };
struct mtd_oob_ops {
    unsigned int mode;
    size_t len, ooblen, retlen, oobretlen;
    unsigned char *datbuf, *oobbuf;
};
struct mtd_info {
    struct device dev;
    void *priv;
    unsigned long long size;
    unsigned int erasesize, writesize, oobsize, flags;
    int (*read_oob)(struct mtd_info *, loff_t, struct mtd_oob_ops *);
};
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define NAND_ECC_SOFT 1
#define NAND_ECC_HW 2
#define MTD_OOB_PLACE 0
#define NAND_BUSWIDTH_16 2
static int wp = 1, reads, creates, raw_result, short_read;
static loff_t last_offset;
static void *dev_get_drvdata(struct device *dev) { return dev->data; }
static int hearth_wp_is_asserted(struct mtd_info *mtd) { return wp; }
static int sysfs_create_bin_file(struct kobject *obj, struct bin_attribute *attr)
{
    assert(attr->attr.mode == 0400 && attr->write == NULL);
    creates++;
    return 0;
}
static int raw_read(struct mtd_info *mtd, loff_t off, struct mtd_oob_ops *ops)
{
    assert(ops->mode == MTD_OOB_PLACE);
    assert(ops->len == 2048 && ops->ooblen == 64);
    assert(ops->oobbuf == ops->datbuf + 2048);
    reads++;
    last_offset = off;
    memset(ops->datbuf, 0x11, 2048);
    memset(ops->oobbuf, 0x22, 64);
    ops->retlen = short_read ? 1 : 2048;
    ops->oobretlen = 64;
    return raw_result;
}
#include "sample.h"
#include "protocol.h"

int main(void)
{
    struct nand_ecclayout layout={.eccbytes=28,.oobfree={{2,34}}};
    struct nand_chip chip = { .options=NAND_BUSWIDTH_16,.ecc={NAND_ECC_HW,2048,28,1,28,&layout} };
    for (int i=0;i<28;i++)layout.eccpos[i]=36+i;
    struct mtd_info mtd = { .priv = &chip, .size = 268435456ULL,
        .erasesize = 131072, .writesize = 2048, .oobsize = 64, .read_oob = raw_read };
    char buf[2112];
    unsigned char payload[2112] = { 0 }, header[32];
    struct kobject *obj = &mtd.dev.kobj;
    mtd.dev.data = &mtd;
    assert(hearth_register_sample(&mtd) == 0 && creates == 1);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == 2112);
    assert(reads == 1 && last_offset == HEARTH_SAMPLE_START && buf[0] == 0x11 && buf[2048] == 0x22);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 63 * 2112, sizeof(buf)) == 2112);
    assert(last_offset == HEARTH_SAMPLE_START + 63 * 2048 && reads == 2);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 64 * 2112, sizeof(buf)) == 0);
    assert(hearth_sample_read(NULL, obj, NULL, buf, -1, sizeof(buf)) == -EINVAL);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 1, sizeof(buf)) == -EINVAL);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 65 * 2112, sizeof(buf)) == -EINVAL);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 1ULL << 32, sizeof(buf)) == -EINVAL);
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf) - 1) == -EINVAL);
    wp = 0;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EROFS);
    wp = 1; mtd.flags = 0x400;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EROFS);
    assert(hearth_register_sample(&mtd) == -EINVAL && reads == 2);
    mtd.flags = 0; chip.ecc.mode = 3;
    assert(hearth_register_sample(&mtd) == -EINVAL);
    chip.ecc.mode = NAND_ECC_HW; mtd.oobsize = 128;
    assert(hearth_register_sample(&mtd) == -EINVAL);
    mtd.oobsize = 64; raw_result = -EIO;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EIO);
    raw_result = -EUCLEAN;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == 2112);
    raw_result = -EBADMSG;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EBADMSG);
    raw_result = -EUCLEAN; short_read=1;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EIO);
    raw_result = 0; short_read = 1;
    assert(hearth_sample_read(NULL, obj, NULL, buf, 0, sizeof(buf)) == -EIO);
    assert(sample_crc((const unsigned char *)"123456789", 9) == 0xcbf43926U);
    sample_header(header, 1, 63, payload);
    assert(fwrite(header, 1, sizeof(header), stdout) == sizeof(header));
    sample_failure_header(header,2,1,49,-EBADMSG);
    assert(fwrite(header,1,sizeof(header),stdout)==sizeof(header));
    layout.eccpos[0]=35;
    assert(hearth_register_sample(&mtd)==-EINVAL);
    layout.eccpos[0]=36;chip.options=0;
    assert(hearth_register_sample(&mtd)==-EINVAL);
    return 0;
}
