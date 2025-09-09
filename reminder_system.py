import threading
import time
from datetime import datetime
import winsound   # Windows only

class ReminderSystem:
    def __init__(self):
        self.tasks = []   # list of (task, datetime)
        # Start background thread
        t = threading.Thread(target=self._monitor, daemon=True)
        t.start()

    def check_and_remind(self, task, time_obj):
        """Add a new reminder"""
        self.tasks.append((task, time_obj))
        print(f"🔔 Reminder set for '{task}' at {time_obj}")

    def _monitor(self):
        """Background loop to check reminders"""
        while True:
            now = datetime.now()
            due = []
            for task, t in self.tasks:
                if t and now >= t:
                    due.append((task, t))

            # Trigger reminders
            for task, t in due:
                print(f"⏰ Reminder: {task} (scheduled at {t})")
                try:
                    winsound.Beep(1000, 500)  # freq=1000Hz, duration=500ms
                except RuntimeError:
                    print("⚠️ Could not play sound (non-Windows system).")
                self.tasks.remove((task, t))

            time.sleep(5)  # check every 5 seconds
