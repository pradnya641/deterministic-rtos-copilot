# Deterministic Embedded RTOS Copilot

A deterministic embedded systems engineering copilot for LPC2148 (ARM7TDMI-S) and FreeRTOS 8.x.

The framework performs deterministic RTOS-aware architecture generation, staged firmware mutation, compiler-assisted validation, and hardware constraint enforcement for embedded firmware pipelines.

Unlike general-purpose LLM code generation systems, this copilot preserves architectural consistency across conversational modifications while enforcing RTOS scheduling semantics, ISR safety rules, peripheral ownership constraints, and embedded hardware validation checks.

---

# Overview

The system is designed to support conversational embedded firmware engineering while maintaining deterministic architectural integrity during iterative modifications.

The framework combines:

- RTOS-aware architecture generation
- Stateful conversational mutation
- Compiler-assisted firmware validation
- Deterministic rollback and recovery
- Hardware-aware constraint analysis
- Embedded retrieval-augmented reasoning (RAG)

Target platform:

- LPC2148 (ARM7TDMI-S)
- FreeRTOS 8.x
- ARM GCC Embedded Toolchain

---

# Core Capabilities

## Deterministic Intent Routing

Queries are classified using a structured routing pipeline that identifies:

- RTOS scheduling requests
- Peripheral interfacing tasks
- ISR modification requests
- Driver generation
- Architecture mutation operations
- Hardware debugging workflows

The routing engine prevents unsafe cross-domain mutations during iterative conversational edits.

---

## Stateful Architecture Mutation

The framework maintains persistent conversational firmware state and applies modifications using staged deterministic mutation.

Mutation stages include:

1. Dependency analysis
2. Resource conflict detection
3. Removal staging
4. Architecture rewrite
5. Validation passes
6. Rollback protection

This prevents common LLM failure modes such as:

- register corruption
- duplicate peripheral ownership
- task desynchronization
- invalid queue topology
- RTOS priority conflicts

---

## RTOS-Aware Validation Engine

Generated firmware is validated against embedded systems constraints including:

- ISR-safe API usage
- FreeRTOS scheduling semantics
- Queue synchronization correctness
- Stack allocation constraints
- RMS priority violations
- VIC interrupt acknowledgement requirements
- PINSEL overlap conflicts
- Peripheral ownership collisions

---

## Compiler-Assisted Verification

All generated firmware blocks are validated using:

```bash
arm-none-eabi-gcc -mcpu=arm7tdmi -fsyntax-only
```

Validation is performed against:

- LPC2148 vendor headers
- FreeRTOS kernel headers
- RTOS queue/task APIs
- Peripheral interface stubs

This ensures generated firmware remains syntactically valid under realistic embedded compilation constraints.

---

## Transactional Rollback Protection

If validation or compilation fails:

- the architecture mutation is rejected
- the previous known-good state is restored
- inconsistent firmware states are prevented

This enables deterministic conversational architecture evolution.

---

# Project Structure

```text
deterministic-rtos-copilot/
│
├── backend/
│   │   server.py
│   │
│   ├── api/
│   │       query.py
│   │
│   ├── core/
│   │   ├── db/
│   │   ├── engine/
│   │   ├── models/
│   │   └── routes/
│   │
│   ├── benchmarks/
│   ├── evaluation/
│   ├── scripts/
│   ├── sdk/
│   ├── tests/
│   └── devtools/
│
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
│
├── docs/
│   ├── architecture.md
│   ├── mutation_engine.md
│   ├── evaluation_framework.md
│   └── reference/
│
├── reports/
│
├── README.md
├── LICENSE
├── requirements.txt
└── .gitignore
```

---

# Engine Architecture

The deterministic reasoning engine is composed of multiple specialized modules.

## Core Engine Modules

```text
architect.py
modifier.py
validator.py
router.py
rag.py
conversation_state.py
```

### Responsibilities

| Module | Responsibility |
|---|---|
| architect.py | RTOS architecture generation |
| modifier.py | Stateful firmware mutation |
| validator.py | Embedded constraint enforcement |
| router.py | Intent routing and query classification |
| rag.py | Retrieval-augmented embedded knowledge access |
| conversation_state.py | Stateful conversational architecture tracking |

---

# Example RTOS Pipeline

Example generated architecture:

```text
UART0 RX ISR
    ↓
xQueueSendFromISR()
    ↓
Parser Task
    ↓
Command Dispatcher Task
    ↓
Motor Control Task
```

Validation checks include:

- ISR-safe queue usage
- priority inversion analysis
- stack allocation verification
- scheduling consistency
- peripheral ownership validation

---

# Embedded Knowledge Base

The system includes indexed reference material for:

- LPC2148 hardware
- FreeRTOS kernel behavior
- RTOS synchronization APIs
- embedded communication protocols
- sensor datasheets
- embedded coding standards

Reference material is stored under:

```text
docs/reference/
```

---

# Quick Start

## Requirements

- Python 3.10+
- ARM GCC Embedded Toolchain
- FastAPI
- FreeRTOS-compatible ARM toolchain

---

# Backend Setup

```bash
cd backend

pip install -r ../requirements.txt

python -m uvicorn server:app --port 8000 --reload
```

---

# Frontend Dashboard

Open:

```text
frontend/index.html
```

The dashboard connects to the FastAPI backend and visualizes:

- conversational interactions
- RTOS task topology
- peripheral routing
- architecture relationships

---

# Running Evaluations

Run comparative evaluation suites:

```bash
cd backend

$env:PYTHONPATH="."

python evaluation/run_comparative_eval.py
```

Evaluation suites test:

- conversational consistency
- architecture mutation stability
- rollback correctness
- RTOS safety enforcement
- scheduling validation accuracy

---

# Benchmark Focus Areas

The benchmark framework evaluates:

- RTOS reasoning
- embedded hardware correctness
- conversational state preservation
- architecture mutation accuracy
- deterministic rollback behavior
- protocol configuration validity
- scheduling consistency

---

# Safety Constraints Enforced

The framework explicitly prevents:

- blocking APIs inside ISRs
- invalid RTOS task priorities
- unsafe interrupt synchronization
- duplicate peripheral mappings
- invalid queue access patterns
- stack under-allocation
- unsafe scheduler mutations

---

# Target Use Cases

- RTOS firmware prototyping
- conversational firmware mutation
- embedded architecture generation
- ISR/task pipeline generation
- hardware debugging assistance
- educational RTOS experimentation
- embedded systems validation research

---

# Future Improvements

Planned extensions include:

- STM32 platform support
- Zephyr RTOS integration
- static timing analysis
- CAN/LIN protocol validation
- multicore scheduling support
- hardware-in-the-loop validation
- automated architecture visualization

---

# License

This project is licensed under the MIT License.

See:

```text
LICENSE
```
