#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

// ChatGPT typical code:
// Uses generic CAN library that doesn't exist on LPC2148
#include <CAN.h> // Arduino MCP2515 library — architecture mismatch!

QueueHandle_t canQueue;

void vCANReadTask(void *pvParameters)
{
    for(;;)
    {
        // Arduino CAN library API — doesn't compile on LPC2148
        if (CAN.parsePacket()) {
            int id = CAN.packetId();
            uint8_t data[8];
            int len = CAN.read(data, 8); // Hallucinated API

            xQueueSend(canQueue, &data, portMAX_DELAY); // Blocking in fast-poll loop
        }
        vTaskDelay(1); // 1ms polling — excessive CPU usage
    }
}

void vTelemetryTask(void *pvParameters)
{
    uint8_t data[8];
    for(;;)
    {
        xQueueReceive(canQueue, &data, portMAX_DELAY);
        // Send via UART — no formatting or protocol
        Serial.println("CAN data received"); // Arduino Serial API!
    }
}

int main(void)
{
    CAN.begin(500000); // Arduino CAN init
    canQueue = xQueueCreate(5, 8); // Too shallow for CAN bus traffic
    xTaskCreate(vCANReadTask, "CAN", 128, NULL, 1, NULL);
    xTaskCreate(vTelemetryTask, "Telem", 128, NULL, 1, NULL); // Same priority — no RMS
    vTaskStartScheduler();
}