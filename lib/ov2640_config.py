CONTRAST_LEVEL = (
    b'\x18\x34'
    b'\x1C\x2A'
    b'\x20\x20'
    b'\x24\x16'
    b'\x28\x0C'
)

SATURATION_LEVEL = (
    b'\x28' # -2
    b'\x38'	# -1
    b'\x48'	# 0
    b'\x58'	# 1
    b'\x68'	# 2
)

AE_LEVEL = (
    b'\x20\x18\x60'
    b'\x34\x1c\x00'
    b'\x3e\x38\x81'
    b'\x48\x40\x81'
    b'\x58\x50\x92'
)

WB_MODE = (
    b'\x5E\x41\x54' # Sunny
    b'\x65\x41\x4F' # Cloudy
    b'\x52\x41\x66'	# Office
    b'\x42\x3F\x71'	# Home
)

EFFECT_VAL = (
    b'\x40\xa6'  # Antique
    b'\xa0\x40'  # Bluish
    b'\x40\x40'  # Greenish
    b'\x40\xc0'  # Reddish
)


