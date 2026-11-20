"""Animated welcome / splash screen shown when the application starts."""
from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .. import __version__


STEPS = [
    ("Preparando la interfaz…", 0.18),
    ("Cargando biblioteca de macros…", 0.45),
    ("Registrando atajos globales…", 0.72),
    ("Listo para grabar", 1.0),
]


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "assets" / "macro_studio.ico"


class WelcomeScreen(ctk.CTkToplevel):
    """Frameless, always-on-top splash that hands over to the main window."""

    def __init__(self, app: ctk.CTk):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.configure(fg_color="#0b0e16")

        width, height = 520, 330
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        try:
            self.iconbitmap(str(_icon_path()))
        except Exception:
            pass

        card = ctk.CTkFrame(
            self, corner_radius=20, fg_color=("#1a2130", "#141a28"),
            border_width=1, border_color=("#6c8cff", "#3a4a7a"),
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)
        card.bind("<Button-1>", lambda _e: self.close())

        # -- logo -----------------------------------------------------------
        logo_path = _icon_path()
        if logo_path.is_file():
            try:
                image = Image.open(logo_path).convert("RGBA")
                image.thumbnail((96, 96), Image.LANCZOS)
                logo_image = ctk.CTkImage(light_image=image, dark_image=image, size=(96, 96))
                ctk.CTkLabel(card, text="", image=logo_image).pack(pady=(28, 6))
            except Exception:
                ctk.CTkLabel(card, text="◎", font=ctk.CTkFont(size=64, weight="bold"),
                             text_color="#6c8cff").pack(pady=(22, 6))
        else:
            ctk.CTkLabel(card, text="◎", font=ctk.CTkFont(size=64, weight="bold"),
                         text_color="#6c8cff").pack(pady=(22, 6))

        # -- text -----------------------------------------------------------
        ctk.CTkLabel(
            card, text="Macro Studio",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=("#e8edff", "#f2f5ff"),
        ).pack()
        ctk.CTkLabel(
            card, text=f"v{__version__}  ·  Grabador & Reproductor de Macros",
            font=ctk.CTkFont(size=11), text_color=("#8fa9ff", "#8fa9ff"),
        ).pack(pady=(2, 18))

        self.progress = ctk.CTkProgressBar(
            card, width=340, height=8, corner_radius=4,
            progress_color="#6c8cff", fg_color=("#2a3346", "#222a3c"),
        )
        self.progress.set(0)
        self.progress.pack()

        self.status = ctk.CTkLabel(
            card, text=STEPS[0][0], font=ctk.CTkFont(size=11),
            text_color=("#9aa7bd", "#9aa7bd"),
        )
        self.status.pack(pady=(10, 0))

        ctk.CTkLabel(
            card, text="Haz clic para continuar",
            font=ctk.CTkFont(size=10), text_color=("#6b7689", "#6b7689"),
        ).pack(side="bottom", pady=(0, 14))

        self._step = 0
        self._job: str | None = None
        self._advance()

    def _advance(self) -> None:
        if self._step < len(STEPS):
            text, value = STEPS[self._step]
            self.status.configure(text=text)
            self.progress.set(value)
            self._step += 1
            self._job = self.after(220, self._advance)
        else:
            self._job = self.after(300, self.close)

    def close(self) -> None:
        """Close the splash and reveal the main window."""
        if not self.winfo_exists():
            return
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self.destroy()
        self.app.deiconify()
        self.app.lift()
