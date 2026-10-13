from ov2640_config import *
from ov2640_regs import *

def _set_bool_register(camera, enable, label, bank, register, mask, set_on_enable=True):
    if not isinstance(enable, bool):
        camera.log(
            "{} expects bool type. Received {}: {} instead.".format(
                label, type(enable), enable
            )
        )
        return

    camera.write_reg(0xff, bank)
    value = camera.read_reg(register)[0]
    if enable == set_on_enable:
        value |= mask
    else:
        value &= ~mask
    camera.write_reg(register, value)


def _apply_sde_settings(camera):
    """Write the complete shared SDE state from the saved camera values."""
    camera.write_reg(0xff, 0x00)

    if camera.special_effect:
        idx = (camera.special_effect - 1) * 2
        chroma_0 = EFFECT_VAL[idx]
        chroma_1 = EFFECT_VAL[idx + 1]
        effect = 0x18
    else:
        chroma_0 = 0x80
        chroma_1 = 0x80
        effect = camera.bw

    # SDE control: selected color effect plus saturation and brightness/
    # contrast enable bits. All five settings share this indirect block.
    camera.write_reg(0x7c, 0x00)
    camera.write_reg(0x7d, effect | 0x06)

    saturation_idx = camera.saturation + 2
    saturation = SATURATION_LEVEL[saturation_idx]
    camera.write_reg(0x7c, 0x03)
    camera.write_reg(0x7d, saturation)
    camera.write_reg(0x7d, saturation)

    camera.write_reg(0x7c, 0x05)
    camera.write_reg(0x7d, chroma_0)
    camera.write_reg(0x7d, chroma_1)

    contrast_idx = (camera.contrast + 2) * 2
    camera.write_reg(0x7c, 0x07)
    camera.write_reg(0x7d, 0x20)
    camera.write_reg(0x7d, CONTRAST_LEVEL[contrast_idx])
    camera.write_reg(0x7d, CONTRAST_LEVEL[contrast_idx + 1])
    camera.write_reg(0x7d, 0x06)

    raw_brightness = (camera.brightness * 64 + 50) // 100
    camera.write_reg(0x7c, 0x09)
    camera.write_reg(0x7d, raw_brightness)
    camera.write_reg(0x7d, 0x00)


def set_brightness(camera, value):
    if not isinstance(value, int):
        camera.log("Brightness {} is not a valid integer.".format(value))
        return
    if value < 0 or value > 100:
        camera.log("Brightness {} must be in between 0 to 100.".format(value))
        return

    camera.brightness = value
    _apply_sde_settings(camera)


def set_contrast(camera, level):
    if not isinstance(level, int):
        camera.log(
            "Contrast level expects type int. Received {}: {}".format(
                type(level), level
            )
        )
        return
    if level > 2 or level < -2:
        camera.log("Contrast level at {}, limits at -2 to 2.".format(level))
        return

    camera.contrast = level
    _apply_sde_settings(camera)


def set_resolution(camera, h, w):
    if not (isinstance(h, int) and isinstance(w, int)):
        camera.log("{} or/and {} is not an integer.".format(h, w))
        return

    table = RESOLUTION_TABLE.get((h, w), None)
    if table is None:
        camera.log("No resolution for {}x{}.".format(h, w))
        return
    camera.reset()
    # camera.write_reg(0xff, 0x00)
    # camera.write_reg(0xe0,0x04)
    camera.write_table(OV2640_JPEG_INIT)
    camera.write_table(OV2640_JPEG)
    camera.write_table(table)
    camera.write_table(OV2640_SYS_INIT)
    camera.resolution = (h, w)
    _apply_saved_settings(camera)


def _apply_saved_settings(camera):
    """Restore non-resolution settings overwritten by a sensor reset.

    Keep the calls explicit instead of building a table of functions and
    values, which would consume extra RAM on MicroPython.
    """
    _apply_sde_settings(camera)

    set_vertical_flip(camera, camera.vflip)
    set_horizontal_flip(camera, camera.hflip)
    set_jpeg_quality(camera, camera.jpeg_quality)

    if camera.auto_exposure is not None:
        set_auto_exposure(camera, camera.auto_exposure)
    if camera.aec_enable:
        # Do not force a stale manual exposure after changing sensor timing.
        set_aec(camera, True)
    else:
        set_aec_value(camera, camera.aec_val)
        set_aec(camera, False)
    set_aec2(camera, camera.aec2_enable)

    set_agc_ceiling(camera, camera.agc_ceiling)
    if camera.agc_enable:
        # Automatic gain should start from the resolution table's state.
        set_agc(camera, True)
    else:
        set_agc_value(camera, camera.agc_value)
        set_agc(camera, False)

    set_awb_mode(camera, camera.awb_mode)
    set_awb_mode_gain(camera, camera.awb_mode_gain)
    set_lens_correction(camera, camera.lens_correction)
    # Apply the preset last. Manual modes select C7[6] after the automatic
    # white-balance block has been restored, so AWB cannot override them.
    set_wb_mode(camera, camera.wb_mode)
    set_wpc(camera, camera.wpc)
    set_bpc(camera, camera.bpc)
    set_colorbar(camera, camera.color_bar)
    

