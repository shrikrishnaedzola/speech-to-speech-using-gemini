"""Choose the FunctionResponse `scheduling` for each tool result.

With asynchronous (NON_BLOCKING) tools the model keeps talking while our tool
runs. `scheduling` tells it what to do when our answer arrives
(https://ai.google.dev/gemini-api/docs/live-tools):

    SILENT     add the result to the context, say nothing now
    WHEN_IDLE  speak about it after the current sentence/turn ends
    INTERRUPT  stop talking now and react to the result

Our rules:
    save_answer / skip_field / request_clarification OK -> AUTO (setting: or always SILENT / WHEN_IDLE)
        AUTO looks at the agent when our result is ready:
        - still speaking -> SILENT: it already moved on to the next question;
          speaking about "saved" would interrupt the flow.
        - silent -> WHEN_IDLE: it called the tool and is waiting for the result.
          SILENT here would leave dead air until the caller speaks again
          (seen in live tests: gemini-3.8-live often waits after save_answer).
    complete_form OK                                     -> WHEN_IDLE
        The agent should thank the caller and say goodbye after its current sentence.
    any error (validation failed, missing fields, timeout) -> INTERRUPT
        The agent may already be asking the NEXT question. It must stop and
        re-ask the failed one now, or the answer is lost.

Notes:
- The prompt writes this as "INTERRUPTED"; the API value is "INTERRUPT".
- gemini-3.8-live-extended-thinking does not support scheduling (model page),
  so None is returned and the field is left out. There, only the error text in
  the result and the system instruction make the agent re-ask.
- Scheduling only applies to NON_BLOCKING tools; with BLOCKING the model waits
  for every result anyway, so it is left out too.
"""

from app.config import MODEL_INFO

SILENT, WHEN_IDLE, INTERRUPT = "SILENT", "WHEN_IDLE", "INTERRUPT"


def choose_scheduling(settings: dict, tool_name: str, result: dict, agent_busy: bool = False) -> str | None:
    """Return SILENT / WHEN_IDLE / INTERRUPT, or None to leave scheduling out.

    Args:
        settings: The call settings (model, tool_behavior, save_ok_scheduling).
        tool_name: Which tool ran.
        result: The tool result dict ({"ok": bool, ...}).
        agent_busy: True if the agent is still generating or playing audio right now.
    """
    model = MODEL_INFO.get(settings.get("model"), {})
    if not model.get("supports_scheduling"):
        return None
    if settings.get("tool_behavior", "NON_BLOCKING") != "NON_BLOCKING":
        return None
    if not result.get("ok"):
        return INTERRUPT
    if tool_name == "complete_form":
        return WHEN_IDLE
    mode = settings.get("save_ok_scheduling", "AUTO")
    if mode == "AUTO":
        return SILENT if agent_busy else WHEN_IDLE
    return mode


def effective_behavior(settings: dict) -> str:
    """BLOCKING is only allowed on models that support scheduling (gemini-3.8-live)."""
    model = MODEL_INFO.get(settings.get("model"), {})
    if not model.get("supports_scheduling"):
        return "NON_BLOCKING"  # extended-thinking: only NON_BLOCKING is supported
    return settings.get("tool_behavior", "NON_BLOCKING")
