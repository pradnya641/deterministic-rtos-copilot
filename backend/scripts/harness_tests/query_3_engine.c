#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct {
    float accel_x, accel_y, accel_z;   /* MPU6050 accelerometer (g) */
    float gyro_x,  gyro_y,  gyro_z;    /* MPU6050 gyroscope (deg/s) */
    uint32_t timestamp_ms;
} IMUData_t;

typedef struct {
    float latitude, longitude;
    uint8_t fix_quality;                /* 0=invalid, 1=GPS fix, 2=DGPS */
    uint32_t timestamp_ms;
} GPSData_t;

typedef struct {
    IMUData_t imu;
    GPSData_t gps;
    float heading_deg;                  /* Fused heading estimate */
} FusedPose_t;

static QueueHandle_t xIMUQueue;   /* IMU task -> Fusion task   (depth=10) */
static QueueHandle_t xGPSQueue;   /* GPS task -> Fusion task   (depth=5)  */
static QueueHandle_t xPoseQueue;  /* Fusion  -> Telemetry task (depth=5)  */

#define PRIORITY_IMU       4  /* Highest: 100Hz sample rate */
#define PRIORITY_GPS       3  /* 10Hz NMEA parse */
#define PRIORITY_FUSION    2  /* Fuses data, event-driven */
#define PRIORITY_TELEMETRY 1  /* Lowest: UART output */

/* IMU Task: reads MPU6050 via I2C at 100Hz */
static void vIMUTask(void *pv)
{
    IMUData_t data;
    for (;;)
    {
        /* Write 0x3B to MPU6050 I2C (0x68), read 14 bytes (ACCEL+TEMP+GYRO) */
        /* Parse: data.accel_x = (int16_t)((raw_H << 8) | raw_L) / 16384.0f */
        data.timestamp_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
        xQueueSend(xIMUQueue, &data, 0);
        vTaskDelay(pdMS_TO_TICKS(10));  /* 100Hz */
    }
}

/* GPS Task: receives NMEA from UART0, parses at 10Hz */
static void vGPSTask(void *pv)
{
    GPSData_t gps;
    char nmea_buf[128];
    for (;;)
    {
        /* Read $GPGGA sentence from UART0, extract lat/lon */
        gps.timestamp_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
        xQueueSend(xGPSQueue, &gps, 0);
        vTaskDelay(pdMS_TO_TICKS(100));  /* 10Hz */
    }
}

/* Fusion Task: complementary filter on IMU + GPS */
static void vFusionTask(void *pv)
{
    IMUData_t imu;  GPSData_t gps;  FusedPose_t pose;
    for (;;)
    {
        xQueueReceive(xIMUQueue, &imu, portMAX_DELAY);
        /* Non-blocking GPS read ? use last known if unavailable */
        xQueueReceive(xGPSQueue, &gps, 0);
        pose.imu = imu;  pose.gps = gps;
        /* Complementary filter: heading = 0.98*gyro_integral + 0.02*GPS_bearing */
        pose.heading_deg = 0.0f;   /* Insert filter logic here */
        xQueueSend(xPoseQueue, &pose, 0);
    }
}

/* Telemetry Task: serializes FusedPose to UART1 (GSM module) */
static void vTelemetryTask(void *pv)
{
    FusedPose_t pose;
    for (;;)
    {
        if (xQueueReceive(xPoseQueue, &pose, portMAX_DELAY) == pdTRUE)
        {
            /* Format and send via U1THR (UART1 = GSM) */
        }
    }
}

int main(void)
{
    xIMUQueue   = xQueueCreate(10, sizeof(IMUData_t));
    xGPSQueue   = xQueueCreate(5,  sizeof(GPSData_t));
    xPoseQueue  = xQueueCreate(5,  sizeof(FusedPose_t));

    xTaskCreate(vIMUTask,       "IMU",       512, NULL, PRIORITY_IMU,       NULL);
    xTaskCreate(vGPSTask,       "GPS",       512, NULL, PRIORITY_GPS,       NULL);
    xTaskCreate(vFusionTask,    "Fusion",    768, NULL, PRIORITY_FUSION,    NULL);
    xTaskCreate(vTelemetryTask, "Telemetry", 256, NULL, PRIORITY_TELEMETRY, NULL);

    vTaskStartScheduler();
    for(;;);
}