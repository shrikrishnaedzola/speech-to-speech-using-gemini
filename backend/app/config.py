"""App settings and the option lists shown in the UI dropdowns.

The Gemini API key is read ONLY from the GEMINI_API_KEY environment variable
(loaded from backend/.env). It is never sent to the browser and never logged.

Model IDs, audio formats, voices and prices come from ai.google.dev (checked Oct 2026):
- Models:   https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live
            https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking
- Live API: https://ai.google.dev/gemini-api/docs/live-guide
- Tools:    https://ai.google.dev/gemini-api/docs/live-tools
- Pricing:  https://ai.google.dev/gemini-api/docs/pricing
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'tester.db'}")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5190").split(",")]

SEED_FORMS_DIR = BACKEND_DIR / "app" / "seed_forms"
SIMULATE_DIR = BACKEND_DIR / "app" / "simulate"

# Audio formats required by the Live API (live-guide): input is raw 16-bit
# little-endian PCM at 16 kHz, output is 16-bit PCM at 24 kHz.
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
INPUT_MIME_TYPE = f"audio/pcm;rate={INPUT_SAMPLE_RATE}"


def has_api_key() -> bool:
    return bool(GEMINI_API_KEY) and not GEMINI_API_KEY.startswith("your_")


# ---------------------------------------------------------------------------
# Dropdown options (sent to the UI by GET /api/options)
# ---------------------------------------------------------------------------

# supports_scheduling: the extended-thinking model accepts only NON_BLOCKING tools
# and does not support FunctionResponse scheduling (its model page says so).
# supports_thinking_level: gemini-3.8-live rejects thinking_level, so it is never sent.
MODELS = [
    {"id": "gemini-3.8-live", "label": "Gemini 3.8 Live (default, low latency)",
     "supports_scheduling": True, "supports_thinking_level": False},
    {"id": "gemini-3.8-live-extended-thinking", "label": "Gemini 3.8 Live Extended Thinking (slower)",
     "supports_scheduling": False, "supports_thinking_level": True},
]
MODEL_INFO = {m["id"]: m for m in MODELS}

# Prebuilt voices. The Live native-audio models accept any voice of the Gemini TTS models.
VOICES = [
    "Kore", "Puck", "Charon", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome",
    "Algenib", "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima",
    "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

# Same list and codes as the Sarvam tester, so exports line up.
# Native-audio models can't take a language code: the language goes into the
# system instruction instead (live-guide, "Supported languages").
LANGUAGES = [
    {"code": "auto", "label": "Auto-detect"},
    {"code": "en-IN", "label": "English (India)"},
    {"code": "hi-IN", "label": "Hindi"},
    {"code": "bn-IN", "label": "Bengali"},
    {"code": "ta-IN", "label": "Tamil"},
    {"code": "te-IN", "label": "Telugu"},
    {"code": "kn-IN", "label": "Kannada"},
    {"code": "ml-IN", "label": "Malayalam"},
    {"code": "mr-IN", "label": "Marathi"},
    {"code": "gu-IN", "label": "Gujarati"},
    {"code": "pa-IN", "label": "Punjabi"},
    {"code": "od-IN", "label": "Odia"},
]
LANGUAGE_NAMES = {lang["code"]: lang["label"] for lang in LANGUAGES}

# ---------------------------------------------------------------------------
# Default call settings (every value can be changed from the UI)
# ---------------------------------------------------------------------------

DEFAULT_CALL_SETTINGS = {
    "model": "gemini-3.8-live",
    "voice": "Kore",
    "language": "auto",
    "audio_quality": "normal",  # "normal" (16 kHz) or "phone" (band-limited to 8 kHz)
    # --- voice activity detection (server-side, automatic) ---
    "vad_start_sensitivity": "default",  # "default", "high" or "low"
    "vad_end_sensitivity": "default",
    "vad_prefix_padding_ms": 20,
    "vad_silence_ms": 500,  # docs recommend 500-800 ms
    # --- tools ---
    "tool_behavior": "NON_BLOCKING",  # gemini-3.8-live only; extended-thinking is always NON_BLOCKING
    # Successful save/skip/clarify: AUTO = SILENT if the agent is still talking, else WHEN_IDLE.
    "save_ok_scheduling": "AUTO",
    "tool_timeout_ms": 3000,
    "tool_max_retries": 1,
    "tool_delay_ms": 0,  # artificial delay to watch the async behaviour (0 = off)
    # --- extended-thinking only ---
    "thinking_level": "low",  # low / medium / high
    # --- cost rates (USD per 1M tokens, paid tier, from the pricing page) ---
    "rate_audio_input_per_1m": 3.00,
    "rate_text_input_per_1m": 0.75,
    "rate_audio_output_per_1m": 12.00,
    "rate_text_output_per_1m": 4.50,
    "usd_to_inr": 88.0,  # exchange rate for the INR column shared with the Sarvam tester
    "usage_counting": "sum",  # "sum" each usage message, or "last" if usage turns out to be cumulative
}
