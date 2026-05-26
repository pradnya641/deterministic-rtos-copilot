#include "FreeRTOS.h"
#include "task.h"
#include <SPI.h> // Arduino SPI library mismatch!

// ChatGPT typical code:
void vSensorTask(void *pvParameters)
{
    SPI.begin(); // Arduino SPI API on LPC2148!
    SPI.setClockDivider(SPI_CLOCK_DIV16); // AVR constant

    for(;;)
    {
        digitalWrite(SS, LOW); // Arduino GPIO API
        uint8_t data = SPI.transfer(0x00); // Blocking SPI transfer — no DMA!
        digitalWrite(SS, HIGH);

        // Claims to use DMA but actually does blocking SPI.transfer()
        // No DMA channel configuration
        // No DMA completion interrupt
        // No FreeRTOS synchronization with DMA

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

int main(void)
{
    xTaskCreate(vSensorTask, "Sensor", 128, NULL, 1, NULL);
    vTaskStartScheduler();
}