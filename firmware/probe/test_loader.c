/* Host-only sanitizer regression harness for the patched GPL OMAP loader.
 * Include source fetched at the recorded revision; never open a real USB device.
 * This harness is GPL-2.0-or-later when combined with that source.
 */
#define main upstream_main
#include "omap_loader.c"
#undef main
#include <assert.h>

static int usb_calls, packet, write_calls;
static uint8_t fake_bus = 1, fake_ports[2] = {1, 1};
static int fake_depth = 1;
static int rom_mode, rom_stage, rom_offset, fail_length, settle_delays;
static useconds_t last_delay;

int __wrap_usleep(useconds_t delay)
{
    assert(delay == 1000 || delay == 20000);
    last_delay = delay;
    if (delay == 20000)
        settle_delays++;
    return 0;
}

uint8_t LIBUSB_CALL __wrap_libusb_get_bus_number(libusb_device *dev)
{
    (void)dev;
    return fake_bus;
}

int LIBUSB_CALL __wrap_libusb_get_port_numbers(libusb_device *dev, uint8_t *ports, int length)
{
    (void)dev;
    assert(length >= fake_depth);
    memcpy(ports, fake_ports, fake_depth);
    return fake_depth;
}

int LIBUSB_CALL __wrap_libusb_init(libusb_context **ctx)
{
    (void)ctx;
    usb_calls++;
    abort(); /* Argument/error tests must fail before touching USB. */
}

int LIBUSB_CALL __wrap_libusb_bulk_transfer(libusb_device_handle *handle,
    unsigned char endpoint, unsigned char *data, int length,
    int *transferred, unsigned int timeout)
{
    uint32_t opcode;
    (void)handle;
    (void)timeout;
    usb_calls++;
    assert(last_delay >= 1000); /* Every physical transfer must be paced. */
    last_delay = 0;
    if (rom_mode) {
        if (endpoint == OMAP_USB_BULK_IN) {
            assert(rom_stage == 0 && length == 512);
            memset(data, 0x5a, 69);
            *transferred = 69;
            rom_stage = 1;
            return 0;
        }
        assert(endpoint == OMAP_USB_BULK_OUT && length <= 512);
        if (rom_stage == 1) {
            assert(length == 4);
            assert(data[0] == 2 && data[1] == 0 && data[2] == 3 && data[3] == 0xf0);
            rom_stage = 2;
        } else if (rom_stage == 2) {
            assert(length == 4);
            assert(data[0] == 6 && data[1] == 4 && data[2] == 0 && data[3] == 0);
            if (fail_length) {
                *transferred = 0;
                return LIBUSB_ERROR_TIMEOUT;
            }
            rom_stage = 3;
        } else {
            int i;
            assert(rom_stage == 3);
            assert(length == ((1030 - rom_offset) > 512 ? 512 : (1030 - rom_offset)));
            for (i = 0; i < length; i++)
                assert(data[i] == 0xa5);
            rom_offset += length;
        }
        *transferred = length;
        return 0;
    }
    if (endpoint == OMAP_USB_BULK_OUT) {
        write_calls++;
        if (write_calls == 1)
            assert(length == 12);
        else if (write_calls == 2)
            assert(length == 4);
        else if (write_calls == 3) {
            assert(length == 12); /* Google x-loader rejects an eight-byte jump. */
            assert(data[0] == 'U' && data[1] == 'S' && data[2] == 'B' && data[3] == 'j');
            assert(data[8] == 0 && data[9] == 0 && data[10] == 0 && data[11] == 0);
        } else
            abort();
        *transferred = length;
        return 0;
    }
    switch (packet++) {
    case 0:
        /* Fill the complete input buffer, without a NUL terminator. The old
         * debug handler passed this data to strlen beyond the allocation.
         */
        memset(data, 'A', length);
        opcode = USBLOAD_CMD_MESSAGE;
        memcpy(data, &opcode, 4);
        *transferred = length;
        return 0;
    case 1: opcode = USBLOAD_CMD_FILE_REQ; break;
    case 2: opcode = USBLOAD_CMD_ECHO_SZ; break;
    case 3: opcode = USBLOAD_CMD_REPORT_SZ; break;
    default: abort();
    }
    memcpy(data, &opcode, 4);
    opcode = 4;
    memcpy(data + 4, &opcode, 4);
    *transferred = 8;
    return 0;
}

int main(void)
{
    char *argv[] = {"loader", "-f", "/hearth-test-nonexistent-input",
        "-f", "/hearth-test-nonexistent-input", "-a", "0x80100000",
        "-f", "/hearth-test-nonexistent-input", "-a", "0x80a00000",
        "-j", "0x80100000", NULL};
    unsigned char first_payload[1030];
    struct file_upload first = {.size = sizeof(first_payload), .data = first_payload,
        .basename = "synthetic-first"};
    unsigned char payload[4] = {0, 1, 2, 3};
    struct file_upload next = {.size = 4, .data = payload,
        .addr = 0x80100000, .basename = "synthetic"};
    struct file_upload *files[2] = { &first, &next };
    struct arg_state args = {.files = files, .numFiles = 2,
        .jumpTarget = 0x80100000};

    assert(hearth_target_port(NULL));
    fake_bus = 2;
    assert(!hearth_target_port(NULL));
    fake_bus = 1;
    fake_depth = 2;
    assert(!hearth_target_port(NULL));
    fake_depth = 1;
    fake_ports[0] = 2;
    assert(!hearth_target_port(NULL));
    fake_ports[0] = 1;
    assert(upstream_main(13, argv) == 1);
    assert(usb_calls == 0);
    memset(first_payload, 0xa5, sizeof(first_payload));
    rom_mode = 1;
    assert(transfer_first_stage(NULL, &args) == 1);
    assert(rom_offset == 1030 && settle_delays == 1 && last_delay == 20000);
    rom_stage = rom_offset = 0;
    fail_length = 1;
    assert(transfer_first_stage(NULL, &args) == 0);
    assert(rom_stage == 2 && rom_offset == 0 && settle_delays == 1);
    rom_mode = 0;
    assert(transfer_other_files(NULL, &args) == 1);
    assert(write_calls == 3); /* size/address, four data bytes, jump */
    puts("Synthetic loader regression checks passed; no real USB access.");
    return 0;
}
