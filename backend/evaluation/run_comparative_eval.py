import os
import json
import time
import re
from fastapi.testclient import TestClient
from app.main import app
from app.routes.query import _extract_c_code, _safe_gcc_syntax_check

client = TestClient(app)

SCENARIOS = {
    1: {
        "name": "UART ISR Pipeline -> Watchdog -> SPI",
        "turns": [
            "Generate UART ISR architecture",
            "Increase queue depth to 64",
            "Add overflow protection",
            "Optimize latency",
            "Add watchdog",
            "Remove UART",
            "Add SPI"
        ]
    },
    2: {
        "name": "Polling -> Interrupt -> Mutex -> CAN -> LCD",
        "turns": [
            "Generate polling sensor architecture",
            "Convert polling to interrupt-driven",
            "Add mutex protection",
            "Add CAN telemetry",
            "Replace CAN with LCD"
        ]
    },
    3: {
        "name": "GPS + GSM -> Fusion -> DMA -> Stack -> RMS",
        "turns": [
            "Generate GPS + GSM architecture",
            "Add sensor fusion",
            "Add DMA",
            "Reduce stack usage",
            "Optimize RMS priorities"
        ]
    }
}

def ensure_dirs():
    os.makedirs("evaluation/comparison_results/traces", exist_ok=True)

