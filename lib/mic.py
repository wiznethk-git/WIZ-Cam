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

#
_DMA_BASE = const(0x40020400)
_DMA_IFCR = const(0x40020404)
_DMA_CCR1 = const(0x40020408)
_DMA_CNDTR1 = const(0x4002040C)
_DMA_CMAR1 = const(0x40020414)


# TX uses Channel 2
_DMA_CCR1_TX = const(0x40020408 + 20)
_DMA_CNDTR1_TX = const(0x4002040C + 20)
_DMA_CMAR1_TX = const(0x40020414 + 20)
_DMA_CPAR1_TX = const(0x40020410 +20)

_I2S_CFGR = const(0x40003C1C)
_I2S_CR2 = const(0x40003C04)
_I2S_SR = const(0x40003C08)
_I2S_DR = const(0x40003C0C)
_I2S_PR = const(0x40003C20)
_RCC_APB1RSTR = const(0x40021010)

# Audio direction. The board has one I2S block (SPI3) wired to both the ICS-43434 and the MAX98357A, and an
# I2S block is receive OR transmit, never both, so these are mutually exclusive.
MIC = const(0)                  # capture, streamed to the client
SPEAKER = const(1)              # playback on the device

_RATE = const(8000)

# Can amend
_BUF_SIZE = const(5120 + 640*4)

