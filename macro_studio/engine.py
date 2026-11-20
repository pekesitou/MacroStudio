"""Input capture, playback engine and global hotkeys."""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable, Dict, List, Optional, Sequence, Set

from pynput import keyboard, mouse

from .models import EventType, Macro, MacroEvent, Settings

# ---------------------------------------------------------------------------
# Key name helpers
# ---------------------------------------------------------------------------

_SPECIAL_KEYS: Dict[str, object] = {}
for _name in (
    "ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r", "alt", "alt_l",
    "alt_r", "alt_gr", "enter", "space", "tab", "backspace", "delete", "esc",
    "up", "down", "left", "right", "home", "end", "page_up", "page_down",
    "caps_lock", "num_lock", "scroll_lock", "insert", "pause", "print_screen",
    "menu", "cmd", "cmd_l", "cmd_r", "apps", "media_play_pause", "media_next",
    "media_previous", "volume_up", "volume_down", "volume_mute",
):
    if hasattr(keyboard.Key, _name):
        _SPECIAL_KEYS[_name.upper()] = getattr(keyboard.Key, _name)
for _i in range(1, 21):
    _SPECIAL_KEYS[f"F{_i}"] = getattr(keyboard.Key, f"f{_i}")

# Friendly aliases -> canonical pynput name
_ALIASES = {
    "CONTROL": "CTRL", "CTL": "CTRL", "SHIFT": "SHIFT", "ALT": "ALT",
    "ESC": "ESC", "ESCAPE": "ESC", "ENTER": "ENTER", "RETURN": "ENTER",
    "SPACE": "SPACE", "SPACEBAR": "SPACE", "DEL": "DELETE", "DELETE": "DELETE",
    "PAGEUP": "PAGE_UP", "PGUP": "PAGE_UP", "PAGEDOWN": "PAGE_DOWN",
    "PGDN": "PAGE_DOWN", "CAPSLOCK": "CAPS_LOCK", "NUMLOCK": "NUM_LOCK",
    "PRINTSCREEN": "PRINT_SCREEN", "PRTSC": "PRINT_SCREEN", "WIN": "CMD",
    "LWIN": "CMD", "RWIN": "CMD_R", "COMMAND": "CMD", "APPSKEY": "APPS",
    "LEFT": "LEFT", "RIGHT": "RIGHT", "UP": "UP", "DOWN": "DOWN",
    "BACKSPACE": "BACKSPACE", "TAB": "TAB", "HOME": "HOME", "END": "END",
    "INSERT": "INSERT", "PAUSE": "PAUSE", "MENU": "MENU",
}

_MOD_PRIORITY = ["CTRL", "SHIFT", "ALT", "CMD", "CMD_R", "WIN"]


def key_to_string(key) -> str:
    """Convert a pynput key object into a stable uppercase name."""
    char = getattr(key, "char", None)
    if char is not None:
        return char.upper() if len(char) == 1 else char
    name = getattr(key, "name", None)
    if name:
        upper = name.upper()
        return _ALIASES.get(upper, upper)
    return str(key).strip("'").upper()


def string_to_key(name: str):
    """Convert a stored key name back into a pynput key object."""
    clean = str(name).strip()
    upper = _ALIASES.get(clean.upper(), clean.upper())
    if upper in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[upper]
    if len(clean) == 1:
        return keyboard.KeyCode.from_char(clean.lower())
    try:
        return keyboard.KeyCode.from_char(clean)
    except Exception:
        return keyboard.KeyCode.from_char(clean[:1] or "a")


def normalize_combo(combo: str) -> str:
    """Normalize 'ctrl+f2' into a canonical '+' separated combo string."""
    parts: Set[str] = set()
    for token in str(combo).replace(" ", "").split("+"):
        if not token:
            continue
        upper = _ALIASES.get(token.upper(), token.upper())
        parts.add(upper)

    def priority(token: str):
        if token in _MOD_PRIORITY:
            return (0, _MOD_PRIORITY.index(token))
        return (1, token)

    return "+".join(sorted(parts, key=priority))


def describe_combo(combo: str) -> str:
    """Human friendly combo text for the UI."""
    return " + ".join(normalize_combo(combo).split("+"))


# ---------------------------------------------------------------------------
# Unicode text typing (works for Spanish/emoji/etc., unlike key-by-key typing)
# ---------------------------------------------------------------------------

