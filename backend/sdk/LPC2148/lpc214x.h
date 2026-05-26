#ifndef LPC214X_H
#define LPC214X_H

#include <stdint.h>

/* Pin Connect Block */
#define PINSEL0         (*((volatile uint32_t *) 0xE002C000))
#define PINSEL1         (*((volatile uint32_t *) 0xE002C004))
#define PINSEL2         (*((volatile uint32_t *) 0xE002C014))

/* GPIO0 */
#define IO0PIN          (*((volatile uint32_t *) 0xE0028000))
#define IO0SET          (*((volatile uint32_t *) 0xE0028004))
#define IO0DIR          (*((volatile uint32_t *) 0xE0028008))
#define IO0CLR          (*((volatile uint32_t *) 0xE002800C))

/* GPIO1 */
#define IO1PIN          (*((volatile uint32_t *) 0xE0028010))
#define IO1SET          (*((volatile uint32_t *) 0xE0028014))
#define IO1DIR          (*((volatile uint32_t *) 0xE0028018))
#define IO1CLR          (*((volatile uint32_t *) 0xE002801C))

/* Watchdog Timer */
#define WDMOD           (*((volatile uint32_t *) 0xE0000000))
#define WDTC            (*((volatile uint32_t *) 0xE0000004))
#define WDFEED          (*((volatile uint32_t *) 0xE0000008))
#define WDTV            (*((volatile uint32_t *) 0xE000000C))

/* UART0 */
#define U0RBR           (*((volatile uint32_t *) 0xE000C000))
#define U0THR           (*((volatile uint32_t *) 0xE000C000))
#define U0DLL           (*((volatile uint32_t *) 0xE000C000))
#define U0DLM           (*((volatile uint32_t *) 0xE000C004))
#define U0IER           (*((volatile uint32_t *) 0xE000C004))
#define U0IIR           (*((volatile uint32_t *) 0xE000C008))
#define U0FCR           (*((volatile uint32_t *) 0xE000C008))
#define U0LCR           (*((volatile uint32_t *) 0xE000C00C))
#define U0LSR           (*((volatile uint32_t *) 0xE000C014))
#define U0SCR           (*((volatile uint32_t *) 0xE000C01C))

/* UART1 */
#define U1RBR           (*((volatile uint32_t *) 0xE0010000))
#define U1THR           (*((volatile uint32_t *) 0xE0010000))
#define U1DLL           (*((volatile uint32_t *) 0xE0010000))
#define U1DLM           (*((volatile uint32_t *) 0xE0010004))
#define U1IER           (*((volatile uint32_t *) 0xE0010004))
#define U1LCR           (*((volatile uint32_t *) 0xE001000C))
#define U1LSR           (*((volatile uint32_t *) 0xE0010014))

/* Timer 0 */
#define T0IR            (*((volatile uint32_t *) 0xE0004000))
#define T0TCR           (*((volatile uint32_t *) 0xE0004004))
#define T0TC            (*((volatile uint32_t *) 0xE0004008))
#define T0PR            (*((volatile uint32_t *) 0xE000400C))
#define T0PC            (*((volatile uint32_t *) 0xE0004010))
#define T0MCR           (*((volatile uint32_t *) 0xE0004014))
#define T0MR0           (*((volatile uint32_t *) 0xE0004018))
#define T0MR1           (*((volatile uint32_t *) 0xE000401C))
#define T0MR2           (*((volatile uint32_t *) 0xE0004020))
#define T0MR3           (*((volatile uint32_t *) 0xE0004024))

/* Timer 1 */
#define T1IR            (*((volatile uint32_t *) 0xE0008000))
#define T1TCR           (*((volatile uint32_t *) 0xE0008004))
#define T1TC            (*((volatile uint32_t *) 0xE0008008))
#define T1PR            (*((volatile uint32_t *) 0xE000800C))
#define T1PC            (*((volatile uint32_t *) 0xE0008010))
#define T1MCR           (*((volatile uint32_t *) 0xE0008014))
#define T1MR0           (*((volatile uint32_t *) 0xE0008018))
#define T1MR1           (*((volatile uint32_t *) 0xE000801C))
#define T1MR2           (*((volatile uint32_t *) 0xE0008020))
#define T1MR3           (*((volatile uint32_t *) 0xE0008024))

/* PWM */
#define PWMTCR          (*((volatile uint32_t *) 0xE0014004))
#define PWMMCR          (*((volatile uint32_t *) 0xE0014014))
#define PWMMR0          (*((volatile uint32_t *) 0xE0014018))
#define PWMMR1          (*((volatile uint32_t *) 0xE001401C))
#define PWMMR2          (*((volatile uint32_t *) 0xE0014020))
#define PWMMR3          (*((volatile uint32_t *) 0xE0014024))
#define PWMPCR          (*((volatile uint32_t *) 0xE001404C))
#define PWMLER          (*((volatile uint32_t *) 0xE0014050))

/* ADC0 */
#define AD0CR           (*((volatile uint32_t *) 0xE0034000))
#define AD0GDR          (*((volatile uint32_t *) 0xE0034004))
#define AD0DR1          (*((volatile uint32_t *) 0xE0034014))

/* ADC1 */
#define AD1CR           (*((volatile uint32_t *) 0xE0060000))
#define AD1GDR          (*((volatile uint32_t *) 0xE0060004))

/* SPI0 */
#define S0SPCR          (*((volatile uint32_t *) 0xE0020000))
#define S0SPSR          (*((volatile uint32_t *) 0xE0020004))
#define S0SPDR          (*((volatile uint32_t *) 0xE0020008))
#define S0SPCCR         (*((volatile uint32_t *) 0xE002000C))

