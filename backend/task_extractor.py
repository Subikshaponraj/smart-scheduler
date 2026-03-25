# task_extractor.py
# Exact drop-in replacement for the original OpenAI-based task_extractor.
# Every function signature is preserved — main.py needs zero changes.
# All LLM calls go through ollama_client.call_local_llm().

import json
import base64
import tempfile
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ollama_client import call_local_llm, safe_parse_json, rule_based_event_extract


# ──────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a helpful AI scheduling assistant. Current date/time: {now}.

Analyze the conversation below and:
1. Identify if the user wants to schedule a NEW event.
2. If the user asks about existing events, reference the calendar context.
3. Reply naturally and helpfully.

Respond with ONLY a valid JSON object — no markdown fences, no explanation.

Required format:
{{
  "response": "<friendly reply to the user>",
  "events": [
    {{
      "title": "<event title>",
      "start_time": "YYYY-MM-DD HH:MM:SS",
      "end_time":   "YYYY-MM-DD HH:MM:SS"
    }}
  ]
}}

Rules:
- "events" must be [] when no scheduling is requested.
- Resolve relative dates (tomorrow, next Monday) against today: {today}.
- Default start time to 09:00:00 when none is mentioned.
- Default end time to start_time + 1 hour when none is mentioned.
- Include location / description inside "title" if space allows; otherwise omit.
- Output ONLY JSON. No prose before or after.

{events_context}

CONVERSATION:
{conversation}
"""

_REMINDER_PROMPT = """\
You are a smart calendar assistant. Write a brief, friendly event reminder in under 40 words.
Include a preparation tip if the event has a location.

Event : {title}
Time  : {start_time}
Location: {location}
Description: {description}
User context: {context}

Output only the reminder text — no JSON, no labels.
"""

_PATTERNS_PROMPT = """\
You are a scheduling analyst. Analyze the events below and return ONLY a JSON object.

Events (last 30 days):
{events_json}

Today: {today}

Required format (no markdown, no extra text):
{{
  "insights":    ["<insight 1>", "<insight 2>", "<insight 3>"],
  "suggestions": ["<suggestion 1>", "<suggestion 2>", "<suggestion 3>"],
  "peak_hours":  [<hour_int>, ...],
  "peak_days":   ["Monday", ...]
}}
"""

_SUMMARY_PROMPT = """\
You are a calendar assistant. Write a brief, friendly summary (under 80 words) of these upcoming events.

{events_list}

Output only the summary — no JSON, no labels.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _fmt_today() -> str:
    return datetime.now().strftime("%Y-%m-%d (%A)")

def _parse_dt(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            pass
    return None

def _build_events_context(existing_events: List) -> str:
    if not existing_events:
        return ""
    lines = ["\nUpcoming events already on the user's calendar:"]
    for e in existing_events:
        start = getattr(e, "start_time", None) or e.get("start_time", "")
        end   = getattr(e, "end_time",   None) or e.get("end_time",   "")
        title = getattr(e, "title",      None) or e.get("title",      "Event")
        desc  = getattr(e, "description",None) or e.get("description", "")
        end_str = end.strftime("%H:%M") if isinstance(end, datetime) else str(end)[:5]
        line = f"- {title} at {start}"
        if end_str:
            line += f" → {end_str}"
        if desc:
            line += f" ({desc})"
        lines.append(line)
    return "\n".join(lines)

def _normalise_events(raw_events: List[dict]) -> List[dict]:
    """Convert LLM event list to datetime objects; drop malformed entries."""
    result = []
    for ev in raw_events:
        start = _parse_dt(str(ev.get("start_time", "")))
        if start is None:
            continue  # skip events with unparseable times

        raw_end = ev.get("end_time")
        end = _parse_dt(str(raw_end)) if raw_end else None
        if end is None:
            end = start + timedelta(hours=1)

        result.append({
            "title":       ev.get("title", "New Event"),
            "start_time":  start,
            "end_time":    end,
            "location":    ev.get("location"),
            "description": ev.get("description") or ev.get("notes"),
            "attendees":   ev.get("attendees", []),
        })
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public functions — called by main.py (signatures unchanged)
# ──────────────────────────────────────────────────────────────────────────────

def extract_events_from_conversation(
    messages: List[Dict[str, str]],
    existing_events: List = None,
) -> Dict[str, Any]:
    """
    Extracts events + assistant reply from conversation history.
    Returns: { "response": str, "events": list[dict] }
    Each event dict has: title, start_time (datetime), end_time (datetime),
    location, description, attendees.
    """
    existing_events = existing_events or []
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages[-12:]
    )

    prompt = _EXTRACT_PROMPT.format(
        now=_fmt_now(),
        today=_fmt_today(),
        events_context=_build_events_context(existing_events),
        conversation=conversation_text,
    )

    raw = call_local_llm(prompt)
    print(f"[TASK_EXTRACTOR] Raw output:\n{raw[:600]}")

    parsed = safe_parse_json(raw) if raw else None

    # ── Fallback 1: rule-based extraction ────────────────────────────────────
    if not parsed:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        fallback = rule_based_event_extract(last_user)
        if fallback:
            print("[TASK_EXTRACTOR] Using rule-based fallback")
            parsed = fallback

    # ── Fallback 2: safe static reply ─────────────────────────────────────────
    if not parsed:
        return {
            "response": (
                "I'm your AI calendar assistant! I can schedule meetings, set reminders, "
                "and help you stay on top of your day. What would you like to do?"
            ),
            "events": [],
        }

    # Normalise event datetimes
    parsed["events"] = _normalise_events(parsed.get("events", []))
    return parsed


