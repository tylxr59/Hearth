/* Original hardware-free gate tests (MIT), never open any device. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "../firmware/file_writer/core.h"
struct fake { int protected,off_failure,on_failure,perform_error,performed,freed; };
static int protection(void *opaque) { return ((struct fake *)opaque)->protected; }
static int protect(void *opaque,int enabled)
{
    struct fake *f=opaque;
    if((enabled&&f->on_failure)||(!enabled&&f->off_failure)) return -1;
    f->protected=enabled;return 0;
}
static int perform(void *opaque,enum hf_operation operation,void *request)
{
    struct fake *f=opaque;assert(f->protected==0);f->performed++;
    if(operation==HF_ERASE) { free(request);f->freed=1; }
    return f->perform_error;
}
int main(int argc,char **argv)
{
    struct hf_window w;struct fake f={1,0,0,0,0,0};
    const struct hf_io io={protection,protect,perform};
    unsigned char plan[32],receipt[32],other[32];int scenario;void *request;
    assert(argc==2);scenario=atoi(argv[1]);memset(plan,1,32);memset(receipt,2,32);memset(other,3,32);
    hf_init(&w,plan,receipt);
    if(scenario==1) {
        assert(hf_open(&w,other,receipt,1)!=0&&w.phase==HF_DISABLED);return 0;
    }
    if(scenario==2) {
        assert(hf_open(&w,plan,other,1)!=0&&w.phase==HF_DISABLED);return 0;
    }
    if(scenario==3) {
        assert(hf_open(&w,plan,receipt,0)!=0&&w.phase==HF_SEALED);return 0;
    }
    if(scenario==4) {
        memset(plan,0,32);hf_init(&w,plan,receipt);assert(hf_open(&w,plan,receipt,1)!=0);return 0;
    }
    assert(hf_open(&w,plan,receipt,1)==0);
    assert(hf_open(&w,plan,receipt,1)!=0);
    request=malloc(16);assert(request);memset(request,0x5a,16);
    if(scenario==5) f.protected=0;
    if(scenario==6) f.off_failure=1;
    if(scenario==7) f.on_failure=1;
    if(scenario==8) f.perform_error=-5;
    if(scenario==9) {
        assert(hf_close(&w,&io,&f)==0&&w.phase==HF_SEALED&&f.protected==1);
        assert(hf_run(&w,&io,&f,HF_PROGRAM,12ULL*1048576,2048,request)!=0&&!f.performed);
        free(request);return 0;
    }
    if(scenario==10) {
        assert(hf_run(&w,&io,&f,HF_PROGRAM,58ULL*1048576,2048,request)!=0&&!f.performed&&f.protected);
        free(request);return 0;
    }
    { int result=hf_run(&w,&io,&f,scenario==11?HF_ERASE:HF_PROGRAM,12ULL*1048576,scenario==11?131072:2048,request);
      if(scenario>=5&&scenario<=8) assert(result!=0);
      else assert(result==0);
    }
    if(scenario==5||scenario==6) assert(!f.performed&&w.phase==HF_SEALED&&f.protected);
    else assert(f.performed==1);
    if(scenario==7) assert(w.phase==HF_SEALED&&!f.protected);
    else assert(f.protected==1);
    if(scenario==8) assert(w.failed==1&&w.phase==HF_ENABLED);
    if(!f.freed) free(request);
    return 0;
}
