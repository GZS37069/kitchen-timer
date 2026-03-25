"""
System tray icon management via pystray.
show() and hide() are safe to call from any thread.
"""

import threading
import queue as queue_module
from PIL import Image, ImageDraw, ImageFont


def _make_icon_image() -> Image.Image:
    """Draw a simple clock-face icon (64x64 RGBA)."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled circle
    draw.ellipse([2, 2, size - 2, size - 2], fill="#0f3460", outline="#4444ff", width=3)
    # Clock hands suggestion — simple "KT" text
    draw.text((18, 16), "KT", fill="#e0e0ff")
    return img


class TrayManager:
    def __init__(self, command_queue: queue_module.Queue, shutdown_event: threading.Event):
        self._cmd_q = command_queue
        self._shutdown = shutdown_event
        self._icon = None
        self._root = None
        self._thread = None

    def start(self, root):
        """Start the pystray icon in a daemon thread."""
        self._root = root
        self._thread = threading.Thread(target=self._run, daemon=True, name="TrayThread")
        self._thread.start()

    def show(self):
        """Restore the main window (safe to call from any thread)."""
        if self._root:
            self._root.after(0, self._do_show)

    def hide(self):
        """Minimize the main window to tray (safe to call from any thread)."""
        if self._root:
            self._root.after(0, self._do_hide)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _run(self):
        try:
            import pystray
        except ImportError:
            print("[tray] pystray not installed — tray icon disabled")
            return

        def on_show(icon, item):
            self._cmd_q.put({"type": "SHOW"})

        def on_quit(icon, item):
            if not self._shutdown.is_set():
                self._shutdown.set()
                self._cmd_q.put({"type": "QUIT"})
                icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Show", on_show),
            pystray.MenuItem("Quit", on_quit),
        )
        self._icon = pystray.Icon(
            "KitchenTimer",
            _make_icon_image(),
            "Kitchen Timer",
            menu,
        )
        self._icon.run()

    def _do_show(self):
        if self._root:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()

    def _do_hide(self):
        if self._root:
            self._root.withdraw()
