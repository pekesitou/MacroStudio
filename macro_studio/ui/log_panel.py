"""Live verbose console panel with filtering, search and coloured levels."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

import customtkinter as ctk

from .icons import icon

LEVEL_STYLE_DARK = {
    "system": ("#8fa9ff", "SYSTEM"),
    "info": ("#c8d2e4", "INFO"),
    "success": ("#4ade80", "OK"),
    "warn": ("#fbbf24", "WARN"),
    "error": ("#ff6b6b", "ERROR"),
    "action": ("#ffb86c", "ACTION"),
    "move": ("#60a5fa", "MOVE"),
    "debug": ("#9aa7bd", "DEBUG"),
}
LEVEL_STYLE_LIGHT = {
    "system": ("#3b5bdb", "SYSTEM"),
    "info": ("#2d3748", "INFO"),
    "success": ("#0f9d58", "OK"),
    "warn": ("#b7791f", "WARN"),
    "error": ("#c53030", "ERROR"),
    "action": ("#c05621", "ACTION"),
    "move": ("#2563eb", "MOVE"),
    "debug": ("#718096", "DEBUG"),
}

FILTERS = ("Todo", "REC", "PLAY", "STEP", "SYS")
MAX_LINES = 2500


class LogPanel(ctk.CTkFrame):
    """Verbose event console with filters and live autoscroll."""

    def __init__(self, master, on_filter_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_filter_change = on_filter_change
        self.entries: Deque[Dict] = deque(maxlen=MAX_LINES)
        self._auto_scroll = ctk.BooleanVar(value=True)
        self._filter = ctk.StringVar(value="Todo")
        self._search = ctk.StringVar(value="")
        self._search.trace_add("write", lambda *_: self._render())
        self._theme = "dark"

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))

        title = ctk.CTkLabel(
            header,
            text="  CONSOLA VERBOSE",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        title.pack(side="top", fill="x")

        row = ctk.CTkFrame(header, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))

        self.filter_menu = ctk.CTkOptionMenu(
            row,
            values=list(FILTERS),
            variable=self._filter,
            command=self._on_filter,
            width=82,
            height=28,
            font=ctk.CTkFont(size=11),
            dropdown_font=ctk.CTkFont(size=11),
        )
        self.filter_menu.pack(side="left")

        search_entry = ctk.CTkEntry(
            row,
            placeholder_text="Buscar…",
            textvariable=self._search,
            height=28,
            width=110,
            font=ctk.CTkFont(size=11),
        )
        search_entry.pack(side="left", padx=(6, 0))

        self.auto_switch = ctk.CTkSwitch(
            row,
            text="Auto",
            variable=self._auto_scroll,
            command=self._render,
            font=ctk.CTkFont(size=11),
            switch_width=30,
            switch_height=16,
            width=62,
        )
        self.auto_switch.pack(side="left", padx=(6, 0))

        copy_btn = ctk.CTkButton(
            row, text="", image=icon("copy", 15), width=28, height=28,
            fg_color="transparent", hover_color=("gray80", "gray25"),
            command=self.copy_all,
        )
        copy_btn.pack(side="right", padx=(4, 0))
        clear_btn = ctk.CTkButton(
            row, text="", image=icon("trash", 15), width=28, height=28,
            fg_color="transparent", hover_color=("gray80", "gray25"),
            command=self.clear,
        )
        clear_btn.pack(side="right")

        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            activate_scrollbars=True,
            border_width=1,
            corner_radius=8,
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.textbox.configure(state="disabled")
        self.set_theme("dark")
        self.log("Consola lista. Los eventos aparecerán aquí en tiempo real.", "system", "SYS")

    # -- public API ---------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        style = LEVEL_STYLE_LIGHT if theme == "light" else LEVEL_STYLE_DARK
        for level, (color, _) in style.items():
            self.textbox.tag_config(level, foreground=color)
        self.textbox.tag_config("time", foreground=("#718096" if theme == "light" else "#6b7689"))
        self.textbox.tag_config("source", foreground=("#805ad5" if theme == "light" else "#b794f4"))

    def set_filter(self, value: str) -> None:
        self._filter.set(value)
        self._render()

    def log(self, message: str, level: str = "info", source: str = "SYS") -> None:
        """Thread-safe: append one verbose line."""
        entry = {"time": time.strftime("%H:%M:%S"), "message": str(message),
                 "level": level, "source": source}
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self._add(entry))
            except RuntimeError:
                pass  # app is shutting down
        else:
            self._add(entry)

    def clear(self) -> None:
        self.entries.clear()
        self._render()

    def copy_all(self) -> None:
        try:
            text = "\n".join(
                f"[{e['time']}] [{e['source']}] {e['message']}" for e in self.entries
            )
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass

    # -- internals ----------------------------------------------------------

    def _on_filter(self, value: str) -> None:
        self._render()
        if self.on_filter_change:
            self.on_filter_change(value)

    def _add(self, entry: Dict) -> None:
        self.entries.append(entry)
        # Fast path: append a single line instead of redrawing thousands of
        # lines on every recorded mouse movement.
        if not self._search.get().strip() and self._matches_filter(entry, self._filter.get()):
            self.textbox.configure(state="normal")
            self._write_line(entry)
            self.textbox.configure(state="disabled")
            if self._auto_scroll.get():
                self.textbox.see("end")
        else:
            self._render()

    @staticmethod
    def _matches_filter(entry: Dict, filter_value: str) -> bool:
        if filter_value == "Todo" or entry["source"] == filter_value:
            return True
        return filter_value == "SYS" and entry["source"] in ("SYS", "APP")

    def _visible(self) -> list:
        filter_value = self._filter.get()
        query = self._search.get().strip().lower()
        result = []
        for entry in self.entries:
            if not self._matches_filter(entry, filter_value):
                continue
            haystack = f"{entry['source']} {entry['message']} {entry['level']}".lower()
            if query and query not in haystack:
                continue
            result.append(entry)
        return result

    def _write_line(self, entry: Dict) -> None:
        style = LEVEL_STYLE_LIGHT if self._theme == "light" else LEVEL_STYLE_DARK
        _, short = style.get(entry["level"], style["info"])
        self.textbox.insert("end", f"[{entry['time']}] ", "time")
        self.textbox.insert("end", f"[{entry['source']:4}] ", "source")
        self.textbox.insert("end", f"[{short:6}] ", entry["level"])
        self.textbox.insert("end", entry["message"] + "\n", entry["level"])

    def _render(self) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        for entry in self._visible():
            self._write_line(entry)
        self.textbox.configure(state="disabled")
        if self._auto_scroll.get():
            self.textbox.see("end")
