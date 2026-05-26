# -*- coding: utf-8 -*-
try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    # Simple placeholder model that returns zero vectors
    class SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass
        def encode(self, sentences, **kwargs):
            # Return dummy tensor/list of zeros matching length
            import numpy as np
            if isinstance(sentences, list):
                return np.zeros((len(sentences), 384))
            return np.zeros((1, 384))
    
    # Fallback stub with minimal interface
    class _UtilStub:
        @staticmethod
        def semantic_search(*args, **kwargs):
            raise ImportError('sentence_transformers is not installed. Semantic search unavailable.')
        @staticmethod
        def cos_sim(*args, **kwargs):
            raise ImportError('sentence_transformers is not installed. Cosine similarity unavailable.')
    util = _UtilStub
from .embeddings import model
import torch
import hashlib
import os

# Load a lightweight model for fast semantic matching
# model loaded from embeddings singleton

GOLD_INSIGHTS = {
    "adc_resolution": """### Hardware Insight: ADC Resolution (LPC2148)
The LPC2148 features a **10-bit** successive approximation ADC.

**Reasoning Chain:**
- **Total Steps:** A 10-bit converter provides 2^10 = **1024** discrete levels.
- **LSB Calculation:** The voltage represented by the Least Significant Bit is `VREF / 1024`.
- **Example:** If VREF = 3.3V, then 1 LSB = 3.22 mV.

**Hardware Result:**
- The digital output range is **0x000 to 0x3FF**.
- **Accuracy Note:** Any change smaller than 3.22 mV (at 3.3V VREF) cannot be resolved.""",

    "adc_pdn": """### Hardware Insight: ADC Power-Down (PDN) bit
**AD0CR** bit 21 is the **PDN** bit.
- **PDN = 0:** ADC is in operational power-down mode.
- **PDN = 1:** ADC is powered on.
- If PDN is 0, setting START bits will be ignored.""",

    "adc_done_bit": """### Hardware Insight: ADC DONE Bit
- DONE = 1 -> conversion complete.
- DONE = 0 -> conversion ongoing.
- Result valid ONLY when DONE = 1.""",

    "adc_start_behavior": """### Hardware Insight: ADC START Bits
- START = 000 -> no conversion.
- Non-zero START -> conversion begins.
- If not set -> ADC idle, DONE stays 0.""",

    "adc_read_before_done": """### Hardware Insight: ADC Read Before DONE
- Reading AD0DR before DONE = 1 returns stale or invalid data.""",

    "pwm_mr1_gt_mr0": """### Hardware Insight: PWM Match Condition Error
If PWMMR1 > PWMMR0:
- TC resets at MR0 before reaching MR1.
- No match event occurs.
- Result: Output stuck (invalid duty cycle).""",

    "uart_wrong_divisor": """### Hardware Insight: UART Divisor Error
If UART divisor is incorrect:
- Baud rate mismatch occurs.
- Receiver samples bits at wrong time.
- Result: Framing errors, corrupted data.""",

    "uart_dlab": """### Hardware Insight: UART DLAB Behavior
**DLAB** is Bit 7 of UxLCR.
- **DLAB = 1:** Access Baud Rate Divisors (UxDLL/DLM).
- **DLAB = 0:** Access UxTHR (TX) and UxRBR (RX).
- If DLAB is not cleared after init, data transmission fails.""",

    "adc_noise": """### Hardware Insight: ADC Noise Behavior
Causes: Supply fluctuations, digital switching, high input impedance.
Result: Output jitter (±1–3 counts).
Fix: Decoupling, low impedance input, averaging.""",

    "adc_averaging": """### Hardware Insight: ADC Averaging
Averaging N samples reduces random noise by sqrt(N) factor.
- Average 4 samples -> noise reduced by 2x.
- Average 16 samples -> noise reduced by 4x.
Implementation:
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) {
      AD0CR |= (1<<24);
      while (!(AD0DR1 & (1<<31)));
      sum += (AD0DR1 >> 6) & 0x3FF;
  }
  uint16_t avg = sum >> 4;""",

    "adc_noise_reduction": """### Hardware Insight: ADC Noise Reduction
1. Hardware: 100nF decoupling cap on VREF pin and analog input pin.
2. Layout: Keep analog traces short, away from digital lines.
3. Ground: Separate AGND from DGND -- star ground at single point.
4. Software: Average 16+ samples.
5. Source impedance: Keep input impedance below 10kohm for LPC2148 ADC.""",

    "sensor_task_priority": """### RTOS Insight: Sensor Acquisition Task Priority
Sensor acquisition tasks get highest RTOS priority because:
1. Hard deadlines: HC-SR04 (60ms), ADC sampling (Nyquist), UART RX
   buffers have strict timing windows. Missing them corrupts data.
2. Irreversibility: A missed sensor reading cannot be recovered.
3. Cascading failure: Delayed acquisition makes all downstream
   tasks (processing, actuation) work on stale data.
4. Short execution: Acquisition tasks run briefly, so high priority
   does not starve lower-priority tasks in practice.""",

    "mpu6050_calibration": """### Sensor Insight: MPU6050 Calibration
Factory bias offsets exist in both gyroscope and accelerometer axes.
- Gyroscope zero-rate output can drift +/-20 dps without calibration.
- Accelerometer offset can be +/-150mg without calibration.
Calibration procedure:
1. Place sensor flat and stationary for 2+ seconds.
2. Read 100+ samples from all 6 axes.
3. Compute mean offset per axis.
4. Write to XA_OFFS (0x06-0x0A), XG_OFFS_USR (0x13-0x18).
Consequence of skipping: heading drift, false orientation detection.""",

    "hcsr04_why_timing": """### Sensor Insight: HC-SR04 Timing Requirement
HC-SR04 measures distance by timing an ultrasonic echo pulse.
- TRIG pulse of exactly 10us initiates a burst of 8x 40kHz pulses.
- ECHO pin goes HIGH when burst is sent, LOW when reflection received.
- Pulse width encodes distance: distance_cm = pulse_width_us / 58.
- Measurement accuracy depends entirely on precise pulse-width capture.
- Timer Capture (CAP0.0) is required for production accuracy.
- Polling-based measurement introduces +/-1-2cm jitter due to scheduling.""",

    "ad0cr_role": """### Hardware Insight: AD0CR Register Role
- **SEL:** Selects analog channels.
- **CLKDIV:** Produces ADC clock (must be ≤ 4.5 MHz).
- **PDN:** Power Down bit (must be 1).
- **START:** Controls conversion start.""",

    "pinsel_function": """### Hardware Insight: PINSEL Register Function
PINSEL registers control pin multiplexing. Pins default to GPIO. PINSEL setup is mandatory for peripherals.""",

    "pwmmr0_purpose": """### Hardware Insight: PWMMR0 Role
PWMMR0 defines the PWM Period. MR1-MR6 define Duty Cycles. If MR0 = 0, PWM module stalls.""",

    "adc_clock_limit": """### Hardware Insight: ADC Clock Constraint
LPC2148 ADC requires clock **≤ 4.5 MHz**.
- **Reason:** SAR logic needs settling time.
- **Exceeding 4.5 MHz:** Comparator becomes unstable, leading to accuracy loss and random data.""",

    "adc_clock_low": """### Hardware Insight: Slow ADC Clock
If ADC clock is very low: Conversion still works, but sampling rate decreases. Data remains valid but latency increases.""",

    "periodic_vs_event": """### Systems Engineering: Periodic vs Event-Driven Sampling
**Why periodic ADC sampling?**
1. **Deterministic Timing:** Critical for DSP/PID.
2. **Aliasing Control:** Nyquist compliance.
3. **Reconstruction:** Allows accurate signal recovery.
4. **Predictability:** Easier task scheduling.""",

    "interrupt_vs_polling": """### Systems Engineering: Interrupts vs Polling
**Why is interrupt-driven UART preferred over polling?**
1. **CPU Efficiency:** Avoids busy-waiting.
2. **Responsiveness:** Immediate handling of data.
3. **Concurrency:** Allows other tasks to run.""",

    "queue_vs_semaphore": """### FreeRTOS: Queue vs Semaphore
**Why choose a Queue instead of a Semaphore?**
1. **Data Transfer:** Queues transfer data payloads; semaphores are signaling only.
2. **Ordering:** Queues maintain FIFO order.
3. **Decoupling:** Queues act as a buffer.
4. **Thread Safety:** Native protection for data transfer.""",

    "lm35_filtering": """### Sensor Insight: LM35 Filtering
**Why is filtering important for LM35?**
1. **Noise:** High impedance makes it sensitive to digital noise.
2. **Stability:** Prevents ADC jitter from ripple.
3. **Accuracy:** Averaging provides stable readings.""",

    "ground_separation": """### Hardware Insight: Analog vs Digital Ground
Separate AGND and DGND to prevent fast digital switching noise from coupling into sensitive analog measurements.""",

    "isr_safe_mutex": """### FreeRTOS Insight: ISR Safety
Mutexes CANNOT be used in ISR because they include priority inheritance and can block, both of which are forbidden in interrupts.""",

    "printf_in_isr": """### FreeRTOS Insight: Interrupt Safety
printf is dangerous in ISR due to deadlock risk (mutex) and high latency (slow UART).""",

    "adc_quantization": """### Hardware Insight: ADC Quantization
ADC converts continuous signals into discrete steps. Small variations below 1 LSB are lost. Intrinsic property.""",

    "sample_hold": """### Hardware Insight: Sample-and-Hold
Captures and holds input voltage constant during the SAR process to prevent drift errors.""",

    "pwm_duty_behavior": """### Hardware Insight: PWM Duty Cycle
MR1 defines duty within MR0 period. Duty = MR1 / MR0.""",

    "freertos_task_creation": """### FreeRTOS Insight: Task Creation
Tasks in FreeRTOS are created using `xTaskCreate()`.

**API Signature and Parameters:**
- `pvTaskCode`: Pointer to the task entry function (must be an infinite loop, never return).
- `pcName`: A descriptive name for debugging.
- `usStackDepth`: Stack size allocated to the task, specified in words (not bytes).
- `pvParameters`: Pointer passed as parameter to the created task.
- `uxPriority`: Priority at which the task should run (higher numbers denote higher priority).
- `pxCreatedTask`: Used to pass out a handle to the task.

**Rule:** Tasks must not return. Priority 1+ is typical for user tasks.""",

    "freertos_priorities": """### FreeRTOS Insight: Task Priorities
FreeRTOS uses a preemptive scheduler where a higher priority number denotes a higher priority task.

**Priority Inversion:**
- Occurs when a high-priority task is blocked waiting for a shared resource (protected by a binary semaphore) held by a low-priority task, while a medium-priority task preempts the low-priority task.
- **Prevention:** Use a Mutex (mutual exclusion semaphore) instead of a binary semaphore. FreeRTOS mutexes implement **priority inheritance**, temporarily raising the low-priority task's priority to match the high-priority task's priority, preventing medium-priority preemption.""",

    "freertos_queue": """### FreeRTOS Insight: Queues
FreeRTOS queues are the primary form of Inter-Process Communication (IPC). They are thread-safe FIFO (First-In, First-Out) buffers.

**Key API Functions:**
- `xQueueCreate`: Allocates queue memory (specifies depth and item size).
- `xQueueSend`: Sends data to the back of the queue (blocks if queue is full).
- `xQueueReceive`: Receives data from the queue (blocks if queue is empty).

**Interrupt Safety:**
Inside interrupts, always use `xQueueSendFromISR` and `xQueueReceiveFromISR` instead of their blocking counterparts to maintain system determinism.""",

    "freertos_semaphore": """### FreeRTOS Insight: Semaphores
Binary (Signaling), Counting (Resource), Mutex (Exclusion).""",

    "freertos_isr_safety": """### FreeRTOS Insight: ISR Safety
Use FromISR variants. Call portYIELD_FROM_ISR at end. Clear VIC.""",

    "hcsr04_timing": """### Sensor Insight: HC-SR04 Ultrasonic Sensor
The HC-SR04 measures distance using sonar:

**Working Principle:**
1. **Trigger:** Set the TRIG pin HIGH for at least 10 us to start the ultrasonic burst.
2. **Echo:** The sensor emits 8 cycles at 40 kHz and sets the ECHO pin HIGH.
3. **Measurement:** ECHO goes LOW when signal returns. The width of the ECHO pulse is proportional to distance.
4. **Timer:** Measure pulse width using an LPC2148 Timer capture input (CAP0.0) or GPIO polling to ensure deterministic timing.

**Interfacing & Voltage Safety:**
- LPC2148 runs at 3.3V, but HC-SR04 is a 5V device.
- **Critical:** Use a level shifter or a resistor voltage divider on the ECHO pin to protect the 3.3V LPC2148 inputs from the 5V ECHO output.""",

    "lm35_integration": """### Sensor Insight: LM35
Linear 10mV/C. Use ADC to read. Filter for stability.""",

    "mpu6050_i2c": """### Sensor Insight: MPU6050
3.3V device. 0x6B to wake. WHO_AM_I = 0x68.""",

    "uart_frame_structure": """### Communication Insight: UART Frame
8N1: Start + 8 Data + Stop.ident baud on both ends.""",

    "spi_protocol": """### Communication Insight: SPI
Full-duplex, 4 wires. CPOL/CPHA modes. CS active LOW.""",

    "i2c_protocol": """### Communication Insight: I2C
2 wires (SDA/SCL). 7-bit addressing. Arbitration for multi-master.""",

    "can_bus_basics": """### Communication Insight: CAN Bus
The Controller Area Network (CAN) bus is a differential, multi-master serial bus.

**CAN Frame Structure:**
- **SOF (Start of Frame):** 1 dominant bit to synchronize nodes.
- **Arbitration Field:** Contains the identifier (determines priority).
  - **Standard Frame:** 11-bit identifier.
  - **Extended Frame:** 29-bit identifier (11-bit base + 18-bit extension).
- **Control Field:** Contains IDE (Identifier Extension) and DLC (Data Length Code).
- **Data Field:** 0 to 8 bytes of payload.
- **CRC Field (Cyclic Redundancy Check):** 15-bit CRC + delimiter for error detection.
- **ACK Field (Acknowledgement):** ACK slot where any receiver asserts dominant bit to acknowledge receipt, plus ACK delimiter.
- **EOF (End of Frame):** 7 recessive bits.""",

    "adas_architecture": """### Automotive Insight: ADAS Architecture
Acquisition -> Processing -> Actuation. Safety-critical decision logic.""",

    "short_isr_rationale": """### Systems Engineering: Short ISRs
**Why must ISRs remain short?**
1. **Latency:** Long ISRs delay other pending interrupts.
2. **Jitter:** Disrupts the timing of periodic tasks.
3. **System Hang:** If an ISR takes longer than the interrupt period, the system will enter an infinite interrupt loop (starvation).
4. **RTOS Scheduling:** The scheduler is often disabled during ISRs; long ISRs prevent task switching.""",

    "mpu6050_registers": """### Sensor Insight: MPU6050 Register Map (I2C)
- **I2C Address:** 0x68 (AD0=LOW) or 0x69 (AD0=HIGH)
- **PWR_MGMT_1 (0x6B):** Wake up device by writing 0x00 (clears SLEEP bit).
- **ACCEL_XOUT_H (0x3B):** High byte of X-axis accelerometer (16-bit, 2's complement).
- **GYRO_XOUT_H (0x43):** High byte of X-axis gyroscope.
- **WHO_AM_I (0x75):** Returns 0x68 — used for device validation.
- **CONFIG (0x1A):** DLPF (Digital Low Pass Filter) configuration.
- **Sample Rate:** Configured via SMPLRT_DIV (0x19). Rate = 8kHz / (1 + SMPLRT_DIV)
- **Initialization sequence:** Write 0x00 to PWR_MGMT_1 -> configure SMPLRT_DIV -> read ACCEL/GYRO registers.""",

    "lm35_formula": """### Sensor Insight: LM35 Temperature Conversion
- **Sensitivity:** 10 mV / °C (linear, no offset calibration needed).
- **Output range:** 0 mV (0°C) to 1500 mV (150°C).
- **Formula (using LPC2148 10-bit ADC at 3.3V VREF):**
  ```
  voltage_mV = (ADC_reading * 3300) / 1024
  temperature_C = voltage_mV / 10.0
  ```
- **Practical note:** High source impedance -> use 100nF bypass capacitor to avoid ADC noise coupling.
- **PINSEL setup:** Configure ADC pin via PINSEL before reading.
- **Filtering:** Average 8–16 samples for stable readings.""",

    "isr_safe_apis": """### FreeRTOS Insight: ISR-Safe API Reference
Only the `FromISR` variants of FreeRTOS functions may be called inside an ISR:

| Forbidden in ISR          | ISR-Safe Replacement               |
|---------------------------|-------------------------------------|
| xQueueSend               | xQueueSendFromISR                  |
| xSemaphoreGive           | xSemaphoreGiveFromISR              |
| xTaskCreate              | NOT callable from ISR               |
| vTaskDelay               | NOT callable from ISR               |
| xEventGroupSetBits       | xEventGroupSetBitsFromISR           |

**Critical:** Always pass `&xHigherPriorityTaskWoken` and call `portYIELD_FROM_ISR(xHigherPriorityTaskWoken)` at the end of the ISR to trigger a context switch if a higher-priority task was unblocked.""",

    "interrupt_latency": """### Systems Engineering: Interrupt Latency
- **Definition:** Time from interrupt assertion to first ISR instruction execution.
- **Components:** VIC arbitration + pipeline flush + register save (stacking).
- **LPC2148 (ARM7TDMI):** ~10–20 CPU cycles for VIC-handled interrupts.
- **Impact on RTOS:** Interrupt latency adds to worst-case task response time.
- **Minimization:** Use VIC hardware prioritization, keep ISR code minimal, avoid nested critical sections.
- **Jitter source:** If another interrupt is in progress, the new interrupt waits -> increases latency variability.""",

    "queue_overflow": """### FreeRTOS Insight: Queue Overflow Behavior
- **Definition:** Occurs when producer sends to a full queue without a wait timeout.
- **Result:** `xQueueSend` returns `errQUEUE_FULL` (pdFAIL).
- **Detection:** Always check return value of `xQueueSend` / `xQueueSendFromISR`.
- **Prevention strategies:**
  1. Size queue for peak burst: `xQueueCreate(depth, item_size)` where `depth` ≥ max burst.
  2. Use `xQueueSendToFront()` for high-priority data.
  3. Log overflow events to detect design imbalances.
- **Dangerous pattern:** Ignoring return value silently drops data — determinism is lost.""",

    "stack_overflow": """### FreeRTOS Insight: Stack Overflow Behavior
- **Definition:** Task writes beyond its allocated stack boundary.
- **Consequence:** Corrupts adjacent memory, causing unpredictable behavior or hard fault.
- **Detection:** Enable `configCHECK_FOR_STACK_OVERFLOW` in FreeRTOSConfig.h:
  - Mode 1: Checks stack boundary at task switch (fast).
  - Mode 2: Fills stack with known pattern, verifies on switch (thorough).
- **Hook function:** `vApplicationStackOverflowHook(TaskHandle_t, char*)` called on detection.
- **Sizing rule:** Minimum stack = local variables + nested function calls + interrupt frame (~68 bytes on ARM7).
- **Typical starting size:** 256 words (1 KB) for simple tasks.""",

    "dma_basics": """### Hardware Insight: DMA (Direct Memory Access)
- **Purpose:** Transfers data between memory and peripheral without CPU involvement.
- **LPC2148 DMA:** GPDMA controller supports memory-to-peripheral, peripheral-to-memory, and memory-to-memory.
- **When to use:** High-throughput ADC streaming, UART burst transfer, SPI large data blocks.
- **Key registers:** DMACCxControl (transfer size, width), DMACCxSrcAddr, DMACCxDestAddr, DMACCxConfig.
- **Interrupt:** GPDMA triggers interrupt on transfer completion — CPU only involved at start/end.
- **Determinism benefit:** Removes CPU polling loop from data path -> frees CPU cycles for RTOS tasks.""",

    "scheduler_tick": """### FreeRTOS Insight: Scheduler Tick
- **Definition:** Periodic timer interrupt that drives the RTOS scheduler.
- **Configured by:** `configTICK_RATE_HZ` in FreeRTOSConfig.h (typically 1000 Hz = 1ms tick).
- **Role:** Decrements task delay counters, unblocks delayed tasks, triggers preemption.
- **Trade-off:** Faster tick -> finer timing resolution but more overhead (ISR overhead × tick frequency).
- **Minimum delay resolution:** `vTaskDelay(1)` = 1 tick period (1ms at 1kHz).
- **Critical:** Never call `vTaskDelay(0)` — use `taskYIELD()` to voluntarily yield without sleeping.
- **Timer source on LPC2148:** Timer0 or Timer1 configured as FreeRTOS tick source via `vPortSetupTimerInterrupt()`.""",
}

