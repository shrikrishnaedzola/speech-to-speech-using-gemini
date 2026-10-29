"""Build the Gemini system instruction from the selected form and language.

Nothing about the form is hard-coded here: field ids, questions, rules and
ranges all come from the form JSON. The base text is the one from the test
brief (same as the OpenAI and Sarvam testers), plus tool rules for async calls.

Native-audio Live models choose the spoken language themselves and don't take a
language code, so the language is set here, in the instruction
(https://ai.google.dev/gemini-api/docs/live-guide).
"""

from app.config import LANGUAGE_NAMES

BASE_INSTRUCTIONS = """You are a polite, friendly survey assistant calling on behalf of an NGO program. \
Speak in {language}. If the caller mixes Hindi and English (Hinglish) or another language with English, \
reply naturally in the same style. Keep sentences short and simple.
- Greet the caller, explain the call takes about {minutes} minutes, and ask if it is a good time to talk.
- Ask ONE question at a time, in the order of the form.
- After each answer, call save_answer right away. Do not wait until the end.
- Do not move to the next question if the last save_answer returned an error; ask that question again politely.
- Ask follow-up questions only when the form rules say so.
- If an answer is unclear or out of range, politely ask again.
- If the caller corrects an earlier answer, update it with save_answer.
- Before ending, read back the key answers briefly and ask the caller to confirm. Then call complete_form.
- Never ask for phone numbers, ID numbers, bank details or addresses.
- If the caller wants to stop, thank them and end politely."""

TOOL_RULES = """How to use the tools:
- save_answer: send numbers as digits (for example "35", not "thirty five"), lists as digits separated by \
commas ("5, 8"), yes/no questions as "yes" or "no", choice questions as the exact option name in English. \
Use confidence "low" if you are not sure you heard correctly.
- Do not wait in silence after calling save_answer: in the same reply, briefly acknowledge the answer and ask \
the next question.
- Tool results can arrive while you are already speaking. If a result has "ok": false, stop and do what its \
"error" says: politely ask that question again, even if you already started the next question.
- A successful save_answer returns "next_question". That is the next question to ask, in the conversation language.
- complete_form may return "missing_fields". Ask those, one at a time, then call complete_form again.
- skip_field is only for optional fields the caller does not want to answer.
- Never say field ids, tool names, JSON or the word "field" out loud."""


def _language_phrase(language_code: str) -> str:
    if language_code == "auto":
        return (
            "the caller's language. Greet in simple English, then from the caller's first reply use "
            "the same language and style the caller uses"
        )
    return LANGUAGE_NAMES.get(language_code, language_code)


def _describe_rule(rule: dict) -> str:
    ops = {"eq": "is", "ne": "is not", "gt": "is more than", "gte": "is at least", "lt": "is less than",
           "lte": "is at most", "in": "is one of"}
    return f'ask ONLY if {rule["field"]} {ops.get(rule["op"], rule["op"])} "{rule["value"]}"'


def describe_field(field: dict) -> str:
    """One line per field, e.g.: - age (number, required, 18 to 100): "What is your age?" """
    kind = {"number_list": "list of numbers", "yes_no": "yes or no"}.get(field["type"], field["type"])
    parts = [kind, "required" if field.get("required") else "optional"]
    if field["type"] == "number" and ("min" in field or "max" in field):
        parts.append(f"{field.get('min', '')} to {field.get('max', '')}")
    if field["type"] == "choice":
        parts.append("options: " + ", ".join(field["choices"]))
    if field.get("show_if"):
        parts.append(_describe_rule(field["show_if"]))
    if field.get("length_equals_field"):
        parts.append(f"must have exactly {field['length_equals_field']} values")
    question = field.get("question", field["label"])
    return f'- {field["id"]} ({"; ".join(parts)}): "{question}"'


def build_system_prompt(form: dict, language_code: str) -> str:
    instructions = BASE_INSTRUCTIONS.format(
        language=_language_phrase(language_code), minutes=form.get("estimated_minutes", 3)
    )
    fields = "\n".join(describe_field(f) for f in form["fields"])
    return (
        f"{instructions}\n\n"
        f"Form: {form['name']}\n"
        f"Questions in order (translate them into the conversation language):\n{fields}\n\n"
        f"{TOOL_RULES}"
    )


# Sent as a user turn right after connecting, so the agent speaks first.
GREETING_TRIGGER = "(The phone call has just connected. Greet the caller now.)"


def resume_message(state: dict, next_q: dict | None) -> str:
    """Context for a NEW Gemini session after a drop when the old session could not be resumed.

    Args:
        state: form_state() of the call (the saved answers are the source of truth).
        next_q: next_question() hint, or None if every visible field is answered.
    """
    saved = [f"{f['id']} = {f['value']}" for f in state["fields"]
             if f["visible"] and f["status"] in ("filled", "needs_confirmation")]
    lines = [
        "(The call dropped and has just reconnected. Do NOT greet again and do NOT re-ask saved answers.",
        "Already saved: " + ("; ".join(saved) if saved else "nothing yet") + ".",
    ]
    if next_q:
        lines.append(f"Say sorry for the break in one short sentence, then ask: {next_q['question']})")
    else:
        lines.append("Say sorry for the break, then read back the answers and ask the caller to confirm.)")
    return "\n".join(lines)
