# ov2640_dma_capture.py -- template for HARDWARE-triggered capture via DMA.
#
# Companion to ANALYSIS.md / ov2640_tuning.py. This is a SCAFFOLD, not a
# drop-in replacement: several addresses below are placeholders that MUST be
# verified against the W55MH32L datasheet before use (see every TODO). Does
# not modify _ov2640.py / ov2640_regs.py / i2c_test.py.
#
# ---------------------------------------------------------------------------
# Why this is a different shape of code than _read_all() in _ov2640.py
# ---------------------------------------------------------------------------
# _read_all() is CPU polling: the core itself executes a load instruction
# per sample, in a loop, competing with everything else for cycles. That is
# what caps it at ~1-3 MHz (see ANALYSIS.md).
#
# True DMA capture removes the CPU from the per-byte path entirely:
#
#   DCLK edge -> timer counts it (hardware) -> timer's DMA request fires ->
#   DMA controller copies one byte from the GPIO data port straight into
#   RAM -> repeat, with zero CPU instructions executed per byte.
#
# The CPU only sets this pipeline up once per frame and then waits for a
# "transfer complete" flag/interrupt. The ceiling is now the timer/DMA
# hardware's request rate (typically tens of MHz), not core instruction
# throughput -- this is the actual fix for the polling ceiling in
# ANALYSIS.md, not a further Viper optimization.
#
# ---------------------------------------------------------------------------
# The catch: OV2640 has no dedicated camera peripheral (DCMI) to lean on
# ---------------------------------------------------------------------------
# The classic STM32F1-style peripheral map this codebase already uses
# (GPIOA @ 0x40010800, GPIOC @ 0x40011000, RCC_APB2ENR @ 0x40021018) has no
# DCMI block. The standard bare-metal workaround, used here:
#
#   1. Route DCLK into a general-purpose timer's external clock input
#      (ETR, or a capture channel used as the clock source) so the timer
#      counts DCLK edges in hardware, not software.
#   2. Put that timer in "gated slave mode" with HREF as the gate input, so
#      it only counts (and only requests DMA) while HREF is high -- line
#      blanking is skipped in hardware, no CPU branch needed.
#   3. Enable the timer's update/capture DMA request so every valid DCLK
#      edge triggers one DMA beat: GPIO data-port IDR -> next RAM byte.
#   4. Handle VSYNC (start-of-frame) and JPEG SOI/EOI hunting outside the
#      hot path, since those are rare, once-per-frame events, not
#      per-byte ones.
#
# THIS REQUIRES: the physical pin used for DCLK to actually be wired to a
# timer channel with capture/ETR capability on your board. If DCLK's pin
# has no timer-capable alternate function, this technique does not work on
# that pin and DCLK would need to be re-routed at the hardware/board level.
# I cannot confirm this from source alone -- check your MCU datasheet's
# alternate-function/timer-input table for the actual DCLK pin.
#
# ---------------------------------------------------------------------------

from machine import mem32
import time

# --- Known-good addresses (reused from the existing GPIO code) -----------
RCC_APB2ENR = const(0x40021018)   # TODO verify: bit for AFIO/GPIO enables
RCC_APB1ENR = const(0x4002101C)   # TODO verify: bit for TIMx/DMA enables

GPIOA_CRL   = const(0x40010800)
GPIOA_IDR   = const(0x40010808)
GPIOC_CRL   = const(0x40011000)
GPIOC_IDR   = const(0x40011008)

# Data port used by i2c_test.py's Camera(data=0x40010C08) -> GPIOB IDR.
GPIOB_IDR   = const(0x40010C08)

# --- Placeholders you MUST verify against the datasheet -------------------
# TODO: confirm DCLK's actual pin has timer ETR/capture capability, and
# which timer/channel that maps to. TIM3 is used below only as an example
# because it is the most common choice on STM32F1-family parts; it may be
# wrong for your silicon/pinout.
TIM3_BASE   = const(0x40000400)   # TODO verify
TIM3_CR1    = TIM3_BASE + 0x00
TIM3_SMCR   = TIM3_BASE + 0x08    # slave mode control (gated mode + trigger select)
TIM3_DIER   = TIM3_BASE + 0x0C    # DMA/interrupt enable
TIM3_SR     = TIM3_BASE + 0x10
TIM3_CNT    = TIM3_BASE + 0x24
TIM3_ARR    = TIM3_BASE + 0x2C

