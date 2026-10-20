import time
import gc
import micropython
from random import getrandbits
from uctypes import addressof
from machine import SoftI2C, Pin, mem32, Timer
from ov2640_regs import *

# Pins
_SCL, _SDA = Pin('PB6', Pin.IN), Pin('PB7', Pin.IN)
_DATA_ADR = const(0x40010808)
_CLK_ADR = const(0x40011008)

_VSYNC = Pin('PC5', Pin.IN) # Change to C5 later
_HREF = Pin('PA8', Pin.IN) # Timer 1 Ch1
_DCLK = Pin('PA12', Pin.IN)


# Timer all reference to Pin CLK
_TIMER_ID = const(1)
_TIMER_CH = const(2) # For DCLK, Indicates the CHANNEL which will trigger dma
_TIMER_BASE_ADDR = const(0x40012C00)
_GATE_CH = const(1) # For HREF

# Timer Reg
_TIMER_DIER = const(_TIMER_BASE_ADDR + 0x0C)
_TIMER_SMCR = const(_TIMER_BASE_ADDR + 0x08)
_TIMER_SR = const(_TIMER_BASE_ADDR + 0x10)
_TIMER_CR1 = const(_TIMER_BASE_ADDR + 0x00)
_TIMER_CR2 = const(_TIMER_BASE_ADDR + 0x04)
_TIMER_EGR = const(_TIMER_BASE_ADDR + 0x14)
_TIMER_CNT = const(_TIMER_BASE_ADDR + 0x24)
_TIMER_ARR = const(_TIMER_BASE_ADDR + 0x2C)
_TIMER_RCR = const(_TIMER_BASE_ADDR + 0x30)

# Timer Cosnt
_DMA_CH_ENABLE = const(1 << (8 + _TIMER_CH)) # From docs, bit 9 enables DMA request

# DMA
_DMA_BASE = const(0x40020000)


# Namings are wrong. ignore first
# Search Datasheet to find Channel => DMA
# E.g. DMA Channel 5  - TIM4_CH3
_DMA_CH = const(3) # TIM1_CH2 is DMA_CH3

_DMA_CCR   = const(_DMA_BASE + 0x08 + 20 * (_DMA_CH - 1))
_DMA_CNDTR = const(_DMA_BASE + 0x0C + 20 * (_DMA_CH - 1))
_DMA_CPAR  = const(_DMA_BASE + 0x10 + 20 * (_DMA_CH - 1))
_DMA_CMAR  = const(_DMA_BASE + 0x14 + 20 * (_DMA_CH - 1))

_DMA_IFCR = const(0x40020004)
_DMA_ISR = const(0x40020000)

# Channel 5 flags are bits 16..19
_DMA_CH_ALL_FLAGS = const(0xF << 4 * (_DMA_CH - 1))

_DMA_SHIFT = const(4 * (_DMA_CH - 1))
_DMA_TCIF = const(1 << (_DMA_SHIFT + 1))
_DMA_HTIF = const(1 << (_DMA_SHIFT + 2))
_DMA_TEIF = const(1 << (_DMA_SHIFT + 3))

# Stream 
_STREAM_BOUNDARY = f"W55MH32IPStream{getrandbits(32)}"

#Debug
DMA_CONFIG = const(
    (2 << 12) |     	# PL = high
    (1 << 7) |       	# MINC
    (1 << 5)  			# Circular
)


