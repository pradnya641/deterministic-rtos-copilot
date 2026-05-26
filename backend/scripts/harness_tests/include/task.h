#ifndef COOS_TASK_H
#define COOS_TASK_H
#include "FreeRTOS.h"
typedef void (*TaskFunction_t)(void *);
BaseType_t xTaskCreate(TaskFunction_t pvTaskCode, const char * const pcName, unsigned short usStackDepth, void *pvParameters, UBaseType_t uxPriority, void **pxCreatedTask);
void vTaskStartScheduler(void);
void vTaskDelay(const TickType_t xTicksToDelay);
TickType_t xTaskGetTickCount(void);
#endif
