"""
Audio worker: serializes pygame beep + pyttsx3 TTS on a dedicated daemon thread.
Both libraries have thread-affinity requirements — they must be created and used
on the same thread.
"""

import queue
import threading
import os


class AudioWorker:
    def __init__(self, beep_path: str = "assets/beep.wav"):
        self._queue: queue.Queue = queue.Queue()
        self._beep_path = beep_path
        self._thread = threading.Thread(target=self._run, daemon=True, name="AudioWorker")
        self._thread.start()

    def ping(self):
        """Queue a short wake-word acknowledgement ping."""
        self._queue.put({"action": "PING", "text": ""})

    def beep(self):
        """Queue a beep only."""
        self._queue.put({"action": "BEEP", "text": ""})

    def beep_and_speak(self, text: str):
        """Queue a beep followed by a TTS announcement."""
        self._queue.put({"action": "BEEP_AND_SPEAK", "text": text})

    def speak(self, text: str):
        """Queue a TTS-only announcement."""
        self._queue.put({"action": "SPEAK", "text": text})

    def speak_and_wait(self, text: str):
        """Speak text and block until TTS finishes (for use at shutdown)."""
        self._queue.put({"action": "SPEAK", "text": text})
        self._queue.join()

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _run(self):
        pygame_ok = self._init_pygame()
        engine = self._init_tts()

        while True:
            msg = self._queue.get()
            action = msg.get("action")
            text = msg.get("text", "")

            if action == "PING" and pygame_ok:
                try:
                    self._play_ping()
                except Exception as e:
                    print(f"[audio] ping error: {e}")

            if action in ("BEEP", "BEEP_AND_SPEAK") and pygame_ok:
                try:
                    self._play_beep()
                except Exception as e:
                    print(f"[audio] beep error: {e}")

            if action in ("SPEAK", "BEEP_AND_SPEAK"):
                if engine is not None:
                    try:
                        print(f"[audio] Speaking: '{text}'")
                        kind, backend = engine
                        if kind == "sapi":
                            backend.Speak(text)
                        else:
                            backend.say(text)
                            backend.runAndWait()
                        print(f"[audio] Done speaking")
                    except Exception as e:
                        print(f"[audio] TTS error: {e}")
                else:
                    print(f"[audio] TTS skipped (no engine): '{text}'")

            self._queue.task_done()

    def _init_pygame(self) -> bool:
        try:
            import pygame
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._pygame = pygame
            # Pre-load beep sound
            if os.path.exists(self._beep_path):
                self._beep_sound = pygame.mixer.Sound(self._beep_path)
            else:
                # Generate a simple beep programmatically
                self._beep_sound = self._generate_beep()
            self._ping_sound = self._generate_ping()
            return True
        except Exception as e:
            print(f"[audio] pygame init failed (beep disabled): {e}")
            return False

    def _generate_beep(self):
        """Generate a simple 880Hz beep as stereo (required by pygame channels=2)."""
        import pygame
        import numpy as np
        sample_rate = 22050
        duration = 0.4  # seconds
        freq = 880
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        mono = (np.sin(2 * np.pi * freq * t) * 32767 * 0.5).astype(np.int16)
        stereo = np.column_stack([mono, mono])  # shape: (N, 2)
        sound = pygame.sndarray.make_sound(stereo)
        return sound

    def _generate_ping(self):
        """Generate a short 1200Hz ping to acknowledge wake word detection."""
        import pygame
        import numpy as np
        sample_rate = 22050
        duration = 0.12
        freq = 1200
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # Fade out to avoid click
        envelope = np.linspace(1.0, 0.0, len(t))
        mono = (np.sin(2 * np.pi * freq * t) * envelope * 32767 * 1.0).astype(np.int16)
        stereo = np.column_stack([mono, mono])
        return pygame.sndarray.make_sound(stereo)

    def _play_ping(self):
        self._ping_sound.play()
        length_ms = int(self._ping_sound.get_length() * 1000) + 20
        self._pygame.time.wait(length_ms)

    def _play_beep(self):
        self._beep_sound.play()
        length_ms = int(self._beep_sound.get_length() * 1000) + 50
        self._pygame.time.wait(length_ms)

    def _init_tts(self):
        # Try win32com SAPI first (most reliable on Windows 11)
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = -1   # slightly slower than default
            speaker.Volume = 100
            print("[audio] TTS: using Windows SAPI via win32com")
            return ("sapi", speaker)
        except Exception as e:
            print(f"[audio] win32com SAPI failed: {e}")

        # Fallback: pyttsx3
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)
            print("[audio] TTS: using pyttsx3")
            return ("pyttsx3", engine)
        except Exception as e:
            print(f"[audio] pyttsx3 init failed (TTS disabled): {e}")
            return None