def analyze_c_code(code, scenario_idx, turn_idx, query):
    if not code:
        return {
            "tasks": [],
            "queues": 0,
            "semaphores": 0,
            "mutexes": 0,
            "violations": ["No code generated"],
            "avr_arduino_mismatch": False,
            "wrong_register_arch": False,
            "unsafe_isr_call": False,
            "stack_underflow": False,
            "rms_violation": False,
            "vic_ack_omission": False,
            "pinsel_conflict": False
        }
        
    violations = []
    
    # 1. Parse tasks: xTaskCreate(vFunction, "Name", StackSize, Parameter, Priority, Handle)
    tasks_raw = re.findall(r'xTaskCreate\s*\(\s*(\w+)\s*,\s*(?:"([^"]*)"|(\w+))\s*,\s*([^,]+)\s*,\s*[^,]+\s*,\s*([^,]+)', code)
    tasks = []
    for match in tasks_raw:
        func = match[0]
        name = match[1] if match[1] else match[2]
        stack = match[3].strip()
        priority = match[4].strip()
        tasks.append({
            "function": func,
            "name": name,
            "stack": stack,
            "priority": priority
        })
        
    # 2. Parse queues
    queues = re.findall(r'xQueueCreate\s*\(', code)
    
    # 3. Parse semaphores / mutexes
    semaphores = re.findall(r'xSemaphoreCreateBinary\s*\(', code)
    mutexes = re.findall(r'xSemaphoreCreateMutex\s*\(', code)
    
    # 4. Check for AVR/Arduino headers and APIs
    avr_arduino_mismatch = False
    if "#include <avr/wdt.h>" in code or "wdt_enable" in code or "wdt_reset" in code:
        avr_arduino_mismatch = True
        violations.append("AVR Watchdog API (<avr/wdt.h>) used on ARM7 target")
    if "#include <SPI.h>" in code or "SPI.begin" in code or "SPI.transfer" in code:
        avr_arduino_mismatch = True
        violations.append("Arduino SPI API (<SPI.h>) used on bare-metal LPC2148")
    if "#include <Wire.h>" in code or "Wire.begin" in code or "Wire.beginTransmission" in code:
        avr_arduino_mismatch = True
        violations.append("Arduino Wire (I2C) API (<Wire.h>) used on bare-metal LPC2148")
    if "#include <LiquidCrystal.h>" in code or "LiquidCrystal" in code or "lcd.begin" in code or "lcd.print" in code:
        avr_arduino_mismatch = True
        violations.append("Arduino LiquidCrystal API (<LiquidCrystal.h>) used on bare-metal LPC2148")
    if "analogRead" in code or "analogWrite" in code or "digitalWrite" in code or "digitalRead" in code or "pinMode" in code or "attachInterrupt" in code:
        avr_arduino_mismatch = True
        violations.append("Arduino pin/peripheral abstraction API used on bare-metal LPC2148")
        
    # 5. Check for Cortex-M/STM32 style register access
    wrong_register_arch = False
    if "NVIC_EnableIRQ" in code or "NVIC_DisableIRQ" in code:
        wrong_register_arch = True
        violations.append("Cortex-M NVIC interrupt controller API used on ARM7 target")
    if "DMA1_Channel1" in code or "DMA1" in code:
        wrong_register_arch = True
        violations.append("STM32 DMA registers (DMA1_Channel1) configured on LPC2148 target")
    if "UART0->DR" in code or "USART1" in code:
        wrong_register_arch = True
        violations.append("Cortex-M/STM32 style UART registers (DR/USART1) used on LPC2148 target")
        
    # 6. Check for unsafe RTOS calls inside ISR
    unsafe_isr_call = False
    isr_matches = re.finditer(r'void\s+(\w*(?:Handler|isr|ISR))\s*\([^\)]*\)\s*\{', code)
    for match in isr_matches:
        func_name = match.group(1)
        start_idx = match.end()
        bracket_count = 1
        body_chars = []
        for idx in range(start_idx, len(code)):
            char = code[idx]
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            body_chars.append(char)
        body = "".join(body_chars)
        
        if "xQueueSend" in body and "FromISR" not in body:
            unsafe_isr_call = True
            violations.append(f"Blocking queue call (xQueueSend) inside ISR {func_name} (must use FromISR variant)")
        if "xQueueReceive" in body and "FromISR" not in body:
            unsafe_isr_call = True
            violations.append(f"Blocking queue call (xQueueReceive) inside ISR {func_name} (must use FromISR variant)")
        if "xSemaphoreGive" in body and "FromISR" not in body:
            unsafe_isr_call = True
            violations.append(f"Blocking semaphore call (xSemaphoreGive) inside ISR {func_name} (must use FromISR variant)")
        if "xSemaphoreTake" in body:
            unsafe_isr_call = True
            violations.append(f"Blocking semaphore call (xSemaphoreTake) inside ISR {func_name} (illegal in ISR)")
        if "vTaskDelay" in body:
            unsafe_isr_call = True
            violations.append(f"Blocking delay (vTaskDelay) inside ISR {func_name}")
        if "portMAX_DELAY" in body:
            unsafe_isr_call = True
            violations.append(f"Blocking wait time (portMAX_DELAY) inside ISR {func_name}")
            
    # 7. Check for VIC acknowledgement omission in ISR
    vic_ack_omission = False
    isr_matches = re.finditer(r'void\s+(\w*(?:Handler|isr|ISR))\s*\([^\)]*\)\s*\{', code)
    for match in isr_matches:
        func_name = match.group(1)
        start_idx = match.end()
        bracket_count = 1
        body_chars = []
        for idx in range(start_idx, len(code)):
            char = code[idx]
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            body_chars.append(char)
        body = "".join(body_chars)
        
        if "Handler" in func_name or "isr" in func_name:
            if "VICVectAddr" not in body and not avr_arduino_mismatch:
                vic_ack_omission = True
                violations.append(f"VIC interrupt acknowledgement (VICVectAddr = 0) omitted in ISR {func_name}")
                
    # 8. Check for stack underflow (stack < 68 words)
    stack_underflow = False
    for task in tasks:
        try:
            sz = int(task["stack"])
            if sz < 68:
                stack_underflow = True
                violations.append(f"Task '{task['name']}' has unsafe stack size {sz} words (minimum 68 words required for ARM7 context)")
        except ValueError:
            pass
            
    # 9. Rate Monotonic Scheduling (RMS) Priority Violation (Scenario 3 specific)
    rms_violation = False
    if scenario_idx == 3:
        gps_prio = None
        imu_prio = None
        gsm_prio = None
        for task in tasks:
            try:
                p = int(task["priority"])
                name = task["name"].lower()
                if "gps" in name:
                    gps_prio = p
                elif "imu" in name:
                    imu_prio = p
                elif "gsm" in name:
                    gsm_prio = p
            except ValueError:
                pass
        if gps_prio is not None and imu_prio is not None and gsm_prio is not None:
            if not (imu_prio > gps_prio > gsm_prio):
                rms_violation = True
                violations.append(f"RMS scheduling priority violation: IMU ({imu_prio}) must be > GPS ({gps_prio}) > GSM ({gsm_prio})")
                
    # 10. Check PINSEL pins conflicts
    pinsel_conflict = False
    if "PINSEL1" in code and "CAN1" in code and "UART" in code:
        pass
        
    return {
        "tasks": [t["name"] for t in tasks],
        "queues": len(queues),
        "semaphores": len(semaphores),
        "mutexes": len(mutexes),
        "violations": violations,
        "avr_arduino_mismatch": avr_arduino_mismatch,
        "wrong_register_arch": wrong_register_arch,
        "unsafe_isr_call": unsafe_isr_call,
        "stack_underflow": stack_underflow,
        "rms_violation": rms_violation,
        "vic_ack_omission": vic_ack_omission,
        "pinsel_conflict": pinsel_conflict
    }

def check_continuity(scenario_idx, turn_idx, query, current_tasks, prev_tasks):
    lost_tasks = []
    is_removal = "remove" in query.lower() or "replace" in query.lower()
    removed_keywords = []
    if "remove uart" in query.lower():
        removed_keywords.extend(["uart", "process", "processor"])
    elif "replace can" in query.lower():
        removed_keywords.extend(["can"])
    
    for pt in prev_tasks:
        should_be_removed = False
        for kw in removed_keywords:
            if kw in pt.lower():
                should_be_removed = True
                break
        
        if not should_be_removed:
            found = False
            for ct in current_tasks:
                if ct.lower() == pt.lower() or pt.lower() in ct.lower() or ct.lower() in pt.lower():
                    found = True
                    break
            if not found:
                lost_tasks.append(pt)
                
    return lost_tasks

