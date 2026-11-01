/* Original bounded SHA-256, MIT; public algorithm/number constants, no copied implementation. */
#include "hash.h"
_Static_assert(sizeof(unsigned int)==4,"32-bit words required");
static const unsigned int k[64]={
 0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,
 0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,
 0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,
 0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,
 0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,
 0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,
 0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,
 0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U};
static unsigned int rotr(unsigned int x,unsigned int n) { return (x>>n)|(x<<(32-n)); }
static unsigned int be(const unsigned char *p)
{ return (unsigned int)p[0]<<24|(unsigned int)p[1]<<16|(unsigned int)p[2]<<8|p[3]; }
static void block(struct hn_hash *c)
{
 unsigned int w[64],a,b,d,e,f,g,h,j,t1,t2,i;
 for(i=0;i<16;i++) w[i]=be(c->block+4*i);
 for(i=16;i<64;i++) {
  unsigned int x=w[i-15],y=w[i-2];
  w[i]=w[i-16]+(rotr(x,7)^rotr(x,18)^(x>>3))+w[i-7]+(rotr(y,17)^rotr(y,19)^(y>>10));
 }
 a=c->state[0];b=c->state[1];j=c->state[2];d=c->state[3];
 e=c->state[4];f=c->state[5];g=c->state[6];h=c->state[7];
 for(i=0;i<64;i++) {
  t1=h+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^(~e&g))+k[i]+w[i];
  t2=(rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&j)^(b&j));
  h=g;g=f;f=e;e=d+t1;d=j;j=b;b=a;a=t1+t2;
 }
 c->state[0]+=a;c->state[1]+=b;c->state[2]+=j;c->state[3]+=d;
 c->state[4]+=e;c->state[5]+=f;c->state[6]+=g;c->state[7]+=h;
}
void hn_hash_init(struct hn_hash *c)
{
 static const unsigned int initial[8]={0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U};
 unsigned int i;for(i=0;i<8;i++) c->state[i]=initial[i];c->total=0;c->used=0;
}
int hn_hash_update(struct hn_hash *c,const unsigned char *p,unsigned int length)
{
 unsigned int i;
 if(!c||(!p&&length)||c->total>HN_HASH_LIMIT||length>HN_HASH_LIMIT-c->total||c->used>=64) return -1;
 c->total+=length;
 for(i=0;i<length;i++) { c->block[c->used++]=p[i];if(c->used==64) { block(c);c->used=0; } }
 return 0;
}
int hn_hash_final(struct hn_hash *c,unsigned char out[32])
{
 unsigned int bits,i;
 if(!c||!out||c->used>=64||c->total>HN_HASH_LIMIT) return -1;
 bits=c->total*8U;
 c->block[c->used++]=0x80;
 if(c->used>56) { while(c->used<64) c->block[c->used++]=0;block(c);c->used=0; }
 while(c->used<60) c->block[c->used++]=0;
 for(i=0;i<4;i++) c->block[60+i]=(unsigned char)(bits>>(24-8*i));
 block(c);
 for(i=0;i<32;i++) out[i]=(unsigned char)(c->state[i/4]>>(24-8*(i%4)));
 /* Consume context so repeated final/update is not silently accepted. */
 c->used=64;
 return 0;
}