_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR (pointer-sized)
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def type_unicode(text: str) -> None:
    """Type arbitrary unicode text using SendInput KEYEVENTF_UNICODE."""
    user32 = ctypes.windll.user32
    for char in text:
        code = ord(char)
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            inp = _INPUT()
            inp.type = _INPUT_KEYBOARD
            inp.u.ki.wVk = 0
            inp.u.ki.wScan = code & 0xFFFF
            inp.u.ki.dwFlags = flags
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            # Supplementary plane characters need a surrogate pair; sending the
            # low word twice is harmless for normal BMP text.
        if code > 0xFFFF:
            pass


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class Recorder:
    """Captures global mouse/keyboard events into a macro."""

    def __init__(
        self,
        settings: Settings,
        log: Callable[[str, str, str], None],
        on_event: Callable[[MacroEvent], None],
    ):
        self.settings = settings
        self.log = log
        self.on_event = on_event
        self.recording = False
        self.events: List[MacroEvent] = []
        self._start = 0.0
        self._last_move = 0.0
        self._last_pos = (-1, -1)
        self._ignore_until = 0.0

    def start(self) -> None:
        self.events = []
        self._start = time.perf_counter()
        self._last_move = self._start
        self._last_pos = (-1, -1)
        self._ignore_until = self._start + 0.20
        self.recording = True
        self.log("Capturando eventos de teclado y ratón…", "info", "REC")

    def stop(self) -> List[MacroEvent]:
        if not self.recording:
            return self.events
        self.recording = False
        duration = self._elapsed()
        self.log(
            f"Grabación finalizada · {len(self.events)} eventos · {duration / 1000:.2f} s",
            "success",
            "REC",
        )
        return self.events

    def _elapsed(self) -> int:
        return max(0, int((time.perf_counter() - self._start) * 1000))

    def _append(self, event: MacroEvent) -> None:
        self.events.append(event)
        self.on_event(event)

    def on_move(self, x: int, y: int) -> None:
        if not self.recording or not self.settings.record_moves:
            return
        now = time.perf_counter()
        if (now - self._last_move) * 1000 < self.settings.move_sample_ms:
            return
        if now < self._ignore_until or (int(x), int(y)) == self._last_pos:
            return
        self._last_move = now
        self._last_pos = (int(x), int(y))
        self._append(MacroEvent(EventType.MOVE, self._elapsed(), x=int(x), y=int(y)))

    def on_click(self, x: int, y: int, button, pressed: bool) -> None:
        if not self.recording or not self.settings.record_clicks:
            return
        if time.perf_counter() < self._ignore_until:
            return
        button_name = getattr(button, "name", str(button))
        self._append(
            MacroEvent(
                EventType.MOUSE_DOWN if pressed else EventType.MOUSE_UP,
                self._elapsed(),
                x=int(x),
                y=int(y),
                button=button_name,
            )
        )

    def on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self.recording or not self.settings.record_scroll:
            return
        if time.perf_counter() < self._ignore_until:
            return
        self._append(
            MacroEvent(
                EventType.SCROLL,
                self._elapsed(),
                x=int(x),
                y=int(y),
                amount=int(dy),
            )
        )

    def on_key(self, key, pressed: bool) -> None:
        if not self.recording or not self.settings.record_keys:
            return
        if time.perf_counter() < self._ignore_until:
            return
        name = key_to_string(key)
        if not name:
            return
        self._append(
            MacroEvent(
                EventType.KEY_DOWN if pressed else EventType.KEY_UP,
                self._elapsed(),
                key=name,
            )
        )


# ---------------------------------------------------------------------------
# Hotkey detector (single keyboard listener shared with the recorder)
# ---------------------------------------------------------------------------

class HotkeyDetector:
    """Detects configurable key combinations from a key event stream."""

    def __init__(self, hotkeys: Dict[str, str], on_trigger: Callable[[str], None]):
        self.on_trigger = on_trigger
        self.bindings: Dict[str, str] = {}
        self.pressed: Set[str] = set()
        self.set_bindings(hotkeys)

    def set_bindings(self, hotkeys: Dict[str, str]) -> None:
        self.bindings = {normalize_combo(combo): name for name, combo in hotkeys.items()}

    def feed(self, key, pressed: bool) -> Optional[str]:
        """Feed one key event; return the triggered action name, if any."""
        name = key_to_string(key)
        if not name:
            return None
        if pressed:
            if name in self.pressed:
                return None  # OS key-repeat
            self.pressed.add(name)
            combo = "+".join(sorted(self.pressed, key=lambda k: (
                _MOD_PRIORITY.index(k) if k in _MOD_PRIORITY else len(_MOD_PRIORITY)
            )))
            action = self.bindings.get(combo)
            if action:
                self.on_trigger(action)
                return action
            return None
        self.pressed.discard(name)
        return None


# ---------------------------------------------------------------------------
# Input hub: owns the pynput listeners and dispatches events
# ---------------------------------------------------------------------------

