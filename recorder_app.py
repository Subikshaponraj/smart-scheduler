# recorder_app.py
import tkinter as tk
import sounddevice as sd
import numpy as np
import wave
import threading

class RecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎙️ Simple Recorder")
        self.is_recording = False
        self.fs = 44100  # Sample rate
        self.frames = []

        # Buttons
        self.start_btn = tk.Button(root, text="Start Recording", command=self.start_recording, bg="blue", fg="white")
        self.start_btn.pack(pady=10)

        self.stop_btn = tk.Button(root, text="Stop Recording", command=self.stop_recording, bg="darkblue", fg="white")
        self.stop_btn.pack(pady=10)

        self.status_label = tk.Label(root, text="Press Start to record...", font=("Arial", 8))
        self.status_label.pack(pady=10)

    def callback(self, indata, frames, time, status):
        if self.is_recording:
            self.frames.append(indata.copy())

    def start_recording(self):
        self.frames = []
        self.is_recording = True
        self.status_label.config(text="🎤 Recording...")

        # Run recording in a thread (to avoid freezing the UI)
        threading.Thread(target=self._record).start()

    def _record(self):
        with sd.InputStream(samplerate=self.fs, channels=1, callback=self.callback):
            while self.is_recording:
                sd.sleep(100)

    def stop_recording(self):
        self.is_recording = False
        self.status_label.config(text="✅ Recording stopped. Saved as output.wav")

        # Save recording
        audio_data = np.concatenate(self.frames, axis=0)
        with wave.open("input.wav", "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.fs)
            wf.writeframes(audio_data.tobytes())

if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()
