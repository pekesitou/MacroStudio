"""Modal dialogs: event editor, settings, hotkey capture, about & countdown."""
from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

import customtkinter as ctk
from pynput import keyboard

from ..engine import describe_combo, key_to_string, normalize_combo
from ..models import EventType, MacroEvent, Settings
from .icons import icon

MODIFIER_NAMES = {"CTRL", "SHIFT", "ALT", "CMD", "CMD_R", "WIN"}


class _Modal(ctk.CTkToplevel):
    def __init__(self, master, title: str, width: int = 450, height: int = 400):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.after(100, self._center)

    def _center(self) -> None:
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - self.winfo_width()) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")


# ---------------------------------------------------------------------------
# Event editor
# ---------------------------------------------------------------------------

class EventDialog(_Modal):
    def __init__(self, master, event: MacroEvent, on_save: Callable[[MacroEvent], None]):
        super().__init__(master, "Editar evento", 440, 460)
        self.event = event
        self.on_save = on_save
        self.result: Optional[MacroEvent] = None

        self.type_var = ctk.StringVar(value=event.type.value)
        self.enabled_var = ctk.BooleanVar(value=event.enabled)

        pad = dict(padx=18, pady=6)

        ctk.CTkLabel(self, text="Tipo de evento", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", **pad)
        type_menu = ctk.CTkOptionMenu(
            self,
            values=[t.value for t in EventType],
            variable=self.type_var,
            command=lambda _: self._update_fields(),
            width=400,
        )
        type_menu.pack(**pad)

        ctk.CTkLabel(self, text="Tiempo (milisegundos desde el inicio)", font=ctk.CTkFont(size=11)).pack(anchor="w", **pad)
        self.time_entry = ctk.CTkEntry(self, width=400)
        self.time_entry.insert(0, str(event.time_ms))
        self.time_entry.pack(**pad)

        self.fields = ctk.CTkFrame(self, fg_color="transparent")
        self.fields.pack(fill="both", expand=True, padx=18, pady=4)

        self.entries: Dict[str, ctk.CTkEntry] = {}
        self._build_fields()

        ctk.CTkSwitch(
            self, text="Evento habilitado", variable=self.enabled_var,
            font=ctk.CTkFont(size=11), switch_width=34, switch_height=18,
        ).pack(anchor="w", padx=18, pady=6)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkButton(buttons, text="Cancelar", width=110, fg_color="transparent",
                      command=self.destroy).pack(side="right")
        ctk.CTkButton(buttons, text="Guardar", width=110, command=self._save).pack(side="right", padx=8)
        self._update_fields()

    def _build_fields(self) -> None:
        for child in self.fields.winfo_children():
            child.destroy()
        self.entries.clear()
        definitions = {
            "move": [("x", "Coordenada X", str(self.event.x)), ("y", "Coordenada Y", str(self.event.y))],
            "mouse_down": [
                ("x", "Coordenada X", str(self.event.x)), ("y", "Coordenada Y", str(self.event.y)),
                ("button", "Botón (left/right/middle)", self.event.button),
            ],
            "mouse_up": [
                ("x", "Coordenada X", str(self.event.x)), ("y", "Coordenada Y", str(self.event.y)),
                ("button", "Botón (left/right/middle)", self.event.button),
            ],
            "scroll": [
                ("amount", "Cantidad (+ arriba / - abajo)", str(self.event.amount)),
                ("x", "Coordenada X", str(self.event.x)), ("y", "Coordenada Y", str(self.event.y)),
            ],
            "key_down": [("key", "Tecla (p. ej. CTRL, A, F2)", self.event.key)],
            "key_up": [("key", "Tecla (p. ej. CTRL, A, F2)", self.event.key)],
            "text": [("text", "Texto a escribir", self.event.text)],
            "comment": [("comment", "Comentario", self.event.comment)],
            "delay": [],
        }
        rows = definitions.get(self.type_var.get(), [])
        for row, (key, label, value) in enumerate(rows):
            ctk.CTkLabel(self.fields, text=label, font=ctk.CTkFont(size=11)).grid(
                row=row * 2, column=0, sticky="w", pady=(4, 0)
            )
            entry = ctk.CTkEntry(self.fields, width=360)
            entry.insert(0, value)
            entry.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(0, 4))
            self.entries[key] = entry

    def _update_fields(self) -> None:
        self._build_fields()

    def _save(self) -> None:
        try:
            time_ms = int(float(self.time_entry.get()))
        except ValueError:
            time_ms = self.event.time_ms
        data = {
            "type": self.type_var.get(),
            "time_ms": max(0, time_ms),
            "enabled": self.enabled_var.get(),
        }
        for key, entry in self.entries.items():
            value = entry.get()
            if key in ("x", "y", "amount"):
                try:
                    value = int(value)
                except ValueError:
                    value = 0
            data[key] = value
        self.result = MacroEvent.from_dict(data)
        self.on_save(self.result)
        self.destroy()


