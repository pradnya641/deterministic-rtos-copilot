import pytest
import re
from app.services.conversation_state import ConversationState, register_peripheral
from app.services.modifier import apply_modification, parse_removals_and_additions, apply_removals, validate_working_state

def test_removal_and_addition_flow():
    # TEST 1: Generate UART + CAN architecture -> remove CAN -> add LCD
    state = ConversationState(session_id="test_session_1")
    state.system_name = "UART + CAN test system"
    state.generated_code = """
#include <lpc214x.h>
#include "FreeRTOS.h"
#include "queue.h"

static QueueHandle_t xCANQueue;
static QueueHandle_t xRxQueue;

void CAN_IRQHandler(void) __attribute__((interrupt("IRQ")));
void CAN_IRQHandler(void) {
    VICVectAddr = 0;
}

void UART0_IRQHandler(void) __attribute__((interrupt("IRQ")));
void UART0_IRQHandler(void) {
    VICVectAddr = 0;
}

int main(void) {
    PINSEL0 |= 0x05; /* UART0 P0.0, P0.1 */
    PINSEL0 |= (1 << 0) | (1 << 2); /* CAN1 */
    
    VICVectAddr6 = (unsigned)UART0_IRQHandler;
    VICVectAddr23 = (unsigned)CAN_IRQHandler;
    
    xRxQueue = xQueueCreate(10, sizeof(uint8_t));
    xCANQueue = xQueueCreate(10, sizeof(uint8_t));
    
    vTaskStartScheduler();
}
"""
    # Initialize state collections
    state.tasks = [
        {"name": "UART0", "function": "UART0_IRQHandler", "priority": 5, "period_ms": 0, "stack_words": 128},
        {"name": "CAN1", "function": "CAN_IRQHandler", "priority": 5, "period_ms": 0, "stack_words": 128}
    ]
    state.queues = [
        {"name": "xRxQueue", "depth": 10, "item_type": "uint8_t"},
        {"name": "xCANQueue", "depth": 10, "item_type": "uint8_t"}
    ]
    state.isr_topology = [
        {"isr_name": "UART0_IRQHandler", "vic_channel": 6, "handler_fn": "UART0_IRQHandler", "queue_name": "xRxQueue", "peripheral": "UART0"},
        {"isr_name": "CAN_IRQHandler", "vic_channel": 23, "handler_fn": "CAN_IRQHandler", "queue_name": "xCANQueue", "peripheral": "CAN1"}
    ]
    register_peripheral(state, "UART0", "UART0_IRQHandler", vic_channel=6)
    register_peripheral(state, "CAN1", "CAN_IRQHandler", vic_channel=23)
    
    # Run modification: remove CAN entirely and add LCD
    query = "remove CAN entirely and just display UART on LCD"
    
    response, entries, new_state = apply_modification(state, "unknown", query)
    
    # Verify:
    # 1. CAN peripheral ownership is removed
    assert "CAN1" not in new_state.peripherals
    # 2. LCD peripheral is added
    assert "LCD" in new_state.peripherals
    # 3. CAN ISR is removed from topology
    assert not any(isr["peripheral"] == "CAN1" for isr in new_state.isr_topology)
    # 4. LCD task/peripheral is added
    assert any(t["name"] == "LCD" for t in new_state.tasks)
    # 5. C code no longer has CAN code but has LCD code
    assert "CAN_IRQHandler" not in new_state.generated_code
    assert "xCANQueue" not in new_state.generated_code
    assert "LCD_Init" in new_state.generated_code


def test_remove_uart_add_spi():
    # TEST 2: Remove UART1 -> add SPI
    state = ConversationState(session_id="test_session_2")
    state.system_name = "UART1 test system"
    state.generated_code = """
#include <lpc214x.h>
void UART1_Init(void) {
    PINSEL0 |= (0x5 << 16);
}
int main(void) {
    UART1_Init();
}
"""
    register_peripheral(state, "UART1", "vTaskUART1", vic_channel=7)
    state.isr_topology = [{"isr_name": "UART1_IRQHandler", "vic_channel": 7, "handler_fn": "UART1_IRQHandler", "queue_name": "xRxQueue1", "peripheral": "UART1"}]
    
    query = "remove UART1 and add SPI sensor"
    response, entries, new_state = apply_modification(state, "unknown", query)
    
    # Verify:
    assert "UART1" not in new_state.peripherals
    assert "SPI0" in new_state.peripherals
    assert not any(isr["peripheral"] == "UART1" for isr in new_state.isr_topology)
    assert "UART1_Init" not in new_state.generated_code
    assert "SPI_Init" in new_state.generated_code


def test_validation_failure_rollback():
    # TEST 3: Validation failure rollback
    state = ConversationState(session_id="test_session_3")
    state.system_name = "UART0 system"
    state.generated_code = """
#include <lpc214x.h>
int main(void) {
    PINSEL0 |= 0x05; /* UART0 */
}
"""
    register_peripheral(state, "UART0", "vTaskUART0", vic_channel=6)
    
    # Verify apply_modification rolls back cleanly on conflict
    query2 = "add PWM1"
    response2, entries2, final_state = apply_modification(state, "unknown", query2)
    
    # The session state must remain unchanged (rollback successful)
    assert final_state == state
    assert "Validation failed" in response2
    assert "PINSEL conflict" in response2


def test_dashboard_truthfulness():
    # TEST 4: Dashboard truthfulness
    state = ConversationState(session_id="test_session_4")
    state.generated_code = """
#include <lpc214x.h>
#include "FreeRTOS.h"
#include "queue.h"
static QueueHandle_t xRxQueue;
/* Only UART0 ISR exists in code, CAN is NOT generated */
void UART0_IRQHandler(void) __attribute__((interrupt("IRQ")));
void UART0_IRQHandler(void) {
    VICVectAddr = 0;
}
int main(void) {
    xRxQueue = xQueueCreate(10, sizeof(uint8_t));
}
"""
    # But in topology we have both registered
    state.isr_topology = [
        {"isr_name": "UART0_IRQHandler", "vic_channel": 6, "handler_fn": "UART0_IRQHandler", "queue_name": "xRxQueue", "peripheral": "UART0"},
        {"isr_name": "CAN_IRQHandler", "vic_channel": 23, "handler_fn": "CAN_IRQHandler", "queue_name": "xCANQueue", "peripheral": "CAN1"}
    ]
    
    # We simulate a turn or apply modification (e.g. retry logic)
    query = "add retry logic"
    state.queues = [{"name": "xRxQueue", "depth": 10, "item_type": "uint8_t"}]
    # Append queue send statement
    state.generated_code += "\nvoid foo(void) { xQueueSend(xRxQueue, &data, 0); }"
    
    response, entries, new_state = apply_modification(state, "add_retry_logic", query)
    
    # Verify tagging:
    uart_isr = next(isr for isr in new_state.isr_topology if isr["isr_name"] == "UART0_IRQHandler")
    can_isr = next(isr for isr in new_state.isr_topology if isr["isr_name"] == "CAN_IRQHandler")
    
    assert uart_isr["source"] == "explicit"
    assert can_isr["source"] == "inferred"
