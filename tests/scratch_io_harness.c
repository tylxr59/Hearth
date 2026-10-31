/* Original synthetic MTD/GPMC adapter test, GPL-2.0-or-later. */
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef unsigned char u_char;
typedef int64_t loff_t;
#define NAND_ROM 1
#define NAND_SKIP_BBTSCAN 2
#define NAND_USE_FLASH_BBT 4
#define BBT_AUTO_REFRESH 8
#define NAND_BUSWIDTH_16 16
#define NAND_ECC_HW 2
#define MTD_OOB_PLACE 0
#define MTD_OOB_RAW 2
#define MTD_ERASE_DONE 8
#define GPMC_CONFIG_WP 5
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct mtd_info;
struct erase_info { struct mtd_info *mtd; uint64_t addr, len; unsigned int state; };
struct mtd_oob_ops {
    unsigned int mode; size_t len, retlen, ooblen, oobretlen; unsigned int ooboffs;
    unsigned char *datbuf, *oobbuf;
};
struct layout {
    unsigned int eccbytes, eccpos[28];
    struct { unsigned int offset, length; } oobfree[1];
};
struct nand_chip {
    unsigned int options, badblockpos, numchips;
    void *bbt;
    struct { unsigned int mode,size,steps,bytes,total; struct layout *layout; } ecc;
    int (*block_markbad)(struct mtd_info *, loff_t);
};
struct mtd_info {
    uint64_t size;
    unsigned int erasesize,writesize,oobsize,flags;
    void *priv;
    int (*read_oob)(struct mtd_info *,loff_t,struct mtd_oob_ops *);
    int (*write)(struct mtd_info *,loff_t,size_t,size_t *,const u_char *);
    int (*erase)(struct mtd_info *,struct erase_info *);
    int (*write_oob)(struct mtd_info *,loff_t,struct mtd_oob_ops *);
};
struct omap_nand_info { struct mtd_info mtd; int gpmc_cs; };
static int wp, wp_error, io_error, short_io, false_erase;
static unsigned int reads, programs, erases, markers;
static int hearth_deny_write(struct mtd_info *m,loff_t a,size_t n,size_t *r,const u_char *b)
{ (void)m;(void)a;(void)n;(void)r;(void)b;return -EROFS; }
static int hearth_deny_erase(struct mtd_info *m,struct erase_info *e)
{ (void)m;(void)e;return -EROFS; }
static int hearth_deny_oob(struct mtd_info *m,loff_t a,struct mtd_oob_ops *o)
{ (void)m;(void)a;(void)o;return -EROFS; }
static int hearth_deny_markbad(struct mtd_info *m,loff_t a)
{ (void)m;(void)a;return -EROFS; }
static int hearth_wp_is_asserted(struct mtd_info *m) { (void)m;return wp; }
static int gpmc_cs_configure(int cs,int cmd,int val)
{ assert(cs==3 && cmd==GPMC_CONFIG_WP);if(wp_error)return -EIO;wp=val;return 0; }
#include "../firmware/scratch_test/io.h"

static int read_oob(struct mtd_info *m,loff_t a,struct mtd_oob_ops *o)
{
    assert(m==hearth_scratch_mtd && wp==1);
    assert(a>=HS_OFFSET && a<HS_OFFSET+131072 && (a-HS_OFFSET)%HS_DATA==0);
    assert(o->mode==MTD_OOB_RAW || o->mode==MTD_OOB_PLACE);
    assert(o->len==HS_DATA && o->ooblen==HS_OOB && o->ooboffs==0);
    assert(o->oobbuf==o->datbuf+HS_DATA);
    ++reads; memset(o->datbuf,0xff,HS_RECORD);
    o->retlen=short_io?1:HS_DATA;o->oobretlen=HS_OOB;
    return io_error;
}
static int program(struct mtd_info *m,loff_t a,size_t n,size_t *done,const u_char *data)
{
    assert(m==hearth_scratch_mtd && wp==0 && a==171968512 && n==2048 && data);
    ++programs;*done=short_io?1:n;return io_error;
}
static int erase(struct mtd_info *m,struct erase_info *e)
{
    assert(m==hearth_scratch_mtd && wp==0 && e->mtd==m);
    assert(e->addr==171966464 && e->len==131072);
    ++erases;e->state=false_erase?0:MTD_ERASE_DONE;return io_error;
}
static int marker(struct mtd_info *m,loff_t a,struct mtd_oob_ops *o)
{
    assert(m==hearth_scratch_mtd && wp==0 && a==171966464);
    assert(o->mode==MTD_OOB_PLACE && o->len==0 && !o->datbuf);
    assert(o->ooboffs==2 && o->ooblen==8 && o->oobbuf);
    ++markers;o->retlen=0;o->oobretlen=short_io?1:8;return io_error;
}

