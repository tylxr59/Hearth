/* Original MIT. Compile INSTEAD OF posix.c: reuse its exact bounded private
 * helpers, with a separate explicit force-rewrite API. Ordinary restoration
 * remains unchanged. A separate NONE-only kernel is mandatory on target. */
#include "../file_install/posix.c"
#include "reencode.h"
#ifdef HEARTH_HOST_LAB
#include <sys/syscall.h>
#include <sys/ioctl.h>
#define RECODE_GETDENTS SYS_getdents64
#else
#define RECODE_GETDENTS 217
extern int ioctl(int,unsigned long,...);
#endif
#define RECODE_ENCODING_IOCTL 0x4871U
unsigned int hearth_posix_reencode_stage;
static int same_name(const char *a,const char *b)
{ unsigned int n=0;while(a[n]&&b[n]&&a[n]==b[n]) n++;return a[n]==b[n]; }
static void reencode_journal_bytes(struct hearth_posix_context *c,unsigned char record[48],unsigned int phase)
{
 unsigned int i;for(i=0;i<48;i++) record[i]=0;
 record[0]='H';record[1]='F';record[2]='I';record[3]='1';
 put(record+4,phase);put(record+8,(1U<<c->count)-1);put(record+12,c->count);
 for(i=0;i<32;i++) record[16+i]=c->plan_id[i];
}
static int archive_name(struct hearth_posix_context *c,const char *name)
{
 unsigned int i;char known[128];
 if(same_name(name,"journal")||same_name(name,"journal.new")) return 1;
 for(i=0;i<c->count;i++) if(c->changes[i].existed) {
  backup_name(i,known);
  { unsigned int n=0;while(known[n]&&name[n]&&known[n]==name[n]) n++;if(!known[n]&&!name[n]) return 1; }
  if(append(known,".plain")) return 0;
  { unsigned int n=0;while(known[n]&&name[n]&&known[n]==name[n]) n++;if(!known[n]&&!name[n]) return 1; }
 }
 return 0;
}
static int archive_inventory(struct hearth_posix_context *c)
{
 unsigned char data[2048];long count;unsigned int entries=0;int result=-1;
 int fd=openat(c->recovery,".",H_RDONLY|H_DIRECTORY|H_NOFOLLOW|H_CLOEXEC);
 if(fd<0) return -1;
 while((count=syscall(RECODE_GETDENTS,fd,data,(long)sizeof(data)))>0) {
  unsigned int at=0;
  if((unsigned long)count>sizeof(data)) goto done;
  while(at<(unsigned long)count) {
   char name[128];unsigned int n=0,length;
   if((unsigned long)count-at<20||++entries>64) goto done;
   length=data[at+16]|(unsigned int)data[at+17]<<8;
   if(length<20||length>(unsigned long)count-at) goto done;
   while(19+n<length&&data[at+19+n]) {
    if(n>=sizeof(name)-1||data[at+19+n]=='/') goto done;
    name[n]=(char)data[at+19+n];n++;
   }
   if(!n||19+n>=length) goto done;
   name[n]=0;at+=length;
   if((n==1&&name[0]=='.')||(n==2&&name[0]=='.'&&name[1]=='.')) continue;
   if(!archive_name(c,name)) goto done;
  }
 }
 if(count==0) result=0;
done:
 if(close(fd)) result=-1;
 return result;
}
int hearth_posix_reencode_preflight(struct hearth_posix_context *c)
{
 unsigned int i,phase,mask;int status;
 hearth_posix_reencode_stage=1;status=hearth_posix_restore_preflight(c);
 if(status) return status;
 hearth_posix_reencode_stage=2;
 if(recovery_journal(c,&phase,&mask)||
    (phase!=HEARTH_RESTORED&&phase!=HEARTH_RESTORING&&phase!=HEARTH_RESTORE_FAILED)||
    (phase!=HEARTH_RESTORE_FAILED&&mask!=((1U<<c->count)-1))) return HEARTH_PREFLIGHT_FAILED;
 hearth_posix_reencode_stage=3;if(archive_inventory(c)) return HEARTH_PREFLIGHT_FAILED;
 for(i=0;i<c->count;i++) {
  const struct hearth_file_change *f=&c->changes[i];char name[128],backup[128];
  int directory=parent(c,f->target,name),result=-1;
  hearth_posix_reencode_stage=10+i;
  if(directory<0) return HEARTH_PREFLIGHT_FAILED;
  if(!(c->created[i]&8U)&&check_original(c,i,directory,name)) goto checked;
  if(c->created[i]&2U) goto checked; /* No replacement installation staging. */
  backup_name(i,backup);
  hearth_posix_reencode_stage=30+i;
  if(f->existed) {
   if(contents(c->recovery,backup,f->original,0600,c)||append(backup,".plain")||
      recover_temporary(c,i,c->recovery,backup,f->original,0600,16)) goto checked;
  } else if(absent(c->recovery,backup)!=1) goto checked;
  result=0;
checked:
  if(close(directory)) result=-1;
  if(result) return HEARTH_PREFLIGHT_FAILED;
 }
 hearth_posix_reencode_stage=60;
 if(absent(c->recovery,"journal.new")!=1) {
  unsigned char record[48];struct hearth_file_bytes expected={record,48};
  reencode_journal_bytes(c,record,HEARTH_RESTORING);
  if(recover_temporary(c,0,c->recovery,"journal.new",expected,0600,32)) {
   reencode_journal_bytes(c,record,HEARTH_RESTORED);
   if(recover_temporary(c,0,c->recovery,"journal.new",expected,0600,32)) return HEARTH_PREFLIGHT_FAILED;
  }
  c->journal_temporary=1;
 }
 hearth_posix_reencode_stage=0;return 0;
}
static int force_original(struct hearth_posix_context *c,unsigned int i)
{
 const struct hearth_file_change *f=&c->changes[i];char name[128],temporary[128];unsigned int n;
 int fd=parent(c,f->target,name),result=-1;
 if(fd<0) return -1;
 if(!f->existed) { result=check_original(c,i,fd,name);goto done; }
 if(!(c->created[i]&8U)&&check_original(c,i,fd,name)) goto done;
 for(n=0;(temporary[n]=name[n]);n++) {}
 if(append(temporary,restore_suffix)||
    create_file(c,fd,temporary,f->original,f->original_mode,&c->created[i],4)||
    renameat(fd,temporary,fd,name)) goto done;
 c->created[i]&=~4U;
 if(fsync(fd)||check_original(c,i,fd,name)) goto done;
 result=0;
done:
 if(close(fd)) result=-1;
 return result;
}
static int force_backup(struct hearth_posix_context *c,unsigned int i)
{
 const struct hearth_file_change *f=&c->changes[i];char name[128],temporary[128];unsigned int n;
 if(!f->existed) return 0;
 backup_name(i,name);for(n=0;(temporary[n]=name[n]);n++) {}
 if(append(temporary,".plain")) return -1;
 if(c->created[i]&16U) {
  if(unlinkat(c->recovery,temporary,0)||fsync(c->recovery)) return -1;
  c->created[i]&=~16U;
 }
 if(contents(c->recovery,name,f->original,0600,c)||
    create_file(c,c->recovery,temporary,f->original,0600,&c->created[i],16)||
    renameat(c->recovery,temporary,c->recovery,name)) return -1;
 c->created[i]&=~16U;
 return fsync(c->recovery)||contents(c->recovery,name,f->original,0600,c) ? -1 : 0;
}
struct hearth_install_result hearth_posix_reencode_originals(struct hearth_posix_context *c)
{
 struct hearth_install_result r={0};unsigned int i;
 r.error=hearth_posix_reencode_preflight(c);if(r.error) return r;
 r.attempted=(1U<<c->count)-1;
 if(journal(c,HEARTH_RESTORING,r.attempted)) { r.journal_error=1;return r; }
 for(i=c->count;i;i--) {
  unsigned int index=i-1;
  if(discard(c,index)||force_original(c,index)) r.rollback_error=1;
  else r.restored|=1U<<index;
 }
 for(i=0;i<c->count;i++) if(force_backup(c,i)) r.rollback_error=1;
 if(journal(c,r.rollback_error?HEARTH_RESTORE_FAILED:HEARTH_RESTORED,r.restored)) r.journal_error=1;
 for(i=0;i<c->count;i++) if(discard(c,i)) r.cleanup_error=1;
 if(r.rollback_error) r.error=HEARTH_ROLLBACK_FAILED;
 return r;
}
static int encoding_fd(int directory,const char *name)
{
 int fd=openat(directory,name,H_RDONLY|H_NONBLOCK|H_NOFOLLOW|H_CLOEXEC),result;
 if(fd<0) return -1;
 result=ioctl(fd,RECODE_ENCODING_IOCTL,0UL);
 if(close(fd)) result=-1;
 return result==0 ? 0 : -1;
}
int hearth_posix_original_encoding(struct hearth_posix_context *c)
{
 unsigned int i;int result=hearth_posix_reencode_preflight(c);
 if(result) return -1;
 if(c->journal_temporary||encoding_fd(c->recovery,"journal")) return -1;
 for(i=0;i<c->count;i++) {
  const struct hearth_file_change *f=&c->changes[i];char name[128],backup[128];int fd;
  if(c->created[i]&22U) return -1;
  if(!f->existed) continue;
  fd=parent(c,f->target,name);if(fd<0) return -1;
  result=encoding_fd(fd,name);if(close(fd)) result=-1;
  if(result) return -1;
  backup_name(i,backup);if(encoding_fd(c->recovery,backup)) return -1;
 }
 return 0;
}
int hearth_posix_selected_encoding(struct hearth_posix_context *c,int replacement)
{
 unsigned int i;int result=hearth_posix_restore_preflight(c);
 if(result||(replacement!=0&&replacement!=1)||archive_inventory(c)||c->journal_temporary||encoding_fd(c->recovery,"journal")) return -1;
 for(i=0;i<c->count;i++) {
  const struct hearth_file_change *f=&c->changes[i];char name[128],backup[128];int fd;
  if(c->created[i]&6U) return -1;
  if(replacement||f->existed) {
   fd=parent(c,f->target,name);if(fd<0) return -1;
   result=encoding_fd(fd,name);if(close(fd)) result=-1;if(result) return -1;
  }
  backup_name(i,backup);
  if(f->existed&&(contents(c->recovery,backup,f->original,0600,c)||encoding_fd(c->recovery,backup))) return -1;
  if(!f->existed&&absent(c->recovery,backup)!=1) return -1;
  if(append(backup,".plain")||absent(c->recovery,backup)!=1) return -1;
 }
 return absent(c->recovery,"journal.new")==1 ? 0 : -1;
}
