/* Original bounded read-only backup fingerprinting (MIT). No mutable opens. */
#include "../network_update/hash.h"
static unsigned char backup_report[532];
static int backup_inventory(int fd)
{
 unsigned char data[2048];unsigned int entries=0,seen=0;long count;
 while((count=raw(217,fd,(long)data,sizeof(data),0,0))>0) {
  unsigned int at=0;if((unsigned long)count>sizeof(data)) return -1;
  while(at<(unsigned long)count) {
   char name[64];unsigned int n=0,length,bit=0;
   if((unsigned long)count-at<20||++entries>32) return -1;
   length=data[at+16]|(unsigned int)data[at+17]<<8;
   if(length<20||length>(unsigned long)count-at) return -1;
   while(19+n<length&&data[at+19+n]) {
    if(n>=sizeof(name)-1||data[at+19+n]=='/') return -1;
    name[n]=(char)data[at+19+n];n++;
   }
   if(!n||19+n>=length) return -1;name[n]=0;at+=length;
   if((n==1&&name[0]=='.')||(n==2&&name[0]=='.'&&name[1]=='.')) continue;
   if(n==7&&name[0]=='j'&&name[1]=='o'&&name[2]=='u'&&name[3]=='r'&&name[4]=='n'&&name[5]=='a'&&name[6]=='l') bit=512;
   else if(n==10&&name[0]>='0'&&name[0]<='8'&&name[1]=='.'&&name[2]=='o'&&name[3]=='r'&&name[4]=='i'&&name[5]=='g'&&name[6]=='i'&&name[7]=='n'&&name[8]=='a'&&name[9]=='l') bit=1U<<(name[0]-'0');
   if(!bit||(seen&bit)) return -1;seen|=bit;
  }
 }
 return count==0 ? 0 : -1;
}
static void backup_fingerprints(int directory,const char *const names[10])
{
 unsigned int i;unsigned long long info[16];
 put(backup_report,1);put(backup_report+4,10);put(backup_report+8,(unsigned int)-1);
 if(directory<0||raw(197,directory,(long)info,0,0,0)) return;
 {
  unsigned char *b=(unsigned char *)info;unsigned int mode=(unsigned int)b[16]|(unsigned int)b[17]<<8|(unsigned int)b[18]<<16|(unsigned int)b[19]<<24;
  if(mode!=0040700||b[24]||b[25]||b[26]||b[27]||b[28]||b[29]||b[30]||b[31]||flistxattr(directory,0,0)) return;
 }
 put(backup_report+8,(unsigned int)backup_inventory(directory));
 for(i=0;i<10;i++) {
  unsigned char *row=backup_report+12+52*i,buffer[4096],*b=(unsigned char *)info;
  struct hn_hash hash;unsigned int size,at=0,j;long fd=raw(322,directory,(long)names[i],2048|32768|524288,0,0),status=-1;
  if(fd<0) { put(row,(unsigned int)fd);continue; }
  if(raw(197,fd,(long)info,0,0,0)) goto done;
  for(j=0;j<4;j++) put(row+4+4*j,(unsigned int)b[(j==0?16:j==1?24:j==2?28:48)]|
      (unsigned int)b[(j==0?16:j==1?24:j==2?28:48)+1]<<8|
      (unsigned int)b[(j==0?16:j==1?24:j==2?28:48)+2]<<16|
      (unsigned int)b[(j==0?16:j==1?24:j==2?28:48)+3]<<24);
  size=(unsigned int)b[48]|(unsigned int)b[49]<<8|(unsigned int)b[50]<<16|(unsigned int)b[51]<<24;
  if(row[4]!=0x80||row[5]!=0x81||row[6]||row[7]||b[20]!=1||b[21]||b[22]||b[23]||
     b[24]||b[25]||b[26]||b[27]||b[28]||b[29]||b[30]||b[31]||
     b[52]||b[53]||b[54]||b[55]||size>HEARTH_FILE_BYTES||flistxattr((int)fd,0,0)) goto done;
  hn_hash_init(&hash);
  while(at<size) {
   unsigned int amount=size-at;long n;if(amount>sizeof(buffer)) amount=sizeof(buffer);
   n=raw(3,fd,(long)buffer,amount,0,0);if(n==-4) continue;
   if(n<=0||(unsigned long)n>amount||hn_hash_update(&hash,buffer,(unsigned int)n)) goto done;
   at+=(unsigned int)n;
  }
  if(raw(3,fd,(long)buffer,1,0,0)||hn_hash_final(&hash,row+20)) goto done;
  status=0;
done:
  if(raw(6,fd,0,0,0,0)) status=-1;put(row,(unsigned int)status);
 }
}
