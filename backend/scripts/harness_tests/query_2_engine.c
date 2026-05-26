#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct { float lat; float lon; uint32_t time; } GPSData_t;

static QueueHandle_t xGPSQueue;

/* vGPSTask: Parsers NMEA sentences from UART1 */
static void vGPSTask(void *pv)
{
    GPSData_t data;
    for (;;)
    {
        /* In production, this would wait for a 'line ready' semaphore from UART1 ISR */
        /* For now, simulate periodic GPS update */
        data.lat = 12.9716f; data.lon = 77.5946f;
        xQueueSend(xGPSQueue, &data, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(1000)); /* 1 Hz GPS update */
    }
}

/* vGSMTask: Sends data to server via UART0/AT commands */
static void vGSMTask(void *pv)
{
    GPSData_t data;
    for (;;)
    {
        if (xQueueReceive(xGPSQueue, &data, portMAX_DELAY) == pdTRUE)
        {
            /* AT+CIPSEND logic here */
        }
    }
}

int main(void)
{
    xGPSQueue = xQueueCreate(5, sizeof(GPSData_t));
    xTaskCreate(vGPSTask, "GPS", 512, NULL, 2, NULL);
    xTaskCreate(vGSMTask, "GSM", 512, NULL, 1, NULL);
    vTaskStartScheduler();
}