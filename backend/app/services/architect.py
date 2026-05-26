"""
Architecture Generator — produces full embedded system blueprints.

Triggered when intent = "system_architecture" OR when the user explicitly
requests a full system design (e.g. "design obstacle detection system").

Output is a structured ArchitectureBlueprint that contains:
  - functional objective
  - hardware components
  - RTOS task graph
  - queue / semaphore flow
  - timing constraints
  - code skeleton (FreeRTOS C)
  - explainability notes (WHY each decision was made)
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict

# ==================================================================================================================─
# DATA STRUCTURES
# ==================================================================================================================─

@dataclass
class RTOSTask:
    name:      str
    function:  str
    priority:  int
    period_ms: int
    stack:     int
    role:      str
    rationale: str          # WHY this priority / period was chosen


@dataclass
class QueueDef:
    name:      str
    length:    int
    item_size: str
    from_task: str
    to_task:   str
    rationale: str


@dataclass
class ArchitectureBlueprint:
    system_name:     str
    objective:       str
    hardware:        List[str]
    protocols:       List[str]
    tasks:           List[RTOSTask]
    queues:          List[QueueDef]
    isr_notes:       List[str]
    timing_budget:   Dict[str, str]
    safety_rules:    List[str]
    code_skeleton:   str
    explainability:  Dict[str, str]   # decision -> rationale


# ==================================================================================================================─
# KNOWN SYSTEM TEMPLATES
# ==================================================================================================================─

def _obstacle_detection() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* === Shared Data Structures ============================================================ */
typedef struct { uint32_t distance_cm; uint32_t timestamp_ms; } SensorReading_t;
typedef struct { uint8_t  alert_level; uint32_t distance_cm;  } AlertCommand_t;

/* === Queue & Semaphore Handles ======================================================─ */
static QueueHandle_t xSensorQueue;   /* HC-SR04 -> Processing  (depth=5) */
static QueueHandle_t xAlertQueue;    /* Processing -> Actuation (depth=3) */

/* === Task Priorities (higher = more urgent) ==================================== */
#define PRIORITY_SENSOR    3   /* Must meet 60ms HC-SR04 cycle */
#define PRIORITY_PROCESS   2
#define PRIORITY_ACTUATE   1

/* === vSensorTask: reads HC-SR04 every 60ms ====================================─ */
static void vSensorTask(void *pv)
{
    SensorReading_t reading;
    for (;;)
    {
        /* Assert TRIG HIGH for 10us */
        IO0SET = (1 << 10);
        /* Delay 10us via busy-wait (timer preferred in production) */
        volatile int d = 0; while(d++ < 150);
        IO0CLR = (1 << 10);

        /* Measure ECHO pulse width (simplified - use Timer capture in production) */
        reading.distance_cm = 100; /* Replace with actual capture */
        reading.timestamp_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

        xQueueSend(xSensorQueue, &reading, 0);   /* non-blocking send */
        vTaskDelay(pdMS_TO_TICKS(60));            /* 60ms cycle */
    }
}

/* === vProcessingTask: classifies distance, issues alerts ===============─ */
static void vProcessingTask(void *pv)
{
    SensorReading_t reading;
    AlertCommand_t  alert;
    for (;;)
    {
        if (xQueueReceive(xSensorQueue, &reading, portMAX_DELAY) == pdTRUE)
        {
            if      (reading.distance_cm < 20)  alert.alert_level = 3; /* CRITICAL */
            else if (reading.distance_cm < 50)  alert.alert_level = 2; /* WARNING  */
            else if (reading.distance_cm < 100) alert.alert_level = 1; /* CAUTION  */
            else                                alert.alert_level = 0; /* CLEAR    */

            alert.distance_cm = reading.distance_cm;
            xQueueSend(xAlertQueue, &alert, 0);
        }
    }
}

/* === vActuationTask: drives buzzer / LED based on alert level =========─ */
static void vActuationTask(void *pv)
{
    AlertCommand_t alert;
    for (;;)
    {
        if (xQueueReceive(xAlertQueue, &alert, portMAX_DELAY) == pdTRUE)
        {
            if (alert.alert_level >= 2) IO0SET = (1 << 11); /* Buzzer ON  */
            else                        IO0CLR = (1 << 11); /* Buzzer OFF */
        }
    }
}

int main(void)
{
    /* GPIO setup */
    IO0DIR |= (1 << 10); /* TRIG = output */
    IO0DIR &= ~(1 << 9); /* ECHO = input  */
    IO0DIR |= (1 << 11); /* BUZZER = output */

    xSensorQueue = xQueueCreate(5, sizeof(SensorReading_t));
    xAlertQueue  = xQueueCreate(3, sizeof(AlertCommand_t));

    xTaskCreate(vSensorTask,     "Sensor",  256, NULL, PRIORITY_SENSOR,  NULL);
    xTaskCreate(vProcessingTask, "Process", 512, NULL, PRIORITY_PROCESS, NULL);
    xTaskCreate(vActuationTask,  "Actuate", 256, NULL, PRIORITY_ACTUATE, NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="Obstacle Detection System (FreeRTOS + LPC2148 + HC-SR04)",
        objective="Continuously measure distance using HC-SR04 ultrasonic sensor, classify proximity zones, and trigger actuation (buzzer/LED) in real time.",
        hardware=["LPC2148 ARM7 MCU", "HC-SR04 Ultrasonic Sensor", "Active Buzzer", "LED indicators", "5V -> 3.3V level shifter (ECHO pin)"],
        protocols=["GPIO (TRIG/ECHO)", "Timer0 capture (ECHO timing)", "GPIO (buzzer/LED output)"],
        tasks=[
            RTOSTask("vSensorTask",     "vSensorTask",     3, 60,  256, "Acquisition",
                     "Priority 3 (highest): HC-SR04 needs a strict 60ms cycle. Missing it causes echo overlap and wrong readings."),
            RTOSTask("vProcessingTask", "vProcessingTask", 2, 0,   512, "Processing",
                     "Priority 2: event-driven (blocks on queue), no fixed period. Stack 512 for classification logic."),
            RTOSTask("vActuationTask",  "vActuationTask",  1, 0,   256, "Actuation",
                     "Priority 1 (lowest): safe to delay actuation by one tick. Never blocks sensor acquisition."),
        ],
        queues=[
            QueueDef("xSensorQueue", 5, "SensorReading_t", "vSensorTask",     "vProcessingTask",
                     "Depth 5: buffers up to 5 unprocessed readings before dropping. Prevents sensor task blocking."),
            QueueDef("xAlertQueue",  3, "AlertCommand_t",  "vProcessingTask", "vActuationTask",
                     "Depth 3: actuation is fast (GPIO), so shallow queue avoids stale alerts."),
        ],
        isr_notes=[
            "HC-SR04 ECHO should ideally use Timer0 CAP0.0 interrupt to measure pulse width precisely.",
            "If Timer capture ISR is used: call xQueueSendFromISR() + portYIELD_FROM_ISR().",
            "VIC must be cleared at end of ISR on LPC2148 (ARM7 non-vectored behavior).",
        ],
        timing_budget={
            "Sensor cycle":       "60 ms (HC-SR04 minimum safe period)",
            "Processing latency": "< 5 ms (simple threshold check)",
            "Actuation latency":  "< 10 ms from alert command",
            "Total system deadline": "< 75 ms from measurement to actuation",
        },
        safety_rules=[
            "NEVER drive actuation directly from sensor task (violates separation of concerns).",
            "If xSensorQueue is full, DROP the reading (non-blocking send) - do not block sensor task.",
            "ECHO pin is 5V - use voltage divider or level shifter before LPC2148 GPIO.",
            "Always check pdPASS on xTaskCreate - failure means heap is exhausted.",
        ],
        code_skeleton=code,
        explainability={
            "Why queue instead of global variable?": "Queues are ISR-safe and thread-safe. A global variable shared between tasks requires a mutex and risks priority inversion.",
            "Why priority 3 for sensor?":            "HC-SR04 has a strict 60ms cycle. If preempted, the TRIG pulse is delayed, causing measurement errors. Highest priority guarantees on-time execution.",
            "Why no mutex?":                         "Tasks communicate only via queues. No shared memory means no critical section needed, eliminating mutex overhead and priority inversion risk.",
            "Why separate processing from actuation?": "Allows processing logic to evolve independently (e.g. add Kalman filter) without changing actuation code. Clean separation of concerns.",
            "Why Timer capture for ECHO?":           "Busy-waiting for ECHO blocks the sensor task for up to 25ms (4m range / 340m/s). Timer capture is interrupt-driven and frees the CPU.",
        }
    )


def _temperature_logger() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct { uint16_t adc_raw; float temp_c; uint32_t tick; } TempReading_t;

static QueueHandle_t xTempQueue;

static void vTempAcqTask(void *pv)
{
    TempReading_t r;
    for (;;)
    {
        /* Start ADC conversion: Channel 1, PDN=1, START=001 */
        AD0CR = (1<<1)|(13<<8)|(1<<21)|(1<<24);
        while (!(AD0DR1 & (1<<31)));            /* Wait DONE */
        r.adc_raw = (AD0DR1 >> 6) & 0x3FF;     /* 10-bit result */
        r.temp_c  = (r.adc_raw * 3300.0f / 1024.0f) / 10.0f;
        r.tick    = xTaskGetTickCount();
        xQueueSend(xTempQueue, &r, 0);
        vTaskDelay(pdMS_TO_TICKS(500));         /* 2 Hz sampling */
    }
}

static void vTempLogTask(void *pv)
{
    TempReading_t r;
    for (;;)
    {
        if (xQueueReceive(xTempQueue, &r, portMAX_DELAY) == pdTRUE)
        {
            /* Transmit via UART0 */
            /* UARTSend("%d.%d C\\n", (int)r.temp_c, (int)(r.temp_c*10)%10); */
        }
    }
}

int main(void)
{
    /* ADC pin: P0.28 = AD0.1 */
    PINSEL1 = (PINSEL1 & ~(3<<24)) | (1<<24);

    xTempQueue = xQueueCreate(10, sizeof(TempReading_t));
    xTaskCreate(vTempAcqTask, "TempAcq", 256, NULL, 2, NULL);
    xTaskCreate(vTempLogTask, "TempLog", 512, NULL, 1, NULL);
    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="Temperature Logger (FreeRTOS + LPC2148 + LM35)",
        objective="Sample LM35 temperature sensor at 2Hz via ADC, log readings over UART.",
        hardware=["LPC2148 ARM7 MCU", "LM35 Temperature Sensor (AD0.1 / P0.28)", "UART0 terminal"],
        protocols=["ADC (polling, 10-bit)", "UART0 (9600 baud, 8N1)"],
        tasks=[
            RTOSTask("vTempAcqTask", "vTempAcqTask", 2, 500, 256, "Acquisition",
                     "Priority 2: periodic 500ms ADC read. Higher than logging to meet sampling deadline."),
            RTOSTask("vTempLogTask", "vTempLogTask", 1, 0,   512, "Logging",
                     "Priority 1: event-driven UART output. Lower priority acceptable - logging can lag slightly."),
        ],
        queues=[
            QueueDef("xTempQueue", 10, "TempReading_t", "vTempAcqTask", "vTempLogTask",
                     "Depth 10: buffers readings if UART is temporarily busy without losing data."),
        ],
        isr_notes=[
            "UART TX interrupt can be added for non-blocking transmission.",
            "ADC interrupt (DONE bit ISR) can replace polling for lower CPU usage.",
        ],
        timing_budget={
            "ADC conversion time": "~11 us at 4.5MHz ADC clock",
            "Sampling period":     "500 ms (2 Hz)",
            "UART TX time":        "~1 ms per reading at 9600 baud",
        },
        safety_rules=[
            "AD0CR PDN bit must be 1 before starting conversion.",
            "Read AD0DR only after DONE bit (bit 31) is set.",
            "DLAB must be cleared after UART baud rate setup.",
            "LM35 output must not exceed 3.3V (LPC2148 ADC VREF limit).",
        ],
        code_skeleton=code,
        explainability={
            "Why poll DONE bit?":       "LM35 ADC reads are simple and infrequent (2Hz). Polling is acceptable. For high-speed ADC, use interrupt.",
            "Why queue depth 10?":      "If UART is busy for up to 5 seconds, 10 readings (at 500ms each) are buffered without data loss.",
            "Why separate tasks?":      "Acquisition and logging have different timing requirements. Separating them allows each to be tuned independently.",
        }
    )


def _telematics_tracking() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct { float lat; float lon; uint32_t time; } GPSData_t;

static QueueHandle_t xGPSQueue;

/* vGPSTask: Parsers NMEA sentences from UART1 */
static void vGPSTask(void *pv)
{
    GPSData_t data;
    for (;;)
    {
        /* In production, this would wait for a 'line ready' semaphore from UART1 ISR */
        /* For now, simulate periodic GPS update */
        data.lat = 12.9716f; data.lon = 77.5946f;
        xQueueSend(xGPSQueue, &data, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(1000)); /* 1 Hz GPS update */
    }
}

/* vGSMTask: Sends data to server via UART0/AT commands */
static void vGSMTask(void *pv)
{
    GPSData_t data;
    for (;;)
    {
        if (xQueueReceive(xGPSQueue, &data, portMAX_DELAY) == pdTRUE)
        {
            /* AT+CIPSEND logic here */
        }
    }
}

int main(void)
{
    xGPSQueue = xQueueCreate(5, sizeof(GPSData_t));
    xTaskCreate(vGPSTask, "GPS", 512, NULL, 2, NULL);
    xTaskCreate(vGSMTask, "GSM", 512, NULL, 1, NULL);
    vTaskStartScheduler();
}"""

    return ArchitectureBlueprint(
        system_name="Telematics Tracking System (GPS + GSM + LPC2148)",
        objective="Collect GPS coordinates at 1Hz and transmit to remote server via GSM/GPRS module.",
        hardware=["LPC2148", "GPS Module (UART1)", "GSM Module (UART0)", "External Antenna"],
        protocols=["UART1 (9600, NMEA)", "UART0 (115200, AT Commands)"],
        tasks=[
            RTOSTask("vGPSTask", "vGPSTask", 2, 1000, 512, "Acquisition", "1Hz GPS update rate is sufficient for vehicle tracking."),
            RTOSTask("vGSMTask", "vGSMTask", 1, 0, 512, "Communication", "Event-driven: transmits only when new GPS data is available."),
        ],
        queues=[
            QueueDef("xGPSQueue", 5, "GPSData_t", "vGPSTask", "vGSMTask", "Buffers coordinates during GSM handshake/reconnection."),
        ],
        isr_notes=["Use UART1 RX interrupt for NMEA sentence buffering.", "Use UART0 RX interrupt for GSM response (OK/ERROR) parsing."],
        timing_budget={"GPS Parsing": "< 50ms", "GSM TX": "variable (network dependent)"},
        safety_rules=["Implement retry logic for GSM AT commands.", "Buffer data locally if network is lost."],
        code_skeleton=code,
        explainability={"Why UART interrupts?": "GPS sends large bursts of NMEA text; polling would lose characters. Interrupts ensure zero-loss buffering."}
    )

