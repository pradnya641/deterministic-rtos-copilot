#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* ISR-to-task pipeline: UART0 RX ISR -> Processing task */
static QueueHandle_t xRxQueue;   /* UART ISR -> Processing (depth=64) */

#define PRIORITY_PROCESS 3
#define PRIORITY_OUTPUT  1

/* UART0 RX Interrupt Handler */
void UART0_IRQHandler(void) __attribute__((interrupt("IRQ")));
void UART0_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    uint8_t byte = U0RBR;   /* Read received byte ? also clears interrupt */

    /* Safe: send byte to task without blocking */
    xQueueSendFromISR(xRxQueue, &byte, &xHigherPriorityTaskWoken);

    /* Acknowledge VIC */
    VICVectAddr = 0;

    /* Yield if a higher-priority task was unblocked */
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

static void vProcessingTask(void *pv)
{
    uint8_t byte;
    char frame[128];  int idx = 0;
    for (;;) {
        xQueueReceive(xRxQueue, &byte, portMAX_DELAY);
        frame[idx++] = byte;
        if (byte == '\n' || idx >= 127) {
            frame[idx] = '\0';
            /* Process complete frame here */
            idx = 0;
        }
    }
}

int main(void)
{
    /* UART0 init: 9600 baud */
    PINSEL0 |= 0x05;        /* P0.0=TXD0, P0.1=RXD0 */
    U0LCR    = 0x83;        /* DLAB=1, 8N1 */
    U0DLL    = 391;         /* 9600 baud @ 60MHz PCLK */
    U0LCR    = 0x03;        /* DLAB=0 */
    U0IER    = 0x01;        /* Enable RX interrupt */

    /* VIC setup for UART0 */
    VICVectAddr6  = (unsigned)UART0_IRQHandler;
    VICVectCntl6  = 0x20 | 6;
    VICIntEnable |= (1 << 6);

    xRxQueue = xQueueCreate(64, sizeof(uint8_t));
    xTaskCreate(vProcessingTask, "Process", 512, NULL, PRIORITY_PROCESS, NULL);
    vTaskStartScheduler();
    for(;;);
}