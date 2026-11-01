/* Original physical write-window policy (MIT), shared by trusted host tests
 * and a future separately reviewed kernel adapter. No flash operation here. */
#include "core.h"
#define MIB 1048576ULL
void hf_init(struct hf_window *w,const unsigned char *plan,const unsigned char *receipt)
{
    unsigned int i;
    w->phase=HF_DISABLED;w->failed=0;
    for(i=0;i<3;i++) w->attempted[i]=0;
    for(i=0;i<32;i++) { w->plan[i]=plan[i];w->receipt[i]=receipt[i]; }
}
int hf_open(struct hf_window *w,const unsigned char *plan,const unsigned char *receipt,int protected)
{
    unsigned int i,difference=0,present_plan=0,present_receipt=0;
    if(!w||!plan||!receipt||w->phase!=HF_DISABLED) return -1;
    for(i=0;i<32;i++) {
        difference|=(unsigned int)(plan[i]^w->plan[i])|(unsigned int)(receipt[i]^w->receipt[i]);
        present_plan|=w->plan[i];present_receipt|=w->receipt[i];
    }
    if(difference||!present_plan||!present_receipt) return -1;
    if(protected!=1) { w->phase=HF_SEALED;return -1; }
    w->phase=HF_ENABLED;return 0;
}
int hf_range(enum hf_operation operation,unsigned long long at,unsigned int length)
{
    unsigned long long span=length;
    if(operation==HF_PROGRAM) {
        if(!length||(at&2047U)||(length&2047U)) return -1;
    } else if(operation==HF_ERASE) {
        if(!length||(at&131071U)||(length&131071U)) return -1;
    } else if(operation==HF_CLEANMARKER) {
        if(length!=8||(at&131071U)) return -1;
        span=2048;
    } else return -1;
    if(at>=12*MIB&&at<58*MIB&&span<=58*MIB-at) return 0;
#ifndef HEARTH_ROOT0_ONLY
    if(at>=116*MIB&&at<124*MIB&&span<=124*MIB-at) return 0;
#endif
    return -1;
}
static int valid_io(const struct hf_io *io)
{ return io&&io->protected&&io->protect&&io->perform; }
static int protect_final(struct hf_window *w,const struct hf_io *io,void *ctx)
{
    int status=io->protect(ctx,1),protected=io->protected(ctx);
    if(status||protected!=1) { w->phase=HF_SEALED;return -1; }
    return 0;
}
int hf_run(struct hf_window *w,const struct hf_io *io,void *ctx,enum hf_operation operation,
           unsigned long long at,unsigned int length,void *request)
{
    int status;
    if(!w||!valid_io(io)||!ctx||!request||w->phase!=HF_ENABLED||hf_range(operation,at,length)) return -1;
    if(io->protected(ctx)!=1) {
        w->phase=HF_SEALED;protect_final(w,io,ctx);return -1;
    }
    if(io->protect(ctx,0)||io->protected(ctx)!=0) {
        w->phase=HF_SEALED;protect_final(w,io,ctx);return -1;
    }
    w->attempted[(unsigned int)operation-1]++;
    /* A synchronous erase completion callback may free request. Do not touch
     * its fields (or pass it anywhere) after perform returns. */
    status=io->perform(ctx,operation,request);
    if(status) w->failed++;
    if(protect_final(w,io,ctx)) return -1;
    return status;
}
int hf_close(struct hf_window *w,const struct hf_io *io,void *ctx)
{
    if(!w||!valid_io(io)||!ctx) return -1;
    w->phase=HF_SEALED;
    return protect_final(w,io,ctx);
}