class Camera:
    def __init__(self, scl = _SCL, sda = _SDA, data = _DATA_ADR,
                 href = _HREF, dclk = _DCLK, vsync = _VSYNC, max_size = 16384):
        
        # Pin configurations
        self.scl = scl
        self.sda = sda
        self.data = data
        self.href = href
        self.dclk = dclk
        self.vsync = vsync
        
        self.href_flag = False
        self._bytes = None
        self.irq_triggered = False
                   
        self.addr = None
        self.i2c = SoftI2C(self.scl, self.sda)
        
        self.max_size = max_size
        self.buf = bytearray(self.max_size)
        self.buf_addr = addressof(self.buf)
        
        self.mv = memoryview(self.buf) 
        self.mv_part_0 = self.mv[0:self.max_size // 4]
        self.mv_part_1 = self.mv[self.max_size // 4: self.max_size // 4 * 2]
        self.mv_part_2 = self.mv[self.max_size // 4 * 2:self.max_size // 4 * 3]
        self.mv_part_3 = self.mv[self.max_size // 4 * 3:]
        
        
        self.timer = Timer(_TIMER_ID, prescaler = 0, period = 0xffff)
        
        self.timer_ch = None
        self.gate_ch = None
        
        for addr in self.i2c.scan():
            if addr  in (0x30, 0x60, 0x61):
                self.addr = addr
 
        if self.addr is None:
            raise OSError(19, "No OV2640 available")
        
        self.benchmark = []
        self.advanced = 0
        self.dropped_frames = 0
        
        # Settings
        self.resolution = 0
        # UI percentage; 50 maps to the sensor's neutral raw value 0x20.
        self.brightness = 0
        self.contrast = 0
        self.hflip = False
        self.vflip = False
        self.jpeg_quality = 20
        self.saturation = 0
        self.bw = 0
        # Sensor reset default: REG45[5:0]=0, AEC=0x33, REG04[1:0]=0.
        self.aec_val = 204
        # None keeps the resolution table's AEW/AEB/VV target. CIF uses a
        # different target from SVGA/UXGA; an integer means user override.
        self.auto_exposure = None
        self.aec_enable = True
        # DSP CTRL0 AEC_SEL is active-low: reset bit 0 means AEC2 enabled.
        self.aec2_enable = True
        self.agc_enable = True
        # COM9=0x48 in OV2640_JPEG_INIT: bits 7:5 are ceiling index 2 (8x).
        self.agc_ceiling = 2
        self.agc_value = 0
        self.wb_mode = 0
        self.special_effect = 0
        self.awb_mode = True
        self.awb_mode_gain = True
        self.lens_correction = False
        self.wpc = True
        self.bpc = True
        self.color_bar = False
        
        # No ESR
        self._init_gate()
        self._init_dma()
        self._remap_pins()

#         print("DIER :", hex(mem32[0x4000080C]))
#         print("SR   :", hex(mem32[0x40000810]))
#         print("CCMR2:", hex(mem32[0x4000081C]))
#         print("CCER :", hex(mem32[0x40000820]))
#         print("CCR3 :", mem32[0x4000083C])
#         print("Capture: ", self.timer_ch.capture())
#         print("Capture: ", self.timer_ch.capture())
 
    def _remap_pins(self):
        """
        Remapping TIM2
        """
        
        # RCC clock enable
        mem32[0x40021018] |= 1
        
        # Clear AFIO stuff
        mem32[0x40010004] &= ~(
            0b11 << 8 | 	# AFIO Tim2 remap
            0b111 << 24  	# AFIO Close SWJ
        )
        
        # AFIO Tim2 enable
        # Now (CH1/ETR/PA15，CH2/PB3，CH3/PB10，CH4/PB11) for TIM2
        mem32[0x40010004] |= 0x3 << 8
        
        # Close SWJ cuz no need
        mem32[0x40010004] |= 0x4 << 24

        
        GPIOB_CRL = 0x40010C00
        GPIOB_IDR = 0x40010C08

        # PB3 = CRL bits 15:12
        crl = mem32[GPIOB_CRL]
        crl &= ~(0xF << 12)

        # floating input
        crl |= 0x4 << 12

        mem32[GPIOB_CRL] = crl
    
    def _init_gate(self):
        # Page 226 of MAnual
        # HREF = PA8 = TIM1_CH1
        self.gate_ch = self.timer.channel(
            _GATE_CH,
            Timer.IC,
            pin=self.href,
            polarity=Timer.RISING,
        )

        # Stop TIM1
        mem32[_TIMER_CR1] &= ~1

        # Configure SMCR properly
        smcr = mem32[_TIMER_SMCR]

        smcr &= ~(
            (0b111  << 0)  |   # SMS
            (0b111  << 4)  |   # TS
            (0b1111 << 8)  |   # ETF
            (0b11   << 12) |   # ETPS
            (1      << 14) |   # ECE
            (1      << 15)     # ETP
        )

        # HREF = hardware gate
        smcr |= 0b101               # SMS = gated mode
        smcr |= 0b101 << 4          # TS = TI1FP1

        # DCLK = external counter clock
        smcr |= 1 << 14             # ECE = External Clock Mode 2

        # ETP=0  -> rising ETR
        # ETPS=0 -> every ETR
        # ETF=0  -> no filter

        mem32[_TIMER_SMCR] = smcr

        # Important for TIM1 advanced timer
        mem32[_TIMER_RCR] = 0

        # We want update on every accepted ETR count
        mem32[_TIMER_ARR] = 0
        mem32[_TIMER_CNT] = 0

        # Force registers into active state
        mem32[_TIMER_EGR] = 1       # UG

        # Clear UIF generated by UG
        mem32[_TIMER_SR] &= ~1

        # Start TIM1
        mem32[_TIMER_CR1] |= 1
        
        # Rerouet dma to channel {DCLK_Channel}
        mem32[_TIMER_CR2] |= 1 << 3
    
            
        
    @micropython.native()
    def _init_dma(self):
        # Enable DMA clock RCC
        mem32[0x40021014] |= 0x01
        
        self._reset_dma()
        
        # Do NOT generate TIM1_UP DMA requests yet
        mem32[_TIMER_DIER] &= ~_DMA_CH_ENABLE
        
    def write_reg(self, reg, cmd):
        self.i2c.writeto_mem(self.addr, reg, cmd.to_bytes())
    
    def read_reg(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)
    
    def read_reg_in_binary(self, reg):
        d = self.i2c.readfrom_mem(self.addr, reg, 1)
        return bin(int(d.hex(), 16))  

    def write_table(self, commands):
        """Write compact register/value byte table in original order."""
        
        for i in range(0, len(commands), 2):
            register = commands[i]
            value = commands[i + 1]
            self.write_reg(register, value)
            
    def reset(self):
        self.dropped_frames = 0
        self.i2c.writeto_mem(self.addr, 0xff, b'\x01')
        self.i2c.writeto_mem(self.addr, 0x12, b'\x80')
        
        self.i2c.writeto_mem(self.addr, 0xff, b'\x00')
        self.i2c.writeto_mem(self.addr, 0xE0, b'\x04')
        time.sleep_ms(100)

          
    @micropython.viper()
    def _wait_vsync(self):
        # W55MH32L
        """
        ptr = ptr32(_CLK_ADR)

        while (int(ptr[0]) & 0x20) == 0:
            pass

        while (int(ptr[0]) & 0x20) != 0:
            pass
        """
        # Address of VSYNC GPIO
        # Now need PF11 
        # idr = ptr32(0x40011C08)
        idr = ptr32(0x40011008)
        
        # Address of TIMER 
        dier 	= ptr32(_TIMER_DIER)
        cnt		= ptr32(_TIMER_CNT)
        sr		= ptr32(_TIMER_SR)
        
        # Addr of DMA registers
        ccr 	= ptr32(_DMA_CCR)
        ifcr 	= ptr32(_DMA_IFCR)
        cpar	= ptr32(_DMA_CPAR)
        cmar	= ptr32(_DMA_CMAR)
        cndtr	= ptr32(_DMA_CNDTR)
    
        
        # Data
        perp_addr = int(self.data)
        mem_addr = int(self.buf_addr)
        max_sz = int(self.max_size)
    

        # Check VREF Pin num value
        # Proved, when pin detects 1 => ov2640 outputs low => meaning previous frame
        # vice versa, when pin detects 0 => ov2640 outputs high => meaning readying to gen new frame
        while (int(idr[0]) & (1 << 5)) != 0:
            pass
        
        # _Reset_dma but in viper
        dier[0] &= ~_DMA_CH_ENABLE
        ccr[0] &= ~1
        ifcr[0] = _DMA_CH_ALL_FLAGS
        
        
        cpar[0] = perp_addr
        cmar[0] = mem_addr
        cndtr[0] = max_sz
        
        cnt[0] = 0
        sr[0] &= ~1 
        ccr[0] = DMA_CONFIG | 1
        
        dier[0] |= _DMA_CH_ENABLE

        while (int(idr[0]) & (1 << 5)) == 0:
            pass
        
        

    @micropython.viper()
    def count_href_rising_edges(self, spin_limit: int = 10000000) -> int:
        """Count HREF line pulses during one active VSYNC frame.

        Returns the number of HREF rising edges, or a negative timeout code:
        -1 while waiting for the current frame to end, -2 while waiting for
        the next frame to start, and -3 if that frame never ends.
        """
        vsync = ptr32(0x40011008)  # GPIOC IDR; VSYNC is PC5
        href = ptr32(0x40010C08)   # GPIOB IDR; HREF is PB3
        vsync_mask = 1 << 5
        href_mask = 1 << 3
        spins = 0

        # Synchronize to the end of any frame already in progress.
        while (int(vsync[0]) & vsync_mask) != 0:
            spins += 1
            if spins >= spin_limit:
                return -1

        # Wait for the next active frame.
        spins = 0
        while (int(vsync[0]) & vsync_mask) == 0:
            spins += 1
            if spins >= spin_limit:
                return -2

        count = 0
        previous = int(href[0]) & href_mask
        spins = 0

        # One rising HREF edge represents the start of one output line.
        while (int(vsync[0]) & vsync_mask) != 0:
            current = int(href[0]) & href_mask
            if current != 0 and previous == 0:
                count += 1
            previous = current
            spins += 1
            if spins >= spin_limit:
                return -3

        return count

    @micropython.viper()
    def count_pa15_rising_edges(self, spin_limit: int = 10000000) -> int:
        """Sample PA15 directly and count observed PCLK rising edges.

        This bypasses TIM2 and DMA. Because PCLK can be faster than the CPU
        polling loop, the result is a presence/activity test rather than an
        exact PCLK count. Negative return values use the same timeout meanings
        as count_href_rising_edges().
        """
        vsync = ptr32(0x40011008)  # GPIOC IDR; VSYNC is PC5
        gpioa = ptr32(0x40010808)  # GPIOA IDR; PCLK is PA15
        vsync_mask = 1 << 5
        pclk_mask = 1 << 15
        spins = 0

        # Synchronize to the end of any frame already in progress.
        while (int(vsync[0]) & vsync_mask) != 0:
            spins += 1
            if spins >= spin_limit:
                return -1

        # Wait for the next active frame.
        spins = 0
        while (int(vsync[0]) & vsync_mask) == 0:
            spins += 1
            if spins >= spin_limit:
                return -2

        count = 0
        previous = int(gpioa[0]) & pclk_mask
        spins = 0

        while (int(vsync[0]) & vsync_mask) != 0:
            current = int(gpioa[0]) & pclk_mask
            if current != 0 and previous == 0:
                count += 1
            previous = current
            spins += 1
            if spins >= spin_limit:
                return -3

        return count
              
        
    
    @micropython.native()
    def _reset_dma(self):

        # No TIM4 -> DMA requests while configuring
        mem32[_TIMER_DIER] &= ~_DMA_CH_ENABLE

        # Disable DMA
        mem32[_DMA_CCR] &= ~1

        # Clean channel state
        mem32[_DMA_IFCR] = _DMA_CH_ALL_FLAGS
        
        # Set R+W addr for DMA
        mem32[_DMA_CPAR] = self.data # This is required apparently, Check notes.
        mem32[_DMA_CMAR] = self.buf_addr
        
        # Set DMA max len
        mem32[_DMA_CNDTR] = self.max_size

        # PL high + MINC
        # mem32[_DMA_CCR] = DMA_CONFIG

        # Arm DMA
        mem32[_DMA_CCR] = DMA_CONFIG | 1
        
    #===========================================================#
    # 						QUARTER VERSION						#
    #===========================================================#
    @micropython.viper()
    def _drain_image(self, threshold: int) -> int:
        isr  = ptr32(_DMA_ISR)
        ifcr = ptr32(_DMA_IFCR)
        dier = ptr32(_TIMER_DIER)
        cndtr = ptr32(_DMA_CNDTR)
        ccr = ptr32(_DMA_CCR)      
        # gpio = ptr32(0x40011C08)
        gpio = ptr32(0x40011008)
        
        # 4 Size
        max_size = int(self.max_size)
        quarter_size = int(self.max_size) // 4
        section = quarter_size * threshold
    
        while True:
            # print("Compare: ", max_size - cndtr[0],", Transaction: ", cndtr[0])
            # Use IRQ for only Last section
            if threshold == 4:
                if (isr[0] & int(_DMA_TCIF)):
                    ifcr[0] = int(_DMA_TCIF)
                    return 2
                
            # Number of bytes written         
            elif (max_size - cndtr[0]) >= section:    
                return 1             
            
            # Check if go low
            if (int(gpio[0]) & (1 << 5)) == 0:
                dier[0] &= ~int(_DMA_CH_ENABLE)
                ccr[0] &= ~1
                return 0
        
   
#     @micropython.native()
#     def stream_frame(self, sock):
#         header = (
#             f"--{_STREAM_BOUNDARY}\r\n"
#             "Content-Type: image/jpeg\r\n"
#             "\r\n"
#         ).encode()
#         
#         while True:
#             gc.collect()
#             sock.write(header)
#             
#             # Synchronise to new frame
#             self._wait_vsync()
#             
#             frame_complete = False
#             section = 1
# 
#             q = self.max_size // 4
#             # Start draining a fame
# 
#             while not frame_complete:
#                 result = self._drain_image(section)
#                 # Select section[x] frame
#                 if result == 1:
#                     # Normal write
#                     start = (section - 1) * q
#                     end = section * q
#                     self._write_all(sock, self.mv[start:end])
#                     section += 1
#                 elif result == 2:
#                     self._write_all(sock, self.mv[3*q:4*q])
#                     section = 1
#                 else:
#                     # Frame ended
#                     start = (section - 1) * q
#                     end = self.max_size - mem32[_DMA_CNDTR]
#                     if end > start:
#                         self._write_all(sock, self.mv[start:end])
#                     frame_complete = True
#             sock.write(b'\r\n')    

    # Sockets
    @micropython.native()
    def _write_all(self, sock, data):

        offset = 0
        while offset < len(data):
            written = sock.write(data[offset:])
            if written is None or written < 0:
                raise OSError("socket write failed")
            elif written == 0:
                # Busy
                pass
            offset += written
            
    @micropython.native()
    def stream_frame_with_settings(self, sock, server, frame = None):
        header = (
            f"--{_STREAM_BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            "\r\n"
        ).encode()
        frame_count = 0
        while True:
            frame_complete = False
            section = 1
            q = self.max_size // 4
            
            # Synchronise to new frame
            self._wait_vsync()
            gc.collect()
            header_complete = False
            # Start draining a fame     
            while not frame_complete:
                result = self._drain_image(section)
                # Select section[x] frame
                if result == 1:
                    # Normal write
#                     before = mem32[_DMA_CNDTR]
                    if section == 1:
                        # Maybe add frame check header (around 20us if only check 0 and 1)
                        if not header_complete:
                            # t0 = time.ticks_us()
                            found = self.find_jpeg_header(self.mv_part_0)
                            # self.benchmark.append(time.ticks_diff(time.ticks_us(), t0))
                            if not found: 
                                # Simulate drop frame use frame_count % 2 == 0 should get fps 13
                                # Drop Frame
                                year, month, day, hour, minute, second, _, _ = time.localtime()
                                print(f"Dropped frame at {hour:02d}:{minute:02d}:{second:02d}")
                                self.dropped_frames += 1
                                frame_complete = True
                                break
                            else:
                                header_complete = True
                                self._write_all(sock, header)
                        self._write_all(sock, self.mv_part_0)
                        # if self.max_size - mem32[_DMA_CNDTR]
                    elif section == 2:
                        self._write_all(sock, self.mv_part_1)
                    elif section == 3:
                        self._write_all(sock, self.mv_part_2)
#                     elif section == 4:
#                         self._write_all(sock, self.mv_part_3)
                    else:
                        self.log("Unknown section.")
                    section += 1
                elif result == 2:
                    self._write_all(sock, self.mv_part_3)
                    section = 1
                else:
                    # Frame ended
                    start = (section - 1) * q
                    end = self.max_size - mem32[_DMA_CNDTR]

                    if section == 1 and not header_complete:
                        if end < 2 or self.buf[0] != 0xFF or self.buf[1] != 0xD8:
                            self.dropped_frames += 1
                            frame_complete = True
                            break

                        self._write_all(sock, header)
                        header_complete = True

                    if end > start:
                        self._write_all(sock, self.mv[start:end])

                    frame_complete = True
                    frame_count += 1
                    if frame is not None:
                        if frame_count > frame:
                            return
                        
                    # See any configuration updates on each end-frame
                    server.poll()
            self._write_all(sock, b"\r\n")

    # Sockets
    @micropython.native()
    def _write_all(self, sock, data):
        # t0 = time.ticks_us()
        offset = 0
        # zero = 0
        while offset < len(data):
            written = sock.write(data[offset:])
            if written is None or written < 0:
                raise OSError("socket write failed")
            elif written == 0:
                # zero += 1
                # Busy
                pass
            offset += written
        #print("send ms:", time.ticks_diff(time.ticks_us(), t0), "zero writes:", zero)
    
    @micropython.native()
    def stream_start(self, sock):
        main_header = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: multipart/x-mixed-replace;boundary={_STREAM_BOUNDARY}\r\n"
            "Connection: keep-alive\r\n"
            "Cache-Control: no-cache\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n" # Critical blank line separating headers from body
        )
        sock.write(main_header.encode('utf-8'))
                   
    
    @micropython.viper()
    def find_jpeg_header(self, buf: ptr8) -> bool:
        if buf[0] == 0xff and buf[1] == 0xd8:
            return True
        else:
            return False
    # Logs
    def log(self, msg):
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8")
        print("[Camera]" +msg)
            
