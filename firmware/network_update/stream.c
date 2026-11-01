/* Original full-file hash/span binding with4KiB scratch, MIT.
 * A failed copy can leave a partial temporary. It never activates or restores a
 * live path; the separate scoped transaction adapter must own that lifecycle. */
#include "stream.h"
static int same(const unsigned char *a,const unsigned char *b,unsigned int n)
{ unsigned int d=0,i;for(i=0;i<n;i++) d|=a[i]^b[i];return !d; }
int hn_plan_valid(const struct hn_plan *p)
{
 static const unsigned int limits[4]={6U*1048576U,1048576U,65536U,65536U};
 unsigned int i,a=0,b=0;
 if(!p||p->target>=4||!p->size||p->size>limits[p->target]||!p->width||p->width>64||
    p->width>p->size||p->offset>p->size-p->width||same(p->original,p->replacement,p->width)||
    same(p->original_hash,p->replacement_hash,32)) return -1;
 for(i=0;i<32;i++) { a|=p->original_hash[i];b|=p->replacement_hash[i]; }
 return a&&b ? 0 : -1;
}
static int process(const struct hn_stream *io,void *ctx,const struct hn_plan *p,
                   enum hn_content input,enum hn_content output,int copying)
{
 struct hn_hash source,destination;unsigned char buffer[4096],digest[32],extra;
 unsigned int at=0,retries=0;
 if(!io||!ctx||!io->rewind||!io->read||(copying&&!io->write)||hn_plan_valid(p)||
    (input!=HN_ORIGINAL&&input!=HN_REPLACEMENT)||
    (output!=HN_ORIGINAL&&output!=HN_REPLACEMENT)||
    (input==HN_REPLACEMENT&&output!=input)||io->rewind(ctx)) return -1;
 hn_hash_init(&source);hn_hash_init(&destination);
 while(at<p->size) {
  unsigned int amount=p->size-at,i,written=0;long n;
  if(amount>sizeof(buffer)) amount=sizeof(buffer);
  n=io->read(ctx,buffer,amount);
  if(n==-4&&retries++<64) continue;
  if(n<=0||(unsigned long)n>amount) return -1;
  retries=0;
  if(hn_hash_update(&source,buffer,(unsigned int)n)) return -1;
  for(i=0;i<(unsigned int)n;i++) if(at+i>=p->offset&&at+i-p->offset<p->width) {
   unsigned int index=at+i-p->offset;
   unsigned char expected=input==HN_ORIGINAL?p->original[index]:p->replacement[index];
   if(buffer[i]!=expected) return -1;
   if(output==HN_REPLACEMENT) buffer[i]=p->replacement[index];
  }
  if(hn_hash_update(&destination,buffer,(unsigned int)n)) return -1;
  while(copying&&written<(unsigned int)n) {
   long k=io->write(ctx,buffer+written,(unsigned int)n-written);
   if(k==-4&&retries++<64) continue;
   if(k<=0||(unsigned long)k>(unsigned int)n-written) return -1;
   retries=0;written+=(unsigned int)k;
  }
  at+=(unsigned int)n;
 }
 retries=0;
 for(;;) {
  long n=io->read(ctx,&extra,1);
  if(n==-4&&retries++<64) continue;
  if(n) return -1;
  break;
 }
 if(hn_hash_final(&source,digest)) return -1;
 if(!same(digest,input==HN_ORIGINAL?p->original_hash:p->replacement_hash,32)) return -1;
 if(hn_hash_final(&destination,digest)) return -1;
 return same(digest,output==HN_ORIGINAL?p->original_hash:p->replacement_hash,32)?0:-1;
}
int hn_preflight(const struct hn_stream *io,void *ctx,const struct hn_plan *p)
{ return process(io,ctx,p,HN_ORIGINAL,HN_REPLACEMENT,0); }
int hn_copy(const struct hn_stream *io,void *ctx,const struct hn_plan *p,enum hn_content output)
{ return process(io,ctx,p,HN_ORIGINAL,output,1); }
int hn_verify(const struct hn_stream *io,void *ctx,const struct hn_plan *p,enum hn_content content)
{ return process(io,ctx,p,content,content,0); }
