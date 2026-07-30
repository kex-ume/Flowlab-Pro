from __future__ import annotations

from typing import Callable

from app.ui.theme.base import Theme
from app.ui.theme.dark import DarkTheme
from app.ui.theme.light import LightTheme


class ThemeManager:
    """
    Global runtime theme manager.
    """

    _theme: Theme = DarkTheme
    _listeners: list[Callable[[Theme], None]] = []

    # ---------------------------------------------------------
    # Current Theme
    # ---------------------------------------------------------

    @classmethod
    def current(cls) -> Theme:
        return cls._theme

    @classmethod
    def colors(cls):
        return cls._theme.color

    # ---------------------------------------------------------
    # Theme Switching
    # ---------------------------------------------------------

    @classmethod
    def set_theme(cls, theme: Theme):
        if cls._theme is theme:
            return

        cls._theme = theme

        for callback in cls._listeners.copy():
            try:
                callback(theme)
            except RuntimeError:
                cls.unregister(callback)

    @classmethod
    def set_dark(cls):
        cls.set_theme(DarkTheme)

    @classmethod
    def set_light(cls):
        cls.set_theme(LightTheme)

    @classmethod
    def toggle(cls):
        if cls.is_dark():
            cls.set_light()
        else:
            cls.set_dark()

    @classmethod
    def is_dark(cls) -> bool:
        return cls._theme.name == "dark"

    # ---------------------------------------------------------
    # Listener Management
    # ---------------------------------------------------------

    @classmethod
    def register(cls, callback: Callable[[Theme], None]):
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unregister(cls, callback: Callable[[Theme], None]):
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def clear(cls):
        cls._listeners.clear()