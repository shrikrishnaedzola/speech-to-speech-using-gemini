"""Configuration settings and cost rates for the Post-Call Report module.

All values are easily customizable for different environments.
Weights, pricing rates, and thresholds can be overridden per call or in settings.
"""

from typing import Dict, Any

# Scoring weights (sum to 1.0)
DEFAULT_WEIGHTS = {
    "accuracy": 0.35,
    "latency": 0.20,
    "mishearings": 0.15,
    "voice_quality": 0.15,
    "language_support": 0.10,
    "cost": 0.05,
}

# Score verdicts
VERDICT_THRESHOLDS = {
    "good": 80.0,
    "needs_improvement": 60.0,
    # Below 60 is "Poor"
}

# Currency exchange rate (USD to INR)
USD_TO_INR = 86.50
RATES_LAST_UPDATED = "2026-10-15"

# Gemini cost rates (in USD)
PROVIDER_RATES: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "display_name": "Google Gemini 3.8 Live",
        "audio_input_per_1m_tokens": 2.00,    # $0.002 per 1k tokens
        "audio_output_per_1m_tokens": 4.00,   # $0.004 per 1k tokens
        "text_input_per_1m_tokens": 0.15,
        "text_output_per_1m_tokens": 0.60,
        "base_rate_unit": "tokens",
    },
}

# Voice quality settings
VOICE_QUALITY_CONFIG = {
    "enable_local_mos": False,  # Optional local open-source MOS predictor (UTMOS / DNSMOS)
    "mos_model_path": None,
    "silence_threshold_seconds": 2.0,  # Long pause detection threshold
}
