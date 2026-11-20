"""Floating vertical recording dock shown instead of the main window."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from .icons import icon

if TYPE_CHECKING:
    from .app import MacroStudioApp
    from ..models import Macro

LEVEL_COLORS = {
    "system": "#8fa9ff",
    "info": "#c8d2e4",
    "success": "#4ade80",
    "warn": "#fbbf24",
    "error": "#ff6b6b",
    "action": "#ffb86c",
    "move": "#60a5fa",
    "debug": "#9aa7bd",
}


class RecordingDock(ctk.CTkToplevel):
    """Small always-on-top vertical panel used while recording."""

    def __init__(self, app: "MacroStudioApp", macro: "Macro"):
        super().__init__(app)
        self.app = app
        self.macro = macro
        # A decorated top-level window gets its own taskbar button.
        self.title("REC DOCK · Macro Studio")
        try:
            from .welcome import _icon_path
            self.iconbitmap(str(_icon_path()))
        except Exception:
            pass
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.configure(fg_color=("#111827", "#0b0e16"))

        width, height = 268, 566
        x = max(0, self.winfo_screenwidth() - width - 28)
        y = max(20, (self.winfo_screenheight() - height) // 2 - 40)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._drag_x = 0
        self._drag_y = 0
        self._line_count = 0

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=("#1a2130", "#141a28"))
        card.pack(fill="both", expand=True, padx=6, pady=6)
        card.bind("<Button-1>", self._start_move)
        card.bind("<B1-Motion>", self._do_move)

        # -- header ---------------------------------------------------------
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 4))
        header.bind("<Button-1>", self._start_move)
        header.bind("<B1-Motion>", self._do_move)
        self.dot = ctk.CTkLabel(header, text="●", font=ctk.CTkFont(size=17), text_color="#6b7689")
        self.dot.pack(side="left")
        ctk.CTkLabel(header, text="REC DOCK", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=4)
        ctk.CTkButton(
            header, text="", image=icon("close", 14), width=24, height=24,
            fg_color="transparent", hover_color=("gray70", "#3a3f52"),
            command=self.app.close_dock,
        ).pack(side="right")

        # -- status ---------------------------------------------------------
        status_card = ctk.CTkFrame(card, corner_radius=10, fg_color=("#222b3d", "#1b2233"))
        status_card.pack(fill="x", padx=12, pady=6)
        self.status_label = ctk.CTkLabel(
            status_card, text="●  LISTO PARA GRABAR",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#8fa9ff",
        )
        self.status_label.pack(pady=(8, 2))
        self.macro_label = ctk.CTkLabel(
            status_card, text=macro.name, font=ctk.CTkFont(size=11),
            text_color=("gray60", "gray65"), wraplength=210,
        )
        self.macro_label.pack(pady=(0, 8))

        # -- capture options -------------------------------------------------
        ctk.CTkLabel(
            card, text="ANTES DE GRABAR", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray65"), anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        options = ctk.CTkFrame(card, corner_radius=10, fg_color=("#222b3d", "#1b2233"))
        options.pack(fill="x", padx=12, pady=2)

        setting_rows = [
            ("Ratón", "record_moves"),
            ("Clics", "record_clicks"),
            ("Teclado", "record_keys"),
            ("Rueda", "record_scroll"),
        ]
        for index, (label, key) in enumerate(setting_rows):
            var = ctk.BooleanVar(value=getattr(self.app.settings, key))
            ctk.CTkSwitch(
                options, text=label, variable=var, font=ctk.CTkFont(size=11),
                switch_width=32, switch_height=17,
                command=lambda k=key, v=var: self._set_setting(k, v.get()),
            ).grid(row=index, column=0, sticky="w", padx=10, pady=(7 if index == 0 else 1, 1))

        right = ctk.CTkFrame(options, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=4, sticky="ns", padx=(4, 10))
        ctk.CTkLabel(right, text="Cuenta atrás", font=ctk.CTkFont(size=10)).pack(anchor="w")
        countdown_var = ctk.StringVar(value=str(self.app.settings.countdown_seconds))
        ctk.CTkOptionMenu(
            right, values=["0", "1", "2", "3", "5", "10"], variable=countdown_var,
            width=88, height=26, font=ctk.CTkFont(size=11),
            command=lambda v: self._set_setting("countdown_seconds", int(v)),
        ).pack(anchor="w", pady=(2, 8))
        ctk.CTkLabel(right, text="Muestreo", font=ctk.CTkFont(size=10)).pack(anchor="w")
        self.sample_var = ctk.IntVar(value=self.app.settings.move_sample_ms)
        ctk.CTkSlider(
            right, from_=5, to=120, number_of_steps=23, variable=self.sample_var,
            width=92, command=self._on_sample,
        ).pack(anchor="w", pady=2)
        self.sample_label = ctk.CTkLabel(
            right, text=f"{self.app.settings.move_sample_ms} ms", font=ctk.CTkFont(size=10)
        )
        self.sample_label.pack(anchor="w")

        # -- live console ----------------------------------------------------
        ctk.CTkLabel(
            card, text="CONSOLA EN VIVO", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray65"), anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))
        self.console = ctk.CTkTextbox(
            card, height=104, corner_radius=8, activate_scrollbars=True,
            font=ctk.CTkFont(family="Consolas", size=10), wrap="word",
        )
        self.console.pack(fill="x", padx=12)
        self.console.configure(state="disabled")
        for level, color in LEVEL_COLORS.items():
            self.console.tag_config(level, foreground=color)

        # -- actions ---------------------------------------------------------
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(10, 12))
        self.start_btn = ctk.CTkButton(
            actions, text="INICIAR GRABACIÓN", image=icon("record", 16), height=40,
            font=ctk.CTkFont(size=11, weight="bold"), fg_color="#d94848", hover_color="#b93636",
            command=self.app.start_recording_from_dock,
        )
        self.start_btn.pack(fill="x", pady=2)
        self.stop_btn = ctk.CTkButton(
            actions, text="DETENER", image=icon("stop", 16), height=36,
            font=ctk.CTkFont(size=11, weight="bold"), fg_color="#3d4351", hover_color="#2d323e",
            state="disabled", command=self.app.stop_recording,
        )
        self.stop_btn.pack(fill="x", pady=2)

        self.append_log("Panel listo. Ajusta las opciones y pulsa INICIAR.", "system")
        self.update_idletasks()
        self._force_taskbar_button()

    def _force_taskbar_button(self) -> None:
        """Make sure Windows treats the dock as a normal taskbar window."""
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            style = (style & ~0x00000080) | 0x00040000  # no TOOLWINDOW, yes APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    # -- public API ---------------------------------------------------------

    def set_status(self, text: str, color: str) -> None:
        if self.winfo_exists():
            self.status_label.configure(text=text, text_color=color)
            self.dot.configure(text_color=color)

    def on_recording_started(self) -> None:
        self.set_status("●  GRABANDO…", "#ff6b6b")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.append_log("Grabación iniciada.", "success")

    def on_recording_stopped(self) -> None:
        self.set_status("●  GRABACIÓN FINALIZADA", "#4ade80")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def update_counter(self, count: int) -> None:
        """Show the number of captured events while recording."""
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.update_counter(count))
            except RuntimeError:
                pass
            return
        if self.winfo_exists():
            self.macro_label.configure(text=f"{self.macro.name}  ·  {count} eventos")

    def append_log(self, message: str, level: str = "info", source: str = "REC") -> None:
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.append_log(message, level, source))
            except RuntimeError:
                pass  # dock/window is being destroyed
            return
        if not self.winfo_exists():
            return
        color = LEVEL_COLORS.get(level, LEVEL_COLORS["info"])
        self._line_count += 1
        if self._line_count > 200:
            self.console.configure(state="normal")
            self.console.delete("1.0", "100.0")
            self.console.configure(state="disabled")
        self.console.configure(state="normal")
        self.console.insert("end", f"[{source}] {message}\n", level)
        self.console.tag_config(level, foreground=color)
        self.console.configure(state="disabled")
        self.console.see("end")

    # -- internals ----------------------------------------------------------

    def _set_setting(self, key: str, value) -> None:
        setattr(self.app.settings, key, value)
        self.app.recorder.settings = self.app.settings

    def _on_sample(self, value) -> None:
        ms = int(value)
        self.app.settings.move_sample_ms = ms
        self.app.recorder.settings = self.app.settings
        self.sample_label.configure(text=f"{ms} ms")

    def _start_move(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event) -> None:
        x = self.winfo_pointerx() - self._drag_x
        y = self.winfo_pointery() - self._drag_y
        self.geometry(f"+{x}+{y}")
