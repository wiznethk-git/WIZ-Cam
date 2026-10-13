import gc
import time
import socket
from setup import SetUpWiznetChip
import machine
import micropython
from machine import SoftI2C, Pin, mem32
from ov2640_regs import *
from server import CommandServer

try:
    from config import DRIVER
except ImportError:
    DRIVER = "ov2640"

def load_driver(name):
    module = __import__("_" + name)    
    return module.Camera

# gc.threshold(50000)
gc.disable()
gc.collect()

# Main
# Try opt level
micropython.opt_level(3)

PORT = const(80)
# Internet
sock = None

nic = SetUpWiznetChip()
# Set four sockets so that can reconnect.
print(nic.getsockbuf())

Camera = load_driver(DRIVER)
cam = Camera(
    scl = Pin('PB6', Pin.IN),
    sda = Pin('PB7', Pin.IN),
    max_size = 28000
)

sock = socket.socket()
sock.bind((nic.ifconfig()[0], PORT))
sock.listen(1)
sock.setblocking(True)
print(f"\nPlease connect to {nic.ifconfig()[0]}:{PORT} for the camera")

# Do here
server = CommandServer(nic.ifconfig()[0], cam)
cam.reset()
# cam.init_sequence()

# JPEG init
cam.write_table(OV2640_JPEG_INIT)
cam.write_table(OV2640_JPEG)

# Resolution Init
# cam.write_table(OV2640_CIF_176X144)
# cam.write_table(OV2640_CIF_320X240)
cam.write_table(OV2640_SVGA_800X600)
# cam.write_table(OV2640_VGA_640X480)
# cam.write_table(OV2640_UXGA_1024X768)
# cam.write_table(OV2640_UXGA_1280X960)

# Apply common sensor/DVP timing after the selected resolution.
cam.write_table(OV2640_SYS_INIT)
while True:
    try:
        conn, addr = sock.accept()
        
        # conn.setblocking(False)
        conn.settimeout(5)



        # Extra settings
        # Table 00
        cam.write_reg(0xff, 0x00)
        # cam.write_reg(0xD3, 0x16) # Stable is 0x20 (0x16 for 216 Mhz)

        # Table 01
        cam.write_reg(0xff,0x01)
        # cam.write_reg(0x2B, 0xFF)
        # cam.write_reg(0x11,0x80) # Stable is 0x08 with D3 is 0x10
        # cam.write_reg(0x46, 0xFF) # FLL timing. Usually is 0x40

        # Measure the sensor's real frame rate before network streaming starts.    
        cam.stream_start(conn)
        # cam.stream_frame(conn)
        gc.collect()
        cam.stream_frame_with_settings(conn, server)

      
        # asyncio.run(asyncio.gather(server.run(),cam.async_stream_frame(conn)))
    except OSError as e:
        if conn is not None:
            try:
                conn.close()
                conn = None
            except:
                pass   
            print("\nConnection ended. Reconnect again.")
        if server is not None:
            server.disconnect()
#         if e.errno not in [7, 128]:
#             raise e
        continue
    except Exception as e:
        if conn is not None:
            try:
                conn.close()
                conn = None
            except:
                pass
        if server is not None:
            server.disconnect()
#         raise e
    finally:
        print("advanced:",cam.advanced)
        if len(cam.benchmark) > 0:
            print(cam.benchmark)
            print("Avg = ", sum(cam.benchmark) // len(cam.benchmark))
        year, month, day, hour, minute, second, _, _ = time.localtime()
        print(f"Stopped at time: {hour:02d}:{minute:02d}:{second:02d}")
        print(f"Dropped frames = {cam.dropped_frames}")
        if conn is not None:
            try:
                conn.close()
                conn = None
            except:
                pass
            print("\nConnection ended. Reconnect again.")
        if server is not None:
            server.disconnect()
    


