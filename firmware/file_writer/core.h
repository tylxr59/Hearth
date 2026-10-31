/* Original physical write-window policy (MIT). No device or filesystem API. */
#ifndef HEARTH_FILESYSTEM_WINDOW_H
#define HEARTH_FILESYSTEM_WINDOW_H
enum hf_phase { HF_DISABLED, HF_ENABLED, HF_SEALED };
enum hf_operation { HF_PROGRAM=1, HF_ERASE, HF_CLEANMARKER };
struct hf_window {
    enum hf_phase phase;
    unsigned char plan[32],receipt[32];
    unsigned int attempted[3],failed;
};
struct hf_io {
    int (*protected)(void *);
    int (*protect)(void *,int);
    int (*perform)(void *,enum hf_operation,void *);
};
void hf_init(struct hf_window *,const unsigned char *,const unsigned char *);
int hf_open(struct hf_window *,const unsigned char *,const unsigned char *,int);
int hf_range(enum hf_operation,unsigned long long,unsigned int);
int hf_run(struct hf_window *,const struct hf_io *,void *,enum hf_operation,
           unsigned long long,unsigned int,void *);
int hf_close(struct hf_window *,const struct hf_io *,void *);
#endif
