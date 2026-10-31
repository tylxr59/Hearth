/* Original hardware-free lifecycle fault cases. No filesystem/device calls. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "../firmware/file_writer/lifecycle.h"
struct fake { int scenario,restoring,transacted,wanted_new;char calls[64];unsigned int used; };
static void add(struct fake *f,char c) { assert(f->used<sizeof(f->calls)-1);f->calls[f->used++]=c;f->calls[f->used]=0; }
static int preflight(void *p) { struct fake *f=p;add(f,'p');return f->scenario==1?-1:0; }
static int open_window(void *p) { struct fake *f=p;add(f,'o');return f->scenario==2?-1:0; }
static int remount(void *p,unsigned int i) { struct fake *f=p;add(f,'0'+i);return f->scenario==(int)(3+i)?-1:0; }
static void transact(void *p,struct hearth_install_result *r)
{
    struct fake *f=p;add(f,'t');f->transacted=1;memset(r,0,sizeof(*r));
    r->attempted=511;r->committed=!f->restoring;if(f->restoring) r->restored=511;
    if(f->scenario==11||f->scenario==12) {
        r->error=HEARTH_ACTIVATE_FAILED;r->committed=0;r->restored=511;
        if(f->scenario==12) { r->rollback_error=1;r->restored=0; }
    }
    if(f->scenario==13) r->cleanup_error=1;
    if(f->scenario==14) r->journal_error=1;
}
static int release(void *p) { struct fake *f=p;add(f,'r');return f->scenario==5?-1:0; }
static int unmount(void *p,unsigned int i) { struct fake *f=p;add(f,i?'u':'v');return f->scenario==(int)(6+i)?-1:0; }
static int seal(void *p) { struct fake *f=p;add(f,'s');return f->scenario==8?-1:0; }
static int verify(void *p,int wanted_new)
{
    struct fake *f=p;add(f,'c');f->wanted_new=wanted_new;
    assert(wanted_new==(f->transacted&&!f->restoring&&f->scenario!=11&&f->scenario!=12));
    return f->scenario==9||f->scenario==12?-1:0;
}
int main(int argc,char **argv)
{
    struct fake f={0};struct hfa_result r;
    const struct hfa_ops ops={preflight,open_window,remount,transact,release,unmount,seal,verify};
    assert(argc==2);f.scenario=atoi(argv[1]);f.restoring=f.scenario==10;
    if(f.scenario==15) {
        r=hfa_cancel(&ops,&f);assert(!strcmp(f.calls,"ruvs")&&r.safe_to_restart&&!r.complete&&!r.rw_attempted);return 0;
    }
    r=hfa_run(&ops,&f,f.restoring);
    assert(strstr(f.calls,"ruvs")!=NULL); /* Never skip cleanup/protection. */
    assert(r.transaction_called==(f.scenario==0||f.scenario>=5));
    if(f.scenario==0||f.scenario==10) {
        assert(!strcmp(f.calls,"po01truvsc")&&r.complete&&r.safe_to_restart&&r.verified);
    } else assert(!r.complete);
    if(f.scenario==1||f.scenario==2) {
        assert(!r.rw_attempted&&r.safe_to_restart&&!r.verified&&!f.transacted);
    }
    if(f.scenario==3) assert(r.rw_attempted==1&&!f.transacted&&r.safe_to_restart);
    if(f.scenario==4) assert(r.rw_attempted==3&&!f.transacted&&r.safe_to_restart);
    if(f.scenario>=5&&f.scenario<=9) assert(!r.safe_to_restart);
    if(f.scenario>=5&&f.scenario<=8) assert(strchr(f.calls,'c')==NULL);
    if(f.scenario==11) assert(r.safe_to_restart&&!r.transaction.committed&&r.verified);
    if(f.scenario==12) assert(!r.safe_to_restart&&r.transaction.rollback_error);
    if(f.scenario==13||f.scenario==14) assert(r.safe_to_restart&&r.transaction.committed&&!r.complete);
    return 0;
}
