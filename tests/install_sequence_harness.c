/* Original host-only sequence gate fault matrix. No device or filesystem API. */
#include <assert.h>
#include "../firmware/file_writer/sequence.h"
int main(void)
{
 struct hf_sequence s;unsigned char plans[3][32]={{1},{2},{3}},receipts[3][32]={{4},{5},{6}};
 unsigned int fault;
 for(fault=0;fault<8;fault++) {
  hf_sequence_init(&s,plans,receipts);s.windows[0].phase=HF_SEALED;
  if(fault==0) s.windows[0].phase=HF_DISABLED;
  if(fault==1) s.windows[0].failed=1;
  if(fault==2) s.windows[0].attempted[0]=1;
  if(fault==3) s.windows[1].phase=HF_SEALED;
  assert(hf_sequence_next(&s,fault==4?plans[2]:plans[1],fault==5?receipts[2]:receipts[1],fault==6?0:1,fault==7?0:1));
  assert(s.selected==0);
 }
 hf_sequence_init(&s,plans,receipts);s.windows[0].phase=HF_SEALED;
 assert(!hf_sequence_next(&s,plans[1],receipts[1],1,1));
 assert(s.selected==1&&s.windows[0].phase==HF_SEALED);
 assert(hf_sequence_next(&s,plans[2],receipts[2],1,1));
 s.windows[1].phase=HF_SEALED;
 assert(hf_sequence_next(&s,plans[2],receipts[2],1,1)); /* no page programs */
 s.windows[1].attempted[0]=5;
 assert(!hf_sequence_next(&s,plans[2],receipts[2],1,1));
 assert(s.selected==2&&s.windows[1].phase==HF_SEALED);
 assert(hf_sequence_next(&s,plans[1],receipts[1],1,1)); /* never backward */
 assert(hf_sequence_next(&s,plans[2],receipts[2],1,1)); /* never replay */
 return 0;
}
