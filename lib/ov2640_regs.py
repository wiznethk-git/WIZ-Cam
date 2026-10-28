"""Generated OV2640 register tables; do not reorder writes.

Source: ov2640_regs.h.
Regenerate with gen/convert_ov2640_regs.py.
"""


# ============================================================
# Common sensor and DVP timing
# ============================================================

# Apply this after OV2640_JPEG_INIT, OV2640_JPEG, and the selected resolution
# table.  Keeping these writes here prevents resolution changes from silently
# selecting different sensor or DVP clocks.
OV2640_SYS_INIT = (
    # DSP bank: DVP output-clock divider
    b'\xFF\x00'
    b'\x2C\xFF'
    b'\x2E\xDF'
    b'\x00\x00'
  
    # Sensor bank: internal clock doubler/divider and frame-length adjustment
    b'\xFF\x01'
    b'\x11\x80'
    b'\x2B\x00'
    b'\x46\x55'
    
)


# ============================================================
# SVGA 800x600
# ============================================================

OV2640_SVGA_800X600 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x40'
    b'\x03\x0A'
    b'\x17\x11'
    b'\x18\x43'
    b'\x19\x00'
    b'\x1A\x4B'
    b'\x32\x09'
    b'\x37\xC0'
    b'\x4F\xCA'
    b'\x50\xA8'
    b'\x5A\x23'
    b'\x6D\x00'
    b'\x3D\x38'
    b'\x39\x12'
    b'\x35\xDA'
    b'\x22\x1A'
    b'\x37\xC3'
    b'\x23\x00'
    b'\x34\xC0'
    b'\x36\x1A'
    b'\x06\x88'
    b'\x07\xC0'
    b'\x0D\x87'
    b'\x0E\x41'
    b'\x4C\x00'
    # DSP bank
    b'\xFF\x00'
    b'\xD3\x16'
    b'\xE0\x04'
    b'\xC0\x64'
    b'\xC1\x4B'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x80'
    b'\x51\xC8'
    b'\x52\x96'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x57\x00'
    b'\x5A\xC8'
    b'\x5B\x96'
    b'\x5C\x00'
    b'\x44\x14'
    b'\xE0\x00'
)


OV2640_VGA_640X480 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x40'
    b'\x03\x0A'
    b'\x17\x11'
    b'\x18\x43'
    b'\x19\x00'
    b'\x1A\x4B'
    b'\x32\x09'
    b'\x37\xC0'
    b'\x4F\xCA'
    b'\x50\xA8'
    b'\x5A\x23'
    b'\x6D\x00'
    b'\x3D\x38'
    b'\x39\x12'
    b'\x35\xDA'
    b'\x22\x1A'
    b'\x37\xC3'
    b'\x23\x00'
    b'\x34\xC0'
    b'\x36\x1A'
    b'\x06\x88'
    b'\x07\xC0'
    b'\x0D\x87'
    b'\x0E\x41'
    b'\x4C\x00'
    # DSP bank
    b'\xFF\x00'
    b'\xD3\x24'
    b'\xE0\x04'
    b'\xC0\x64'
    b'\xC1\x4B'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x80'
    b'\x51\xC8'
    b'\x52\x96'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x57\x00'
    b'\x5A\xA0'
    b'\x5B\x78'
    b'\x5C\x00'
    b'\x44\x14'
    b'\xE0\x00'
)


OV2640_UXGA_1280X960 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x00'
    b'\x03\x0F'
    b'\x17\x11'
    b'\x18\x75'
    b'\x19\x01'
    b'\x1A\x97'
    b'\x32\x36'
    b'\x37\x40'
    b'\x4F\xBB'
    b'\x50\x9C'
    b'\x5A\x57'
    b'\x6D\x80'
    b'\x3D\x34'
    b'\x39\x02'
    b'\x35\x88'
    b'\x22\x0A'
    b'\x37\x40'
    b'\x34\xA0'
    b'\x06\x02'
    b'\x0D\xB7'
    b'\x0E\x01'

    # DSP bank
    b'\xFF\x00'
    b'\xD3\x14'
    b'\xE0\x04'
    b'\xC0\xC8'
    b'\xC1\x96'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x80'
    b'\x51\x90'
    b'\x52\x2C'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x88'
    b'\x57\x00'
    b'\x5A\x40'
    b'\x5B\xF0'
    b'\x5C\x01'
    b'\x44\x14'
    b'\xE0\x00'
)


OV2640_UXGA_1024X768 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x00'
    b'\x03\x0F'
    b'\x17\x11'
    b'\x18\x75'
    b'\x19\x01'
    b'\x1A\x97'
    b'\x32\x36'
    b'\x37\x40'
    b'\x4F\xBB'
    b'\x50\x9C'
    b'\x5A\x57'
    b'\x6D\x80'
    b'\x3D\x34'
    b'\x39\x02'
    b'\x35\x88'
    b'\x22\x0A'
    b'\x37\x40'
    b'\x34\xA0'
    b'\x06\x02'
    b'\x0D\xB7'
    b'\x0E\x01'

    # DSP bank
    b'\xFF\x00'
    b'\xD3\x18'
    b'\xE0\x04'
    b'\xC0\xC8'
    b'\xC1\x96'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x80'
    b'\x51\x90'
    b'\x52\x2C'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x88'
    b'\x57\x00'
    b'\x5A\x00'
    b'\x5B\xC0'
    b'\x5C\x01'
    b'\x44\x14'
    b'\xE0\x00'
)


