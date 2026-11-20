"""Entry point for Macro Studio."""
from __future__ import annotations

import sys
import traceback

try:
    import customtkinter  # noqa: F401
    import pynput  # noqa: F401
    from PIL import Image  # noqa: F401
except ImportError as exc:
    print("Faltan dependencias. Instálalas con:")
    print("  python -m pip install customtkinter pynput pillow")
    print(f"Detalle: {exc}")
    sys.exit(1)

from macro_studio.ui.app import MacroStudioApp
from macro_studio.ui.welcome import WelcomeScreen


def main() -> None:
    try:
        app = MacroStudioApp()
        app.withdraw()
        WelcomeScreen(app)  # hands over to the main window when it closes
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("Presiona Enter para salir…")


if __name__ == "__main__":
    main()
