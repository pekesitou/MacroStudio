"""Main application window."""
from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .. import __version__
from ..engine import (
    HotkeyDetector, InputHub, Player, Recorder, beep, describe_combo,
)
from ..models import EventType, Macro, MacroEvent, Settings
from ..storage import (
    export_rms, import_rms, load_library, load_macro_json, load_settings,
    save_library, save_macro_json, save_settings,
)
from .dialogs import AboutDialog, CountdownOverlay, EventDialog, SettingsDialog
from .event_list import EventList
from .icons import icon
from .log_panel import LogPanel
from .recording_dock import RecordingDock

STATE_STYLES = {
    "idle": ("●  EN ESPERA", ("gray55", "#3a4254"), ("#d7dce5", "#d7dce5")),
    "recording": ("●  GRABANDO", ("#c92a2a", "#ff4d4d"), ("#ffffff", "#1a0000")),
    "playing": ("●  REPRODUCIENDO", ("#0f9d58", "#26de81"), ("#ffffff", "#062b18")),
    "paused": ("●  EN PAUSA", ("#d97706", "#fbbf24"), ("#ffffff", "#3a2600")),
    "stepping": ("●  DEPURANDO", ("#7048e8", "#a29bfe"), ("#ffffff", "#1b1040")),
}


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource both from source and from a PyInstaller build."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / relative
    return Path(__file__).resolve().parents[2] / relative


class MacroStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings: Settings = load_settings()
        self.macros: List[Macro] = load_library()
        self.current: Optional[Macro] = self.macros[0] if self.macros else None
        self.app_state = "idle"
        self._capturing_hotkey = False
        self._save_job: Optional[str] = None
        self._refresh_job: Optional[str] = None
        self._move_counter = 0
        # Recording UI updates are batched on the main thread. The pynput
        # listener only appends to this buffer, so it never touches Tk widgets.
        self._record_buffer = []
        self._record_lock = threading.Lock()
        self._record_poll_job: Optional[str] = None
        self.dock: Optional[RecordingDock] = None
        self._pending_record_macro: Optional[Macro] = None

        ctk.set_appearance_mode(self.settings.theme)
        ctk.set_default_color_theme("blue")

        self.title("Macro Studio — Grabador & Reproductor de Macros")
        self._set_window_icon()
        self.geometry("1320x820")
        self.minsize(1080, 700)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._compact_mode: Optional[bool] = None
        self._button_specs = {
            self.record_btn: ("GRABAR", 135),
            self.play_btn: ("REPRODUCIR", 155),
            self.stop_btn: ("DETENER", 115),
            self.pause_btn: ("PAUSA", 120),
            self.step_btn: ("PASO", 120),
            self.import_btn: ("Importar…", 150),
            self.export_btn: ("Exportar…", 150),
            self.from_here_btn: ("Desde selección", 130),
        }
        for button, (label, _) in self._button_specs.items():
            button.bind(
                "<Enter>",
                lambda _e, text=label: self._hint_button(text) if self._compact_mode else None,
            )
            button.bind("<Leave>", lambda _e: self.on_select_event(None))
        self._apply_compact_mode()
        self._build_engine()
        self._apply_hotkeys()
        self._refresh_all()
        self._log("Macro Studio listo. Usa F10 para grabar y CTRL+F2 para reproducir.", "system")
        self._log(
            f"Biblioteca cargada: {len(self.macros)} macro(s) · "
            f"Atajos: {describe_combo(self.settings.hotkeys['record'])} / "
            f"{describe_combo(self.settings.hotkeys['play'])}",
            "info",
        )

    def _set_window_icon(self) -> None:
        """Use the app icon for the window and the Windows taskbar button."""
        icon_file = resource_path("assets/macro_studio.ico")
        if not icon_file.is_file():
            return
        try:
            self.iconbitmap(str(icon_file))
            self.wm_iconbitmap(str(icon_file))
        except Exception:
            pass  # icon is cosmetic; never block startup because of it

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=("gray92", "#151925"))
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(self.topbar, text="◎", font=ctk.CTkFont(size=30, weight="bold"),
                            text_color=("#6c8cff", "#8fa9ff"))
        logo.grid(row=0, column=0, padx=(18, 6), pady=10)
        title_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w", pady=8)
        ctk.CTkLabel(title_frame, text="MACRO STUDIO", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Graba · Reproduce · Depura",
                     font=ctk.CTkFont(size=10), text_color=("gray50", "gray65")).pack(anchor="w")

        self.status_pill = ctk.CTkLabel(
            self.topbar, text="", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=20, height=32, padx=18,
        )
        self.status_pill.grid(row=0, column=2, padx=10)

        top_buttons = ctk.CTkFrame(self.topbar, fg_color="transparent")
        top_buttons.grid(row=0, column=3, padx=(6, 16))
        ctk.CTkButton(top_buttons, text="", image=icon("save", 17), width=34, height=34,
                      fg_color="transparent", hover_color=("gray80", "gray25"),
                      command=self.save_library).pack(side="left", padx=3)
        ctk.CTkButton(top_buttons, text="", image=icon("settings", 17), width=34, height=34,
                      fg_color="transparent", hover_color=("gray80", "gray25"),
                      command=self.open_settings).pack(side="left", padx=3)
        self.theme_btn = ctk.CTkButton(
            top_buttons, text="",
            image=icon("sun" if self.settings.theme == "dark" else "moon", 17),
            width=34, height=34, fg_color="transparent", hover_color=("gray80", "gray25"),
            command=self.toggle_theme,
        )
        self.theme_btn.pack(side="left", padx=3)
        ctk.CTkButton(top_buttons, text="", image=icon("info", 17), width=34, height=34,
                      fg_color="transparent", hover_color=("gray80", "gray25"),
                      command=lambda: AboutDialog(self, __version__)).pack(side="left", padx=3)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=0, minsize=232)
        main.grid_columnconfigure(1, weight=1, minsize=430)
        main.grid_columnconfigure(2, weight=0, minsize=330)
        main.grid_rowconfigure(0, weight=1)

        self._build_sidebar(main)
        self._build_center(main)

        self.log_panel = LogPanel(main, fg_color=("gray94", "#161a26"), corner_radius=12)
        self.log_panel.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self.log_panel.set_theme("light" if self.settings.theme == "light" else "dark")

        self.statusbar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=("gray92", "#151925"))
        self.statusbar.grid(row=2, column=0, sticky="ew")
        self.hint_label = ctk.CTkLabel(
            self.statusbar, text="", font=ctk.CTkFont(size=10), text_color=("gray50", "gray65"), anchor="w"
        )
        self.hint_label.pack(side="left", padx=14)
        self.progress = ctk.CTkProgressBar(self.statusbar, height=6, width=260)
        self.progress.pack(side="right", padx=14)
        self.progress.set(0)

    def _build_sidebar(self, parent) -> None:
        sidebar = ctk.CTkFrame(parent, fg_color=("gray94", "#161a26"), corner_radius=12)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(header, text="MIS MACROS", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="", image=icon("plus", 15), width=26, height=26,
                      fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
                      command=self.new_macro).pack(side="right")

        self.macro_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent", label_text="")
        self.macro_list.grid(row=1, column=0, sticky="nsew", padx=8)
        self.macro_list.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.import_btn = ctk.CTkButton(
            bottom, text="Importar…", image=icon("import", 15), width=150, height=30,
            font=ctk.CTkFont(size=11), fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"), command=self.import_macro)
        self.import_btn.pack(fill="x", pady=2)
        self.export_btn = ctk.CTkButton(
            bottom, text="Exportar…", image=icon("export", 15), width=150, height=30,
            font=ctk.CTkFont(size=11), fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"), command=self.export_macro)
        self.export_btn.pack(fill="x", pady=2)
        self._sidebar_buttons = [self.import_btn, self.export_btn]

    def _build_center(self, parent) -> None:
        center = ctk.CTkFrame(parent, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=8)
        center.grid_rowconfigure(4, weight=1)
        center.grid_columnconfigure(0, weight=1)

        name_card = ctk.CTkFrame(center, fg_color=("gray94", "#161a26"), corner_radius=12)
        name_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        name_card.grid_columnconfigure(0, weight=1)
        self.name_entry = ctk.CTkEntry(name_card, font=ctk.CTkFont(size=16, weight="bold"), height=38)
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        self.name_entry.bind("<KeyRelease>", self._on_name_change)
        self.desc_entry = ctk.CTkEntry(name_card, placeholder_text="Descripción (opcional)",
                                       font=ctk.CTkFont(size=11), height=28)
        self.desc_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.desc_entry.bind("<KeyRelease>", self._on_desc_change)

        # Single row of icons, always. The outer columns expand so the tight
        # group stays centred inside a roomy panel in every window state.
        control = ctk.CTkFrame(center, fg_color=("gray94", "#161a26"), corner_radius=14, height=62)
        control.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        control.grid_columnconfigure((0, 6), weight=1)
        control.grid_propagate(False)

        button_style = dict(text="", width=46, height=44)
        self.record_btn = ctk.CTkButton(
            control, image=icon("record", 18),
            fg_color="#d94848", hover_color="#b93636", command=self.toggle_record, **button_style,
        )
        self.record_btn.grid(row=0, column=1, padx=2, pady=9)
        self.play_btn = ctk.CTkButton(
            control, image=icon("play", 18),
            fg_color="#1f9d65", hover_color="#187f51", command=self.play, **button_style,
        )
        self.play_btn.grid(row=0, column=2, padx=2, pady=9)
        self.stop_btn = ctk.CTkButton(
            control, image=icon("stop", 18),
            fg_color="#3d4351", hover_color="#2d323e", command=self.stop_all, **button_style,
        )
        self.stop_btn.grid(row=0, column=3, padx=2, pady=9)
        self.pause_btn = ctk.CTkButton(
            control, image=icon("pause", 18),
            fg_color="#c9861b", hover_color="#a96f15", command=self.toggle_pause, **button_style,
        )
        self.pause_btn.grid(row=0, column=4, padx=2, pady=9)
        self.step_btn = ctk.CTkButton(
            control, image=icon("step", 18),
            fg_color="#7048e8", hover_color="#5a37c4", command=self.step, **button_style,
        )
        self.step_btn.grid(row=0, column=5, padx=2, pady=9)

        options = ctk.CTkFrame(center, fg_color=("gray94", "#161a26"), corner_radius=12)
        options.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        options.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(options, text="Repeticiones (0 = ∞)", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.repeat_var = ctk.IntVar(value=self.settings.repeat)
        self.repeat_entry = ctk.CTkEntry(options, textvariable=self.repeat_var, width=70, height=28)
        self.repeat_entry.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 6))

        self._repeat_before_until = self.settings.repeat if self.settings.repeat > 0 else 1
        self.repeat_until_var = ctk.BooleanVar(
            value=self.settings.repeat_until_stopped or self.settings.repeat == 0)
        self.repeat_until_switch = ctk.CTkSwitch(
            options, text="repetir hasta detener", variable=self.repeat_until_var,
            font=ctk.CTkFont(size=11), switch_width=34, switch_height=18,
            command=self._on_repeat_until_change,
        )
        self.repeat_until_switch.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))
        self._on_repeat_until_change()

        ctk.CTkLabel(options, text="Velocidad", font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="w", pady=(10, 0))
        speed_row = ctk.CTkFrame(options, fg_color="transparent")
        speed_row.grid(row=1, column=2, sticky="ew", pady=(2, 8))
        self.speed_var = ctk.DoubleVar(value=self.settings.playback_speed)
        ctk.CTkSlider(speed_row, from_=0.1, to=4.0, number_of_steps=39,
                      variable=self.speed_var, width=200).pack(side="left")
        self.speed_label = ctk.CTkLabel(speed_row, text=f"×{self.settings.playback_speed:.2f}",
                                        font=ctk.CTkFont(size=11, weight="bold"))
        self.speed_label.pack(side="left", padx=8)
        self.speed_var.trace_add("write", lambda *_: self.speed_label.configure(text=f"×{self.speed_var.get():.2f}"))

        self.from_here_btn = ctk.CTkButton(
            options, text="Desde selección", image=icon("play", 15), height=30, width=130,
            font=ctk.CTkFont(size=11), fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"), command=self.play_from_selection,
        )
        self.from_here_btn.grid(row=0, column=3, rowspan=3, padx=12, pady=8)

        stats = ctk.CTkFrame(center, fg_color="transparent")
        stats.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.stat_labels = {}
        for i, (key, label) in enumerate([
            ("events", "EVENTOS"), ("duration", "DURACIÓN"), ("clicks", "CLICS"), ("keys", "TECLAS"),
        ]):
            card = ctk.CTkFrame(stats, fg_color=("gray94", "#161a26"), corner_radius=10, height=52)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            stats.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=9),
                         text_color=("gray50", "gray65")).pack(pady=(6, 0))
            value = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=16, weight="bold"))
            value.pack(pady=(0, 6))
            self.stat_labels[key] = value

        self.event_list = EventList(
            center,
            on_edit=self.edit_event,
            on_delete=self.delete_events,
            on_toggle=self.toggle_events,
            on_reorder=self.reorder_event,
            on_select=self.on_select_event,
            on_add=self.add_event,
            fg_color=("gray94", "#161a26"), corner_radius=12,
        )
        self.event_list.grid(row=4, column=0, sticky="nsew")

    def _build_engine(self) -> None:
        self.recorder = Recorder(self.settings, self._log, self._on_record_event)
        self.player = Player(self._log, self._on_progress, self._set_state)
        self.hotkeys = HotkeyDetector(self.settings.hotkeys, self._on_hotkey)
        self.hub = InputHub(self.hotkeys.feed, self.recorder, self.hotkeys)
        self.hub.start()

    # ------------------------------------------------------------------
    # Engine callbacks
    # ------------------------------------------------------------------

    def _log(self, message: str, level: str = "info", source: str = "SYS") -> None:
        self.log_panel.log(message, level, source)
        if self.dock is not None:
            self.dock.append_log(message, level, source)

    def _on_record_event(self, event: MacroEvent) -> None:
        """Called from the input listener thread - keep it lock-free and cheap."""
        with self._record_lock:
            self._record_buffer.append(event)

    def _poll_record_buffer(self) -> None:
        """Drain captured events on the main thread in one batched update."""
        with self._record_lock:
            events, self._record_buffer = self._record_buffer, []
        if events:
            lines = []
            moves = 0
            for event in events:
                if event.type is EventType.MOVE:
                    moves += 1
                    self._move_counter += 1
                    if self._move_counter % 12 == 0:
                        lines.append((f"Movimiento → ({event.x}, {event.y})", "move"))
                else:
                    lines.append((f"{event.glyph} {event.description()}", "action"))
            if moves and not any(level == "move" for _, level in lines):
                lines.append((f"{moves} muestras de movimiento descartadas por muestreo", "debug"))
            # One console write per batch instead of one per event.
            if lines:
                text = "\n".join(line for line, _ in lines)
                self.log_panel.log(text, lines[0][1], "REC")
                if self.dock is not None:
                    self.dock.append_log(text, lines[0][1], "REC")
            if self.dock is not None:
                self.dock.update_counter(len(self.recorder.events))
        if self.recorder.recording:
            self._record_poll_job = self.after(200, self._poll_record_buffer)

    def _flush_refresh(self) -> None:
        self._refresh_job = None
        if self.current:
            self.current.modified_at = time.time()
            self.event_list.set_macro(self.current)
            self._update_stats()
            self._schedule_save()

    def _on_progress(self, index: int, total: int, cycle: int) -> None:
        def update():
            self.progress.set(index / max(total, 1))
            self.event_list.highlight(index - 1)
        self.after(0, update)

    def _set_state(self, state: str) -> None:
        def apply():
            self.app_state = state
            text, bg, fg = STATE_STYLES[state]
            self.status_pill.configure(text=text, fg_color=bg, text_color=fg)
            self._update_buttons()
        self.after(0, apply)

    def _on_hotkey(self, action: str) -> None:
        if self._capturing_hotkey:
            return
        self.after(0, lambda: self._handle_hotkey(action))

    def _handle_hotkey(self, action: str) -> None:
        if action == "record":
            self._log(f"Atajo {describe_combo(self.settings.hotkeys['record'])} → grabar", "debug", "SYS")
            if self.dock is not None:
                if self.recorder.recording:
                    self.stop_recording()
                else:
                    self.start_recording_from_dock()
            else:
                self.toggle_record()
        elif action == "play":
            self._log(f"Atajo {describe_combo(self.settings.hotkeys['play'])} → reproducir/pausa", "debug", "SYS")
            if self.player.playing and not self.player.step_mode:
                self.toggle_pause()
            else:
                self.play()
        elif action == "stop":
            self._log("Atajo de parada de emergencia pulsado", "warn", "SYS")
            if self.recorder.recording:
                self.stop_recording()
            if self.player.playing:
                self.player.stop("hotkey")
        elif action == "step":
            self.step()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def toggle_record(self) -> None:
        """Open the vertical recording dock; recording starts from there."""
        if self.recorder.recording:
            self.stop_recording()
            return
        if self.player.playing:
            self._log("Detén la reproducción antes de grabar.", "warn")
            return
        if self.dock is not None:
            self.start_recording_from_dock()
            return
        self.open_recording_dock()

    def open_recording_dock(self) -> None:
        macro = self.current
        if macro is None or macro.events:
            macro = self.new_macro(select=True, silent=True)
        if macro is None:
            return
        self._pending_record_macro = macro
        self.withdraw()  # the big window is closed/hidden first
        self.dock = RecordingDock(self, macro)
        self.dock.protocol("WM_DELETE_WINDOW", self.close_dock)
        self._log("Panel de grabación abierto. Ajusta las opciones y pulsa INICIAR.", "system")

    def start_recording_from_dock(self) -> None:
        if self.recorder.recording or self.dock is None:
            return
        macro = self._pending_record_macro or self.current
        if macro is None:
            return
        seconds = self.settings.countdown_seconds
        if seconds > 0:
            CountdownOverlay(self.dock, seconds, lambda: self._begin_recording(macro))
        else:
            self._begin_recording(macro)

    def _begin_recording(self, macro: Macro) -> None:
        self._pending_record_macro = macro
        with self._record_lock:
            self._record_buffer.clear()
        self._move_counter = 0
        self.recorder.start()
        if self._record_poll_job:
            try:
                self.after_cancel(self._record_poll_job)
            except Exception:
                pass
        self._record_poll_job = self.after(200, self._poll_record_buffer)
        self._set_state("recording")
        if self.dock is not None:
            self.dock.on_recording_started()
        self._log(
            f"Grabando en «{macro.name}» · pulsa {describe_combo(self.settings.hotkeys['record'])} "
            f"o DETENER en el panel para terminar",
            "system", "REC",
        )
        if self.settings.play_sound:
            beep(660, 80)

    def stop_recording(self) -> None:
        if not self.recorder.recording:
            self.close_dock()
            return
        events = self.recorder.stop()
        if self._record_poll_job:
            try:
                self.after_cancel(self._record_poll_job)
            except Exception:
                pass
            self._record_poll_job = None
        self._poll_record_buffer()  # flush the last batch before closing the dock
        self._set_state("idle")
        if self.dock is not None:
            self.dock.on_recording_stopped()
        macro = self._pending_record_macro or self.current
        if macro is not None:
            macro.events = list(events)
            macro.sort()
            macro.modified_at = time.time()
            self.current = macro
            self._refresh_all()
            self._schedule_save()
        if self.settings.play_sound:
            beep(440, 80)
        self.close_dock()

    def close_dock(self) -> None:
        """Close the mini panel and bring the main window back."""
        if self.recorder.recording:
            self.stop_recording()
            return
        self._destroy_dock()
        self.deiconify()
        self.after(50, self.lift)

    def _destroy_dock(self) -> None:
        if self.dock is not None:
            try:
                self.dock.destroy()
            except Exception:
                pass
            self.dock = None

    def _on_repeat_until_change(self) -> None:
        """«repetir hasta detener» forces the infinite (0) repeat mode."""
        until = bool(self.repeat_until_var.get())
        if until:
            current = self.repeat_var.get()
            if current and current > 0:
                self._repeat_before_until = current
            self.repeat_var.set(0)
        else:
            self.repeat_var.set(self._repeat_before_until)
        self.repeat_entry.configure(state="disabled" if until else "normal")

    def _sync_repeat_settings(self) -> None:
        """Keep the persisted repeat values coherent with the switch."""
        self.settings.repeat_until_stopped = bool(self.repeat_until_var.get())
        if self.settings.repeat_until_stopped:
            self.settings.repeat = 0
        else:
            self.settings.repeat = self.repeat_var.get()

    def play(self, start_index: Optional[int] = None) -> None:
        if self.player.playing:
            self._log("Ya hay una reproducción activa.", "warn")
            return
        if not self.current or not self.current.events:
            self._log("No hay eventos en la macro actual.", "warn")
            return
        self._sync_repeat_settings()
        self.settings.playback_speed = self.speed_var.get()
        save_settings(self.settings)
        if self.settings.minimize_on_play:
            self.iconify()
        self.player.play(self.current, speed=self.settings.playback_speed,
                         repeat=self.settings.repeat, start_index=start_index or 0)
        if self.settings.play_sound:
            beep(880, 70)

    def play_from_selection(self) -> None:
        selected = self.event_list.selected_indices()
        if not selected:
            self._log("Selecciona un evento para reproducir desde ahí.", "warn")
            return
        self.play(start_index=selected[0])

    def toggle_pause(self) -> None:
        if self.player.playing and not self.player.step_mode:
            self.player.toggle_pause()

    def step(self) -> None:
        if self.player.playing and self.player.step_mode:
            self.player.step()
        elif not self.player.playing:
            if not self.current or not self.current.events:
                self._log("No hay eventos para depurar.", "warn")
                return
            self.player.start_step(self.current)
        else:
            self._log("Detén la reproducción antes de usar el modo paso.", "warn")

    def stop_all(self) -> None:
        if self.recorder.recording:
            self.stop_recording()
        if self.player.playing:
            self.player.stop("manual")
        self.progress.set(0)
        self.event_list.highlight(None)
        self._log("Todas las operaciones detenidas.", "system")

    def new_macro(self, select: bool = True, silent: bool = False) -> Optional[Macro]:
        macro = Macro(name=f"Macros {len(self.macros) + 1}")
        self.macros.append(macro)
        if select:
            self.current = macro
        self._refresh_macro_list()
        self._refresh_all()
        self._schedule_save()
        if not silent:
            self._log(f"Macro «{macro.name}» creada.", "success")
        return macro

    def duplicate_macro(self) -> None:
        if not self.current:
            return
        clone = Macro.from_dict(self.current.to_dict())
        clone.id = uuid.uuid4().hex[:8]
        clone.name = self.current.name + " (copia)"
        self.macros.append(clone)
        self.current = clone
        self._refresh_macro_list()
        self._refresh_all()
        self._schedule_save()
        self._log(f"Macro duplicada como «{clone.name}».", "success")

    def delete_macro(self) -> None:
        if not self.current:
            return
        if self.settings.confirm_delete and not messagebox.askyesno(
            "Eliminar macro", f"¿Eliminar «{self.current.name}»?"
        ):
            return
        self.macros.remove(self.current)
        self.current = self.macros[0] if self.macros else None
        self._refresh_macro_list()
        self._refresh_all()
        self._schedule_save()
        self._log("Macro eliminada.", "warn")

    def import_macro(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar macro",
            filetypes=[("Macro Studio / ReMouse", "*.json *.rms *.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            lower = path.lower()
            if lower.endswith(".rms") or lower.endswith(".txt"):
                macro = import_rms(Path(path))
            else:
                macro = load_macro_json(Path(path))
        except Exception as exc:
            messagebox.showerror("Error al importar", str(exc))
            self._log(f"Error al importar: {exc}", "error")
            return
        self.macros.append(macro)
        self.current = macro
        self._refresh_macro_list()
        self._refresh_all()
        self._schedule_save()
        self._log(f"Importada «{macro.name}» · {macro.event_count} eventos.", "success")

    def export_macro(self) -> None:
        if not self.current:
            self._log("No hay macro para exportar.", "warn")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar macro",
            defaultextension=".rms",
            initialfile=self.current.name.replace(" ", "_") + ".rms",
            filetypes=[("ReMouse .rms", "*.rms"), ("Macro Studio .json", "*.json")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".json"):
                save_macro_json(self.current, Path(path))
            else:
                Path(path).write_text(export_rms(self.current), encoding="utf-8")
            self._log(f"Exportada a {path}", "success")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))
            self._log(f"Error al exportar: {exc}", "error")

    # -- event editing ------------------------------------------------------

    def add_event(self, kind: str) -> None:
        if not self.current:
            self._log("Crea una macro primero.", "warn")
            return
        last_time = self.current.duration_ms
        if kind == "delay":
            event = MacroEvent(EventType.DELAY, last_time + 500)
        else:
            event = MacroEvent(EventType.COMMENT, last_time, comment="Nueva nota")
        EventDialog(self, event, lambda saved: self._insert_event(saved))

    def _insert_event(self, event: MacroEvent) -> None:
        if not self.current:
            return
        self.current.add_event(event)
        self.current.sort()
        self.event_list.set_macro(self.current)
        self._update_stats()
        self._schedule_save()
        self._log(f"Evento añadido: {event.description()}", "success")

    def edit_event(self, index: int) -> None:
        if not self.current or index >= len(self.current.events):
            return
        EventDialog(self, self.current.events[index], lambda saved: self._replace_event(index, saved))

    def _replace_event(self, index: int, event: MacroEvent) -> None:
        if not self.current:
            return
        self.current.events[index] = event
        self.current.sort()
        self.current.modified_at = time.time()
        self.event_list.set_macro(self.current)
        self._update_stats()
        self._schedule_save()
        self._log(f"Evento #{index + 1} actualizado: {event.description()}", "info")

    def delete_events(self, indices: List[int]) -> None:
        if not self.current or not indices:
            return
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.current.events):
                del self.current.events[index]
        self.event_list.set_macro(self.current)
        self._update_stats()
        self._schedule_save()
        self._log(f"{len(indices)} evento(s) eliminado(s).", "warn")

    def toggle_events(self, indices: List[int]) -> None:
        if not self.current:
            return
        for index in indices:
            if 0 <= index < len(self.current.events):
                event = self.current.events[index]
                event.enabled = not event.enabled
        self.event_list.set_macro(self.current)
        self._schedule_save()
        self._log(f"Estado de {len(indices)} evento(s) cambiado.", "info")

    def reorder_event(self, old: int, new: int) -> None:
        if not self.current:
            return
        events = self.current.events
        events[old], events[new] = events[new], events[old]
        self.current.modified_at = time.time()
        self.event_list.set_macro(self.current)
        self._schedule_save()
        self._log(f"Evento movido de #{old + 1} a #{new + 1}.", "debug")

    def on_select_event(self, index: Optional[int]) -> None:
        if index is not None and self.current and index < len(self.current.events):
            event = self.current.events[index]
            self.hint_label.configure(
                text=f"Seleccionado #{index + 1}: {event.description()} ·"
                     f" Doble clic para editar · Espacio para activar/desactivar"
            )
        else:
            self.hint_label.configure(
                text=f"Grabar: {describe_combo(self.settings.hotkeys['record'])}   ·   "
                     f"Reproducir: {describe_combo(self.settings.hotkeys['play'])}   ·   "
                     f"Parada: {describe_combo(self.settings.hotkeys['stop'])}   ·   "
                     f"Paso: {describe_combo(self.settings.hotkeys['step'])}"
            )

    # -- settings / theme ---------------------------------------------------

    def open_settings(self) -> None:
        SettingsDialog(
            self, self.settings,
            on_save=self._apply_settings,
            hotkey_actions={
                "record": "Iniciar / detener grabación",
                "play": "Reproducir / pausar",
                "stop": "Parada de emergencia",
                "step": "Modo paso a paso",
            },
            on_hotkey=lambda: None,
            capture_start=lambda: setattr(self, "_capturing_hotkey", True),
            capture_end=lambda: setattr(self, "_capturing_hotkey", False),
        )

    def _apply_settings(self, settings: Settings) -> None:
        old_hint = str(self.hint_label.cget("text"))
        self.settings = settings
        save_settings(settings)
        ctk.set_appearance_mode(settings.theme)
        theme = "light" if settings.theme == "light" else "dark"
        self.log_panel.set_theme(theme)
        self.event_list.configure_style(theme)
        self.recorder.settings = settings
        until = bool(settings.repeat_until_stopped) or settings.repeat == 0
        self._repeat_before_until = settings.repeat if settings.repeat > 0 else 1
        self.repeat_var.set(0 if until else settings.repeat)
        self.repeat_until_var.set(until)
        self._on_repeat_until_change()
        self._apply_hotkeys()
        self.theme_btn.configure(image=icon("sun" if theme == "dark" else "moon", 17))
        self._refresh_macro_list()
        self._log("Preferencias guardadas.", "success")

    def _apply_hotkeys(self) -> None:
        self.hotkeys.set_bindings(self.settings.hotkeys)
        self.on_select_event(None)

    def toggle_theme(self) -> None:
        self.settings.theme = "light" if self.settings.theme == "dark" else "dark"
        self._apply_settings(self.settings)
        self._log(f"Tema cambiado a {self.settings.theme}.", "info")

    # -- persistence & refresh ---------------------------------------------

    def _schedule_save(self) -> None:
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(700, self._delayed_save)

    def _delayed_save(self) -> None:
        self._save_job = None
        self.save_library()

    def save_library(self) -> None:
        try:
            save_library(self.macros)
        except Exception as exc:
            self._log(f"No se pudo guardar la biblioteca: {exc}", "error")

    def _refresh_all(self) -> None:
        self._refresh_macro_list()
        if self.current:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, self.current.name)
            self.desc_entry.delete(0, "end")
            self.desc_entry.insert(0, self.current.description)
        else:
            self.name_entry.delete(0, "end")
            self.desc_entry.delete(0, "end")
        self.event_list.set_macro(self.current)
        self._update_stats()
        self._update_buttons()

    def _refresh_macro_list(self) -> None:
        for child in self.macro_list.winfo_children():
            child.destroy()
        for index, macro in enumerate(self.macros):
            selected = macro is self.current
            card = ctk.CTkFrame(
                self.macro_list,
                fg_color=("#263354", "#1f2740") if selected else ("gray88", "#1c202c"),
                corner_radius=8,
                border_width=1 if selected else 0,
                border_color=("#6c8cff", "#6c8cff"),
            )
            card.grid(row=index, column=0, sticky="ew", pady=3)
            card.grid_columnconfigure(0, weight=1)
            btn = ctk.CTkButton(
                card, text=macro.name or "Sin nombre", anchor="w", height=34,
                font=ctk.CTkFont(size=12, weight="bold" if selected else "normal"),
                fg_color="transparent", hover_color=("gray78", "#2a3040"),
                command=lambda m=macro: self.select_macro(m),
            )
            btn.grid(row=0, column=0, sticky="ew", padx=6, pady=(5, 0))
            detail = ctk.CTkLabel(
                card, text=f"{macro.event_count} eventos · {macro.duration_ms / 1000:.1f} s",
                font=ctk.CTkFont(size=10), text_color=("gray50", "gray65"), anchor="w",
            )
            detail.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 5))
            ctk.CTkButton(
                card, text="⋯", width=24, height=24, font=ctk.CTkFont(size=14),
                fg_color="transparent", hover_color=("gray78", "#2a3040"),
                command=lambda m=macro: self._macro_menu(m),
            ).grid(row=0, column=1, padx=4)
        if not self.macros:
            ctk.CTkLabel(self.macro_list, text="Sin macros.\nPulsa + para crear una.",
                         font=ctk.CTkFont(size=11), text_color=("gray50", "gray65"),
                         justify="center").grid(row=0, column=0, pady=30)

    def _macro_menu(self, macro: Macro) -> None:
        import tkinter as tk

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Seleccionar", command=lambda: self.select_macro(macro))
        menu.add_command(label="Duplicar", command=lambda: (self.select_macro(macro), self.duplicate_macro()))
        menu.add_command(label="Eliminar", command=lambda: (self.select_macro(macro), self.delete_macro()))
        menu.post(self.winfo_pointerx(), self.winfo_pointery())

    def select_macro(self, macro: Macro) -> None:
        if self.current is macro:
            return
        if self.player.playing or self.recorder.recording:
            self._log("Detén la operación actual antes de cambiar de macro.", "warn")
            return
        self.current = macro
        self._refresh_all()
        self._log(f"Macro seleccionada: «{macro.name}».", "info")

    def _on_name_change(self, _event=None) -> None:
        if self.current:
            self.current.name = self.name_entry.get() or "Sin nombre"
            self.current.modified_at = time.time()
            self._refresh_macro_list()
            self._schedule_save()

    def _on_desc_change(self, _event=None) -> None:
        if self.current:
            self.current.description = self.desc_entry.get()
            self._schedule_save()

    def _update_stats(self) -> None:
        if not self.current:
            for label in self.stat_labels.values():
                label.configure(text="0")
            return
        stats = self.current.stats()
        values = {
            "events": str(self.current.event_count),
            "duration": f"{self.current.duration_ms / 1000:.2f}s",
            "clicks": str(stats["clicks"]),
            "keys": str(stats["keys"]),
        }
        for key, value in values.items():
            self.stat_labels[key].configure(text=value)

    # -- icon-only button layout --------------------------------------------

    def _apply_compact_mode(self) -> None:
        """Buttons are icon-only in every window state, including maximised."""
        self._compact_mode = True
        for button in self._button_specs:
            button.configure(text="")
        for button in self._sidebar_buttons:
            button.pack_configure(fill="none")

    def _hint_button(self, label: str) -> None:
        self.hint_label.configure(text=f"  {label}")

    def _update_buttons(self) -> None:
        recording = self.recorder.recording
        playing = self.player.playing
        self.play_btn.configure(state="disabled" if playing or recording else "normal")
        self.pause_btn.configure(state="normal" if playing and not self.player.step_mode else "disabled")
        self.step_btn.configure(state="normal" if playing and self.player.step_mode else "normal")
        self.stop_btn.configure(state="normal" if playing or recording else "disabled")
        self.from_here_btn.configure(state="normal" if not playing and not recording else "disabled")

    def on_close(self) -> None:
        if self._record_poll_job:
            try:
                self.after_cancel(self._record_poll_job)
            except Exception:
                pass
            self._record_poll_job = None
        if self.recorder.recording:
            self.stop_recording()
        self._destroy_dock()
        if self.player.playing:
            self.player.stop("manual")
        self.hub.stop()
        self._sync_repeat_settings()
        self.settings.playback_speed = self.speed_var.get()
        save_settings(self.settings)
        self.save_library()
        self.destroy()
