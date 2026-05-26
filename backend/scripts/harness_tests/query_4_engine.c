#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct {
    uint32_t distance_cm;
    uint32_t timestamp_ms;
} SensorReading_t;

static QueueHandle_t xSensorQueue;   /* Sensor -> Navigation (depth=5) */

#define PRIORITY_SENSOR  3   /* Highest: 20ms HC-SR04 cycle */
#define PRIORITY_NAV     2
#define PRIORITY_MOTOR   1

/* ── vSensorTask: HC-SR04 on P0.10 (TRIG) and P0.9 (ECHO) */
static void vSensorTask(void *pv)
{
    SensorReading_t reading;
    for (;;)
    {
        /* Assert TRIG HIGH on P0.10 for 10us */
        IO0SET = (1<<10);
        volatile int d = 0; while(d++ < 150);   /* ~10us busy-wait @ 15MHz */
        IO0CLR = (1<<10);

        /* Measure ECHO on P0.9 (use Timer1 CAP1.0 in production) */
        uint32_t start = 0, end = 0;
        while (!(IO0PIN & (1<<9)));              /* Wait ECHO HIGH */
        start = T1TC;                           /* Capture start tick */
        while  (IO0PIN & (1<<9));               /* Wait ECHO LOW  */
        end   = T1TC;                           /* Capture end tick */

        /* distance_cm = echo_ticks / (2 * PCLK / 34000) */
        reading.distance_cm  = (end - start) / 882;  /* At PCLK=15MHz: 15e6/34000/2 ~= 220 ticks/cm -- adjust */
        reading.timestamp_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

        xQueueSend(xSensorQueue, &reading, 0);
        vTaskDelay(pdMS_TO_TICKS(60));           /* 60ms minimum HC-SR04 cycle */
    }
}

/* ── vNavigationTask: obstacle avoidance logic */
static void vNavigationTask(void *pv)
{
    SensorReading_t reading;
    for (;;)
    {
        if (xQueueReceive(xSensorQueue, &reading, portMAX_DELAY) == pdTRUE)
        {
            if (reading.distance_cm < 30)
            {
                /* Obstacle: sharp right turn — left full, right reverse */
                PWMMR1 = 200;   /* Left motor slow */
                PWMMR2 = 800;   /* Right motor fast */
            }
            else
            {
                /* Clear path: go forward */
                PWMMR1 = 700;
                PWMMR2 = 700;
            }
            PWMLER = (1<<0) | (1<<1) | (1<<2);  /* Latch new duty cycles */
        }
    }
}

/* ── vMotorTask: applies latched PWM duty cycles */
static void vMotorTask(void *pv)
{
    for (;;)
    {
        /* PWM registers already written by vNavigationTask via PWMMR1/2 + PWMLER */
        /* This task handles periodic health checks or emergency stop logic */
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

int main(void)
{
    /* GPIO: P0.10 TRIG=output, P0.9 ECHO=input */
    IO0DIR |= (1<<10);          /* TRIG output */
    IO0DIR &= ~(1<<9);          /* ECHO input  */

    /* PWM pin config: P0.0=PWM1 (bits[1:0]=10), P0.7=PWM2 (bits[15:14]=10) */
    PINSEL0 = (PINSEL0 & ~(3<<0))  | (2<<0);    /* P0.0 -> PWM1 */
    PINSEL0 = (PINSEL0 & ~(3<<14)) | (2<<14);   /* P0.7 -> PWM2 */

    /* PWM setup: period=1000, reset on MR0 match, enable CH1+CH2 outputs */
    PWMMR0 = 1000;              /* Period ticks (100% = 1000) */
    PWMMR1 = 700;               /* Left motor initial duty */
    PWMMR2 = 700;               /* Right motor initial duty */
    PWMMCR = (1<<1);            /* Reset TC on MR0 match */
    PWMPCR = (1<<9) | (1<<10);  /* Enable PWM1 and PWM2 outputs */
    PWMLER = (1<<0) | (1<<1) | (1<<2); /* Latch MR0, MR1, MR2 */
    PWMTCR = (1<<0) | (1<<3);  /* Counter enable + PWM enable */

    /* Timer1: free-running at PCLK for ECHO timing */
    T1TCR = 1;                  /* Enable Timer1 */

    xSensorQueue = xQueueCreate(5, sizeof(SensorReading_t));
    xTaskCreate(vSensorTask,     "Sensor", 256, NULL, PRIORITY_SENSOR, NULL);
    xTaskCreate(vNavigationTask, "Nav",    512, NULL, PRIORITY_NAV,    NULL);
    xTaskCreate(vMotorTask,      "Motor",  256, NULL, PRIORITY_MOTOR,  NULL);

    vTaskStartScheduler();
    for(;;);
}