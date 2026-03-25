"""
Central configuration for Kitchen Timer app.
"""

# Voice
WAKE_WORD = "hey kitchen / hey janet"
COMMAND_TIMEOUT_SECS = 5
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# Timers
MAX_TIMERS = 4

# Audio
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = 4000  # ~125ms of audio at 16kHz

# UI update interval (ms)
POLL_INTERVAL_MS = 100

# Colors per timer state
COLORS = {
    "EMPTY": {
        "bg": "#1a1a2e",
        "fg": "#444466",
        "border": "#333355",
        "badge_bg": "#1a1a2e",
        "badge_fg": "#444466",
    },
    "RUNNING": {
        "bg": "#0f3460",
        "fg": "#e0e0ff",
        "border": "#4444ff",
        "badge_bg": "#0f3460",
        "badge_fg": "#e0e0ff",
    },
    "PAUSED": {
        "bg": "#2d1b4e",
        "fg": "#cc99ff",
        "border": "#8844cc",
        "badge_bg": "#8844cc",
        "badge_fg": "#ffffff",
    },
    "COMPLETED": {
        "bg": "#3d0000",
        "fg": "#ff6666",
        "border": "#ff2222",
        "badge_bg": "#ff2222",
        "badge_fg": "#ffffff",
    },
}

# Root window background
ROOT_BG = "#1a1a2e"

# Fonts (tkinter format)
FONT_NAME = ("Helvetica", 52, "bold")
FONT_TIME = ("Courier", 80, "bold")
FONT_BADGE = ("Helvetica", 16, "bold")
FONT_EMPTY = ("Helvetica", 24)
