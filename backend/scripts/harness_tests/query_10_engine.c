#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include <lpc214x.h>

typedef struct { uint32_t distance_cm; } ObstacleData_t;
typedef struct { int8_t left_speed;  int8_t right_speed; } MotorCommand_t;

static QueueHandle_t  xObstacleQueue;   /* Sensor -> Navigation */
static QueueHandle_t  xMotorQueue;      /* Navigation -> Motor */
static SemaphoreHandle_t xMotorMutex;   /* Protects shared motor registers at task level */

#define PRIORITY_SENSOR  4
#define PRIORITY_NAV     3
#define PRIORITY_MOTOR   2
#define PRIORITY_STATUS  1

static void vSensorTask(void *pv)
{
    ObstacleData_t obs;
    for(;;) {
        obs.distance_cm = 100;  /* Replace: HC-SR04 Timer capture */
        xQueueSend(xObstacleQueue, &obs, 0);
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

static void vNavigationTask(void *pv)
{
    ObstacleData_t obs;  MotorCommand_t cmd;
    for(;;) {
        xQueueReceive(xObstacleQueue, &obs, portMAX_DELAY);
        if (obs.distance_cm < 30) {
            cmd.left_speed = -50;  cmd.right_speed = 50;  /* Turn */
        } else {
            cmd.left_speed =  80;  cmd.right_speed = 80;  /* Forward */
        }
        xQueueSend(xMotorQueue, &cmd, 0);
    }
}

static void vMotorTask(void *pv)
{
    MotorCommand_t cmd;
    for(;;) {
        xQueueReceive(xMotorQueue, &cmd, portMAX_DELAY);
        xSemaphoreTake(xMotorMutex, portMAX_DELAY);
        /* Set PWM1 (left) and PWM2 (right) duty cycles */
        PWMMR1 = (cmd.left_speed  * PWMMR0) / 100;
        PWMMR2 = (cmd.right_speed * PWMMR0) / 100;
        PWMLER = (1<<1)|(1<<2);   /* Latch enable */
        xSemaphoreGive(xMotorMutex);
    }
}

int main(void)
{
    xObstacleQueue = xQueueCreate(10, sizeof(ObstacleData_t));
    xMotorQueue    = xQueueCreate(5,  sizeof(MotorCommand_t));
    xMotorMutex    = xSemaphoreCreateMutex();

    xTaskCreate(vSensorTask,     "Sensor", 256, NULL, PRIORITY_SENSOR, NULL);
    xTaskCreate(vNavigationTask, "Nav",    512, NULL, PRIORITY_NAV,    NULL);
    xTaskCreate(vMotorTask,      "Motor",  256, NULL, PRIORITY_MOTOR,  NULL);
    vTaskStartScheduler();
    for(;;);
}