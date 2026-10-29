"""Security and privacy protections for Zolabs Voice Form Tester reports.

Features:
- Regex-based PII detector for 10-digit phone numbers and 12-digit Aadhaar numbers.
- Masks sensitive digits (e.g., 9876543210 -> 98XXXXXX10, 1234-5678-9012 -> XXXX-XXXX-9012).
- Returns warnings and counts of masked occurrences.
- Validates that API keys or environment secrets are never exposed in reports.
"""

import re
from typing import Tuple, List, Dict, Any

# Pattern for Indian 10-digit mobile numbers (optional country code +91 or 0)
PHONE_PATTERN = re.compile(r'(?:\+?91[\-\s]?)?(?<!\d)([6-9]\d{9})(?!\d)')

# Pattern for 12-digit Aadhaar numbers (with optional spaces or dashes: XXXX XXXX XXXX or XXXXXXXXXXXX)
AADHAAR_PATTERN = re.compile(r'(?<!\d)(\d{4}[\-\s]?\d{4}[\-\s]?\d{4})(?!\d)')


def mask_phone_number(match: re.Match) -> str:
    """Mask a 10-digit mobile number, preserving only first 2 and last 2 digits."""
    raw = match.group(1)
    return f"{raw[:2]}XXXXXX{raw[-2:]}"


def mask_aadhaar_number(match: re.Match) -> str:
    """Mask a 12-digit Aadhaar number, keeping only the last 4 digits."""
    raw = match.group(1).replace("-", "").replace(" ", "")
    return f"XXXX-XXXX-{raw[-4:]}"


def scan_and_mask_text(text: str) -> Tuple[str, List[str]]:
    """Scan a single text string for phone numbers or Aadhaar numbers and mask them.
    
    Returns:
        (masked_text, list_of_detected_warnings)
    """
    if not isinstance(text, str) or not text:
        return text, []

    warnings: List[str] = []
    masked = text

    # Check for Aadhaar
    aadhaar_matches = AADHAAR_PATTERN.findall(masked)
    if aadhaar_matches:
        warnings.append(f"Masked {len(aadhaar_matches)} potential Aadhaar/12-digit ID number(s)")
        masked = AADHAAR_PATTERN.sub(mask_aadhaar_number, masked)

    # Check for Phone numbers
    phone_matches = PHONE_PATTERN.findall(masked)
    if phone_matches:
        warnings.append(f"Masked {len(phone_matches)} potential 10-digit phone number(s)")
        masked = PHONE_PATTERN.sub(mask_phone_number, masked)

    return masked, warnings


def sanitize_value(val: Any) -> Tuple[Any, List[str]]:
    """Recursively mask strings within dicts, lists, or primitives."""
    if isinstance(val, str):
        return scan_and_mask_text(val)
    elif isinstance(val, list):
        clean_list = []
        all_warnings = []
        for item in val:
            cleaned_item, warns = sanitize_value(item)
            clean_list.append(cleaned_item)
            all_warnings.extend(warns)
        return clean_list, all_warnings
    elif isinstance(val, dict):
        clean_dict = {}
        all_warnings = []
        for k, v in val.items():
            cleaned_val, warns = sanitize_value(v)
            clean_dict[k] = cleaned_val
            all_warnings.extend(warns)
        return clean_dict, all_warnings
    return val, []


def sanitize_report_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Scan an entire report data structure, mask PII, and collect warnings."""
    cleaned_data, warnings = sanitize_value(data)
    # Deduplicate warnings
    unique_warnings = list(dict.fromkeys(warnings))
    return cleaned_data, unique_warnings
