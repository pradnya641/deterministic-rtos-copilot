#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

// ChatGPT typical code:
SemaphoreHandle_t xMotorMutex;
int motorSpeed = 0; // Global, unprotected outside mutex scope

void vControlTask(void *pvParameters)
{
    for(;;)
    {
        xSemaphoreTake(xMotorMutex, portMAX_DELAY);
        motorSpeed = 100;
        analogWrite(3, motorSpeed); // Arduino API on LPC2148!
        xSemaphoreGive(xMotorMutex);
        vTaskDelay(50);
    }
}

void vSafetyTask(void *pvParameters)
{
    for(;;)
    {
        // UNSAFE: Reads motorSpeed WITHOUT taking mutex — race condition!
        if(motorSpeed > 80) {
            xSemaphoreTake(xMotorMutex, portMAX_DELAY);
            motorSpeed = 0;
            analogWrite(3, 0); // Arduino API
            xSemaphoreGive(xMotorMutex);
        }
        vTaskDelay(10);
    }
}

void MOTOR_IRQHandler(void)
{
    // CRITICAL BUG: Taking mutex inside ISR!
    xSemaphoreTake(xMotorMutex, portMAX_DELAY); // BLOCKS IN ISR!
    motorSpeed = 0; // Emergency stop
    analogWrite(3, 0);
    xSemaphoreGive(xMotorMutex);
    // Missing VICVectAddr = 0
}

int main(void)
{
    xMotorMutex = xSemaphoreCreateMutex();
    xTaskCreate(vControlTask, "Control", 100, NULL, 1, NULL);
    xTaskCreate(vSafetyTask, "Safety", 100, NULL, 1, NULL); // Same priority!
    vTaskStartScheduler();
}