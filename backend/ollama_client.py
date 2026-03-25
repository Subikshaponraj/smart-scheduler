# ollama_client.py
# Reusable Ollama client — drop-in replacement for all OpenAI calls.
# Requires: pip install requests

import json
import re
import requests
from datetime import datetime, timedelta
from typing import Any, Optional

# ── Configuration ──────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "mistral"          # swap to "llama3" or any model you have pulled
REQUEST_TIMEOUT = 90                 # seconds — local models can be slow on first load
# ──────────────────────────────────────────────────────────────────────────────


def call_local_llm(prompt: str, max_tokens: int = 1500, retries: int = 2) -> str:
    """
    Send a prompt to Ollama and return the text response.
    Returns "" on any failure so callers can apply their own fallback.
    """
    url     = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,        # deterministic output — critical for JSON
            "num_predict": max_tokens,
        },
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            if text:
                print(f"[OLLAMA] Response received ({len(text)} chars)")
                return text
            print(f"[OLLAMA] Attempt {attempt}: empty response body")
        except requests.exceptions.ConnectionError:
            print(
                f"[OLLAMA] Attempt {attempt}: Cannot reach Ollama at {OLLAMA_BASE_URL}. "
                "Make sure `ollama serve` is running."
            )
        except requests.exceptions.Timeout:
            print(f"[OLLAMA] Attempt {attempt}: Timed out after {REQUEST_TIMEOUT}s")
        except Exception as exc:
            print(f"[OLLAMA] Attempt {attempt}: Unexpected error — {exc}")

    return ""


def safe_parse_json(raw: str) -> Optional[Any]:
    """
    Robustly parse JSON from LLM output.
    Handles markdown fences, leading text, and minor formatting issues.
    Returns the parsed object or None on failure.
    """
    if not raw:
        return None

    text = raw.strip()

    # Strip markdown fences  ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$",          "", text)
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first {...} or [...] block
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    print(f"[OLLAMA] JSON parse failed. First 400 chars:\n{raw[:400]}")
    return None


# ── Rule-based fallback (no LLM needed) ───────────────────────────────────────

_TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_RELATIVE_DATES = {
    "today":              0,
    "tonight":            0,
    "tomorrow":           1,
    "tmrw":               1,
    "day after tomorrow": 2,
    "next week":          7,
}
_SCHEDULE_VERBS = [
    "schedule", "book", "set up", "add", "remind", "arrange",
    "meeting", "call", "appointment", "event",
]


def rule_based_event_extract(text: str) -> Optional[dict]:
    """
    Lightweight regex fallback used when Ollama is unavailable.
    Returns a structured response dict or None if no scheduling intent detected.
    """
    lower = text.lower()
    if not any(v in lower for v in _SCHEDULE_VERBS):
        return None

    # Resolve relative date
    detected_date = ""
    for word, offset in _RELATIVE_DATES.items():
        if word in lower:
            detected_date = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
            break

    # Extract time
    detected_time = "09:00:00"
    m = _TIME_PATTERN.search(text)
    if m:
        hour     = int(m.group(1))
        minute   = m.group(2) or "00"
        meridiem = m.group(3)
        if meridiem.lower() == "pm" and hour != 12:
            hour += 12
        elif meridiem.lower() == "am" and hour == 12:
            hour = 0
        detected_time = f"{hour:02d}:{minute}:00"

    # Best-effort title
    title = "New Event"
    for verb in _SCHEDULE_VERBS:
        idx = lower.find(verb)
        if idx != -1:
            snippet = text[idx: idx + 60].strip()
            title   = snippet[:50].rstrip(".,;:")
            break

    date_part = detected_date or datetime.now().strftime("%Y-%m-%d")
    end_hour  = (int(detected_time[:2]) + 1) % 24
    end_time  = f"{date_part} {end_hour:02d}:{detected_time[3:]}"

    return {
        "response": (
            f"Got it! I've scheduled '{title}' for "
            f"{date_part} at {detected_time[:5]}."
        ),
        "events": [{
            "title":       title,
            "start_time":  f"{date_part} {detected_time}",
            "end_time":    end_time,
            "location":    None,
            "description": None,
            "attendees":   [],
        }],
    }