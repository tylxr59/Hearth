/* Original Hearth fixed scratch I/O, GPL-2.0-or-later. */
#include "core.h"

static struct mtd_info *hearth_scratch_mtd;
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

