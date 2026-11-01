/* Trusted host-only fixture; synthetic opaque bytes, no ARM firmware. */
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "../firmware/network_writer/data.h"
#include "../firmware/network_update/stream.h"
#include "plan.h"
int main(int argc,char **argv)
{
 unsigned int i;int fd,result;
 if(argc!=2&&argc!=3) return 2;
 fd=open(argv[1],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
 if(fd<0) return 2;
 result=hn_data_load(fd);close(fd);
 if(result) { if(hn_data_release()) return 3;puts("refused");return 0; }
 for(i=0;i<4;i++) {
  const struct hearth_file_change *f=&hn_changes[i];unsigned int j;
  if(f->original.size!=hn_plans[i].size||f->replacement.size!=hn_plans[i].size) return 4;
  for(j=0;j<hn_plans[i].size;j++) {
   unsigned char want=f->original.data[j];
   if(j>=hn_plans[i].offset&&j<hn_plans[i].offset+hn_plans[i].width)
    want=hn_plans[i].replacement[j-hn_plans[i].offset];
   if(f->replacement.data[j]!=want) return 5;
  }
 }
 if(argc==3) {
  struct hearth_posix_context c={0};struct hearth_install_result r;
  c.roots[0]=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
  c.roots[1]=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
  c.recovery=-1;c.owner=getuid();c.group=getgid();c.count=4;c.changes=hn_changes;c.archive_layout=1;
  memcpy(c.plan_id,hn_plan_id,32);
  r=hearth_install_files(&hearth_posix_file_ops,&c,4,1);
  if(r.error||!r.committed||r.attempted!=15||r.restored) return 7;
  if(c.recovery>=0) { close(c.recovery);c.recovery=-1; }
  r=hearth_posix_restore_files(&c);
  if(r.error||r.committed||r.attempted!=15||r.restored!=15||r.rollback_error||r.journal_error||r.cleanup_error) return 8;
  if(c.recovery>=0) close(c.recovery);
  close(c.roots[0]);close(c.roots[1]);
 }
 if(hn_data_load(-1)!=-1||hn_data_release()||hn_data_release()) return 6;
 puts("mapped-and-verified");return 0;
}
