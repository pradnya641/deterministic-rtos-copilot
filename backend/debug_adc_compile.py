import re
from app.services.architect import _adc_filtering_system, render_blueprint
from app.services.modifier import extract_state_from_response, _mod_convert_polling_to_isr
from app.routes.query import _safe_gcc_syntax_check, _extract_c_code

bp = _adc_filtering_system()
rendered = render_blueprint(bp)
state = extract_state_from_response("test_session", "Generate ADC acquisition", rendered, {"intent": "system_architecture"})

new_state, entries, explanation = _mod_convert_polling_to_isr(state, {})
c_code = _extract_c_code(new_state.generated_code)

comp_ok, comp_msg = _safe_gcc_syntax_check(c_code)
print("Compiler OK:", comp_ok)
print("Compiler msg:")
print(comp_msg)
