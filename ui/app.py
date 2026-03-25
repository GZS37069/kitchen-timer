"""
Main Tkinter application window.
Owns the root Tk window and the poll_and_tick() heartbeat loop.
"""

import tkinter as tk
import queue
import threading
import os
import sys

from config import ROOT_BG, POLL_INTERVAL_MS
from timer.manager import TimerManager
from ui.quadrant import Quadrant
from ui.sidebar import CommandBanner
from ui.tray import TrayManager
from audio.alerts import AudioWorker


class KitchenTimerApp:
    def __init__(self, command_queue: queue.Queue, shutdown_event: threading.Event):
        self._cmd_q = command_queue
        self._shutdown = shutdown_event

        # Core components
        self._timer_mgr = TimerManager()
        self._audio = AudioWorker(beep_path=self._asset("assets/beep.wav"))
        self._was_active = False  # track previous active state for minimize logic

        # Register callbacks
        self._timer_mgr.on_complete(self._on_timer_complete)
        self._timer_mgr.on_milestone(self._on_timer_milestone)
        self._timer_mgr.on_repeat_beep(self._on_repeat_beep)

        # Build Tk window
        self._root = tk.Tk()
        self._root.title("Kitchen Timer")
        self._root.configure(bg=ROOT_BG)
        self._root.attributes("-fullscreen", True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Allow Escape to exit fullscreen / quit
        self._root.bind("<Escape>", lambda e: self._on_close())

        # Top-level horizontal layout: sidebar | timer grid
        outer = tk.Frame(self._root, bg=ROOT_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        # Left sidebar
        sidebar = CommandBanner(outer)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)

        # Build 2×2 quadrant grid
        frame = tk.Frame(outer, bg=ROOT_BG)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self._quadrants: list[Quadrant] = []
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for row, col in positions:
            q = Quadrant(frame, on_cancel=self._on_cancel_timer)
            q.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            self._quadrants.append(q)

        # System tray
        self._tray = TrayManager(command_queue, shutdown_event)
        self._tray.start(self._root)

        # Start heartbeat
        self._root.after(POLL_INTERVAL_MS, self._poll_and_tick)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self):
        """Start the Tkinter main loop (blocking)."""
        self._root.mainloop()

    # ------------------------------------------------------------------
    # Heartbeat (main thread only)
    # ------------------------------------------------------------------

    def _poll_and_tick(self):
        try:
            if self._shutdown.is_set():
                self._root.destroy()
                return

            # 1. Drain command queue
            while True:
                try:
                    cmd = self._cmd_q.get_nowait()
                    print(f"[ui] Command received: {cmd}")
                    self._handle_command(cmd)
                except queue.Empty:
                    break

            # 2. Tick timers
            self._timer_mgr.tick()

            # 3. Refresh quadrant widgets
            snapshot = self._timer_mgr.snapshot()
            for i, state in enumerate(snapshot):
                self._quadrants[i].update(state)

            # 4. Auto-minimize when all timers clear
            active = self._timer_mgr.active_count()
            if active == 0 and self._was_active:
                self._tray.hide()
            self._was_active = active > 0

        except Exception as e:
            import traceback
            print(f"[ui] ERROR in poll_and_tick: {e}")
            traceback.print_exc()

        finally:
            # Always reschedule even if an error occurred
            self._root.after(POLL_INTERVAL_MS, self._poll_and_tick)

    # ------------------------------------------------------------------
    # Command dispatch (main thread)
    # ------------------------------------------------------------------

    def _handle_command(self, cmd: dict):
        t = cmd.get("type")

        if t == "ADD":
            self._tray.show()
            ok = self._timer_mgr.add(cmd["name"], cmd["duration"])
            print(f"[ui] ADD '{cmd['name']}' {cmd['duration']}s -> {'ok' if ok else 'FULL'}")
            if not ok:
                self._audio.speak("All timers are in use")

        elif t == "CANCEL":
            self._timer_mgr.cancel(cmd["name"])
            # minimize handled automatically in poll_and_tick if no timers remain

        elif t == "PAUSE":
            ok = self._timer_mgr.pause(cmd["name"])
            if not ok:
                self._audio.speak(f"No running timer named {cmd['name']}")

        elif t == "RESUME":
            ok = self._timer_mgr.resume(cmd["name"])
            if not ok:
                self._audio.speak(f"No paused timer named {cmd['name']}")

        elif t == "SHOW":
            self._tray.show()

        elif t == "QUIT":
            self._on_close()

    def _on_cancel_timer(self, name_key: str):
        """Called by a quadrant's Cancel button."""
        self._cmd_q.put({"type": "CANCEL", "name": name_key})

    # ------------------------------------------------------------------
    # Timer completion callback (called from tick, main thread)
    # ------------------------------------------------------------------

    def _on_timer_complete(self, name: str):
        self._audio.beep_and_speak(f"Timer {name} complete")

    def _on_repeat_beep(self, name: str):
        self._audio.beep()

    def _on_timer_milestone(self, name: str, seconds: int):
        if seconds >= 60:
            minutes = seconds // 60
            text = f"{name}, {minutes} minute{'s' if minutes > 1 else ''} remaining"
        else:
            text = f"{name}, {seconds} seconds remaining"
        print(f"[ui] Milestone: {text}")
        self._audio.speak(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_close(self):
        if not self._shutdown.is_set():
            self._shutdown.set()
        self._root.destroy()

    @staticmethod
    def _asset(path: str) -> str:
        """Resolve asset path relative to this file's directory."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, path)
