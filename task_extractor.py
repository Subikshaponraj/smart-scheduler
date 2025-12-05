# task_extractor.py
import os
import json
import base64
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Any

from openai import OpenAI

# Initialize client
client = OpenAI()

def _call_llm(prompt: str, max_tokens: int = 1500) -> str:
    """
    Wrapper for OpenAI Chat API (new 1.0+ syntax)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM ERROR] _call_llm: {e}")
        return ""

def extract_events_from_conversation(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extracts events + assistant reply from conversation
    """
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in messages])

    prompt = f"""
You are a helpful AI scheduling assistant. The current date/time is {current_datetime}.

Analyze this conversation and:
1) Extract any events the user wants to schedule.
2) Reply naturally to the user.
3) Return ONLY a valid JSON object.

Format:
{{
  "response":"string",
  "events":[
    {{
      "title":"string",
      "start_time":"YYYY-MM-DD HH:MM:SS",
      "end_time":"YYYY-MM-DD HH:MM:SS"
    }}
  ]
}}

Conversation:
{conversation_text}

Example:
{{"response":"Sure! I scheduled it.","events":[{{"title":"Team meeting","start_time":"2025-12-04 14:00:00"}}]}}
"""

    raw = _call_llm(prompt)

    if not raw:
        return {
            "response": "I'm here to help you schedule events and manage your calendar. What would you like to do?",
            "events": []
        }

    # Try parsing JSON
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        json_str = raw[start:end]
        data = json.loads(json_str)
    except Exception as e:
        print("[PARSE ERROR]", e)
        print("RAW:", raw)
        return {
            "response": "Sorry, I couldn't understand that. Can you rephrase?",
            "events": []
        }

    # Convert to datetime objects if possible
    for ev in data.get("events", []):
        try:
            ev["start_time"] = datetime.strptime(ev["start_time"], "%Y-%m-%d %H:%M:%S")
        except:
            pass

        if "end_time" in ev:
            try:
                ev["end_time"] = datetime.strptime(ev["end_time"], "%Y-%m-%d %H:%M:%S")
            except:
                ev["end_time"] = ev["start_time"] + timedelta(hours=1)

    return data


def transcribe_audio(audio_base64: str) -> str:
    """
    Transcribes audio using the new OpenAI 1.0+ API
    """
    try:
        audio_data = base64.b64decode(audio_base64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(audio_data)
            temp_path = tmp.name

        with open(temp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        return transcript.text

    except Exception as e:
        print("[TRANSCRIBE ERROR]", e)
        return ""



def generate_smart_reminder(event: Any, user_event_history: List[Any]) -> str:
    """
    Agentic AI generates contextual, smart reminders based on user patterns
    """
    
    # Analyze user's typical behavior
    event_times = [e.start_time.hour for e in user_event_history if e.start_time]
    avg_event_time = sum(event_times) / len(event_times) if event_times else 14
    
    # Build context
    history_summary = f"User typically schedules events around {int(avg_event_time)}:00"
    
    prompt = f"""You are an intelligent calendar assistant. Generate a smart, contextual reminder for this upcoming event.

Event: {event.title}
Start Time: {event.start_time}
Location: {event.location or 'Not specified'}
Description: {event.description or 'None'}

User Context: {history_summary}

Generate a brief, helpful reminder that:
- Is personalized and contextual
- Includes relevant preparation tips
- Accounts for travel time if location is specified
- Is encouraging and friendly
- Is under 100 words

Return only the reminder text, no JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"Error generating reminder: {e}")
        return f"Reminder: {event.title} coming up at {event.start_time.strftime('%I:%M %p')}"

def analyze_user_patterns(events: List[Any]) -> Dict[str, Any]:
    """
    Agentic AI analyzes user scheduling patterns and provides insights
    """
    
    event_data = []
    for event in events:
        event_data.append({
            "title": event.title,
            "day_of_week": event.start_time.strftime("%A") if event.start_time else None,
            "hour": event.start_time.hour if event.start_time else None,
            "has_location": bool(event.location),
            "has_attendees": bool(event.attendees and event.attendees != "[]"),
        })
    
    prompt = f"""You are an intelligent calendar analytics assistant. Analyze this user's event patterns and provide insights.

Events from last 30 days:
{json.dumps(event_data, indent=2)}

Analyze and provide:
1. Peak scheduling times (what days/hours they book most)
2. Meeting patterns (solo vs group, location preferences)
3. Scheduling habits (advance planning vs last-minute)
4. Productivity insights
5. Actionable suggestions to optimize their calendar

Return JSON:
{{
    "insights": [
        "Insight 1 about their patterns",
        "Insight 2 about their behavior",
        "Insight 3 about trends"
    ],
    "suggestions": [
        "Actionable suggestion 1",
        "Actionable suggestion 2",
        "Actionable suggestion 3"
    ],
    "peak_hours": [9, 14, 16],
    "peak_days": ["Monday", "Wednesday"]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error analyzing patterns: {e}")
        return {
            "insights": ["Not enough data to analyze patterns yet"],
            "suggestions": ["Keep scheduling events to unlock insights"],
            "peak_hours": [],
            "peak_days": []
        }

def generate_calendar_summary(events: List[Dict[str, Any]]) -> str:
    """
    Generate a natural language summary of calendar events
    """
    
    if not events:
        return "You don't have any upcoming events scheduled."
    
    events_text = "\n".join([
        f"- {event['title']} at {event['start_time'].strftime('%B %d, %I:%M %p')}"
        for event in events
    ])
    
    prompt = f"""Generate a brief, natural summary of these calendar events:

{events_text}

Keep it conversational and friendly, under 100 words. Highlight what's coming up soon."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return f"You have {len(events)} upcoming events."