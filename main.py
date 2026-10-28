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

_HTTP_MODE = const(0)
_RTSP_MODE = const(1)

try:
    from config import DRIVER
except ImportError:
    DRIVER = "ov2640"
try:
    from config import CAM_TYPE
except ImportError:
    CAM_TYPE = _HTTP_MODE

def load_driver(name, mode):
    # RTSPCamera subclasses Camera and adds stream_rtp(); the HTTP path does not need its packet buffer.
    module = __import__("_" + name)
    return module.RTSPCamera if mode == _RTSP_MODE else module.Camera


gc.threshold(4096)
gc.enable()
gc.collect()

# Main
# Try opt level
micropython.opt_level(3)

PORT = const(80)
# Internet
sock = None

nic = SetUpWiznetChip()
print(nic.getsockbuf())

Camera = load_driver(DRIVER, CAM_TYPE)
cam = Camera(
    scl = Pin('PB6', Pin.IN),
    sda = Pin('PB7', Pin.IN),
    # HTTP writes whole sections over TCP; RTP sends packet by packet and stays much closer to the DMA.
    max_size = 8400 if CAM_TYPE == _RTSP_MODE else 16000
)


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

print('\n')


# Start depends on config
if CAM_TYPE == _HTTP_MODE:
    print(f"Please connect to {nic.ifconfig()[0]}:{PORT} for HTTP Stream")
    server = CommandServer(nic.ifconfig()[0], cam)
    while True:
        try:

            sock = socket.socket()
            sock.bind((nic.ifconfig()[0], PORT))
            sock.listen(0)
            sock.setblocking(True)
            
            conn, addr = sock.accept()
            sock = None

            # conn.setblocking(False)
            conn.settimeout(5000)

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
            print(e)
            if conn is not None:
                try:
                    conn.close()
                    conn = None
                except:
                    pass   
                print("\nConnection ended. Reconnect again.")
            if server is not None:
                server.disconnect()
            if e.errno not in [7, 128]:
                raise e
            continue
        except Exception as e:
            print(e)
            if conn is not None:
                try:
                    conn.close()
                    conn = None
                except:
                    pass
            if server is not None:
                server.disconnect()
            raise e
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
else:
    # RTSP Server. CommandServer first, then RTSPServer, then its two RTP sockets: that order decides which
    # hardware socket each one gets, and so which TX buffer from setsockbuf() it uses.
    mic = Microphone()
    server = CommandServer(nic.ifconfig()[0], cam)
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
            print("free:", gc.mem_free())
            raise e
    
    



