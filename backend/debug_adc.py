import re
from app.services.architect import _adc_filtering_system, render_blueprint
from app.services.modifier import extract_state_from_response, _mod_convert_polling_to_isr

bp = _adc_filtering_system()
rendered = render_blueprint(bp)
state = extract_state_from_response("test_session", "Generate ADC acquisition", rendered, {"intent": "system_architecture"})

new_state, entries, explanation = _mod_convert_polling_to_isr(state, {})
print("Entries count:", len(entries))
for i, entry in enumerate(entries):
    print(f"Entry {i}:")
    print(f"  file_section: {entry.file_section}")
    print(f"  old_line: {repr(entry.old_line)}")
    print(f"  new_line: {entry.new_line.encode('ascii', errors='replace').decode('ascii')!r}")
    print(f"  reason: {entry.reason.encode('ascii', errors='replace').decode('ascii')}")
    print(f"  rtos_impact: {entry.rtos_impact.encode('ascii', errors='replace').decode('ascii')}")
