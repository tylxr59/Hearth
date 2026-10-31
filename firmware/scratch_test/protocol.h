/* Original bounded scratch framing, MIT. No flash address/content on the wire. */
#define HS_WIRE_BYTES (128U + 2U * 135168U + 2U * 2112U)
#define HS_WIRE_HEADER 32U

static unsigned int hs_crc(const unsigned char *data, unsigned int size)
{
    unsigned int crc = ~0U, i, bit;
    for (i = 0; i < size; ++i) {
        crc ^= data[i];
        for (bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}
static void hs_u32(unsigned char *out, unsigned int value)
{
    unsigned int i;
    for (i = 0; i < 4; ++i) out[i] = value >> (8 * i);
}
static void hs_wire_header(unsigned char *out, unsigned int stage, const unsigned char *data)
{
    const unsigned char magic[8] = {'H','R','T','H','S','W','R','1'};
    unsigned int i;
    for (i = 0; i < 8; ++i) out[i] = magic[i];
    hs_u32(out + 8, 1);
    hs_u32(out + 12, stage);
    hs_u32(out + 16, HS_WIRE_BYTES);
    hs_u32(out + 20, hs_crc(data, HS_WIRE_BYTES));
    hs_u32(out + 24, 0);
    hs_u32(out + 28, hs_crc(out, 28));
}