int main(void)
{
    struct omap_nand_info info;
    struct nand_chip chip;
    struct layout layout;
    unsigned char buffer[HS_RECORD];
    unsigned int i;
    memset(&info,0,sizeof(info));memset(&chip,0,sizeof(chip));memset(&layout,0,sizeof(layout));
    info.gpmc_cs=3;info.mtd.size=268435456;info.mtd.erasesize=131072;
    info.mtd.writesize=2048;info.mtd.oobsize=64;info.mtd.priv=&chip;
    info.mtd.read_oob=read_oob;info.mtd.write=hearth_deny_write;
    info.mtd.erase=hearth_deny_erase;info.mtd.write_oob=hearth_deny_oob;
    chip.options=NAND_ROM|NAND_SKIP_BBTSCAN|NAND_BUSWIDTH_16;
    chip.numchips=1;chip.ecc.mode=NAND_ECC_HW;chip.ecc.size=2048;
    chip.ecc.steps=1;chip.ecc.bytes=28;chip.ecc.total=28;chip.ecc.layout=&layout;
    chip.block_markbad=hearth_deny_markbad;layout.eccbytes=28;
    layout.oobfree[0].offset=2;layout.oobfree[0].length=34;
    for(i=0;i<28;i++)layout.eccpos[i]=36+i;
    hearth_scratch_mtd=&info.mtd;hearth_saved_program=program;
    hearth_saved_erase=erase;hearth_saved_oob=marker;wp=1;
    assert(!hearth_scratch_guard(&info.mtd));
    for(i=0;i<64;i++)assert(!hearth_scratch_read_page(&info.mtd,i,0,buffer));
    assert(hearth_scratch_read_page(&info.mtd,64,0,buffer)<0 && reads==64);
    assert(hearth_scratch_read_page(&info.mtd,0,2,buffer)<0);
    io_error=-EUCLEAN;assert(hearth_scratch_read_page(&info.mtd,1,0,buffer)<0);
    assert(!hearth_scratch_read_page(&info.mtd,1,1,buffer));
    io_error=-EBADMSG;assert(hearth_scratch_read_page(&info.mtd,1,1,buffer)<0);
    io_error=0;short_io=1;assert(hearth_scratch_read_page(&info.mtd,1,1,buffer)<0);
    short_io=0;
    assert(hearth_scratch_program(&info.mtd,buffer)<0 && programs==0);
    assert(hearth_scratch_erase(&info.mtd)<0 && erases==0);
    assert(hearth_scratch_marker(&info.mtd,buffer)<0 && markers==0);
    assert(hearth_scratch_protected(&info.mtd)==1);
    assert(!hearth_scratch_writable(&info.mtd,1) && !wp);
    assert(!hearth_scratch_program(&info.mtd,buffer) && programs==1);
    assert(!hearth_scratch_erase(&info.mtd) && erases==1);
    assert(!hearth_scratch_marker(&info.mtd,buffer) && markers==1);
    short_io=1;
    assert(hearth_scratch_program(&info.mtd,buffer)<0);
    assert(hearth_scratch_marker(&info.mtd,buffer)<0);
    short_io=0;false_erase=1;assert(hearth_scratch_erase(&info.mtd)<0);false_erase=0;
    io_error=-EIO;assert(hearth_scratch_program(&info.mtd,buffer)<0);
    assert(hearth_scratch_erase(&info.mtd)<0 && hearth_scratch_marker(&info.mtd,buffer)<0);
    io_error=0;assert(!hearth_scratch_writable(&info.mtd,0) && wp);
    wp_error=1;assert(hearth_scratch_writable(&info.mtd,1)<0 && wp);wp_error=0;
    chip.options|=BBT_AUTO_REFRESH;assert(hearth_scratch_guard(&info.mtd)<0);
    chip.options&=~BBT_AUTO_REFRESH;
    chip.options|=NAND_USE_FLASH_BBT;assert(hearth_scratch_guard(&info.mtd)<0);
    chip.options&=~NAND_USE_FLASH_BBT;
    chip.bbt=&chip;assert(hearth_scratch_guard(&info.mtd)<0);chip.bbt=NULL;
    chip.options&=~NAND_ROM;assert(hearth_scratch_guard(&info.mtd)<0);chip.options|=NAND_ROM;
    chip.options&=~NAND_SKIP_BBTSCAN;assert(hearth_scratch_guard(&info.mtd)<0);
    chip.options|=NAND_SKIP_BBTSCAN;
    chip.options&=~NAND_BUSWIDTH_16;assert(hearth_scratch_guard(&info.mtd)<0);
    chip.options|=NAND_BUSWIDTH_16;
    info.mtd.flags=1;assert(hearth_scratch_guard(&info.mtd)<0);info.mtd.flags=0;
    for(i=0;i<28;i++){layout.eccpos[i]^=1;assert(hearth_scratch_guard(&info.mtd)<0);layout.eccpos[i]^=1;}
    layout.oobfree[0].length=35;assert(hearth_scratch_guard(&info.mtd)<0);
    puts("fixed scratch adapter I/O model passed; hardware unqualified");
    return 0;
}
