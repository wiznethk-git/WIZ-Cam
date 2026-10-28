import network
from machine import SPI, Pin
try:
    from config import DHCP
except ImportError:
    DHCP = False

def SetUpWiznetChip(DHCP = DHCP):
    NET_IP   = "192.168.1.13"
    NET_SN   = "255.255.255.0"
    NET_GW   = "192.168.1.1"
    NET_DNS  = "8.8.8.8"
#     NET_IP   = "10.0.1.151"
#     NET_SN   = "255.255.255.0"
#     NET_GW   = "10.0.1.254"
#     NET_DNS  = "8.8.8.8"

    spi = SPI(2, baudrate=36_000_000, polarity=0, phase=0)

    cs  = Pin("PB12", Pin.OUT)
    rst = Pin("PD9", Pin.OUT)
    pwn = Pin("PE15", Pin.OUT, value =0)

    nic = network.WIZNET5K(spi, cs, rst)
    
    # Reset the WIZnet chip
    nic.active(True)
    
    # RTSP
    # Socket 0 is UDP and RTSP Command Server
    # Socket 1 + 2 is Video and Audio
    # Socket 3 is for RTSP
    # Socket 4 - 7 for remainig RTP
    
    # HTTP
    # Socket 0 is UDP
    # Socket 1, 2 is for HTTP Stream (Once close use the other)
    nic.setsockbuf((1,4,4,2,1,1,1,1), "tx")
    
    
    # Please use your PC to Ping "192.168.1.20"
    if DHCP:
        try:
            print('==== Assigning DHCP ====')
            nic.ifconfig("dhcp")
        except Exception as e:
            print('==== Failure in DHCP. Try Static IP instead ====')
            print('IP at ', NET_IP)
            nic.ifconfig((NET_IP, NET_SN, NET_GW, NET_DNS))
    else:
        nic.ifconfig((NET_IP, NET_SN, NET_GW, NET_DNS))
    print('Your IP is : ', nic.ifconfig()[0])
    return nic