from app.ui.theme import ThemeManager


class _ColorsProxy:
    """
    Backward-compatible color accessor.

    Existing code can continue using:
        Colors.PRIMARY
        Colors.TEXT
        Colors.BORDER
        ...

    Values are always read from the active theme.
    """

    _map = {
        # Brand
        "PRIMARY": "primary",
        "PRIMARY_HOVER": "primary_hover",
        "PRIMARY_PRESSED": "primary_pressed",

        # Backgrounds
        "WINDOW": "window",
        "SURFACE": "surface",
        "CARD": "card",
        "SIDEBAR": "sidebar",

        # Borders
        "BORDER": "border",
        "DIVIDER": "divider",

        # Text
        "TEXT": "text",
        "TEXT_SECONDARY": "text_secondary",
        "TEXT_LIGHT": "text_light",

        # Status
        "SUCCESS": "success",
        "WARNING": "warning",
        "ERROR": "error",
        "INFO": "info",

        # Inputs
        "INPUT": "input",
        "INPUT_BORDER": "input_border",
        "INPUT_FOCUS": "input_focus",

        # Tables
        "TABLE_HEADER": "table_header",
        "TABLE_GRID": "table_grid",

        # Charts
        "CHART_1": "chart_1",
        "CHART_2": "chart_2",
        "CHART_3": "chart_3",
        "CHART_4": "chart_4",
        "CHART_5": "chart_5",
    }

    def __getattr__(self, name):
        if name not in self._map:
            raise AttributeError(name)

        return getattr(ThemeManager.current().color, self._map[name])


Colors = _ColorsProxy()