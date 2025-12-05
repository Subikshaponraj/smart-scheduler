# agent.py
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

import openai

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable not set")
openai.api_key = OPENAI_API_KEY

def _call_llm(prompt: str, max_tokens: int = 500) -> str:
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return text
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return ""

def analyze_task_patterns(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not tasks:
        return {"insights": [], "suggestions": []}

    task_summary = []
    for t in tasks:
        task_summary.append({
            "title": t.get("title"),
            "status": t.get("status"),
            "due_date": str(t.get("due_date")),
            "followup_count": t.get("followup_count", 0),
            "priority": t.get("priority")
        })

    prompt = f"""You are an intelligent task management assistant. Analyze this user's task history and provide insights.

Tasks: {json.dumps(task_summary, indent=2)}
Current date: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Return ONLY a JSON object:
{{
  "insights": ["..."],
  "suggestions": ["..."]
}}"""

    raw = _call_llm(prompt, max_tokens=800)
    if not raw:
        return {"insights": [], "suggestions": []}

    # try parsing JSON
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[-1].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[PARSE ERROR] {e}\nRAW:\n{raw}")
        return {"insights": [], "suggestions": []}

def generate_followup_message(task: Dict[str, Any], followup_count: int) -> str:
    prompt = f"""Generate a short followup for this overdue task:
Task: {task.get('title')}
Description: {task.get('description', '')}
Due: {task.get('due_date')}
Previous followups: {followup_count}
Return only the message text (max 50 words)."""
    raw = _call_llm(prompt, max_tokens=80)
    return raw or f"Hey! Checking in on '{task.get('title')}'. Still need this?"

def should_reschedule_task(task: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""Analyze if this task should be rescheduled. Task: {task.get('title')}, due: {task.get('due_date')}, priority: {task.get('priority')}, times_rescheduled:{task.get('followup_count',0)}.
Return only JSON: {{ "should_reschedule": true/false, "suggested_date": "YYYY-MM-DD HH:MM:SS or null", "reasoning":"..." }}"""
    raw = _call_llm(prompt, max_tokens=200)
    if not raw:
        return {"should_reschedule": True, "suggested_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), "reasoning": "Default suggestion"}
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[-1].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[PARSE ERROR] {e}\nRAW:\n{raw}")
        return {"should_reschedule": True, "suggested_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), "reasoning": "Default suggestion"}
