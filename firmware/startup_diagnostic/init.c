/* Original syscall-only read-only startup snapshot/log supervisor (MIT).
 * The proven kernel retains WP and denies all write callbacks. */
#define _start hearth_snapshot_fallback_start
#include "../file_snapshot/init.c"
#undef _start
#include "logs.h"
static unsigned char logs[HFD_LIMIT];
static unsigned int log_size;
static unsigned int get32(const unsigned char *p)
{ return p[0]|(unsigned int)p[1]<<8|(unsigned int)p[2]<<16|(unsigned int)p[3]<<24; }
static int log_open(int fd,const char *name)
{ return (int)raw(322,fd,(long)name,2048|32768|524288,0,0); }
static int log_close(int fd) { return (int)raw(6,fd,0,0,0,0); }
static int log_metadata(int fd,struct hfd_stat *m)
{
 unsigned long long data[16];unsigned char *p=(unsigned char *)data;
 if(raw(197,fd,(long)data,0,0,0)||get32(p+52)) return -1;
 m->mode=get32(p+16);m->owner=get32(p+24);m->group=get32(p+28);m->size=get32(p+48);return 0;
}
static int log_directory(int fd)
{
 unsigned long long data[16];unsigned char *p=(unsigned char *)data;
 if(raw(100,fd,(long)data,0,0,0)||get32(p)!=0x72b6||!(get32(p+44)&1)) return -1;
 return 0;
}
static long log_entries(int fd,unsigned char *out,unsigned int capacity)
{ return raw(217,fd,(long)out,capacity,0,0); }
static long log_read(int fd,unsigned char *out,unsigned int capacity)
{ return raw(3,fd,(long)out,capacity,0,0); }
static long log_seek(int fd,unsigned int at) { return raw(19,fd,at,0,0,0); }
static const struct hfd_ops ops={log_open,log_close,log_metadata,log_directory,log_entries,log_read,log_seek};
static void acquire_logs(void)
{
 int fd=-1;
 put(logs,1);put(logs+4,0);put(logs+8,0);put(logs+12,0);log_size=16;
 if(raw(39,(long)"/logs",0700,0,0,0)||raw(21,(long)"mtd:log",(long)"/logs",(long)"jffs2",1039,0)) return;
 fd=(int)raw(5,(long)"/logs",16384|32768|524288,0,0,0);
 if(fd>=0) { log_size=hfd_capture(&ops,fd,logs,sizeof(logs));if(log_close(fd)) put(logs,1); }
 if(raw(52,(long)"/logs",0,0,0,0)) put(logs,1);
}
void __attribute__((noreturn)) _start(void)
{
 unsigned char header[48]={'H','F','S','N','A','P','1','\n'},log_header[48]={'H','F','L','O','G','S','1','\n'};
 const unsigned char footer[]="HFSEND1\n",log_end[]="HFENDL1\n",failure[]="HEARTH_SNAPSHOT_FAILED_V1\n";
 long pause[2]={1,0};unsigned int i;int failed;
 failed=raw(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
        raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
        raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755");
 if(!failed) failed=capture();
 acquire_logs();
 for(i=0;i<32;i++) { header[8+i]=hearth_session[i];log_header[8+i]=hearth_session[i]; }
 put(header+40,size);put(header+44,crc(payload,size));
 put(log_header+40,log_size);put(log_header+44,crc(logs,log_size));
 for(;;) {
  long fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
  if(fd>=0) {
   if(failed) send_all(fd,failure,sizeof(failure)-1);
   else if(!send_all(fd,header,sizeof(header))&&!send_all(fd,payload,size)&&!send_all(fd,footer,sizeof(footer)-1)&&
           !send_all(fd,log_header,sizeof(log_header))&&!send_all(fd,logs,log_size)) send_all(fd,log_end,sizeof(log_end)-1);
   raw(6,fd,0,0,0,0);
  }
  raw(162,(long)pause,0,0,0,0);
 }
}
