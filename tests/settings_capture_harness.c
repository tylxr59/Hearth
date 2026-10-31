/* Original shared target cache policy, exercised on the host under sanitizers. */
#include <assert.h>
#include <string.h>
#include "../firmware/settings_probe/capture.h"
int main(void)
{
    static const unsigned char row[] = "{\"type\":\"settings_case\"}\n";
    unsigned char noise[128];
    int n;
    memset(noise, 'x', sizeof(noise));
    for (n = 0; n < 12; n++) {
        assert(capture_output(row, 7));
        assert(capture_diagnostics(noise, sizeof(noise)));
        assert(capture_output(row+7, sizeof(row)-1-7));
        /* Many times more diagnostics than the entire old report budget. */
        for (int i = 0; i < 64; i++) assert(capture_diagnostics(noise, sizeof(noise)));
    }
    assert(output_used == 12 * (sizeof(row)-1));
    for (n = 0; n < 12; n++) assert(memcmp(child_output+n*(sizeof(row)-1), row, sizeof(row)-1) == 0);
    assert(diagnostics_used == SETTINGS_DIAGNOSTIC_LIMIT && diagnostics_dropped > 16384);
    assert(!capture_output(noise, SETTINGS_OUTPUT_LIMIT));
    assert(!capture_diagnostics(noise, SETTINGS_DROPPED_LIMIT));
    assert(!capture_output(noise, -1) && !capture_diagnostics(noise, -1));
    return 0;
}
