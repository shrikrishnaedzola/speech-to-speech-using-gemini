import pytest

from app.config import DEFAULT_CALL_SETTINGS
from app.services.scheduling import choose_scheduling, effective_behavior
from app.services.tool_schema import gemini_tools

LIVE = {**DEFAULT_CALL_SETTINGS, "model": "gemini-3.8-live"}
THINKING = {**DEFAULT_CALL_SETTINGS, "model": "gemini-3.8-live-extended-thinking"}
OK, ERROR = {"ok": True}, {"ok": False, "error": "Age must be at most 100"}


@pytest.mark.parametrize("tool", ["save_answer", "skip_field", "request_clarification"])
def test_auto_success_is_silent_while_agent_talks(tool):
    assert choose_scheduling(LIVE, tool, OK, agent_busy=True) == "SILENT"


@pytest.mark.parametrize("tool", ["save_answer", "skip_field", "request_clarification"])
def test_auto_success_wakes_a_waiting_agent(tool):
    # The agent called the tool and went quiet: SILENT would leave dead air.
    assert choose_scheduling(LIVE, tool, OK, agent_busy=False) == "WHEN_IDLE"


@pytest.mark.parametrize("mode", ["SILENT", "WHEN_IDLE"])
def test_fixed_modes_ignore_agent_state(mode):
    settings = {**LIVE, "save_ok_scheduling": mode}
    assert choose_scheduling(settings, "save_answer", OK, agent_busy=True) == mode
    assert choose_scheduling(settings, "save_answer", OK, agent_busy=False) == mode


@pytest.mark.parametrize("tool", ["save_answer", "skip_field", "request_clarification", "complete_form"])
def test_any_error_interrupts(tool):
    assert choose_scheduling(LIVE, tool, ERROR) == "INTERRUPT"


def test_complete_form():
    assert choose_scheduling(LIVE, "complete_form", OK) == "WHEN_IDLE"
    missing = {"ok": False, "missing_fields": [{"field_id": "age"}]}
    assert choose_scheduling(LIVE, "complete_form", missing) == "INTERRUPT"


def test_extended_thinking_has_no_scheduling():
    # Its model page: only NON_BLOCKING, scheduling not supported.
    assert choose_scheduling(THINKING, "save_answer", ERROR) is None
    assert effective_behavior({**THINKING, "tool_behavior": "BLOCKING"}) == "NON_BLOCKING"


def test_blocking_has_no_scheduling():
    blocking = {**LIVE, "tool_behavior": "BLOCKING"}
    assert choose_scheduling(blocking, "save_answer", ERROR) is None
    assert effective_behavior(blocking) == "BLOCKING"


def test_declarations_carry_behavior():
    decls = gemini_tools(["age"], "NON_BLOCKING")[0].function_declarations
    assert [d.name for d in decls] == ["save_answer", "request_clarification", "skip_field", "complete_form"]
    assert all(d.behavior.value == "NON_BLOCKING" for d in decls)
    assert decls[0].parameters_json_schema["properties"]["field_id"]["enum"] == ["age"]
