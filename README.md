# Deterministic Embedded RTOS Copilot

A deterministic conversational embedded systems co-pilot for LPC2148 (ARM7TDMI-S) and FreeRTOS 8.x.

This copilot provides robust, verified, and state-preserving conversational mutations to firmware architectures, preventing the bugs, register mixups, and invalid scheduling priorities common in standard general-purpose LLM generations.

---

## 🚀 Key Features

* **Deterministic Intent Routing**: Classifies queries using a structured routing pipeline to target hardware, RTOS configuration, code generation, or hardware debugging.
* **Staged Architecture Mutation**: Executes modifications in a transactional manner—processing removals first, resetting state indicators, applying additions, and running rigorous multi-level checks.
* **Atomic Transactional Rollback**: If compilation or validation checks fail, the system rolls back to the last known-good state automatically.
* **Fair Compiler Validation**: Automatically compiles every generated firmware block using `arm-none-eabi-gcc -mcpu=arm7tdmi -fsyntax-only` against FreeRTOS and LPC2148 vendor header stubs.
* **RTOS & Hardware Compliance Auditor**: Detects blocking calls in interrupts, stack size underflows (<68 words), Rate Monotonic Scheduling (RMS) priority inversions, missing VIC acknowledgements, and PINSEL pin overlap conflicts.

---

## 📁 Project Structure

```text
deterministic-rtos-copilot/
│
├── backend/
│   ├── app/                      # FastAPI Backend server
│   │   ├── main.py               # Main application entrypoint
│   │   ├── models/               # Pydantic schemas and dataclasses
│   │   ├── routes/               # API endpoints (/chat, /ask, etc.)
│   │   └── services/             # Core engines (architect, modifier, validator, etc.)
│   │
│   ├── benchmarks/               # Stress tests and benchmark suites
│   ├── evaluation/               # Regression and Comparative evaluation suites
│   │   ├── reference_chatgpt/    # Real conversational baseline snapshots
│   │   ├── results/              # Evaluation results and logs
│   │   ├── comparative_reporter.py # Report generator (HTML/MD/DOCX)
│   │   └── run_comparative_eval.py # Main testbed runner
│   │
│   ├── scripts/                  # Compiler check stubs and tools
│   ├── tests/                    # Integration and unit tests
│   ├── sdk/                      # Header and library mock files
│   ├── requirements.txt          # Python requirements list
│   └── run_eval.py               # Regression evaluation runner entry
│
├── frontend/                     # Interactive HTML/JS Web Dashboard
│   ├── index.html                # Sidebar architecture layout & chat
│   ├── style.css                 # Dark HSL theme design
│   └── script.js                 # API bridge and SVG topology renderer
│
├── docs/                         # Engineering Documentation
│   ├── architecture.md           # Application design and RAG integration
│   ├── mutation_engine.md        # Transactional staged modification detail
│   └── evaluation_framework.md   # Sandbox compiler & metrics scoreboard
│
├── reports/                      # Output Reports & Scorecard
│   ├── comparison_report_sample.html # Sample generated HTML comparison report
│   └── benchmark_summary.md      # Summary of copilot vs general LLM baseline
│
├── README.md                     # Main project guide
├── LICENSE                       # MIT License
└── .gitignore                    # Python version-control filters
```

---

## 🛠️ Quick Start

### 1. Requirements
* Python 3.10+
* ARM GCC Toolchain (to run local syntax compilation checks, configured in `app/routes/query.py`)

### 2. Backend Installation & Run
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
python -m uvicorn app.main:app --port 8000 --reload
```

### 3. Frontend Dashboard
Simply open `frontend/index.html` in your web browser. The dashboard connects to the live FastAPI backend on port 8000, displaying the conversational chat side-by-side with an SVG-rendered peripheral and RTOS task topology graph.

### 4. Running the Benchmarks
To execute the automated comparative evaluation against the general-purpose LLM response corpus:
```bash
# From the backend directory:
$env:PYTHONPATH="."; python evaluation/run_comparative_eval.py
```
This runs 17 turns of conversational requests, compiles code blocks for both sides, evaluates metrics, and outputs comparison scorecards to `evaluation/comparison_results/`.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
