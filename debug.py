DMA1_CH4_CCR   = 0x40020044
DMA1_CH4_CNDTR = 0x40020048
DMA1_CH5_CCR   = 0x40020058
DMA1_CH5_CNDTR = 0x4002005C
SPI2_CR2       = 0x40003804
SPI2_SR        = 0x40003808
SPI2_CR1       = 0x40000000 + 0x00003800

def dump_spi_dma(label):
    print(
        label,
        "CR1", hex(mem32[SPI2_CR1]),
        "CR2", hex(mem32[SPI2_CR2]),
        "SR", hex(mem32[SPI2_SR]),
        "CH4", hex(mem32[DMA1_CH4_CCR]), mem32[DMA1_CH4_CNDTR],
        "CH5", hex(mem32[DMA1_CH5_CCR]), mem32[DMA1_CH5_CNDTR],
    )
