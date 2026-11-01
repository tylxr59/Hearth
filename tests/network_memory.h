/* Original memory-only fault fixture, shared unchanged on host and ARM. */
#ifndef HEARTH_NETWORK_MEMORY_H
#define HEARTH_NETWORK_MEMORY_H
#include "../firmware/network_update/stream.h"
struct memory {
 unsigned char *input,*output;
 unsigned int length,at,out,reads,writes,rewinds;
 int fault;
};
static int rewind_memory(void *opaque)
{ struct memory *m=opaque;m->rewinds++;m->at=0;return m->fault==11?-1:0; }
static long read_memory(void *opaque,unsigned char *p,unsigned int n)
{
 struct memory *m=opaque;unsigned int amount=n;m->reads++;
 if(m->fault==3&&m->reads==1) return -4;
 if(m->fault==5&&m->reads==1) return -5;
 if(m->fault==13) return -4;
 if(m->fault==8&&m->reads==1) return 0;
 if(m->fault==9) return n+1U;
 if(m->at==m->length) { if(m->fault==12) { p[0]=42;return 1; }return 0; }
 if(amount>m->length-m->at) amount=m->length-m->at;
 if(m->fault==1&&amount>3) amount=3;
 { unsigned int i;for(i=0;i<amount;i++) p[i]=m->input[m->at+i]; }m->at+=amount;return amount;
}
static long write_memory(void *opaque,const unsigned char *p,unsigned int n)
{
 struct memory *m=opaque;unsigned int amount=n;m->writes++;
 if(m->fault==4&&m->writes==1) return -4;
 if(m->fault==6&&m->writes==1) return -28;
 if(m->fault==7) return 0;
 if(m->fault==10) return n+1U;
 if(m->fault==14) return -4;
 if(m->fault==2&&amount>3) amount=3;
 if(m->out>HN_HASH_LIMIT||amount>HN_HASH_LIMIT-m->out) return -1;
 { unsigned int i;for(i=0;i<amount;i++) m->output[m->out+i]=p[i]; }m->out+=amount;return amount;
}
#endif