def generate_smart_reminder(event: Any, user_event_history: List[Any]) -> str:
    """
    Generate a contextual, smart reminder for an upcoming event.
    Matches the original function signature exactly.
    """
    # Compute average hour from history for context
    hours = [
        e.start_time.hour
        for e in (user_event_history or [])
        if getattr(e, "start_time", None)
    ]
    avg_hour = int(sum(hours) / len(hours)) if hours else 14

    prompt = _REMINDER_PROMPT.format(
        title       = getattr(event, "title",       "Event"),
        start_time  = getattr(event, "start_time",  "soon"),
        location    = getattr(event, "location",    "Not specified") or "Not specified",
        description = getattr(event, "description", "None")          or "None",
        context     = f"User typically schedules events around {avg_hour}:00",
    )

    raw = call_local_llm(prompt, max_tokens=200)
    if raw:
        return raw.strip()

    # Static fallback
    start = getattr(event, "start_time", "")
    start_str = start.strftime("%I:%M %p") if isinstance(start, datetime) else str(start)
    return f"Reminder: '{getattr(event, 'title', 'your event')}' is coming up at {start_str}!"


def analyze_user_patterns(events: List[Any]) -> Dict[str, Any]:
    """
    Analyse scheduling patterns and return insights + suggestions.
    Matches the original function signature exactly.
    """
    if not events:
        return {
            "insights":    ["Not enough data to analyse patterns yet."],
            "suggestions": ["Keep scheduling events to unlock insights!"],
            "peak_hours":  [],
            "peak_days":   [],
        }

    event_data = [
        {
            "title":        getattr(e, "title",       e.get("title",       "")),
            "day_of_week":  getattr(e, "start_time",  None) and
                            getattr(e, "start_time").strftime("%A"),
            "hour":         getattr(e, "start_time",  None) and
                            getattr(e, "start_time").hour,
            "has_location": bool(getattr(e, "location", None)),
            "has_attendees": bool(
                getattr(e, "attendees", None) and
                getattr(e, "attendees") not in (None, "[]", [])
            ),
        }
        for e in events
    ]

    prompt = _PATTERNS_PROMPT.format(
        events_json=json.dumps(event_data, indent=2),
        today=_fmt_today(),
    )

    raw    = call_local_llm(prompt, max_tokens=800)
    parsed = safe_parse_json(raw) if raw else None

    if isinstance(parsed, dict):
        # Ensure all expected keys exist
        parsed.setdefault("insights",    [])
        parsed.setdefault("suggestions", [])
        parsed.setdefault("peak_hours",  [])
        parsed.setdefault("peak_days",   [])
        return parsed

    return {
        "insights":    ["Could not analyse patterns right now."],
        "suggestions": ["Try again later for AI-powered scheduling insights."],
        "peak_hours":  [],
        "peak_days":   [],
    }


def generate_calendar_summary(events: List[Dict[str, Any]]) -> str:
    """
    Generate a natural language summary of calendar events.
    Matches the original function signature exactly.
    """
    if not events:
        return "You don't have any upcoming events scheduled."

    lines = []
    for e in events:
        start = e.get("start_time") or e.get("start_time", "")
        title = e.get("title", "Event")
        if isinstance(start, datetime):
            start = start.strftime("%B %d, %I:%M %p")
        lines.append(f"- {title} at {start}")

    prompt = _SUMMARY_PROMPT.format(events_list="\n".join(lines))
    raw = call_local_llm(prompt, max_tokens=300)
    return raw.strip() if raw else f"You have {len(events)} upcoming event(s)."


def transcribe_audio(audio_base64: str) -> str:
    """
    Audio transcription.  Ollama does not support audio natively.

    To enable local transcription, install openai-whisper:
        pip install openai-whisper
    Then uncomment the block below.
    """
    # ── Uncomment to enable local Whisper transcription ──────────────────────
    # try:
    #     import whisper
    #     import tempfile, base64, os
    #     model = whisper.load_model("base")          # "tiny" is faster
    #     audio_bytes = base64.b64decode(audio_base64)
    #     with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
    #         f.write(audio_bytes)
    #         tmp_path = f.name
    #     result = model.transcribe(tmp_path)
    #     os.unlink(tmp_path)
    #     return result["text"].strip()
    # except Exception as e:
    #     print(f"[WHISPER] Error: {e}")
    #     return ""
    # ─────────────────────────────────────────────────────────────────────────

    print("[TRANSCRIBE] Local Whisper not enabled. See transcribe_audio() in task_extractor.py.")
    return ""