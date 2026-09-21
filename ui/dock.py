# -*- coding: utf-8 -*-

from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSize, QRect, QSettings
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QLabel,
    QTabBar,
    QStackedWidget,
)
from qgis.PyQt.QtGui import QPixmap, QIcon

from .search_widget import SearchWidget
from .results_widget import ResultsWidget
from .log_widget import LogWidget
from .system_widget import SystemWidget
from .layer_widgets import LayersWidget
from .fire_widget import FireWidget
from ..core.roi_manager import ROIManager

from .analisar_pontos_goes_dialog import AnalisarPontosGoesDialog


class VerticalIconTabBar(QTabBar):

    def tabSizeHint(self, index):
        return QSize(46, 48) # QSize(46, 58)

    def paintEvent(self, event):
        from qgis.PyQt.QtGui import QPainter

        painter = QPainter(self)

        for index in range(self.count()):
            rect = self.tabRect(index)

            if not rect.isValid():
                continue

            if index == self.currentIndex():
                painter.fillRect(
                    rect,
                    self.palette().alternateBase()
                )

            icon = self.tabIcon(index)

            if not icon.isNull():
                icon_size = self.iconSize()

                x = rect.x() + (
                    rect.width() - icon_size.width()
                ) // 2

                y = rect.y() + (
                    rect.height() - icon_size.height()
                ) // 2

                icon.paint(
                    painter,
                    QRect(
                        x,
                        y,
                        icon_size.width(),
                        icon_size.height(),
                    ),
                    Qt.AlignCenter,
                )

            painter.drawLine(
                rect.bottomLeft(),
                rect.bottomRight()
            )

        painter.end()


