/* Original Hearth bounded normal-ECC read experiment, GPL-2.0-or-later. */
#include <linux/sysfs.h>

#define HEARTH_SAMPLE_START (190ULL * 131072)
#define HEARTH_SAMPLE_PAGE 2048U
#define HEARTH_SAMPLE_OOB 64U
#define HEARTH_SAMPLE_RECORD (HEARTH_SAMPLE_PAGE + HEARTH_SAMPLE_OOB)
#define HEARTH_SAMPLE_PAGES 64U
#define HEARTH_SAMPLE_BYTES (HEARTH_SAMPLE_PAGES * HEARTH_SAMPLE_RECORD)

static ssize_t hearth_sample_read(struct file *file, struct kobject *kobj,
                                 struct bin_attribute *attr, char *buf,
                                 loff_t off, size_t count)
{
    struct device *dev = container_of(kobj, struct device, kobj);
    struct mtd_info *mtd = dev_get_drvdata(dev);
    struct mtd_oob_ops ops;
    unsigned int offset, page;
    int ret;

    if (off == HEARTH_SAMPLE_BYTES)
        return 0;
    if (off < 0 || off > HEARTH_SAMPLE_BYTES || count != HEARTH_SAMPLE_RECORD)
        return -EINVAL;
    offset = (unsigned int)off;
    if (offset % HEARTH_SAMPLE_RECORD)
        return -EINVAL;
    if (mtd->flags != 0 || !hearth_wp_is_asserted(mtd))
        return -EROFS;
    page = offset / HEARTH_SAMPLE_RECORD;
    memset(&ops, 0, sizeof(ops));
    ops.mode = MTD_OOB_PLACE;
    ops.len = HEARTH_SAMPLE_PAGE;
    ops.ooblen = HEARTH_SAMPLE_OOB;
    ops.datbuf = (uint8_t *)buf;
    ops.oobbuf = (uint8_t *)buf + HEARTH_SAMPLE_PAGE;
    ret = mtd->read_oob(mtd, HEARTH_SAMPLE_START + (loff_t)page * HEARTH_SAMPLE_PAGE, &ops);
    if ((ret && ret != -EUCLEAN) || ops.retlen != HEARTH_SAMPLE_PAGE || ops.oobretlen != HEARTH_SAMPLE_OOB)
        return ret && ret != -EUCLEAN ? ret : -EIO;
    return HEARTH_SAMPLE_RECORD;
}

static struct bin_attribute hearth_sample_attr = {
    .attr = { .name = "hearth_ecc_sample", .mode = 0400 },
    .size = HEARTH_SAMPLE_BYTES,
    .read = hearth_sample_read,
};

static int hearth_register_sample(struct mtd_info *mtd)
{
    struct nand_chip *chip = mtd->priv;
    unsigned int i;
    if (mtd->size != 268435456ULL || mtd->erasesize != 131072 ||
        mtd->writesize != HEARTH_SAMPLE_PAGE || mtd->oobsize != HEARTH_SAMPLE_OOB ||
        mtd->flags != 0 || !mtd->read_oob ||
        (chip->ecc.mode != NAND_ECC_HW || chip->ecc.size != 2048 ||
         chip->ecc.bytes != 28 || chip->ecc.steps != 1 || chip->ecc.total != 28 ||
         !(chip->options & NAND_BUSWIDTH_16) || chip->badblockpos != 0 ||
         !chip->ecc.layout || chip->ecc.layout->eccbytes != 28))
        return -EINVAL;
    if (HEARTH_SAMPLE_START + mtd->erasesize > mtd->size)
        return -EINVAL;
    if (chip->ecc.layout->oobfree[0].offset != 2 || chip->ecc.layout->oobfree[0].length != 34)
        return -EINVAL;
    for (i = 0; i < 28; i++)
        if (chip->ecc.layout->eccpos[i] != 36 + i)
            return -EINVAL;
    return sysfs_create_bin_file(&mtd->dev.kobj, &hearth_sample_attr);
}
