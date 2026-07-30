from app.ui.theme.base import ColorPalette, Theme


DarkTheme = Theme(
    name="dark",
    color=ColorPalette(
        # Brand
        primary="#2563EB",
        primary_hover="#1D4ED8",
        primary_pressed="#1E40AF",

        # Backgrounds
        window="#111827",
        surface="#1E293B",
        card="#1F2937",
        sidebar="#0F172A",

        # Borders
        border="#334155",
        divider="#475569",

        # Text
        text="#F8FAFC",
        text_secondary="#CBD5E1",
        text_light="#FFFFFF",

        # Status
        success="#22C55E",
        warning="#F59E0B",
        error="#EF4444",
        info="#3B82F6",

        # Inputs
        input="#1E293B",
        input_border="#475569",
        input_focus="#2563EB",

        # Tables
        table_header="#1E293B",
        table_grid="#334155",

        # Charts
        chart_1="#2563EB",
        chart_2="#10B981",
        chart_3="#F59E0B",
        chart_4="#EF4444",
        chart_5="#8B5CF6",
    ),
)