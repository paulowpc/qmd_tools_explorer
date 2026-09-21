# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QDialogButtonBox,
    QGroupBox,
)


class SettingsDialog(QDialog):
    """Janela de configurações do QMD Tools Explorer."""

    MODULES = [
        ("search", "Busca / Imagens de Satélite"),
        ("results", "Resultados"),
        ("fire", "Focos de Queimadas"),
        ("goes", "Análise de pontos GOES"),
        ("layers", "Camadas de Referência"),
        ("log", "Log"),
        ("system", "Sistema"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Configurações — QMD Tools Explorer"
        )

        self.setMinimumWidth(360)

        self.settings = QSettings(
            "INPE",
            "QMDToolsExplorer"
        )

        self.checkboxes = {}

        self._build_ui()
        self._load_settings()


    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            14, 14, 14, 14
        )

        layout.setSpacing(10)

        title = QLabel(
            "Configurações do QMD Tools Explorer"
        )

        title.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
        )

        layout.addWidget(title)

        group = QGroupBox("Módulos")

        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(7)

        for key, label in self.MODULES:

            checkbox = QCheckBox(label)

            self.checkboxes[key] = checkbox

            group_layout.addWidget(
                checkbox
            )

        layout.addWidget(group)
        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel |
            QDialogButtonBox.Save
        )

        buttons.button(
            QDialogButtonBox.Save
        ).setText("Salvar")

        buttons.button(
            QDialogButtonBox.Cancel
        ).setText("Cancelar")

        buttons.accepted.connect(
            self._save_settings
        )

        buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(buttons)


    def _load_settings(self):

        for key, _label in self.MODULES:

            value = self.settings.value(
                f"modules/{key}",
                True,
                type=bool,
            )

            self.checkboxes[key].setChecked(
                value
            )


    def _save_settings(self):

        for key, checkbox in self.checkboxes.items():

            self.settings.setValue(
                f"modules/{key}",
                checkbox.isChecked()
            )

        self.settings.sync()

        self.accept()


    def module_states(self):

        return {
            key: checkbox.isChecked()
            for key, checkbox in self.checkboxes.items()
        }


__all__ = [
    "SettingsDialog"
]
