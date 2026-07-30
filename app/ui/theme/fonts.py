from PySide6.QtGui import QFont


class Fonts:
    FAMILY = "Segoe UI"

    @classmethod
    def _font(cls, size: int, bold: bool = False, family: str | None = None):
        font = QFont(family or cls.FAMILY, size)
        font.setBold(bold)
        return font

    @classmethod
    def title(cls):
        return cls._font(24, bold=True)

    @classmethod
    def heading(cls):
        return cls._font(16, bold=True)

    @classmethod
    def subtitle(cls):
        return cls._font(11)

    @classmethod
    def body(cls):
        return cls._font(10)

    @classmethod
    def button(cls):
        return cls._font(10, bold=True)

    @classmethod
    def card_title(cls):
        return cls._font(10, bold=True)

    @classmethod
    def card_value(cls):
        return cls._font(30, bold=True)

    @classmethod
    def small(cls):
        return cls._font(9)

    @classmethod
    def mono(cls):
        return cls._font(10, family="Consolas")