def run_evaluation():
    ensure_dirs()
    print("=" * 60)
    print("STARTING COMPARATIVE CONVERSATIONAL EVALUATION RUNNER")
    print("=" * 60)
    
    results = []
    
    for sc_idx, sc_info in SCENARIOS.items():
        print(f"\nRunning Scenario {sc_idx}: {sc_info['name']}")
        print("-" * 50)
        
        # Unique session ID for each scenario to verify state preservation
        session_id = f"comparative_sc{sc_idx}_{int(time.time())}"
        
        sc_turns = []
        copilot_prev_tasks = []
        ref_prev_tasks = []
        
        for turn_idx, query in enumerate(sc_info["turns"], 1):
            print(f"  Turn {turn_idx}: '{query}'")
            
            # ─────────────────────────────────────────────────────────────────
            # COPILOT EVALUATION (Live FastAPI backend via TestClient)
            # ─────────────────────────────────────────────────────────────────
            start_time = time.time()
            res = client.post("/chat", json={
                "session_id": session_id,
                "text": query
            })
            latency_ms = int((time.time() - start_time) * 1000)
            
            assert res.status_code == 200, f"HTTP Error {res.status_code}"
            res_data = res.json()
            
            copilot_status = res_data.get("status")
            copilot_response = res_data.get("response", "")
            copilot_diff = res_data.get("diff", "")
            
            copilot_code = _extract_c_code(copilot_response)
            copilot_compile_ok = False
            copilot_compile_msg = "No code block found"
            
            if copilot_code:
                copilot_compile_ok, copilot_compile_msg = _safe_gcc_syntax_check(copilot_code)
                
            copilot_analysis = analyze_c_code(copilot_code, sc_idx, turn_idx, query)
            copilot_rollback = (copilot_status == "error")
            
            # Check mutation continuity
            copilot_lost_tasks = check_continuity(sc_idx, turn_idx, query, copilot_analysis["tasks"], copilot_prev_tasks)
            copilot_continuity_ok = len(copilot_lost_tasks) == 0
            copilot_prev_tasks = copilot_analysis["tasks"]
            
            # ─────────────────────────────────────────────────────────────────
            # REFERENCE LLM EVALUATION (Replayed snapshot)
            # ─────────────────────────────────────────────────────────────────
            ref_path = f"evaluation/reference_chatgpt/sc{sc_idx}_turn{turn_idx}.json"
            with open(ref_path, "r", encoding="utf-8") as f:
                ref_data = json.load(f)
                
            ref_response = ref_data.get("response", "")
            ref_code = _extract_c_code(ref_response)
            
            ref_compile_ok = False
            ref_compile_msg = "No code block found"
            if ref_code:
                ref_compile_ok, ref_compile_msg = _safe_gcc_syntax_check(ref_code)
                
            ref_analysis = analyze_c_code(ref_code, sc_idx, turn_idx, query)
            
            # Reference has no live rollback mechanism
            ref_rollback = False
            
            ref_lost_tasks = check_continuity(sc_idx, turn_idx, query, ref_analysis["tasks"], ref_prev_tasks)
            ref_continuity_ok = len(ref_lost_tasks) == 0
            ref_prev_tasks = ref_analysis["tasks"]
            
            turn_results = {
                "turn": turn_idx,
                "query": query,
                "copilot": {
                    "response": copilot_response,
                    "code": copilot_code,
                    "diff": copilot_diff,
                    "compile_ok": copilot_compile_ok,
                    "compile_msg": copilot_compile_msg,
                    "rollback_triggered": copilot_rollback,
                    "continuity_ok": copilot_continuity_ok,
                    "lost_tasks": copilot_lost_tasks,
                    "latency_ms": latency_ms,
                    **copilot_analysis
                },
                "reference": {
                    "response": ref_response,
                    "code": ref_code,
                    "compile_ok": ref_compile_ok,
                    "compile_msg": ref_compile_msg,
                    "rollback_triggered": ref_rollback,
                    "continuity_ok": ref_continuity_ok,
                    "lost_tasks": ref_lost_tasks,
                    "latency_ms": 0,
                    **ref_analysis
                }
            }
            sc_turns.append(turn_results)
            
            # Print turn summary
            print(f"    Copilot   - Compile: {copilot_compile_ok}, Rollback: {copilot_rollback}, Continuity: {copilot_continuity_ok}, Violations: {len(copilot_analysis['violations'])}")
            print(f"    Reference - Compile: {ref_compile_ok}, Rollback: {ref_rollback}, Continuity: {ref_continuity_ok}, Violations: {len(ref_analysis['violations'])}")
            
        results.append({
            "scenario": sc_idx,
            "name": sc_info["name"],
            "turns": sc_turns
        })
        
    # Save the trace results
    trace_path = "evaluation/comparison_results/traces/comparison_trace.json"
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nTrace results written to {trace_path}")
    
    # Import and run reporter to generate final reports
    from evaluation.comparative_reporter import generate_reports
    generate_reports(results)

if __name__ == "__main__":
    run_evaluation()
