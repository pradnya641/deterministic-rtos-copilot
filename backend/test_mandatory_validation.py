import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_scenario_1_isr_safety_violation():
    # 1. Generate UART ISR architecture
    session_id = "test_s1"
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate UART ISR architecture"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] in ("success", "degraded")
    assert "UART0" in res_data["response"]
    
    # Keep track of generated code from first turn
    initial_code = res_data["architecture_snapshot"]["summary"]
    
    # 2. Try to use xSemaphoreTake inside ISR -> must reject
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "use xSemaphoreTake inside ISR"
    })
    assert response.status_code == 200
    res_data2 = response.json()
    assert res_data2["status"] == "error"
    assert "ISR Safety Violation" in res_data2["response"]
    assert "priority inheritance" in res_data2["response"].lower()
    
    # Check that previous state is preserved
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "increase queue depth to 32"
    })
    assert response.status_code == 200
    res_data3 = response.json()
    # Confirm it succeeded (meaning the session wasn't corrupted/lost by the rejection)
    assert res_data3["status"] == "success"


def test_scenario_2_generate_gps_gsm():
    session_id = "test_s2"
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate GPS GSM architecture"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] in ("success", "degraded")
    # Verify it created a telematics system with GPS/GSM
    snapshot = res_data["architecture_snapshot"]
    assert snapshot is not None
    # Telematics tracking has UART0 and UART1
    periphs = [p["peripheral"] for p in snapshot["peripherals"]]
    assert "UART0" in periphs
    assert "UART1" in periphs


def test_scenario_3_increase_queue_depth():
    session_id = "test_s3"
    # 1. Generate UART ISR architecture
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate UART ISR architecture"
    })
    assert response.status_code == 200
    
    # 2. Increase queue depth to 512
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "increase queue depth to 512"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    
    # Verify code and snapshot both show 512
    snapshot = res_data["architecture_snapshot"]
    assert snapshot["queues"][0]["depth"] == 512
    assert "512" in res_data["response"]


def test_scenario_4_convert_polling_to_interrupt():
    session_id = "test_s4"
    # 1. Generate polling sensor architecture
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate polling sensor architecture"
    })
    assert response.status_code == 200
    
    # 2. Convert polling to interrupt driven
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "convert polling to interrupt driven"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    
    # Verify EINT1 ISR is in snapshot and code
    snapshot = res_data["architecture_snapshot"]
    isrs = [isr["isr_name"] for isr in snapshot["isr_topology"]]
    assert "EINT1_IRQHandler" in isrs


def test_scenario_5_rms_optimization():
    session_id = "test_s5"
    # 1. Generate a system that has tasks with different periods (e.g. ADC moving average)
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate ADC Acquisition + Moving Average Filter"
    })
    assert response.status_code == 200
    
    # 2. Optimize priorities for RMS scheduling
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "optimize priorities for RMS scheduling"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    # Should optimize/verify priorities
    assert "RMS" in res_data["response"] or "Rate Monotonic" in res_data["response"]


def test_scenario_6_reduce_latency():
    session_id = "test_s6"
    # 1. Generate UART ISR architecture
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate UART ISR architecture"
    })
    assert response.status_code == 200
    
    # 2. Reduce latency
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "reduce latency"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    # Should optimize latency and have a detailed diff explanation
    assert "latency" in res_data["response"].lower()


def test_scenario_7_staged_replacement():
    session_id = "test_s7"
    # 1. Generate CAN architecture
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate CAN architecture"
    })
    assert response.status_code == 200
    
    # 2. Remove CAN and add LCD
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "remove CAN entirely and just display UART on LCD"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    
    snapshot = res_data["architecture_snapshot"]
    # Verify CAN is removed and LCD is added
    periphs = [p["peripheral"] for p in snapshot["peripherals"]]
    assert "CAN1" not in periphs
    assert "LCD" in periphs


def test_scenario_8_queue_overflow_detection():
    session_id = "test_s8"
    # 1. Generate UART architecture
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "Generate UART ISR architecture"
    })
    assert response.status_code == 200
    
    # 2. Add queue overflow detection
    response = client.post("/chat", json={
        "session_id": session_id,
        "text": "add queue overflow detection"
    })
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    
    snapshot = res_data["architecture_snapshot"]
    tasks = [t["name"] for t in snapshot["tasks"]]
    # Should add QueueMonitor task
    assert "QueueMonitor" in tasks
