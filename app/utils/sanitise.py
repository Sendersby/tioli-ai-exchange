"""Input sanitisation utilities to prevent XSS and injection attacks."""
import html
import re
from typing import Optional


def sanitise_input(text: str) -> str:
    """Strip HTML tags, escape special characters, remove null bytes."""
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    # Remove null bytes
    text = text.replace('\x00', '')
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape remaining special characters
    text = html.escape(text, quote=True)
    return text.strip()


def sanitise_dict(data: dict, fields: Optional[list] = None) -> dict:
    """Sanitise string values in a dict. If fields specified, only sanitise those."""
    if not isinstance(data, dict):
        return data
    result = dict(data)
    for key, value in result.items():
        if isinstance(value, str) and (fields is None or key in fields):
            result[key] = sanitise_input(value)
    return result
