"""HMAC and replay-window primitives."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone


def request_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def verify_signature(body: bytes, signature_header: str | None, secret: bytes) -> bool:
    """Verify ``sha256=<hex>`` (or bare hex) in constant-time for valid-size input."""

    expected = hmac.new(secret, body, hashlib.sha256).digest()
    candidate_text = (signature_header or "").strip()
    if candidate_text.lower().startswith("sha256="):
        candidate_text = candidate_text[7:]

    format_valid = len(candidate_text) == 64
    try:
        candidate = bytes.fromhex(candidate_text) if format_valid else bytes(32)
    except ValueError:
        candidate = bytes(32)
        format_valid = False

    digest_matches = hmac.compare_digest(candidate, expected)
    return format_valid and digest_matches


def parse_event_timestamp_ms(value: int | str) -> int:
    """Normalize epoch seconds/ms or timezone-aware ISO-8601 to epoch ms."""

    if isinstance(value, int):
        numeric = value
    else:
        stripped = value.strip()
        try:
            numeric = int(stripped)
        except ValueError:
            iso_value = stripped[:-1] + "+00:00" if stripped.endswith(("Z", "z")) else stripped
            try:
                parsed = datetime.fromisoformat(iso_value)
            except ValueError as exc:
                raise ValueError("timestamp must be epoch seconds/ms or ISO-8601") from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("ISO-8601 timestamp must include a timezone")
            return int(parsed.astimezone(timezone.utc).timestamp() * 1_000)

    # Contemporary epoch seconds have 10 digits; epoch milliseconds have 13.
    if numeric >= 10_000_000_000_000:
        raise ValueError("timestamp precision above milliseconds is not accepted")
    return numeric if numeric >= 10_000_000_000 else numeric * 1_000


def timestamp_within_window(
    event_timestamp_ms: int,
    now_seconds: float,
    replay_window_seconds: int,
    future_tolerance_seconds: int,
) -> bool:
    now_ms = int(now_seconds * 1_000)
    return (
        now_ms - replay_window_seconds * 1_000
        <= event_timestamp_ms
        <= now_ms + future_tolerance_seconds * 1_000
    )
