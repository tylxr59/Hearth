/* Original syscall simulator, MIT. Executes only the original supervisor logic. */
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include "supervisor-under-test.c"

static jmp_buf stopped;
static unsigned char cached[HS_WIRE_BYTES], sent[2*(HS_WIRE_BYTES+32)];
static unsigned int cursor, token_cursor, sent_bytes, prepared, commands;
static int mode, executed;

static long call5(long nr,long a,long b,long c,long d,long e)
{
    unsigned char *buf=(unsigned char *)b;
    (void)d;(void)e;
    if(nr==21 || nr==6)return 0;
    if(nr==162) { if(*(long *)a==1)longjmp(stopped,1); return 0; }
    if(nr==5) {
        const char *name=(const char *)a;
        if(!strcmp(name,"/sys/class/mtd/mtd0/hearth_scratch_control"))return 10;
        if(!strcmp(name,"/sys/class/mtd/mtd0/hearth_scratch_snapshot")){cursor=0;return 12;}
        assert(!strcmp(name,"/dev/ttyGS0") && b==(2|0400|04000));return 11;
    }
    if(nr==4 && a==10) {
        if(c==8) {
            assert(!prepared && !memcmp(buf,"PREPARE\n",8));prepared=1;
            memset(cached,0,sizeof(cached));memcpy(cached,"HRTHSCR1",8);
            hs_u32(cached+8,1);hs_u32(cached+12,2);
            memset(cached+64,0x4d,32);
            return 8;
        }
        assert(prepared && c==40 && !commands++ && !memcmp(buf,"HSACK001",8));
        for(unsigned int i=8;i<40;i++)
            if(buf[i]!=0x4d){hs_u32(cached+12,4);return -5;}
        executed=1;hs_u32(cached+12,5);return 40;
    }
    if(nr==4 && a==11) {
        if(mode==6 && c>17)c=17;
        assert(sent_bytes+(unsigned int)c<=sizeof(sent));
        memcpy(sent+sent_bytes,buf,(size_t)c);sent_bytes+=(unsigned int)c;return c;
    }
    if(nr==3 && a==12) {
        if(mode==4 || (mode==5 && executed))return -5;
        assert(cursor+(unsigned int)c<=HS_WIRE_BYTES);
        memcpy(buf,cached+cursor,(size_t)c);cursor+=(unsigned int)c;return c;
    }
    if(nr==3 && a==11) {
        if(token_cursor<8) {
            const char *begin=mode==1?"BADBEGIN":"HSBEGIN1";
            assert(c==(long)(8-token_cursor));
            if(mode==6 && c>3)c=3;
            memcpy(buf,begin+token_cursor,(size_t)c);token_cursor+=(unsigned int)c;return c;
        }
        unsigned char ack[40];unsigned int pos=token_cursor-8;
        assert(c==(long)(40-pos));
        if(mode==2 || (mode==7 && pos>0))return -5;
        memcpy(ack,"HSACK001",8);memset(ack+8,mode==3?0x4e:0x4d,32);
        if((mode==6 || mode==7) && c>7)c=7;
        memcpy(buf,ack+pos,(size_t)c);token_cursor+=(unsigned int)c;return c;
    }
    assert(0);return -5;
}

int main(void)
{
    for(mode=0;mode<8;mode++) {
        cursor=token_cursor=sent_bytes=prepared=commands=0;executed=0;
        memset(cached,0,sizeof(cached));memset(snapshot,0,sizeof(snapshot));
        if(!setjmp(stopped))hs_supervisor();
        assert(prepared==1 && commands<=1);
        if(mode==0 || mode==6)assert(executed && commands==1 && sent_bytes==2*(HS_WIRE_BYTES+32));
        if(mode==1 || mode==2 || mode==7)assert(!executed && !commands);
        if(mode==3)assert(!executed && commands==1 && sent_bytes==2*(HS_WIRE_BYTES+32));
        if(mode==4)assert(!executed && !commands && !sent_bytes);
        if(mode==5)assert(executed && commands==1 && sent_bytes==HS_WIRE_BYTES+32);
        if(sent_bytes) {
            assert(!memcmp(sent,"HRTHSWR1",8));
            assert(hs_crc(sent+32,HS_WIRE_BYTES)==(unsigned int)
                (sent[20]|sent[21]<<8|sent[22]<<16|(unsigned int)sent[23]<<24));
        }
    }
    puts("supervisor syscall model passed; no device execution");return 0;
}
