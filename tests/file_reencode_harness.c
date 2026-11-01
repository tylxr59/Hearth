/* Original synthetic forced-rewrite lab, MIT. No device or compression codec. */
#define HEARTH_RECOVERY_ENTRY hearth_original_recovery_matrix
#define __wrap_renameat original_reencode_rename
#include "file_recovery_harness.c"
#undef __wrap_renameat
#include "../firmware/file_reencode/reencode.h"
static int reencode_rename_fault;
int __wrap_renameat(int a,const char *b,int c,const char *d)
{
 if(reencode_rename_fault&&suffix(b,".original.plain")) { reencode_rename_fault=0;errno=EIO;return -1; }
 return original_reencode_rename(a,b,c,d);
}
static unsigned long long inode_number(int directory,const char *path)
{
 int fd=openat(directory,path,O_RDONLY|O_NOFOLLOW);unsigned long long result;
 assert(fd>=0);
#ifdef HEARTH_RAM_LAB
 { unsigned long long bytes[16];unsigned char *p=(unsigned char *)bytes;
   assert(syscall(197,fd,bytes)==0);
   result=p[12]|(unsigned int)p[13]<<8|(unsigned int)p[14]<<16|(unsigned int)p[15]<<24; }
#else
 { struct stat s;assert(fstat(fd,&s)==0);result=s.st_ino; }
#endif
 assert(close(fd)==0);return result;
}
static void close_recovery(struct hearth_posix_context *c)
{ if(c->recovery>=0) assert(close(c->recovery)==0);c->recovery=-1; }
static int archive_scenario(int number,const char *directory)
{
 struct hearth_posix_context c;struct hearth_install_result r;unsigned char saved[48],observed[48];int fd,legacy;
 int base=open(directory,O_RDONLY|O_DIRECTORY);assert(base>=0);
 scenario=0;inject=0;activation=0;recovery_case=0;recovery_write_fault=0;reencode_rename_fault=0;
 setup(base,&c);r=hearth_install_files(&hearth_posix_file_ops,&c,9,1);assert(r.committed);close_recovery(&c);
 r=hearth_posix_restore_files(&c);assert(!r.error&&r.restored==511);close_recovery(&c);
 legacy=openat(c.roots[1],".hearth-rollback",O_RDONLY|O_DIRECTORY);assert(legacy>=0);
 fd=openat(legacy,"journal",O_RDONLY);assert(fd>=0&&read(fd,saved,48)==48&&close(fd)==0);
 c.archive_layout=1;c.plan_id[0]^=128;
 r=hearth_install_files(&hearth_posix_file_ops,&c,9,1);assert(r.committed&&!r.error);
 fd=openat(c.recovery,"journal",O_RDONLY);assert(fd>=0&&read(fd,observed,48)==48&&close(fd)==0);
 assert(!memcmp(observed+16,c.plan_id,32));close_recovery(&c);
 fd=openat(legacy,"journal",O_RDONLY);assert(fd>=0&&read(fd,observed,48)==48&&close(fd)==0);
 assert(!memcmp(saved,observed,48));check_file(legacy,"0.original",old,sizeof(old)-1,0600);
 if(number==1) {
  r=hearth_install_files(&hearth_posix_file_ops,&c,9,1);assert(r.error==HEARTH_PREFLIGHT_FAILED&&!r.attempted);
  check_file(c.roots[0],paths[0],replacement,sizeof(replacement)-1,new_modes[0]);
 }
 if(number==2) {
  c.plan_id[0]^=1;r=hearth_posix_restore_files(&c);assert(r.error==HEARTH_PREFLIGHT_FAILED&&!r.attempted);close_recovery(&c);
  check_file(c.roots[0],paths[0],replacement,sizeof(replacement)-1,new_modes[0]);c.plan_id[0]^=1;
 }
 r=hearth_posix_restore_files(&c);assert(!r.error&&r.restored==511);close_recovery(&c);
 for(unsigned int i=0;i<9;i++) if(modes[i]) check_file(c.roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
 fd=openat(legacy,"journal",O_RDONLY);assert(fd>=0&&read(fd,observed,48)==48&&close(fd)==0);assert(!memcmp(saved,observed,48));
 if(number==2) { c.archive_layout=2;r=hearth_posix_restore_files(&c);assert(r.error==HEARTH_INVALID_PLAN&&!r.attempted); }
 assert(close(legacy)==0&&close(c.roots[0])==0&&close(c.roots[1])==0&&close(base)==0);return 0;
}
static int reencode_scenario(int number,const char *directory)
{
 if(number>=13) return archive_scenario(number-13,directory);
 struct hearth_posix_context c;struct hearth_install_result r;unsigned int i;
 unsigned long long before[9]={0},backups[9]={0};int bad=number>=1&&number<=4;
 int base=open(directory,O_RDONLY|O_DIRECTORY),archive;char name[32];
 assert(base>=0);scenario=0;inject=0;activation=0;write_started=0;recovery_case=0;recovery_write_fault=0;reencode_rename_fault=0;
 setup(base,&c);
 r=hearth_install_files(&hearth_posix_file_ops,&c,9,1);assert(r.committed==1&&!r.error);close_recovery(&c);
 r=hearth_posix_restore_files(&c);assert(!r.error&&!r.journal_error&&r.restored==511);close_recovery(&c);
 archive=openat(c.roots[1],".hearth-rollback",O_RDONLY|O_DIRECTORY);assert(archive>=0);
 for(i=0;i<9;i++) if(modes[i]) {
  before[i]=inode_number(c.roots[i==HEARTH_SETTINGS],paths[i]);
  snprintf(name,sizeof(name),"%u.original",i);backups[i]=inode_number(archive,name);
 }
 if(number==1) write_file(archive,"8.original",replacement,sizeof(replacement)-1,0600);
 if(number==2) c.plan_id[0]^=1;
 if(number==3) write_file(c.roots[1],paths[7],replacement,sizeof(replacement)-1,modes[7]);
 if(number==4) write_file(archive,"unexpected",old,sizeof(old)-1,0600);
 if(number==5) write_file(archive,"0.original.plain",old,3,0600);
 if(number==8) {
  unsigned char data[48];int fd=openat(archive,"journal",O_RDONLY);assert(fd>=0);
  assert(read(fd,data,sizeof(data))==sizeof(data)&&close(fd)==0);data[4]=HEARTH_RESTORING;
  write_file(archive,"journal.new",data,9,0600);
 }
 if(number==9) write_file(archive,"0.original.plain",replacement,3,0600);
 if(number==9) bad=1;
 if(number==10||number==12) assert(unlinkat(c.roots[1],paths[7],0)==0);
 if(number==11) { assert(unlinkat(c.roots[0],paths[3],0)==0);bad=1; }
 if(number==12) { assert(symlinkat("../root/etc/ntp.conf",c.roots[1],paths[7])==0);bad=1; }
 assert(close(archive)==0);
 if(number==10) { assert(hearth_posix_restore_preflight(&c)==HEARTH_PREFLIGHT_FAILED);close_recovery(&c);assert(hearth_posix_settings_state(&c)==1); }
 if(number==12) assert(hearth_posix_settings_state(&c)==4);
 { int status=hearth_posix_reencode_preflight(&c);
   assert((status!=0)==bad);close_recovery(&c);
   for(i=0;i<9;i++) if(modes[i]&&!((number==10||number==12)&&i==7)&&!(number==11&&i==3)) assert(inode_number(c.roots[i==HEARTH_SETTINGS],paths[i])==before[i]); }
 if(bad) {
  r=hearth_posix_reencode_originals(&c);assert(r.error==HEARTH_PREFLIGHT_FAILED&&!r.attempted&&!r.restored);close_recovery(&c);
 } else {
  if(number==6) recovery_write_fault=2;
  if(number==7) reencode_rename_fault=1;
  r=hearth_posix_reencode_originals(&c);
  if(number==6||number==7) {
   assert(r.error==HEARTH_ROLLBACK_FAILED&&r.rollback_error&&!r.committed);close_recovery(&c);
   r=hearth_posix_reencode_originals(&c);
  }
  assert(!r.error&&!r.rollback_error&&!r.journal_error&&!r.cleanup_error&&r.restored==511&&!r.committed);close_recovery(&c);
  archive=openat(c.roots[1],".hearth-rollback",O_RDONLY|O_DIRECTORY);assert(archive>=0);
  for(i=0;i<9;i++) if(modes[i]) {
   check_file(c.roots[i==HEARTH_SETTINGS],paths[i],old,sizeof(old)-1,modes[i]);
   if(!(number==10&&i==7)) assert(inode_number(c.roots[i==HEARTH_SETTINGS],paths[i])!=before[i]);
   snprintf(name,sizeof(name),"%u.original",i);
   check_file(archive,name,old,sizeof(old)-1,0600);assert(inode_number(archive,name)!=backups[i]);
  }
  assert(close(archive)==0);
 }
 close_recovery(&c);assert(close(c.roots[0])==0&&close(c.roots[1])==0&&close(base)==0);return 0;
}
#ifndef HEARTH_RAM_LAB
int main(int argc,char **argv) { assert(argc==3);return reencode_scenario(atoi(argv[1]),argv[2]); }
#else
int main(int argc,char **argv)
{
 int i,n;char directory[96],line[128];
 assert(hearth_original_recovery_matrix(argc,argv)==0);
 for(i=0;i<16;i++) {
  snprintf(directory,sizeof(directory),"/state/reencode-case-%d",i);assert(mkdir(directory,0700)==0);
  assert(reencode_scenario(i,directory)==0);
  n=snprintf(line,sizeof(line),"{\"type\":\"reencode_case\",\"case\":%d,\"passed\":true}\n",i);
  assert(n>0&&n<(int)sizeof(line)&&__real_write(1,line,n)==n);
 }
 return 0;
}
#endif
