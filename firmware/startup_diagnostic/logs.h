/* Original bounded read-only log-tree acquisition (MIT). */
#ifndef HEARTH_STARTUP_LOGS_H
#define HEARTH_STARTUP_LOGS_H
#define HFD_FILES 64U
#define HFD_TAIL 65536U
#define HFD_LIMIT (16U+HFD_FILES*(HFD_TAIL+264U))
struct hfd_stat { unsigned int mode,owner,group,size; };
struct hfd_ops {
 int (*open)(int,const char *);
 int (*close)(int);
 int (*metadata)(int,struct hfd_stat *);
 int (*directory)(int);
 long (*entries)(int,unsigned char *,unsigned int);
 long (*read)(int,unsigned char *,unsigned int);
 long (*seek)(int,unsigned int);
};
/* Header: status, captured files, scanned entries, limit flag. Each file:
 * path length, mode, uid, gid, original size, tail size; path bytes; tail bytes.
 * status0 means complete within bounds,1 means read failure,2 bound reached. */
unsigned int hfd_capture(const struct hfd_ops *,int,unsigned char *,unsigned int);
#endif
