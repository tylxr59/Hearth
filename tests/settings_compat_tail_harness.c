#include <assert.h>
#include <string.h>
#include "../firmware/settings_probe/capture.h"
#include "../firmware/settings_compat_probe/tail.h"
int main(void)
{
    unsigned char stream[10007];
    for (int i=0;i<(int)sizeof(stream);i++) stream[i]=(unsigned char)(i*17);
    for (int chunk=1;chunk<=2048;chunk+=17) {
        diagnostics_used=diagnostics_dropped=0;
        for (long offset=0;offset<(long)sizeof(stream);) {
            long size=sizeof(stream)-offset;
            if (size>chunk) size=chunk;
            assert(capture_diagnostic_tail(stream+offset,size));
            offset+=size;
        }
        assert(diagnostics_used==2048 && diagnostics_dropped==sizeof(stream)-2048);
        assert(!memcmp(child_diagnostics,stream+sizeof(stream)-2048,2048));
    }
    unsigned char saved[2048]; memcpy(saved,child_diagnostics,2048);
    diagnostics_dropped=SETTINGS_DROPPED_LIMIT;
    assert(!capture_diagnostic_tail(stream,1));
    assert(!memcmp(saved,child_diagnostics,2048));
    assert(!capture_diagnostic_tail(stream,-1));
    assert(!capture_diagnostic_tail(stream,2049));
    assert(capture_output(stream,1));
    diagnostics_used=diagnostics_dropped=0;
    assert(capture_diagnostics(stream,1));
    return 0;
}
