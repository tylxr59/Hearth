/* Original trusted-host memory-only streaming harness, MIT. No device API. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../firmware/network_update/stream.h"
#include "network_memory.h"
int main(int argc,char **argv)
{
 struct hn_plan plan;struct memory memory={0};
 struct hn_stream io={rewind_memory,read_memory,write_memory};
 unsigned int report[5];int status;
 assert(argc==3);
 if(!strcmp(argv[1],"hash")) {
  struct hn_hash h;unsigned char buffer[4096],digest[32];unsigned int amount=(unsigned int)atoi(argv[2]);size_t n;
  assert(amount>0&&amount<=sizeof(buffer));hn_hash_init(&h);
  while((n=fread(buffer,1,amount,stdin))) if(hn_hash_update(&h,buffer,(unsigned int)n)) return 2;
  assert(!ferror(stdin));assert(hn_hash_final(&h,digest)==0);
  assert(hn_hash_final(&h,digest)==-1);assert(hn_hash_update(&h,buffer,0)==-1);
  assert(fwrite(digest,1,sizeof(digest),stdout)==sizeof(digest));return 0;
 }
 assert(fread(&plan,1,sizeof(plan),stdin)==sizeof(plan));
 memory.input=malloc(HN_HASH_LIMIT+1U);memory.output=malloc(HN_HASH_LIMIT);assert(memory.input&&memory.output);
 memory.length=(unsigned int)fread(memory.input,1,HN_HASH_LIMIT+1U,stdin);assert(!ferror(stdin));
 memory.fault=atoi(argv[2]);
 if(!strcmp(argv[1],"preflight")) status=hn_preflight(&io,&memory,&plan);
 else if(!strcmp(argv[1],"copy")) status=hn_copy(&io,&memory,&plan,HN_REPLACEMENT);
 else if(!strcmp(argv[1],"original")) status=hn_copy(&io,&memory,&plan,HN_ORIGINAL);
 else if(!strcmp(argv[1],"verify")) status=hn_verify(&io,&memory,&plan,HN_REPLACEMENT);
 else { assert(0);return 1; }
 report[0]=(unsigned int)status;report[1]=memory.reads;report[2]=memory.writes;report[3]=memory.rewinds;report[4]=memory.out;
 assert(fwrite(report,1,sizeof(report),stdout)==sizeof(report));
 assert(fwrite(memory.output,1,memory.out,stdout)==memory.out);
 free(memory.input);free(memory.output);return 0;
}
