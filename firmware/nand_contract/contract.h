/* Original metadata-only extension, GPL-2.0-or-later with the Linux driver.
 * No writes, raw NAND contents, identifiers or mutable interface.
 */
static ssize_t hearth_contract_show(struct device *dev,
                                   struct device_attribute *attr, char *buf)
{
    struct mtd_info *mtd = container_of(dev, struct mtd_info, dev);
    struct nand_chip *chip = mtd->priv;
    struct nand_ecclayout *layout;
    unsigned int i;
    int used;
    (void)attr;
    if (!chip || mtd->type != MTD_NANDFLASH || mtd->flags || !hearth_wp_is_asserted(mtd))
        return -EROFS;
    layout = chip->ecc.layout;
    if (!layout || !layout->eccbytes || layout->eccbytes > 64)
        return -EINVAL;
    used = scnprintf(buf, 1024,
        "source=custom-ram-kernel\nname=%s\ntype=nand\nflags=0x0\n"
        "size=%llu\nerasesize=%u\nwritesize=%u\noobsize=%u\n"
        "protected=1\nbus_width=%u\nbadblock_position=%u\n"
        "scan_second_page=%u\nscan_last_page=%u\nscan_byte1_and6=%u\n"
        "pattern_present=%u\npattern_offset=%u\npattern_length=%u\npattern_options=%u\n"
        "ecc_mode=%u\necc_size=%u\necc_bytes=%u\necc_steps=%u\necc_total=%u\n"
        "oob_free_offset=%u\noob_free_length=%u\necc_positions=",
        mtd->name, (unsigned long long)mtd->size, mtd->erasesize, mtd->writesize, mtd->oobsize,
        (chip->options & NAND_BUSWIDTH_16) ? 16U : 8U,
        (unsigned int)chip->badblockpos,
        !!(chip->options & NAND_BBT_SCAN2NDPAGE),
        !!(chip->options & NAND_BBT_SCANLASTPAGE),
        !!(chip->options & NAND_BBT_SCANBYTE1AND6),
        chip->badblock_pattern ? 1U : 0U,
        chip->badblock_pattern ? chip->badblock_pattern->offs : 0U,
        chip->badblock_pattern ? chip->badblock_pattern->len : 0U,
        chip->badblock_pattern ? chip->badblock_pattern->options : 0U,
        (unsigned int)chip->ecc.mode, chip->ecc.size, chip->ecc.bytes,
        chip->ecc.steps, chip->ecc.total,
        layout->oobfree[0].offset, layout->oobfree[0].length);
    for (i = 0; i < layout->eccbytes; i++)
        used += scnprintf(buf + used, 1024 - used, "%s%u", i ? "," : "", layout->eccpos[i]);
    used += scnprintf(buf + used, 1024 - used, "\n");
    return used;
}
static DEVICE_ATTR(hearth_contract, S_IRUSR, hearth_contract_show, NULL);
