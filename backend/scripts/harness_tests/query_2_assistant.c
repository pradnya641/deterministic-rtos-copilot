#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

// ChatGPT typical code:
QueueHandle_t gpsQueue;

void vGPSTask(void *pvParameters)
{
    float lat, lon;
    for(;;)
    {
        // Arduino-like abstraction or generic polling loop
        lat = readGPSLatitude(); // Hallucinated helper
        lon = readGPSLongitude();
        
        xQueueSend(gpsQueue, &lat, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(100)); // Polling way too fast for 1Hz GPS
    }
}

void vGSMTask(void *pvParameters)
{
    float data;
    for(;;)
    {
        // Unsafe queue access without timeout check
        xQueueReceive(gpsQueue, &data, portMAX_DELAY);
        
        sendGSM("AT+CIPSEND", data); // Generic/Hallucinated AT logic
        vTaskDelay(pdMS_TO_TICKS(5000)); // Long blocking delay disrupts timing
    }
}

int main(void)
{
    gpsQueue = xQueueCreate(1, sizeof(float)); // Queue too shallow, will overflow
    
    xTaskCreate(vGPSTask, "GPS", 128, NULL, 1, NULL); // Sized in bytes or words? Sizing is arbitary
    xTaskCreate(vGSMTask, "GSM", 128, NULL, 2, NULL); // GSM task has higher priority than GPS (incorrect RMS)
    vTaskStartScheduler();
}