# TODO verify: DMA channel that services TIM3 (varies by timer/channel and
# by MCU -- on classic STM32F1 this is typically DMA1, but the *channel*
# number depends on which TIM3 event/channel you use).
DMA1_BASE   = const(0x40020000)   # TODO verify
DMA1_CH_BASE = DMA1_BASE + 0x08   # TODO verify: offset for the specific channel
DMA_CCR     = DMA1_CH_BASE + 0x00
DMA_CNDTR   = DMA1_CH_BASE + 0x04
DMA_CPAR    = DMA1_CH_BASE + 0x08   # peripheral address (source)
DMA_CMAR    = DMA1_CH_BASE + 0x0C   # memory address (destination)

VSYNC_BIT   = const(1 << 6)   # PA6, matches _ov2640.py's _wait_vsync()


def _wait_vsync():
    """One-time per-frame gate. Not throughput-critical, so plain polling
    here is fine -- this mirrors _ov2640.py's _wait_vsync(), not a
    duplicate of the part that actually needed fixing."""
    ptr = GPIOA_IDR
    while (mem32[ptr] & VSYNC_BIT) == 0:
        pass
    while (mem32[ptr] & VSYNC_BIT) != 0:
        pass


def init_dma_capture():
    """One-time hardware setup. Placeholder bit values -- fill in from your
    datasheet's timer/DMA chapters before use. Left unimplemented (raises)
    rather than silently doing the wrong thing with guessed bit positions,
    since wrong CR1/SMCR/CCR bits on real silicon can be a genuinely
    confusing failure mode to debug blind."""
    raise NotImplementedError(
        "Fill in TIM3/DMA1 bit-level setup for your confirmed DCLK timer "
        "pin mapping before using this. See the TODOs above this function."
    )

    # Sketch of what setup looks like once addresses are confirmed:
    #
    # 1. Enable AFIO/GPIOA/GPIOB/TIM3/DMA1 clocks in RCC_APB2ENR/APB1ENR.
    # 2. Configure the DCLK pin as the timer's external clock input
    #    (alternate-function input, per datasheet), HREF pin as the
    #    slave-mode trigger input.
    # 3. TIM3_SMCR: select "Gated Mode" (SMS=101) with HREF as the trigger
    #    input (TS bits), and external clock source for the counter.
    # 4. TIM3_DIER: enable the DMA request on whichever event you're
    #    driving DMA from (update or capture-compare, per your channel
    #    choice).
    # 5. DMA_CPAR = GPIOB_IDR (or the specific byte-wide alias if your part
    #    exposes one -- reading the full 32-bit IDR and masking in a tiny
    #    post-pass may be simpler/safer than fighting for a byte-sized
    #    peripheral address).
    # 6. DMA_CMAR = destination buffer address, DMA_CNDTR = buffer length,
    #    DMA_CCR = enable, memory-increment, circular or one-shot per frame.
    # 7. TIM3_CR1 = enable counter.


def capture_frame_dma(buf, max_size):
    """buf: bytearray sized for the expected frame. Requires
    init_dma_capture() to have been called and the peripherals configured.
    Returns the number of bytes DMA'd once transfer-complete fires, or -1
    on VSYNC timeout. Left as a sketch for the same reason as
    init_dma_capture(): filling in guessed register bit positions here
    would be worse than being explicit about what's unverified."""
    raise NotImplementedError(
        "Wire this up once init_dma_capture() is filled in: start VSYNC "
        "wait, arm DMA_CNDTR/DMA_CCR for this frame, start TIM3_CR1 "
        "counter, then poll (or IRQ on) the DMA transfer-complete flag "
        "instead of polling GPIO per byte."
    )


if __name__ == '__main__':
    print(__doc__)
    print()
    print("This file intentionally does not run a capture yet.")
    print("Fill in the TODOs (timer/DMA addresses + bit fields verified")
    print("against the W55MH32L datasheet) before calling init_dma_capture().")
