import gc
import time
import socket
from setup import SetUpWiznetChip
import machine
import micropython
from machine import SoftI2C, Pin, mem32
from ov2640_regs import *
from server import CommandServer
from rtsp_server import RTSPServer
from mic import Microphone

# Set start light
Pin('PG2', Pin.OUT).value(0)

try:
    from config import DRIVER
except ImportError:
    DRIVER = "ov2640"

def load_driver(name):
    module = __import__("_" + name)    
    return module.RTSPCamera

gc.threshold(4096)
gc.enable()
gc.collect()

# Main
# Try opt level
micropython.opt_level(3)

PORT = const(554) # Default RTSP port
# Internet
sock = None

nic = SetUpWiznetChip()


RTSPCamera = load_driver(DRIVER)
cam = RTSPCamera(
    scl = Pin('PB6', Pin.IN),
    sda = Pin('PB7', Pin.IN),
    max_size = 16000
)
mic = Microphone()


print(f"\nPlease connect to {nic.ifconfig()[0]}:{PORT} for the camera")



cam.reset()
# cam.init_sequence()

# JPEG init
cam.write_table(OV2640_JPEG_INIT)
cam.write_table(OV2640_JPEG)

# Resolution Init
# cam.write_table(OV2640_CIF_176X144)
# cam.write_table(OV2640_CIF_320X240)
# cam.write_table(OV2640_SVGA_800X600)
# cam.write_table(OV2640_VGA_640X480)
# cam.write_table(OV2640_UXGA_1024X768)
cam.write_table(OV2640_UXGA_1280X960)

# Apply common sensor/DVP timing after the selected resolution.
cam.write_table(OV2640_SYS_INIT)

# Extra settings
# Table 00
cam.write_reg(0xff, 0x00)
# cam.write_reg(0xD3, 0x16) # Stable is 0x20 (0x16 for 216 Mhz)

# Table 01
cam.write_reg(0xff,0x01)
# cam.write_reg(0x2B, 0xFF)
# cam.write_reg(0x11,0x80) # Stable is 0x08 with D3 is 0x10
# cam.write_reg(0x46, 0xFF) # FLL timing. Usually is 0x40

# Main
# UDP Command server
server = CommandServer(nic.ifconfig()[0], cam)

# RTSP Server
rtsp = RTSPServer(nic.ifconfig()[0])
while True:
    try:
        # Handle RTSP
        if not rtsp.playing:
            rtsp.run()
            time.sleep_ms(20)
        else:
            cam.stream_rtp(mic, rtsp, server) 
    except OSError as e:
        print(e)
        if server is not None:
            server.disconnect()
        if e.errno not in [7, 128]:
            raise e
        continue
    except Exception as e:
        print(gc.mem_free())
        raise e
    finally:
        print(gc.mem_free())
#     finally:
#         print("advanced:",cam.advanced)
#         if len(cam.benchmark) > 0:
#             print(cam.benchmark)
#             print("Avg = ", sum(cam.benchmark) // len(cam.benchmark))
#         year, month, day, hour, minute, second, _, _ = time.localtime()
#         print(f"Stopped at time: {hour:02d}:{minute:02d}:{second:02d}")
#         print(f"Dropped frames = {cam.dropped_frames}")
#         if conn is not None:
#             try:
#                 conn.close()
#                 conn = None
#             except:
#                 pass
#             print("\nConnection ended. Reconnect again.")
#         if server is not None:
#             server.disconnect()
    



