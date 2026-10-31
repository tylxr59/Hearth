/* Original host-only exercise of the actual cached-report send state. */
#include <assert.h>
#include <string.h>
#include "../firmware/settings_compat_probe/transmit.h"
static char received[70000];
static long count,capacity=20479,interrupt_at=-1;
static long writer(long fd,const char *data,long size)
{
    long n=size;assert(fd==7);
    if(interrupt_at==count) { interrupt_at=-1;return -4; }
    if(!capacity) return -11;
    if(n>capacity)n=capacity;
    assert(count+n<=(long)sizeof(received));memcpy(received+count,data,(size_t)n);
    count+=n;capacity-=n;return n;
}
static long too_large(long fd,const char *data,long size)
{ (void)fd;(void)data;return size+1; }
static long failed(long fd,const char *data,long size)
{ (void)fd;(void)data;(void)size;return -5; }
int main(void)
{
    char frame[30000];struct hearth_cached_transmit state={0};int status,complete=0,waits=0,steps=0;
    memset(frame,'x',sizeof(frame));memcpy(frame,"BEGIN\n",6);memcpy(frame+sizeof(frame)-4,"END\n",4);
    interrupt_at=20479;
    while(complete<2&&steps++<20) {
        long before=state.offset;
        status=hearth_cached_transmit_step(&state,7,frame,sizeof(frame),writer);
        if(status==HEARTH_TRANSMIT_DONE) { complete++;assert(state.offset==0);capacity=20479; }
        else if(status==HEARTH_TRANSMIT_WAIT) { assert(state.offset==before);waits++;capacity=20479; }
        else assert(status==HEARTH_TRANSMIT_MORE);
    }
    assert(complete==2&&waits>=2&&count==2*(long)sizeof(frame));
    assert(!memcmp(received,frame,sizeof(frame))&&!memcmp(received+sizeof(frame),frame,sizeof(frame)));
    state.offset=17;
    assert(hearth_cached_transmit_step(&state,7,frame,sizeof(frame),too_large)==HEARTH_TRANSMIT_ERROR&&state.offset==17);
    assert(hearth_cached_transmit_step(&state,7,frame,sizeof(frame),failed)==HEARTH_TRANSMIT_ERROR&&state.offset==17);
    state.offset=sizeof(frame);
    assert(hearth_cached_transmit_step(&state,7,frame,sizeof(frame),writer)==HEARTH_TRANSMIT_ERROR);
    return 0;
}