def _smart_parking() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "semphr.h"

static SemaphoreHandle_t xGateMutex;
static uint8_t occupied_slots = 0;

void vSensorTask(void *pv)
{
    for (;;)
    {
        /* Check sensor (HC-SR04) */
        if (xSemaphoreTake(xGateMutex, portMAX_DELAY))
        {
            /* Update occupied_slots logic */
            xSemaphoreGive(xGateMutex);
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}"""

    return ArchitectureBlueprint(
        system_name="Smart Parking System (Ultrasonic + Mutex)",
        objective="Manage parking lot occupancy and drive entry/exit gates.",
        hardware=["LPC2148", "HC-SR04 (xN)", "Servo Motors (Gates)", "I2C Display"],
        protocols=["GPIO", "PWM (Servo Control)", "I2C (Display)"],
        tasks=[
            RTOSTask("vSensorTask", "vSensorTask", 2, 100, 256, "Detection", "Scans parking slots for occupancy."),
            RTOSTask("vGateTask", "vGateTask", 3, 0, 256, "Actuation", "High priority: entry gate must respond instantly to vehicle arrival."),
        ],
        queues=[],
        isr_notes=["Use Timer Capture for ultrasonic pulse width."],
        timing_budget={"Detection latency": "< 200ms", "Gate response": "< 50ms"},
        safety_rules=["Use Mutex to protect 'occupied_slots' global variable.", "Prevent gate closing if IR sensor detects obstruction."],
        code_skeleton=code,
        explainability={"Why Mutex?": "Since multiple sensors might update the global occupancy count, a Mutex prevents race conditions."}
    )


# =============================================================================
# SENSOR FUSION: GPS + MPU6050 (Inertial Navigation / Telematics)
# =============================================================================
def _sensor_fusion_gps_imu() -> ArchitectureBlueprint:
    code = """\
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
        /* Non-blocking GPS read — use last known if unavailable */
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
}"""

    return ArchitectureBlueprint(
        system_name="Sensor Fusion: GPS + MPU6050 Inertial Navigation",
        objective="Fuse IMU (accelerometer + gyroscope) with GPS to produce a continuously updated position and heading estimate, transmitted via GSM.",
        hardware=["LPC2148", "MPU6050 (I2C)", "GPS Module (UART0)", "GSM Module (UART1)"],
        protocols=["I2C (MPU6050 @ 0x68)", "UART0 (GPS NMEA)", "UART1 (GSM telemetry)"],
        tasks=[
            RTOSTask("vIMUTask",       "vIMUTask",       4, 10,  512, "IMU Acquisition",
                     "Priority 4 (highest): Grounded in Rate Monotonic Scheduling (RMS). Shorter period (10ms, 100Hz) demands higher priority to guarantee deterministic sensor sampling and prevent data loss."),
            RTOSTask("vGPSTask",       "vGPSTask",       3, 100, 512, "GPS Parsing",
                     "Priority 3: Grounded in RMS. GPS runs at 10Hz (100ms period), so it is assigned a lower priority than the 100Hz IMU task, preventing unnecessary preemption of fast sensors."),
            RTOSTask("vFusionTask",    "vFusionTask",    2, 0,   768, "Sensor Fusion",
                     "Priority 2: Grounded in RMS. Wakes on IMU queue event, matching processing rate of the primary data stream. Stack 768 words handles complementary filter math."),
            RTOSTask("vTelemetryTask", "vTelemetryTask", 1, 0,   256, "GSM Telemetry",
                     "Priority 1 (lowest): Grounded in RMS. Low frequency telemetry serialization can be safely delayed without affecting real-time loop stability."),
        ],
        queues=[
            QueueDef("xIMUQueue",  10, "IMUData_t",    "vIMUTask",    "vFusionTask",    "Depth 10: Holds up to 100ms of sensor data. Memory overhead: ~80 bytes (control struct) + 10 * 28 bytes (data payload) = ~360 bytes of RAM."),
            QueueDef("xGPSQueue",  5,  "GPSData_t",    "vGPSTask",    "vFusionTask",    "Depth 5: Holds up to 500ms of GPS coordinates. Memory overhead: ~80 bytes + 5 * 12 bytes = ~140 bytes of RAM."),
            QueueDef("xPoseQueue", 5,  "FusedPose_t",  "vFusionTask", "vTelemetryTask", "Depth 5: Fused pose buffer. Memory overhead: ~80 bytes + 5 * 48 bytes = ~320 bytes of RAM."),
        ],
        isr_notes=[
            "Use UART0 RX interrupt for GPS character accumulation. In the ISR, call xQueueSendFromISR() with &xHigherPriorityTaskWoken, then call portYIELD_FROM_ISR(xHigherPriorityTaskWoken) on exit to ensure instant preemptive task scheduling.",
            "Use I2C master completion interrupt for non-blocking MPU6050 reading (avoid busy-wait polling loops inside tasks).",
            "Clear VectAddr = 0 at the end of LPC2148 interrupts to acknowledge VIC.",
        ],
        timing_budget={
            "IMU sample period": "10ms (100Hz)",
            "GPS parse period":  "100ms (10Hz)",
            "Fusion latency":    "<15ms from IMU sample to fused pose",
            "Telemetry period":  "<500ms (GSM burst)",
        },
        safety_rules=[
            "MPU6050 is 3.3V — use level shifter on I2C lines if LPC2148 runs at 5V.",
            "Never call vTaskDelay() in ISR — use FromISR variants only.",
            "Queue overflow in xIMUQueue = sensor data loss — size queue for worst-case burst.",
            "Validate GPS fix_quality > 0 before using lat/lon in fusion.",
        ],
        code_skeleton=code,
        explainability={
            "Why priority 4 for IMU?": "IMU at 100Hz has the tightest timing constraint. Grounded in Rate Monotonic Scheduling (RMS), the task with the highest execution frequency is assigned the highest priority to avoid sample jitter and complementary filter degradation.",
            "Why complementary filter?": "Simple to implement on ARM7, deterministic latency, suitable for real-time systems without an FPU.",
            "Why separate GPS and IMU queues?": "Different rates (10Hz vs 100Hz). Decoupled queues allow Fusion to read both independently without blocking.",
            "Why is Telemetry lowest priority?": "GSM transmission can be delayed without affecting real-time sensing. Safety-critical data must not wait for UART.",
        }
    )


# =============================================================================
# AUTONOMOUS ROBOT: Multi-sensor + Motor Control
# =============================================================================
def _autonomous_robot() -> ArchitectureBlueprint:
    code = """\
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
}"""

    return ArchitectureBlueprint(
        system_name="FreeRTOS Autonomous Robot (Obstacle Avoidance)",
        objective="Navigate autonomously using HC-SR04 obstacle detection, PWM motor control, and a FreeRTOS task pipeline.",
        hardware=["LPC2148", "HC-SR04", "DC Motors (L298N driver)", "PWM outputs"],
        protocols=["GPIO (HC-SR04)", "Timer Capture (ECHO)", "PWM (Motor speed)"],
        tasks=[
            RTOSTask("vSensorTask",     "vSensorTask",     4, 50,  256, "Sensing",
                     "Priority 4 (highest): Grounded in RMS. Sensor cycle of 50ms (20Hz) must be met to ensure timely obstacle detection. Priority is higher than control loops to guarantee fresh inputs."),
            RTOSTask("vNavigationTask", "vNavigationTask", 3, 0,   512, "Navigation",
                     "Priority 3: Grounded in RMS. Event-driven controller that processes obstacle readings. Needs high priority to calculate avoidance paths immediately after sensor updates."),
            RTOSTask("vMotorTask",      "vMotorTask",      2, 0,   256, "Actuation",
                     "Priority 2: Grounded in RMS. Drives hardware registers. Lower than sensor/nav to prevent blocking upstream pipeline logic."),
        ],
        queues=[
            QueueDef("xObstacleQueue", 10, "ObstacleData_t", "vSensorTask",     "vNavigationTask", "Depth 10: Holds up to 500ms of readings. Memory overhead: ~80 bytes + 10 * 4 bytes = ~120 bytes of RAM."),
            QueueDef("xMotorQueue",    5,  "MotorCommand_t", "vNavigationTask", "vMotorTask",      "Depth 5: Holds motor speed updates. Memory overhead: ~80 bytes + 5 * 2 bytes = ~90 bytes of RAM."),
        ],
        isr_notes=[
            "Timer1 Capture ISR measures ECHO pulse width. On completion, the ISR must call xQueueSendFromISR() with &xHigherPriorityTaskWoken, then call portYIELD_FROM_ISR(xHigherPriorityTaskWoken) to trigger immediate preemption of the sensor task if unblocked.",
            "Interrupt handlers (ISRs) must NEVER attempt to acquire or release mutexes as they can block and are not ISR-safe. Safety overrides inside interrupts must use queue-based signaling or task notifications instead.",
        ],
        timing_budget={"Sensor cycle": "50ms", "Nav decision": "<5ms", "Motor update": "<1ms"},
        safety_rules=[
            "Mutex on motor PWM registers is for task-level synchronization only (e.g. between vMotorTask and a secondary diagnostics or manual override task).",
            "PWMMR1 must never exceed PWMMR0 — validate before writing.",
            "HC-SR04 ECHO is 5V — use level shifter to protect LPC2148 GPIO.",
        ],
        code_skeleton=code,
        explainability={
            "Why Mutex for motors?": "Protects the shared motor hardware state / PWM registers from concurrent access by multiple task-level writers (e.g., vMotorTask and a high-priority safety control/override task). FreeRTOS mutexes implement priority inheritance, which temporarily elevates the priority of a lower-priority task holding the mutex when a higher-priority task attempts to acquire it, preventing unbounded priority inversion. Note: Mutexes must never be used in interrupts (ISRs) as they can block and lack priority inheritance support; interrupt-driven emergency overrides must use queue-based serialization or task notifications.",
            "Why queue depth 10 for sensors?": "At 50ms cycle, 10 readings = 500ms buffer — allows Navigation to be temporarily delayed without data loss.",
        }
    )


# =============================================================================
# ISR-TO-TASK PIPELINE: Interrupt-driven UART receive
# =============================================================================
def _isr_to_task_pipeline() -> ArchitectureBlueprint:
    code = r"""#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* ISR-to-task pipeline: UART0 RX ISR -> Processing task */