_PCM_PORT = const(6000)         # audio IN, alongside 6100 video out and 6102 audio out
_PCM_SAMPLES = const(160)       # per packet, 20 ms at 8 kHz
_PCM_PKT = const(2 + 320)       # 2-byte sequence number + 160 big-endian 16-bit samples
_SLOT = const(_PCM_SAMPLES * 8) # buffer bytes one packet expands to: 160 frames x 8
_SLOTS = const(_BUF_SIZE // _SLOT)
_PCM_AHEAD = const(_SLOTS - 1)  # never write further ahead than this many slots

_START_TONE = False             # True = start speaker mode on the 500 Hz tone instead of silence, for testing

# One 500 Hz period at 8 kHz: 16 frames. _BUF_SIZE / 8 = 640 frames = exactly 40 periods, so a circular DMA
# loops the buffer with no click at the wrap.
_TONE = (0, 2296, 4243, 5543, 6000, 5543, 4243, 2296, 0, -2296, -4243, -5543, -6000, -5543, -4243, -2296)

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
            rate = _RATE,
            ibuf = 1
        )
        self.mode = MIC
        
        self.buf = bytearray(_BUF_SIZE)
        self.num_read = 0
        self.buf_addr = addressof(self.buf)
        self.pkt = bytearray(12 + 320) # RTP Header + 160 samples * 2 bytes (L16)
        self.pkt_mv = memoryview(self.pkt)
        self.pkt_addr = addressof(self.pkt)
        self.ssrc = _SSRC           # the RTCP sender report has to carry this stream's own SSRC
        self.a_seq = 0
        self.ts = 0
        self.r_idx = 0
        self.t_silence = 0          # when the next silence packet is due, see _send_silence()
        self.w_idx = 0              # where playback writes next, the mirror of r_idx
        self.pcm_sock = None        # audio-in socket, only open while playing
        self.pcm_in = bytearray(_PCM_PKT)   # one received packet, so _expand() can take ptr8 of an attribute
        self.pcm_in_mv = memoryview(self.pcm_in)
        self.pcm_seq = -1           # next sequence number expected; -1 = not started
        self.pcm_got = 0
        self.pcm_lost = 0           # packets never arrived, filled with silence
        self.pcm_late = 0           # arrived after the DMA had passed their slot, discarded
        self.pcm_over = 0           # arrived faster than real time, discarded to protect unplayed audio
        self.t_pcm = 0
        self.t_rx = 0               # when the mid-frame socket drain last ran, see _service_audio()
        self.w_idx = 0

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

        # _package_rtp() rewrites these every time, but a silence packet sent before the first captured one
        # would otherwise carry zeros and look to the client like a different stream.
        self.pkt[8] = (_SSRC >> 24) & 0xFF
        self.pkt[9] = (_SSRC >> 16) & 0xFF
        self.pkt[10] = (_SSRC >> 8) & 0xFF
        self.pkt[11] = _SSRC & 0xFF


        # Defaults to Mic DMA
        self._init_rx_dma()
        
      
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
    
    @micropython.viper()
    def _zero(self, off: int, n: int):
        # Zero n bytes of the buffer at off, a word at a time. Slots are 1280 bytes and aligned, so off and n
        # are always multiples of 4.
        p = ptr32(self.buf)
        i = off >> 2
        end = (off + n) >> 2
        while i < end:
            p[i] = 0
            i += 1

    @micropython.viper()
    def _expand(self, off: int):
        # One packet of L16 into one buffer slot: 160 samples, 2 bytes each, becoming 160 frames of 8.
        # This is _package_rtp run backwards. L16 is big endian on the wire and memory is little endian, so the
        # two bytes swap; the sample goes in the MS half of each 32-bit slot (bytes 0-1 and 4-5) because that
        # is the halfword the DMA sends first, and in both slots because this amp plays (left+right)/2.
        # ptr8 is taken of an attribute here, never passed in as an argument: a viper pointer parameter
        # converted from a Python object is what the HardFault pointed at, and _package_rtp does it this way.
        # Bytes 2-3 and 6-7 - the LS halves of the two 32-bit I2S slots - are NOT written here. They are zero
        # for every 16-bit sample, forever, and to_speaker() zeroes the whole ring before arming the TX DMA;
        # nothing else writes the ring except _zero(), which also writes zeros. So they are set once instead
        # of 32000 times a second, which halves the stores in this loop. Keep that _zero(0, _BUF_SIZE) in
        # to_speaker(): without it the pads hold leftover microphone samples, which the I2S would clock out
        # as the low bits of every word - quiet, but there.
        # off MUST be a multiple of _SLOT: ptr8 does no bounds checking, so an unaligned off writes past the
        # end of self.buf and corrupts whatever the GC put next to it - which showed up as the instance
        # randomly losing attributes. Every writer of w_idx therefore rounds down to a slot boundary.
        buf = ptr8(self.buf)
        pay = ptr8(self.pcm_in)
        i = 2                                       # skip the sequence number
        o = off
        k = 0
        while k < _PCM_SAMPLES:
            hi = int(pay[i])
            lo = int(pay[i + 1])
            buf[o] = lo
            buf[o + 1] = hi
            buf[o + 4] = lo
            buf[o + 5] = hi
            i += 2
            o += 8
            k += 1

    @micropython.viper()
    def _tx_pos(self) -> int:
        # Where the playback DMA is reading, in bytes. The mirror of avail()'s write position.
        b = int(_BUF_SIZE)
        cndtr = ptr32(_DMA_CNDTR1_TX)
        return (b // 2 - cndtr[0]) * 2

#     @micropython.viper()
#     def handle_gap(self, pay:ptr8) -> int:
#         seq = (pay[0] << 8) | pay[1]
#         self.pcm_seq = seq if int(self.pcm_seq) < 0 else self.pcm_seq
        
    @micropython.native()
    def _recv_pcm(self, limit = 6):
        # Take PCM from the network and write it into the buffer ahead of the playback DMA.
        #
        # UDP can lose and reorder, so position comes from the sequence number, not arrival order. For
        # playback a late packet is as useless as a lost one: the DMA has already swept past the place it
        # belonged, which is also why retransmission would not help and TCP is the wrong tool here.
        sock = self.pcm_sock
        if sock is None:
            return
        n = 0
        while n < limit:
            try:
                pay, _ = sock.recvfrom(_PCM_PKT)
            except OSError:
                break                               # nothing waiting
            n += 1
            if len(pay) != _PCM_PKT:
                continue
            seq = (pay[0] << 8) | pay[1]

            if self.pcm_seq < 0:                    # first packet decides where the stream starts
                self.pcm_seq = seq
            gap = (seq - self.pcm_seq) & 0xFFFF
            
            # Usually zero because we are in ethernet => No reordering or lost
            if gap > 32767:                         # negative: it belongs in the past
                self.pcm_late += 1
                continue
            if gap >= _SLOTS:                       # too big a hole to paper over, so start afresh here
                self.pcm_lost += gap
                gap = 0

            # Do not run further ahead than the buffer: that would overwrite audio the DMA has not played yet.
            if ((self.w_idx - self._tx_pos()) % _BUF_SIZE) >= _PCM_AHEAD * _SLOT:
                # Slip: discard this packet AND its place in the timeline. Leaving pcm_seq where it was would
                # make the next packet arrive with gap = 1, and the fill loop would then write a silence slot
                # plus the audio - advancing w_idx by two slots while the DMA consumed one, putting the cushion
                # straight back over the guard. That oscillation dropped ~38% of all packets (over ~= lost in
                # the 3 s report) for a clock mismatch that only justifies discarding one packet every 1.7 s.
                self.pcm_over += 1
                self.pcm_seq = (seq + 1) & 0xFFFF
                continue

            w = self.w_idx
            while gap:                              # the missing packets play as silence, not as stale audio
                self._zero(w, _SLOT)
                w = (w + _SLOT) % _BUF_SIZE
                self.pcm_lost += 1
                gap -= 1
            # Copy from buffer
            self.pcm_in_mv[:] = pay   
            
            # Write audio from PCM packets to Buffer for I2S
            self._expand(w)
            
            w = (w + _SLOT) % _BUF_SIZE
            self._zero(w, _SLOT)                    # keep one slot of silence ahead, so an underrun is quiet
            self.w_idx = w
            self.pcm_seq = (seq + 1) & 0xFFFF
            self.pcm_got += 1
    
    @micropython.viper()
    def _make_pcm(self):
        # Fill the whole buffer with a 500 Hz tone, in the layout the I2S actually wants: the 16-bit sample in
        # bytes 0-1 (the MS half of the left slot) and 4-5 (the right slot), both LS halves left at zero. The
        # amp on this board plays (left+right)/2, hence both slots.
        #
        # Note this is the OPPOSITE layout from feeding i2s.write(), which takes normal little-endian 32-bit
        # samples and swaps the halves itself (reformat_32_bit_samples in machine_i2s.c). Driving the DMA
        # directly, nothing does that for us: the halfword stored first is the one sent first, and the I2S
        # wants the MS half first. It is the same layout the capture DMA produces, which is what lets one
        # buffer serve both directions.
        buf = self.buf
        i = 0
        k = 0
        while i < _BUF_SIZE:
            v = int(_TONE[k]) & 0xFFFF
            lo = v & 0xFF
            hi = (v >> 8) & 0xFF
            buf[i] = lo
            buf[i + 1] = hi
            buf[i + 2] = 0
            buf[i + 3] = 0
            buf[i + 4] = lo
            buf[i + 5] = hi
            buf[i + 6] = 0
            buf[i + 7] = 0
            i += 8
            k = (k + 1) & 15

    @micropython.native()
    def _send_silence(self, rtsp, packets):
        # Playing on the speaker. There is nothing to capture, but a client that syncs to the audio clock (VLC,
        # ffplay without -an) freezes the VIDEO too when audio simply stops arriving - that was the stall. So
        # keep sending 20 ms packets of silence so its clock goes on running.
        #
        # No extra RAM: to_speaker() zeroed the payload and _package_rtp() is never called in this mode, so only
        # the 12 byte header changes.
        if not rtsp.audio_port:
            return
        pkt = self.pkt
        mv = self.pkt_mv
        due = self.t_silence
        now = time.ticks_ms()

        # Send every packet that is DUE, not just one. The video loop calls us at its own rhythm - roughly 14
        # times a second at the frame boundary, plus whenever it happens to be idle - so one per call would
        # advance the audio clock at 2240 samples/s instead of 8000 and the client would stall anyway.
        # Honour the caller's limit, like the capture path does. The frame loop asks for 1 while it is inside
        # a frame and 2 at the frame boundary, precisely to bound how long one call can take - a 332-byte
        # sendto costs about as much as a video one (~610 us, the fixed cost dominates), so ignoring that and
        # sending 4 or 8 meant a multi-millisecond stall mid-frame, which the ring cannot absorb.
        n = 0
        while time.ticks_diff(now, due) >= 0 and n < packets:
            seq = self.a_seq
            ts = self.ts
            pkt[2] = (seq >> 8) & 0xFF
            pkt[3] = seq & 0xFF
            pkt[4] = (ts >> 24) & 0xFF
            pkt[5] = (ts >> 16) & 0xFF
            pkt[6] = (ts >> 8) & 0xFF
            pkt[7] = ts & 0xFF
            rtsp.send_audio_rtp(mv)
            self.a_seq = (seq + 1) & 0xFFFF
            self.ts = (ts + 160) & 0xFFFFFFFF
            self.sent += 1
            due = time.ticks_add(due, 20)           # exactly 20 ms on, so the clock does not drift slow
            n += 1

        # Do not try to make up a long gap (a slow frame, or n hit the cap): skip ahead instead.
        self.t_silence = now if time.ticks_diff(now, due) > 200 else due

    @micropython.native()
    def _service_audio(self, rtsp, packets = 1, rx = False):
        if self.mode != MIC:
            self._send_silence(rtsp, packets)       # capture is stopped, but the RTP clock must keep ticking
            # Draining the socket costs ~580 us per packet, which mid-frame is capture ring that nothing is
            # emptying - an unbounded drain here tore the JPEG half to three quarters down. So the boundary
            # caller (rx) does the full catch-up in the vertical blanking, where the camera sends nothing,
            # and mid-frame we take at most 2 packets and no more often than every 20 ms.
            #
            # The mid-frame drain is not redundant with the boundary one. Draining only once per frame makes
            # the arrival burst as large as a frame period (~2 packets at 26 fps), and queued then sawtooths
            # by that much - which is what pushed the peaks into the _PCM_AHEAD guard. It also ties playback
            # to the frame rate, so UXGA (~12 fps, 83 ms) starved between feeds. A 20 ms gate fixes both:
            # smaller bursts, and a feed rate that does not depend on how long a frame takes.
            if rx:
                self._recv_pcm()
            elif time.ticks_diff(time.ticks_ms(), self.t_rx) >= 20:
                self.t_rx = time.ticks_ms()
                self._recv_pcm(2)
            return
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


    def report(self):
        # The 3 s DEBUG summary for whichever direction is running. Call this from the frame boundary ONLY:
        # one print over USB costs several milliseconds, which is long enough for the camera DMA to lap the
        # capture ring. Measured as a 4.8 ms loop stall when it still lived inside _service_audio.
        if not DEBUG:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.t_log) < 3000:
            return
        self.t_log = now
        if self.mode == MIC:
            self.log("pkts/s", self.sent - self.last_sent, "avail", self.avail(), "drop", self.a_drop,
                     "half/s", self.half)
            self.last_sent = self.sent
            self.half = 0
        else:
            self.log("pcm got", self.pcm_got, "lost", self.pcm_lost, "late", self.pcm_late,
                     "over", self.pcm_over, "queued", (self.w_idx - self._tx_pos()) % _BUF_SIZE)

    def to_speaker(self):
        # Turn the single I2S block around to playback. Returns False if it was already there.
        if self.mode == SPEAKER:
            return False
        # The audio-in socket is opened FIRST, before any hardware is touched. Everything below leaves the
        # microphone dead if it only half completes, so anything that can fail has to fail while the capture
        # is still running and we can simply return.
        #
        # It is not opened in __init__ because that would take hardware socket 0 and shift every other socket
        # down one, changing which TX buffer the video socket gets from setsockbuf().
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", _PCM_PORT))       # the wrapper's bind only uses the port
            sock.setblocking(False)
        except OSError as e:
            self.log("cannot open the audio-in socket on port", _PCM_PORT, "-", e)
            return False
        self.pcm_sock = sock
        self.pcm_seq = -1
        self.pcm_got = 0
        self.pcm_lost = 0
        self.pcm_late = 0
        self.pcm_over = 0
        self.t_pcm = time.ticks_ms()

        # Order matters: stop the DMA request first so none is left pending, then the channel, then the clock.
        mem32[_I2S_CR2] &= ~1                       # RXDMAEN off
        mem32[_DMA_CCR1] &= ~1                      # capture DMA off
        mem32[_I2S_CFGR] &= ~(1 << 10)              # I2SE off
        self.i2s.deinit()
        # bits=32 is not a choice: the I2S clock is SYSCLK and the rate divider only reaches 511, so 16-bit data
        # at 8 kHz would need 843 and HAL_I2S_Init fails. 32-bit needs 422 - the same divider the microphone
        # uses, so I2SPR never changes across a switch.
        self.i2s = I2S(
            3,
            sck = Pin('PB3'),
            ws = Pin('PA15'),
            sd = Pin('PB5'),
            mode = I2S.TX,
            bits = 32,
            format = I2S.STEREO,
            rate = _RATE,
            ibuf = 1
        )

        self._zero(0, _BUF_SIZE)                # silence until the network fills it
        self._init_tx_dma()
        self.mode = SPEAKER

        # Zero the payload once: every silence packet reuses it, so only the header changes afterwards.
        for i in range(12, len(self.pkt)):
            self.pkt[i] = 0
            
        self.t_silence = time.ticks_ms()
        self.t_rx = time.ticks_ms()                 # so the first mid-frame drain waits a full gate period
        # Start writing two slots ahead of the DMA. That gap is the jitter buffer.
        # Used to allow data to have some 
        self.w_idx = ((self._tx_pos() + _SLOT // 2) // _SLOT + 3) * _SLOT % _BUF_SIZE
        return True

    def to_mic(self):
        # Back to capture. Returns False if it was already there.
        if self.mode == MIC:
            return False
        self.i2s.deinit()
        self.i2s = I2S(
            3,
            sck = Pin('PB3'),
            sd = Pin('PB5'),
            ws = Pin('PA15'),
            bits = 16,
            format = I2S.MONO,
            mode = I2S.RX,
            rate = _RATE,
            ibuf = 1
        )
        self._init_rx_dma()                            # resets SPI3 and re-arms DMA2 channel 1
        if self.pcm_sock is not None:               # release the hardware socket while not playing
            self.pcm_sock.close()
            self.pcm_sock = None
        ts = self.ts                                # start() resets it, which would jump the client's clock
        self.start()                                # drop stale audio, reset the counters
        self.ts = ts                                # the silence packets already carried it forward
        self.mode = MIC
        return True

    def _init_rx_dma(self):
        # Disable I2S Clock
        mem32[_I2S_CFGR] &= ~(1 << 10)

        # Stop I2S asking for DMA (RXDMAEN), so no stale request stays pending
        mem32[_I2S_CR2] &= ~1

        # Disable DMA
        mem32[_DMA_CCR1] &= ~1
        mem32[_DMA_CCR1_TX] &= ~1 

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
        
    
    def _init_tx_dma(self):
        # Disable I2S Clock
        mem32[_I2S_CFGR] &= ~(1 << 10)

        # Stop I2S asking for DMA (RXDMAEN), so no stale request stays pending
        mem32[_I2S_CR2] &= ~(1 << 1)

        # Disable DMA
        mem32[_DMA_CCR1] &= ~1                  # leaving capture: stop the mic's channel
        mem32[_DMA_CCR1_TX] &= ~1               # and CCR cannot be written while this one is enabled,
                                                # which it is: HAL_I2S_Transmit_DMA just started it

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
        mem32[_DMA_CCR1_TX] = 0b10010110110000

        # Clear all interrup flags
        mem32[_DMA_IFCR] |= (0xf << 4)

        # Peripheral end: the I2S data register, fixed (PINC is 0). MicroPython's own TX setup already
        # put this here, but do not depend on that.
        mem32[_DMA_CPAR1_TX] = _I2S_DR

        # Set Buf address
        mem32[_DMA_CMAR1_TX] = self.buf_addr

        # Set number of DMA transfer
        mem32[_DMA_CNDTR1_TX] = _BUF_SIZE // 2

        # Enable DMA again
        mem32[_DMA_CCR1_TX] |= 1

        # Let I2S ask for DMA again
        mem32[_I2S_CR2] |= (1 << 1)             # TXDMAEN, not RXDMAEN

        # Enable I2S Clock
        mem32[_I2S_CFGR] |= (1 << 10)
    
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


