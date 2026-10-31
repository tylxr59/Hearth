/* Original scanner tests; only public synthetic strings, never native logs. */
#include <assert.h>
#include <string.h>
#include "../firmware/settings_compat_probe/scan.h"
int main(void)
{
    struct stream_scan scan;
    const char *text="xxsynthetic_secret_newyysynthetic_secret_oldzz";
    long size=strlen(text);
    for(long split=0;split<=size;split++) {
        assert(scan_init(&scan,"synthetic_secret_"));
        scan_bytes(&scan,(const unsigned char *)text,split);
        scan_bytes(&scan,(const unsigned char *)text+split,size-split);
        assert(scan.matches==2);
    }
    assert(scan_init(&scan,"synthetic_secret_"));
    for(int n=0;n<100000;n++) scan_bytes(&scan,(const unsigned char *)"x",1);
    for(long n=0;n<size;n++) scan_bytes(&scan,(const unsigned char *)text+n,1);
    assert(scan.matches==2); /* scan continues long after the diagnostic cache fills */
    assert(scan_init(&scan,"abababa"));
    scan_bytes(&scan,(const unsigned char *)"abababababa",11);
    assert(scan.matches==3);
    assert(!scan_init(&scan,""));
    assert(!scan_init(&scan,"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"));
    return 0;
}
