# Kitchen Timer Project

## Project Overview

Voice-controlled kitchen timer app for Windows. Manages up to 4 simultaneous timers via natural speech commands. Fullscreen Tkinter GUI with system tray integration.

## Tech Stack

- **Python 3.x** — primary language
- **Tkinter** — GUI (built-in)
- **Vosk** — offline speech recognition (16kHz mono)
- **PyAudio** — microphone input
- **pyttsx3 / win32com (SAPI)** — TTS; prefer SAPI, fall back to pyttsx3
- **pygame** — audio playback (beeps)
- **pystray + Pillow** — system tray icon
- **NumPy** — beep waveform synthesis

**Windows only** — relies on pyaudio and win32com/SAPI.

## Project Structure

```
kitchen-timer/
├── main.py              # Entry point; wires all components
├── config.py            # Central config (colors, fonts, wake words, timing constants)
├── requirements.txt
├── start.bat            # Launch silently via pythonw.exe
├── assets/              # beep.wav generated at runtime if missing
├── audio/alerts.py      # AudioWorker thread — beep + TTS queue
├── timer/manager.py     # TimerManager, TimerState, TimerStatus state machine
├── ui/app.py            # KitchenTimerApp — Tkinter window + heartbeat loop
├── ui/quadrant.py       # Single 2×2 grid cell widget
├── ui/sidebar.py        # Left sidebar — voice command reference
├── ui/tray.py           # TrayManager — system tray show/hide
├── voice/listener.py    # VoiceListener — Vosk mic loop, wake word, 2-stage capture
├── voice/parser.py      # NLP parsing — spoken numbers, durations → command dicts
└── models/
    └── vosk-model-small-en-us-0.15/
```

## Architecture

### Threading Model
- **Main thread** — Tkinter event loop + all timer state mutations (no locks needed)
- **VoiceListener thread** — Vosk mic loop, pushes parsed commands to a queue
- **AudioWorker thread** — serialized beep/TTS via async queue
- **TrayManager thread** — pystray event loop

All timer state changes happen on the main thread via `poll_and_tick()` — thread safety via single-threaded access, not locks.

### Heartbeat Loop (100ms)
`KitchenTimerApp._poll_and_tick()`:
1. Drain voice command queue
2. Tick RUNNING timers
3. Fire completion/milestone callbacks (TTS, beeps)
4. Refresh quadrant widgets
5. Auto-minimize to tray when `active_count() == 0`

### Voice Recognition (2-Stage)
1. Listen continuously for wake word: **"hey kitchen"** or **"hey janet"**
2. If no command in same utterance, open 5-second capture window for follow-up
3. `voice/parser.py` converts transcript to typed command dict via regex

### Timer State Machine
States: `RUNNING` → `PAUSED` → `RUNNING`, or `RUNNING` → `COMPLETED`

`TimerState` fields:
- `remaining: float` — current seconds (float for precision)
- `total: float` — original duration (immutable)
- `announced: set` — milestones already announced (prevents duplicate TTS)
- `last_beep_at: float` — timestamp for repeat beeps every 5s while COMPLETED

### Command Dict Format
```python
{"type": "ADD",    "name": "Pasta", "duration": 300}
{"type": "CANCEL", "name": "pasta"}   # name_key (lowercase)
{"type": "PAUSE",  "name": "pasta"}
{"type": "RESUME", "name": "pasta"}
{"type": "SHOW"}
{"type": "QUIT"}
```

## Conventions

### Naming
- `name` — display name, title-cased (e.g., `"Pasta"`)
- `name_key` — lowercase lookup key (e.g., `"pasta"`)
- Private methods/attributes — `_prefix`

### Code Style
- Type hints throughout
- Module-level docstrings on every file
- Callbacks registered via `on_complete()`, `on_milestone()`, `on_repeat_beep()`
- Graceful degradation everywhere (TTS, audio init, Vosk model missing)
- Exception handling with traceback logging in `poll_and_tick()`

### Config
All magic numbers live in `config.py` — colors, fonts, timing constants, wake words, model path.

### Color Theming (state-driven)
- `EMPTY` — dark blue, dimmed text
- `RUNNING` — bright blue border, white text
- `PAUSED` — purple + "PAUSED" badge
- `COMPLETED` — red + "OVERTIME" badge

## Audio Behavior
- **Completion:** 880Hz beep (0.4s) + TTS "Timer [Name] complete"
- **Milestones:** TTS at 2 min, 1 min, 30 sec remaining (skipped if >= total duration)
- **Repeat alerts:** beep every 5s while COMPLETED
- If `assets/beep.wav` missing, synthesized on-the-fly from NumPy sine wave

## No Tests
No automated test suite. Manual testing only.

## Running the App
```bat
start.bat          # Preferred — silent launch via pythonw.exe
python main.py     # Dev launch with console output
```
Requires Python 3.x, all requirements installed, and `models/vosk-model-small-en-us-0.15/` present.
