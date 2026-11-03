/* Original read-only encoding audit (MIT). No write-open, NAND gate or commit.
 * Snapshot and syscall helpers are the measured protected reader's source. */
#define _start snapshot_fallback_start
#include "../file_snapshot/init.c"
#undef _start
static unsigned char audit[128];
#include "../file_install/targets.h"
#include "audit-archive.h"
#include "backups.h"
static int encoding(int directory,const char *path)
{
 long fd=raw(322,directory,(long)path,2048|32768|524288,0,0),result;
 if(fd<0) return (int)fd;
 result=raw(54,fd,0x4872,0,0,0);
 if(raw(6,fd,0,0,0,0)) return -10000;
 return (int)result;
}
void __attribute__((noreturn)) _start(void)
{
 unsigned char header[48]={'H','F','S','N','A','P','1','\n'},extra[48]={'H','F','E','A','U','D','1','\n'};
 unsigned char hashes[48]={'H','F','E','A','H','S','H','1'};
 static const unsigned char end[]="HFSEND1\n",audit_end[]="HFEEND1\n",failure[]="HEARTH_SNAPSHOT_FAILED_V1\n";
 const char *backups[10]={"0.original","1.original","2.original","3.original",
 "4.original","5.original","6.original","7.original","8.original","journal"};
 long pause[2]={1,0};unsigned int i;int failed,archive=-1,roots[2]={-1,-1};
 failed=raw(21,(long)"proc",(long)"/proc",(long)"proc",10,0)||
 raw(21,(long)"sysfs",(long)"/sys",(long)"sysfs",10,0)||
 raw(21,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",10,(long)"mode=0755");
 if(!failed) failed=capture();
 put(audit,2);put(audit+4,19);
 roots[0]=openat(-100,"/native",16384|32768|524288);
 roots[1]=openat(-100,"/user",16384|32768|524288);
 if(roots[0]<0||roots[1]<0) failed=1;
 if(roots[1]>=0) archive=openat(roots[1],HEARTH_AUDIT_ARCHIVE,16384|32768|524288);
 for(i=0;i<9;i++) put(audit+8+4*i,(unsigned int)encoding(roots[i==7],hearth_target_paths[i]));
 for(i=0;i<10;i++) put(audit+44+4*i,(unsigned int)encoding(archive,backups[i]));
 backup_fingerprints(archive,backups);
 if(archive>=0&&close(archive)) failed=1;
 if(roots[0]>=0&&close(roots[0])) failed=1;
 if(roots[1]>=0&&close(roots[1])) failed=1;
 for(i=0;i<32;i++) { header[8+i]=hearth_session[i];extra[8+i]=hearth_session[i];hashes[8+i]=hearth_session[i]; }
 put(header+40,size);put(header+44,crc(payload,size));put(extra+40,84);put(extra+44,crc(audit,84));
 put(hashes+40,sizeof(backup_report));put(hashes+44,crc(backup_report,sizeof(backup_report)));
 for(;;) {
  long fd=raw(5,(long)"/dev/ttyGS0",1|0400|04000,0,0,0);
  if(fd>=0) {
   if(failed) send_all(fd,failure,sizeof(failure)-1);
   else if(!send_all(fd,header,sizeof(header))&&!send_all(fd,payload,size)&&!send_all(fd,end,sizeof(end)-1)&&
           !send_all(fd,extra,sizeof(extra))&&!send_all(fd,audit,84)&&!send_all(fd,audit_end,sizeof(audit_end)-1)&&
           !send_all(fd,hashes,sizeof(hashes))&&!send_all(fd,backup_report,sizeof(backup_report))) send_all(fd,audit_end,sizeof(audit_end)-1);
   raw(6,fd,0,0,0,0);
  }
  raw(162,(long)pause,0,0,0,0);
 }
}
