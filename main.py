from voice_input import capture_and_transcribe
from nlp_parser import parse_task_and_time
from agent_model import AgentScheduler
from calendar_agent import GoogleCalendarAgent
from reminder_system import check_and_remind
import time

# Init
agent = AgentScheduler()
calendar = GoogleCalendarAgent()

print("🎙️ Press ENTER anytime to record your task.")
print("🔁 Reminders are being monitored in the background...\n")

while True:
    # 1. Press ENTER to capture voice
    input("🔘 Press ENTER to speak your task... ")

    # 2. Capture and transcribe
    spoken_text = capture_and_transcribe()

    # 3. NLP parsing
    task, time_obj = parse_task_and_time(spoken_text)

    # 4. If task is parsed, save and schedule
    if task and time_obj:
        agent.remember(task, time_obj)
        calendar.add_event(task, time_obj)
        print(f"✅ Task added: '{task}' at {time_obj.strftime('%I:%M %p')}")
    else:
        print("⚠️ Could not parse task or time.")

    # 5. Background reminder check
    check_and_remind(agent)

    # Sleep for a short while to avoid CPU overload
    time.sleep(5)

