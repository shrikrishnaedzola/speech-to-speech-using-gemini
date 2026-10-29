"""JSON export and canonical schema validation for Gemini Voice Form Tester reports.

Ensures that Gemini Live reports adhere to the validated canonical JSON format.
"""

import json
from typing import Dict, Any, Tuple, List


# Key required top-level schema fields
REQUIRED_TOP_LEVEL_FIELDS = [
    "metadata",
    "call_info",
    "scoring",
    "transcript",
    "mishearings",
    "voice_quality",
    "latency",
    "language",
    "accuracy",
    "cost",
    "issues_and_recommendations",
    "ai_summary",
]


def validate_report_schema(report_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that the report dictionary conforms to the required comparison schema."""
    errors = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in report_data:
            errors.append(f"Missing required top-level field: '{field}'")

    call_info = report_data.get("call_info", {})
    for req in ["provider", "model", "language", "duration_formatted"]:
        if req not in call_info:
            errors.append(f"Missing call_info field: '{req}'")

    scoring = report_data.get("scoring", {})
    if "overall_score" not in scoring or "verdict" not in scoring:
        errors.append("Missing scoring fields ('overall_score' or 'verdict')")

    return len(errors) == 0, errors


def export_report_to_json(report_data: Dict[str, Any], indent: int = 2) -> str:
    """Serialize the report to a formatted JSON string."""
    is_valid, errors = validate_report_schema(report_data)
    if not is_valid:
        # Include validation warnings inside the payload metadata
        if "metadata" in report_data:
            report_data["metadata"]["schema_validation_errors"] = errors

    return json.dumps(report_data, indent=indent, default=str, ensure_ascii=False)
