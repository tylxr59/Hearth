/* Original scoped adapter instantiation and exact post-write audit (MIT).
 * Kernel's inode encoding checker is separate GPL source, unchanged. */
#ifndef HEARTH_NETWORK_ADAPTER
#error "Only the fixed four-file adapter may compile this translation unit"
#endif
#include "../file_reencode/reencode.c"
int hn_exact_readback(struct hearth_posix_context *c,int replacement)
{
 unsigned int i;if(replacement!=0&&replacement!=1) return -1;
 for(i=0;i<4;i++) {
  const struct hearth_file_change *f=&c->changes[i];char name[128];int result;
  int directory=parent(c,f->target,name);if(directory<0) return -1;
  result=contents(directory,name,replacement?f->replacement:f->original,
                  replacement?f->replacement_mode:f->original_mode,c);
  if(close(directory)) result=-1;if(result) return -1;
 }
 return hearth_posix_selected_encoding(c,replacement);
}