class BDCSTACDock(QDockWidget):

    def __init__(self, iface_or_parent=None):

        parent = (
            iface_or_parent.mainWindow()
            if hasattr(iface_or_parent, "mainWindow")
            else iface_or_parent
        )

        super().__init__(parent)

        self.setObjectName("QMDToolsExplorerDock")
        self.setWindowTitle("QMD Tools Explorer")

        self.setAllowedAreas(
            Qt.LeftDockWidgetArea |
            Qt.RightDockWidgetArea
        )

        self.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )

        # Largura livre para permitir redimensionamento horizontal.
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self.resize(450, 700)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.settings = QSettings("INPE", "QMDToolsExplorer")
        self._module_defs = []
        self._module_enabled = {}

        self._build_ui()


    # ======================================================
    # INTERFACE
    # ======================================================

    def _build_ui(self):

        root = QWidget(self)
        root.setMinimumSize(0, 0)
        root.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==================================================
        # SIDEBAR
        # ==================================================

        sidebar = QWidget()
        sidebar.setFixedWidth(56)
        sidebar.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding
        )

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        tab_bar = VerticalIconTabBar()
        tab_bar.setShape(QTabBar.RoundedWest)
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setIconSize(QSize(26, 26))
        tab_bar.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding
        )

        tab_bar.setStyleSheet("""
            QTabBar::tab {
                width: 50px;
                height: 48px;
                margin: 0px;
                padding: 2px;
            }

            QTabBar::tab:selected {
                background: #f2f2f2;
            }

            QTabBar::tab:hover {
                background: #e8e8e8;
            }
        """)

        sidebar_layout.addWidget(tab_bar, 1)

        # ==================================================
        # BOTÃO CONFIGURAÇÕES
        # ==================================================

        settings_button = QPushButton()
        settings_button.setToolTip("Configurações")
        settings_button.setFixedSize(46,48)
        settings_button.setIconSize(QSize(26, 26))
        settings_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
            }

            QPushButton:hover {
                background: #e8e8e8;
            }
        """)

        # Primeiro tenta o SVG local do plugin.
        settings_icon_path = (
            Path(__file__).resolve().parent.parent
            / "assets" / "icons" / "settings.svg"
        )

        if settings_icon_path.exists():
            settings_button.setIcon(
                QIcon(str(settings_icon_path))
            )

        sidebar_layout.addWidget(
            settings_button,
            0,
            Qt.AlignHCenter
        )

        main_layout.addWidget(sidebar)

        # ==================================================
        # PAINEL DIREITO
        # ==================================================

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ==================================================
        # CABEÇALHO
        # ==================================================

        header = QWidget()
        header.setFixedHeight(45)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(0)

        # --------------------------------------------------
        # TÍTULO
        # --------------------------------------------------

        title_label = QLabel("QMD Tools Explorer")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)

        header_layout.addWidget(title_label)
        right_layout.addWidget(header)

        # ==================================================
        # ROI
        # ==================================================

        self.roi_manager = ROIManager(self)

        # ==================================================
        # WIDGETS DOS MÓDULOS
        # ==================================================

        self.search = SearchWidget(
            roi_manager=self.roi_manager
        )

        self.results = ResultsWidget(
            roi_manager=self.roi_manager
        )

        self.fire = FireWidget(
            roi_manager=self.roi_manager
        )

        self.goes = AnalisarPontosGoesDialog()

        self.layers = LayersWidget()
        self.log = LogWidget()
        self.system = SystemWidget()

        for widget in (
            self.search,
            self.results,
            self.fire,
            self.goes,
            self.layers,
            self.log,
            self.system,
        ):
            widget.setMinimumSize(0, 0)
            widget.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Ignored
            )

        # ==================================================
        # ÁREA DE CONTEÚDO
        # ==================================================

        stack = QStackedWidget()
        stack.setMinimumSize(0, 0)
        stack.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        right_layout.addWidget(stack, 1)

        # Diretório raiz do plugin, usado pelos ícones dos módulos.
        plugin_dir = Path(__file__).resolve().parent.parent

        # ==================================================
        # DEFINIÇÃO DOS MÓDULOS
        # ==================================================

        tab_icons = [
            "busca.png",
            "resultado3.png",
            "fire.png",
            "goes.png",
            "camadas.png",
            "log2.png",
            "systems.png",
        ]

        module_defs = [
            (
                "search",
                "Busca / Imagens de Satélite",
                self.search,
                "Busca",
                tab_icons[0],
            ),
            (
                "results",
                "Resultados",
                self.results,
                "Resultados",
                tab_icons[1],
            ),
            (
                "fire",
                "Focos de Queimadas",
                self.fire,
                "Focos",
                tab_icons[2],
            ),
            (
                "goes",
                "Análise de pontos GOES",
                self.goes,
                "GOES",
                tab_icons[3],
            ),
            (
                "layers",
                "Camadas de Referência",
                self.layers,
                "Camadas",
                tab_icons[4],
            ),
            (
                "log",
                "Log",
                self.log,
                "Log",
                tab_icons[5],
            ),
            (
                "system",
                "Sistema",
                self.system,
                "Sistema",
                tab_icons[6],
            ),
        ]

        self._module_defs = []

        for key, label, widget, tooltip, icon_name in module_defs:

            icon_path = (
                plugin_dir
                / "assets"
                / "icons"
                / icon_name
            )

            icon = (
                QIcon(str(icon_path))
                if icon_path.exists()
                else QIcon()
            )

            stack_index = stack.addWidget(widget)

            self._module_defs.append({
                "key": key,
                "label": label,
                "widget": widget,
                "tooltip": tooltip,
                "icon": icon,
                "stack_index": stack_index,
            })

        self.tabs = stack
        self.tab_bar = tab_bar
        self.settings_button = settings_button

        # Monta as abas de acordo com as configurações salvas.
        self._load_module_visibility()

        # ==================================================
        # CONEXÕES
        # ==================================================

        tab_bar.currentChanged.connect(
            self._on_tab_changed
        )

        settings_button.clicked.connect(
            self._open_settings
        )

        self.search.search_requested.connect(
            self._show_results
        )

        # Painel direito: cabeçalho + conteúdo do módulo
        main_layout.addWidget(right_panel, 1)

        self.setWidget(root)


    # ======================================================
    # MÓDULOS / CONFIGURAÇÕES
    # ======================================================

    def _load_module_visibility(self):

        states = {}

        for module in self._module_defs:
            key = module["key"]

            states[key] = self.settings.value(
                f"modules/{key}",
                True,
                type=bool,
            )

        self._apply_module_visibility(states)


    def _apply_module_visibility(self, states):

        self._module_enabled = dict(states)

        current_widget = (
            self.tabs.currentWidget()
            if self.tabs.count() > 0
            else None
        )

        current_key = None

        for module in self._module_defs:
            if module["widget"] is current_widget:
                current_key = module["key"]
                break

        self.tab_bar.blockSignals(True)

        # Remove as abas atuais sem remover os widgets do stack.
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)

        # Recria somente as abas habilitadas.
        for module in self._module_defs:

            key = module["key"]

            if not states.get(key, True):
                continue

            index = self.tab_bar.addTab(
                module["icon"],
                ""
            )

            self.tab_bar.setTabToolTip(
                index,
                module["tooltip"]
            )

        self.tab_bar.blockSignals(False)

        # Mantém o módulo atual se ele continuar habilitado.
        if (
            current_key
            and states.get(current_key, True)
        ):
            self._select_module_by_key(current_key)

        else:
            # Se o módulo atual foi desabilitado,
            # seleciona o primeiro módulo disponível.
            if self.tab_bar.count() > 0:
                self.tab_bar.setCurrentIndex(0)
            else:
                self.tabs.setCurrentIndex(-1)


    def _select_module_by_key(self, key):

        visible_index = 0

        for module in self._module_defs:

            if not self._module_enabled.get(
                module["key"],
                True
            ):
                continue

            if module["key"] == key:

                self.tab_bar.setCurrentIndex(
                    visible_index
                )

                self.tabs.setCurrentIndex(
                    module["stack_index"]
                )

                return

            visible_index += 1


    def _on_tab_changed(self, index):

        if index < 0:
            return

        visible_modules = [
            module
            for module in self._module_defs
            if self._module_enabled.get(
                module["key"],
                True
            )
        ]

        if index >= len(visible_modules):
            return

        module = visible_modules[index]

        self.tabs.setCurrentIndex(
            module["stack_index"]
        )


    def _open_settings(self):

        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)

        if dialog.exec_():
            states = dialog.module_states()

            self._apply_module_visibility(
                states
            )


    # ======================================================
    # LIMPAR PESQUISA
    # ======================================================

    def clear_search(self):

        self.results.clear_search()

        # Só muda para Resultados se o módulo estiver habilitado.
        if self._module_enabled.get(
            "search",
            True
        ):
            self._select_module_by_key("search")


    # ======================================================
    # MOSTRAR RESULTADOS
    # ======================================================

    def _show_results(self, data):

        self.results.set_results(
            data["items"],
            data["output_dir"]
        )

        if self._module_enabled.get(
            "results",
            True
        ):
            self._select_module_by_key("results")
        else:
            self._select_module_by_key("search")


    # ======================================================
    # EXECUTAR BUSCA
    # ======================================================

    def run_search(self):

        self.search.execute_search(False)


    # ======================================================
    # CARREGAR GOOGLE HYBRID
    # ======================================================

    def load_google_hybrid(self):

        self.search.load_google_hybrid()


__all__ = [
    "BDCSTACDock"
]
