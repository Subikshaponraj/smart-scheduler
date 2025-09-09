import dateparser
import re
import requests
from datetime import datetime

def call_llm_phi(prompt):
    try:
        # Improved prompt with examples
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "phi",
            "prompt": f"""Extract the task and time from this sentence. Examples:
            
            Input: "submit the report at 5 p.m. today"
            Output: Task: submit the report\nTime: 5 p.m. today
            
            Input: "summit mic report at 5 p.m. today"
            Output: Task: summit mic report\nTime: 5 p.m. today
            
            Input: "{prompt}"
            Respond ONLY in this format:
            Task: <task>
            Time: <time or None>""",
            "stream": False
        })
        if response.status_code == 200:
            output = response.json()["response"]
            task_match = re.search(r"Task:\s*(.*)", output)
            time_match = re.search(r"Time:\s*(.*)", output)
            task = task_match.group(1).strip() if task_match else None
            time_str = time_match.group(1).strip() if time_match else None
            
            # Parse the time string to datetime object
            if time_str and time_str.lower() != "none":
                time_obj = dateparser.parse(time_str, settings={'PREFER_DATES_FROM': 'future'})
                return task, time_obj
            return task, None
        else:
            return None, None
    except Exception as e:
        print("⚠️ LLM call failed:", e)
        return None, None

def rule_based_parser(text):
    # First try to extract time and then task
    time_matches = re.finditer(r'(\d{1,2}(:\d{2})?\s*(a\.?m\.?|p\.?m\.?)|today|tomorrow|noon|midnight)', text, re.IGNORECASE)
    
    for match in time_matches:
        time_str = match.group(0)
        time_obj = dateparser.parse(time_str, settings={'PREFER_DATES_FROM': 'future'})
        if time_obj:
            # Extract everything before the time as task
            task = text[:match.start()].strip()
            if not task:
                # If time is at start, try to get task after time
                task = text[match.end():].strip()
            
            # Clean up task from connecting words
            task = re.sub(r'^(to|about|for|me|that|please|remind)\s*', '', task, flags=re.IGNORECASE).strip()
            task = re.sub(r'\s*(at|by|on|before)\s*$', '', task, flags=re.IGNORECASE).strip()
            
            if task:
                return task, time_obj
    
    # Fallback: try dateparser on full text
    time_obj = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
    if time_obj:
        # Remove time words to get task
        time_words = r'at\s*\d|on\s*\w+|today|tomorrow|noon|midnight'
        task = re.sub(time_words, '', text, flags=re.IGNORECASE).strip()
        if task:
            return task, time_obj
    
    return None, None

def parse_task_and_time(text):
    print(f"🔍 Parsing: '{text}'")
    
    # First try rule-based as it's faster
    task, time_obj = rule_based_parser(text)
    if task and time_obj:
        print(f"✅ Rule-based parsed: Task: {task}, Time: {time_obj}")
        return task, time_obj
    
    # Fallback to LLM if rule-based fails
    print("⚠️ Rule-based failed. Trying LLM...")
    task, time_obj = call_llm_phi(text)
    if task and time_obj:
        print(f"✅ LLM parsed: Task: {task}, Time: {time_obj}")
        return task, time_obj
    
    print("❌ All parsing methods failed")
    return None, None

