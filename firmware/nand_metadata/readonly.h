/* Original Hearth guards, GPL-2.0-or-later when combined with the Linux driver.
 * A geometry-only experiment, not a restoration or flash-programming tool.
 */
#include <linux/uio.h>

static int hearth_deny_erase(struct mtd_info *mtd, struct erase_info *instr)
{
    instr->state = MTD_ERASE_FAILED;
    return -EROFS;
}

static int hearth_deny_write(struct mtd_info *mtd, loff_t to, size_t len,
                            size_t *retlen, const u_char *buf)
{
    if (retlen)
        *retlen = 0;
    return -EROFS;
}

static int hearth_deny_oob(struct mtd_info *mtd, loff_t to, struct mtd_oob_ops *ops)
{
    if (ops) {
        ops->retlen = 0;
        ops->oobretlen = 0;
    }
    return -EROFS;
}

static int hearth_deny_markbad(struct mtd_info *mtd, loff_t offset)
{
    return -EROFS;
}

static int hearth_deny_lock(struct mtd_info *mtd, loff_t offset, uint64_t len)
{
    return -EROFS;
}

static int hearth_deny_prot_lock(struct mtd_info *mtd, loff_t offset, size_t len)
{
    return -EROFS;
}

/* This kernel's OTP write callback predates const-correct data buffers. */
static int hearth_deny_prot_write(struct mtd_info *mtd, loff_t to, size_t len,
                                 size_t *retlen, u_char *buf)
{
    return hearth_deny_write(mtd, to, len, retlen, buf);
}

static int hearth_deny_writev(struct mtd_info *mtd, const struct kvec *vecs,
                             unsigned long count, loff_t to, size_t *retlen)
{
    if (retlen)
        *retlen = 0;
    return -EROFS;
}

static int hearth_wp_is_asserted(struct mtd_info *mtd)
{
    struct nand_chip *chip = mtd->priv;
    int status;
    chip->select_chip(mtd, 0);
    chip->cmdfunc(mtd, NAND_CMD_STATUS, -1, -1);
    status = chip->read_byte(mtd);
    chip->select_chip(mtd, -1);
    /* Same status-bit meaning used by nand_check_wp in this kernel. */
    return !(status & NAND_STATUS_WP);
}

static void hearth_block_mtd_writes(struct mtd_info *mtd)
{
    struct nand_chip *chip = mtd->priv;
    mtd->flags &= ~MTD_WRITEABLE;
    mtd->erase = hearth_deny_erase;
    mtd->write = hearth_deny_write;
    mtd->panic_write = hearth_deny_write;
    mtd->write_oob = hearth_deny_oob;
    mtd->block_markbad = hearth_deny_markbad;
    mtd->write_user_prot_reg = hearth_deny_prot_write;
    mtd->lock_user_prot_reg = hearth_deny_prot_lock;
    mtd->lock = hearth_deny_lock;
    mtd->unlock = hearth_deny_lock;
    mtd->writev = hearth_deny_writev;
    chip->block_markbad = hearth_deny_markbad;
}
