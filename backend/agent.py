# agent.py
# Drop-in replacement — all OpenAI calls replaced with Ollama.
# Function signatures are unchanged so nothing else needs updating.

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ollama_client import call_local_llm, safe_parse_json


def analyze_task_patterns(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyse task history and return AI insights + suggestions.
    """
    if not tasks:
        return {"insights": [], "suggestions": []}

    task_summary = [
        {
            "title":         t.get("title"),
            "status":        t.get("status"),
            "due_date":      str(t.get("due_date")),
            "followup_count": t.get("followup_count", 0),
            "priority":      t.get("priority"),
        }
        for t in tasks
    ]

    prompt = f"""\
You are an intelligent task management assistant.
Analyse the task history and return ONLY a JSON object — no markdown, no extra text.

Tasks:
{json.dumps(task_summary, indent=2)}

Current date: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Required format:
{{
  "insights":    ["<insight 1>", "<insight 2>"],
  "suggestions": ["<suggestion 1>", "<suggestion 2>"]
}}"""

    raw    = call_local_llm(prompt, max_tokens=600)
    parsed = safe_parse_json(raw) if raw else None

    if isinstance(parsed, dict):
        parsed.setdefault("insights",    [])
        parsed.setdefault("suggestions", [])
        return parsed

    print(f"[AGENT] analyze_task_patterns parse failed. Raw:\n{raw[:300]}")
    return {"insights": [], "suggestions": []}


def generate_followup_message(task: Dict[str, Any], followup_count: int) -> str:
    """
    Generate a short follow-up message for an overdue task.
    """
    prompt = f"""\
Generate a short, friendly follow-up message for this overdue task.
Keep it under 50 words. Output only the message text — no JSON, no labels.

Task          : {task.get("title")}
Description   : {task.get("description", "")}
Due date      : {task.get("due_date")}
Previous follow-ups sent: {followup_count}"""

    raw = call_local_llm(prompt, max_tokens=100)
    if raw:
        return raw.strip()

    # Static fallback
    return f"Hey! Just checking in on '{task.get('title')}'. Is this still on your radar?"


def should_reschedule_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide whether a task should be rescheduled and suggest a new date.
    """
    prompt = f"""\
Decide whether this task should be rescheduled.
Return ONLY a JSON object — no markdown, no extra text.

Task             : {task.get("title")}
Due date         : {task.get("due_date")}
Priority         : {task.get("priority")}
Times rescheduled: {task.get("followup_count", 0)}

Required format:
{{
  "should_reschedule": true | false,
  "suggested_date":    "YYYY-MM-DD HH:MM:SS" or null,
  "reasoning":         "<brief reason>"
}}"""

    raw    = call_local_llm(prompt, max_tokens=200)
    parsed = safe_parse_json(raw) if raw else None

    if isinstance(parsed, dict) and "should_reschedule" in parsed:
        return parsed

    print(f"[AGENT] should_reschedule_task parse failed. Raw:\n{raw[:300]}")
    default_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "should_reschedule": True,
        "suggested_date":    default_date,
        "reasoning":         "Defaulting to tomorrow due to parse error.",
    }