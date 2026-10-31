/* Original fixed-argv execution adapter. No shell or user-selected commands. */
#ifndef HEARTH_LAB_EXEC_H
#define HEARTH_LAB_EXEC_H
static long hearth_exec_argv(char *const argv[],char *const env[],
    long (*execute)(const char *,char *const [],char *const []))
{
    if(!argv||!argv[0]||!env||!execute) return -22;
    return execute(argv[0],argv,env);
}
#endif
