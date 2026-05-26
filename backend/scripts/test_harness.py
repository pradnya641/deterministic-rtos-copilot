import os
import re
import subprocess
import shutil

# Paths
workspace_dir = r"c:\genai_project\backend"
harness_dir = os.path.join(workspace_dir, "scripts", "harness_tests")
include_dir = os.path.join(harness_dir, "include")
sdk_dir = os.path.join(workspace_dir, "sdk")
report_path = r"C:\Users\puroh\.gemini\antigravity-ide\brain\7a165bed-5d85-4b01-931e-c8fe550ff96d\code_comparison_report.md"
gcc_path = r"C:\Users\puroh\.gemini\antigravity-ide\scratch\arm-gcc\xpack-arm-none-eabi-gcc-13.2.1-1.1\bin\arm-none-eabi-gcc.exe"
build_results_path = r"C:\Users\puroh\.gemini\antigravity-ide\brain\7a165bed-5d85-4b01-931e-c8fe550ff96d\build_results.md"

# 1. Create directories
os.makedirs(include_dir, exist_ok=True)

# 2. Generate FreeRTOS and lpc2148 stub headers for syntax-only check
stubs = {}
stubs["FreeRTOS.h"] = """#ifndef FREERTOS_H
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
"""

stubs["task.h"] = """#ifndef COOS_TASK_H
#define COOS_TASK_H
#include "FreeRTOS.h"
typedef void (*TaskFunction_t)(void *);
BaseType_t xTaskCreate(TaskFunction_t pvTaskCode, const char * const pcName, unsigned short usStackDepth, void *pvParameters, UBaseType_t uxPriority, void **pxCreatedTask);
void vTaskStartScheduler(void);
void vTaskDelay(const TickType_t xTicksToDelay);
TickType_t xTaskGetTickCount(void);
#endif
"""

stubs["queue.h"] = """#ifndef COOS_QUEUE_H
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
"""

stubs["semphr.h"] = """#ifndef COOS_SEMPHR_H
#define COOS_SEMPHR_H
#include "FreeRTOS.h"
typedef void * SemaphoreHandle_t;
SemaphoreHandle_t xSemaphoreCreateMutex(void);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
BaseType_t xSemaphoreTake(SemaphoreHandle_t xSemaphore, TickType_t xTicksToWait);
BaseType_t xSemaphoreGive(SemaphoreHandle_t xSemaphore);
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t xSemaphore, BaseType_t * const pxHigherPriorityTaskWoken);
BaseType_t xSemaphoreTakeFromISR(SemaphoreHandle_t xSemaphore, BaseType_t * const pxHigherPriorityTaskWoken);
#endif
"""

stubs["lpc214x.h"] = """#ifndef LPC214X_H
#define LPC214X_H
#include <stdint.h>
extern volatile uint32_t U0RBR;
extern volatile uint32_t VICVectAddr;
extern volatile uint32_t PINSEL0;
extern volatile uint32_t U0LCR;
extern volatile uint32_t U0DLL;
extern volatile uint32_t U0IER;
extern volatile uint32_t VICVectAddr6;
extern volatile uint32_t VICVectCntl6;
extern volatile uint32_t VICIntEnable;
extern volatile uint32_t IO0SET;
extern volatile uint32_t IO0CLR;
extern volatile uint32_t IO0PIN;
extern volatile uint32_t T1TC;
extern volatile uint32_t PWMMR1;
extern volatile uint32_t PWMMR2;
extern volatile uint32_t PWMLER;
extern volatile uint32_t IO0DIR;
extern volatile uint32_t PWMMR0;
extern volatile uint32_t PWMMCR;
extern volatile uint32_t PWMPCR;
extern volatile uint32_t PWMTCR;
extern volatile uint32_t T1TCR;
extern volatile uint32_t AD0CR;
extern volatile uint32_t AD0DR1;
extern volatile uint32_t PINSEL1;
extern volatile uint32_t CAN1RID;
extern volatile uint32_t CAN1RFS;
extern volatile uint32_t CAN1RDA;
extern volatile uint32_t CAN1RDB;
extern volatile uint32_t CAN1CMR;
extern volatile uint32_t CAN1MOD;
extern volatile uint32_t CAN1BTR;
extern volatile uint32_t VICVectAddr23;
extern volatile uint32_t VICVectCntl23;
extern volatile uint32_t CAN1IER;
extern volatile uint32_t S0SPCR;
extern volatile uint32_t S0SPCCR;
extern volatile uint32_t S0SPDR;
extern volatile uint32_t S0SPSR;

extern volatile uint32_t EXTINT;
extern volatile uint32_t EXTMODE;
extern volatile uint32_t EXTPOLAR;

extern volatile uint32_t VICVectAddr0;
extern volatile uint32_t VICVectAddr1;
extern volatile uint32_t VICVectAddr2;
extern volatile uint32_t VICVectAddr3;
extern volatile uint32_t VICVectAddr4;
extern volatile uint32_t VICVectAddr5;
extern volatile uint32_t VICVectAddr7;
extern volatile uint32_t VICVectAddr8;
extern volatile uint32_t VICVectAddr9;
extern volatile uint32_t VICVectAddr10;
extern volatile uint32_t VICVectAddr11;
extern volatile uint32_t VICVectAddr12;
extern volatile uint32_t VICVectAddr13;
extern volatile uint32_t VICVectAddr14;
extern volatile uint32_t VICVectAddr15;

extern volatile uint32_t VICVectCntl0;
extern volatile uint32_t VICVectCntl1;
extern volatile uint32_t VICVectCntl2;
extern volatile uint32_t VICVectCntl3;
extern volatile uint32_t VICVectCntl4;
extern volatile uint32_t VICVectCntl5;
extern volatile uint32_t VICVectCntl7;
extern volatile uint32_t VICVectCntl8;
extern volatile uint32_t VICVectCntl9;
extern volatile uint32_t VICVectCntl10;
extern volatile uint32_t VICVectCntl11;
extern volatile uint32_t VICVectCntl12;
extern volatile uint32_t VICVectCntl13;
extern volatile uint32_t VICVectCntl14;
extern volatile uint32_t VICVectCntl15;
#endif
"""

