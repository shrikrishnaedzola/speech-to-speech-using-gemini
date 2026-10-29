"""Cost calculation engine for Voice Form Tester reports (Gemini).

Calculates Gemini 3.8 Live API call cost based on token usage:
- Audio input tokens
- Audio output tokens
- Text input tokens (prompt + tools)
- Text output tokens

Outputs:
- Call cost in USD & INR
- Granular breakdown per billing item
- Cost per minute & cost per completed form
- Scaled projection for 1,000 similar calls
- Pricing revision timestamp
"""

from typing import Dict, Any, Optional
from app.report_module.config import PROVIDER_RATES, USD_TO_INR, RATES_LAST_UPDATED


def calculate_call_cost(
    provider: str,
    duration_seconds: float,
    audio_in_tokens: int = 0,
    audio_out_tokens: int = 0,
    text_in_tokens: int = 0,
    text_out_tokens: int = 0,
    form_completed: bool = True,
    tts_characters: int = 0,
    custom_exchange_rate: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate Gemini API cost for a test call."""
    # Always use Gemini rates (fallback to gemini if another key is passed)
    rates = PROVIDER_RATES.get("gemini")
    exchange_rate = custom_exchange_rate or USD_TO_INR
    minutes = max(0.1, duration_seconds / 60.0)

    # Gemini token-based pricing
    audio_in_cost  = (audio_in_tokens  / 1_000_000.0) * rates["audio_input_per_1m_tokens"]
    audio_out_cost = (audio_out_tokens / 1_000_000.0) * rates["audio_output_per_1m_tokens"]
    text_in_cost   = (text_in_tokens   / 1_000_000.0) * rates["text_input_per_1m_tokens"]
    text_out_cost  = (text_out_tokens  / 1_000_000.0) * rates["text_output_per_1m_tokens"]

    breakdown = [
        {
            "item": "Audio Input Tokens",
            "quantity": f"{audio_in_tokens:,} tokens",
            "rate": f"${rates['audio_input_per_1m_tokens']:.2f} / 1M tokens",
            "cost_usd": round(audio_in_cost, 5),
            "cost_inr": round(audio_in_cost * exchange_rate, 2),
        },
        {
            "item": "Audio Output Tokens",
            "quantity": f"{audio_out_tokens:,} tokens",
            "rate": f"${rates['audio_output_per_1m_tokens']:.2f} / 1M tokens",
            "cost_usd": round(audio_out_cost, 5),
            "cost_inr": round(audio_out_cost * exchange_rate, 2),
        },
        {
            "item": "Text Input Tokens (Prompt / Tools)",
            "quantity": f"{text_in_tokens:,} tokens",
            "rate": f"${rates['text_input_per_1m_tokens']:.2f} / 1M tokens",
            "cost_usd": round(text_in_cost, 5),
            "cost_inr": round(text_in_cost * exchange_rate, 2),
        },
        {
            "item": "Text Output Tokens",
            "quantity": f"{text_out_tokens:,} tokens",
            "rate": f"${rates['text_output_per_1m_tokens']:.2f} / 1M tokens",
            "cost_usd": round(text_out_cost, 5),
            "cost_inr": round(text_out_cost * exchange_rate, 2),
        },
    ]

    total_usd = audio_in_cost + audio_out_cost + text_in_cost + text_out_cost

    # Overall metrics
    total_inr = total_usd * exchange_rate
    cost_per_minute_usd = total_usd / minutes if minutes > 0 else total_usd
    cost_per_minute_inr = total_inr / minutes if minutes > 0 else total_inr

    # Cost per successfully completed form (penalise incomplete forms)
    cost_per_completed_form_usd = total_usd if form_completed else (total_usd * 2.0)
    cost_per_completed_form_inr = cost_per_completed_form_usd * exchange_rate

    # Projection for 1,000 similar calls
    projection_1000_usd = round(total_usd * 1000.0, 2)
    projection_1000_inr = round(total_inr  * 1000.0, 2)

    return {
        "provider": "gemini",
        "provider_display_name": rates["display_name"],
        "duration_minutes": round(minutes, 2),
        "total_cost_usd": round(total_usd, 4),
        "total_cost_inr": round(total_inr, 2),
        "cost_per_minute_usd": round(cost_per_minute_usd, 4),
        "cost_per_minute_inr": round(cost_per_minute_inr, 2),
        "cost_per_completed_form_usd": round(cost_per_completed_form_usd, 4),
        "cost_per_completed_form_inr": round(cost_per_completed_form_inr, 2),
        "projection_1000_calls": {
            "usd": projection_1000_usd,
            "inr": projection_1000_inr,
        },
        "breakdown": breakdown,
        "exchange_rate_usd_to_inr": exchange_rate,
        "rates_last_updated": RATES_LAST_UPDATED,
    }
