/* Original bounded streaming data core, MIT. No path, device or mutation authority. */
#ifndef HEARTH_NETWORK_STREAM_H
#define HEARTH_NETWORK_STREAM_H
#include "hash.h"
struct hn_plan {
 unsigned int target,size,offset,width;
 unsigned char original[64],replacement[64],original_hash[32],replacement_hash[32];
};
struct hn_stream {
 int (*rewind)(void *);
 long (*read)(void *,unsigned char *,unsigned int);
 long (*write)(void *,const unsigned char *,unsigned int);
};
enum hn_content { HN_ORIGINAL=0,HN_REPLACEMENT=1 };
int hn_plan_valid(const struct hn_plan *);
/* Pure read-only original+derived candidate verification before staging. */
int hn_preflight(const struct hn_stream *,void *,const struct hn_plan *);
/* Copy originals to an owned temporary/archive only. No rename/commit here. */
int hn_copy(const struct hn_stream *,void *,const struct hn_plan *,enum hn_content);
int hn_verify(const struct hn_stream *,void *,const struct hn_plan *,enum hn_content);
#endif
