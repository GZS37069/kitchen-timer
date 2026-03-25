"""
Left-side command reference banner.
"""

import tkinter as tk

_BG       = "#13132a"
_BORDER   = "#2a2a4a"
_TITLE_FG = "#9999dd"
_HEAD_FG  = "#6699ff"
_CMD_FG   = "#ddddf0"
_EX_FG    = "#55556a"
_DIV_FG   = "#252545"

_SECTIONS = [
    (
        "ADD TIMER",
        "kitchen, add [time] timer for [name]\nkitchen, add a timer for [time]",
        '"kitchen add 10 minute timer for pasta"\n"kitchen start a timer for 10 minutes"',
    ),
    (
        "PAUSE / RESUME",
        "kitchen, pause [name] timer\nkitchen, resume [name] timer",
        '"kitchen pause pasta timer"\n"kitchen resume pasta timer"',
    ),
    (
        "CANCEL",
        "kitchen, cancel [name] timer\nor click ✕ CANCEL on the timer",
        '"kitchen cancel pasta timer"',
    ),
]


_WIDTH = 840


class CommandBanner(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=_BG, width=_WIDTH,
                         highlightbackground=_BORDER,
                         highlightthickness=1, **kwargs)
        self.pack_propagate(False)

        # ── Title ──────────────────────────────────────────────
        tk.Label(self, text="VOICE COMMANDS",
                 font=("Helvetica", 36, "bold"),
                 bg=_BG, fg=_TITLE_FG,
                 anchor="center").pack(fill=tk.X, padx=16, pady=(26, 8))

        self._divider()

        # ── Wake word ──────────────────────────────────────────
        tk.Label(self, text="Wake word",
                 font=("Helvetica", 28),
                 bg=_BG, fg=_EX_FG,
                 anchor="w").pack(fill=tk.X, padx=22, pady=(16, 2))
        tk.Label(self, text='"hey kitchen"  or  "hey janet"',
                 font=("Courier", 34, "bold"),
                 bg=_BG, fg=_CMD_FG,
                 anchor="w").pack(fill=tk.X, padx=22, pady=(0, 16))

        self._divider()

        # ── Command sections ───────────────────────────────────
        for heading, syntax, example in _SECTIONS:
            self._section(heading, syntax, example)

    # ── helpers ────────────────────────────────────────────────

    def _divider(self):
        tk.Frame(self, bg=_DIV_FG, height=1).pack(fill=tk.X, padx=12)

    def _section(self, heading: str, syntax: str, example: str):
        tk.Label(self, text=heading,
                 font=("Helvetica", 30, "bold"),
                 bg=_BG, fg=_HEAD_FG,
                 anchor="w").pack(fill=tk.X, padx=22, pady=(16, 4))

        tk.Label(self, text=syntax,
                 font=("Helvetica", 26),
                 bg=_BG, fg=_CMD_FG,
                 justify="left", anchor="w").pack(fill=tk.X, padx=22)

        tk.Label(self, text=example,
                 font=("Helvetica", 26, "italic"),
                 bg=_BG, fg=_EX_FG,
                 justify="left", anchor="w").pack(fill=tk.X, padx=22, pady=(6, 14))

        self._divider()
