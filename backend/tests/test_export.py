import csv
import io
import json

from app.models import Call, TurnMetric
from app.services.export import COMMON_COLUMNS, CSV_COLUMNS, GEMINI_EXTRA_COLUMNS, SARVAM_TURN_COLUMNS, TURN_COLUMNS
from tests.conftest import save

# Copied from the Sarvam tester's export.py: the shared columns must not drift.
SARVAM_COMMON_COLUMNS = [
    "call_id", "pipeline", "mode", "form_id", "form_name", "started_at", "duration_s",
    "stt_model", "llm_model", "tts_model", "tts_voice", "language", "audio_quality",
    "field_id", "field_label", "required", "visible", "status", "saved_value", "confidence",
    "attempts", "review_verdict", "expected_value",
    "accuracy", "completion", "turns", "interruptions", "avg_response_ms", "max_response_ms",
    "tool_calls", "tool_calls_failed", "json_parse_failures", "est_cost_inr",
]


def _setup_call(client, db, call_id):
    save(client, call_id, "caller_name", "Test User")
    save(client, call_id, "age", "35")
    save(client, call_id, "attended_sessions", "no")
    db.add(TurnMetric(call_id=call_id, turn_index=0, total_ms=None, agent_text="Namaste"))  # greeting
    db.add(TurnMetric(call_id=call_id, turn_index=1, total_ms=700, stop_source="energy", user_text="Test", agent_text="Ok"))
    db.add(TurnMetric(call_id=call_id, turn_index=2, total_ms=1100, stop_source="energy"))
    call = db.get(Call, call_id)
    call.audio_input_tokens, call.audio_output_tokens = 1_000_000, 100_000
    db.commit()
    client.post(f"/api/calls/{call_id}/review", json={"reviews": [
        {"field_id": "caller_name", "verdict": "correct"},
        {"field_id": "age", "verdict": "wrong", "expected_value": "36"},
    ]})


def test_shared_columns_match_sarvam():
    assert COMMON_COLUMNS == SARVAM_COMMON_COLUMNS
    assert CSV_COLUMNS[: len(COMMON_COLUMNS)] == COMMON_COLUMNS  # shared first, extras last
    assert CSV_COLUMNS[len(COMMON_COLUMNS):] == GEMINI_EXTRA_COLUMNS
    assert TURN_COLUMNS[: len(SARVAM_TURN_COLUMNS)] == SARVAM_TURN_COLUMNS


def test_csv_export(client, db, call_id):
    _setup_call(client, db, call_id)
    res = client.get(f"/api/calls/{call_id}/export?format=csv")
    assert res.status_code == 200
    rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert list(rows[0].keys()) == CSV_COLUMNS
    by_field = {r["field_id"]: r for r in rows}
    assert len(rows) == 12  # one row per form field
    age = by_field["age"]
    assert age["pipeline"] == "gemini_live" and age["llm_model"] == "gemini-3.8-live"
    assert age["stt_model"] == "native-audio" and age["tts_voice"] == "Kore"
    assert age["review_verdict"] == "wrong" and age["expected_value"] == "36"
    assert by_field["sessions_attended_count"]["status"] == "not_applicable"
    assert by_field["reason_not_attended"]["status"] == "pending"
    assert age["accuracy"] == "0.5"  # 1 correct of 2 reviewed
    assert age["turns"] == "2"  # caller turns only; the greeting is not a turn
    assert age["avg_response_ms"] == "900.0" and age["max_response_ms"] == "1100.0"
    # 1M audio-in tokens x $3 + 0.1M audio-out x $12 = $4.20 -> x 88 INR
    assert age["est_cost_usd"] == "4.2" and age["est_cost_inr"] == "369.6"


def test_turns_csv(client, db, call_id):
    _setup_call(client, db, call_id)
    res = client.get(f"/api/calls/{call_id}/export?format=csv&section=turns")
    rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert list(rows[0].keys()) == TURN_COLUMNS
    assert [r["total_ms"] for r in rows] == ["", "700.0", "1100.0"]
    assert rows[1]["stt_ms"] == ""  # no separate STT step in speech-to-speech


def test_json_export(client, db, call_id):
    _setup_call(client, db, call_id)
    data = json.loads(client.get(f"/api/calls/{call_id}/export?format=json").content)
    assert data["call"]["pipeline"] == "gemini_live"
    assert len(data["rows"]) == 12 and len(data["turns"]) == 3
    assert data["metrics"]["completion"] is not None
    assert data["metrics"]["cost"]["currency"] == "INR"
    assert "GEMINI_API_KEY" not in json.dumps(data)


def test_tool_call_fields_in_report(client, call_id):
    save(client, call_id, "age", "150")
    tool = client.get(f"/api/calls/{call_id}").json()["tool_calls"][-1]
    assert tool["success"] is False and tool["scheduling"] == "INTERRUPT"
    assert {"timed_out", "retries", "gemini_call_id", "agent_speaking_at_call"} <= tool.keys()


def test_review_can_be_removed(client, db, call_id):
    _setup_call(client, db, call_id)
    state = client.post(f"/api/calls/{call_id}/review",
                        json={"reviews": [{"field_id": "age", "verdict": None}]}).json()
    assert next(f for f in state["fields"] if f["id"] == "age")["review"] is None


def test_unknown_call_404(client):
    assert client.get("/api/calls/nope/export?format=csv").status_code == 404
