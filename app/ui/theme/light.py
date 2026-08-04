from app.ui.theme.base import ColorPalette, Theme


LightTheme = Theme(
    name="light",
    color=ColorPalette(
        # Brand
        primary="#0E7C86",
        primary_hover="#0A5F67",
        primary_pressed="#084B52",

        # Backgrounds
        window="#F2F6F9",
        surface="#FFFFFF",
        card="#FFFFFF",
        sidebar="#0F2942",
        sidebar_text="#E7EEF3",
        sidebar_text_secondary="#93AAC0",
        sidebar_active="#0E7C86",
        sidebar_hover="#15334F",
        sidebar_card="#15334F",
        sidebar_card_border="#294762",

        # Borders
        border="#DCE5EC",
        divider="#EAF0F4",

        # Text
        text="#0E2131",
        text_secondary="#5B7185",
        text_light="#FFFFFF",

        # Status
        success="#1F8F5F",
        warning="#C2872F",
        error="#C6413E",
        info="#2A4E92",

        # Inputs
        input="#FFFFFF",
        input_border="#DCE5EC",
        input_focus="#0E7C86",

        # Tables
        table_header="#F2F6F9",
        table_grid="#EAF0F4",

        # Charts
        chart_1="#0E7C86",
        chart_2="#1F8F5F",
        chart_3="#C2872F",
        chart_4="#C6413E",
        chart_5="#2A4E92",
    ),
)
