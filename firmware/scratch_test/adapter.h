/* Original Hearth fixed scratch adapter, GPL-2.0-or-later. Experimental writer.
 * Included ONLY by a separately patched diagnostic omap2.c, never read-only builds.
 */
#include <crypto/hash.h>
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include <linux/vmalloc.h>
#include "core.c"

static struct hs_tx *hearth_scratch;
static struct mtd_info *hearth_scratch_mtd;
static DEFINE_MUTEX(hearth_scratch_mutex);
static int (*hearth_saved_program)(struct mtd_info *, loff_t, size_t, size_t *, const u_char *);
static int (*hearth_saved_erase)(struct mtd_info *, struct erase_info *);
static int (*hearth_saved_oob)(struct mtd_info *, loff_t, struct mtd_oob_ops *);

static int hearth_scratch_guard(void *ctx)
{
    struct mtd_info *mtd = ctx;
    struct nand_chip *chip = mtd->priv;
    unsigned int i;
    if (mtd != hearth_scratch_mtd || mtd->size != 268435456ULL ||
        mtd->erasesize != 131072 || mtd->writesize != HS_DATA || mtd->oobsize != HS_OOB ||
        mtd->flags != 0 || !mtd->read_oob ||
        mtd->write != hearth_deny_write || mtd->erase != hearth_deny_erase ||
        mtd->write_oob != hearth_deny_oob || chip->block_markbad != hearth_deny_markbad ||
        !(chip->options & NAND_ROM) || !(chip->options & NAND_SKIP_BBTSCAN) ||
        chip->options & (NAND_USE_FLASH_BBT | BBT_AUTO_REFRESH) || chip->bbt ||
        !(chip->options & NAND_BUSWIDTH_16) || chip->badblockpos != 0 ||
        chip->numchips != 1 || chip->ecc.mode != NAND_ECC_HW || chip->ecc.size != HS_DATA ||
        chip->ecc.steps != 1 || chip->ecc.bytes != 28 || chip->ecc.total != 28 ||
        !chip->ecc.layout || chip->ecc.layout->eccbytes != 28 ||
        chip->ecc.layout->oobfree[0].offset != 2 ||
        chip->ecc.layout->oobfree[0].length != 34 ||
        (unsigned long long)HS_OFFSET + mtd->erasesize > mtd->size ||
        HS_OFFSET != HS_BLOCK * 131072u ||
        !hearth_saved_program || !hearth_saved_erase || !hearth_saved_oob)
        return -EINVAL;
    for (i = 0; i < 28; ++i)
        if (chip->ecc.layout->eccpos[i] != 36 + i)
            return -EINVAL;
    return 0;
}

static int hearth_scratch_protected(void *ctx)
{
    return hearth_wp_is_asserted(ctx);
}

static int hearth_scratch_writable(void *ctx, int enabled)
{
    struct omap_nand_info *info = container_of((struct mtd_info *)ctx,
                                              struct omap_nand_info, mtd);
    int ret = gpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, enabled ? 0 : 1);
    if (ret || hearth_wp_is_asserted(ctx) != !enabled)
        return -EIO;
    return 0;
}

static int hearth_scratch_read_page(void *ctx, unsigned int page, int normal,
                                   unsigned char *out)
{
    struct mtd_info *mtd = ctx;
    struct mtd_oob_ops ops;
    int ret;
    if (page >= HS_PAGES || (normal != 0 && normal != 1) ||
        hearth_scratch_guard(ctx) || !hearth_wp_is_asserted(mtd))
        return -EINVAL;
    memset(&ops, 0, sizeof(ops));
    ops.mode = normal ? MTD_OOB_PLACE : MTD_OOB_RAW;
    ops.len = HS_DATA;
    ops.ooblen = HS_OOB;
    ops.datbuf = out;
    ops.oobbuf = out + HS_DATA;
    ret = mtd->read_oob(mtd, HS_OFFSET + (loff_t)page * HS_DATA, &ops);
    if ((ret && !(normal && ret == -EUCLEAN)) ||
        ops.retlen != HS_DATA || ops.oobretlen != HS_OOB)
        return -EIO;
    return 0;
}

