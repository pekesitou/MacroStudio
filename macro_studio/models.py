"""Data models for Macro Studio."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    """Kinds of recorded actions."""

    DELAY = "delay"
    MOVE = "move"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    SCROLL = "scroll"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    TEXT = "text"
    COMMENT = "comment"

    @property
    def label(self) -> str:
        return {
            "delay": "Retardo",
            "move": "Mover ratón",
            "mouse_down": "Ratón abajo",
            "mouse_up": "Ratón arriba",
            "scroll": "Rueda",
            "key_down": "Tecla abajo",
            "key_up": "Tecla arriba",
            "text": "Escribir texto",
            "comment": "Comentario",
        }[self.value]

    @property
    def glyph(self) -> str:
        return {
            "delay": "⏱",
            "move": "➤",
            "mouse_down": "▼",
            "mouse_up": "▲",
            "scroll": "↕",
            "key_down": "⬇",
            "key_up": "⬆",
            "text": "⌨",
            "comment": "#",
        }[self.value]

    @property
    def color(self) -> str:
        return {
            "delay": "#8b93a7",
            "move": "#5b9dff",
            "mouse_down": "#ff9f43",
            "mouse_up": "#ffbe76",
            "scroll": "#a29bfe",
            "key_down": "#26de81",
            "key_up": "#4cd137",
            "text": "#00d2d3",
            "comment": "#7f8c9a",
        }[self.value]


BUTTON_NAMES = {
    "left": "Izquierdo",
    "right": "Derecho",
    "middle": "Medio",
    "x1": "Extra 1",
    "x2": "Extra 2",
}


@dataclass
class MacroEvent:
    """A single timed action inside a macro.

    ``time_ms`` is the offset from the beginning of the macro, which avoids
    accumulated drift while playing (delays are computed as differences).
    """

    type: EventType
    time_ms: int = 0
    x: int = 0
    y: int = 0
    button: str = "left"
    key: str = ""
    amount: int = 0
    text: str = ""
    comment: str = ""
    enabled: bool = True

    @property
    def glyph(self) -> str:
        return self.type.glyph

    @property
    def type_label(self) -> str:
        return self.type.label

    @property
    def color(self) -> str:
        return self.type.color

    def description(self) -> str:
        """Short human-readable description of this event."""
        t = self.type
        if t is EventType.DELAY:
            return f"Esperar {self.time_ms} ms"
        if t is EventType.MOVE:
            return f"Mover a ({self.x}, {self.y})"
        if t is EventType.MOUSE_DOWN:
            return f"Pulsar ratón {BUTTON_NAMES.get(self.button, self.button)} en ({self.x}, {self.y})"
        if t is EventType.MOUSE_UP:
            return f"Soltar ratón {BUTTON_NAMES.get(self.button, self.button)} en ({self.x}, {self.y})"
        if t is EventType.SCROLL:
            direction = "arriba" if self.amount > 0 else "abajo"
            return f"Rueda {direction} ({abs(self.amount)}) en ({self.x}, {self.y})"
        if t is EventType.KEY_DOWN:
            return f"Pulsar tecla {self.key}"
        if t is EventType.KEY_UP:
            return f"Soltar tecla {self.key}"
        if t is EventType.TEXT:
            preview = self.text.replace("\n", "\\n")
            if len(preview) > 28:
                preview = preview[:25] + "..."
            return f"Escribir «{preview}»"
        if t is EventType.COMMENT:
            return f"# {self.comment}"
        return t.value

    def rms_command(self) -> Optional[str]:
        """Return the ReMouse .rms command for this event, if representable."""
        t = self.type
        if t is EventType.MOUSE_DOWN:
            return f"{_rms_button(self.button)} down ({self.x},{self.y})"
        if t is EventType.MOUSE_UP:
            return f"{_rms_button(self.button)} up ({self.x},{self.y})"
        if t is EventType.KEY_DOWN:
            return f"KeyDown {self.key}"
        if t is EventType.KEY_UP:
            return f"KeyUp {self.key}"
        if t is EventType.TEXT:
            return f"Text {self.text}"
        if t is EventType.COMMENT:
            return f"# {self.comment}"
        if t is EventType.SCROLL:
            return f"Wheel {self.amount} ({self.x},{self.y})"
        return None  # DELAY and MOVE are handled specially on export

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "time_ms": self.time_ms,
            "x": self.x,
            "y": self.y,
            "button": self.button,
            "key": self.key,
            "amount": self.amount,
            "text": self.text,
            "comment": self.comment,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "MacroEvent":
        return MacroEvent(
            type=EventType(data.get("type", "comment")),
            time_ms=int(data.get("time_ms", 0)),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            button=str(data.get("button", "left")),
            key=str(data.get("key", "")),
            amount=int(data.get("amount", 0)),
            text=str(data.get("text", "")),
            comment=str(data.get("comment", "")),
            enabled=bool(data.get("enabled", True)),
        )


def _rms_button(button: str) -> str:
    return {"left": "LMouse", "right": "RMouse", "middle": "MMouse"}.get(button, "LMouse")


@dataclass
class Macro:
    """A named sequence of macro events."""

    name: str = "Nueva macro"
    events: List[MacroEvent] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    repeat: int = 1  # 0 means infinite
    speed: float = 1.0
    description: str = ""

    @property
    def duration_ms(self) -> int:
        return max((e.time_ms for e in self.events), default=0)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def enabled_count(self) -> int:
        return sum(1 for e in self.events if e.enabled)

    def stats(self) -> Dict[str, int]:
        result = {t.value: 0 for t in EventType}
        for e in self.events:
            result[e.type.value] += 1
        result["clicks"] = result["mouse_down"] + result["mouse_up"]
        result["keys"] = result["key_down"] + result["key_up"]
        return result

    def add_event(self, event: MacroEvent) -> None:
        self.events.append(event)
        self.modified_at = time.time()

    def sort(self) -> None:
        self.events.sort(key=lambda e: e.time_ms)
        self.modified_at = time.time()

    def clear(self) -> None:
        self.events.clear()
        self.modified_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "macro-studio",
            "version": 1,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "repeat": self.repeat,
            "speed": self.speed,
            "events": [e.to_dict() for e in self.events],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Macro":
        return Macro(
            name=str(data.get("name", "Macro importada")),
            events=[MacroEvent.from_dict(e) for e in data.get("events", [])],
            id=str(data.get("id", uuid.uuid4().hex[:8])),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time())),
            repeat=int(data.get("repeat", 1)),
            speed=float(data.get("speed", 1.0)),
            description=str(data.get("description", "")),
        )


DEFAULT_HOTKEYS = {
    "record": "f10",
    "play": "ctrl+f2",
    "stop": "esc",
    "step": "ctrl+f3",
}


@dataclass
class Settings:
    """Application preferences, persisted as JSON next to the macros."""

    theme: str = "dark"  # dark | light | system
    accent: str = "#6c8cff"
    hotkeys: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))
    record_moves: bool = True
    record_clicks: bool = True
    record_keys: bool = True
    record_scroll: bool = True
    move_sample_ms: int = 25
    countdown_seconds: int = 3
    playback_speed: float = 1.0
    repeat: int = 1
    repeat_until_stopped: bool = False
    auto_scroll_log: bool = True
    log_filter: str = "Todo"
    play_sound: bool = True
    show_mouse_pointer: bool = True
    minimize_on_play: bool = False
    minimize_on_record: bool = True
    confirm_delete: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme": self.theme,
            "accent": self.accent,
            "hotkeys": dict(self.hotkeys),
            "record_moves": self.record_moves,
            "record_clicks": self.record_clicks,
            "record_keys": self.record_keys,
            "record_scroll": self.record_scroll,
            "move_sample_ms": self.move_sample_ms,
            "countdown_seconds": self.countdown_seconds,
            "playback_speed": self.playback_speed,
            "repeat": self.repeat,
            "repeat_until_stopped": self.repeat_until_stopped,
            "auto_scroll_log": self.auto_scroll_log,
            "log_filter": self.log_filter,
            "play_sound": self.play_sound,
            "show_mouse_pointer": self.show_mouse_pointer,
            "minimize_on_play": self.minimize_on_play,
            "minimize_on_record": self.minimize_on_record,
            "confirm_delete": self.confirm_delete,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Settings":
        s = Settings()
        for key, value in data.items():
            if key == "hotkeys" and isinstance(value, dict):
                s.hotkeys = {**DEFAULT_HOTKEYS, **value}
            elif hasattr(s, key):
                setattr(s, key, value)
        return s
