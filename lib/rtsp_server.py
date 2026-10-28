import socket
import gc
import time
from machine import Pin

_RTSP_PORT = const(554)
_SESSION = const(171819202122232425)
_VIDEO_PORT = const(6100)
_AUDIO_PORT = const(6102)

try:
    from config import DEBUG
except ImportError:
    DEBUG = False


class RTSPServer:
    def __init__(self, ip, port = _RTSP_PORT):
        self.ip = ip
        self.port = port
        self.conn = None
        self.conn_ip = None
        self.session = str(_SESSION).encode()
        self.playing = False
        
        # Video
        self.video_sock = None
        self.video_port = None
        # Audio
        self.audio_sock = None
        self.audio_port = None
    
        
        self.led = Pin('PG3', Pin.OUT)
        self.led.value(0)
        
        self.sdp = (
            b"v=0\r\n"
            b"o=- 0 0 IN IP4 "+ self.ip.encode() + b"\r\n" 
            b"s=W55MH32 camera\r\n"
            b"c=IN IP4 0.0.0.0\r\n"
            b"t=0 0\r\n"
            b"m=video 0 RTP/AVP 26\r\n"
            b"a=rtpmap:26 JPEG/90000\r\n"
            b"a=control:track0\r\n"
#             G.711
#             b"m=audio 0 RTP/AVP 0\r\n"
#             b"a=rtpmap:0 PCMU/8000\r\n"
#             b"a=control:track1\r\n"
#             PCM
            b"m=audio 0 RTP/AVP 96\r\n"
            b"a=rtpmap:96 L16/8000/1\r\n"
            b"a=control:track1\r\n"
        )
        
        # Make Socket 1 + 2 to Video and Audio
        self._init_rtp()
        
        # Remaining for RTSP
        self._init_socket()
    
    def log(self, *args):
        print("[rtsp]", *args)

    def _init_socket(self):
        if self.conn != None:
            return
        ip, port = self.ip, self.port
        sock = socket.socket()
        sock.bind((ip, port))
        sock.listen(1)
        sock.setblocking(True)
        print(f"Please connect to {ip}:{port} for RTSP Server")
        conn, client_ip = sock.accept()
        sock.close()
        conn.setblocking(False)
        self.conn = conn
        self.conn_ip = client_ip
        
    def run(self):
        if self.conn is None:
            self._init_socket()
        conn = self.conn
        # ba, mv = self.recv_bytes, self.mv
        try:
            req = conn.recv(1024)
            if req == b"" or None:
                return
        except OSError as e:
            if e.errno in [11, 116]:
                return
            else:
                if conn:
                    conn.close()
                self.conn = None
                return
        except Exception as e:
            if conn:
                conn.close()
            self.conn = None
            return
        self.handle_request(req)
    
    def _header(self, lines, name):
        # RTSP headers can come in any order, so look one up by name instead of by line number.
        # name must be lower case and end with a colon, e.g. b"transport:".
        n = len(name)
        for line in lines:
            if line[:n].lower() == name:
                return line[n:].strip()
        return None

    def _field(self, header, name):
        # One ";"-separated field of a header, found by prefix rather than position: a client may send
        # client_port in the middle, e.g. RTP/AVP;unicast;client_port=5000-5001;mode="PLAY".
        if header is None:
            return None
        n = len(name)
        for part in header.split(b";"):
            part = part.strip()
            if part[:n].lower() == name:
                return part[n:]
        return None

    def handle_request(self, req):
        conn = self.conn
        sdp = self.sdp
        lines = req.strip(b'\r\n\r\n').split(b'\r\n')
        if DEBUG:
            self.log(lines)
        action = lines[0].split(b' ')[0]
        cseq = self._header(lines, b"cseq:")
        if cseq is None:
            cseq = b"0"
        
        try:
            # Actions
            if action == b"OPTIONS":
                conn.write(b"RTSP/1.0 200 OK\r\nCSeq: %s\r\nPublic: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\n\r\n" % cseq)
            elif action == b"DESCRIBE":
                reply = (
                 b"RTSP/1.0 200 OK\r\nCSeq:  %s\r\n" % cseq +
                 b"Content-Type: application/sdp\r\n" +
                 b"Content-Length: " + str(len(sdp)).encode() + b"\r\n\r\n" + sdp)
                conn.write(reply)
            elif action == b"SETUP":
                transport = self._header(lines, b"transport:")
                track = lines[0].split(b" ")[-2].rstrip(b"/").split(b"/")[-1]
                low = transport.lower() if transport else b""

                # We only do RTP over UDP. A client asking for interleaved TCP (RTP/AVP/TCP;interleaved=0-1)
                # sends no client_port at all, because the media would come back down this RTSP connection.
                # 461 makes it retry the same SETUP over UDP; a 200 OK would leave it waiting forever.
                cp = self._field(transport, b"client_port=")
                if b"/tcp" in low or b"interleaved" in low or cp is None:
                    self.log("rejecting transport:", transport)
                    conn.write(
                        b"RTSP/1.0 461 Unsupported Transport\r\n" +
                        b"CSeq: %s\r\n" % cseq +
                        b"\r\n")
                    return
                port = int(cp.split(b"-")[0])

                if track == b"track0":
                    self.video_port = port
                    server_port = _VIDEO_PORT
                elif track == b"track1":
                    self.audio_port = port
                    server_port = _AUDIO_PORT
                else:
                    self.log("unknown SETUP track:", track)
                    conn.write(
                        b"RTSP/1.0 454 Session Not Found\r\n" +
                        b"CSeq: %s\r\n" % cseq +
                        b"\r\n")
                    return
                conn.write(
                    b"RTSP/1.0 200 OK\r\n" +
                    b"CSeq: %s\r\n" % cseq +
                    b"Session: %s;timeout=60\r\n" % self.session +
                    b"Transport: RTP/AVP;unicast;client_port=%s;server_port=%d-%d\r\n" % (cp, server_port, server_port + 1) +
                    b"\r\n")
            elif action == b"PLAY":
                conn.write(
                    b"RTSP/1.0 200 OK\r\n" +
                    b"CSeq: %s" % cseq + b"\r\n" +
                    b"Session: %s\r\n" % self.session +
                    b"Range: npt=0.000-\r\n" +
                    b"\r\n")
                self.playing = True
            elif action == b"TEARDOWN":
                conn.write(
                    b"RTSP/1.0 200 OK\r\n" +
                    b"CSeq: %s\r\n" % cseq +
                    b"\r\n"
                )
                self.playing = False
            gc.collect()
        except OSError as e:
            raise e
            if conn:
                conn.close()
            conn = None
        except Exception as e:
            print(e)
            if conn: conn.close()
    
    @micropython.native()
    def send_rtp(self, pkt):
        self.led.value(0)
        self.video_sock.sendto(pkt, (self.conn_ip[0], self.video_port))
        self.led.value(1)   
    
    @micropython.native()
    def send_audio_rtp(self, pkt):
        self.led.value(0)
        self.audio_sock.sendto(pkt, (self.conn_ip[0], self.audio_port))
        self.led.value(1)
    
    def _init_rtp(self):
        sock0 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock0.bind((self.ip, _VIDEO_PORT))
        sock0.setblocking(False)
        self.video_sock = sock0   
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock1.bind((self.ip, _AUDIO_PORT))
        sock1.setblocking(False)
        self.audio_sock = sock1
        
# if __name__ == "__main__":
#     import time
#     from setup import SetUpWiznetChip
# 
#     nic = SetUpWiznetChip()
#     print(nic.getsockbuf())
#     server = RTSPServer(nic.ifconfig()[0])
#     while True:
#         server.run()
#         time.sleep_ms(500)