/* Original fixed three-stage policy (MIT). No reset/reopen of a sealed window.
 * Each slot is initialized once and can be selected only once, in order.
 * The capacity slot never permits writes. Cleanup has root0-only range checks.
 */
#ifndef HEARTH_INSTALL_SEQUENCE_H
#define HEARTH_INSTALL_SEQUENCE_H
#include "core.h"
struct hf_sequence { struct hf_window windows[3];unsigned int selected; };
static void hf_sequence_init(struct hf_sequence *s,const unsigned char plans[3][32],
                             const unsigned char receipts[3][32])
{
    unsigned int i;s->selected=0;
    for(i=0;i<3;i++) hf_init(&s->windows[i],plans[i],receipts[i]);
}
static int hf_sequence_next(struct hf_sequence *s,const unsigned char *plan,
                            const unsigned char *receipt,int protected,int unmounted)
{
    unsigned int i,difference=0;struct hf_window *old,*next;
    if(!s||!plan||!receipt||s->selected>=2||protected!=1||unmounted!=1) return -1;
    old=&s->windows[s->selected];next=&s->windows[s->selected+1];
    if(old->phase!=HF_SEALED||old->failed||next->phase!=HF_DISABLED) return -1;
    if(!s->selected&&(old->attempted[0]||old->attempted[1]||old->attempted[2])) return -1;
    if(s->selected==1&&!old->attempted[0]) return -1;
    for(i=0;i<32;i++) difference|=(plan[i]^next->plan[i])|(receipt[i]^next->receipt[i]);
    if(difference) return -1;
    s->selected++;return 0;
}
#endif