OV2640_CIF_320X240 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x20'
    b'\x03\x06'
    b'\x17\x11'
    b'\x18\x43'
    b'\x19\x00'
    b'\x1A\x25'
    # CIF needs a brighter automatic-exposure stable region than JPEG_INIT.
    b'\x24\x60'
    b'\x25\x58'
    b'\x32\x09'
    b'\x37\xC0'
    b'\x4F\xCA'
    b'\x50\xA8'
    b'\x5A\x23'
    b'\x6D\x00'
    b'\x3D\x38'
    b'\x39\x12'
    b'\x35\xDA'
    b'\x22\x1A'
    b'\x37\xC3'
    b'\x23\x00'
    b'\x34\xC0'
    b'\x36\x1A'
    b'\x06\x88'
    b'\x07\xC0'
    b'\x0D\x87'
    b'\x0E\x41'
    b'\x4C\x00'

    # DSP bank
    b'\xFF\x00'
    b'\xD3\x20'
    b'\xE0\x04'
    b'\xC0\x32'
    b'\xC1\x25'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x80'
    b'\x51\x64'
    b'\x52\x4A'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x57\x00'
    b'\x5A\x50'
    b'\x5B\x3C'
    b'\x5C\x00'
    b'\x44\x14'
    b'\xE0\x00'
)


OV2640_CIF_176X144 = (
    # Sensor bank
    b'\xFF\x01'
    b'\x12\x20'
    b'\x03\x06'
    b'\x17\x11'
    b'\x18\x43'
    b'\x19\x00'
    b'\x1A\x25'
    # CIF needs a brighter automatic-exposure stable region than JPEG_INIT.
    b'\x24\x60'
    b'\x25\x58'
    b'\x32\x09'
    b'\x37\xC0'
    b'\x4F\xCA'
    b'\x50\xA8'
    b'\x5A\x23'
    b'\x6D\x00'
    b'\x3D\x38'
    b'\x39\x12'
    b'\x35\xDA'
    b'\x22\x1A'
    b'\x37\xC3'
    b'\x23\x00'
    b'\x34\xC0'
    b'\x36\x1A'
    b'\x06\x88'
    b'\x07\xC0'
    b'\x0D\x87'
    b'\x0E\x41'
    b'\x4C\x00'

    # DSP bank
    b'\xFF\x00'
    b'\xD3\x18'
    b'\xE0\x04'
    b'\xC0\x32'
    b'\xC1\x25'
    b'\x8C\x00'
    b'\x86\x35'
    b'\x50\x89'
    b'\x51\x64'
    b'\x52\x4A'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x57\x00'
    b'\x5A\x2C'
    b'\x5B\x24'
    b'\x5C\x00'
    b'\x44\x14'
    b'\xE0\x00'
    
    
)


# ============================================================
# JPEG configuration
# ============================================================

OV2640_JPEG = (
    b'\xE0\x14'
    b'\xE1\x77'
    b'\xE5\x1F'
    b'\xD7\x03'
    b'\xDA\x10'
    b'\xE0\x00'
    b'\xFF\x01'
    b'\x04\x08'
)


# ============================================================
# JPEG initialization
# ============================================================

OV2640_MAX_AUTO_EXPOSURE = (
    b'\xFF\x01'
    b'\x13\xE5'
)



