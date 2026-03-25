"""
Voice listener: continuous Vosk microphone loop.

Strategy: run one recognizer continuously. On each final result, check if
"kitchen" appears in the text. If so, parse it immediately — the full command
is already in the same utterance (e.g. "kitchen add 10 minute timer for steak").

If only the wake word came through with no parseable command (user paused
after saying "kitchen"), we enter a short capture window to grab the
follow-up utterance.
"""

import json
import queue
import re
import threading
import time
import os

from config import WAKE_WORD, AUDIO_SAMPLE_RATE, AUDIO_CHUNK_SIZE, COMMAND_TIMEOUT_SECS, VOSK_MODEL_PATH
from voice.parser import parse

# Require at least one word before "kitchen" or "janet" — catches "hey kitchen",
# "hey janet", "a kitchen", etc. regardless of how Vosk transcribes "hey"
_WAKE_RE = re.compile(r'\b\w+\s+(?:kitchen|janet)\b', re.IGNORECASE)

def _wake_word_detected(text: str) -> bool:
    return bool(_WAKE_RE.search(text))


class VoiceListener:
    def __init__(self, command_queue: queue.Queue, shutdown_event: threading.Event, audio=None):
        self._cmd_q = command_queue
        self._shutdown = shutdown_event
        self._audio = audio
        self._thread = threading.Thread(target=self._run, daemon=True, name="VoiceListener")

    def start(self):
        self._thread.start()

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _run(self):
        try:
            from vosk import Model, KaldiRecognizer
            import pyaudio
        except ImportError as e:
            print(f"[voice] Missing dependency: {e}")
            return

        model_path = self._resolve_model_path()
        if not os.path.isdir(model_path):
            print(f"[voice] Vosk model not found at: {model_path}")
            return

        print("[voice] Loading Vosk model...")
        model = Model(model_path)
        print(f"[voice] Ready — listening for wake word: '{WAKE_WORD}'")

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=AUDIO_SAMPLE_RATE,
            input=True,
            frames_per_buffer=AUDIO_CHUNK_SIZE,
        )
        stream.start_stream()

        try:
            rec = KaldiRecognizer(model, AUDIO_SAMPLE_RATE)

            while not self._shutdown.is_set():
                data = stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)

                if rec.AcceptWaveform(data):
                    # Final result — full sentence recognized
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if not text:
                        continue

                    print(f"[voice] Heard: '{text}'")

                    if not _wake_word_detected(text):
                        continue  # not a kitchen command

                    if self._audio:
                        self._audio.ping()

                    # Try to parse the command from this utterance
                    cmd = parse(text)
                    if cmd:
                        print(f"[voice] Parsed: {cmd}")
                        self._cmd_q.put({"type": "_HEARD", "text": text, "cmd": cmd})
                        self._cmd_q.put(cmd)
                    else:
                        # Wake word heard but no command yet — capture next utterance
                        print("[voice] Wake word detected, waiting for command...")
                        rec2 = KaldiRecognizer(model, AUDIO_SAMPLE_RATE)
                        utterance = self._capture_next(stream, rec2)
                        if utterance:
                            print(f"[voice] Follow-up: '{utterance}'")
                            # Prepend "kitchen" so parser patterns match
                            has_wake = re.match(r'(?:kitchen|janet)\b', utterance, re.IGNORECASE)
                            full = utterance if has_wake else f"kitchen {utterance}"
                            cmd = parse(full)
                            if cmd:
                                print(f"[voice] Parsed: {cmd}")
                            else:
                                print("[voice] Could not parse command.")
                            self._cmd_q.put({"type": "_HEARD", "text": utterance, "cmd": cmd})
                            if cmd:
                                self._cmd_q.put(cmd)
                        else:
                            self._cmd_q.put({"type": "_HEARD", "text": "(no follow-up heard)", "cmd": None})
                else:
                    # Partial result — just show for debugging
                    partial = json.loads(rec.PartialResult())
                    p = partial.get("partial", "")
                    if p:
                        print(f"[voice] ... {p}")

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _capture_next(self, stream, rec) -> str:
        """Capture one utterance (final result) within the timeout window."""
        deadline = time.monotonic() + COMMAND_TIMEOUT_SECS
        while time.monotonic() < deadline and not self._shutdown.is_set():
            data = stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text:
                    return text
        # Flush
        final = json.loads(rec.FinalResult())
        return final.get("text", "").strip()

    @staticmethod
    def _resolve_model_path() -> str:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, VOSK_MODEL_PATH)
