/* Original Hearth sample framing (MIT). Wire fields are explicitly little endian. */
#define SAMPLE_PAGES 64U
#define SAMPLE_RECORD 2112U
#define SAMPLE_PASSES 2U
#define SAMPLE_HEADER 32U

static unsigned int sample_crc(const unsigned char *data, unsigned int size)
{
    unsigned int crc = ~0U, i, bit;
    for (i = 0; i < size; i++) {
        crc ^= data[i];
        for (bit = 0; bit < 8; bit++)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}

static void sample_u32(unsigned char *out, unsigned int value)
{
    unsigned int i;
    for (i = 0; i < 4; i++)
        out[i] = (unsigned char)(value >> (8 * i));
}

static void sample_header(unsigned char *out, unsigned int pass, unsigned int page,
                          const unsigned char *payload)
{
    static const unsigned char magic[8] = { 'H','R','T','H','C','O','R','1' };
    unsigned int i;
    for (i = 0; i < 8; i++)
        out[i] = magic[i];
    sample_u32(out + 8, 1);
    sample_u32(out + 12, pass);
    sample_u32(out + 16, 12160U + page);
    sample_u32(out + 20, SAMPLE_RECORD);
    sample_u32(out + 24, sample_crc(payload, SAMPLE_RECORD));
    sample_u32(out + 28, sample_crc(out, 28));
}

static void sample_failure_header(unsigned char *out, unsigned int stage,
                                  unsigned int pass, unsigned int page, int code)
{
    static const unsigned char magic[8] = { 'H','R','T','H','F','A','L','1' };
    unsigned int i;
    for (i=0;i<8;i++) out[i]=magic[i];
    sample_u32(out+8,1); sample_u32(out+12,stage);
    sample_u32(out+16,pass); sample_u32(out+20,12160U+page);
    sample_u32(out+24,(unsigned int)code); sample_u32(out+28,sample_crc(out,28));
}