class InputHub:
    """Single pair of global listeners that feed the hotkeys and recorder."""

    def __init__(
        self,
        on_key: Callable[[object, bool], Optional[str]],
        recorder: Recorder,
        hotkey_detector: Optional[HotkeyDetector] = None,
    ):
        self.on_key_callback = on_key
        self.recorder = recorder
        self.hotkey_detector = hotkey_detector
        self._suppressed: Set[str] = set()
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None

    def _on_press(self, key) -> None:
        action = self.on_key_callback(key, True)
        if action and self.hotkey_detector:
            # A hotkey key must never end up recorded inside the macro.
            self._suppressed.update(self.hotkey_detector.pressed)
        name = key_to_string(key)
        if name not in self._suppressed:
            self.recorder.on_key(key, True)

    def _on_release(self, key) -> None:
        self.on_key_callback(key, False)
        name = key_to_string(key)
        if name not in self._suppressed:
            self.recorder.on_key(key, False)
        self._suppressed.discard(name)

    def _on_move(self, x, y) -> None:
        self.recorder.on_move(int(x), int(y))

    def _on_click(self, x, y, button, pressed) -> None:
        self.recorder.on_click(int(x), int(y), button, pressed)

    def _on_scroll(self, x, y, dx, dy) -> None:
        self.recorder.on_scroll(int(x), int(y), int(dx), int(dy))

    def start(self) -> None:
        if self._keyboard_listener:
            return
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self) -> None:
        for listener in (self._keyboard_listener, self._mouse_listener):
            if listener:
                listener.stop()
        self._keyboard_listener = None
        self._mouse_listener = None


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player:
    """Plays macros back with precise timing, loops, speed and verbose logs."""

    def __init__(
        self,
        log: Callable[[str, str, str], None],
        on_progress: Callable[[int, int, int], None],
        on_state: Callable[[str], None],
    ):
        self.log = log
        self.on_progress = on_progress
        self.on_state = on_state
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.playing = False
        self.paused = False
        self.step_mode = False
        self.events: List[MacroEvent] = []
        self.index = 0
        self.cycle = 0
        self.total_cycles = 1
        self.speed = 1.0
        self._mouse = mouse.Controller()
        self._keyboard = keyboard.Controller()

    # -- public API ---------------------------------------------------------

    def play(
        self,
        macro: Macro,
        speed: float = 1.0,
        repeat: int = 1,
        start_index: int = 0,
    ) -> bool:
        if self.playing:
            return False
        events = sorted((e for e in macro.events if e.enabled), key=lambda e: e.time_ms)
        if start_index > 0 and start_index < len(macro.events):
            base_time = macro.events[start_index].time_ms
            tail = [e for e in events if e.time_ms >= base_time]
            if tail:
                offset = tail[0].time_ms
                # Copy events so the original macro is never modified, and
                # rebase their times so playback starts immediately.
                events = [
                    MacroEvent.from_dict({**e.to_dict(), "time_ms": e.time_ms - offset})
                    for e in tail
                ]
        if not events:
            self.log("No hay eventos habilitados para reproducir.", "warn", "PLAY")
            return False

        self.events = events
        self.speed = max(0.05, float(speed))
        self.total_cycles = repeat if repeat > 0 else 0  # 0 = infinite
        self.index = 0
        self.cycle = 0
        self.step_mode = False
        self.paused = False
        self._stop_event.clear()
        self._pause_event.clear()
        self.playing = True
        self.on_state("playing")

        self.log(
            f"Reproduciendo «{macro.name}» · {len(events)} eventos · "
            f"velocidad ×{self.speed:.2f} · "
            f"{'infinito' if self.total_cycles == 0 else str(self.total_cycles) + ' ciclo(s)'}",
            "system",
            "PLAY",
        )
        self._thread = threading.Thread(target=self._run, daemon=True, name="MacroPlayer")
        self._thread.start()
        return True

    def start_step(self, macro: Macro, start_index: int = 0) -> bool:
        if self.playing:
            return False
        events = sorted((e for e in macro.events if e.enabled), key=lambda e: e.time_ms)
        if not events:
            self.log("No hay eventos para depurar.", "warn", "STEP")
            return False
        self.events = events
        self.index = start_index
        self.cycle = 1
        self.total_cycles = 1
        self.step_mode = True
        self.playing = True
        self.paused = True
        self._stop_event.clear()
        self.on_state("stepping")
        self.log(
            f"Modo depuración activado · {len(events)} eventos · usa «Paso» para avanzar",
            "system",
            "STEP",
        )
        return True

    def step(self) -> None:
        if not self.playing or not self.step_mode:
            return
        if self.index >= len(self.events):
            self.log("Fin de la secuencia en modo depuración.", "success", "STEP")
            self.stop()
            return
        event = self.events[self.index]
        self.log(f"[Paso {self.index + 1}/{len(self.events)}] {event.description()}", "debug", "STEP")
        self._execute(event)
        self.index += 1
        self.on_progress(self.index, len(self.events), 1)

    def pause(self) -> None:
        if self.playing and not self.step_mode:
            self.paused = True
            self._pause_event.set()
            self.on_state("paused")
            self.log("Reproducción en pausa.", "warn", "PLAY")

    def resume(self) -> None:
        if self.playing and not self.step_mode:
            self.paused = False
            self._pause_event.clear()
            self.on_state("playing")
            self.log("Reproducción reanudada.", "info", "PLAY")

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def stop(self, reason: str = "manual") -> None:
        if not self.playing:
            return
        self._stop_event.set()
        self._pause_event.clear()
        self.playing = False
        self.paused = False
        self.step_mode = False
        self.on_state("idle")
        messages = {
            "manual": "Reproducción detenida por el usuario.",
            "hotkey": "¡PARADA DE EMERGENCIA! Reproducción abortada.",
            "done": "Reproducción completada correctamente.",
        }
        self.log(messages.get(reason, "Reproducción finalizada."),
                 "success" if reason == "done" else "warn", "PLAY")

    # -- internals ----------------------------------------------------------

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set() and (self.total_cycles == 0 or self.cycle < self.total_cycles):
                self.cycle += 1
                cycle_label = f"{self.cycle}/{self.total_cycles}" if self.total_cycles else str(self.cycle)
                self.log(f"── Ciclo {cycle_label} ──", "system", "PLAY")
                cycle_start = time.perf_counter()

                for i, event in enumerate(self.events):
                    if self._stop_event.is_set():
                        return
                    target = cycle_start + (event.time_ms / 1000.0) / self.speed
                    if not self._wait_until(target):
                        return

                    delta = event.time_ms - (self.events[i - 1].time_ms if i else 0)
                    self.log(
                        f"[{i + 1:03d}/{len(self.events):03d}] +{delta:5d} ms · {event.description()}",
                        _level_for(event.type),
                        "PLAY",
                    )
                    self._execute(event)
                    self.index = i + 1
                    self.on_progress(self.index, len(self.events), self.cycle)

            if not self._stop_event.is_set():
                self.stop("done")
        except Exception as exc:  # never crash the app because of playback
            self.log(f"Error durante la reproducción: {exc}", "error", "PLAY")
            self.stop("manual")

    def _wait_until(self, target: float) -> bool:
        """Wait until target time; handle pause without drifting the schedule."""
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                pause_started = time.perf_counter()
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.02)
                target += time.perf_counter() - pause_started
                continue
            remaining = target - time.perf_counter()
            if remaining <= 0:
                return True
            time.sleep(min(remaining, 0.02))
        return False

    def _execute(self, event: MacroEvent) -> None:
        t = event.type
        if t is EventType.MOVE:
            self._mouse.position = (event.x, event.y)
        elif t is EventType.MOUSE_DOWN:
            try:
                self._mouse.position = (event.x, event.y)
            except Exception:
                pass
            self._mouse.press(_mouse_button(event.button))
        elif t is EventType.MOUSE_UP:
            self._mouse.release(_mouse_button(event.button))
        elif t is EventType.SCROLL:
            steps = max(1, min(abs(event.amount), 20))
            direction = 1 if event.amount > 0 else -1
            for _ in range(steps):
                self._mouse.scroll(0, direction)
        elif t is EventType.KEY_DOWN:
            self._keyboard.press(string_to_key(event.key))
        elif t is EventType.KEY_UP:
            self._keyboard.release(string_to_key(event.key))
        elif t is EventType.TEXT:
            try:
                type_unicode(event.text)
            except Exception:
                self._keyboard.type(event.text)


def _mouse_button(name: str):
    return {
        "left": mouse.Button.left,
        "right": mouse.Button.right,
        "middle": mouse.Button.middle,
        "x1": mouse.Button.x1,
        "x2": mouse.Button.x2,
    }.get(name, mouse.Button.left)


def _level_for(event_type: EventType) -> str:
    return {
        EventType.MOUSE_DOWN: "action",
        EventType.MOUSE_UP: "action",
        EventType.KEY_DOWN: "action",
        EventType.KEY_UP: "action",
        EventType.MOVE: "move",
        EventType.SCROLL: "action",
        EventType.TEXT: "action",
        EventType.COMMENT: "debug",
        EventType.DELAY: "debug",
    }.get(event_type, "info")


def beep(frequency: int = 880, duration: int = 90) -> None:
    """Best-effort feedback beep; silently ignored if audio is unavailable."""
    try:
        import winsound

        winsound.Beep(frequency, duration)
    except Exception:
        pass
