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


def main():
    command_queue: queue.Queue = queue.Queue()
    shutdown_event = threading.Event()

    # Start voice listener thread
    listener = VoiceListener(command_queue, shutdown_event)
    listener.start()

    # Build and run the UI (blocking — Tkinter main loop)
    app = KitchenTimerApp(command_queue, shutdown_event)
    app.run()

    # After window closes, ensure everything shuts down
    shutdown_event.set()
    print("[main] Exited.")


if __name__ == "__main__":
    main()
