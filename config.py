# Camera
DRIVER = "ov2640"
MODE   = "svga"

DEBUG = False

# Network
DHCP     = False
NET_IP   = "192.168.1.13"
NET_SN   = "255.255.255.0"
NET_GW   = "192.168.1.0"
NET_DNS  = "8.8.8.8"
CAM_PORT = 80
SERVER_PORT = 5000

# Return
START_ON_REPL = True

# Transport: 0 = HTTP MJPEG stream, 1 = RTSP/RTP (video on 6100, audio on 6102)
CAM_TYPE = 0
