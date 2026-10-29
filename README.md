# Zolabs Voice Form Tester – Gemini 3.8 Live

An **internal test tool**, not for production use. It checks how well Google's Gemini 3.8 Live
speech-to-speech models run a phone-style survey call. The agent asks the form's questions one by one,
asks follow-ups and saves the answers as structured data through tool calls. Every turn and every tool
call is timed.

It uses the same form, tools, 3-column layout and export columns as the Sarvam tester
(`../voice agent with sarwam`), so results can go into one spreadsheet.

```
Browser mic (16 kHz PCM) ──WS /ws/call──► FastAPI backend ──Live API WebSocket──► Gemini 3.8 Live
Browser speaker ◄── 24 kHz PCM ─────────── (holds the API key, runs every tool call, times everything)
```

> **TEST MODE – use dummy data only.** Never use real names, phone numbers, Aadhaar numbers or any real
> beneficiary data.

---

## 1. Setup (Windows, macOS or Linux)

You need **Python 3.11 or 3.12** and **Node 18 or newer**.

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
# open backend/.env and set GEMINI_API_KEY=<your key>

# Frontend
cd ../frontend
npm install
```

The backend reads the API key **only** from `backend/.env`, which is git-ignored. The browser never sees
the key. It only talks to our backend, which talks to Gemini. Error messages are scrubbed of the key
before they are logged or shown.

## 2. Run

Use two terminals:

```bash
# Terminal 1 – backend on http://localhost:8020
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8020