# Pre-calculate embeddings (with disk cache to avoid 10+ second startup)
insight_keys = list(GOLD_INSIGHTS.keys())
insight_texts = list(GOLD_INSIGHTS.values())

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "insight_embeddings.pt"
)

def _load_or_compute_embeddings(texts, mdl):
    """Load embeddings from disk cache if checksum matches, else recompute."""
    checksum = hashlib.md5(str(texts).encode()).hexdigest()
    if os.path.exists(CACHE_PATH):
        try:
            cached = torch.load(CACHE_PATH, weights_only=True)
            if cached.get("checksum") == checksum:
                return cached["embeddings"]
        except Exception:
            pass  # corrupt cache — recompute
    embeddings = mdl.encode(texts, convert_to_tensor=True)
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    torch.save({"checksum": checksum, "embeddings": embeddings}, CACHE_PATH)
    return embeddings

insight_embeddings = _load_or_compute_embeddings(insight_texts, model)

def check_gold_insight(query: str, allow_semantic: bool = True) -> str:
    q = query.lower()

    # Systems Engineering
    if "periodic" in q and "adc" in q: return GOLD_INSIGHTS["periodic_vs_event"]
    if "interrupt" in q and "polling" in q: return GOLD_INSIGHTS["interrupt_vs_polling"]
    if "queue" in q and "semaphore" in q: return GOLD_INSIGHTS["queue_vs_semaphore"]
    if "isr" in q and "short" in q: return GOLD_INSIGHTS["short_isr_rationale"]

    # ADC
    if "done bit" in q: return GOLD_INSIGHTS["adc_done_bit"]
    if "start bit" in q: return GOLD_INSIGHTS["adc_start_behavior"]
    if "before done" in q: return GOLD_INSIGHTS["adc_read_before_done"]
    if "quantization" in q: return GOLD_INSIGHTS["adc_quantization"]
    if "sample" in q and "hold" in q: return GOLD_INSIGHTS["sample_hold"]
    if "averaging" in q: return GOLD_INSIGHTS["adc_averaging"]
    if "noise reduction" in q: return GOLD_INSIGHTS["adc_noise_reduction"]
    if "clock" in q and ("too low" in q or "low frequency" in q): return GOLD_INSIGHTS["adc_clock_low"]

    # Explicit high‑priority keyword triggers
    # pwm_mr1_gt_mr0 — expanded triggers
    if ("mr1" in q or "pwmmr1" in q) and ("mr0" in q or "pwmmr0" in q):
        return GOLD_INSIGHTS["pwm_mr1_gt_mr0"]
    if "mr1" in q and any(k in q for k in ["greater", "exceed", "larger", ">"]):
        return GOLD_INSIGHTS["pwm_mr1_gt_mr0"]

    # HC-SR04 timing rationale — must check before generic hcsr04_timing
    if ("hc-sr04" in q or "ultrasonic" in q) and any(
            k in q for k in ["why", "timing", "pulse", "require"]):
        return GOLD_INSIGHTS["hcsr04_why_timing"]
    # echo/distance only trigger sensor_integration if paired with hc-sr04/trig keywords
    if ("echo" in q or "distance" in q) and any(
            k in q for k in ["hc-sr04", "ultrasonic", "trig"]):
        return GOLD_INSIGHTS["hcsr04_timing"]
    if "hcsr04" in q or "hc-sr04" in q or "ultrasonic" in q:
        return GOLD_INSIGHTS["hcsr04_timing"]

    # MPU6050 calibration
    if "mpu6050" in q and any(k in q for k in ["calibrat", "bias", "offset"]):
        return GOLD_INSIGHTS["mpu6050_calibration"]

    # Sensor acquisition task priority
    if ("sensor" in q or "acquisition" in q) and any(
            k in q for k in ["priority", "higher priority", "highest"]):
        return GOLD_INSIGHTS["sensor_task_priority"]

    # FreeRTOS
    if "semaphore" in q and "queue" in q: return GOLD_INSIGHTS["queue_vs_semaphore"]
    if "priority inversion" in q or "priority" in q and "inversion" in q: return GOLD_INSIGHTS["freertos_priorities"]
    if "mutex" in q and ("isr" in q or "interrupt" in q): return GOLD_INSIGHTS["isr_safe_mutex"]
    if "printf" in q and ("isr" in q or "interrupt" in q): return GOLD_INSIGHTS["printf_in_isr"]
    if any(k in q for k in ["xqueuesend", "fromisr", "from isr", "from an isr", "isr safe", "isr-safe", "blocking api", "safely send", "isr to task", "send data from", "send from isr", "queue from isr", "semaphore from isr"]):
        return GOLD_INSIGHTS["isr_safe_apis"]
    if "queue" in q and ("overflow" in q or "full" in q): return GOLD_INSIGHTS["queue_overflow"]
    if "stack overflow" in q or ("stack" in q and "overflow" in q): return GOLD_INSIGHTS["stack_overflow"]
    if "tick" in q and ("scheduler" in q or "rtos" in q or "freertos" in q): return GOLD_INSIGHTS["scheduler_tick"]
    if "interrupt latency" in q or ("interrupt" in q and "latency" in q): return GOLD_INSIGHTS["interrupt_latency"]
    if "dma" in q: return GOLD_INSIGHTS["dma_basics"]
    if "task" in q and ("create" in q or "launch" in q or "signature" in q or "parameter" in q or "xtaskcreate" in q):
        return GOLD_INSIGHTS["freertos_task_creation"]
    if "queue" in q and ("work" in q or "how" in q or "basics" in q or "use" in q or "xqueue" in q):
        return GOLD_INSIGHTS["freertos_queue"]
    if "can bus" in q or "can" in q and ("bus" in q or "frame" in q or "identifier" in q):
        return GOLD_INSIGHTS["can_bus_basics"]

    # Sensors
    if "lm35" in q and "filter" in q: return GOLD_INSIGHTS["lm35_filtering"]
    if "lm35" in q and ("formula" in q or "conversion" in q or "temperature" in q or "voltage" in q):
        return GOLD_INSIGHTS["lm35_formula"]
    if "mpu6050" in q and ("register" in q or "i2c" in q or "address" in q or "0x6b" in q or "pwr" in q):
        return GOLD_INSIGHTS["mpu6050_registers"]

    # Pin Mapping
    if "pin" in q and ("mapping" in q or "out" in q or "map" in q):
        if "not" not in q and "no " not in q and "without" not in q:
            if "pwm" in q:
                # check channel
                channel_str = ""
                for ch in ["1", "2", "3", "4", "5", "6"]:
                    if ch in q:
                        channel_str = f"PWM{ch}"
                        break
                from app.services.templates import LPC2148_PWM_PIN_TABLE
                resp = (
                    "### Pin Mapping: LPC2148\n\n"
                    "The following pin mappings are verified for PWM channels on LPC2148:\n\n"
                    f"{LPC2148_PWM_PIN_TABLE}"
                )
                if channel_str:
                    resp += f"\n\n**Note:** You specifically asked for **{channel_str}**. See the corresponding row above."
                return resp

    # Register Map
    register_map = {
        "ad0cr": "ad0cr_role",
        "pinsel": "pinsel_function",
        "pwmmr0": "pwmmr0_purpose",
        "dlab": "uart_dlab",
        "pdn": "adc_pdn",
        "resolution": "adc_resolution",
        "noise": "adc_noise",
        "clock": "adc_clock_limit",
    }
    for keyword, key in register_map.items():
        if keyword in q: return GOLD_INSIGHTS[key]

    # Semantic Fallback — gated by allow_semantic flag
    if allow_semantic:
        query_embedding = model.encode(query, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, insight_embeddings)[0]
        best_idx = torch.argmax(cos_scores).item()
        if cos_scores[best_idx].item() > 0.72:
            return GOLD_INSIGHTS[insight_keys[best_idx]]

    return None
