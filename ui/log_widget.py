# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton
from ..core.stac_core import set_log_callback

class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        clear = QPushButton("Limpar")
        buttons.addStretch()
        buttons.addWidget(clear)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addLayout(buttons)
        layout.addWidget(self.text)
        clear.clicked.connect(self.text.clear)
        set_log_callback(self.append_log)

    def append_log(self, message):
        self.text.appendPlainText(str(message))
