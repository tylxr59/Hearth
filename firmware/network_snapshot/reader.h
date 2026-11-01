/* Original fixed network-file capture contract (MIT). No mutation API. */
#ifndef HEARTH_NETWORK_READER_H
#define HEARTH_NETWORK_READER_H
typedef __SIZE_TYPE__ hearth_file_size;
#define HNS_COUNT 4U
#define HNS_CAPACITY (32U+4U*24U+6U*1048576U+1048576U+2U*65536U)
struct hns_file { unsigned int target,existed,mode,owner,group;hearth_file_size size; };
static const char *const hns_paths[HNS_COUNT]={"nestlabs/sbin/nlclient","usr/sbin/connmand","etc/connman/main.conf","etc/nestlabs/client.config"};
static const unsigned int hns_limits[HNS_COUNT]={6U*1048576U,1048576U,65536U,65536U};
int hns_capture_file(int,unsigned int,unsigned int,unsigned int,unsigned char *,hearth_file_size,struct hns_file *);
int hns_filesystem(int,unsigned int [6]);
#endif
