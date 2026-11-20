"""Persistence: settings, macro library and ReMouse .rms import/export."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from .models import EventType, Macro, MacroEvent, Settings

APP_NAME = "MacroStudio"


def app_dir() -> Path:
    """Directory where the app stores its data.

    If a ``portable.txt`` marker lives beside the executable, all data is
    kept in a ``data`` folder there, making the install fully portable.
    Otherwise the normal per-user Windows location is used.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path(__file__).resolve().parents[1]
    if (exe_dir / "portable.txt").is_file():
        path = exe_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.cwd() / ".macro_studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = None  # resolved lazily so tests can override app_dir
LIBRARY_FILE = None


def _settings_path() -> Path:
    return app_dir() / "settings.json"


def _library_path() -> Path:
    return app_dir() / "library.json"


def load_settings() -> Settings:
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
        return Settings.from_dict(data)
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    _settings_path().write_text(
        json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_library() -> List[Macro]:
    try:
        data = json.loads(_library_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("macros", [])
        return [Macro.from_dict(item) for item in data]
    except (OSError, ValueError, TypeError):
        return []


def save_library(macros: List[Macro]) -> None:
    _library_path().write_text(
        json.dumps([m.to_dict() for m in macros], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_macro_json(macro: Macro, path: Path) -> None:
    Path(path).write_text(
        json.dumps(macro.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_macro_json(path: Path) -> Macro:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Macro.from_dict(data)


# ---------------------------------------------------------------------------
# ReMouse .rms format
# ---------------------------------------------------------------------------

_COMMAND_RE = re.compile(r"\{([^{}]*)\}")
_MOUSE_RE = re.compile(
    r"^(LMouse|RMouse|MMouse)\s+(down|up)\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$",
    re.IGNORECASE,
)
_MOVEMENTS_RE = re.compile(r"^\s*Movements\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL)
_DELAY_RE = re.compile(r"^\s*Delay\s+([0-9.]+)\s*$", re.IGNORECASE)
_WHEEL_RE = re.compile(r"^\s*Wheel\s+(-?\d+)\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$", re.IGNORECASE)
_KEY_RE = re.compile(r"^\s*(KeyDown|KeyUp|Key|Press)\s+(.+?)\s*$", re.IGNORECASE)
_TEXT_RE = re.compile(r"^\s*Text\s+(.*)$", re.IGNORECASE | re.DOTALL)

_BUTTONS = {"lmouse": "left", "rmouse": "right", "mmouse": "middle"}


def _read_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def import_rms(path: Path) -> Macro:
    """Parse a ReMouse .rms script into a Macro Studio macro."""
    text = _read_text(path)
    events: List[MacroEvent] = []
    cursor_ms = 0

    for match in _COMMAND_RE.finditer(text):
        command = match.group(1).strip()
        if not command:
            continue

        low = command.lower()

        delay_match = _DELAY_RE.match(command)
        if delay_match:
            try:
                cursor_ms += int(round(float(delay_match.group(1)) * 1000))
            except ValueError:
                pass
            continue

        movement_match = _MOVEMENTS_RE.match(command)
        if movement_match:
            body = movement_match.group(1).strip()
            if body.startswith("(") and body.endswith(")"):
                body = body[1:-1]
            for part in body.split("|"):
                part = part.strip()
                if not part:
                    continue
                bits = part.split(":")
                if len(bits) < 3:
                    continue
                try:
                    delta = int(round(float(bits[0]) * 1000))
                    x, y = int(float(bits[1])), int(float(bits[2]))
                except ValueError:
                    continue
                cursor_ms += delta
                events.append(MacroEvent(type=EventType.MOVE, time_ms=cursor_ms, x=x, y=y))
            continue

        mouse_match = _MOUSE_RE.match(command)
        if mouse_match:
            button = _BUTTONS.get(mouse_match.group(1).lower(), "left")
            pressed = mouse_match.group(2).lower() == "down"
            x, y = int(mouse_match.group(3)), int(mouse_match.group(4))
            events.append(
                MacroEvent(
                    type=EventType.MOUSE_DOWN if pressed else EventType.MOUSE_UP,
                    time_ms=cursor_ms,
                    x=x,
                    y=y,
                    button=button,
                )
            )
            continue

        wheel_match = _WHEEL_RE.match(command)
        if wheel_match:
            events.append(
                MacroEvent(
                    type=EventType.SCROLL,
                    time_ms=cursor_ms,
                    amount=int(wheel_match.group(1)),
                    x=int(wheel_match.group(2)),
                    y=int(wheel_match.group(3)),
                )
            )
            continue

        key_match = _KEY_RE.match(command)
        if key_match:
            action = key_match.group(1).lower()
            key = key_match.group(2).strip()
            if action in ("keydown",):
                events.append(MacroEvent(type=EventType.KEY_DOWN, time_ms=cursor_ms, key=key))
            elif action in ("keyup",):
                events.append(MacroEvent(type=EventType.KEY_UP, time_ms=cursor_ms, key=key))
            else:
                events.append(MacroEvent(type=EventType.KEY_DOWN, time_ms=cursor_ms, key=key))
                events.append(MacroEvent(type=EventType.KEY_UP, time_ms=cursor_ms + 50, key=key))
                cursor_ms += 50
            continue

        text_match = _TEXT_RE.match(command)
        if text_match:
            events.append(MacroEvent(type=EventType.TEXT, time_ms=cursor_ms, text=text_match.group(1)))
            continue

        if low.startswith("#") or low.startswith("comment"):
            events.append(
                MacroEvent(type=EventType.COMMENT, time_ms=cursor_ms, comment=command.lstrip("# ").strip())
            )
            continue

        # Unknown ReMouse command: keep it as a comment so nothing is lost.
        events.append(MacroEvent(type=EventType.COMMENT, time_ms=cursor_ms, comment=command))

    macro = Macro(name=path.stem, events=events, description=f"Importada de ReMouse: {path.name}")
    macro.sort()
    return macro


def export_rms(macro: Macro) -> str:
    """Serialize a Macro Studio macro into ReMouse-compatible .rms text."""
    events = sorted((e for e in macro.events), key=lambda e: e.time_ms)
    lines: List[str] = []
    cursor_ms = 0
    index = 0

    def emit_delay(target_ms: int) -> None:
        nonlocal cursor_ms
        if target_ms > cursor_ms:
            lines.append("{Delay %.2f}" % ((target_ms - cursor_ms) / 1000.0))
            cursor_ms = target_ms

    while index < len(events):
        event = events[index]

        if not event.enabled:
            index += 1
            continue

        # Group consecutive, enabled MOVE events into a single Movements block.
        if event.type is EventType.MOVE:
            group: List[Tuple[int, int, int]] = []
            previous_time = cursor_ms
            while index < len(events):
                current = events[index]
                if current.type is not EventType.MOVE or not current.enabled:
                    break
                delta = max(0, current.time_ms - previous_time)
                group.append((delta, current.x, current.y))
                previous_time = current.time_ms
                index += 1
            segments = "|".join(f"{d / 1000.0:.2f}:{x}:{y}" for d, x, y in group)
            lines.append("{Movements (" + segments + ")}")
            cursor_ms = previous_time
            continue

        emit_delay(event.time_ms)
        if event.type is EventType.DELAY:
            cursor_ms = event.time_ms
            index += 1
            continue

        command = event.rms_command()
        if command:
            lines.append("{" + command + "}")
        index += 1

    return "\n".join(lines) + "\n"
