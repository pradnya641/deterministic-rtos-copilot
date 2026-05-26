# Comparative Benchmark Summary

This report documents the performance evaluation of the **Deterministic Embedded RTOS Copilot** compared to the **Reference LLM Response Corpus** across 17 turns of conversational modification scenarios.

---

## 📊 Performance Comparison

| Metric | Deterministic Copilot | Reference LLM Corpus |
| --- | --- | --- |
| **Compile Success Rate** | **76.5% (13/17)** | 5.9% (1/17) |
| **Mutation Continuity Rate** | 70.6% (12/17) | **100.0% (17/17)** |
| **RTOS Safety Rate** | **100.0% (17/17)** | 5.9% (1/17) |
| **Rollbacks Triggered** | 1 | 0 |
| **Total Safety Violations** | **0** | 60 |

---

## 🔍 Key Findings & Failure Mode Analysis

The benchmark highlighted three critical categories of engineering failure modes in standard general-purpose LLM responses:

### 1. Register and Architecture Mismatches
General-purpose LLMs frequently mix up register structures between processor families:
* **Cortex-M and STM32 Mixups**: In 11 of the 17 turns, the Reference LLM used Cortex-M specific APIs (like `NVIC_EnableIRQ()`) and register accesses (like `UART0->DR` or `DMA1_Channel1->CPAR`) on the target bare-metal LPC2148 processor.
* **Arduino/AVR Mismatches**: The Reference LLM frequently pulled in Arduino APIs (like `analogRead()`, `attachInterrupt()`, or `Wire.begin()`) or AVR registers (like `WDTO_2S`), which fail compilation instantly.

### 2. Critical RTOS Safety Violations
In 16 of the 17 turns, the Reference LLM generated unsafe RTOS patterns that would result in deadlocks or kernel crashes in a real system:
* **Blocking inside ISR**: post/receive calls to queues (`xQueueSend`, `xQueueReceive`) and semaphores (`xSemaphoreTake`) were called inside ISR handlers (`UART0_Handler`, `sensor_isr`) without using the `FromISR` suffix and while specifying blocking wait times (`portMAX_DELAY` or `100`).
* **Stack Underflow**: Tasks were created with stack sizes under 68 words (e.g. 50 words). On the ARM7 processor, storing the CPU register context during context switching requires a minimum of 16 registers (64 bytes / 16 words) plus the task stack frame. A stack of 50 words leaves virtually no headroom, leading to an immediate stack overflow.
* **Priority Inversion**: Tasks were configured with priorities that violated Rate Monotonic Scheduling (RMS) rules—for instance, assigning the high-frequency IMU task a lower priority than the slow GSM task.

### 3. Accidental Architecture Loss
During modification turns, the Reference LLM re-generated the entire codebase from scratch, resulting in:
* **State Loss**: Forgetting watchdog configurations or auxiliary tasks when asked to add a new peripheral.
* **VIC Omissions**: Omiting the necessary interrupt acknowledgement `VICVectAddr = 0;` at the end of ISR routines, which prevents subsequent interrupts from firing.

---

## 🛡️ How the Deterministic Copilot Prevents Failures

The Deterministic Copilot addresses these gaps through:
1. **Structural Code Isolation**: Parsing queries to identify specific target components, applying edits via a clean staged diff pipeline, and preserving unaffected tasks/queues.
2. **Deterministic Constraint Rules**: Intercepting invalid configurations (like STM32 registers or Arduino API calls) at the keyword and semantic levels.
3. **Automated GCC Verification**: Compiling the code immediately inside a stubbed LPC2148 compiler path.
4. **Transactional Rollback**: Reverting the state atomically to the last known-good architecture if any compile check or compliance check fails.
