from datetime import datetime, timedelta
from plyer import notification # type: ignore
import platform
import winsound

# Only import winsound on Windows
if platform.system() == "Windows":
    import winsound

class AgentScheduler:
    def __init__(self):
        self.memory = []  # store past tasks

    def interpret(self, user_input):
        # Send to Ollama LLM
        response = self.call_ollama(user_input)
        task, time = self.extract_task_time(response)
        decision = self.decide_action(task, time)
        return task, time, decision

    def call_ollama(self, prompt):
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "phi", "prompt": f"""Extract the task and time from this input: "{prompt}". Respond in JSON like: {{ "task": "...", "time": "..." }}"""}
        )
        return response.json()["response"]

    def extract_task_time(self, response):
        import json
        try:
            parsed = json.loads(response)
            return parsed.get("task"), parsed.get("time")
        except Exception:
            return None, None

    def decide_action(self, task, time):
        if not task or not time:
            return "ask_user"
        # You can add more decision logic here
        if "meeting" in task.lower():
            return "add_to_calendar"
        return "set_reminder"

    def remember(self, task, time):
        self.memory.append({"task": task, "time": time})

    def check_tasks(self, current_time):
        updated_memory = []
        for task in self.memory:
            task_time = task.get("time")
            task_name = task.get("task")

            if isinstance(task_time, str):
                task_time = datetime.fromisoformat(task_time)

            # Trigger reminder if due within the current minute
            if 0 <= (task_time - current_time).total_seconds() <= 60:
                self.remind(task_name)
            else:
                updated_memory.append(task)

        self.memory = updated_memory
    def add_task(self, task_text, time_obj):
        from calendar_agent import CalendarAgent
        cal = CalendarAgent()
        cal.authenticate()
        cal.add_event(task_text, time_obj)

    def remind(self, task_name):
        print(f"🔔 Reminder: {task_name}")
        try:
            winsound.Beep(1000, 500)
        except:
            print("🔇 Beep not available.")
        try:
            notification.notify(
                title="Reminder",
                message=task_name,
                timeout=5
            )
        except:
            print("⚠️ Notification failed.")
            
    def call_llm_phi(text):
        print("📡 Dummy call_llm_phi received text:", text)
        # Simulate failure so rule-based fallback works
        return None, None
