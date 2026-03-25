"""
Timer state machine and manager.
All methods are called exclusively from the main (Tkinter) thread via poll_and_tick,
so no locking is required.
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class TimerStatus(Enum):
    RUNNING   = auto()
    PAUSED    = auto()
    COMPLETED = auto()


# Milestones (seconds remaining) at which to announce time left
ANNOUNCE_MILESTONES = [120, 60, 30]  # 2 minutes, 1 minute, 30 seconds


@dataclass
class TimerState:
    slot: int
    name: str           # Title-cased display name, e.g. "Steak"
    name_key: str       # Lowercase lookup key, e.g. "steak"
    total: int          # Original duration in seconds
    remaining: float    # Seconds left (float for sub-second accuracy)
    status: TimerStatus
    completed_at: float = 0.0   # time.monotonic() when it hit zero
    overtime: float = 0.0       # seconds elapsed since completion
    announced: set = None       # milestones already announced
    last_beep_at: float = 0.0   # time.monotonic() of last completion beep

    def __post_init__(self):
        if self.announced is None:
            # Skip milestones that are >= the timer's total duration
            self.announced = {m for m in ANNOUNCE_MILESTONES if m >= self.total}


class TimerManager:
    def __init__(self):
        # None = empty slot
        self._slots: list[Optional[TimerState]] = [None] * 4
        self._last_tick: float = time.monotonic()
        # Callbacks fired when a timer completes: (name: str) -> None
        self._on_complete_callbacks: list = []
        # Callbacks fired at time milestones: (name: str, seconds_remaining: int) -> None
        self._on_milestone_callbacks: list = []
        # Callbacks fired for repeat beep on completed timers: (name: str) -> None
        self._on_repeat_beep_callbacks: list = []

    # ------------------------------------------------------------------
    # Public API (all called from main thread)
    # ------------------------------------------------------------------

    def on_complete(self, callback):
        """Register a callback invoked when a timer reaches zero."""
        self._on_complete_callbacks.append(callback)

    def on_milestone(self, callback):
        """Register a callback invoked at time milestones (2 min, 1 min, 30 sec)."""
        self._on_milestone_callbacks.append(callback)

    def on_repeat_beep(self, callback):
        """Register a callback invoked every 5 seconds while a timer is COMPLETED."""
        self._on_repeat_beep_callbacks.append(callback)

    def add(self, name: str, duration: int) -> bool:
        """
        Add a new timer. Returns True on success, False if all slots are full.
        name      : display name (will be title-cased)
        duration  : seconds
        """
        for i, slot in enumerate(self._slots):
            if slot is None:
                self._slots[i] = TimerState(
                    slot=i,
                    name=name.strip().title(),
                    name_key=name.strip().lower(),
                    total=duration,
                    remaining=float(duration),
                    status=TimerStatus.RUNNING,
                )
                self._last_tick = time.monotonic()
                return True
        return False

    def cancel(self, name_key: str) -> bool:
        """Cancel a timer by name. Returns True if found."""
        idx = self._find(name_key)
        if idx is None:
            return False
        self._slots[idx] = None
        return True

    def pause(self, name_key: str) -> bool:
        """Pause a RUNNING timer. Returns True if found and was running."""
        idx = self._find(name_key)
        if idx is None:
            return False
        t = self._slots[idx]
        if t.status == TimerStatus.RUNNING:
            t.status = TimerStatus.PAUSED
            return True
        return False

    def resume(self, name_key: str) -> bool:
        """Resume a PAUSED timer. Returns True if found and was paused."""
        idx = self._find(name_key)
        if idx is None:
            return False
        t = self._slots[idx]
        if t.status == TimerStatus.PAUSED:
            t.status = TimerStatus.RUNNING
            # Reset last_tick so we don't apply the paused gap to remaining
            self._last_tick = time.monotonic()
            return True
        return False

    def tick(self):
        """
        Advance all RUNNING timers by the elapsed wall-clock time.
        Call this every ~100ms from the Tkinter after() loop.
        """
        now = time.monotonic()
        delta = now - self._last_tick
        self._last_tick = now

        for t in self._slots:
            if t is None:
                continue
            if t.status == TimerStatus.RUNNING:
                t.remaining -= delta
                if t.remaining <= 0:
                    t.remaining = 0.0
                    t.status = TimerStatus.COMPLETED
                    t.completed_at = now
                    t.last_beep_at = now
                    for cb in self._on_complete_callbacks:
                        cb(t.name)
                else:
                    # Check milestones
                    for milestone in ANNOUNCE_MILESTONES:
                        if milestone not in t.announced and t.remaining <= milestone:
                            t.announced.add(milestone)
                            for cb in self._on_milestone_callbacks:
                                cb(t.name, milestone)
            elif t.status == TimerStatus.COMPLETED:
                t.overtime = now - t.completed_at
                if now - t.last_beep_at >= 5.0:
                    t.last_beep_at = now
                    for cb in self._on_repeat_beep_callbacks:
                        cb(t.name)

    def snapshot(self) -> list:
        """Return a shallow copy of the 4 slots (None or TimerState)."""
        return list(self._slots)

    def active_count(self) -> int:
        """Number of non-empty slots."""
        return sum(1 for s in self._slots if s is not None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find(self, name_key: str) -> Optional[int]:
        """Return slot index for the given name_key, or None."""
        name_key = name_key.strip().lower()
        for i, t in enumerate(self._slots):
            if t is not None and t.name_key == name_key:
                return i
        return None
