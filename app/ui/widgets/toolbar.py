from PySide6.QtWidgets import QHBoxLayout, QWidget


class ToolBar(QWidget):

    def __init__(self):
        super().__init__()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

    def add(self, widget):
        self.layout.addWidget(widget)

    def addStretch(self):
        self.layout.addStretch()

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()