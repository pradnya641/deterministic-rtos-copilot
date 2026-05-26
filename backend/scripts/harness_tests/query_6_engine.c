#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include <lpc214x.h>

/* Queue / Semaphore handles */
static QueueHandle_t     xSensorQueue;
static SemaphoreHandle_t xDataMutex;

/* Telemetry and Overflow Statistics (Watermark tracking) */
static volatile uint32_t ulOverflowCount = 0;
static volatile UBaseType_t uxMaxQueueOccupancy = 0;

/* Task Prototypes */
static void vAcquisitionTask(void *pvParameters);
static void vProcessingTask(void *pvParameters);
static void vActuationTask(void *pvParameters);

/* Acquisition Task (HIGH priority) */
static void vAcquisitionTask(void *pvParameters)
{
    uint32_t sensor_val;
    TickType_t xPacingDelay = pdMS_TO_TICKS(50); /* Base period 50ms */
    
    for (;;)
    {
        /* Read sensor / peripheral here */
        sensor_val = 0; /* Replace with actual read */

        /* 1. Watermark Tracking and Occupancy Monitoring */
        UBaseType_t uxCurrentWaiting = uxQueueMessagesWaiting(xSensorQueue);
        if (uxCurrentWaiting > uxMaxQueueOccupancy)
        {
            uxMaxQueueOccupancy = uxCurrentWaiting;
        }

        /* 2. Producer Throttling & Adaptive Pacing */
        if (uxCurrentWaiting >= 8) /* 80% capacity watermark (Queue depth = 10) */
        {
            /* Throttling policy: double pacing delay to slow down producer */
            xPacingDelay = pdMS_TO_TICKS(100);
        }
        else
        {
            xPacingDelay = pdMS_TO_TICKS(50);
        }

        /* 3. Overwrite Policy: drop oldest element if queue is fully saturated */
        if (uxCurrentWaiting >= 10)
        {
            ulOverflowCount++;
            uint32_t dummy;
            /* Pop oldest message in queue to free one slot */
            xQueueReceive(xSensorQueue, &dummy, 0);
        }

        /* Send to processing queue (non-blocking from task) */
        xQueueSend(xSensorQueue, &sensor_val, 0);

        vTaskDelay(xPacingDelay);
    }
}

/* Processing Task (MEDIUM priority) */
static void vProcessingTask(void *pvParameters)
{
    uint32_t data;
    for (;;)
    {
        if (xQueueReceive(xSensorQueue, &data, portMAX_DELAY) == pdTRUE)
        {
            xSemaphoreTake(xDataMutex, portMAX_DELAY);
            /* Process data here */
            xSemaphoreGive(xDataMutex);
        }
    }
}

/* Actuation Task (LOW priority) */
static void vActuationTask(void *pvParameters)
{
    for (;;)
    {
        xSemaphoreTake(xDataMutex, portMAX_DELAY);
        /* Apply actuation here */
        xSemaphoreGive(xDataMutex);

        /* Telemetry logging: transmit statistics periodically */
        /* Sized variables are protected via task-level mutex when logging in production */
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* Main Entry */
int main(void)
{
    xSensorQueue = xQueueCreate(10, sizeof(uint32_t));
    xDataMutex   = xSemaphoreCreateMutex();

    xTaskCreate(vAcquisitionTask, "Acquire", 512, NULL, 3, NULL);
    xTaskCreate(vProcessingTask,  "Process", 512, NULL, 2, NULL);
    xTaskCreate(vActuationTask,   "Actuate", 256, NULL, 1, NULL);

    vTaskStartScheduler(); /* Never returns */
    for (;;);
}