# ---------------------------------------------------------------------------
# Hotkey capture
# ---------------------------------------------------------------------------

class HotkeyDialog(_Modal):
    def __init__(self, master, action_label: str, current: str, on_save: Callable[[str], None],
                 on_capture_start: Optional[Callable] = None,
                 on_capture_end: Optional[Callable] = None):
        super().__init__(master, f"Atajo: {action_label}", 360, 190)
        self.on_save = on_save
        self.on_capture_start = on_capture_start
        self.on_capture_end = on_capture_end
        self.combo = normalize_combo(current)
        self.pressed = set()
        self.listener: Optional[keyboard.Listener] = None

        ctk.CTkLabel(
            self, text=f"Pulsa la combinación para:\n{action_label}",
            font=ctk.CTkFont(size=13, weight="bold"), justify="center",
        ).pack(pady=(22, 10))

        self.display = ctk.CTkLabel(
            self, text=describe_combo(self.combo), font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#6c8cff", "#8fa9ff"),
        )
        self.display.pack()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=(16, 16))
        ctk.CTkButton(buttons, text="Cancelar", width=95, command=self._cancel).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Aplicar", width=95, command=self._apply).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(150, self._start_listener)

    def _start_listener(self) -> None:
        if self.on_capture_start:
            self.on_capture_start()
        self.pressed.clear()
        self.listener = keyboard.Listener(on_press=self._press, on_release=self._release)
        self.listener.start()

    def _press(self, key) -> None:
        name = key_to_string(key)
        if name:
            self.pressed.add(name)
            self.after(0, lambda: self.display.configure(text=describe_combo("+".join(sorted(self.pressed)))))

    def _release(self, key) -> None:
        name = key_to_string(key)
        if name in self.pressed and name not in MODIFIER_NAMES:
            self.after(0, self._apply)

    def _stop_listener(self) -> None:
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.on_capture_end:
            self.on_capture_end()

    def _apply(self) -> None:
        if not self.pressed:
            return
        self.combo = "+".join(sorted(self.pressed, key=lambda k: (
            0 if k in MODIFIER_NAMES else 1, k
        )))
        self._stop_listener()
        self.on_save(self.combo)
        self.destroy()

    def _cancel(self) -> None:
        self._stop_listener()
        self.destroy()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsDialog(_Modal):
    def __init__(self, master, settings: Settings, on_save: Callable[[Settings], None],
                 hotkey_actions: Dict[str, str], on_hotkey: Callable,
                 capture_start: Callable, capture_end: Callable):
        super().__init__(master, "Preferencias", 520, 520)
        self.settings = settings
        self.on_save = on_save
        self.hotkey_actions = hotkey_actions
        self.on_hotkey = on_hotkey
        self.capture_start = capture_start
        self.capture_end = capture_end

        self.vars: Dict[str, object] = {}
        tabs = ctk.CTkTabview(self, width=490, height=430)
        tabs.pack(fill="both", expand=True, padx=14, pady=(14, 6))
        for name in ("General", "Grabación", "Reproducción", "Atajos"):
            tabs.add(name)

        self._general(tabs.tab("General"))
        self._recording(tabs.tab("Grabación"))
        self._playback(tabs.tab("Reproducción"))
        self._hotkeys(tabs.tab("Atajos"))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=14, pady=(6, 14))
        ctk.CTkButton(buttons, text="Cancelar", width=110, fg_color="transparent",
                      command=self.destroy).pack(side="right")
        ctk.CTkButton(buttons, text="Guardar", width=110, command=self._save).pack(side="right", padx=8)

    def _switch(self, parent, text: str, key: str, value: bool, row: int) -> None:
        var = ctk.BooleanVar(value=value)
        self.vars[key] = var
        ctk.CTkSwitch(parent, text=text, variable=var, font=ctk.CTkFont(size=12),
                      switch_width=36, switch_height=18).grid(row=row, column=0, sticky="w", pady=6, padx=8)

    def _general(self, parent) -> None:
        ctk.CTkLabel(parent, text="Tema de la interfaz", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(16, 4))
        theme_var = ctk.StringVar(value=self.settings.theme)
        self.vars["theme"] = theme_var
        ctk.CTkOptionMenu(parent, values=["dark", "light", "system"], variable=theme_var, width=160).grid(
            row=1, column=0, sticky="w", padx=8)
        self._switch(parent, "Sonidos de aviso", "play_sound", self.settings.play_sound, 3)
        self._switch(parent, "Auto-scroll en la consola", "auto_scroll_log", self.settings.auto_scroll_log, 4)
        self._switch(parent, "Pedir confirmación al borrar", "confirm_delete", self.settings.confirm_delete, 5)

    def _recording(self, parent) -> None:
        self._switch(parent, "Grabar movimientos del ratón", "record_moves", self.settings.record_moves, 0)
        self._switch(parent, "Grabar clics", "record_clicks", self.settings.record_clicks, 1)
        self._switch(parent, "Grabar pulsaciones de teclado", "record_keys", self.settings.record_keys, 2)
        self._switch(parent, "Grabar rueda del ratón", "record_scroll", self.settings.record_scroll, 3)
        ctk.CTkLabel(
            parent, text="La ventana principal se oculta y se abre el panel vertical al grabar.",
            font=ctk.CTkFont(size=10), text_color=("gray50", "gray65"),
            wraplength=420, justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        ctk.CTkLabel(parent, text="Muestreo de movimiento (ms)", font=ctk.CTkFont(size=12)).grid(
            row=5, column=0, sticky="w", padx=8, pady=(10, 0))
        sample_var = ctk.IntVar(value=self.settings.move_sample_ms)
        self.vars["move_sample_ms"] = sample_var
        ctk.CTkSlider(parent, from_=5, to=120, number_of_steps=23, variable=sample_var, width=300).grid(
            row=6, column=0, sticky="w", padx=8)
        self.sample_label = ctk.CTkLabel(parent, text=f"{self.settings.move_sample_ms} ms")
        self.sample_label.grid(row=6, column=1, padx=8)
        sample_var.trace_add("write", lambda *_: self.sample_label.configure(text=f"{sample_var.get()} ms"))

        ctk.CTkLabel(parent, text="Cuenta atrás antes de grabar (s)", font=ctk.CTkFont(size=12)).grid(
            row=7, column=0, sticky="w", padx=8, pady=(10, 0))
        countdown_var = ctk.IntVar(value=self.settings.countdown_seconds)
        self.vars["countdown_seconds"] = countdown_var
        ctk.CTkOptionMenu(parent, values=["0", "1", "2", "3", "5", "10"],
                          variable=ctk.StringVar(value=str(self.settings.countdown_seconds)),
                          command=lambda v: countdown_var.set(int(v)), width=90).grid(
            row=8, column=0, sticky="w", padx=8)

    def _playback(self, parent) -> None:
        ctk.CTkLabel(parent, text="Velocidad de reproducción", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(16, 4))
        speed_var = ctk.DoubleVar(value=self.settings.playback_speed)
        self.vars["playback_speed"] = speed_var
        ctk.CTkSlider(parent, from_=0.1, to=4.0, number_of_steps=39, variable=speed_var, width=300).grid(
            row=1, column=0, sticky="w", padx=8)
        self.speed_label = ctk.CTkLabel(parent, text=f"×{self.settings.playback_speed:.2f}")
        self.speed_label.grid(row=1, column=1, padx=8)
        speed_var.trace_add("write", lambda *_: self.speed_label.configure(text=f"×{speed_var.get():.2f}"))

        ctk.CTkLabel(parent, text="Repeticiones (0 = infinito)", font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w", padx=8, pady=(14, 4))
        repeat_var = ctk.IntVar(value=self.settings.repeat)
        self.vars["repeat"] = repeat_var
        ctk.CTkEntry(parent, textvariable=repeat_var, width=90).grid(row=3, column=0, sticky="w", padx=8)

        self._switch(parent, "repetir hasta detener", "repeat_until_stopped",
                     self.settings.repeat_until_stopped or self.settings.repeat == 0, 4)
        self._switch(parent, "Minimizar al reproducir", "minimize_on_play", self.settings.minimize_on_play, 5)
        self._switch(parent, "Mostrar cursor del ratón", "show_mouse_pointer", self.settings.show_mouse_pointer, 6)

    def _hotkeys(self, parent) -> None:
        ctk.CTkLabel(parent, text="Pulsa «Configurar» y luego la combinación deseada.",
                     font=ctk.CTkFont(size=11), text_color=("gray50", "gray65")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(14, 10))
        self.hotkey_labels = {}
        for row, (key, label) in enumerate(self.hotkey_actions.items(), start=1):
            ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=12)).grid(
                row=row, column=0, sticky="w", padx=8, pady=8)
            combo = describe_combo(self.settings.hotkeys.get(key, ""))
            lbl = ctk.CTkLabel(parent, text=combo, font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=("#6c8cff", "#8fa9ff"), width=130)
            lbl.grid(row=row, column=1, padx=6)
            self.hotkey_labels[key] = lbl
            ctk.CTkButton(
                parent, text="Configurar", width=95,
                command=lambda k=key, l=label: self._capture(k, l),
            ).grid(row=row, column=2, padx=8)

    def _capture(self, key: str, label: str) -> None:
        def save(combo: str) -> None:
            self.settings.hotkeys[key] = combo
            self.hotkey_labels[key].configure(text=describe_combo(combo))
        HotkeyDialog(self, label, self.settings.hotkeys[key], save,
                     self.capture_start, self.capture_end)

    def _save(self) -> None:
        s = self.settings
        for key, var in self.vars.items():
            if hasattr(s, key):
                setattr(s, key, var.get())
        if s.repeat_until_stopped:
            s.repeat = 0
        self.on_save(s)
        self.destroy()