static int hearth_scratch_program(void *ctx, const unsigned char *data)
{
    struct mtd_info *mtd = ctx;
    size_t done = 0;
    int ret;
    if (hearth_scratch_guard(ctx) || hearth_wp_is_asserted(mtd))
        return -EROFS;
    ret = hearth_saved_program(mtd, HS_OFFSET + HS_TEST_PAGE * HS_DATA, HS_DATA, &done, data);
    return ret || done != HS_DATA ? -EIO : 0;
}

static int hearth_scratch_erase(void *ctx)
{
    struct erase_info erase;
    int ret;
    if (hearth_scratch_guard(ctx) || hearth_wp_is_asserted(ctx))
        return -EROFS;
    memset(&erase, 0, sizeof(erase));
    erase.mtd = ctx;
    erase.addr = HS_OFFSET;
    erase.len = 131072;
    ret = hearth_saved_erase(ctx, &erase);
    /* This pinned nand_erase completes synchronously and updates state before
     * returning. No BBT auto-refresh or flash-BBT callback can be enabled.
     */
    return ret || erase.state != MTD_ERASE_DONE ? -EIO : 0;
}

static int hearth_scratch_marker(void *ctx, const unsigned char *marker)
{
    struct mtd_oob_ops ops;
    int ret;
    if (hearth_scratch_guard(ctx) || hearth_wp_is_asserted(ctx))
        return -EROFS;
    memset(&ops, 0, sizeof(ops));
    ops.mode = MTD_OOB_PLACE;
    ops.ooboffs = 2;
    ops.ooblen = 8;
    ops.oobbuf = (unsigned char *)marker;
    ret = hearth_saved_oob(ctx, HS_OFFSET, &ops);
    return ret || ops.oobretlen != 8 || ops.retlen != 0 ? -EIO : 0;
}

static int hearth_scratch_hash(void *ctx, const unsigned char *data,
                              unsigned int len, unsigned char *out)
{
    struct crypto_shash *tfm;
    struct shash_desc *desc;
    int ret;
    if (len != HS_BYTES)
        return -EINVAL;
    tfm = crypto_alloc_shash("sha256-generic", 0, 0);
    if (IS_ERR(tfm))
        return PTR_ERR(tfm);
    desc = kzalloc(sizeof(*desc) + crypto_shash_descsize(tfm), GFP_KERNEL);
    if (!desc) {
        crypto_free_shash(tfm);
        return -ENOMEM;
    }
    desc->tfm = tfm;
    ret = crypto_shash_digest(desc, data, len, out);
    kfree(desc);
    crypto_free_shash(tfm);
    return ret;
}

static const struct hs_ops hearth_scratch_ops = {
    hearth_scratch_guard, hearth_scratch_protected, hearth_scratch_read_page,
    hearth_scratch_writable, hearth_scratch_program, hearth_scratch_erase,
    hearth_scratch_marker, hearth_scratch_hash
};

/* The snapshot is exposed only from RAM. No read can address NAND or cause a
 * write. Fixed layout: 128-byte metadata + original + programmed raw/normal + final.
 */
