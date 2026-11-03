/* Original exact-existing-backup reuse contract, MIT. No arbitrary paths. */
#ifndef HEARTH_SHARED_NETWORK_BACKUP_H
#define HEARTH_SHARED_NETWORK_BACKUP_H
struct hn_shared_archive {
 char directory[96];
 unsigned char journal[48];
 unsigned int sizes[4];
 unsigned char hashes[4][32];
};
struct hearth_posix_context;
int hn_shared_preflight(struct hearth_posix_context *,int);
int hn_shared_stage(struct hearth_posix_context *,unsigned int,const char *);
int hn_shared_contents(struct hearth_posix_context *,unsigned int,const char *);
#endif
