# Conversational Mutation Engine

This document explains the design and operational rules of the **Staged Mutation Engine**, which handles conversational firmware modification with strict type and hardware safety.

---

## ⚙️ The Challenge: State Preservation
Standard LLMs regenerate code blocks from scratch on every turn. This leads to accidental resets, register conflicts, and lost variables. The co-pilot solves this by utilizing a **Staged Mutation Flow** that operates on an active architecture graph.

---

## 🔄 The Staged Mutation Flow

Every code modification request is processed in the following atomic stages:

```text
  [Active State]
         │
         ▼
  1. Clone State ─────► [Working State]
                             │
                             ▼
  2. Removals First ──► Release PINSEL bits, VIC slots & Delete Code Blocks
                             │
                             ▼
  3. Sync State ──────► Re-extract active tasks/queues from clean code
                             │
                             ▼
  4. Additions ───────► Allocate hardware resources & Inject new code blocks
                             │
                             ▼
  5. Validate ────────► Audit against LPC2148 and FreeRTOS rules
       │
       ├───► [FAIL] ──► Discard Working State (Transactional Rollback)
       │
       └───► [PASS] ──► Merge & Save to Active Store (Commit)
```

### Stage Details
1. **State Cloning**: The current active session state is cloned into a temporary `working_state`.
2. **Removals First**: If a user requests to replace or remove a peripheral (e.g. "replace CAN with LCD"), the engine processes the removal first. This prevents false PINSEL conflicts by releasing the pins and interrupts used by the old peripheral *before* validating the new one.
3. **State Synchronization**: Re-parses the intermediate code to synchronize the list of active tasks, queues, and semaphores.
4. **Additions/Modifications**: Adds the new components, dynamically mapping available hardware pins and interrupt controller slots.
5. **Auditing & Verification**: Checks the mutated code for compiler validity and registers conflicts.
6. **Commit/Rollback**: If validation fails, the active state remains unchanged. If validation passes, changes are saved.

---

## 🔌 Hardware Resource Allocation (LPC2148)

The mutation engine manages two critical hardware layers:

### 1. Pin Connect Block (PINSEL)
LPC2148 pins are multiplexed using `PINSEL0` and `PINSEL1` registers. 
* **Pin Allocation Table**:
  * `UART0`: `P0.0` (TXD0) and `P0.1` (RXD0). Requires setting `PINSEL0` bits [1:0] = `01` and [3:2] = `01`.
  * `SPI0`: `P0.4` (SCK0), `P0.5` (MISO0), `P0.6` (MOSI0), `P0.7` (SSEL0). Configured in `PINSEL0` bits [9:8], [11:10], [13:12], and [15:14].
  * `CAN1`: `P0.25` (RD1) and `P0.26` (TD1). Configured in `PINSEL1` bits [19:18] and [21:20].
* **Overlap Check**: Before allocating pins, the modifier queries the peripheral ownership table. If the requested pin bits are already written with another value, the mutation is rejected.

### 2. Vectored Interrupt Controller (VIC)
The VIC handles 16 vectored interrupt slots (`VICVectAddr0` to `VICVectAddr15` and `VICVectCntl0` to `VICVectCntl15`).
* **Vectored Slots**: The modifier tracks which slot is allocated to which interrupt source (e.g., UART0, Timer1, EINT0).
* **Collision Check**: If a mutation attempts to assign an interrupt handler to an already-occupied slot, or assigns the same peripheral to multiple slots, the modifier flags a collision and rejects the query.
* **Interrupt Acknowledge**: Every vectored ISR must execute `VICVectAddr = 0;` at exit to clear the interrupt flag. The compliance validator checks for this instruction inside generated ISR bodies.
