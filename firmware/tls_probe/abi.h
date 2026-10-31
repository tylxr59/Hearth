/* Minimal Linux ARM/glibc declarations for the isolated RAM test helper.
 * No thermostat headers or private source are required to compile this file. */
#ifndef HEARTH_TLS_ABI_H
#define HEARTH_TLS_ABI_H
typedef __SIZE_TYPE__ size_t;
typedef unsigned short u16;
typedef unsigned int u32;
struct address { u16 family, port; u32 ip; unsigned char zero[8]; };
extern int socket(int, int, int), bind(int, const void *, unsigned int);
extern int listen(int, int), accept(int, void *, void *), close(int);
extern int setsockopt(int, int, int, const void *, unsigned int);
extern int fork(void), waitpid(int, int *, int);
extern unsigned int alarm(unsigned int);
extern void _exit(int) __attribute__((noreturn));
extern long time(void *);
extern long write(int, const void *, size_t);
extern int snprintf(char *, size_t, const char *, ...);
extern int strcmp(const char *, const char *);
extern void *dlopen(const char *, int), *dlsym(void *, const char *);
extern char *dlerror(void);
extern void (*signal(int, void (*)(int)))(int);
#endif