def set_vertical_flip(camera, flip):
    _set_bool_register(camera, flip, "Vertical flip", 0x01, 0x04, 0x50)
    camera.vflip = flip


def set_horizontal_flip(camera, flip):
    _set_bool_register(camera, flip, "Horizontal flip", 0x01, 0x04, 0x80)
    camera.hflip = flip

def set_jpeg_quality(camera, quality):
    if not isinstance(quality, int):
        camera.log(
            "JPEG quality expects int. Received {}: {}.".format(
                type(quality), quality
            )
        )
        return
    if quality <= 0 or quality > 63:
        camera.log("JPEG can only be in (0 - 63). Received {}".format(quality))
        return

    camera.write_reg(0xff, 0x00)
    camera.write_reg(0x44, quality)
    camera.jpeg_quality = quality

def set_saturation(camera, level):
    if not isinstance(level, int):
        camera.log(
            "Saturation level expects type int. Received {}: {}.".format(
                type(level), level
            )
        )
        return
    if level > 2 or level < -2:
        camera.log("Saturation level at {}, limits at -2 to 2.".format(level))
        return

    camera.saturation = level
    _apply_sde_settings(camera)

def set_black_white(camera, value):
    if not isinstance(value, int):
        camera.log(
            "Black and white expects type int. Received {}: {}.".format(
                type(value), value
            )
        )
        return
    if value not in (0x00, 0x18, 0x40, 0x58):
        camera.log(
            "Black and white {} can only be 0x00, 0x18, 0x40 or 0x58.".format(
                value
            )
        )
        return

    camera.bw = value
    camera.special_effect = 0
    _apply_sde_settings(camera)

# Exposure
def set_aec_value(camera, value):
    if not isinstance(value, int):
        camera.log(
            "AEC value expects type int. Received {}: {}.".format(
                type(value), value
            )
        )
        return
    if value < 0 or value > 1200:
        camera.log("AEC {} must be between 0 to 1200".format(value))
        return
    camera.write_reg(0xff, 0x01)
    
    reg04 = camera.read_reg(0x04)[0]
    reg45 = camera.read_reg(0x45)[0]
    
    reg04 = (reg04 & ~0x03) | (value & 0x03)
    reg45 = (reg45 & ~0x3F) | ((value >> 10) & 0x3F)
    aec = (value >> 2) & 0xFF
    
    camera.write_reg(0x04, reg04)
    camera.write_reg(0x45, reg45)
    camera.write_reg(0x10, aec)
    
    camera.aec_val = value
    
def set_auto_exposure(camera, level):
    if not isinstance(level, int):
        camera.log(
            "Auto exposure level expects type int. Received {}: {}.".format(
                type(level), level
            )
        )
        return
    if level > 2 or level < -2:
        camera.log("Auto exposure level at {}, limits at -2 to 2.".format(level))
        return

    # Map level -2 to table index 0, with three bytes per level.
    idx = (level + 2) * 3
    camera.write_reg(0xff, 0x01)
    camera.write_reg(0x24, AE_LEVEL[idx])
    camera.write_reg(0x25, AE_LEVEL[idx + 1])
    camera.write_reg(0x26, AE_LEVEL[idx + 2])
    camera.auto_exposure = level
    
def set_aec(camera, enable):
    _set_bool_register(camera, enable, "AEC", 0x01, 0x13, 0x01)
    camera.aec_enable = enable
    
def set_aec2(camera, enable):
    # CTRL0.AEC_SEL is active-low in the OV2640 reference driver.
    _set_bool_register(camera, enable, "AEC2", 0x00, 0xC2, 0x40, False)
    camera.aec2_enable = enable    
        
# Gain     
def set_agc(camera, enable):
    _set_bool_register(camera, enable, "AGC", 0x01, 0x13, 0x04)
    camera.agc_enable = enable    

