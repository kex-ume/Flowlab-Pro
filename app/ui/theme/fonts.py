from PySide6.QtGui import QFont


class Fonts:

    FAMILY = "Segoe UI"

    @staticmethod
    def title():
        f = QFont(Fonts.FAMILY, 24)
        f.setBold(True)
        return f

    @staticmethod
    def heading():
        f = QFont(Fonts.FAMILY, 16)
        f.setBold(True)
        return f

    @staticmethod
    def subtitle():
        return QFont(Fonts.FAMILY, 11)

    @staticmethod
    def body():
        return QFont(Fonts.FAMILY, 10)

    @staticmethod
    def button():
        f = QFont(Fonts.FAMILY, 10)
        f.setBold(True)
        return f

    @staticmethod
    def card_title():
        f = QFont(Fonts.FAMILY, 10)
        f.setBold(True)
        return f

    @staticmethod
    def card_value():
        f = QFont(Fonts.FAMILY, 30)
        f.setBold(True)
        return f

    @staticmethod
    def small():
        return QFont(Fonts.FAMILY, 9)

    @staticmethod
    def mono():
        return QFont("Consolas", 10)