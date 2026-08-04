from __future__ import annotations

from dataclasses import dataclass, field


# ----------------------------------------------------------------------
# Colors
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class ColorPalette:
    # Brand
    primary: str
    primary_hover: str
    primary_pressed: str

    # Backgrounds
    window: str
    surface: str
    card: str
    sidebar: str
    sidebar_text: str
    sidebar_text_secondary: str
    sidebar_active: str
    sidebar_hover: str
    sidebar_card: str
    sidebar_card_border: str

    # Borders
    border: str
    divider: str

    # Text
    text: str
    text_secondary: str
    text_light: str

    # Status
    success: str
    warning: str
    error: str
    info: str

    # Inputs
    input: str
    input_border: str
    input_focus: str

    # Tables
    table_header: str
    table_grid: str

    # Charts
    chart_1: str
    chart_2: str
    chart_3: str
    chart_4: str
    chart_5: str

    # --------------------------------------------------
    # Backward Compatibility
    # --------------------------------------------------

    @property
    def input_bg(self):
        return self.input

    @property
    def border_light(self):
        return self.divider

    @property
    def table_hover(self):
        return self.divider

    @property
    def table_selected(self):
        return self.primary

    @property
    def text_muted(self):
        return self.text_secondary


# ----------------------------------------------------------------------
# Radius
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Radius:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20


# ----------------------------------------------------------------------
# Spacing
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


# ----------------------------------------------------------------------
# Typography Tokens
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Fonts:
    family: str = "Segoe UI"

    title: int = 24
    heading: int = 18
    subtitle: int = 15
    body: int = 13
    small: int = 11

    button: int = 10
    card_title: int = 10
    card_value: int = 30

    mono_family: str = "Consolas"
    mono_size: int = 10


# ----------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    name: str
    color: ColorPalette
    radius: Radius = field(default_factory=Radius)
    spacing: Spacing = field(default_factory=Spacing)
    font: Fonts = field(default_factory=Fonts)
