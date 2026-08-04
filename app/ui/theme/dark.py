from app.ui.theme.base import ColorPalette, Theme


DarkTheme = Theme(
    name="dark",
    color=ColorPalette(
        # Brand
        primary="#22A5AD",
        primary_hover="#15909A",
        primary_pressed="#0E7C86",

        # Backgrounds
        window="#0A1D30",
        surface="#102941",
        card="#15334F",
        sidebar="#0A1D30",
        sidebar_text="#E7EEF3",
        sidebar_text_secondary="#93AAC0",
        sidebar_active="#0E7C86",
        sidebar_hover="#15334F",
        sidebar_card="#15334F",
        sidebar_card_border="#294762",

        # Borders
        border="#294762",
        divider="#203C56",

        # Text
        text="#E7EEF3",
        text_secondary="#AFC4D6",
        text_light="#FFFFFF",

        # Status
        success="#48B983",
        warning="#D9A74E",
        error="#E26C68",
        info="#79A9E8",

        # Inputs
        input="#102941",
        input_border="#294762",
        input_focus="#22A5AD",

        # Tables
        table_header="#102941",
        table_grid="#203C56",

        # Charts
        chart_1="#22A5AD",
        chart_2="#48B983",
        chart_3="#D9A74E",
        chart_4="#E26C68",
        chart_5="#79A9E8",
    ),
)