# ---------------------------------------------------------------------------
# About & countdown
# ---------------------------------------------------------------------------

class AboutDialog(_Modal):
    def __init__(self, master, version: str):
        super().__init__(master, "Acerca de Macro Studio", 400, 280)
        ctk.CTkLabel(self, text="MACRO STUDIO", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30, 4))
        ctk.CTkLabel(self, text=f"Versión {version}", font=ctk.CTkFont(size=12)).pack()
        ctk.CTkLabel(
            self,
            text="Grabador y reproductor de macros con consola verbose,\n"
                 "timeline editable, atajos globales e importación .rms.",
            font=ctk.CTkFont(size=12), justify="center",
        ).pack(pady=18)
        ctk.CTkButton(self, text="Cerrar", width=110, command=self.destroy).pack(pady=10)


class CountdownOverlay(ctk.CTkToplevel):
    """Borderless always-on-top countdown shown before recording."""

    def __init__(self, master, seconds: int, on_done: Callable[[], None]):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=("#101522", "#0d111c"))
        self.on_done = on_done
        self.remaining = seconds

        self.label = ctk.CTkLabel(
            self, text=str(seconds) if seconds else "GRABANDO",
            font=ctk.CTkFont(size=96, weight="bold"),
            text_color=("#6c8cff", "#8fa9ff"),
        )
        self.label.pack(padx=60, pady=40)
        self.subtitle = ctk.CTkLabel(
            self, text="Prepárate para grabar…", font=ctk.CTkFont(size=13)
        )
        self.subtitle.pack(pady=(0, 25))

        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")
        self._tick()

    def _tick(self) -> None:
        if self.remaining > 0:
            self.label.configure(text=str(self.remaining))
            self.remaining -= 1
            self.after(1000, self._tick)
        else:
            self.label.configure(text="● REC")
            self.label.configure(text_color=("#ff6b6b", "#ff6b6b"))
            self.subtitle.configure(text="Grabando ahora")
            self.after(350, self._finish)

    def _finish(self) -> None:
        self.destroy()
        self.on_done()
