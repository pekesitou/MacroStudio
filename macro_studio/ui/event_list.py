"""Editable timeline / event list widget."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

import customtkinter as ctk

from ..models import EventType, Macro, MacroEvent
from .icons import icon

TYPE_TAGS = {
    EventType.MOVE: ("move", "#5b9dff"),
    EventType.MOUSE_DOWN: ("click", "#ff9f43"),
    EventType.MOUSE_UP: ("click", "#ff9f43"),
    EventType.SCROLL: ("scroll", "#a29bfe"),
    EventType.KEY_DOWN: ("key", "#26de81"),
    EventType.KEY_UP: ("key", "#26de81"),
    EventType.TEXT: ("text", "#00d2d3"),
    EventType.DELAY: ("delay", "#8b93a7"),
    EventType.COMMENT: ("comment", "#7f8c9a"),
}


class EventList(ctk.CTkFrame):
    """Treeview-based editable list of macro events."""

    def __init__(
        self,
        master,
        on_edit: Callable[[int], None],
        on_delete: Callable[[List[int]], None],
        on_toggle: Callable[[List[int]], None],
        on_reorder: Callable[[int, int], None],
        on_select: Callable[[Optional[int]], None],
        on_add: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_toggle = on_toggle
        self.on_reorder = on_reorder
        self.on_select = on_select
        self.on_add = on_add
        self.macro: Optional[Macro] = None
        self._highlight: Optional[int] = None
        self._style_configured = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            header, text="  LÍNEA DE TIEMPO", font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        ).pack(side="left")
        self.count_label = ctk.CTkLabel(
            header, text="0 eventos", font=ctk.CTkFont(size=11), text_color=("gray50", "gray65")
        )
        self.count_label.pack(side="right")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(0, 4))
        buttons = [
            ("add_delay", "Retardo", 70),
            ("add_comment", "Nota", 55),
            ("edit", "Editar", 62),
            ("toggle", "Activar", 68),
            ("up", "↑", 30),
            ("down", "↓", 30),
            ("delete", "Borrar", 62),
            ("clear", "Vaciar", 62),
        ]
        self.buttons = {}
        for key, label, width in buttons:
            btn = ctk.CTkButton(
                toolbar, text=label, width=width, height=26,
                font=ctk.CTkFont(size=11),
                fg_color=("gray75", "gray25"),
                hover_color=("gray65", "gray35"),
                command=lambda k=key: self._dispatch(k),
            )
            btn.pack(side="left", padx=2)
            self.buttons[key] = btn

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("num", "time", "type", "detail"),
            show="headings",
            selectmode="extended",
            height=12,
        )
        self.tree.heading("num", text="#", anchor="w")
        self.tree.heading("time", text="Tiempo", anchor="w")
        self.tree.heading("type", text="Tipo", anchor="w")
        self.tree.heading("detail", text="Acción", anchor="w")
        self.tree.column("num", width=38, anchor="w", stretch=False)
        self.tree.column("time", width=75, anchor="w", stretch=False)
        self.tree.column("type", width=108, anchor="w", stretch=False)
        self.tree.column("detail", width=320, anchor="w", stretch=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._dispatch("edit"))
        self.tree.bind("<Delete>", lambda e: self._dispatch("delete"))
        self.tree.bind("<space>", lambda e: self._dispatch("toggle"))

        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Editar…", command=lambda: self._dispatch("edit"))
        self._menu.add_command(label="Activar / desactivar", command=lambda: self._dispatch("toggle"))
        self._menu.add_separator()
        self._menu.add_command(label="Subir", command=lambda: self._dispatch("up"))
        self._menu.add_command(label="Bajar", command=lambda: self._dispatch("down"))
        self._menu.add_separator()
        self._menu.add_command(label="Eliminar", command=lambda: self._dispatch("delete"))
        self.tree.bind("<Button-3>", self._on_right_click)

    # -- theming ------------------------------------------------------------

    def configure_style(self, theme: str) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        dark = theme != "light"
        bg = "#1b1e27" if dark else "#fdfdff"
        fg = "#d7dce5" if dark else "#2d3748"
        sel_bg = "#2f3d63" if dark else "#c3d4ff"
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg,
                        rowheight=26, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=("#242a38" if dark else "#e8edf7"),
                        foreground=fg, relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", sel_bg)],
                  foreground=[("selected", "#ffffff" if dark else "#14213d")])
        style.configure("Vertical.TScrollbar", background=("#2a3040" if dark else "#d7dce8"),
                        arrowcolor=fg, troughcolor=bg, borderwidth=0)
        for tag, (_, color) in TYPE_TAGS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.tag_configure("disabled", foreground="#606a7d")
        self.tree.tag_configure("current", background="#3a4d7a" if dark else "#ffe3a3")
        self._style_configured = True

    # -- public API ---------------------------------------------------------

    def set_macro(self, macro: Optional[Macro]) -> None:
        self.macro = macro
        self._refresh()

    def refresh(self) -> None:
        self._refresh()

    def highlight(self, index: Optional[int]) -> None:
        if self._highlight == index:
            return
        self._highlight = index
        for item in self.tree.get_children():
            self.tree.item(item, tags=[])
        if index is not None:
            item = self.tree.get_children()[index] if index < len(self.tree.get_children()) else None
            if item:
                current_tags = list(self.tree.item(item, "tags"))
                self.tree.item(item, tags=current_tags + ["current"])
                self.tree.see(item)

    def selected_indices(self) -> List[int]:
        result = []
        for item in self.tree.selection():
            try:
                result.append(int(item))
            except ValueError:
                pass
        return sorted(result)

    # -- internals ----------------------------------------------------------

    def _refresh(self) -> None:
        if not self._style_configured:
            self.configure_style("dark")
        self.tree.delete(*self.tree.get_children())
        if not self.macro:
            self.count_label.configure(text="0 eventos")
            return
        for index, event in enumerate(self.macro.events):
            tag = TYPE_TAGS.get(event.type, ("delay", "#8b93a7"))[0]
            tags = [tag]
            if not event.enabled:
                tags.append("disabled")
            if index == self._highlight:
                tags.append("current")
            self.tree.insert(
                "", "end", iid=str(index),
                values=(
                    str(index + 1),
                    f"{event.time_ms / 1000:.2f} s",
                    f"{event.glyph} {event.type_label}",
                    event.description(),
                ),
                tags=tags,
            )
        self.count_label.configure(
            text=f"{len(self.macro.events)} eventos · {self.macro.duration_ms / 1000:.2f} s"
        )

    def _on_tree_select(self, _event=None) -> None:
        indices = self.selected_indices()
        self.on_select(indices[0] if indices else None)

    def _on_right_click(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self._menu.tk_popup(event.x_root, event.y_root)

    def _dispatch(self, key: str) -> None:
        indices = self.selected_indices()
        if key == "add_delay":
            self.on_add("delay")
        elif key == "add_comment":
            self.on_add("comment")
        elif key == "edit" and indices:
            self.on_edit(indices[0])
        elif key == "toggle" and indices:
            self.on_toggle(indices)
        elif key == "delete" and indices:
            self.on_delete(indices)
        elif key == "clear":
            self.on_delete(list(range(len(self.macro.events)))) if self.macro else None
        elif key in ("up", "down") and indices:
            index = indices[0]
            target = index - 1 if key == "up" else index + 1
            if 0 <= target < len(self.macro.events):
                self.on_reorder(index, target)
