/* Original cached-report transmitter for raw Linux syscall results (MIT).
 * Retries only cached bytes. It never restarts the diagnostic workload.
 */
#ifndef HEARTH_CACHED_TRANSMIT_H
#define HEARTH_CACHED_TRANSMIT_H
struct hearth_cached_transmit { long offset; };
enum hearth_transmit_status {
    HEARTH_TRANSMIT_MORE = 0, HEARTH_TRANSMIT_DONE = 1,
    HEARTH_TRANSMIT_WAIT = 2, HEARTH_TRANSMIT_ERROR = -1
};
static int hearth_cached_transmit_step(struct hearth_cached_transmit *state,
    long fd,const char *data,long size,long (*send_bytes)(long,const char *,long))
{
    long written,remaining;
    if(!state||!data||!send_bytes||size<=0||state->offset<0||state->offset>=size) return HEARTH_TRANSMIT_ERROR;
    remaining=size-state->offset;
    written=send_bytes(fd,data+state->offset,remaining);
    if(written==-11||written==-4) return HEARTH_TRANSMIT_WAIT;
    if(written<=0||written>remaining) return HEARTH_TRANSMIT_ERROR;
    state->offset+=written;
    if(state->offset==size) {
        state->offset=0;
        return HEARTH_TRANSMIT_DONE;
    }
    return HEARTH_TRANSMIT_MORE;
}
#endif
