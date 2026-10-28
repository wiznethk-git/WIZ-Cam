import gc
import socket
import random
import time
from uctypes import addressof
from machine import Pin, I2S, mem32
try:
    from config import DEBUG
except ImportError:
    DEBUG = False

_SSRC = random.getrandbits(32)
_DMA_BASE = const(0x40020400)
_DMA_IFCR = const(0x40020404)
_DMA_CCR1 = const(0x40020408)
_DMA_CNDTR1 = const(0x4002040C)
_DMA_CMAR1 = const(0x40020414)
_I2S_CFGR = const(0x40003C1C)
_I2S_CR2 = const(0x40003C04)
_I2S_SR = const(0x40003C08)
_I2S_DR = const(0x40003C0C)
_I2S_PR = const(0x40003C20)
_RCC_APB1RSTR = const(0x40021010)

# Can amend
_BUF_SIZE = const(5120)

class Microphone:
    def __init__(self):
        self.i2s = I2S(
            3,
            sck = Pin('PB3'),
            sd = Pin('PB5'),
            ws = Pin('PA15'),
            bits = 16,
            format = I2S.MONO,
            mode = I2S.RX,
            rate = 8000,
            ibuf = 1
        )
        
        self.buf = bytearray(_BUF_SIZE)
        self.num_read = 0
        self.buf_addr = addressof(self.buf)
        self.pkt = bytearray(12 + 320) # RTP Header + 160 samples * 2 bytes (L16)
        self.pkt_mv = memoryview(self.pkt)
        self.pkt_addr = addressof(self.pkt)
        self.a_seq = 0
        self.ts = 0
        self.r_idx = 0

        # Gain as a right shift of the 24 bit sample: 8 = x1, 5 = x8, 4 = x16
        self.shift = 8

        # Debug counters
        self.sent = 0
        self.last_sent = 0
        self.a_drop = 0
        self.t_log = 0
        self.half = 0           # halfwords the DMA captured since the last print (32000/s when healthy)
        self.last_cndtr = 0

        # Marker based on Audio type
        self.hdr = 0x60
        
        # Always the same
        self.pkt[0] = 0x80
        self.pkt[1] = self.hdr


        
        self._init_dma()

        
    def _send_rtp(self):
        ...
      
    @micropython.viper()
    def _package_rtp(self): 
        buf = ptr8(self.buf)
        pkt = ptr8(self.pkt)
        seq = int(self.a_seq)
        ts = int(self.ts)
        ssrc = int(_SSRC)
        
        #  Sequence number, 16 bit, pack into two bytes
        pkt[2] = (seq >> 8) & 0xFF
        pkt[3] = seq & 0xFF
        
        # Time, 32 bit. Pack them into 4 bytes
        pkt[4] = (ts >> 24) & 0xFF
        pkt[5] = (ts >> 16) & 0xFF
        pkt[6] = (ts >> 8) & 0xFF
        pkt[7] = ts & 0xFF
        
        # SSRC, maybe use random but force static number first
        pkt[8] = (ssrc >> 24) & 0xFF
        pkt[9] = (ssrc >> 16) & 0xFF
        pkt[10] = (ssrc >> 8) & 0xFF
        pkt[11] = ssrc & 0xFF
        
        # Do data: 160 samples. Each frame in the ring is 8 bytes:
        #   [0-1] sample bits 23..8 (little endian), [2] padding, [3] sample bits 7..0, [4-7] right slot (unused)
        rd = int(self.r_idx)
        shift = int(self.shift)
        i = 0
        o = 12
        while i < 160:
            # L16 is big endian: high byte first
            # print(int(buf[rd + 1]))
            # print(int(buf[rd]))
            pkt[o] = int(buf[rd + 1])
            pkt[o + 1] = int(buf[rd])
            o += 2
            rd += 8
            if rd >= _BUF_SIZE:
                rd = 0
            i += 1

        # Next packet starts where this one ended
        self.r_idx = rd
        self.a_seq = (seq + 1) & 0xFFFF
        self.ts = (ts + 160) & int(0xFFFFFFFF)
        
    def log(self, *args):
        print("[I2S]", *args)
    
    @micropython.native()
    def avail(self):
        # DMA write position in bytes. CNDTR counts halfwords, so x2.
        wr = (_BUF_SIZE // 2 - mem32[_DMA_CNDTR1]) * 2
        # Bytes written since our read index. % handles the wrap at the end of the ring.
        return (wr - self.r_idx) % _BUF_SIZE

    def _find_phase(self):
        # The DMA can start one halfword off the I2S frame, so index 0 of the ring
        # is not always the start of a frame. In a correct frame, byte 2 (padding) and
        # bytes 4-7 (unused right slot) are always 0. Try the 4 halfword offsets and
        # return the one where those bytes are zero in the most of the 32 frames checked.
        buf = self.buf
        best = 0
        best_score = -1
        for p in (0, 2, 4, 6):
            score = 0
            for k in range(32):
                f = p + k * 8
                if buf[f + 2] == 0 and buf[f + 4] == 0 and buf[f + 5] == 0 and buf[f + 6] == 0 and buf[f + 7] == 0:
                    score += 1
            if score > best_score:
                best = p
                best_score = score
        return best
    
    @micropython.native()
    def _service_audio(self, rtsp, packets = 1):
#         if not rtsp.audio_port:
#             return
        # Debug: count the halfwords the DMA really captured since the last call
        c = mem32[_DMA_CNDTR1]
        self.half += (self.last_cndtr - c) % (_BUF_SIZE // 2)
        self.last_cndtr = c

        n = 0
        while n < packets:
            avail = self.avail()

            # The ring is circular. If the DMA is about to lap us, the oldest audio is lost anyway,
            # so drop it on purpose and keep the newest 2 packets.
            if avail > _BUF_SIZE - 1280:
                skip = (avail - 2 * 1280) & ~7          # multiple of 8, so r_idx stays on a frame start
                self.r_idx = (self.r_idx + skip) % _BUF_SIZE
                self.ts = (self.ts + skip // 8) & 0xFFFFFFFF   # show the gap in the timeline (8 bytes per sample)
                self.a_drop += skip // 8
                avail = avail - skip
                # No print here: _service_audio runs inside the video frame loop and one print over USB costs
                # milliseconds, which is long enough for the camera DMA to overrun the ring. a_drop is reported
                # by the 3 s summary instead.

            # Need a full packet: 160 samples * 8 bytes per frame
            if avail < 1280:
                break
            # print(self.buf[:48])
            self._package_rtp()

            # Only send if the client set up the audio track (SETUP track1)
            if rtsp.audio_port:
                rtsp.send_audio_rtp(self.pkt_mv)
            self.sent += 1
            n += 1

        # Every 3 s (DEBUG only): packets built, bytes waiting, samples dropped
        if DEBUG:
            now = time.ticks_ms()
            if time.ticks_diff(now, self.t_log) >= 3000:
                self.log("pkts/s", self.sent - self.last_sent, "avail", self.avail(), "drop", self.a_drop, "half/s", self.half)
                self.last_sent = self.sent
                self.half = 0
                self.t_log = now
        
    def _init_dma(self):
        # Disable I2S Clock
        mem32[_I2S_CFGR] &= ~(1 << 10)

        # Stop I2S asking for DMA (RXDMAEN), so no stale request stays pending
        mem32[_I2S_CR2] &= ~1

        # Disable DMA
        mem32[_DMA_CCR1] &= ~1

        # Reset SPI3 so the I2S starts from its reset state, like the firmware's first start.
        # Pins (GPIO) are not touched. Save the I2S clock divider and mode, reset, then restore them.
        i2spr = mem32[_I2S_PR]
        i2scfgr = mem32[_I2S_CFGR]
        mem32[_RCC_APB1RSTR] |= (1 << 15)
        mem32[_RCC_APB1RSTR] &= ~(1 << 15)
        mem32[_I2S_PR] = i2spr
        mem32[_I2S_CFGR] = i2scfgr

        # Clear stale RXNE / overrun left by a previous run: read DR, then SR
        _ = mem32[_I2S_DR]
        _ = mem32[_I2S_SR]

        # DMA reconfigure all settings
        mem32[_DMA_CCR1] = 0b10010110100000

        # Clear all interrup flags
        mem32[_DMA_IFCR] |= 0xf

        # Set Buf address
        mem32[_DMA_CMAR1] = self.buf_addr

        # Set number of DMA transfer
        mem32[_DMA_CNDTR1] = _BUF_SIZE // 2

        # Enable DMA again
        mem32[_DMA_CCR1] |= 1

        # Let I2S ask for DMA again
        mem32[_I2S_CR2] |= 1

        # Enable I2S Clock
        mem32[_I2S_CFGR] |= (1 << 10)
        
#         i = 0
#         while i < 30:
#             print(self.buf[:24])
#             i += 1
#         raise
    
    def start(self):
        # used to match start up time of video play.
        self.ts = (time.ticks_ms() * 8) & 0xFFFFFFFF

        # Drop old audio: start reading from where the DMA is now.
        # Round down to a multiple of 8 so we start on a frame boundary.
        wr = (_BUF_SIZE // 2 - mem32[_DMA_CNDTR1]) * 2
        self.r_idx = wr & ~7

        # Reset the debug counters
        self.sent = 0
        self.last_sent = 0
        self.a_drop = 0
        self.half = 0
        self.last_cndtr = mem32[_DMA_CNDTR1]
        self.t_log = time.ticks_ms()


