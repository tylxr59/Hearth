/* Original deterministic memory-only selftests, MIT. No syscall or live path. */
#include "ram.h"
#include "ram_vectors.h"
#include "../../tests/network_memory.h"
static unsigned char input[10244],output[10244];
static int equal_bytes(const unsigned char *a,const unsigned char *b,unsigned int n)
{ unsigned int i,d=0;for(i=0;i<n;i++) d|=a[i]^b[i];return !d; }
static void fixture(void)
{
 unsigned int i;for(i=0;i<10240;i++) input[i]=(unsigned char)i;
 input[10240]='t';input[10241]='a';input[10242]='i';input[10243]='l';
}
static void memory_init(struct memory *m,int fault)
{
 m->input=input;m->output=output;m->length=sizeof(input);
 m->at=0;m->out=0;m->reads=0;m->writes=0;m->rewinds=0;m->fault=fault;
}
static void plan_init(struct hn_plan *p,unsigned int variant)
{
 unsigned int i;p->target=0;p->size=sizeof(input);p->offset=hn_offsets[variant];p->width=40;
 for(i=0;i<40;i++) { p->original[i]=input[p->offset+i];p->replacement[i]='l'; }
 for(i=0;i<32;i++) { p->original_hash[i]=hn_original[i];p->replacement_hash[i]=hn_candidates[variant][i]; }
}
#define CHECK(condition) do { if(!(condition)) return -__LINE__; } while(0)
int hn_ram_selftest(unsigned int *cases)
{
 struct hn_hash h;struct hn_plan p;struct memory m;
 struct hn_stream io={rewind_memory,read_memory,write_memory};
 unsigned char digest[32];unsigned int i,j,left;int result;
 if(!cases) return -1;*cases=0;fixture();
 for(i=0;i<12;i++) {
  hn_hash_init(&h);
  for(j=0;j<hn_lengths[i];j++) CHECK(hn_hash_update(&h,input+j,1)==0);
  CHECK(hn_hash_final(&h,digest)==0&&equal_bytes(digest,hn_expected[i],32));(*cases)++;
 }
 for(i=0;i<4096;i++) input[i]='a';hn_hash_init(&h);left=1000000;
 while(left) { unsigned int n=left>4096?4096:left;CHECK(hn_hash_update(&h,input,n)==0);left-=n; }
 CHECK(hn_hash_final(&h,digest)==0&&equal_bytes(digest,hn_million,32));(*cases)++;
 hn_hash_init(&h);h.total=HN_HASH_LIMIT;CHECK(hn_hash_update(&h,input,1)==-1);(*cases)++;
 hn_hash_init(&h);CHECK(hn_hash_final(&h,digest)==0);
 CHECK(hn_hash_final(&h,digest)==-1&&hn_hash_update(&h,input,0)==-1);(*cases)++;
 fixture();
 for(i=0;i<4;i++) {
  plan_init(&p,i);memory_init(&m,0);
  CHECK(hn_preflight(&io,&m,&p)==0&&m.writes==0&&m.out==0);
  CHECK(hn_copy(&io,&m,&p,HN_REPLACEMENT)==0&&m.out==sizeof(input));
  for(j=0;j<sizeof(input);j++) CHECK(output[j]==(j>=p.offset&&j-p.offset<p.width?'l':input[j]));
  m.input=output;CHECK(hn_verify(&io,&m,&p,HN_REPLACEMENT)==0);
  memory_init(&m,0);CHECK(hn_copy(&io,&m,&p,HN_ORIGINAL)==0&&equal_bytes(input,output,sizeof(input)));(*cases)++;
 }
 plan_init(&p,1);
 for(i=1;i<=14;i++) {
  memory_init(&m,(int)i);result=hn_copy(&io,&m,&p,HN_REPLACEMENT);
  CHECK((result==0)==(i<=4));
  if(i<=4) for(j=0;j<sizeof(input);j++) CHECK(output[j]==(j>=p.offset&&j-p.offset<p.width?'l':input[j]));
  (*cases)++;
 }
 for(i=0;i<8;i++) {
  fixture();plan_init(&p,1);memory_init(&m,0);
  if(i==0) input[10243]^=1;
  if(i==1) input[p.offset]^=1;
  if(i==2) p.original_hash[0]^=1;
  if(i==3) p.replacement_hash[0]^=1;
  if(i==4) p.target=4;
  if(i==5) p.size=0;
  if(i==6) p.width=65;
  result=i==7?hn_verify(&io,&m,&p,(enum hn_content)2):hn_preflight(&io,&m,&p);
  CHECK(result==-1&&m.writes==0&&m.out==0);(*cases)++;
 }
 return *cases==HN_RAM_CASES?0:-2;
}
