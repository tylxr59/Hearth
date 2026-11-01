/* Original host execution of the exact source intended for the RAM image. */
#include <assert.h>
#include "../firmware/network_update/ram.h"
int main(void)
{
 unsigned int cases=0;assert(hn_ram_selftest(&cases)==0&&cases==HN_RAM_CASES);return 0;
}
