#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* ── Queue: Acquisition -> Processing (uint16_t ADC samples, depth=32) */
static QueueHandle_t xADCQueue;

/* ── Task Priorities (Rate Monotonic: shorter period = higher priority) */
#define PRIORITY_ACQ    3   /* 50Hz (20ms) — highest */
#define PRIORITY_PROC   2   /* Event-driven on queue */
#define PRIORITY_OUTPUT 1   /* Lowest: UART/display */

/* ── vAcquisitionTask: reads AD0.1 at 50Hz */
static void vAcquisitionTask(void *pv)
{
    uint16_t raw;
    for (;;)
    {
        /* Start ADC: Channel 1 (bit 1), CLKDIV=13 (15MHz/14 ~= 1MHz), PDN=1 (bit 21) */
        AD0CR = (1<<1) | (13<<8) | (1<<21);
        AD0CR |= (1<<24);                    /* START=001: start now */
        while (!(AD0DR1 & (1<<31)));         /* Wait DONE bit (bit 31) */
        raw = (AD0DR1 >> 6) & 0x3FF;        /* Extract 10-bit result */

        xQueueSend(xADCQueue, &raw, 0);     /* Non-blocking send */
        vTaskDelay(pdMS_TO_TICKS(20));      /* 50Hz sampling period */
    }
}

/* ── vProcessingTask: 16-sample moving average filter */
static void vProcessingTask(void *pv)
{
    uint16_t samples[16] = {0};
    uint32_t sum = 0;
    uint8_t  idx = 0;
    uint16_t raw, avg;

    for (;;)
    {
        if (xQueueReceive(xADCQueue, &raw, portMAX_DELAY) == pdTRUE)
        {
            /* Sliding window: add new, remove oldest */
            sum += raw;
            sum -= samples[idx];
            samples[idx] = raw;
            idx = (idx + 1) & 0x0F;   /* Wrap at 16 (power of 2) */
            avg = (uint16_t)(sum >> 4); /* Divide by 16 via shift */

            /* Forward filtered result to output queue */
            xQueueSend(xADCQueue, &avg, 0); /* Replace with dedicated output queue in production */
        }
    }
}

/* ── vOutputTask: serializes filtered value to UART0 */
static void vOutputTask(void *pv)
{
    uint16_t filtered;
    for (;;)
    {
        if (xQueueReceive(xADCQueue, &filtered, portMAX_DELAY) == pdTRUE)
        {
            /* Transmit via U0THR. Convert to voltage: V = (filtered * 3300) / 1024 mV */
        }
    }
}

int main(void)
{
    /* Configure P0.28 as AD0.1: PINSEL1 bits [25:24] = 01 */
    PINSEL1 = (PINSEL1 & ~(3<<24)) | (1<<24);

    xADCQueue = xQueueCreate(32, sizeof(uint16_t));

    xTaskCreate(vAcquisitionTask, "ADCacq",  256, NULL, PRIORITY_ACQ,    NULL);
    xTaskCreate(vProcessingTask,  "ADCproc", 512, NULL, PRIORITY_PROC,   NULL);
    xTaskCreate(vOutputTask,      "Output",  256, NULL, PRIORITY_OUTPUT, NULL);

    vTaskStartScheduler();
    for(;;);
}