static QueueHandle_t xRxQueue;   /* UART ISR -> Processing (depth=64) */

#define PRIORITY_PROCESS 3
#define PRIORITY_OUTPUT  1

/* UART0 RX Interrupt Handler */
void UART0_IRQHandler(void) __attribute__((interrupt("IRQ")));
void UART0_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    uint8_t byte = U0RBR;   /* Read received byte — also clears interrupt */

    /* Safe: send byte to task without blocking */
    xQueueSendFromISR(xRxQueue, &byte, &xHigherPriorityTaskWoken);

    /* Acknowledge VIC */
    VICVectAddr = 0;

    /* Yield if a higher-priority task was unblocked */
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

static void vProcessingTask(void *pv)
{
    uint8_t byte;
    char frame[128];  int idx = 0;
    for (;;) {
        xQueueReceive(xRxQueue, &byte, portMAX_DELAY);
        frame[idx++] = byte;
        if (byte == '\n' || idx >= 127) {
            frame[idx] = '\0';
            /* Process complete frame here */
            idx = 0;
        }
    }
}

int main(void)
{
    /* UART0 init: 9600 baud */
    PINSEL0 |= 0x05;        /* P0.0=TXD0, P0.1=RXD0 */
    U0LCR    = 0x83;        /* DLAB=1, 8N1 */
    U0DLL    = 391;         /* 9600 baud @ 60MHz PCLK */
    U0LCR    = 0x03;        /* DLAB=0 */
    U0IER    = 0x01;        /* Enable RX interrupt */

    /* VIC setup for UART0 */
    VICVectAddr6  = (unsigned)UART0_IRQHandler;
    VICVectCntl6  = 0x20 | 6;
    VICIntEnable |= (1 << 6);

    xRxQueue = xQueueCreate(64, sizeof(uint8_t));
    xTaskCreate(vProcessingTask, "Process", 512, NULL, PRIORITY_PROCESS, NULL);
    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="ISR-to-Task Pipeline: UART RX Interrupt-Driven",
        objective="Receive UART bytes via interrupt (zero CPU polling), accumulate into frames in a processing task via FreeRTOS queue.",
        hardware=["LPC2148", "UART0", "Any serial device (GPS/GSM/PC)"],
        protocols=["UART0 (interrupt-driven RX)"],
        tasks=[
            RTOSTask("UART0_IRQHandler", "ISR",               5, 0,  0,   "ISR",
                     "Priority 5 (highest): Hardware interrupt context. Bypasses scheduler priorities entirely. Must be kept extremely short, doing only xQueueSendFromISR and VIC clearing to prevent interrupt starvation."),
            RTOSTask("vProcessingTask",  "vProcessingTask",   3, 0,  512, "Frame Parse",
                     "Priority 3: Wakes on queue data, processes incoming bytes. Higher than general logging/telemetry to avoid buffer overflow under heavy serial load."),
        ],
        queues=[
            QueueDef("xRxQueue", 64, "uint8_t", "UART0_IRQHandler", "vProcessingTask",
                     "Depth 64 bytes: Handles burst serial traffic. Memory overhead: ~80 bytes (control struct) + 64 * 1 byte = ~144 bytes of RAM."),
        ],
        isr_notes=[
            "xQueueSendFromISR() is the ONLY FreeRTOS call permitted inside UART0_IRQHandler.",
            "portYIELD_FROM_ISR(xHigherPriorityTaskWoken) triggers immediate context switch on interrupt exit if a higher priority task was unblocked, avoiding tick delay.",
            "VICVectAddr = 0 must be written at end of ISR to clear VIC interrupt.",
            "U0RBR read clears the RX interrupt flag — do NOT skip this read.",
        ],
        timing_budget={"ISR execution": "<5 CPU cycles", "Byte-to-task latency": "<1ms"},
        safety_rules=[
            "NEVER call xQueueSend() (blocking version) from ISR — use xQueueSendFromISR().",
            "NEVER call vTaskDelay() from ISR.",
            "NEVER use mutexes in ISR — mutexes include priority inheritance and may block.",
            "Always write VICVectAddr = 0 at the end of every VIC-handled IRQ.",
        ],
        code_skeleton=code,
        explainability={
            "Why ISR-to-queue pattern?": "ISRs must be kept as short as possible to minimize interrupt latency and jitter. The queue pattern decouples fast byte collection in the interrupt from slower frame parsing in the task context.",
            "Why queue depth 64?": "Designed for UART0 RX. At 115200 baud, 1 byte arrives every ~86us. A queue depth of 64 bytes holds up to ~5.5ms of burst data, allowing the scheduler to delay the processing task by several ticks without data loss. FreeRTOS queue memory overhead is calculated as: Queue Structure (RAM) = sizeof(QueueDefinition) + (uxLength * uxItemSize). On 32-bit ARM7 (LPC2148), sizeof(QueueDefinition) is ~80 bytes. For depth=64, item_size=1, RAM overhead is ~80 + 64 = 144 bytes, which is highly efficient.",
            "Why portYIELD_FROM_ISR?": "When xQueueSendFromISR() unblocks vProcessingTask (which has a higher priority than the currently running task), the scheduler must preempt the interrupted task immediately. Calling portYIELD_FROM_ISR() triggers a context switch on interrupt exit, ensuring the higher-priority task runs without waiting for the next scheduler tick interrupt (avoiding up to 1ms of tick latency and jitter).",
        }
    )