/* Vectored Interrupt Controller (VIC) */
#define VICIRQStatus    (*((volatile uint32_t *) 0xFFFFF000))
#define VICFIQStatus    (*((volatile uint32_t *) 0xFFFFF004))
#define VICRawIntr      (*((volatile uint32_t *) 0xFFFFF008))
#define VICIntSelect    (*((volatile uint32_t *) 0xFFFFF00C))
#define VICIntEnable    (*((volatile uint32_t *) 0xFFFFF010))
#define VICIntEnClr     (*((volatile uint32_t *) 0xFFFFF014))
#define VICSoftInt      (*((volatile uint32_t *) 0xFFFFF018))
#define VICSoftIntClear (*((volatile uint32_t *) 0xFFFFF01C))
#define VICProtection   (*((volatile uint32_t *) 0xFFFFF020))
#define VICVectAddr     (*((volatile uint32_t *) 0xFFFFF030))
#define VICDefVectAddr  (*((volatile uint32_t *) 0xFFFFF034))

#define VICVectAddr0    (*((volatile uint32_t *) 0xFFFFF100))
#define VICVectAddr1    (*((volatile uint32_t *) 0xFFFFF104))
#define VICVectAddr2    (*((volatile uint32_t *) 0xFFFFF108))
#define VICVectAddr3    (*((volatile uint32_t *) 0xFFFFF10C))
#define VICVectAddr4    (*((volatile uint32_t *) 0xFFFFF110))
#define VICVectAddr5    (*((volatile uint32_t *) 0xFFFFF114))
#define VICVectAddr6    (*((volatile uint32_t *) 0xFFFFF118))
#define VICVectAddr7    (*((volatile uint32_t *) 0xFFFFF11C))
#define VICVectAddr8    (*((volatile uint32_t *) 0xFFFFF120))
#define VICVectAddr9    (*((volatile uint32_t *) 0xFFFFF124))
#define VICVectAddr10   (*((volatile uint32_t *) 0xFFFFF128))
#define VICVectAddr11   (*((volatile uint32_t *) 0xFFFFF12C))
#define VICVectAddr12   (*((volatile uint32_t *) 0xFFFFF130))
#define VICVectAddr13   (*((volatile uint32_t *) 0xFFFFF134))
#define VICVectAddr14   (*((volatile uint32_t *) 0xFFFFF138))
#define VICVectAddr15   (*((volatile uint32_t *) 0xFFFFF13C))
#define VICVectAddr23   (*((volatile uint32_t *) 0xFFFFF15C))

#define VICVectCntl0    (*((volatile uint32_t *) 0xFFFFF200))
#define VICVectCntl1    (*((volatile uint32_t *) 0xFFFFF204))
#define VICVectCntl2    (*((volatile uint32_t *) 0xFFFFF208))
#define VICVectCntl3    (*((volatile uint32_t *) 0xFFFFF20C))
#define VICVectCntl4    (*((volatile uint32_t *) 0xFFFFF210))
#define VICVectCntl5    (*((volatile uint32_t *) 0xFFFFF214))
#define VICVectCntl6    (*((volatile uint32_t *) 0xFFFFF218))
#define VICVectCntl7    (*((volatile uint32_t *) 0xFFFFF21C))
#define VICVectCntl8    (*((volatile uint32_t *) 0xFFFFF220))
#define VICVectCntl9    (*((volatile uint32_t *) 0xFFFFF224))
#define VICVectCntl10   (*((volatile uint32_t *) 0xFFFFF228))
#define VICVectCntl11   (*((volatile uint32_t *) 0xFFFFF22C))
#define VICVectCntl12   (*((volatile uint32_t *) 0xFFFFF230))
#define VICVectCntl13   (*((volatile uint32_t *) 0xFFFFF234))
#define VICVectCntl14   (*((volatile uint32_t *) 0xFFFFF238))
#define VICVectCntl15   (*((volatile uint32_t *) 0xFFFFF23C))
#define VICVectCntl23   (*((volatile uint32_t *) 0xFFFFF25C))

/* External Interrupts */
#define EXTINT          (*((volatile uint32_t *) 0xE01FC140))
#define EXTMODE         (*((volatile uint32_t *) 0xE01FC148))
#define EXTPOLAR        (*((volatile uint32_t *) 0xE01FC14C))

/* CAN Controller 1 */
#define CAN1MOD         (*((volatile uint32_t *) 0xE0040000))
#define CAN1CMR         (*((volatile uint32_t *) 0xE0040004))
#define CAN1IER         (*((volatile uint32_t *) 0xE0040008))
#define CAN1GSR         (*((volatile uint32_t *) 0xE004000C))
#define CAN1BTR         (*((volatile uint32_t *) 0xE0040010))
#define CAN1RFS         (*((volatile uint32_t *) 0xE0040020))
#define CAN1RID         (*((volatile uint32_t *) 0xE0040024))
#define CAN1RDA         (*((volatile uint32_t *) 0xE0040028))
#define CAN1RDB         (*((volatile uint32_t *) 0xE004002C))

/* Timer aliases for the FreeRTOS LPC2000 port compatibility */
#define T0_IR   T0IR
#define T0_TCR  T0TCR
#define T0_TC   T0TC
#define T0_PR   T0PR
#define T0_PC   T0PC
#define T0_MCR  T0MCR
#define T0_MR0  T0MR0
#define T0_MR1  T0MR1
#define T0_MR2  T0MR2
#define T0_MR3  T0MR3

#endif /* LPC214X_H */
