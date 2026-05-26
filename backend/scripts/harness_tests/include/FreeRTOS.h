#ifndef FREERTOS_H
#define FREERTOS_H
#include <stdint.h>
#include <stddef.h>
typedef long BaseType_t;
typedef unsigned long UBaseType_t;
typedef unsigned long TickType_t;
#define pdTRUE (1)
#define pdFALSE (0)
#define pdPASS (1)
#define pdFAIL (0)
#define portMAX_DELAY ((TickType_t)0xffffffffUL)
#define portTICK_PERIOD_MS (10)
#define pdMS_TO_TICKS(x) ((TickType_t)(x))
#define portYIELD_FROM_ISR(x) do { (void)(x); } while(0)
#endif
