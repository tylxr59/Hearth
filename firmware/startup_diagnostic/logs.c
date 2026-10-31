/* Original MIT. No write, exec, networking or symlink traversal operation. */
#include "logs.h"
struct state { const struct hfd_ops *ops;unsigned char *out;unsigned int capacity,at,files,scanned,status; };
static void put(unsigned char *p,unsigned int n)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(n>>(8*i)); }
static unsigned int word16(const unsigned char *p) { return p[0]|(unsigned int)p[1]<<8; }
static int equal(const struct hfd_stat *a,const struct hfd_stat *b)
{ return a->mode==b->mode&&a->owner==b->owner&&a->group==b->group&&a->size==b->size; }
static void walk(struct state *s,int parent,const char *prefix,unsigned int length,unsigned int depth)
{
 unsigned char entries[4096];long amount;unsigned int pos,i;
 if(depth>4) { s->status=2;return; }
 if(s->ops->directory(parent)) { s->status=1;return; }
 while((amount=s->ops->entries(parent,entries,sizeof(entries)))>0) {
  if((unsigned long)amount>sizeof(entries)) { s->status=1;return; }
  pos=0;
  while(pos<(unsigned long)amount) {
   unsigned int record,n=0,path_length,tail,at;char path[240],name[240];int fd;
   struct hfd_stat before,after;
   if((unsigned long)amount-pos<20) { s->status=1;return; }
   record=word16(entries+pos+16);
   if(record<20||record>(unsigned long)amount-pos) { s->status=1;return; }
   while(19+n<record&&entries[pos+19+n]) {
    unsigned char c=entries[pos+19+n];
    if(n>=sizeof(name)-1||c<' '||c>'~'||c=='/') { s->status=1;return; }
    name[n++]=(char)c;
   }
   if(!n||19+n>=record) { s->status=1;return; }
   name[n]=0;pos+=record;
   if((n==1&&name[0]=='.')||(n==2&&name[0]=='.'&&name[1]=='.')) continue;
   if(++s->scanned>512||s->files>=HFD_FILES) { s->status=2;return; }
   path_length=length+(length?1U:0U)+n;
   if(path_length>=sizeof(path)) { s->status=2;continue; }
   for(i=0;i<length;i++) path[i]=prefix[i];
   if(length) path[length]='/';
   for(i=0;i<n;i++) path[length+(length?1U:0U)+i]=name[i];
   path[path_length]=0;
   /* getdents d_type is only a hint. O_NOFOLLOW|O_NONBLOCK and fstat below
    * enforce type without following links or blocking on substituted FIFOs. */
   if(entries[pos-record+18]==10) continue;
   fd=s->ops->open(parent,name);
   if(fd<0) { s->status=1;return; }
   if(s->ops->metadata(fd,&before)) { s->ops->close(fd);s->status=1;return; }
   if((before.mode&0170000)==0040000) walk(s,fd,path,path_length,depth+1);
   else if((before.mode&0170000)==0100000) {
    tail=before.size>HFD_TAIL?HFD_TAIL:before.size;
    if(s->at>s->capacity||24U+path_length+tail>s->capacity-s->at) { s->status=2;s->ops->close(fd);return; }
    if(before.size>0x7fffffffU||s->ops->seek(fd,before.size-tail)!=(long)(before.size-tail)) { s->ops->close(fd);s->status=1;return; }
    put(s->out+s->at,path_length);put(s->out+s->at+4,before.mode);
    put(s->out+s->at+8,before.owner);put(s->out+s->at+12,before.group);
    put(s->out+s->at+16,before.size);put(s->out+s->at+20,tail);
    at=s->at+24;
    for(i=0;i<path_length;i++) s->out[at++]=(unsigned char)path[i];
    i=0;
    while(i<tail) {
     long count=s->ops->read(fd,s->out+at+i,tail-i);
     if(count<=0||(unsigned long)count>tail-i) { s->ops->close(fd);s->status=1;return; }
     i+=(unsigned int)count;
    }
    if(s->ops->metadata(fd,&after)||!equal(&before,&after)) { s->ops->close(fd);s->status=1;return; }
    s->at=at+tail;s->files++;
   }
   if(s->ops->close(fd)) { s->status=1;return; }
   if(s->status) return;
  }
 }
 if(amount<0) s->status=1;
}
unsigned int hfd_capture(const struct hfd_ops *ops,int root,unsigned char *out,unsigned int capacity)
{
 struct state s={ops,out,capacity,16,0,0,0};
 if(!ops||!out||capacity<16||!ops->open||!ops->close||!ops->metadata||!ops->directory||
    !ops->entries||!ops->read||!ops->seek) return 0;
 walk(&s,root,"",0,0);
 put(out,s.status);put(out+4,s.files);put(out+8,s.scanned);put(out+12,s.status==2);
 return s.at;
}
