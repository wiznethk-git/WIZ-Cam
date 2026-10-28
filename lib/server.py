import gc
import socket
import time
# import asyncio
import json
import camera_setting as settings

_CMD_PORT = 5000
class CommandServer:
    def __init__(self, ip, camera):
        self.ip = ip
        self.port = _CMD_PORT
        self.conn = None
        self.client_ip = None
        self.sock = None
        
        self.camera = camera
        self.func_dict = {
            "brightness": settings.set_brightness,
            "contrast": settings.set_contrast,
            "resolution": settings.set_resolution,
            "vertical_flip": settings.set_vertical_flip,
            "horizontal_flip": settings.set_horizontal_flip,
            "jpeg_quality": settings.set_jpeg_quality,
            "saturation": settings.set_saturation,
            "black_white": settings.set_black_white,
            
            # exposure
            "auto_exposure": settings.set_auto_exposure,
            "AEC_value":settings.set_aec_value,
            "AEC": settings.set_aec,
            "AEC2": settings.set_aec2,
            
            # gain
            "auto_gain": settings.set_agc,
            "agc_ceiling": settings.set_agc_ceiling,
            "agc_value": settings.set_agc_value,
            
            # White balance
            "wb_mode": settings.set_wb_mode,
            "awb_mode": settings.set_awb_mode,
            "awb_mode_gain": settings.set_awb_mode_gain,
            "lens_correction": settings.set_lens_correction,
            "wpc": settings.set_wpc,
            "bpc": settings.set_bpc,
            "special_effect": settings.set_special_effect,
            "color_bar": settings.set_colorbar,
        }
        self._init_socket()
        print(f'For configuration server, please connect to {self.ip}:{self.port}')
        
    def _init_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # sock= socket.socket()
        sock.bind((self.ip, self.port))
        sock.setblocking(False)
        # sock.listen(1)
        self.sock = sock
        
#     @micropython.native()      
#     def _wait_connection(self):
#         if self.sock is None:
#             self._init_socket()
#         try:
#             self.conn, self.client_ip = self.sock.accept()
#             self.conn.setblocking(False)
#             self.log(f"Connection accepted from {self.client_ip}.")
#         except OSError as e:
#             if e.errno in [11, 116]:
#                 return 
#         except Exception as e:
#             raise e

    @micropython.native()      
    def _wait_command(self):
        if self.sock is None:
            self._init_socket()
        try:
            data, addr = self.sock.recvfrom(1024)
        except OSError as e:
            return 
        except Exception as e:
            raise e
           
        self.handle_message(data, addr)
        
            
#     @micropython.native()      
#     def _wait_message(self):
#         try:
#             msg = self.conn.recv(1024)
#         except OSError as e:
#             if not (e.errno in [11, 116]):
#                 if self.conn:
#                     self.conn.close()
#                 self.conn = None
#             return
# 
#         if not msg or msg == b"":
#             # Maybe ended
#             self.disconnect()
#             return
#         self.handle_message(msg)
    
#     @micropython.native()      
#     async def _await_connection(self):
#         if self.sock is None:
#             self._init_socket()
#         while self.conn is None:
#             try:
#                 self.conn, self.client_ip = self.sock.accept()
#             except OSError as e:
#                 if e.errno in [11, 116]:
#                     await asyncio.sleep(1)
#                     continue
#             except Exception as e:
#                 raise e
#     
#     @micropython.native()
#     async def _await_message(self):
#         while True:
#             try:
#                 msg = self.conn.recv(1024)
#             except OSError as e:
#                 if (e.errno in [11, 116]):
#                     await asyncio.sleep(1)
#                     continue
#             if not msg:
#                     break
#             self.handle_message(msg)
#         
#         # Lost connection
#         if self.conn is not None:
#             self.conn.close()
#         if self.sock is not None:
#             self.sock.close()
#         self.sock = None
#         self.conn = None
#     
#     @micropython.native()
#     async def run(self):
#         while True:
#             await self._await_connection()
#             await self._await_message()
#             self.log("Connection Lost. Connect to Command Server again")
#           
    def handle_message(self, msg, addr=None):
        try:
            data = json.loads(msg)
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            self.log("Message expects to be in dictionary format.")
            return
        except Exception as e:
            print(e)
            return
        
        # A desktop client uses this lightweight handshake to discover the
        # camera's live values.  Build the reply only when requested so the
        # board does not keep a second settings dictionary in RAM.
        if data.get("connection") is True:
            if addr is not None:
                self._send_settings(addr)
            return

        for key, value in data.items():
            # name = "set_" + key
            # func = self.camera_call(name)
            func = self.camera_call(key)
            if func is not None:
                if isinstance(value, dict):
                    # func(**value)
                    func(self.camera, **value)
                elif isinstance(value, (list, tuple)):
                    # func(*value)
                    func(self.camera, *value)
                else:
                    # func(value)
                    func(self.camera, value)

        # Return the authoritative state after applying a command.  This is
        # especially important when a resolution table forces another value,
        # such as CIF selecting auto-exposure level +2.
        if addr is not None:
            self._send_settings(addr)

        gc.collect()

    def _send_settings(self, addr):
        camera = self.camera
        settings_data = {
            "resolution": camera.resolution,
            "brightness": camera.brightness,
            "contrast": camera.contrast,
            "vertical_flip": camera.vflip,
            "horizontal_flip": camera.hflip,
            "jpeg_quality": camera.jpeg_quality,
            "saturation": camera.saturation,
            "black_white": camera.bw,
            "auto_exposure": camera.auto_exposure,
            "AEC_value": camera.aec_val,
            "AEC": camera.aec_enable,
            "AEC2": camera.aec2_enable,
            "auto_gain": camera.agc_enable,
            "agc_ceiling": camera.agc_ceiling,
            "agc_value": camera.agc_value,
            "wb_mode": camera.wb_mode,
            "awb_mode": camera.awb_mode,
            "awb_mode_gain": camera.awb_mode_gain,
            "lens_correction": camera.lens_correction,
            "wpc": camera.wpc,
            "bpc": camera.bpc,
            "special_effect": camera.special_effect,
            "color_bar": camera.color_bar,
        }
        wire = json.dumps({"connection": True, "settings": settings_data})
        self.sock.sendto(wire.encode("utf-8"), addr)
        settings_data = None
        wire = None
        gc.collect()
    
    def camera_call(self, name):
        # func = getattr(self.camera, name, None)
        func = self.func_dict.get(name, None)
        if func is None or not callable(func):
            self.log(f"Function name {name} not found.")
            return None
        return func
        
        
#     @micropython.native()
#     def poll(self):
#         if self.conn is None:
#             self._wait_connection()
#             return
#         self._wait_message()

    @micropython.native()
    def poll(self):
        self._wait_command()
      
    def log(self,message):
        print(
            "[CmdServer]" +
            message
        )
        
    def disconnect(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            
            
    
            
    
            