# =============================================================================
# ADC ACQUISITION + FILTERING SYSTEM
# =============================================================================
def _adc_filtering_system() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* === Queue: Acquisition -> Processing (uint16_t ADC samples, depth=32) */
static QueueHandle_t xADCQueue;

/* === Task Priorities (Rate Monotonic: shorter period = higher priority) */
#define PRIORITY_ACQ    3   /* 50Hz (20ms) — highest */
#define PRIORITY_PROC   2   /* Event-driven on queue */
#define PRIORITY_OUTPUT 1   /* Lowest: UART/display */

/* === vAcquisitionTask: reads AD0.1 at 50Hz */
static void vAcquisitionTask(void *pv)
{
    uint16_t raw;
    for (;;)
    {
        /* Start ADC: Channel 1 (bit 1), CLKDIV=13 (15MHz/14 ~= 1MHz), PDN=1 (bit 21) */
        AD0CR = (1<<1) | (13<<8) | (1<<21);
        AD0CR |= (1<<24);                    /* START=001: start now */
        while (!(AD0DR1 & (1<<31)));         /* Wait DONE bit (bit 31) */
        raw = (AD0DR1 >> 6) & 0x3FF;        /* Extract 10-bit result */

        xQueueSend(xADCQueue, &raw, 0);     /* Non-blocking send */
        vTaskDelay(pdMS_TO_TICKS(20));      /* 50Hz sampling period */
    }
}

/* === vProcessingTask: 16-sample moving average filter */
static void vProcessingTask(void *pv)
{
    uint16_t samples[16] = {0};
    uint32_t sum = 0;
    uint8_t  idx = 0;
    uint16_t raw, avg;

    for (;;)
    {
        if (xQueueReceive(xADCQueue, &raw, portMAX_DELAY) == pdTRUE)
        {
            /* Sliding window: add new, remove oldest */
            sum += raw;
            sum -= samples[idx];
            samples[idx] = raw;
            idx = (idx + 1) & 0x0F;   /* Wrap at 16 (power of 2) */
            avg = (uint16_t)(sum >> 4); /* Divide by 16 via shift */

            /* Forward filtered result to output queue */
            xQueueSend(xADCQueue, &avg, 0); /* Replace with dedicated output queue in production */
        }
    }
}

