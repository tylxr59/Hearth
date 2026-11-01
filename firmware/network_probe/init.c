/* Original protected RAM-only network adapter/preflight supervisor, MIT.
 * Kernel denies flash writes. Root0 is mounted read-only only AFTER synthetic
 * tests. The only child is our original RAM filesystem harness as UID65534. */
#ifdef HEARTH_WRITER_ACTION
#if HEARTH_WRITER_ACTION != 1 && HEARTH_WRITER_ACTION != 2
#error "Only the reviewed install/restore bootstrap actions are supported"
#endif
typedef __SIZE_TYPE__ hearth_file_size;
#else
#include "../network_snapshot/reader.h"
#endif
#include "../network_snapshot/syscalls.h"
#include "../network_update/stream.h"
#include "../network_update/ram.h"
#include "plan.h"
#include "session.h"
void *memset(void *p,int value,hearth_file_size n)
{ unsigned char *b=p;while(n--) *b++=(unsigned char)value;return p; }
#ifndef HEARTH_WRITER_ACTION
static unsigned char cache[HNS_CAPACITY];
#endif
static unsigned char report[4096],errors[1024];
static unsigned int used,error_bytes,stream_cases,transaction_cases,real_files;
static int child_status=-1,phase;
static long now(void)
{ long v[2]={0,0};return raw(263,1,(long)v,0,0,0)==0?v[0]:-1; }
static void pause_short(void) { long t[2]={0,10000000};raw(162,(long)t,0,0,0,0); }
static void append(const char *s)
{ while(*s&&used<sizeof(report)-64) report[used++]=(unsigned char)*s++; }
static void number(long n)
{
 char digits[16];unsigned int count=0;unsigned long x;
 if(n<0) append("-");x=n<0?0UL-(unsigned long)n:(unsigned long)n;
 do { digits[count++]=(char)('0'+x%10);x/=10; }while(x);
 while(count) { char one[2]={digits[--count],0};append(one); }
}
static int run_case(unsigned int scenario,long deadline)
{
 int pipes[2],pid,status=-1,pollfd[2];long n;
 char digits[3],path[]="/state/transaction-00";
 digits[0]=(char)('0'+scenario/10);digits[1]=(char)('0'+scenario%10);digits[2]=0;
 path[19]=digits[0];path[20]=digits[1];
 if(raw(42,(long)pipes,0,0,0,0)) return -1;
 pid=(int)raw(2,0,0,0,0,0);
 if(pid==0) {
  char *const args[]={"/network-transaction",digits,path,0};
  char *const env[]={"LD_LIBRARY_PATH=/lib","HOME=/nonexistent","LC_ALL=C",0};
  int i;long fd;
  if(raw(57,0,0,0,0,0)||raw(63,pipes[1],1,0,0,0)<0||raw(63,pipes[1],2,0,0,0)<0) goto child_failed;
  fd=raw(5,(long)"/dev/null",2,0,0,0);if(fd<0||raw(63,fd,0,0,0,0)<0) goto child_failed;
  for(i=3;i<64;i++) raw(6,i,0,0,0,0);
  if(raw(206,0,0,0,0,0)||raw(214,65534,0,0,0,0)||raw(213,65534,0,0,0,0)) goto child_failed;
  raw(11,(long)args[0],(long)args,(long)env,0,0);
child_failed:
  raw(248,130,0,0,0,0);for(;;) pause_short();
 }
 raw(6,pipes[1],0,0,0,0);
 if(pid<0) { raw(6,pipes[0],0,0,0,0);return -1; }
 if(raw(55,pipes[0],4,2048,0,0)) goto stop;
 for(;;) {
  long clock=now();if(clock<0||clock>deadline) goto stop;
  pollfd[0]=pipes[0];pollfd[1]=1;
  n=raw(168,(long)pollfd,1,500,0,0);if(n<0) goto stop;
  if(!n) continue;
  n=raw(3,pipes[0],(long)errors,sizeof(errors),0,0);
  if(n==-11||n==-4) continue;
  if(n>0) { error_bytes=(unsigned int)n;goto stop; }
  if(n<0) goto stop;
  raw(6,pipes[0],0,0,0,0);
  if(raw(114,pid,(long)&status,0,0,0)!=pid) return -1;
  return status;
 }
stop:
 raw(37,-pid,9,0,0,0);raw(37,pid,9,0,0,0);raw(6,pipes[0],0,0,0,0);
 raw(114,pid,(long)&status,0,0,0);return status?status:-1;
}
#ifndef HEARTH_WRITER_ACTION
struct input { const unsigned char *data;unsigned int size,at; };
static int input_rewind(void *p) { ((struct input *)p)->at=0;return 0; }
static long input_read(void *p,unsigned char *out,unsigned int n)
{
 struct input *in=p;unsigned int i;if(n>in->size-in->at) n=in->size-in->at;
 for(i=0;i<n;i++) out[i]=in->data[in->at+i];in->at+=n;return n;
}
static int real_preflight(void)
{
 const struct hn_stream io={input_rewind,input_read,0};
 unsigned int i,offset=0,fs[6],present=0;struct hns_file file;struct input in;int fd,result=-1;
 for(i=0;i<32;i++) present|=hn_plan_id[i]|hn_receipt_id[i];if(!present) return -1;
 phase=51;
 if(raw(39,(long)"/native",0700,0,0,0)||raw(21,(long)"mtd:root0",(long)"/native",(long)"jffs2",1039,0)) return -1;
 phase=52;fd=openat(-100,"/native",16384|32768|524288);if(fd<0) return -1;
 phase=53;
 if(hns_filesystem(fd,fs)) goto done;
 for(i=0;i<4;i++) {
  phase=60+(int)i;
  if(hn_plans[i].target!=i||hn_plan_valid(&hn_plans[i])||
     hns_capture_file(fd,0,0,i,cache+offset,hns_limits[i],&file)||
     file.mode!=hn_modes[i]||file.size!=hn_plans[i].size) goto done;
  in.data=cache+offset;in.size=file.size;in.at=0;
  if(hn_preflight(&io,&in,&hn_plans[i])) goto done;
  offset+=hns_limits[i];real_files++;
 }
 result=0;
done:
 if(close(fd)) result=-1;
 if(raw(52,(long)"/native",0,0,0,0)) result=-1;
 return result;
}
#endif
static void put(unsigned char *p,unsigned int n)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(n>>(8*i)); }
static unsigned int crc(const unsigned char *p,unsigned int n)
{ unsigned int value=~0U,i,j;for(i=0;i<n;i++) { value^=p[i];for(j=0;j<8;j++) value=(value>>1)^((0U-(value&1U))&0xedb88320U); }return ~value; }
static int send_all(long fd,const unsigned char *p,unsigned int n)
{
 unsigned int at=0,retries=0;
 while(at<n) { long k=raw(4,fd,(long)(p+at),n-at,0,0);
  if(k>0&&(unsigned long)k<=n-at) { at+=(unsigned int)k;retries=0; }
  else if((k==-4||k==-11)&&retries++<500) pause_short();else return -1;
 }return 0;
}
void __attribute__((noreturn)) _start(void)
{
 unsigned int i,length;int success=0;long deadline;
#ifdef HEARTH_WRITER_ACTION
 long ack_started;
#endif
 phase=1;
 if(raw(21,(long)"proc",(long)"/proc",(long)"proc",14,0)||
    raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",14,0)||
    raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755")) goto emit;
 phase=2;if(hn_ram_selftest(&stream_cases)||stream_cases!=HN_RAM_CASES) goto emit;
 deadline=now();if(deadline<0) goto emit;deadline+=150;
 for(i=0;i<20;i++) { phase=10+(int)i;child_status=run_case(i,deadline);if(child_status) goto emit;transaction_cases++; }
#ifndef HEARTH_WRITER_ACTION
 phase=50;if(real_preflight()) goto emit;
#endif
 success=1;phase=0;
emit:
#ifdef HEARTH_WRITER_ACTION
 used=84;
#else
 used=48;
#endif
 append("{\"type\":\"network_ram_preflight\",\"stream_cases\":");number(stream_cases);
 append(",\"transaction_cases\":");number(transaction_cases);
 append(",\"child_status\":");number(child_status);append(",\"child_output_bytes\":");number(error_bytes);
 append(",\"real_files_checked\":");number(real_files);append(",\"real_preflight\":");
#ifdef HEARTH_WRITER_ACTION
 append("false");
#else
 append(success?"true":"false");
#endif
 append(",\"phase\":");number(phase);append(",\"flash_writes\":false,\"diagnostic_hex\":\"");
 for(i=0;i<error_bytes;i++) { static const char hex[]="0123456789abcdef";char pair[3]={hex[errors[i]>>4],hex[errors[i]&15],0};append(pair); }
 append("\"}\n");
#ifdef HEARTH_WRITER_ACTION
 length=used-84;
 for(i=0;i<8;i++) report[i]=(unsigned char)"HFW_TST1"[i];
 for(i=0;i<32;i++) { report[8+i]=hn_plan_id[i];report[40+i]=hn_receipt_id[i]; }
 put(report+72,HEARTH_WRITER_ACTION);put(report+76,length);put(report+80,crc(report+84,length));
 for(i=0;i<8;i++) report[used++]=(unsigned char)"HFW_END1"[i];
#else
 length=used-48;
 for(i=0;i<8;i++) report[i]=(unsigned char)"HNPREP1\n"[i];
 for(i=0;i<32;i++) report[8+i]=hearth_session[i];put(report+40,length);put(report+44,crc(report+48,length));
 for(i=0;i<8;i++) report[used++]=(unsigned char)"HNPEND1\n"[i];
#endif
#ifdef HEARTH_WRITER_ACTION
 ack_started=now();
#endif
 for(;;) {
#ifdef HEARTH_WRITER_ACTION
  /* An ACK launches only the root preflight/waiter. Persistent writes require
   * its DIFFERENT scoped commit, never accepted by this bootstrap. */
  long fd=raw(5,(long)"/dev/ttyGS0",2|0400|04000,0,0,0);
  if(fd>=0) {
   unsigned char ack[76],input[256];unsigned int matched=0;
   for(i=0;i<8;i++) ack[i]=(unsigned char)"HFW_ACK1"[i];
   for(i=0;i<32;i++) { ack[8+i]=hn_plan_id[i];ack[40+i]=hn_receipt_id[i]; }put(ack+72,HEARTH_WRITER_ACTION);
   while(ack_started>=0&&now()>=ack_started&&now()-ack_started<240) {
    long count;
    send_all(fd,report,used);
    count=raw(3,fd,(long)input,sizeof(input),0,0);
    if(count>0&&(unsigned long)count<=sizeof(input)) for(i=0;i<(unsigned int)count;i++) {
     if(input[i]==ack[matched]) matched++;else matched=input[i]==ack[0]?1U:0U;
     if(matched==sizeof(ack)&&success) {
      char *const args[]={"/file-action",0};
      char *const env[]={"LD_LIBRARY_PATH=/lib","HOME=/nonexistent","LC_ALL=C",0};
      raw(6,fd,0,0,0,0);raw(11,(long)args[0],(long)args,(long)env,0,0);
      for(;;) {
       static const unsigned char failure[]="HFW_BOOTSTRAP_FAILED_V1\n";
       long error_fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
       if(error_fd>=0) { send_all(error_fd,failure,sizeof(failure)-1);raw(6,error_fd,0,0,0,0); }
       { long t[2]={1,0};raw(162,(long)t,0,0,0,0); }
      }
     }
     if(matched==sizeof(ack)) matched=0;
    }
    { long t[2]={0,100000000};raw(162,(long)t,0,0,0,0); }
   }
   send_all(fd,report,used); /* Evidence only after ACK expiry; never re-arm. */
   raw(6,fd,0,0,0,0);
  }
#else
  long fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
  if(fd>=0) { send_all(fd,report,used);raw(6,fd,0,0,0,0); }
#endif
  { long t[2]={1,0};raw(162,(long)t,0,0,0,0); }
 }
}
