/* Original MIT. Protected snapshot plus bounded library/executable data export.
 * No native execution, flash write/erase, writable mount, networking or ioctls.
 */
#define _start hearth_snapshot_fallback_start
#include "../file_snapshot/init.c"
#undef _start
#include "../startup_diagnostic/logs.h"
#include "../network_snapshot/reader.h"
#define ACQ_LIMIT (16U*1024U*1024U)
static unsigned char acquisition[ACQ_LIMIT];
static unsigned int get32(const unsigned char *p)
{ return p[0]|(unsigned int)p[1]<<8|(unsigned int)p[2]<<16|(unsigned int)p[3]<<24; }
static int acq_open(int fd,const char *name)
{
 unsigned long long data[16];unsigned int type;
 /* Check without following links before opening: never open a device/FIFO. */
 if(raw(327,fd,(long)name,(long)data,256,0)) return -1;
 type=get32((unsigned char *)data+16)&0170000;
 if(type!=0040000&&type!=0100000) return -1;
 return (int)raw(322,fd,(long)name,2048|32768|524288,0,0);
}
static int acq_close(int fd) { return (int)raw(6,fd,0,0,0,0); }
static int acq_metadata(int fd,struct hfd_stat *m)
{
 unsigned long long data[16];unsigned char *p=(unsigned char *)data;
 if(raw(197,fd,(long)data,0,0,0)||get32(p+52)) return -1;
 m->mode=get32(p+16);m->owner=get32(p+24);m->group=get32(p+28);m->size=get32(p+48);return 0;
}
static int acq_directory(int fd)
{
 unsigned long long data[16];unsigned char *p=(unsigned char *)data;
 return raw(100,fd,(long)data,0,0,0)||get32(p)!=0x72b6||!(get32(p+44)&1)?-1:0;
}
static long acq_entries(int fd,unsigned char *out,unsigned int capacity)
{ return raw(217,fd,(long)out,capacity,0,0); }
static long acq_read(int fd,unsigned char *out,unsigned int capacity)
{ return raw(3,fd,(long)out,capacity,0,0); }
static long acq_seek(int fd,unsigned int at) { return raw(19,fd,at,0,0,0); }
static const struct hfd_ops ops={acq_open,acq_close,acq_metadata,acq_directory,acq_entries,acq_read,acq_seek};
static int await_session(int fd)
{
 unsigned char token[32];unsigned int at=0,attempts=0,i;long pause[2]={0,100000000};
 while(at<32&&attempts++<1200) {
  long n=raw(3,fd,(long)(token+at),32-at,0,0);
  if(n>0&&(unsigned long)n<=32-at) at+=(unsigned int)n;
  else if(n!=0&&n!=-11&&n!=-4) return -1;
  if(at<32) raw(162,(long)pause,0,0,0,0);
 }
 if(at!=32) return -1;
 for(i=0;i<32;i++) if(token[i]!=hearth_session[i]) return -1;
 return 0;
}
static int export_network(int fd)
{
 unsigned char header[48]={'H','N','S','N','A','P','1','\n'};
 unsigned int at=32,i,fs[6];int root,status=-1;struct hns_file f;
 root=openat(-100,"/native",16384|32768|524288);
 if(root<0) return -1;
 if(hns_filesystem(root,fs)) goto done;
 put(acquisition,0);put(acquisition+4,4);
 for(i=0;i<6;i++) put(acquisition+8+4*i,fs[i]);
 for(i=0;i<HNS_COUNT;i++) {
  if(at>sizeof(acquisition)-24U||hns_limits[i]>sizeof(acquisition)-at-24U||
     hns_capture_file(root,0,0,i,acquisition+at+24U,hns_limits[i],&f)) goto done;
  put(acquisition+at,f.target);put(acquisition+at+4,f.existed);put(acquisition+at+8,f.mode);
  put(acquisition+at+12,f.owner);put(acquisition+at+16,f.group);put(acquisition+at+20,f.size);
  at+=24U+f.size;
 }
 for(i=0;i<32;i++) header[8+i]=hearth_session[i];
 put(header+40,at);put(header+44,crc(acquisition,at));
 status=send_all(fd,header,sizeof(header))||send_all(fd,acquisition,at)||send_all(fd,(const unsigned char *)"HNSEND1\n",8);
done:
 if(close(root)) status=-1;
 return status;
}
static int export_groups(int fd)
{
 const char *paths[4]={"/native/lib","/native/usr/lib","/native/nestlabs/lib","/native/nestlabs/sbin"};
 const unsigned char footer[]="HACQEND1";
 unsigned int i,j,length;int root;
 for(i=0;i<4;i++) {
  unsigned char header[52]={'H','A','C','Q','L','I','B','1'};
  root=(int)raw(5,(long)paths[i],16384|32768|524288,0,0,0);
  if(root<0) return -1;
  length=hfd_capture(&ops,root,acquisition,sizeof(acquisition));
  if(acq_close(root)||length<16||get32(acquisition)!=0) return -1;
  for(j=0;j<32;j++) header[8+j]=hearth_session[j];
  put(header+40,i);put(header+44,length);put(header+48,crc(acquisition,length));
  if(send_all(fd,header,sizeof(header))||send_all(fd,acquisition,length)||send_all(fd,footer,8)) return -1;
 }
 return send_all(fd,(const unsigned char *)"HACQDONE",8);
}
void __attribute__((noreturn)) _start(void)
{
 unsigned char header[48]={'H','F','S','N','A','P','1','\n'};
 const unsigned char footer[]="HFSEND1\n",failure[]="HEARTH_ACQUISITION_FAILED_V1\n";
 long pause[2]={0,100000000};unsigned int i;int failed,fd=-1,tries=0;
 failed=raw(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
        raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
        raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755");
 if(!failed) failed=capture();
 for(i=0;i<32;i++) header[8+i]=hearth_session[i];
 put(header+40,size);put(header+44,crc(payload,size));
 while(fd<0&&tries++<1200) {
  fd=(int)raw(5,(long)"/dev/ttyGS0",2|256|2048|32768,0,0,0);
  if(fd<0) raw(162,(long)pause,0,0,0,0);
 }
 if(fd>=0) {
  if(!failed) failed=await_session(fd);
  if(!failed) failed=send_all(fd,header,sizeof(header))||send_all(fd,payload,size)||send_all(fd,footer,8)||export_network(fd)||export_groups(fd);
  if(failed) send_all(fd,failure,sizeof(failure)-1);
  raw(6,fd,0,0,0,0);
 }
 /* One bounded attempt only, remain in RAM for an owner-timed restart. */
 for(;;) raw(162,(long)pause,0,0,0,0);
}
