/* Original bounded SHA-256 implementation, MIT. Not a validated crypto module.
 * Algorithm: NIST FIPS180-4 sections4.1.2,4.2.2,5,6.2.
 * https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf */
#ifndef HEARTH_NETWORK_HASH_H
#define HEARTH_NETWORK_HASH_H
#define HN_HASH_LIMIT (6U*1048576U)
struct hn_hash { unsigned int state[8],total,used;unsigned char block[64]; };
void hn_hash_init(struct hn_hash *);
int hn_hash_update(struct hn_hash *,const unsigned char *,unsigned int);
int hn_hash_final(struct hn_hash *,unsigned char [32]);
#endif
