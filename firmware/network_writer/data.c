/* Original opaque DATA mappings, MIT. Never executes original firmware.
 * Candidate MAP_PRIVATE pages share unchanged original bytes. Only reviewed
 * spans get COW pages, then mprotect seals candidates read-only/non-executable.
 * No flash, rename, write-open, network or arbitrary path interface here. */
#include "data.h"
#include "../network_update/stream.h"
#include "plan.h"
#ifdef HEARTH_HOST_LAB
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <sys/xattr.h>
#include <fcntl.h>
#include <unistd.h>
#define H_NOFOLLOW O_NOFOLLOW
#define H_CLOEXEC O_CLOEXEC
#else
#include "../file_writer/abi.h"
extern void *mmap(void *,size_t,int,int,int,long);
extern int munmap(void *,size_t),mprotect(void *,size_t,int);
extern long flistxattr(int,char *,size_t);
#define H_NOFOLLOW O_NOFOLLOW
#define H_CLOEXEC O_CLOEXEC
#endif
struct hearth_file_change hn_changes[4];
unsigned int hn_memory_free,hn_space_available,hn_space_required,hn_data_diagnostic;
static void *originals[4],*candidates[4];
static unsigned int lengths[4];
static int loaded;
#ifndef HEARTH_HOST_LAB
static unsigned int word(const unsigned char *p)
{ return p[0]|(unsigned int)p[1]<<8|(unsigned int)p[2]<<16|(unsigned int)p[3]<<24; }
#endif
static int metadata(int fd,int directory,unsigned int length)
{
 unsigned int mode,links,owner,group;unsigned long long size;long attrs;
#ifdef HEARTH_HOST_LAB
 struct stat s;if(fstat(fd,&s)) return -1;
 mode=s.st_mode;links=s.st_nlink;owner=s.st_uid;group=s.st_gid;size=(unsigned long long)s.st_size;
 if(owner!=getuid()||group!=getgid()) return -1;
#else
 unsigned long long s[16],fs[16];unsigned char *b=(unsigned char *)s;
 if(syscall(197,fd,s)||syscall(100,fd,fs)||
    (word((unsigned char *)fs)!=0x858458f6U&&word((unsigned char *)fs)!=0x01021994U)) return -1;
 mode=word(b+16);links=word(b+20);owner=word(b+24);group=word(b+28);
 size=(unsigned long long)word(b+48)|(unsigned long long)word(b+52)<<32;
 if(owner||group) return -1;
#endif
 if(directory) { if((mode&0177777)!=0040700) return -1; }
 else if((mode&0177777)!=0100400||links!=1||size!=length) return -1;
 attrs=flistxattr(fd,0,0);
#ifdef HEARTH_HOST_LAB
 return attrs==0?0:-1;
#else
 return attrs==0||(attrs<0&&errno==95)?0:-1; /* Only the proven RAM fs above. */
#endif
}
int hn_memory_guard(void)
{
#ifdef HEARTH_HOST_LAB
 hn_memory_free=64U*1048576U;
#else
 unsigned long long s[16],total,free;unsigned char *b=(unsigned char *)s;unsigned int unit;
 if(syscall(116,s)) return -1;
 unit=word(b+52);total=(unsigned long long)word(b+16)*unit;free=(unsigned long long)word(b+20)*unit;
 if(!unit||unit>65536||!total||total>1073741824ULL||free>total) return -1;
 hn_memory_free=(unsigned int)free;
#endif
 return hn_memory_free>=24U*1048576U?0:-1;
}
struct input { const unsigned char *p;unsigned int length,at; };
static int rewind_input(void *p) { ((struct input *)p)->at=0;return 0; }
static long read_input(void *p,unsigned char *out,unsigned int n)
{
 struct input *in=p;unsigned int i;if(n>in->length-in->at) n=in->length-in->at;
 for(i=0;i<n;i++) out[i]=in->p[in->at+i];in->at+=n;return n;
}
int hn_data_release(void)
{
 unsigned int i;int result=0;
 for(i=0;i<4;i++) {
  if(originals[i]&&munmap(originals[i],lengths[i])) result=-1;
  if(candidates[i]&&munmap(candidates[i],lengths[i])) result=-1;
  originals[i]=0;candidates[i]=0;lengths[i]=0;
  hn_changes[i].original.data=hn_changes[i].replacement.data=0;
 }
 loaded=0;return result;
}
int hn_data_load(int directory)
{
 const struct hn_stream io={rewind_input,read_input,0};
 unsigned int i,j;struct input in;int fd=-1;
 if(loaded||directory<0||metadata(directory,1,0)) return -1;
 hn_data_diagnostic=100;if(hn_memory_guard()) return -1;
 for(i=0;i<4;i++) {
  char name[2]={(char)('0'+i),0};unsigned char *candidate;void *source;
  hn_data_diagnostic=101+i;
  if(hn_plans[i].target!=i||hn_plan_valid(&hn_plans[i])||!hn_modes[i]||hn_modes[i]&~0777U||hn_modes[i]&0022U) goto fail;
  fd=openat(directory,name,2048|H_NOFOLLOW|H_CLOEXEC);
  if(fd<0||metadata(fd,0,hn_plans[i].size)) goto fail;
  source=mmap(0,hn_plans[i].size,1,2,fd,0);
  if(source==(void *)-1||!source) goto fail;
  originals[i]=source;lengths[i]=hn_plans[i].size;
  candidate=mmap(0,hn_plans[i].size,3,2,fd,0);
  if(candidate==(void *)-1||!candidate) goto fail;
  candidates[i]=candidate;
  if(close(fd)) { fd=-1;goto fail; }fd=-1;
  in.p=source;in.length=hn_plans[i].size;in.at=0;
  if(hn_preflight(&io,&in,&hn_plans[i])) goto fail;
  for(j=0;j<hn_plans[i].width;j++) candidate[hn_plans[i].offset+j]=hn_plans[i].replacement[j];
  in.p=candidate;
  if(hn_verify(&io,&in,&hn_plans[i],HN_REPLACEMENT)||mprotect(candidate,hn_plans[i].size,1)) goto fail;
  in.p=source;if(hn_verify(&io,&in,&hn_plans[i],HN_ORIGINAL)) goto fail;
  hn_changes[i]=(struct hearth_file_change){i,1,{source,hn_plans[i].size},{candidate,hn_plans[i].size},hn_modes[i],hn_modes[i]};
 }
 hn_data_diagnostic=106;if(hn_memory_guard()) goto fail;
 loaded=1;hn_data_diagnostic=0;return 0;
fail:
 if(fd>=0) close(fd);
 hn_data_release();return -1;
}
int hn_space_guard(int fd,int restoring)
{
 unsigned int i,total=0,largest=0,block,available;
 if(!loaded||(restoring!=0&&restoring!=1)) return -1;
 for(i=0;i<4;i++) { total+=hn_plans[i].size;if(hn_plans[i].size>largest) largest=hn_plans[i].size; }
#ifdef HEARTH_HOST_LAB
 { struct statfs s;if(fstatfs(fd,&s)) return -1;block=(unsigned int)s.f_bsize;available=(unsigned int)s.f_bavail; }
#else
 { unsigned long long s[16];unsigned char *b=(unsigned char *)s;
   if(syscall(100,fd,s)||word(b)!=0x72b6||!(word(b+44)&1U)) return -1;
   block=word(b+4);available=word(b+16);
 }
#endif
 if(!block||block>65536||(unsigned long long)block*available>0xffffffffULL) return -1;
 hn_space_available=block*available;
 /* Account for backups, staging and one large restore temporary. Reported
  * JFFS2 space includes dirty/reclaimable bytes; this is not a guarantee. */
 hn_space_required=restoring?largest+4U*1048576U:3U*total+2U*1048576U;
 return hn_space_available>=hn_space_required?0:-1;
}
