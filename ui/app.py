"""
Main Tkinter application window.
Owns the root Tk window and the poll_and_tick() heartbeat loop.
"""

import tkinter as tk
import queue
import subprocess
import threading
import os
import sys
import ctypes

from config import ROOT_BG, POLL_INTERVAL_MS
from timer.manager import TimerManager
from ui.quadrant import Quadrant
from ui.sidebar import CommandBanner
from ui.tray import TrayManager
from audio.alerts import AudioWorker


class KitchenTimerApp:
    def __init__(self, command_queue: queue.Queue, shutdown_event: threading.Event, audio: AudioWorker = None):
        self._cmd_q = command_queue
        self._shutdown = shutdown_event

        # Core components
        self._timer_mgr = TimerManager()
        self._audio = audio or AudioWorker(beep_path=self._asset("assets/beep.wav"))

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

        # Bottom bar: transcript (left) + version (right)
        bottom_bar = tk.Frame(self._root, bg="#0d0d1a")
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._transcript_label = tk.Label(
            bottom_bar,
            text="",
            bg="#0d0d1a",
            fg="#8888aa",
            font=("Helvetica", 14),
            anchor="w",
            padx=12,
            pady=6,
        )
        self._transcript_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            bottom_bar,
            text=self._version_string(),
            bg="#0d0d1a",
            fg="#444466",
            font=("Helvetica", 10),
            anchor="e",
            padx=12,
            pady=6,
        ).pack(side=tk.RIGHT)

        self._transcript_clear_id = None

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

        # Screensaver suppression state
        self._display_awake = False

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
                self._quit()
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

            # 4. Suppress screensaver while any timer is active
            self._update_display_lock()

            # (auto-minimize removed — UI stays visible until explicitly closed)

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
            # If a completed timer with this name exists, repeat it in-place instead
            # of adding a duplicate to a new slot.
            name_key = cmd["name"].strip().lower()
            repeated = self._timer_mgr.repeat(name_key, completed_only=True)
            if repeated:
                print(f"[ui] ADD '{cmd['name']}' -> completed timer found, repeating in-place")
                self._audio.clear()
                self._audio.speak(f"Repeating {repeated}")
            else:
                self._tray.show()
                ok = self._timer_mgr.add(cmd["name"], cmd["duration"])
                print(f"[ui] ADD '{cmd['name']}' {cmd['duration']}s -> {'ok' if ok else 'FULL'}")
                if not ok:
                    self._audio.speak("All timers are in use")

        elif t == "CANCEL":
            self._audio.clear()
            self._timer_mgr.cancel(cmd["name"])

        elif t == "CANCEL_ALL":
            self._audio.clear()
            self._timer_mgr.cancel_all()

        elif t == "PAUSE":
            ok = self._timer_mgr.pause(cmd["name"])
            if not ok:
                self._audio.speak(f"No running timer named {cmd['name']}")

        elif t == "RESUME":
            ok = self._timer_mgr.resume(cmd["name"])
            if not ok:
                self._audio.speak(f"No paused timer named {cmd['name']}")

        elif t == "REPEAT":
            target = cmd.get("name")
            print(f"[ui] REPEAT requested, name_key={repr(target)}, slots={[(s.name, s.status.name) if s else None for s in self._timer_mgr.snapshot()]}")
            name = self._timer_mgr.repeat(target)
            print(f"[ui] REPEAT result: {repr(name)}")
            if name:
                self._audio.clear()
                self._audio.speak(f"Repeating {name}")
            else:
                self._audio.speak("No completed timer to repeat")

        elif t == "SHOW":
            self._tray.show()

        elif t == "QUIT":
            self._on_close()

        elif t == "_HEARD":
            self._show_transcript(cmd.get("text", ""), cmd.get("cmd"))

    def _show_transcript(self, text: str, parsed_cmd: dict | None):
        """Update the bottom banner with the heard transcript and parsed result."""
        if self._transcript_clear_id is not None:
            self._root.after_cancel(self._transcript_clear_id)

        if parsed_cmd:
            t = parsed_cmd.get("type", "?")
            name = parsed_cmd.get("name", "")
            duration = parsed_cmd.get("duration")
            if duration:
                detail = f"{name}  {duration}s" if name else f"{duration}s"
            else:
                detail = name
            label = f"▶  \"{text}\"   →   {t}{':  ' + detail if detail else ''}"
            self._transcript_label.config(fg="#66ffaa", text=label)
        else:
            label = f"▶  \"{text}\"   →   not recognized"
            self._transcript_label.config(fg="#ffaa44", text=label)

        self._transcript_clear_id = self._root.after(5000, self._clear_transcript)

    def _clear_transcript(self):
        self._transcript_label.config(text="")
        self._transcript_clear_id = None

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

    def _update_display_lock(self):
        """Prevent screensaver/display-off while any timer is active; restore when idle."""
        # ES_CONTINUOUS = 0x80000000, ES_DISPLAY_REQUIRED = 0x00000002
        ES_CONTINUOUS       = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        has_active = self._timer_mgr.active_count() > 0
        if has_active and not self._display_awake:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED)
            self._display_awake = True
        elif not has_active and self._display_awake:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            self._display_awake = False

    def _quit(self):
        """Single shutdown path — says goodbye, then destroys the window."""
        if hasattr(self, '_quitting'):
            return
        self._quitting = True
        self._shutdown.set()
        # Release display lock before exit
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS
        self._audio.speak_and_wait("Goodbye")
        self._root.destroy()

    def _on_close(self):
        self._quit()

    @staticmethod
    def _version_string() -> str:
        """Return 'Version 1.MMDDYY' based on the last git commit date."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cd", "--date=format:%m%d%y"],
                capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            date = result.stdout.strip()
            if date:
                return f"Version 1.{date}"
        except Exception:
            pass
        return "Version 1"

    @staticmethod
    def _asset(path: str) -> str:
        """Resolve asset path relative to this file's directory."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, path)
