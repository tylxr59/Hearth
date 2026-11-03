/* Original MIT. Included only in the fixed network adapter translation unit.
 * Reuse exactly matching, already-restored originals. Never mutate their data,
 * metadata permissions, old journal or names. Every new reference is verified. */
#include "../network_update/hash.h"
#ifdef HEARTH_HOST_LAB
#include <sys/syscall.h>
#define HN_SHARED_DENTS SYS_getdents64
#else
#define HN_SHARED_DENTS 217
extern int ioctl(int,unsigned long,...);
#endif
static unsigned int shared_word(const unsigned char *p)
{ return p[0]|(unsigned int)p[1]<<8|(unsigned int)p[2]<<16|(unsigned int)p[3]<<24; }
static int shared_same(const char *a,const char *b)
{ unsigned int i=0;while(a[i]&&b[i]&&a[i]==b[i]) i++;return a[i]==b[i]; }
static int shared_spec(struct hearth_posix_context *c)
{
 static const char prefix[]=".hearth-rollback-",hex[]="0123456789abcdef";
 unsigned int i,other=0;const struct hn_shared_archive *s=c->shared;
 if(!s||c->count!=3||c->archive_layout!=1||!equal(s->journal,(const unsigned char *)"HFI1",4)||
    shared_word(s->journal+4)!=HEARTH_RESTORED||shared_word(s->journal+8)!=15||shared_word(s->journal+12)!=4) return -1;
 for(i=0;i<sizeof(prefix)-1;i++) if(s->directory[i]!=prefix[i]) return -1;
 for(i=0;i<32;i++) {
  unsigned int n=sizeof(prefix)-1+2*i;unsigned char v=s->journal[16+i];
  if(s->directory[n]!=hex[v>>4]||s->directory[n+1]!=hex[v&15]) return -1;
  other|=v^c->plan_id[i];
 }
 if(!other) return -1;
 for(i=sizeof(prefix)-1+64;i<sizeof(s->directory);i++) if(s->directory[i]) return -1;
 for(i=0;i<4;i++) {
  unsigned int limit=i==0?6U*1048576U:i==1?1048576U:65536U;
  if(!s->sizes[i]||s->sizes[i]>limit) return -1;
  if(i<3) {
   struct hn_hash h;unsigned char digest[32];const struct hearth_file_change *f=&c->changes[i];
   if(f->target!=i||!f->existed||!f->original.data||f->original.size!=s->sizes[i]) return -1;
   hn_hash_init(&h);if(hn_hash_update(&h,f->original.data,s->sizes[i])||hn_hash_final(&h,digest)||
      !equal(digest,s->hashes[i],32)) return -1;
  }
 }
 return 0;
}
static int shared_inventory(int fd)
{
 unsigned char data[2048];unsigned int seen=0,entries=0;long count;
 while((count=syscall(HN_SHARED_DENTS,fd,data,(long)sizeof(data)))>0) {
  unsigned int at=0;if((unsigned long)count>sizeof(data)) return -1;
  while(at<(unsigned long)count) {
   char name[128];unsigned int n=0,length,bit=0;
   if((unsigned long)count-at<20||++entries>32) return -1;
   length=data[at+16]|(unsigned int)data[at+17]<<8;
   if(length<20||length>(unsigned long)count-at) return -1;
   while(19+n<length&&data[at+19+n]) {
    if(n>=sizeof(name)-1||data[at+19+n]=='/') return -1;
    name[n]=(char)data[at+19+n];n++;
   }
   if(!n||19+n>=length) return -1;name[n]=0;at+=length;
   if(shared_same(name,".")||shared_same(name,"..")) continue;
   if(shared_same(name,"journal")) bit=16;
   else if(n==10&&name[0]>='0'&&name[0]<='3'&&shared_same(name+1,".original")) bit=1U<<(name[0]-'0');
   if(!bit||(seen&bit)) return -1;seen|=bit;
  }
 }
 return count==0&&seen==31 ? 0 : -1;
}
static int shared_open(struct hearth_posix_context *c)
{
 int fd;struct metadata m,root;
 if(shared_spec(c)) return -1;
 fd=openat(c->roots[1],c->shared->directory,H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
 if(fd<0) return -1;
 if(local_root(c,fd)||metadata(fd,&m)||metadata(c->roots[1],&root)||
    m.device!=root.device||(m.mode&07777)!=0700||m.group!=c->group||no_attributes(fd)||
    contents(fd,"journal",(struct hearth_file_bytes){c->shared->journal,48},0600,c)||shared_inventory(fd)) {
  close(fd);return -1;
 }
 return fd;
}
static int shared_hash_file(struct hearth_posix_context *c,int directory,unsigned int index,
                           unsigned int links,struct metadata *out)
{
 unsigned char buffer[4096],digest[32];struct hn_hash hash;unsigned int at=0;char name[16];
 int fd,result=-1;struct metadata m,root;
 backup_name(index,name);fd=openat(directory,name,H_RDONLY|H_NONBLOCK|H_NOFOLLOW|H_CLOEXEC);
 if(fd<0) return -1;
 if(metadata(fd,&m)||metadata(c->roots[1],&root)||m.device!=root.device||!m.inode||
    (m.mode&0177777)!=0100600||m.links!=links||m.owner!=c->owner||m.group!=c->group||
    m.size!=c->shared->sizes[index]||no_attributes(fd)) goto done;
#if !defined(HEARTH_HOST_LAB) && !defined(HEARTH_RAM_LAB)
 if(ioctl(fd,0x4871U,0UL)) goto done;
#endif
 hn_hash_init(&hash);
 while(at<c->shared->sizes[index]) {
  unsigned int amount=c->shared->sizes[index]-at;long n;if(amount>sizeof(buffer)) amount=sizeof(buffer);
  n=read(fd,buffer,amount);if(n<0&&*__errno_location()==4) continue;
  if(n<=0||(unsigned long)n>amount||hn_hash_update(&hash,buffer,(unsigned int)n)) goto done;
  at+=(unsigned int)n;
 }
 if(read(fd,buffer,1)||hn_hash_final(&hash,digest)||!equal(digest,c->shared->hashes[index],32)) goto done;
 if(out) *out=m;result=0;
done:
 if(close(fd)) result=-1;return result;
}
int hn_shared_contents(struct hearth_posix_context *c,unsigned int index,const char *name)
{
 int old,result=-1;struct metadata a,b;char expected[16];
 if(index>=3||c->recovery<0) return -1;
 backup_name(index,expected);if(!shared_same(name,expected)) return -1;
 old=shared_open(c);if(old<0) return -1;
 if(!shared_hash_file(c,old,index,2,&a)&&!shared_hash_file(c,c->recovery,index,2,&b)&&
    a.device==b.device&&a.inode==b.inode&&
    !contents_links(c->recovery,name,c->changes[index].original,0600,c,2)) result=0;
 if(close(old)) result=-1;return result;
}
int hn_shared_preflight(struct hearth_posix_context *c,int restoring)
{
 int old,current=-1,result=-1;unsigned int i;char archive[96];const char *name;
 if(restoring!=0&&restoring!=1) return -1;
 old=shared_open(c);if(old<0) return -1;
 name=recovery_name(c,archive);if(!name) goto done;
 if(restoring) {
  struct metadata m;int status=absent(c->roots[1],name);
  if(status<0) goto done;
  if(!status) {
   current=openat(c->roots[1],name,H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
   if(current<0||local_root(c,current)||metadata(current,&m)||(m.mode&07777)!=0700||
      m.group!=c->group||no_attributes(current)) goto done;
  }
 }
 for(i=0;i<4;i++) {
  unsigned int links=1;struct metadata a,b;char backup[16];backup_name(i,backup);
  if(restoring&&i<3&&current>=0) {
   int status=absent(current,backup);if(status<0) goto done;
   if(!status) {
    links=2;if(shared_hash_file(c,current,i,2,&b)) goto done;
   }
  }
  if(shared_hash_file(c,old,i,links,&a)) goto done;
  if(links==2&&(a.device!=b.device||a.inode!=b.inode)) goto done;
 }
 result=0;
done:
 if(current>=0&&close(current)) result=-1;
 if(close(old)) result=-1;return result;
}
int hn_shared_stage(struct hearth_posix_context *c,unsigned int index,const char *name)
{
 int old,result=-1;char expected[16];
 if(index>=3||c->recovery<0) return -1;
 backup_name(index,expected);if(!shared_same(name,expected)) return -1;
 old=shared_open(c);if(old<0) return -1;
 if(shared_hash_file(c,old,index,1,0)||linkat(old,name,c->recovery,name,0)) goto done;
 c->created[index]|=1U;
 if(!fsync(old)&&!fsync(c->recovery)&&!hn_shared_contents(c,index,name)) result=0;
done:
 if(close(old)) result=-1;return result;
}
