"""Interactive overview pages for the FlowLab operating-system domains."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


@dataclass(frozen=True)
class Feature:
    title: str
    description: str
    action: str


class FeaturePage(QWidget):
    """A click-through page for a defined SDS domain.

    These pages intentionally expose only SDS-approved operational concepts.
    They give every active navigation destination a useful, interactive surface
    while the underlying specialised services are implemented incrementally.
    """

    action_requested = Signal(str)

    def __init__(self, title: str, subtitle: str, features: tuple[Feature, ...]):
        super().__init__()
        self.setObjectName("FeaturePage")
        self._title = title
        self._subtitle = subtitle
        self._features = features
        self._build_ui()
        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("FeatureScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        content = QVBoxLayout(body)
        content.setContentsMargins(28, 26, 28, 40)
        content.setSpacing(20)

        header = QVBoxLayout()
        header.setSpacing(2)
        heading = QLabel(self._title)
        heading.setObjectName("FeatureHeading")
        subtitle = QLabel(self._subtitle)
        subtitle.setObjectName("FeatureSubtitle")
        subtitle.setWordWrap(True)
        header.addWidget(heading)
        header.addWidget(subtitle)
        content.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for index, feature in enumerate(self._features):
            card = self._make_card(feature)
            grid.addWidget(card, index // 3, index % 3)
            grid.setColumnStretch(index % 3, 1)
        content.addLayout(grid)

        self.detail = QFrame()
        self.detail.setObjectName("FeatureDetail")
        detail_layout = QHBoxLayout(self.detail)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        self.detail_label = QLabel("Select an area to review its controlled workflow.")
        self.detail_label.setObjectName("FeatureDetailText")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(self.detail_label)
        content.addWidget(self.detail)
        content.addStretch(1)

    def _make_card(self, feature: Feature):
        card = QPushButton()
        card.setObjectName("FeatureCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(134)
        card.setToolTip(f"Open {feature.title}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(5)
        title = QLabel(feature.title)
        title.setObjectName("FeatureCardTitle")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        description = QLabel(feature.description)
        description.setObjectName("FeatureCardDescription")
        description.setWordWrap(True)
        description.setAttribute(Qt.WA_TransparentForMouseEvents)
        prompt = QLabel("Open →")
        prompt.setObjectName("FeatureCardPrompt")
        prompt.setAttribute(Qt.WA_TransparentForMouseEvents)
        card_layout.addWidget(title)
        card_layout.addWidget(description, 1)
        card_layout.addWidget(prompt)
        card.clicked.connect(lambda: self._open_feature(feature))
        return card

    def _open_feature(self, feature: Feature):
        self.detail_label.setText(
            f"{feature.title}: {feature.description}"
        )
        self.action_requested.emit(feature.action)

    def _apply_theme(self, theme):
        c = theme.color
        self.setStyleSheet(f"""
QWidget#FeaturePage, QScrollArea#FeatureScroll {{ background: {c.window}; border: none; }}
QLabel#FeatureHeading {{ color: {c.text}; font-size: 22px; font-weight: 700; }}
QLabel#FeatureSubtitle {{ color: {c.text_secondary}; font-size: 12px; }}
QPushButton#FeatureCard {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 12px; text-align: left; }}
QPushButton#FeatureCard:hover {{ border-color: {c.primary}; background: {c.window}; }}
QPushButton#FeatureCard QLabel {{ background: transparent; border: none; }}
QLabel#FeatureCardTitle {{ color: {c.text}; font-size: 14px; font-weight: 700; }}
QLabel#FeatureCardDescription {{ color: {c.text_secondary}; font-size: 11px; }}
QLabel#FeatureCardPrompt {{ color: {c.primary}; font-size: 11px; font-weight: 700; }}
QFrame#FeatureDetail {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; }}
QLabel#FeatureDetailText {{ color: {c.text_secondary}; font-size: 12px; }}
""")

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
