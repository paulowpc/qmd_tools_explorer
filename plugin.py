# -*- coding: utf-8 -*-

from pathlib import Path

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .ui.dock import BDCSTACDock


class QMDToolsExplorerPlugin:

    def __init__(self, iface):

        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):

        # Diretório principal do plugin
        plugin_dir = Path(__file__).resolve().parent

        # Caminho do ícone
        icon_path = plugin_dir / "icon.png"

        # Cria a ação com ícone + texto
        self.action = QAction(
            QIcon(str(icon_path)),
            "QMD Tools Explorer",
            self.iface.mainWindow()
        )

        self.action.setToolTip(
            "Abrir QMD Tools Explorer"
        )

        self.action.setStatusTip(
            "Abrir QMD Tools Explorer"
        )

        self.action.triggered.connect(
            self.run
        )

        # Menu do QGIS
        self.iface.addPluginToMenu(
            "&QMD Tools Explorer",
            self.action
        )

        # Barra de ferramentas
        self.iface.addToolBarIcon(
            self.action
        )

    def unload(self):

        if self.action:

            self.iface.removePluginMenu(
                "&QMD Tools Explorer",
                self.action
            )

            self.iface.removeToolBarIcon(
                self.action
            )

        if self.dock:

            self.iface.removeDockWidget(
                self.dock
            )

            self.dock.deleteLater()
            self.dock = None

    def run(self):

        if self.dock is None:

            self.dock = BDCSTACDock(
                self.iface
            )

            self.iface.addDockWidget(
                2,
                self.dock
            )

        self.dock.show()
        self.dock.raise_()