"""
Kitchen Timer — entry point.
Wires all components together and starts the Tkinter main loop.
"""

import queue
import threading
import os
import sys

# Ensure imports resolve from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice.listener import VoiceListener
from ui.app import KitchenTimerApp
from audio.alerts import AudioWorker


def main():
    command_queue: queue.Queue = queue.Queue()
    shutdown_event = threading.Event()

    # Shared audio worker (beeps, TTS, and wake-word ping)
    audio = AudioWorker(beep_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "beep.wav"))

    # Start voice listener thread
    listener = VoiceListener(command_queue, shutdown_event, audio=audio)
    listener.start()

    # Build and run the UI (blocking — Tkinter main loop)
    app = KitchenTimerApp(command_queue, shutdown_event, audio=audio)
    app.run()

    # After window closes, ensure everything shuts down
    shutdown_event.set()
    print("[main] Exited.")


if __name__ == "__main__":
    main()