# Terminal 2 – frontend on http://localhost:5190 (forwards /api and /ws to the backend)
cd frontend
npm run dev
```

Open **http://localhost:5190**. The ports avoid the Sarvam tester's (8010 and 5180), so both can run at
the same time. To change them, edit `frontend/vite.config.js` and `CORS_ORIGINS` in `.env`.

## 3. Run a test call

1. **Try Simulate first. It is free.** Click **Simulate**. It replays a saved dummy Hinglish call
   (`backend/app/simulate/sample_call.json`) through the **real** tool, validation and scheduling code,
   without the mic or Gemini. The timings in this mode are made up. The dummy call includes:
   - a rejected answer (age 150, sent back with `INTERRUPT`),
   - a malformed tool call,
   - a barge-in,
   - a dropped connection,
   - a correction (2 children → 3).
2. **Live call.** Choose the form, model, voice, language and audio quality. Click **Start Call** and
   allow the microphone. Use a headset to avoid echo. The agent speaks first.
3. **While the call runs:**
   - Column 1 shows the transcript, from Gemini's input and output transcription.
   - Column 2 fills in the form cards. Follow-up questions appear only when their condition is met.
   - Column 3 shows the response time per turn and every tool call, with its scheduling, its time and
     whether the agent kept talking during it.
   - **Test drop** closes the Gemini connection on purpose. The backend reconnects with the latest session
     resumption handle, and the saved answers stay in place.
4. **After the call:** in Column 2, mark each answer **Correct** or **Wrong**. Typing an expected value
   marks it Wrong automatically. Then use **Export JSON / CSV / Turns CSV**.
   - **Accuracy** = correct ÷ reviewed filled fields.
   - **Completion** = filled required fields ÷ visible required fields.

**Comparing models:** run the same script once with `gemini-3.8-live` and once with
`gemini-3.8-live-extended-thinking`. Each call stores its settings, and the export has `llm_model` on
every row.

**Phone 8 kHz** band-limits both directions to 300–3400 Hz and drops to 8 kHz with a G.711 mu-law round
trip. It then goes back up to the rate Gemini needs, because the Live API only accepts 16 kHz input
(`backend/app/services/audio.py`).

## 4. Tests

```bash
cd backend
.venv\Scripts\python -m pytest
```

129 tests, no network and no key needed. They cover:
- field validation
- follow-up conditions
- spoken numbers ("teen", "moonu", "do saal", native digits)
- the scheduling choice for each result and model
- `complete_form`'s missing-field check
- the export columns, including a check that the shared columns still match Sarvam's
- phone-line filtering

`tests/test_live_call.py` runs the real session code against a **fake Gemini connection**. It checks:
- a rejected answer gets `INTERRUPT` with the same function-call id;
- timeouts and retries are logged;
- response time is measured;
- a dropped connection resumes with the latest handle without losing answers.

---

## 5. Design choices

### Connection: Option A (backend proxy), not ephemeral tokens

- **Tool calls arrive at the backend directly.** Validate → save → `FunctionResponse` with the same id
  happens in one process. Option B would need the browser to forward every tool call back to us.
- **One clock.** End of caller speech, first agent audio and tool time are all measured with
  `time.perf_counter()` in one place.
- **The key stays on the server.** Ephemeral tokens are still **Preview**. The docs say they are v1beta
  only, while google-genai 2.33 prints a warning that its token support is **v1alpha** only. That
  mismatch is one more reason to avoid them for now.
- **Downside:** one extra hop. On localhost it is about 1 ms. Response times are measured in the backend,
  so this hop and the browser's ~50 ms playback buffer are **not** included.

### Tool calls and scheduling

All four tools are declared with `behavior: NON_BLOCKING`, so the model keeps talking while our tool
runs. Every result goes back as a `FunctionResponse` with **the same `id`** Gemini sent. The id is stored
in `tool_calls.gemini_call_id`.

| Result | Scheduling | Why |
|---|---|---|
| `save_answer` / `skip_field` / `request_clarification` OK, agent still talking | `SILENT` | The agent already moved on to the next question; talking about "saved" would break the flow. |
| Same, agent silent | `WHEN_IDLE` | The agent called the tool and is waiting for the result. `SILENT` here leaves dead air until the caller speaks (seen in the first live test). |
| `complete_form` OK | `WHEN_IDLE` | Thank the caller and say goodbye after the current sentence. |
| Any error (validation, missing fields, timeout, bad arguments) | `INTERRUPT` | The agent may already be asking the next question. It must stop and re-ask the failed one now. |

The logic lives in `backend/app/services/scheduling.py`. Some details:

- **The prompt said `INTERRUPTED`.** The API value is **`INTERRUPT`**, so that is what we send.
- **Extended thinking ignores scheduling.** `gemini-3.8-live-extended-thinking` supports only
  `NON_BLOCKING` and does not support scheduling, so we leave the field out. There, re-asking after an
  error relies only on the error text and the system instruction. This is a real difference to compare
  between the two models.
- **`AUTO` (default) vs fixed modes.** `AUTO` chooses between the first two rows above when the result is
  ready. "Talking" means Gemini is still sending audio or the browser is still playing it. Settings can
  force always `SILENT` or always `WHEN_IDLE` for comparison.
- **Timeouts.** Each tool call has a timeout (default 3000 ms) and retries (default 1). A timed-out call
  returns an error, which is sent with `INTERRUPT`. **Extra tool delay** (Settings) simulates a slow
  backend, so you can watch the async behaviour.
- **Async behaviour.** For each tool call we record whether the agent was speaking when the call arrived,
  and how many audio chunks Gemini sent while the tool ran.
- **Cancellations.** `tool_call_cancellation` (usually after a barge-in) is logged. Answers already saved
  stay saved.

### Response time per turn

The time from the last mic chunk loud enough to be speech (our RMS check on the backend) to Gemini's first
audio chunk for the reply. It includes Gemini's VAD silence window, because a real caller waits through it
too. If the mic level never crosses the threshold, Gemini's end-of-speech signal is used instead (the
`stop_source` column). The greeting, and replies that no caller speech triggered, are not counted.

### Session resumption and drops

Every connection enables session resumption and context-window compression. Without compression, audio
sessions end after about 15 minutes, and a connection lasts about 10 minutes either way. On a drop or a
`GoAway`, the backend reconnects with the newest handle. Handles are valid for 2 hours.

If resuming fails twice, the backend starts a **new** session and sends it the saved answers and the next
question, so the agent continues without re-asking.

The answers themselves are always in SQLite, so a drop never loses them. If the **browser's** WebSocket
drops, the page reconnects with the same `call_id`, and the backend keeps the Gemini session for 30
seconds.

### Language

Native-audio Live models choose the spoken language themselves and don't accept a language code. The
selected language goes into the system instruction ("Speak in Tamil…"), which is built from the selected
form.

### Cost

The estimate uses `usage_metadata` from Gemini, split into audio and text tokens. Default rates (USD per
1M tokens, paid tier):

| | Rate |
|---|---|
| Audio input | $3.00 |
| Text input | $0.75 |
| Audio output | $12.00 |
| Text output (thinking counts as output) | $4.50 |

`est_cost_inr` uses the **USD → INR** setting, so it means the same thing as in the Sarvam tester's
column. The docs don't say clearly whether `usage_metadata` is a running total. We **sum** every message
by default. If the numbers look about N× too high against your billing page, switch **Usage counting** to
"running total".

### Export format

The CSV has one row per form field.

- **Shared columns first.** `COMMON_COLUMNS` is copied unchanged from the Sarvam tester, and a test checks
  that it stays the same.
- **Gemini-only columns last:** reconnects, tool timeouts and retries, tools-while-speaking, audio
  tokens, USD cost, VAD silence, scheduling, behaviour and thinking level.
- **How shared columns are filled:** `pipeline = gemini_live`, `llm_model` = the Gemini model,
  `stt_model` / `tts_model` = `native-audio`, `tts_voice` = the Gemini voice.
- **Turns CSV:** keeps the Sarvam turn columns. `stt_ms` / `llm_ttft_ms` / `tts_ttfb_ms` are empty,
  because speech-to-speech has no separate steps; `total_ms` is the response time.
- **The OpenAI tester's export wasn't available** (the Sarvam tester has the same note). If its columns
  differ, change `COMMON_COLUMNS` in `backend/app/services/export.py` in all testers.

### Adding a form

Drop a new `.json` file into `backend/app/seed_forms/`, using the same shape as
`program_feedback_survey.json`, and restart the backend. Field types are `text`, `number`, `choice`,
`yes_no` and `number_list`. Follow-ups use `show_if`, and list length rules use `length_equals_field`.

---

## 6. Where the docs differed from the original brief

| Brief | Docs (Oct 2026) | What we did |
|---|---|---|
| Error → `INTERRUPTED` | The enum value is `INTERRUPT` | Send `INTERRUPT` |
| Scheduling on both models | Extended thinking: `NON_BLOCKING` only, scheduling **not supported**; `turnComplete` ≠ idle, use `interaction_status` | Scheduling is left out for extended thinking; the status shows "Thinking" while `interaction_status = IN_PROGRESS` |
| "thinking_level not supported" | True for `gemini-3.8-live`. Extended thinking **supports** `low` / `medium` / `high` | Thinking level setting, sent only to extended thinking |
| Language dropdown | No language code for native-audio models | Language goes into the system instruction |
| 8 kHz phone mode | Input must be 16 kHz PCM; output is 24 kHz | Band-limit to 8 kHz, then resample back up to 16 kHz |
| — | `proactive_audio` is always on; `enable_affective_dialog` was removed | Neither is sent |

## 7. Vertex AI in India (for data-residency planning)

Checked on 26 Oct 2026 on the [Vertex AI generative AI locations page](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations-genai):

- **`gemini-3.8-live` is listed in Mumbai (`asia-south1`)**, the only India region on the page.
- **`gemini-3.8-live-extended-thinking` is not listed** in any region on that page.
- Google notes that regional **endpoints don't guarantee data residency or in-region ML processing**.
  Confirm data-residency terms separately before using it for real beneficiary calls.

This tester uses the Gemini API (AI Studio key), not Vertex AI.

## 8. Gemini docs used

- [Gemini 3.8 Live model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live): model code,
  async-by-default tools, migration notes
- [Gemini 3.8 Live Extended Thinking](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking):
  `thinking_level`, async-only tools, `interaction_status`
- [Live API capabilities guide](https://ai.google.dev/gemini-api/docs/live-guide): audio formats, VAD,
  transcription, voices, languages
- [Live API tool use](https://ai.google.dev/gemini-api/docs/live-tools): `NON_BLOCKING`, scheduling
- [Live API session management](https://ai.google.dev/gemini-api/docs/live-session): resumption, GoAway,
  context window compression, limits
- [Ephemeral tokens](https://ai.google.dev/gemini-api/docs/ephemeral-tokens): why Option B was not used
- [Live API reference](https://ai.google.dev/api/live): message and field names
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing): default cost rates
- Field names were also checked against the installed `google-genai` 2.33 package
  (`types.FunctionResponseScheduling`, `LiveServerContent.interaction_status`, and others).

## 9. Known limits

- **Response time** is measured in the backend and does not include network to the browser or the browser
  playback buffer.
- **Barge-in:** Gemini only sends `interrupted` while it is still generating. If it has finished sending
  audio and the browser is still playing it, speaking over it does not stop playback.
- **Audio during a reconnect** (usually under 1 second) is dropped, not buffered.
- **`usage_metadata` counting** (sum vs running total) needs checking against one real billing record.
#   s p e e c h - t o - s p e e c h - u s i n g - g e m i n i  
 