/* Original host execution-dispatch check. No process or firmware is executed. */
#include <assert.h>
#include <string.h>
#include "../firmware/settings_compat_probe/exec.h"
static const char *expected;
static char *const *expected_argv,*const *expected_env;
static int calls;
static long execute(const char *path,char *const argv[],char *const env[])
{
    assert(!strcmp(path,expected));assert(argv==expected_argv&&env==expected_env);
    calls++;return -5;
}
int main(void)
{
    char *const environment[]={"LD_LIBRARY_PATH=/lib",0};
    char *const settings[]={"/settings-test","candidate",0};
    char *const files[]={"/file-test","files",0};
    expected_env=environment;expected_argv=settings;expected=settings[0];
    assert(hearth_exec_argv(settings,environment,execute)==-5);
    expected_argv=files;expected=files[0];
    assert(hearth_exec_argv(files,environment,execute)==-5&&calls==2);
    assert(hearth_exec_argv(0,environment,execute)==-22&&calls==2);
    assert(hearth_exec_argv(files,0,execute)==-22&&calls==2);
    assert(hearth_exec_argv(files,environment,0)==-22&&calls==2);
    return 0;
}
