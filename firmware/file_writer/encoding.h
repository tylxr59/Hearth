/* Original read-only per-inode JFFS2 encoding audit, GPL-2.0-or-later.
 * No raw data, addresses, arbitrary ioctl buffers or write operation exposed. */
#include <linux/capability.h>
#include <linux/crc32.h>
#define HEARTH_ENCODING_IOCTL 0x4871U
static long hearth_encoding_check(struct file *file,unsigned int command,unsigned long argument)
{
 struct inode *inode=file->f_path.dentry->d_inode;
 struct jffs2_inode_info *f;
 struct jffs2_sb_info *c;
 struct jffs2_node_frag *fragment;
 int result=0;
 if(command!=HEARTH_ENCODING_IOCTL||argument) return -ENOTTY;
 if(!capable(CAP_SYS_ADMIN)||!S_ISREG(inode->i_mode)) return -EPERM;
 f=JFFS2_INODE_INFO(inode);c=JFFS2_SB_INFO(inode->i_sb);
 mutex_lock(&f->sem);
 for(fragment=frag_first(&f->fragtree);fragment;fragment=frag_next(fragment)) {
  struct jffs2_raw_inode raw;
  size_t amount=0;
  if(!fragment->node) continue; /* Ordinary uncompressed sparse-file hole. */
  if(!fragment->node->raw||jffs2_flash_read(c,ref_offset(fragment->node->raw),sizeof(raw),&amount,(unsigned char *)&raw)||
     amount!=sizeof(raw)||je16_to_cpu(raw.magic)!=JFFS2_MAGIC_BITMASK||
     je16_to_cpu(raw.nodetype)!=JFFS2_NODETYPE_INODE||je32_to_cpu(raw.ino)!=inode->i_ino||
     crc32(0,&raw,sizeof(raw)-8)!=je32_to_cpu(raw.node_crc)) { result=-EIO;break; }
  if(raw.compr!=JFFS2_COMPR_NONE&&raw.compr!=JFFS2_COMPR_ZERO) { result=-EOPNOTSUPP;break; }
 }
 mutex_unlock(&f->sem);
 return result;
}