def set_agc_ceiling(camera, ceiling):
    if not isinstance(ceiling, int):
        camera.log(
            "AGC ceiling expects int type. Received {}: {}.".format(
                type(ceiling), ceiling
            )
        )
        return
    if ceiling < 0 or ceiling > 6:
        camera.log("AGC ceiling {} must be in between 0 to 6.".format(ceiling))
        return
    camera.write_reg(0xff, 0x01)
    com9 = camera.read_reg(0x14)[0]
    com9 = (com9 & 0x1F) | (ceiling << 5)
    camera.write_reg(0x14, com9)
    camera.agc_ceiling = ceiling
    
def set_agc_value(camera, gain):
    if not isinstance(gain, int):
        camera.log(
            "Gain expects int type. Received {}: {}.".format(
                type(gain), gain
            )
        )
        return
    if gain < 0 or gain > (1 << 10) - 1:
        camera.log("AGC value {} must be between 0 to 1024".format(gain))
        return
    
    # Find table
    camera.write_reg(0xff, 0x01)
    reg45 = camera.read_reg(0x45)[0]
    
    reg45 = (reg45 & ~(3 << 6)) 
    msb = (gain >> 8) & 3
    lsb = gain & 0xFF    
    
    camera.write_reg(0x45, reg45 | (msb << 6))
    camera.write_reg(0x00, lsb)
    camera.agc_value = gain
  

# White balance
def set_wb_mode(camera, mode):
    if not isinstance(mode, int):
        camera.log(
            "White balance mode must be type int. Received {}: {}.".format(
                type(mode), mode
            )
        )
        return
    if mode > 4 or mode < 0:
        camera.log("White balance {} must be in between 0 to 4.".format(mode))
        return

    camera.write_reg(0xff, 0x00)
    c7 = camera.read_reg(0xc7)[0]
    if mode == 0:
        # Mode 0 uses automatic white balance.
        camera.write_reg(0xc7, c7 & ~0x40)
    else:
        # C7[6] selects the manual white-balance gain registers.
        camera.write_reg(0xc7, c7 | 0x40)

        # Mode 1 maps to index 0, with three bytes per manual mode.
        idx = (mode - 1) * 3
        camera.write_reg(0xcc, WB_MODE[idx])
        camera.write_reg(0xcd, WB_MODE[idx + 1])
        camera.write_reg(0xce, WB_MODE[idx + 2])

    camera.wb_mode = mode
    
def set_special_effect(camera, effect):
    if not isinstance(effect, int):
        camera.log(
            "Special effect must be type int. Received {}: {}.".format(
                type(effect), effect
            )
        )
        return
    if effect < 0 or effect > 4:
        camera.log(f"special effect only allow (0-4), recevied {effect}")
        return
    
    camera.special_effect = effect
    camera.bw = 0
    _apply_sde_settings(camera)
    

def set_awb_mode(camera, enable):
    _set_bool_register(camera, enable, "Auto white balance", 0x00, 0xC3, 0x08)
    camera.awb_mode = enable

def set_awb_mode_gain(camera, enable):
    _set_bool_register(camera, enable, "Auto white balance gain", 0x00, 0xC3, 0x04)
    camera.awb_mode_gain = enable    

def set_lens_correction(camera, enable):
    _set_bool_register(camera, enable, "Lens correction", 0x00, 0xC3, 0x02)
    camera.lens_correction = enable    

def set_wpc(camera, enable):
    _set_bool_register(camera, enable, "White pixel correction", 0x00, 0x87, 0x40)
    camera.wpc = enable    

def set_bpc(camera, enable):
    _set_bool_register(camera, enable, "Black pixel correction", 0x00, 0x87, 0x80)
    camera.bpc = enable

def set_colorbar(camera, enable):
    _set_bool_register(camera, enable, "Color bar", 0x01, 0x12, 0x02)
    camera.color_bar = enable

def reset_sde(camera, reset):
    # Reset no matter the value
    camera.write_reg(0xff, 0x00)

    # Neutral saturation
    camera.write_reg(0x7c, 0x03)
    camera.write_reg(0x7d, 0x48)
    camera.write_reg(0x7d, 0x48)

    # Neutral special-effect chroma
    camera.write_reg(0x7c, 0x05)
    camera.write_reg(0x7d, 0x80)
    camera.write_reg(0x7d, 0x80)

    # Neutral contrast and brightness
    camera.write_reg(0x7c, 0x07)
    camera.write_reg(0x7d, 0x20)
    camera.write_reg(0x7d, 0x20)
    camera.write_reg(0x7d, 0x20)
    camera.write_reg(0x7d, 0x06)

    # Disable individual SDE operations last.
    camera.write_reg(0x7c, 0x00)
    camera.write_reg(0x7d, 0x00)

def send_grey(camera, reset = True):
    camera.grey = True
