#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

// ChatGPT typical code:
SemaphoreHandle_t xMotorMutex;

void vSensorTask(void *pvParameters)
{
    for(;;)
    {
        // analogRead or Arduino trigger
        digitalWrite(10, HIGH); // Arduino API mismatch
        delayMicroseconds(10);
        digitalWrite(10, LOW);
        long duration = pulseIn(9, HIGH); // Non-deterministic blocking call inside task!
        
        xSemaphoreTake(xMotorMutex, portMAX_DELAY);
        // Direct motor control inside sensor task (violates concern separation)
        if(duration < 1000) {
             analogWrite(5, 0); // stop
        } else {
             analogWrite(5, 255);
        }
        xSemaphoreGive(xMotorMutex);
        vTaskDelay(50);
    }
}

int main(void)
{
    xMotorMutex = xSemaphoreCreateMutex();
    xTaskCreate(vSensorTask, "Sensor", 100, NULL, 1, NULL);
    vTaskStartScheduler();
}