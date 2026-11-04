/* Original terminal handshake for child actions in a fixed RAM sequence (MIT).
 * Only a durable, host-validated successful result may be acknowledged. No
 * result acknowledgement is a commit; every writer still requires HFW_RUN1.
 */
#ifdef HEARTH_SEQUENCE_CHILD
static int hfw_finish(int fd,int eligible)
{
    static unsigned int matched;
    unsigned char ack[76],input[256];unsigned int i;long n;
    for(i=0;i<8;i++) ack[i]=(unsigned char)"HFW_DONE"[i];
    for(i=0;i<32;i++) { ack[8+i]=hearth_expected_plan[i];ack[40+i]=hearth_expected_receipt[i]; }
    for(i=0;i<4;i++) ack[72+i]=(unsigned char)(HEARTH_FILE_ACTION>>(8*i));
    n=read(fd,input,sizeof(input));
    for(i=0;n>0&&i<(unsigned long)n;i++) {
        matched=input[i]==ack[matched]?matched+1:input[i]==ack[0];
        if(matched==sizeof(ack)) { matched=0;if(eligible) return 1; }
    }
    return 0;
}
#endif
