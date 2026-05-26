#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

// ChatGPT typical code:
QueueHandle_t xDataQueue;

void vProducerTask(void *pvParameters)
{
    int data = 0;
    for(;;)
    {
        // UNSAFE: Blocking send with portMAX_DELAY — producer hangs if queue is full!
        xQueueSend(xDataQueue, &data, portMAX_DELAY);
        data++;
        vTaskDelay(10);
    }
}

void vConsumerTask(void *pvParameters)
{
    int data;
    for(;;)
    {
        xQueueReceive(xDataQueue, &data, portMAX_DELAY);
        // Process data
        vTaskDelay(50); // Consumer is 5x slower than producer — guaranteed overflow!
    }
}

int main(void)
{
    // Queue depth of 5 with 5:1 producer/consumer rate mismatch — will overflow immediately
    xDataQueue = xQueueCreate(5, sizeof(int));

    xTaskCreate(vProducerTask, "Producer", 100, NULL, 2, NULL); // Stack too small
    xTaskCreate(vConsumerTask, "Consumer", 100, NULL, 1, NULL);
    vTaskStartScheduler();
    for(;;);
}