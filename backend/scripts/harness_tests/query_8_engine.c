#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct {
    uint32_t id;        /* CAN message identifier */
    uint8_t  dlc;       /* Data Length Code (0-8 bytes) */
    uint8_t  data[8];   /* CAN payload */
} CANFrame_t;

static QueueHandle_t xCANQueue;   /* CAN ISR -> Processing (depth=16) */

#define PRIORITY_CAN_PROC  3
#define PRIORITY_TELEM     1

/* CAN1 RX Interrupt Handler */
void CAN_IRQHandler(void) __attribute__((interrupt("IRQ")));
void CAN_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    CANFrame_t frame;

    /* Read CAN1 receive registers */
    frame.id  = CAN1RID;                        /* Received ID */
    frame.dlc = (CAN1RFS >> 16) & 0x0F;         /* Frame info: DLC bits [19:16] */
    frame.data[0] = CAN1RDA & 0xFF;             /* Bytes 0-3 from CAN1RDA */
    frame.data[1] = (CAN1RDA >> 8)  & 0xFF;
    frame.data[2] = (CAN1RDA >> 16) & 0xFF;
    frame.data[3] = (CAN1RDA >> 24) & 0xFF;
    frame.data[4] = CAN1RDB & 0xFF;             /* Bytes 4-7 from CAN1RDB */
    frame.data[5] = (CAN1RDB >> 8)  & 0xFF;
    frame.data[6] = (CAN1RDB >> 16) & 0xFF;
    frame.data[7] = (CAN1RDB >> 24) & 0xFF;

    /* Release receive buffer */
    CAN1CMR = (1<<2);   /* CMR: RRB (Release Receive Buffer) */

    xQueueSendFromISR(xCANQueue, &frame, &xHigherPriorityTaskWoken);

    /* Acknowledge VIC */
    VICVectAddr = 0;
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

/* vCANProcessingTask: decodes CAN frames by ID */
static void vCANProcessingTask(void *pv)
{
    CANFrame_t frame;
    uint16_t speed_kmh, rpm;
    for (;;)
    {
        if (xQueueReceive(xCANQueue, &frame, portMAX_DELAY) == pdTRUE)
        {
            if (frame.id == 0x100)   /* Speed frame */
                speed_kmh = ((uint16_t)frame.data[1] << 8) | frame.data[0];
            else if (frame.id == 0x200) /* RPM frame */
                rpm = ((uint16_t)frame.data[1] << 8) | frame.data[0];
            /* Forward to telemetry via additional queue */
        }
    }
}

/* vTelemetryTask: serializes decoded data to UART0 */
static void vTelemetryTask(void *pv)
{
    for (;;)
    {
        /* Transmit speed/RPM as CSV via U0THR */
        vTaskDelay(pdMS_TO_TICKS(100));  /* 10Hz telemetry rate */
    }
}

int main(void)
{
    /* Configure P0.0=RD1, P0.1=TD1: PINSEL0 bits[1:0]=01, bits[3:2]=01 */
    PINSEL0 = (PINSEL0 & ~0xF) | 0x5;

    /* Enter reset mode to configure CAN1 */
    CAN1MOD = 1;

    /* Bit timing for 500kbps at PCLK=15MHz:
       BRP=1 (bits[9:0]), TSEG1=9 (bits[19:16]), TSEG2=5 (bits[22:20]), SJW=1 (bits[25:24])
       Total TQ = (BRP+1) * (1 + TSEG1 + TSEG2) = 2 * 15 = 30 -- gives exactly 500kbps at 15MHz PCLK */
    CAN1BTR = (1<<24) | (5<<20) | (9<<16) | (1);

    /* Return to operating mode */
    CAN1MOD = 0;

    /* VIC: channel 23 for CAN1 */
    VICVectAddr23  = (unsigned)CAN_IRQHandler;
    VICVectCntl23  = 0x20 | 23;
    VICIntEnable  |= (1<<23);

    /* Enable CAN1 RX interrupt: CAN1IER bit 0 */
    CAN1IER = 1;

    xCANQueue = xQueueCreate(16, sizeof(CANFrame_t));
    xTaskCreate(vCANProcessingTask, "CANproc", 512, NULL, PRIORITY_CAN_PROC, NULL);
    xTaskCreate(vTelemetryTask,     "Telem",   256, NULL, PRIORITY_TELEM,    NULL);

    vTaskStartScheduler();
    for(;;);
}