#define HEARTH_SCRATCH_HEADER 128u
#define HEARTH_SCRATCH_WIRE (HEARTH_SCRATCH_HEADER + 2 * HS_BYTES + 2 * HS_RECORD)
static void hearth_scratch_u32(unsigned char *out, unsigned int value)
{
    unsigned int i;
    for (i = 0; i < 4; ++i)
        out[i] = value >> (8 * i);
}
static unsigned char hearth_scratch_byte(unsigned int off, const unsigned char *header)
{
    if (off < HEARTH_SCRATCH_HEADER) return header[off];
    off -= HEARTH_SCRATCH_HEADER;
    if (off < HS_BYTES) return hearth_scratch->original[off];
    off -= HS_BYTES;
    if (off < HS_RECORD) return hearth_scratch->programmed_raw[off];
    off -= HS_RECORD;
    if (off < HS_RECORD) return hearth_scratch->programmed_normal[off];
    off -= HS_RECORD;
    return hearth_scratch->final[off];
}
static ssize_t hearth_scratch_snapshot(struct file *file, struct kobject *kobj,
        struct bin_attribute *attr, char *buf, loff_t off, size_t count)
{
    unsigned char header[HEARTH_SCRATCH_HEADER];
    struct hs_report *r;
    unsigned int i;
    if (off < 0 || off > HEARTH_SCRATCH_WIRE) return -EINVAL;
    mutex_lock(&hearth_scratch_mutex);
    if (!hearth_scratch || hearth_scratch->state == HS_EMPTY) {
        mutex_unlock(&hearth_scratch_mutex);
        return -EAGAIN;
    }
    memset(header, 0, sizeof(header));
    memcpy(header, "HRTHSCR1", 8);
    r = &hearth_scratch->report;
    hearth_scratch_u32(header + 8, 1);
    hearth_scratch_u32(header + 12, hearth_scratch->state);
    hearth_scratch_u32(header + 16, r->error);
    hearth_scratch_u32(header + 20, r->program_attempted);
    hearth_scratch_u32(header + 24, r->erase_attempted);
    hearth_scratch_u32(header + 28, r->marker_attempted);
    hearth_scratch_u32(header + 32, r->program_data_match);
    hearth_scratch_u32(header + 36, r->restored);
    hearth_scratch_u32(header + 40, r->final_protected);
    hearth_scratch_u32(header + 44, (unsigned int)r->program_result);
    hearth_scratch_u32(header + 48, (unsigned int)r->erase_result);
    hearth_scratch_u32(header + 52, (unsigned int)r->marker_result);
    hearth_scratch_u32(header + 56, HS_BLOCK);
    hearth_scratch_u32(header + 60, HS_BYTES);
    memcpy(header + 64, hearth_scratch->digest, HS_DIGEST);
    memcpy(header + 96, hearth_scratch->final_digest, HS_DIGEST);
    count = min_t(size_t, count, HEARTH_SCRATCH_WIRE - off);
    for (i = 0; i < count; ++i)
        buf[i] = hearth_scratch_byte((unsigned int)off + i, header);
    mutex_unlock(&hearth_scratch_mutex);
    return count;
}

static ssize_t hearth_scratch_command(struct device *dev,
        struct device_attribute *attr, const char *buf, size_t count)
{
    int ret;
    mutex_lock(&hearth_scratch_mutex);
    if (!hearth_scratch) ret = -ENODEV;
    else if (count == 8 && !memcmp(buf, "PREPARE\n", 8))
        ret = hs_prepare(hearth_scratch, &hearth_scratch_ops, hearth_scratch_mtd);
    else if (count == 40 && !memcmp(buf, "HSACK001", 8))
        ret = hs_execute(hearth_scratch, &hearth_scratch_ops, hearth_scratch_mtd,
                         (const unsigned char *)buf + 8);
    else ret = -EINVAL;
    mutex_unlock(&hearth_scratch_mutex);
    return ret ? -EIO : count;
}
static DEVICE_ATTR(hearth_scratch_control, 0200, NULL, hearth_scratch_command);
static struct bin_attribute hearth_scratch_snapshot_attr = {
    .attr = { .name = "hearth_scratch_snapshot", .mode = 0400 },
    .size = HEARTH_SCRATCH_WIRE,
    .read = hearth_scratch_snapshot
};

static void hearth_scratch_save_mutators(struct mtd_info *mtd)
{
    hearth_saved_program = mtd->write;
    hearth_saved_erase = mtd->erase;
    hearth_saved_oob = mtd->write_oob;
}

static int hearth_scratch_register(struct mtd_info *mtd)
{
    int ret;
    if (hearth_scratch_mtd) return -EBUSY;
    hearth_scratch_mtd = mtd;
    if (hearth_scratch_guard(mtd) || !hearth_wp_is_asserted(mtd)) return -EINVAL;
    hearth_scratch = vzalloc(sizeof(*hearth_scratch));
    if (!hearth_scratch) return -ENOMEM;
    ret = sysfs_create_bin_file(&mtd->dev.kobj, &hearth_scratch_snapshot_attr);
    if (ret) goto failed;
    ret = device_create_file(&mtd->dev, &dev_attr_hearth_scratch_control);
    if (!ret) return 0;
    sysfs_remove_bin_file(&mtd->dev.kobj, &hearth_scratch_snapshot_attr);
failed:
    vfree(hearth_scratch);
    hearth_scratch = NULL;
    return ret;
}
static void hearth_scratch_remove(struct mtd_info *mtd)
{
    device_remove_file(&mtd->dev, &dev_attr_hearth_scratch_control);
    sysfs_remove_bin_file(&mtd->dev.kobj, &hearth_scratch_snapshot_attr);
    vfree(hearth_scratch);
    hearth_scratch = NULL;
}