/* === vOutputTask: serializes filtered value to UART */
static void vOutputTask(void *pv)
{
    uint16_t filtered;
    for (;;)
    {
        if (xQueueReceive(xADCQueue, &filtered, portMAX_DELAY) == pdTRUE)
        {
            /* Transmit via U0THR. Convert to voltage: V = (filtered * 3300) / 1024 mV */
        }
    }
}

int main(void)
{
    /* Configure P0.28 as AD0.1: PINSEL1 bits [25:24] = 01 */
    PINSEL1 = (PINSEL1 & ~(3<<24)) | (1<<24);

    xADCQueue = xQueueCreate(32, sizeof(uint16_t));

    xTaskCreate(vAcquisitionTask, "ADCacq",  256, NULL, PRIORITY_ACQ,    NULL);
    xTaskCreate(vProcessingTask,  "ADCproc", 512, NULL, PRIORITY_PROC,   NULL);
    xTaskCreate(vOutputTask,      "Output",  256, NULL, PRIORITY_OUTPUT, NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="ADC Acquisition + Moving Average Filter (FreeRTOS + LPC2148)",
        objective="Sample AD0.1 at 50Hz, apply a 16-sample sliding window moving average, output filtered value via UART.",
        hardware=["LPC2148 ARM7 MCU", "Analog sensor on P0.28 (AD0.1)", "UART terminal"],
        protocols=["ADC (polling, 10-bit, 1MHz ADC clock)", "UART (output)"],
        tasks=[
            RTOSTask("vAcquisitionTask", "vAcquisitionTask", 3, 20,  256, "ADC Acquisition",
                     "Priority 3 (highest): 50Hz sampling (20ms period). RMS assigns highest priority to shortest period."),
            RTOSTask("vProcessingTask",  "vProcessingTask",  2, 0,   512, "Moving Average",
                     "Priority 2: event-driven, wakes on queue data. Stack 512 for 16-sample buffer and arithmetic."),
            RTOSTask("vOutputTask",      "vOutputTask",      1, 0,   256, "UART Output",
                     "Priority 1 (lowest): UART transmission can lag without affecting filter accuracy."),
        ],
        queues=[
            QueueDef("xADCQueue", 32, "uint16_t", "vAcquisitionTask", "vProcessingTask",
                     "Depth 32: holds ~640ms of 50Hz samples. Memory: ~80 + 32*2 = ~144 bytes of RAM."),
        ],
        isr_notes=[
            "ADC DONE bit polling is safe at 50Hz. For >1kHz rates, use ADC interrupt instead.",
            "If ADC interrupt is used: call xQueueSendFromISR() + portYIELD_FROM_ISR().",
        ],
        timing_budget={
            "ADC conversion time": "~11us at 1MHz ADC clock",
            "Sampling period":     "20ms (50Hz)",
            "Filter latency":      "<1ms (16 additions/shifts)",
        },
        safety_rules=[
            "AD0CR PDN (bit 21) must be set before starting conversion.",
            "Read AD0DR1 only after DONE bit (bit 31) is confirmed set.",
            "PINSEL1 must configure P0.28 as AD0.1 before AD0CR is written.",
            "Analog input voltage must not exceed VREF (3.3V on LPC2148).",
        ],
        code_skeleton=code,
        explainability={
            "Why moving average via shift?": "sum >> 4 replaces division by 16 — deterministic single-cycle on ARM7 TDMI. No FPU needed.",
            "Why queue depth 32?": "At 50Hz, 32 samples = 640ms buffer. Allows Processing task to be delayed up to 640ms without data loss.",
            "Why polling DONE bit?": "At 50Hz, ADC polling occupies <0.1% CPU. ISR overhead is not justified unless sampling rate exceeds 1kHz.",
        }
    )


# =============================================================================
# CAN BUS TELEMETRY SYSTEM
# =============================================================================
def _can_telemetry_system() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

typedef struct {
    uint32_t id;        /* CAN message identifier */
    uint8_t  dlc;       /* Data Length Code (0-8 bytes) */
    uint8_t  data[8];   /* CAN payload */
} CANFrame_t;

static QueueHandle_t xCANQueue;   /* CAN ISR -> Processing (depth=16) */

#define PRIORITY_CAN_PROC  3
#define PRIORITY_TELEM     1

/* CAN1 RX Interrupt Handler */
void CAN_IRQHandler(void) __attribute__((interrupt("IRQ")));
void CAN_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    CANFrame_t frame;

    /* Read CAN1 receive registers */
    frame.id  = CAN1RID;                        /* Received ID */
    frame.dlc = (CAN1RFS >> 16) & 0x0F;         /* Frame info: DLC bits [19:16] */
    frame.data[0] = CAN1RDA & 0xFF;             /* Bytes 0-3 from CAN1RDA */
    frame.data[1] = (CAN1RDA >> 8)  & 0xFF;
    frame.data[2] = (CAN1RDA >> 16) & 0xFF;
    frame.data[3] = (CAN1RDA >> 24) & 0xFF;
    frame.data[4] = CAN1RDB & 0xFF;             /* Bytes 4-7 from CAN1RDB */
    frame.data[5] = (CAN1RDB >> 8)  & 0xFF;
    frame.data[6] = (CAN1RDB >> 16) & 0xFF;
    frame.data[7] = (CAN1RDB >> 24) & 0xFF;

    /* Release receive buffer */
    CAN1CMR = (1<<2);   /* CMR: RRB (Release Receive Buffer) */

    xQueueSendFromISR(xCANQueue, &frame, &xHigherPriorityTaskWoken);

    /* Acknowledge VIC */
    VICVectAddr = 0;
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

/* vCANProcessingTask: decodes CAN frames by ID */
static void vCANProcessingTask(void *pv)
{
    CANFrame_t frame;
    uint16_t speed_kmh, rpm;
    for (;;)
    {
        if (xQueueReceive(xCANQueue, &frame, portMAX_DELAY) == pdTRUE)
        {
            if (frame.id == 0x100)   /* Speed frame */
                speed_kmh = ((uint16_t)frame.data[1] << 8) | frame.data[0];
            else if (frame.id == 0x200) /* RPM frame */
                rpm = ((uint16_t)frame.data[1] << 8) | frame.data[0];
            /* Forward to telemetry via additional queue */
        }
    }
}

/* vTelemetryTask: serializes decoded data to UART0 */
static void vTelemetryTask(void *pv)
{
    for (;;)
    {
        /* Transmit speed/RPM as CSV via U0THR */
        vTaskDelay(pdMS_TO_TICKS(100));  /* 10Hz telemetry rate */
    }
}

int main(void)
{
    /* Configure P0.0=RD1, P0.1=TD1: PINSEL0 bits[1:0]=01, bits[3:2]=01 */
    PINSEL0 = (PINSEL0 & ~0xF) | 0x5;

    /* Enter reset mode to configure CAN1 */
    CAN1MOD = 1;

    /* Bit timing for 500kbps at PCLK=15MHz:
       BRP=1 (bits[9:0]), TSEG1=9 (bits[19:16]), TSEG2=5 (bits[22:20]), SJW=1 (bits[25:24])
       Total TQ = (BRP+1) * (1 + TSEG1 + TSEG2) = 2 * 15 = 30 -- gives exactly 500kbps at 15MHz PCLK */
    CAN1BTR = (1<<24) | (5<<20) | (9<<16) | (1);

    /* Return to operating mode */
    CAN1MOD = 0;

    /* VIC: channel 23 for CAN1 */
    VICVectAddr23  = (unsigned)CAN_IRQHandler;
    VICVectCntl23  = 0x20 | 23;
    VICIntEnable  |= (1<<23);

    /* Enable CAN1 RX interrupt: CAN1IER bit 0 */
    CAN1IER = 1;

    xCANQueue = xQueueCreate(16, sizeof(CANFrame_t));
    xTaskCreate(vCANProcessingTask, "CANproc", 512, NULL, PRIORITY_CAN_PROC, NULL);
    xTaskCreate(vTelemetryTask,     "Telem",   256, NULL, PRIORITY_TELEM,    NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="CAN Bus Telemetry RTOS System (FreeRTOS + LPC2148 CAN1)",
        objective="Receive CAN bus frames via interrupt-driven ISR, decode speed/RPM by frame ID, serialize to UART0 for telematics.",
        hardware=["LPC2148 ARM7 MCU", "CAN transceiver (e.g. MCP2551) on P0.0/P0.1", "UART0 terminal"],
        protocols=["CAN 2.0B (500kbps)", "UART0 (telemetry output)"],
        tasks=[
            RTOSTask("CAN_IRQHandler",      "ISR",                    5, 0, 0,   "CAN RX ISR",
                     "Interrupt context: reads CAN1RDA/CAN1RDB, releases buffer, sends to queue via xQueueSendFromISR. Must not block."),
            RTOSTask("vCANProcessingTask",  "vCANProcessingTask",     3, 0, 512, "Frame Decode",
                     "Priority 3: event-driven, wakes immediately on CAN frame arrival. Decodes by ID."),
            RTOSTask("vTelemetryTask",      "vTelemetryTask",         1, 100,256, "UART Output",
                     "Priority 1 (lowest): 10Hz telemetry output. Can be delayed without affecting CAN reception."),
        ],
        queues=[
            QueueDef("xCANQueue", 16, "CANFrame_t", "CAN_IRQHandler", "vCANProcessingTask",
                     "Depth 16: handles CAN bus bursts. Memory: ~80 + 16*13 = ~288 bytes of RAM."),
        ],
        isr_notes=[
            "CAN_IRQHandler must release receive buffer (CAN1CMR = 1<<2) before returning.",
            "VICVectAddr = 0 must be written to acknowledge the VIC interrupt.",
            "xQueueSendFromISR() is the ONLY FreeRTOS call permitted inside CAN ISR.",
            "portYIELD_FROM_ISR() ensures immediate task wakeup on ISR exit.",
        ],
        timing_budget={
            "CAN frame rate":    "Up to 3000 frames/sec at 500kbps",
            "ISR latency":       "<5us (register read + queue send)",
            "Decode latency":    "<1ms per frame",
            "Telemetry period":  "100ms (10Hz)",
        },
        safety_rules=[
            "CAN1 must be put in reset mode (CAN1MOD=1) before configuring CAN1BTR.",
            "CAN1CMR RRB bit must be written to release the hardware receive buffer after reading.",
            "NEVER call blocking xQueueSend() from the CAN ISR — use xQueueSendFromISR().",
            "Validate DLC before reading data bytes to avoid buffer overread.",
        ],
        code_skeleton=code,
        explainability={
            "Why ISR-driven CAN RX?": "CAN bus can deliver frames faster than a polling task can service them. ISR guarantees zero-loss reception.",
            "Why queue depth 16?": "At peak 500kbps with 8-byte frames, burst density can be 500+ frames/sec. 16 frames = ~32ms buffer at 500 fps.",
            "Why VIC channel 23?": "LPC2148 VIC assigns CAN1 to interrupt channel 23 per the datasheet interrupt source table.",
        }
    )


# =============================================================================
# AUTONOMOUS ROBOT: HC-SR04 + PWM Motor Control (LPC2148 specific)
# =============================================================================
def _autonomous_robot_system() -> ArchitectureBlueprint:
    code = """\
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

/* === vSensorTask: HC-SR04 on P0.10 (TRIG) and P0.9 (ECHO) */
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

/* === vNavigationTask: obstacle avoidance logic */
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

/* === vMotorTask: applies latched PWM duty cycles */
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
}"""

    return ArchitectureBlueprint(
        system_name="Autonomous Robot: HC-SR04 + PWM Motor Control (FreeRTOS + LPC2148)",
        objective="Navigate autonomously using HC-SR04 distance sensing on P0.10/P0.9, drive PWM motors on P0.0/P0.7 (PWM1/PWM2) with collision avoidance logic.",
        hardware=["LPC2148 ARM7 MCU", "HC-SR04 Ultrasonic Sensor (P0.10 TRIG, P0.9 ECHO)",
                  "DC Motors + L298N driver", "PWM1 on P0.0", "PWM2 on P0.7"],
        protocols=["GPIO (HC-SR04 TRIG/ECHO)", "PWM (motor speed)", "Timer1 (ECHO timing)"],
        tasks=[
            RTOSTask("vSensorTask",     "vSensorTask",     3, 60,  256, "HC-SR04 Sensing",
                     "Priority 3 (highest): 60ms cycle enforced by RMS. TRIG must fire on time or echo overlaps corrupt distance."),
            RTOSTask("vNavigationTask", "vNavigationTask", 2, 0,   512, "Obstacle Avoidance",
                     "Priority 2: event-driven, wakes on sensor data. Computes PWM duty and latches via PWMLER."),
            RTOSTask("vMotorTask",      "vMotorTask",      1, 500, 256, "Motor Monitor",
                     "Priority 1 (lowest): periodic health monitor / emergency stop check."),
        ],
        queues=[
            QueueDef("xSensorQueue", 5, "SensorReading_t", "vSensorTask", "vNavigationTask",
                     "Depth 5: 300ms buffer at 60ms rate. Memory: ~80 + 5*8 = ~120 bytes of RAM."),
        ],
        isr_notes=[
            "In production, use Timer1 CAP1.0 interrupt to measure ECHO pulse width (non-blocking).",
            "Timer1 CAP ISR: call xQueueSendFromISR() + portYIELD_FROM_ISR(xHigherPriorityTaskWoken).",
            "HC-SR04 ECHO is 5V — use a 1kΩ/2kΩ voltage divider before LPC2148 GPIO input.",
        ],
        timing_budget={
            "HC-SR04 cycle":     "60ms (minimum between triggers)",
            "Nav decision":      "<5ms (threshold comparison + register write)",
            "PWM latch latency": "<1 PWM period (<=1ms at 1kHz)",
        },
        safety_rules=[
            "PWMMR1 and PWMMR2 must never exceed PWMMR0 (1000). Validate before writing.",
            "Write PWMLER to latch new duty cycles — without this, PWMMR1/2 changes are ignored.",
            "HC-SR04 ECHO is 5V — NEVER connect directly to LPC2148 GPIO without level shifting.",
            "Always check pdPASS on xTaskCreate — failure means heap exhausted.",
        ],
        code_skeleton=code,
        explainability={
            "Why PWMLER?": "LPC2148 PWM uses double-buffered match registers. Writing PWMMR1/2 alone does NOT immediately change duty. PWMLER=1<<n latches the new value on the next period boundary, ensuring glitch-free transitions.",
            "Why PWMMR0=1000?": "At PCLK=15MHz with PWMPR=0 (no prescale), each PWM tick is 67ns. Period=1000 ticks = 67us = ~15kHz PWM frequency. Motors respond well at 10-20kHz.",
            "Why Timer1 for ECHO?": "Busy-wait polling blocks the task for up to 25ms (at 4m range). Timer1 capture frees the CPU and enables deterministic interrupt-driven measurement.",
        }
    )
def _spi_sensor_pipeline() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

#define PRIORITY_SPI    2
#define PRIORITY_OUTPUT 1

static QueueHandle_t xSPIQueue;

static void vSPITask(void *pv)
{
    uint8_t data;
    for (;;)
    {
        /* Select slave (CS low) */
        IO0CLR = (1 << 7);

        /* Write dummy byte to transmit/clock data in */
        S0SPDR = 0xFF;
        while (!(S0SPSR & (1 << 7))); /* Wait for SPIF */
        data = S0SPDR;

        /* Deselect slave (CS high) */
        IO0SET = (1 << 7);

        xQueueSend(xSPIQueue, &data, 0);
        vTaskDelay(pdMS_TO_TICKS(50)); /* 20Hz rate */
    }
}

static void vOutputTask(void *pv)
{
    uint8_t sensor_val;
    for (;;)
    {
        if (xQueueReceive(xSPIQueue, &sensor_val, portMAX_DELAY) == pdTRUE)
        {
            /* Process sensor_val and send over UART */
        }
    }
}

int main(void)
{
    /* Configure SCK0 (P0.4), MISO0 (P0.5), MOSI0 (P0.6) as SPI0 pins: PINSEL0 bits [13:8] = 010101 */
    PINSEL0 = (PINSEL0 & ~(0x3F << 8)) | (0x15 << 8);
    
    /* Configure P0.7 (CS) as GPIO output */
    IO0DIR |= (1 << 7);
    IO0SET = (1 << 7); /* CS high */

    /* SPI Control Register: Master mode, MSB first, 8-bit */
    S0SPCR = (1 << 5);
    S0SPCCR = 8;

    xSPIQueue = xQueueCreate(16, sizeof(uint8_t));

    xTaskCreate(vSPITask, "SPITask", 256, NULL, PRIORITY_SPI, NULL);
    xTaskCreate(vOutputTask, "OutputTask", 256, NULL, PRIORITY_OUTPUT, NULL);

    vTaskStartScheduler();
    for (;;);
}"""

    return ArchitectureBlueprint(
        system_name="SPI Sensor Pipeline",
        objective="Read SPI sensor data at 20Hz, process and queue readings for output.",
        hardware=["LPC2148 MCU", "SPI Sensor (connected to SPI0)", "GPIO CS pin"],
        protocols=["SPI0 (master, 8-bit, SCK0/MISO0/MOSI0)", "GPIO"],
        tasks=[
            RTOSTask("vSPITask", "vSPITask", 2, 50, 256, "SPI Reading",
                     "Priority 2: periodic 50ms SPI sensor query. Shorter period than output task."),
            RTOSTask("vOutputTask", "vOutputTask", 1, 0, 256, "UART Output",
                     "Priority 1: event-driven output processing task."),
        ],
        queues=[
            QueueDef("xSPIQueue", 16, "uint8_t", "vSPITask", "vOutputTask",
                     "Depth 16: buffers SPI sensor readings for processing task."),
        ],
        isr_notes=[
            "SPI uses polling for transfer completion. For high speed, use SPI interrupt.",
        ],
        timing_budget={
            "SPI transfer time": "<10us at 1MHz SPI clock",
            "Sensing period":     "50 ms (20 Hz)",
        },
        safety_rules=[
            "CS/SSEL0 must be driven low before transfer and high after transfer.",
            "S0SPCCR must be even and >= 8 to ensure valid clock division.",
        ],
        code_skeleton=code,
        explainability={
            "Why SPI Master?": "LPC2148 acts as the bus master to initiate transfers with the peripheral sensor.",
            "Why CS line control?": "Manual CS line toggling allows exact framing of multi-byte SPI transactions.",
        }
    )


def _polling_adc_architecture() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

/* === Queue: Acquisition -> Processing */
static QueueHandle_t xADCQueue;

/* === Task Priorities */
#define PRIORITY_ACQ    2
#define PRIORITY_PROC   1

/* === vADCPollingTask: reads AD0.1 at 50Hz */
static void vADCPollingTask(void *pv)
{
    uint16_t raw;
    for (;;)
    {
        /* Start ADC: Channel 1, CLKDIV=13, PDN=1 */
        AD0CR = (1<<1) | (13<<8) | (1<<21);
        AD0CR |= (1<<24);                    /* START=001: start now */
        while (!(AD0DR1 & (1<<31)));         /* Wait DONE bit (bit 31) */
        raw = (AD0DR1 >> 6) & 0x3FF;        /* Extract 10-bit result */

        xQueueSend(xADCQueue, &raw, 0);     /* Non-blocking send */
        vTaskDelay(pdMS_TO_TICKS(20));      /* 50Hz sampling period */
    }
}

/* === vProcessingTask: processes ADC data */
static void vProcessingTask(void *pv)
{
    uint16_t raw;
    for (;;)
    {
        if (xQueueReceive(xADCQueue, &raw, portMAX_DELAY) == pdTRUE)
        {
            /* Process sample */
        }
    }
}

int main(void)
{
    /* Configure P0.28 as AD0.1 */
    PINSEL1 = (PINSEL1 & ~(3<<24)) | (1<<24);

    xADCQueue = xQueueCreate(10, sizeof(uint16_t));
    xTaskCreate(vADCPollingTask, "ADCPoll", 256, NULL, PRIORITY_ACQ, NULL);
    xTaskCreate(vProcessingTask, "Process", 256, NULL, PRIORITY_PROC, NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="Polling ADC Acquisition (FreeRTOS + LPC2148)",
        objective="Sample AD0.1 at 50Hz by polling the ADC DONE bit inside a periodic FreeRTOS task, passing readings to a processing task.",
        hardware=["LPC2148 ARM7 MCU", "Analog Sensor (P0.28)"],
        protocols=["ADC (polling, 10-bit)"],
        tasks=[
            RTOSTask("vADCPollingTask", "vADCPollingTask", 2, 20, 256, "Acquisition",
                     "Priority 2: periodic 20ms ADC read. Higher than processing to meet sampling deadline."),
            RTOSTask("vProcessingTask", "vProcessingTask", 1, 0, 256, "Processing",
                     "Priority 1: event-driven sample processing task."),
        ],
        queues=[
            QueueDef("xADCQueue", 10, "uint16_t", "vADCPollingTask", "vProcessingTask",
                     "Depth 10: buffers ADC samples to prevent loss during processing bursts."),
        ],
        isr_notes=[
            "Uses software polling of the ADC DONE bit. For high sample rates, convert to interrupt-driven.",
        ],
        timing_budget={
            "ADC conversion time": "~11 us",
            "Sampling period":     "20 ms (50 Hz)",
        },
        safety_rules=[
            "AD0CR PDN bit must be set before starting conversion.",
            "Read AD0DR1 only after DONE bit (bit 31) is set.",
        ],
        code_skeleton=code,
        explainability={
            "Why polling inside task?": "At 50Hz, the CPU overhead of polling is negligible (<0.1%), making polling acceptable without interrupt complexity.",
        }
    )

def _polling_uart_pipeline() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

static QueueHandle_t xRxQueue;

/* === vUARTPollingTask: polls UART0 RX FIFO */
static void vUARTPollingTask(void *pv)
{
    uint8_t ch;
    for (;;)
    {
        /* Poll Receiver Data Ready (RDR) bit in U0LSR */
        if (U0LSR & 0x01)
        {
            ch = U0RBR; /* Read character */
            xQueueSend(xRxQueue, &ch, 0);
        }
        vTaskDelay(pdMS_TO_TICKS(10)); /* Poll every 10ms */
    }
}

/* === vParserTask: processes UART characters */
static void vParserTask(void *pv)
{
    uint8_t ch;
    for (;;)
    {
        if (xQueueReceive(xRxQueue, &ch, portMAX_DELAY) == pdTRUE)
        {
            /* Parse character */
        }
    }
}

int main(void)
{
    /* UART0 setup: 9600 baud */
    PINSEL0 |= 0x05; /* P0.0=TXD0, P0.1=RXD0 */
    U0LCR = 0x83;    /* DLAB=1, 8N1 */
    U0DLL = 391;     /* 9600 baud */
    U0LCR = 0x03;    /* DLAB=0 */

    xRxQueue = xQueueCreate(16, sizeof(uint8_t));
    xTaskCreate(vUARTPollingTask, "UARTPoll", 256, NULL, 2, NULL);
    xTaskCreate(vParserTask, "Parser", 256, NULL, 1, NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="Polling UART Pipeline (FreeRTOS + LPC2148)",
        objective="Poll the UART0 receiver state periodically inside a FreeRTOS task, passing characters to a parser task.",
        hardware=["LPC2148 ARM7 MCU", "UART transceiver"],
        protocols=["UART0 (polling)"],
        tasks=[
            RTOSTask("vUARTPollingTask", "vUARTPollingTask", 2, 10, 256, "Acquisition",
                     "Priority 2: periodic 10ms UART register check. Higher than parser to avoid FIFO overflow."),
            RTOSTask("vParserTask", "vParserTask", 1, 0, 256, "Parsing",
                     "Priority 1: event-driven parser task."),
        ],
        queues=[
            QueueDef("xRxQueue", 16, "uint8_t", "vUARTPollingTask", "vParserTask",
                     "Depth 16: buffers characters between acquisition and parser."),
        ],
        isr_notes=[
            "Uses periodic register polling. For high-speed serial, convert to UART RX interrupt.",
        ],
        timing_budget={
            "Baud rate": "9600",
            "Polling interval": "10 ms",
        },
        safety_rules=[
            "Ensure DLAB is cleared after configuring baud rates.",
        ],
        code_skeleton=code,
        explainability={
            "Why 10ms polling?": "At 9600 baud, characters arrive at ~1ms intervals. Polling at 10ms is safe for hardware FIFOs of 16 bytes.",
        }
    )

def _polling_sensor_architecture() -> ArchitectureBlueprint:
    code = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <lpc214x.h>

static QueueHandle_t xSensorQueue;

/* === vSensorPollingTask: polls GPIO pin */
static void vSensorPollingTask(void *pv)
{
    uint32_t val;
    for (;;)
    {
        /* Poll pin P0.10 */
        val = (IO0PIN & (1<<10)) ? 1 : 0;
        xQueueSend(xSensorQueue, &val, 0);
        vTaskDelay(pdMS_TO_TICKS(100)); /* Poll every 100ms */
    }
}

/* === vDisplayTask: displays sensor state */
static void vDisplayTask(void *pv)
{
    uint32_t val;
    for (;;)
    {
        if (xQueueReceive(xSensorQueue, &val, portMAX_DELAY) == pdTRUE)
        {
            /* Update display */
        }
    }
}

int main(void)
{
    /* Set P0.10 as input */
    IO0DIR &= ~(1<<10);

    xSensorQueue = xQueueCreate(5, sizeof(uint32_t));
    xTaskCreate(vSensorPollingTask, "SensorPoll", 256, NULL, 2, NULL);
    xTaskCreate(vDisplayTask, "Display", 256, NULL, 1, NULL);

    vTaskStartScheduler();
    for(;;);
}"""

    return ArchitectureBlueprint(
        system_name="Polling Sensor Architecture (FreeRTOS + LPC2148)",
        objective="Poll a GPIO-connected sensor periodically inside a FreeRTOS task, passing state updates to a display/actuation task.",
        hardware=["LPC2148 ARM7 MCU", "GPIO Sensor"],
        protocols=["GPIO (polling)"],
        tasks=[
            RTOSTask("vSensorPollingTask", "vSensorPollingTask", 2, 100, 256, "Sensing",
                     "Priority 2: periodic 100ms GPIO pin poll."),
            RTOSTask("vDisplayTask", "vDisplayTask", 1, 0, 256, "Actuation",
                     "Priority 1: event-driven UI updater."),
        ],
        queues=[
            QueueDef("xSensorQueue", 5, "uint32_t", "vSensorPollingTask", "vDisplayTask",
                     "Depth 5: buffers sensor state updates."),
        ],
        isr_notes=[
            "GPIO uses simple task polling. For fast transition events, convert to external interrupt.",
        ],
        timing_budget={
            "Polling cycle": "100 ms",
        },
        safety_rules=[
            "Ensure pin direction is set as input in IO0DIR.",
        ],
        code_skeleton=code,
        explainability={
            "Why periodic polling?": "GPIO state changes slowly (e.g. human button press or level switch), making 100ms polling highly efficient and debounce-free.",
        }
    )


def detect_system_type(query: str) -> str:
    q = query.lower()
    
    # Force generic fallback (knowledge base) for informational / explanation queries,
    # unless they explicitly request design/architecture synthesis.
    info_keywords = [
        "explain", "register", "calibration", "formula", "value", "why",
        "how does", "what does", "can", "how to read", "how to configure",
        "what is", "what are", "difference", "causes of", "how do you safely",
        "what happens", "role of", "benefits of", "how to interface", "work and"
    ]
    design_keywords = ["design", "architecture", "blueprint", "synthesize", "build", "generate rtos", "system template"]
    
    if any(k in q for k in info_keywords) and not any(k in q for k in design_keywords):
        return "generic"

    if "polling" in q:
        if any(k in q for k in ["adc", "analog"]):
            return "polling_adc"
        if any(k in q for k in ["uart", "serial"]):
            return "polling_uart"
        return "polling_sensor"

    if any(k in q for k in ["sensor fusion", "mpu6050", "imu", "accelerometer", "gyro"]):
        if any(k in q for k in ["gps", "location", "navigation"]):
            return "sensor_fusion_gps"
        return "sensor_fusion_imu"
    if any(k in q for k in ["telematics", "tracking", "gps", "gsm"]):
        return "telematics_tracking"
    if any(k in q for k in ["parking", "occupancy", "gate"]):
        return "smart_parking"
    if any(k in q for k in ["temperature", "lm35", "thermal", "heat"]):
        return "temperature_logger"
    if any(k in q for k in ["adc", "filter", "averaging", "acquisition"]):
        return "adc_filtering"
    if any(k in q for k in ["can bus", "can frame", "canbus", "can telemetry", "can bus telemetry", "can architecture", "can system"]) or "can" in q.split() or "can1" in q.split():
        return "can_telemetry"
    if any(k in q for k in ["spi"]):
        return "spi_sensor"
    # Autonomous robot checked before generic obstacle_detection:
    # queries like "autonomous robot using HC-SR04 + PWM" span both domains.
    if any(k in q for k in ["robot", "autonomous"]):
        return "autonomous_robot"
    if any(k in q for k in ["adas", "obstacle", "ultrasonic", "hc-sr04", "distance", "collision"]):
        return "obstacle_detection"
    if any(k in q for k in ["motor", "navigation", "drive"]):
        return "autonomous_robot"
    if any(k in q for k in ["uart", "serial"]):
        return "isr_to_task_pipeline"
    if any(k in q for k in ["isr", "interrupt", "queue-based", "queue based", "producer", "consumer"]):
        return "isr_to_task_pipeline"
    return "generic"


def generate_blueprint(query: str) -> ArchitectureBlueprint | None:
    system_type = detect_system_type(query)
    if system_type == "polling_adc":
        return _polling_adc_architecture()
    if system_type == "polling_uart":
        return _polling_uart_pipeline()
    if system_type == "polling_sensor":
        return _polling_sensor_architecture()
    if system_type == "telematics_tracking":
        return _telematics_tracking()
    if system_type == "smart_parking":
        return _smart_parking()
    if system_type == "obstacle_detection":
        return _obstacle_detection()
    if system_type == "temperature_logger":
        return _temperature_logger()
    if system_type in ("sensor_fusion_gps", "sensor_fusion_imu"):
        return _sensor_fusion_gps_imu()
    if system_type == "adc_filtering":
        return _adc_filtering_system()
    if system_type == "can_telemetry":
        return _can_telemetry_system()
    if system_type == "autonomous_robot":
        return _autonomous_robot_system()
    if system_type == "isr_to_task_pipeline":
        return _isr_to_task_pipeline()
    if system_type == "spi_sensor":
        return _spi_sensor_pipeline()
    return None


def polling_sensor_architecture() -> ArchitectureBlueprint:
    return _polling_sensor_architecture()


def polling_uart_pipeline() -> ArchitectureBlueprint:
    return _polling_uart_pipeline()


def adc_polling_task() -> ArchitectureBlueprint:
    return _polling_adc_architecture()



# ==================================================================================================================─
# BLUEPRINT RENDERER -> formatted markdown string
# ==================================================================================================================─

def render_blueprint(bp: ArchitectureBlueprint) -> str:
    lines = []

    lines.append(f"# System Architecture: {bp.system_name}\n")
    lines.append(f"**Objective:** {bp.objective}\n")

    lines.append("## Hardware Components")
    for h in bp.hardware:
        lines.append(f"- {h}")
    lines.append("")

    lines.append("## Protocols / Interfaces")
    for p in bp.protocols:
        lines.append(f"- {p}")
    lines.append("")

    lines.append("## RTOS Task Graph")
    lines.append("| Task | Priority | Period | Stack | Role |")
    lines.append("|------|----------|--------|-------|------|")
    for t in bp.tasks:
        period = f"{t.period_ms} ms" if t.period_ms else "event-driven"
        lines.append(f"| {t.name} | {t.priority} | {period} | {t.stack} words | {t.role} |")
    lines.append("")

    lines.append("## Queue / Communication Flow")
    lines.append("| Queue | Depth | Item Type | Producer | Consumer |")
    lines.append("|-------|-------|-----------|----------|----------|")
    for q in bp.queues:
        lines.append(f"| {q.name} | {q.length} | {q.item_size} | {q.from_task} | {q.to_task} |")
    lines.append("")

    lines.append("## Timing Budget")
    for k, v in bp.timing_budget.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")

    lines.append("## Safety Rules")
    for r in bp.safety_rules:
        lines.append(f"- {r}")
    lines.append("")

    lines.append("## ISR Notes")
    for n in bp.isr_notes:
        lines.append(f"- {n}")
    lines.append("")

    lines.append("## System Explainability (Why each decision was made)")
    for decision, rationale in bp.explainability.items():
        lines.append(f"**{decision}**")
        lines.append(f"> {rationale}")
        lines.append("")

    lines.append("## Embedded C Skeleton")
    lines.append("```c")
    lines.append(bp.code_skeleton)
    lines.append("```")

    return "\n".join(lines)
