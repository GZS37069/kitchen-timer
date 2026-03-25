"""
Single quadrant widget. Passive — app.py calls update() to refresh its display.
"""

import tkinter as tk
from config import COLORS, FONT_NAME, FONT_TIME, FONT_BADGE, FONT_EMPTY


def _fmt_time(seconds: float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class Quadrant(tk.Frame):
    def __init__(self, parent, on_cancel=None, **kwargs):
        c = COLORS["EMPTY"]
        super().__init__(
            parent,
            bg=c["bg"],
            highlightbackground=c["border"],
            highlightthickness=3,
            **kwargs,
        )

        self._on_cancel = on_cancel
        self._current_name_key = None

        # Badge (top-right): shows "PAUSED" or "OVERTIME"
        self._badge = tk.Label(self, text="", font=FONT_BADGE,
                               bg=c["badge_bg"], fg=c["badge_fg"],
                               padx=8, pady=2)
        self._badge.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

        # Timer name (center-upper)
        self._name_lbl = tk.Label(self, text="", font=FONT_NAME,
                                  bg=c["bg"], fg=c["fg"])
        self._name_lbl.place(relx=0.5, rely=0.35, anchor="center")

        # Time display (center)
        self._time_lbl = tk.Label(self, text="", font=FONT_TIME,
                                  bg=c["bg"], fg=c["fg"])
        self._time_lbl.place(relx=0.5, rely=0.57, anchor="center")

        # Cancel button (bottom-center)
        self._cancel_btn = tk.Button(
            self, text="✕  CANCEL",
            font=FONT_BADGE,
            relief="groove", bd=2,
            padx=20, pady=8,
            command=self._do_cancel,
        )
        self._cancel_btn.place_forget()

        # Empty placeholder
        self._empty_lbl = tk.Label(self, text="— empty —", font=FONT_EMPTY,
                                   bg=c["bg"], fg=c["fg"])
        self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._show_empty()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def update(self, state):
        """
        state: None  → empty
               TimerState → render according to its status
        """
        if state is None:
            self._show_empty()
            return

        from timer.manager import TimerStatus
        status_name = state.status.name  # "RUNNING", "PAUSED", "COMPLETED"
        c = COLORS[status_name]

        self._current_name_key = state.name_key

        # Background & border
        self.config(bg=c["bg"], highlightbackground=c["border"])

        # Name
        self._name_lbl.config(text=state.name.upper(), bg=c["bg"], fg=c["fg"])

        # Time
        if state.status == TimerStatus.COMPLETED:
            time_str = "+" + _fmt_time(state.overtime)
        else:
            time_str = _fmt_time(state.remaining)
        self._time_lbl.config(text=time_str, bg=c["bg"], fg=c["fg"])

        # Badge
        if state.status == TimerStatus.PAUSED:
            self._badge.config(text="PAUSED", bg=c["badge_bg"], fg=c["badge_fg"])
            self._badge.lift()
        elif state.status == TimerStatus.COMPLETED:
            self._badge.config(text="OVERTIME", bg=c["badge_bg"], fg=c["badge_fg"])
            self._badge.lift()
        else:
            self._badge.config(text="")

        # Cancel button
        self._cancel_btn.config(
            bg=c["border"], fg="#ffffff",
            activebackground=c["fg"], activeforeground=c["bg"],
        )
        self._cancel_btn.place(relx=0.5, rely=0.84, anchor="center")
        self._cancel_btn.lift()

        self._empty_lbl.place_forget()
        self._name_lbl.place(relx=0.5, rely=0.35, anchor="center")
        self._time_lbl.place(relx=0.5, rely=0.57, anchor="center")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _show_empty(self):
        c = COLORS["EMPTY"]
        self.config(bg=c["bg"], highlightbackground=c["border"])
        self._badge.config(text="", bg=c["bg"], fg=c["fg"])
        self._cancel_btn.place_forget()
        self._current_name_key = None
        self._name_lbl.place_forget()
        self._time_lbl.place_forget()
        self._empty_lbl.config(bg=c["bg"], fg=c["fg"])
        self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _do_cancel(self):
        if self._on_cancel and self._current_name_key:
            self._on_cancel(self._current_name_key)
