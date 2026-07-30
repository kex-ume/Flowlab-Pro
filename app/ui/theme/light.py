from app.ui.theme.base import ColorPalette, Theme


LightTheme = Theme(
    name="light",
    color=ColorPalette(
        # Brand
        primary="#2563EB",
        primary_hover="#1D4ED8",
        primary_pressed="#1E40AF",

        # Backgrounds
        window="#F3F6FB",
        surface="#FFFFFF",
        card="#FFFFFF",
        sidebar="#E5E7EB",

        # Borders
        border="#D1D5DB",
        divider="#E5E7EB",

        # Text
        text="#111827",
        text_secondary="#374151",
        text_light="#FFFFFF",

        # Status
        success="#22C55E",
        warning="#F59E0B",
        error="#EF4444",
        info="#3B82F6",

        # Inputs
        input="#FFFFFF",
        input_border="#D1D5DB",
        input_focus="#2563EB",

        # Tables
        table_header="#F9FAFB",
        table_grid="#E5E7EB",

        # Charts
        chart_1="#2563EB",
        chart_2="#10B981",
        chart_3="#F59E0B",
        chart_4="#EF4444",
        chart_5="#8B5CF6",
    ),
)