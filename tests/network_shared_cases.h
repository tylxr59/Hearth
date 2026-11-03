/* Original synthetic shared-original fault cases; same source runs on host/RAM. */
#include "../firmware/network_update/hash.h"
static void shared_fixture_file(int fd,const char *name,const unsigned char *data,unsigned int size,unsigned int mode)
{
 int out=openat(fd,name,O_WRONLY|O_CREAT|O_EXCL,0600);assert(out>=0);
 assert(write(out,data,size)==(ssize_t)size);assert(fchmod(out,mode)==0);assert(close(out)==0);
}
static void shared_fixture_remove(int fd,const char *name,int flags)
{ int r=unlinkat(fd,name,flags);assert(r==0||errno==ENOENT); }
static void shared_case(int root,unsigned int which,const char *const *dirs)
{
 struct hearth_posix_context c;struct hearth_file_change changes[3];struct hn_shared_archive spec;
 struct hearth_install_result result;unsigned char original[256],replacement[256];
 unsigned int i,n=0;int old,fd;char name[16];static const char prefix[]=".hearth-rollback-";
 memset(&c,0,sizeof(c));memset(&spec,0,sizeof(spec));
 for(i=0;i<sizeof(original);i++) { original[i]=(unsigned char)i;replacement[i]=(unsigned char)(i^0x5a); }
 for(i=0;i<sizeof(prefix)-1;i++) spec.directory[n++]=prefix[i];
 for(i=0;i<32;i++) { spec.directory[n++]='3';spec.directory[n++]='1';spec.journal[16+i]=0x31; }
 spec.journal[0]='H';spec.journal[1]='F';spec.journal[2]='I';spec.journal[3]='1';
 spec.journal[4]=6;spec.journal[8]=15;spec.journal[12]=4;
 assert(mkdirat(root,spec.directory,0700)==0);
 old=openat(root,spec.directory,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(old>=0);
 for(i=0;i<4;i++) {
  struct hn_hash h;spec.sizes[i]=sizeof(original);hn_hash_init(&h);
  assert(hn_hash_update(&h,original,sizeof(original))==0);assert(hn_hash_final(&h,spec.hashes[i])==0);
  snprintf(name,sizeof(name),"%u.original",i);shared_fixture_file(old,name,original,sizeof(original),0600);
 }
 shared_fixture_file(old,"journal",spec.journal,48,0600);
 for(i=0;i<7;i++) assert(mkdirat(root,dirs[i],0755)==0);
 for(i=0;i<3;i++) {
  changes[i]=(struct hearth_file_change){i,1,{original,sizeof(original)},{replacement,sizeof(replacement)},0755,0755};
  shared_fixture_file(root,hearth_target_paths[i],original,sizeof(original),0755);
 }
 shared_fixture_file(root,"etc/nestlabs/client.config",old_unused_scope,sizeof(old_unused_scope)-1,0600);
 c.roots[0]=root;c.roots[1]=openat(root,".",O_RDONLY|O_DIRECTORY);assert(c.roots[1]>=0);
 c.recovery=-1;c.owner=getuid();c.group=getgid();c.count=3;c.changes=changes;c.archive_layout=1;c.shared=&spec;
 memset(c.plan_id,42,sizeof(c.plan_id));
 if(which==9) { fd=openat(old,"0.original",O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0); }
 if(which==10) { fd=openat(old,"journal",O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0); }
 if(which==11) shared_fixture_file(old,"unexpected",original,1,0600);
 if(which==12) assert(linkat(old,"0.original",root,"alien",0)==0);
 if(which==13) { fd=openat(old,"0.original",O_RDONLY);assert(fd>=0);assert(fchmod(fd,0644)==0);assert(close(fd)==0); }
 if(which==14) { assert(unlinkat(old,"0.original",0)==0);assert(symlinkat("journal",old,"0.original")==0); }
 if(which>=9&&which<=14) {
  assert(hn_shared_preflight(&c,0)!=0);goto done;
 }
 assert(hn_shared_preflight(&c,0)==0);
 /* Reuse the actual transaction fault wrappers, including uncertain renames. */
 armed=which>=1&&which<=8;writes=0;injected=0;renamed=0;
 result=hearth_install_files(&hearth_posix_file_ops,&c,3,1);armed=0;
 if(which>=3&&which<=8) {
  assert(result.error&&!result.committed&&!result.rollback_error);
  for(i=0;i<3;i++) check_file(root,hearth_target_paths[i],original,sizeof(original));
  assert(hn_shared_preflight(&c,1)==0);reset(&c);
  result=hearth_posix_restore_files(&c);
  if(which==3||which==7||which==8) { assert(result.error==HEARTH_PREFLIGHT_FAILED);goto done; }
  assert(!result.error&&result.restored==7);
  for(i=0;i<3;i++) { snprintf(name,sizeof(name),"%u.original",i);assert(hn_shared_contents(&c,i,name)==0); }
  goto done;
 }
 assert(result.committed&&!result.error);
 for(i=0;i<3;i++) check_file(root,hearth_target_paths[i],replacement,sizeof(replacement));
 assert(hn_shared_preflight(&c,1)==0);
 for(i=0;i<3;i++) { snprintf(name,sizeof(name),"%u.original",i);assert(hn_shared_contents(&c,i,name)==0); }
 if(which==15) {
  fd=openat(c.recovery,"0.original",O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0);
  assert(hn_shared_preflight(&c,1)!=0);goto done;
 }
 if(which==16) {
  assert(unlinkat(c.recovery,"0.original",0)==0);
  shared_fixture_file(c.recovery,"0.original",original,sizeof(original),0600);
  assert(linkat(c.recovery,"0.original",root,"alien",0)==0);
  assert(hn_shared_preflight(&c,1)!=0);goto done;
 }
 if(which==17) { assert(unlinkat(old,"0.original",0)==0);assert(hn_shared_preflight(&c,1)!=0);goto done; }
 if(which==18) { fd=openat(old,"journal",O_WRONLY);assert(fd>=0);assert(write(fd,"?",1)==1);assert(close(fd)==0);assert(hn_shared_preflight(&c,1)!=0);goto done; }
 reset(&c);assert(hearth_posix_restore_preflight(&c)==0);reset(&c);
 result=hearth_posix_restore_files(&c);assert(!result.error&&result.restored==7);
 assert(hn_shared_preflight(&c,1)==0);
 for(i=0;i<3;i++) check_file(root,hearth_target_paths[i],original,sizeof(original));
 check_file(old,"journal",spec.journal,48);
done:
 reset(&c);assert(close(c.roots[1])==0);clean_fixture(root,dirs);
 for(i=0;i<4;i++) { snprintf(name,sizeof(name),"%u.original",i);shared_fixture_remove(old,name,0); }
 shared_fixture_remove(old,"journal",0);shared_fixture_remove(old,"unexpected",0);
 assert(close(old)==0);shared_fixture_remove(root,spec.directory,AT_REMOVEDIR);shared_fixture_remove(root,"alien",0);
 armed=0;injected=0;renamed=0;writes=0;
}