stubs["uart.h"] = "/* Empty uart.h stub */\n"
stubs["Wire.h"] = "/* Empty Wire.h stub */\n"
stubs["CAN.h"] = "/* Empty CAN.h stub */\n"
stubs["SPI.h"] = "/* Empty SPI.h stub */\n"

for name, content in stubs.items():
    path = os.path.join(include_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
print("Stub headers written.")

# 3. Parse report and extract code blocks
with open(report_path, "r", encoding="utf-8") as f:
    report_content = f.read()

sections = report_content.split("\n## Query ")
queries_data = []

query_keys = {
    1: "Q1 UART ISR",
    2: "Q2 GPS/GSM",
    3: "Q3 Sensor Fusion",
    4: "Q4 Autonomous Robot",
    5: "Q5 ADC Filtering",
    6: "Q6 Queue Overflow",
    7: "Q7 Ring Buffer",
    8: "Q8 CAN Telemetry",
    9: "Q9 SPI DMA",
    10: "Q10 Motor Control"
}

for idx, sec in enumerate(sections[1:], 1):
    lines = sec.split("\n")
    title_line = lines[0]
    m = re.match(r"^(\d+)\s*[:.]\s*(.*)", title_line)
    if not m:
        continue
    query_num = int(m.group(1))
    title = m.group(2)
    
    code_blocks = []
    in_block = False
    current_block = []
    for line in lines[1:]:
        if line.strip().startswith("```c"):
            in_block = True
            current_block = []
        elif line.strip().startswith("```") and in_block:
            in_block = False
            code_blocks.append("\n".join(current_block))
        elif in_block:
            current_block.append(line)
            
    if len(code_blocks) >= 2:
        queries_data.append({
            "index": query_num,
            "title": title,
            "assistant_code": code_blocks[0],
            "engine_code": code_blocks[1]
        })

print(f"Parsed {len(queries_data)} queries successfully.")

def classify_linker_error(stderr):
    stderr_lower = stderr.lower()
    if "region" in stderr_lower and "overflowed by" in stderr_lower:
        return "Section Overflow (Flash/RAM limit exceeded)"
    elif "undefined reference to" in stderr_lower:
        symbols = re.findall(r"undefined reference to `([^']+)'", stderr)
        sym_str = f" ({', '.join(symbols)})" if symbols else ""
        return f"Undefined Linker Symbol{sym_str}"
    elif "abi" in stderr_lower or "uses hardware fp" in stderr_lower or "conflicts with" in stderr_lower:
        return "ARM7 ABI Compatibility Issue"
    elif "naked" in stderr_lower or "interrupt" in stderr_lower:
        return "Naked Function / Stack Nesting Constraints Violation"
    elif "multiple definition of" in stderr_lower:
        return "Multiple Symbol Definitions"
    elif "assertion failed" in stderr_lower or "assert" in stderr_lower:
        return "Linker Assertion Failure"
    elif "cannot open linker script" in stderr_lower:
        return "Missing Linker Script"
    elif "no such file or directory" in stderr_lower:
        files = re.findall(r"([^:\s\\]+): No such file or directory", stderr)
        file_str = f" ({', '.join(files)})" if files else ""
        return f"Missing Required Header{file_str}"
    else:
        # Check if there are compiler/syntax error snippets in stderr
        errors = []
        for line in stderr.split("\n"):
            if "error:" in line:
                parts = line.split("error:", 1)
                errors.append(parts[1].strip())
        if errors:
            return "Compiler Error: " + "; ".join(errors[:2])
        return "Linker / Compilation Failure"

def syntax_check_file(filepath):
    cmd = [
        gcc_path,
        "-mcpu=arm7tdmi",
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-fsyntax-only",
        f"-I{include_dir}",
        filepath
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        exit_code = res.returncode
        stderr = res.stderr
    except Exception as e:
        return "FAIL", f"Syntax runner error: {str(e)}"
        
    errors = []
    warnings = []
    for line in stderr.split("\n"):
        line = line.strip()
        if "error:" in line:
            parts = line.split("error:", 1)
            msg = parts[1].strip()
            if msg not in errors:
                errors.append(msg)
        elif "warning:" in line:
            parts = line.split("warning:", 1)
            msg = parts[1].strip()
            if msg not in warnings:
                warnings.append(msg)
                
    if exit_code != 0:
        return "FAIL", "; ".join(errors[:2])
    elif len(warnings) > 0:
        return "WARNINGS", "; ".join(warnings[:2])
    else:
        return "PASS", "Syntax OK"

def sdk_compile_file(filepath):
    # Run make clean
    subprocess.run("make clean", cwd=sdk_dir, shell=True, capture_output=True, text=True)
    
    # Run make TARGET_C=<filepath>
    filepath_normalized = filepath.replace("\\", "/")
    cmd = f"make TARGET_C={filepath_normalized}"
    try:
        res = subprocess.run(cmd, cwd=sdk_dir, shell=True, capture_output=True, text=True, timeout=15)
        exit_code = res.returncode
        stderr = res.stderr
        stdout = res.stdout
    except Exception as e:
        return "FAIL", f"Make runner error: {str(e)}"
    
    # Check if firmware.elf was generated and exit code is 0
    elf_path = os.path.join(sdk_dir, "firmware.elf")
    if exit_code == 0 and os.path.exists(elf_path):
        # Move elf to harness_tests to preserve it
        dest_elf = filepath.replace(".c", ".elf")
        if os.path.exists(dest_elf):
            os.remove(dest_elf)
        shutil.move(elf_path, dest_elf)
        return "PASS", "Linked successfully"
    else:
        err_msg = classify_linker_error(stderr)
        return "FAIL", err_msg

# 5. Compile each query code block
results = []
for q in queries_data:
    idx = q["index"]
    query_key = query_keys.get(idx, f"Q{idx}")
    
    # Save files
    assistant_file = os.path.join(harness_dir, f"query_{idx}_assistant.c")
    engine_file = os.path.join(harness_dir, f"query_{idx}_engine.c")
    
    # Helper to check if file contains main, if not append it
    def write_with_main_check(dest_path, code):
        if not re.search(r"\bmain\s*\(", code):
            code += "\n\n/* Automatically appended main stub for SDK link verification */\nint main(void) {\n    return 0;\n}\n"
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(code)
            
    write_with_main_check(assistant_file, q["assistant_code"])
    write_with_main_check(engine_file, q["engine_code"])
        
    # Run tests
    eng_syntax_status, eng_syntax_details = syntax_check_file(engine_file)
    asst_syntax_status, asst_syntax_details = syntax_check_file(assistant_file)
    
    eng_sdk_status, eng_sdk_details = sdk_compile_file(engine_file)
    asst_sdk_status, asst_sdk_details = sdk_compile_file(assistant_file)
    
    results.append({
        "query": query_key,
        "eng_syntax": eng_syntax_status,
        "eng_sdk": eng_sdk_status,
        "asst_syntax": asst_syntax_status,
        "asst_sdk": asst_sdk_status,
        "eng_details": eng_sdk_details,
        "asst_details": asst_sdk_details
    })
    
    print(f"Processed {query_key}:")
    print(f"  Engine   : Syntax={eng_syntax_status}, SDK={eng_sdk_status} (Details: {eng_sdk_details})")
    print(f"  Assistant: Syntax={asst_syntax_status}, SDK={asst_sdk_status} (Details: {asst_sdk_details})")

# 6. Generate build_results.md
md_table = []
md_table.append("# Build Verification Results (Phase A)\n")
md_table.append("This report documents the verification results of ChatGPT/Assistant and Deterministic Engine code blocks compiled against the **real FreeRTOS LPC2148 SDK**.\n")
md_table.append("## Verification Levels Definition\n")
md_table.append("- **Syntax-valid**: The code compiles syntax-wise (equivalent to `-fsyntax-only` using basic stubs).\n")
md_table.append("- **SDK-valid**: The code compiles and links cleanly against the real SDK, generating a valid ARM7 ELF.\n")
md_table.append("\n## Build & Link Matrix\n")
md_table.append("| Query | Engine Syntax | Engine SDK-Link | Assistant Syntax | Assistant SDK-Link | Details / Linker Failure Class |")
md_table.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

for r in results:
    details_str = f"Engine: {r['eng_details']}; Assistant: {r['asst_details']}"
    md_table.append(f"| {r['query']} | {r['eng_syntax']} | {r['eng_sdk']} | {r['asst_syntax']} | {r['asst_sdk']} | {details_str} |")

with open(build_results_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_table))

print(f"\nBuild results written to {build_results_path}")
