# Evaluation Framework & Compiler Validation

This document describes the automated comparative testing, compiler verification sandbox, and scorecard metrics used by the **Comparative Conversational Evaluation System**.

---

## 🧪 Automated Testing Design

The evaluation framework consists of:
1. **Reference LLM Response Corpus (`evaluation/reference_chatgpt/`)**: A frozen set of 17 turns across 3 scenarios, containing real conversational interactions from general-purpose LLMs on identical prompts.
2. **FastAPI TestClient**: Executes live co-pilot chat turns in-process, maintaining session memory across turns.
3. **Comparative Evaluation Runner (`run_comparative_eval.py`)**: Runs turns sequentially, extracts code blocks from both sides, compiles them under identical rules, performs static compliance auditing, and computes comparative metrics.
4. **Comparative Report Generator (`comparative_reporter.py`)**: Generates Markdown, HTML, and Word (DOCX) scoreboard reports.

---

## ⚙️ Fair Compiler Sandbox

To ensure 100% fair and credible compilation checks:
* **Identical Parser**: Both the Copilot and Reference LLM responses are parsed using the same `_extract_c_code` markdown parser.
* **Shared Cross-Compiler Toolchain**: Both generated code blocks are compiled inside a temporary scratch folder using:
  ```bash
  arm-none-eabi-gcc -mcpu=arm7tdmi -std=c99 -fsyntax-only -Iscripts/harness_tests/include
  ```
* **LPC2148 / FreeRTOS Stubs**: Located in `scripts/harness_tests/include`, these stub headers provide correct declarations for LPC2148 registers (e.g. `AD0CR`, `U0RBR`, `VICVectAddr`) and FreeRTOS APIs (e.g. `xTaskCreate`, `xQueueSendFromISR`), allowing bare-metal compilation checks on any host machine.

---

## 📊 Scorecard Metrics

The runner evaluates four core engineering dimensions:

### 1. Compile Success Rate
* **Metric**: Ratio of turns that compile with zero syntax errors.
* **Significance**: General-purpose LLMs often produce STM32/Cortex-M register definitions (like `USART1->DR`) or Arduino/AVR API mappings (like `digitalWrite`), which fail compilation on an LPC2148 target.

### 2. Mutation Continuity Rate
* **Metric**: Ratio of turns where all active, un-modified tasks/queues are preserved from the previous turn.
* **Significance**: Detects "accidental resets" where the LLM forgets the watchdog or auxiliary tasks when asked to modify unrelated modules.

### 3. RTOS & Platform Safety Rate
* **Metric**: Ratio of turns with zero safety auditor violations.
* **Audited Violations**:
  * **Blocking in ISR**: Use of blocking calls (`vTaskDelay`, `xQueueSend`, `xSemaphoreTake`, or `portMAX_DELAY`) inside interrupt handlers.
  * **ISR API variants**: Omission of the `FromISR` suffix on queue/semaphore APIs inside ISRs.
  * **Stack Sizing**: Tasks created with stack sizes under 68 words (which causes instant ARM7 context overflow).
  * **Rate Monotonic Scheduling (RMS)**: Violations of frequency-based priority assignments.
  * **Interrupt Acknowledgement**: Omission of clearing `VICVectAddr` at the end of vectored ISR handlers.

### 4. Rollback Success Rate
* **Metric**: Ability of the transaction manager to reject unsafe inputs and restore the last valid architecture state.
