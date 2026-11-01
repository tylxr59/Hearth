/* Original synthetic kernel API fixtures for the actual encoding audit header.
 * CRC is a deterministic test stub, not a replacement CRC implementation. */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#define _LINUX_CAPABILITY_H
#define CAP_SYS_ADMIN 21
#define JFFS2_MAGIC_BITMASK 0x1985
#define JFFS2_NODETYPE_INODE 0xe002
#define JFFS2_COMPR_NONE 0
#define JFFS2_COMPR_ZERO 1
#define je16_to_cpu(x) (x)
#define je32_to_cpu(x) (x)
struct jffs2_raw_inode { uint16_t magic,nodetype;uint32_t ino;unsigned char compr,pad[7];uint32_t data_crc,node_crc; };
struct raw_reference { unsigned int offset; };
struct full_node { struct raw_reference *raw; };
struct jffs2_node_frag { struct full_node *node;struct jffs2_node_frag *next; };
struct jffs2_inode_info { int sem;struct jffs2_node_frag *fragtree; };
struct jffs2_sb_info { int unused; };
struct inode { unsigned int i_ino,i_mode;struct jffs2_sb_info *i_sb;struct jffs2_inode_info *info; };
struct dentry { struct inode *d_inode; };
struct file { struct { struct dentry *dentry; } f_path; };
#define JFFS2_INODE_INFO(inode) ((inode)->info)
#define JFFS2_SB_INFO(sb) (sb)
#define frag_first(root) (*(root))
#define frag_next(fragment) ((fragment)->next)
#define ref_offset(raw) ((raw)->offset)
static struct jffs2_raw_inode nodes[3];static int authorized=1,locked,reads,read_fault,short_read;
static int capable(int which) { assert(which==CAP_SYS_ADMIN);return authorized; }
static void mutex_lock(int *lock) { (void)lock;assert(!locked);locked=1; }
static void mutex_unlock(int *lock) { (void)lock;assert(locked);locked=0; }
static uint32_t crc32(uint32_t seed,const void *data,size_t length)
{ assert(!seed&&data&&length==sizeof(struct jffs2_raw_inode)-8);return 42; }
static int jffs2_flash_read(struct jffs2_sb_info *sb,unsigned int at,size_t length,size_t *done,unsigned char *out)
{ assert(sb&&locked&&at<3&&length==sizeof(nodes[at]));reads++;if(read_fault) return -EIO;memcpy(out,&nodes[at],length);*done=short_read?length-1:length;return 0; }
#include "../firmware/file_writer/encoding.h"
int main(int argc,char **argv)
{
 struct raw_reference refs[3]={{0},{1},{2}};struct full_node full[3]={{refs},{refs+1},{refs+2}};
 struct jffs2_node_frag fragments[3]={{full,0},{full+1,0},{full+2,0}};
 struct jffs2_inode_info info={0,fragments};struct jffs2_sb_info sb={0};
 struct inode inode={123,S_IFREG|0600,&sb,&info};struct dentry entry={&inode};struct file file={{&entry}};
 unsigned int command=HEARTH_ENCODING_IOCTL;unsigned long argument=0;long expected=0;int scenario,i;
 assert(argc==2);scenario=atoi(argv[1]);
 for(i=0;i<3;i++) nodes[i]=(struct jffs2_raw_inode){JFFS2_MAGIC_BITMASK,JFFS2_NODETYPE_INODE,123,0,{0},0,42};
 if(scenario==1) { nodes[0].compr=7;expected=-EOPNOTSUPP; }
 if(scenario==2) { nodes[0].compr=6;expected=-EOPNOTSUPP; }
 if(scenario==3) nodes[0].compr=1;
 if(scenario==4) { nodes[0].node_crc=0;expected=-EIO; }
 if(scenario==5) { nodes[0].ino=321;expected=-EIO; }
 if(scenario==6) { nodes[0].magic=0;expected=-EIO; }
 if(scenario==7) { read_fault=1;expected=-EIO; }
 if(scenario==8) { short_read=1;expected=-EIO; }
 if(scenario==9) { command++;expected=-ENOTTY; }
 if(scenario==10) { argument=1;expected=-ENOTTY; }
 if(scenario==11) { authorized=0;expected=-EPERM; }
 if(scenario==12) { inode.i_mode=S_IFDIR|0700;expected=-EPERM; }
 if(scenario==13) fragments[0].node=0;
 if(scenario==14) { fragments[0].next=fragments+1;fragments[1].next=fragments+2;nodes[1].compr=7;expected=-EOPNOTSUPP; }
 assert(hearth_encoding_check(&file,command,argument)==expected&&!locked);
 if(scenario==14) assert(reads==2);
 if(scenario>=9&&scenario<=13) assert(!reads);
 return 0;
}