OV2640_JPEG_INIT = (
    # Initial sequence
    b'\xFF\x01'
    b'\x3C\x32'

    # CLKRC
    # 0x00 = XCLK not divided
    b'\x11\x00'

    b'\x09\x02'
    b'\x04\x28'

    # Automatic exposure / gain / white-balance related setup
    b'\x13\xE5'

    # Maximum exposure gain
    b'\x14\x48'

    b'\x2C\x0C'
    b'\x33\x78'
    b'\x3A\x33'
    b'\x3B\xFB'
    b'\x3E\x00'
    b'\x43\x11'
    b'\x16\x10'
    b'\x39\x92'
    b'\x35\xDA'
    b'\x22\x1A'
    b'\x37\xC3'
    b'\x23\x00'
    b'\x34\xC0'
    b'\x36\x1A'
    b'\x06\x88'
    b'\x07\xC0'
    b'\x0D\x87'
    b'\x0E\x41'
    b'\x4C\x00'
    b'\x48\x00'
    b'\x5B\x00'
    b'\x42\x03'
    b'\x4A\x81'
    b'\x21\x99'
    b'\x24\x40'
    b'\x25\x38'
    b'\x26\x82'
    b'\x5C\x00'
    b'\x63\x00'
    b'\x61\x70'
    b'\x62\x80'
    b'\x7C\x05'
    b'\x20\x80'
    b'\x28\x30'
    b'\x6C\x00'
    b'\x6D\x80'
    b'\x6E\x00'
    b'\x70\x02'
    b'\x71\x94'
    b'\x73\xC1'
    b'\x12\x40'
    b'\x17\x11'
    b'\x18\x43'
    b'\x19\x00'
    b'\x1A\x4B'
    b'\x32\x09'
    b'\x37\xC0'
    b'\x4F\x60'
    b'\x50\xA8'
    b'\x6D\x00'
    b'\x3D\x38'
    b'\x46\x3F'
    b'\x0C\x3C'

    # Switch to DSP bank
    b'\xFF\x00'
    b'\xE5\x7F'
    b'\xF9\xC0'
    b'\x41\x24'
    b'\xE0\x14'
    b'\x76\xFF'
    b'\x33\xA0'
    b'\x42\x20'
    b'\x43\x18'
    b'\x4C\x00'
    b'\x87\xD5'
    b'\x88\x3F'
    b'\xD7\x03'
    b'\xD9\x10'
    b'\xD3\x20'
    b'\xC8\x08'
    b'\xC9\x80'

    b'\x7C\x00'
    b'\x7D\x00'

    b'\x7C\x03'
    b'\x7D\x48'
    b'\x7D\x48'

    b'\x7C\x08'
    b'\x7D\x20'
    b'\x7D\x10'
    b'\x7D\x0E'

    b'\x90\x00'

    b'\x91\x0E'
    b'\x91\x1A'
    b'\x91\x31'
    b'\x91\x5A'
    b'\x91\x69'
    b'\x91\x75'
    b'\x91\x7E'
    b'\x91\x88'
    b'\x91\x8F'
    b'\x91\x96'
    b'\x91\xA3'
    b'\x91\xAF'
    b'\x91\xC4'
    b'\x91\xD7'
    b'\x91\xE8'
    b'\x91\x20'

    b'\x92\x00'

    b'\x93\x06'
    b'\x93\xE3'
    b'\x93\x05'
    b'\x93\x05'
    b'\x93\x00'
    b'\x93\x04'
    b'\x93\x00'
    b'\x93\x00'
    b'\x93\x00'
    b'\x93\x00'
    b'\x93\x00'
    b'\x93\x00'
    b'\x93\x00'

    b'\x96\x00'

    b'\x97\x08'
    b'\x97\x19'
    b'\x97\x02'
    b'\x97\x0C'
    b'\x97\x24'
    b'\x97\x30'
    b'\x97\x28'
    b'\x97\x26'
    b'\x97\x02'
    b'\x97\x98'
    b'\x97\x80'
    b'\x97\x00'
    b'\x97\x00'

    b'\xC3\xED'
    b'\xA4\x00'
    b'\xA8\x00'
    b'\xC5\x11'
    b'\xC6\x51'
    b'\xBF\x80'
    b'\xC7\x10'
    b'\xB6\x66'
    b'\xB8\xA5'
    b'\xB7\x64'
    b'\xB9\x7C'
    b'\xB3\xAF'
    b'\xB4\x97'
    b'\xB5\xFF'
    b'\xB0\xC5'
    b'\xB1\x94'
    b'\xB2\x0F'
    b'\xC4\x5C'

    b'\xC0\x64'
    b'\xC1\x4B'
    b'\x8C\x00'
    b'\x86\x3D'
    b'\x50\x00'
    b'\x51\xC8'
    b'\x52\x96'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x5A\xC8'
    b'\x5B\x96'
    b'\x5C\x00'
    b'\xD3\x7F'

    b'\xC3\xED'
    b'\x7F\x00'
    b'\xDA\x00'
    b'\xE5\x1F'
    b'\xE1\x67'
    b'\xE0\x00'
    b'\xDD\x7F'
    b'\x05\x00'
    b'\x12\x40'
    b'\xD3\x7F'

    b'\xC0\x16'
    b'\xC1\x12'
    b'\x8C\x00'
    b'\x86\x3D'
    b'\x50\x00'
    b'\x51\x2C'
    b'\x52\x24'
    b'\x53\x00'
    b'\x54\x00'
    b'\x55\x00'
    b'\x5A\x2C'
    b'\x5B\x24'
    b'\x5C\x00'
)



RESOLUTION_TABLE = {
    (1280, 960): OV2640_UXGA_1280X960,
    (1024, 768): OV2640_UXGA_1024X768,
    (800, 600): OV2640_SVGA_800X600,
    (640, 480): OV2640_VGA_640X480,
    (320, 240): OV2640_CIF_320X240,
    (176, 144): OV2640_CIF_176X144,
}

# RESOLUTION_TABLE = [
#     OV2640_UXGA_1280X960,
#     OV2640_UXGA_1024X768,
#     OV2640_SVGA_800X600,
#     OV2640_VGA_640X480,
#     OV2640_CIF_320X240,
#     OV2640_CIF_176X144,
# ]
