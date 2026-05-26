#ifndef COOS_QUEUE_H
#define COOS_QUEUE_H
#include "FreeRTOS.h"
typedef void * QueueHandle_t;
QueueHandle_t xQueueCreate(UBaseType_t uxQueueLength, UBaseType_t uxItemSize);
BaseType_t xQueueSend(QueueHandle_t xQueue, const void * pvItemToQueue, TickType_t xTicksToWait);
BaseType_t xQueueSendFromISR(QueueHandle_t xQueue, const void * pvItemToQueue, BaseType_t * const pxHigherPriorityTaskWoken);
BaseType_t xQueueReceive(QueueHandle_t xQueue, void * const pvBuffer, TickType_t xTicksToWait);
UBaseType_t uxQueueMessagesWaiting(QueueHandle_t xQueue);
UBaseType_t uxQueueMessagesWaitingFromISR(QueueHandle_t xQueue);
#endif
