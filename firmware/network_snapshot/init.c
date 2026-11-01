/* Original cached read-only four-file supervisor (MIT). No firmware execution. */
#include "reader.h"
#include "session.h"
#include "syscalls.h"
void *memset(void *memory,int value,hearth_file_size length)
{ unsigned char *p=memory;while(length--) *p++=(unsigned char)value;return memory; }
static unsigned char payload[HNS_CAPACITY];
static unsigned int size;
static void put(unsigned char *p,unsigned int n)
{ unsigned int i;for(i=0;i<4;i++) p[i]=(unsigned char)(n>>(8*i)); }
static unsigned int crc(const unsigned char *p,unsigned int n)
{
 unsigned int value=~0U,i,j;
 for(i=0;i<n;i++) { value^=p[i];for(j=0;j<8;j++) value=(value>>1)^((0U-(value&1U))&0xedb88320U); }
 return ~value;
}
static int capture(void)
{
 int root=-1,status=-1;unsigned int i,fs[6];struct hns_file f;
 if(raw(39,(long)"/native",0700,0,0,0)||
    raw(21,(long)"mtd:root0",(long)"/native",(long)"jffs2",1039,0)) return -1;
 root=openat(-100,"/native",16384|32768|524288);
 if(root<0||hns_filesystem(root,fs)) goto done;
 put(payload,0);put(payload+4,HNS_COUNT);size=32;
 for(i=0;i<6;i++) put(payload+8+4*i,fs[i]);
 for(i=0;i<HNS_COUNT;i++) {
  if(size>sizeof(payload)-24U||hns_limits[i]>sizeof(payload)-size-24U||
     hns_capture_file(root,0,0,i,payload+size+24,hns_limits[i],&f)) goto done;
  put(payload+size,f.target);put(payload+size+4,f.existed);put(payload+size+8,f.mode);
  put(payload+size+12,f.owner);put(payload+size+16,f.group);put(payload+size+20,f.size);
  size+=24U+f.size;
 }
 status=0;
done:
 if(root>=0&&close(root)) status=-1;
 if(status) { memset(payload,0,sizeof(payload));size=0; }
 return status;
}
static int send_all(long fd,const unsigned char *p,unsigned int n)
{
 unsigned int at=0,retries=0;long pause[2]={0,10000000};
 while(at<n) {
  long count=raw(4,fd,(long)(p+at),n-at,0,0);
  if(count>0&&(unsigned long)count<=n-at) { at+=(unsigned int)count;retries=0; }
  else if((count==-11||count==-4)&&retries++<500) raw(162,(long)pause,0,0,0,0);
  else return -1;
 }
 return 0;
}
void __attribute__((noreturn)) _start(void)
{
 unsigned char header[48]={'H','N','S','N','A','P','1','\n'};
 static const unsigned char footer[]="HNSEND1\n",failure[]="HEARTH_NETWORK_SNAPSHOT_FAILED_V1\n";
 long pause[2]={1,0};unsigned int i;int failed;
 failed=raw(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
        raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
        raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755");
 if(!failed) failed=capture();
 for(i=0;i<32;i++) header[8+i]=hearth_session[i];
 put(header+40,size);put(header+44,crc(payload,size));
 for(;;) {
  long fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
  if(fd>=0) {
   if(failed) send_all(fd,failure,sizeof(failure)-1);
   else if(!send_all(fd,header,sizeof(header))&&!send_all(fd,payload,size)) send_all(fd,footer,sizeof(footer)-1);
   raw(6,fd,0,0,0,0);
  }
  raw(162,(long)pause,0,0,0,0);
 }
}
