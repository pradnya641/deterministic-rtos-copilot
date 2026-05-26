#include <lpc214x.h>

void SPI_Init(void)
{
    /* Step 1: Configure P0.4=SCK0, P0.5=MISO0, P0.6=MOSI0, P0.7=SSEL0 */
    /* PINSEL0 bits [9:8]=01 (SCK), [11:10]=01 (MISO), [13:12]=01 (MOSI), [15:14]=01 (SSEL) */
    PINSEL0 = (PINSEL0 & ~(0xFF << 8)) | (0x55 << 8);

    /* Step 2: Configure SPI — Master, 8-bit, CPOL=0, CPHA=0
       Bit  2 (BitEnable) = 1 → activates BITS[11:8] field
       Bit  5 (MSTR)      = 1 → Master mode
       Bits 11:8 (BITS)   = 8 → 8-bit transfer (binary 1000)
       Combined: (1<<5)|(1<<2)|(8<<8) = 0x824 */
    S0SPCR = (1 << 5) | (1 << 2) | (8 << 8); /* 0x824: Master, BitEnable, 8-bit */

    /* Step 3: Set clock divider — SPI clock = PCLK / S0SPCCR */
    /* At PCLK=15MHz, S0SPCCR=8 gives SPI clock = 1.875MHz */
    S0SPCCR = 8;
}

uint8_t SPI_Transfer(uint8_t data)
{
    S0SPDR = data;                    /* Write byte to start transfer */
    while (!(S0SPSR & (1 << 7)));    /* Wait for SPIF (transfer complete) */
    return S0SPDR;                    /* Read received byte */
}

/* Automatically appended main stub for SDK link verification */
int main(void) {
    return 0;
}
