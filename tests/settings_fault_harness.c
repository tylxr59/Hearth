/* Execute ONLY original host-built code against an original NSPR test double. */
#include <assert.h>
#include <stdio.h>
#include <dlfcn.h>
#include <unistd.h>
#include "../firmware/settings_probe/faults.h"
int main(int argc, char **argv)
{
    char temporary[1024], destination[1024], decoy[1024];
    int mode;
    assert(argc == 3);
    assert(dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL));
    assert(fault_load());
    snprintf(temporary, sizeof(temporary), "%s/target.tmp", argv[2]);
    snprintf(destination, sizeof(destination), "%s/target", argv[2]);
    snprintf(decoy, sizeof(decoy), "%s/decoy", argv[2]);
    for (mode = NORMAL; mode <= DIR_CLOSE; mode++) {
        void *file, *directory, *other;
        int r;
        fault_begin(mode, argv[2], destination, temporary);
        other = PR_Open(decoy, 0x2a, 0600); assert(other);
        assert(PR_Write(other, "<s key=\"x\" value=\"y\"/>\n", 23) == 23);
        assert(PR_Sync(other) == 0 && PR_Close(other) == 0);
        assert(observed.injected == 0 && observed.file_opens == 0);
        file = PR_Open(temporary, 0x2a, 0600);
        assert((file == NULL) == (mode == FILE_OPEN));
        if (file) {
            r = PR_Write(file, "<settings>\n", 11); assert(r == (mode == HEADER_WRITE ? -1 : 11));
            r = PR_Write(file, "<s key=\"x\" value=\"y\"/>\n", 23);
            assert(r == (mode == ENTRY_ERROR ? -1 : mode == ENTRY_SHORT ? 11 : 23));
            r = PR_Write(file, "</settings>\n", 12); assert(r == (mode == FOOTER_WRITE ? -1 : 12));
            assert(PR_Sync(file) == (mode == FILE_SYNC ? -1 : 0));
            assert(PR_Close(file) == (mode == FILE_CLOSE ? -1 : 0));
            assert(rename(temporary, destination) == (mode == RENAME ? -1 : 0));
        }
        directory = PR_Open(argv[2], 1, 0);
        assert((directory == NULL) == (mode == DIR_OPEN));
        if (directory) {
            assert(PR_Sync(directory) == (mode == DIR_SYNC ? -1 : 0));
            assert(PR_Close(directory) == (mode == DIR_CLOSE ? -1 : 0));
        }
        assert(observed.injected == (mode != NORMAL));
        /* Injection is one-shot even if the same selected operation repeats. */
        file = PR_Open(temporary, 0x2a, 0600); assert(file);
        assert(PR_Write(file, "<s key=\"x\" value=\"y\"/>\n", 23) == 23);
        assert(PR_Sync(file) == 0 && PR_Close(file) == 0);
        assert(rename(temporary, destination) == 0);
        directory = PR_Open(argv[2], 1, 0); assert(directory);
        assert(PR_Sync(directory) == 0 && PR_Close(directory) == 0);
        assert(observed.injected == (mode != NORMAL));
        fault_disarm();
    }
    return 0;
}
