# -*- coding: utf-8 -*-

import sys
import importlib
from importlib import metadata
from pathlib import Path
import site

from qgis.PyQt.QtCore import Qt, QProcess
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QDialog, QDialogButtonBox,
)


class SystemWidget(QWidget):
    # Modo de teste temporario do instalador.
    # Simula lxml ausente sem alterar o ambiente Python.
    TEST_INSTALLER = False
    TEST_MISSING_PACKAGE = "lxml"


    """Módulo Sistema: apenas detecta e mostra dependências Python."""

    DEPENDENCIES = [
        {
            "package": "pystac-client",
            "import_name": "pystac_client",
            "description": "Acesso a catálogos STAC",
            "modules": ["Busca / Imagens de Satélite"],
        },
        {
            "package": "pystac",
            "import_name": "pystac",
            "description": "Estrutura e objetos STAC",
            "modules": ["Busca / Imagens de Satélite"],
        },
        {
            "package": "shapely",
            "import_name": "shapely",
            "description": "Operações e análises geométricas",
            "modules": ["Busca / Imagens de Satélite"],
        },
        {
            "package": "requests",
            "import_name": "requests",
            "description": "Acesso a serviços HTTP",
            "modules": ["Focos de Queimadas", "Resultados"],
        },
        {
            "package": "lxml",
            "import_name": "lxml",
            "description": "Processamento XML",
            "modules": ["Focos de Queimadas"],
        },
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.verificar_dependencias()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Sistema")
        title.setObjectName("systemTitle")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel(
            "Informações do ambiente Python e dependências utilizadas "
            "pelo QMD Tools Explorer."
        )
        subtitle.setObjectName("systemSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Ambiente Python
        # Usa um QWidget simples em vez de QGroupBox para evitar o
        # preenchimento/fundo padrão do tema do QGIS nessa área.
        python_group = QWidget()
        python_layout = QVBoxLayout(python_group)
        python_layout.setContentsMargins(18, 0, 18, 0)
        python_layout.setSpacing(6)

        python_title = QLabel("Ambiente Python")
        python_title_font = QFont()
        python_title_font.setBold(True)
        python_title.setFont(python_title_font)

        self.python_executable = QLabel()
        self.python_version = QLabel()
        self.python_executable.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.python_version.setTextInteractionFlags(Qt.TextSelectableByMouse)

        python_layout.addWidget(python_title)
        python_layout.addWidget(
            self._info_row("Executável:", self.python_executable)
        )
        python_layout.addWidget(
            self._info_row("Versão:", self.python_version)
        )

        layout.addWidget(python_group)

        dependencies_group = QGroupBox("Dependências Python")
        dependencies_layout = QVBoxLayout(dependencies_group)
        dependencies_layout.setContentsMargins(12, 12, 12, 12)
        dependencies_layout.setSpacing(10)

        self.table = QTableWidget(len(self.DEPENDENCIES), 5)
        self.table.setHorizontalHeaderLabels([
            "Pacote",
            "Versão",
            "Status",
            "Origem",
            "Utilizado por",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(True)
        dependencies_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.verify_button = QPushButton("↻  Verificar dependências")
        self.verify_button.setMinimumHeight(32)
        self.verify_button.clicked.connect(
            self.abrir_verificacao_dependencias
        )
        buttons.addWidget(self.verify_button)

        self.install_button = QPushButton("  Instalar dependências...")
        self.install_button.setMinimumHeight(32)
        self.install_button.clicked.connect(
            self.abrir_instalacao_dependencias
        )
        buttons.addWidget(self.install_button)

        dependencies_layout.addLayout(buttons)

        layout.addWidget(dependencies_group)
        layout.addStretch()



    @staticmethod
    def _info_row(label_text, value_widget):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(80)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        layout.addWidget(value_widget, 1)
        return widget

    def abrir_instalacao_dependencias(self):
        dialog = DependencyInstallDialog(
            self.DEPENDENCIES,
            parent=self,
        )
        dialog.exec_()
        self.verificar_dependencias()

    def abrir_verificacao_dependencias(self):
        """
        Abre a janela de verificação detalhada das dependências.

        A janela apenas verifica e informa o estado dos pacotes.
        Nenhuma instalação ou alteração no ambiente é realizada.
        """
        dialog = DependencyCheckDialog(
            self.DEPENDENCIES,
            parent=self,
        )

        dialog.exec_()

        # Atualiza a tabela principal ao fechar a janela.
        self.verificar_dependencias()

    def verificar_dependencias(self):
        self.python_executable.setText(sys.executable)
        self.python_version.setText(sys.version.split()[0])

        for row, dependency in enumerate(self.DEPENDENCIES):
            package = dependency["package"]
            description = dependency["description"]
            modules = dependency["modules"]

            available, version, origin = self._detect_dependency(
                dependency
            )

            self.table.setItem(row, 0, QTableWidgetItem(package))

            version_item = QTableWidgetItem(
                version if available else "—"
            )
            version_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, version_item)

            status_item = QTableWidgetItem(
                "✓ Disponível" if available else "✕ Ausente"
            )
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, status_item)

            self.table.setItem(
                row, 3, QTableWidgetItem(origin)
            )

            usage_item = QTableWidgetItem("\n".join(modules))
            usage_item.setToolTip(
                f"{description}\n\nUtilizado por:\n• "
                + "\n• ".join(modules)
            )
            self.table.setItem(row, 4, usage_item)

        # Mantém a altura da tabela principal estável.
        # resizeRowsToContents() fazia as linhas aumentarem cada vez que
        # a janela de verificação/instalação era fechada, por causa do
        # texto em múltiplas linhas na coluna "Utilizado por".
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 30)

        # requests possui dois módulos associados e pode usar duas linhas.
        requests_row = next(
            (
                row
                for row, dependency in enumerate(self.DEPENDENCIES)
                if dependency["package"] == "requests"
            ),
            None,
        )
        if requests_row is not None:
            self.table.setRowHeight(requests_row, 44)

    @staticmethod
    def _detect_dependency(dependency):
        """
        Importa a biblioteca pelo ambiente real do QGIS e identifica
        de onde ela veio pelo caminho do módulo.
        """
        import_name = dependency["import_name"]

        try:
            module = importlib.import_module(import_name)
        except Exception:
            return False, "—", "Não disponível"

        module_file = Path(
            getattr(module, "__file__", "")
        ).resolve()

        version = getattr(module, "__version__", None)

        if not version:
            try:
                version = metadata.version(
                    dependency["package"]
                )
            except Exception:
                version = "não informada"

        path_text = str(module_file).replace("\\", "/").lower()

        if "/qmd_image_explorer/vendor/" in path_text:
            origin = "QMD Tools Erolorer"
        elif "/plugins/qgis_stac/lib/" in path_text:
            origin = "STAC API Browser"
        elif "/site-packages/" in path_text:
            origin = "Ambiente Python"
        else:
            origin = "Outro"

        return True, str(version), origin

    @staticmethod
    def _is_importable(module_name):
        try:
            importlib.import_module(module_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _get_package_version(package_name):
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return "—"
        except Exception:
            return "?"


class DependencyCheckDialog(QDialog):
    """
    Janela de verificação das dependências do QMD Tools Erolorer.

    Apenas detecta e apresenta o status. Não instala pacotes.
    """

    def __init__(self, dependencies, parent=None):
        super().__init__(parent)

        self.dependencies = dependencies

        self.setWindowTitle("Verificar dependências")
        self.setMinimumWidth(620)
        self.setModal(True)

        self._setup_ui()
        self.verificar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Verificação de dependências")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.table = QTableWidget(
            len(self.dependencies),
            5,
        )

        self.table.setHorizontalHeaderLabels([
            "Pacote",
            "Versão",
            "Status",
            "Origem",
            "Utilizado por",
        ])

        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setWordWrap(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Close
        )

        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def verificar(self):
        ausentes = []

        for row, dependency in enumerate(self.dependencies):
            package = dependency["package"]
            modules = dependency["modules"]

            available, version, origin = SystemWidget._detect_dependency(
                dependency
            )

            self.table.setItem(
                row, 0, QTableWidgetItem(package)
            )

            version_item = QTableWidgetItem(
                version if available else "—"
            )
            version_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, version_item)

            status_item = QTableWidgetItem(
                "✓ Disponível" if available else "✕ Ausente"
            )
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, status_item)

            self.table.setItem(
                row, 3, QTableWidgetItem(origin)
            )

            self.table.setItem(
                row, 4, QTableWidgetItem("\n".join(modules))
            )

            if not available:
                ausentes.append(package)

        self.table.resizeRowsToContents()

    @staticmethod
    def _is_importable(module_name):
        try:
            importlib.import_module(module_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _get_package_version(package_name):
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return "—"
        except Exception:
            return "?"


class DependencyInstallDialog(QDialog):
    """
    Janela de instalação das dependências externas do QMD.

    A instalação somente é oferecida para bibliotecas externas
    controladas pelo QMD. pystac/pystac-client não entram aqui,
    pois atualmente são fornecidos pelo STAC API Browser.
    """

    INSTALLABLE = {
        "shapely": "shapely",
        "requests": "requests",
        "lxml": "lxml",
    }

    def __init__(self, dependencies, parent=None):
        super().__init__(parent)

        self.dependencies = dependencies
        self.missing = []
        self.process = None
        self.verification_process = None
        self.install_python = None

        self.setWindowTitle("Instalar dependências")
        self.setMinimumWidth(560)
        self.setModal(True)

        self._setup_ui()
        self._find_missing()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        title = QLabel("Instalar dependências")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.list_label = QLabel()
        self.list_label.setWordWrap(True)
        layout.addWidget(self.list_label)

        self.output = QLabel()
        self.output.setWordWrap(True)
        self.output.hide()
        layout.addWidget(self.output)

        self.button_box = QDialogButtonBox()

        self.yes_button = self.button_box.addButton(
            "Sim",
            QDialogButtonBox.AcceptRole,
        )
        self.no_button = self.button_box.addButton(
            "Não",
            QDialogButtonBox.RejectRole,
        )

        self.yes_button.clicked.connect(self._start_installation)
        self.no_button.clicked.connect(self.reject)

        layout.addWidget(self.button_box)

    def _find_missing(self):
        self.missing = []

        # Verificação real das dependências externas instaláveis.
        for dependency in self.dependencies:
            package = dependency["package"]
            import_name = dependency["import_name"]

            if package not in self.INSTALLABLE:
                continue

            try:
                importlib.import_module(import_name)
            except Exception:
                self.missing.append(package)

        if self.missing:
            python_exe = self._python_executable()

            self.message.setText(
                "Faltam instalar as seguintes bibliotecas de Python:"
            )

            self.list_label.setText(
                "<b>" + "<br>".join(
                    f"• {package}" for package in self.missing
                ) + "</b><br><br>"
                "Deseja instalá-las agora?<br><br>"
                f"<b>Python:</b> {python_exe}<br>"
                "<b>Destino:</b> ambiente do usuário"
            )

            self.yes_button.setEnabled(True)

        else:
            self.message.setText(
                "Todas as dependências externas instaláveis "
                "estão disponíveis."
            )

            self.list_label.setText(
                "Nenhuma instalação é necessária neste momento.<br><br>"
                "<b>pystac</b> e <b>pystac-client</b> não são "
                "alterados por esta janela, pois atualmente são "
                "fornecidos pelo STAC API Browser."
            )

            self.yes_button.setEnabled(False)
            self.no_button.setText("Fechar")

    def _python_executable(self):
        """
        Localiza um python.exe real na instalação do QGIS.

        sys.executable pode ser qgis-ltr-bin.exe no Windows.
        """
        current = Path(sys.executable)

        if current.name.lower() == "python.exe":
            return str(current)

        candidates = []

        # .../QGIS 3.40.6/bin/qgis-ltr-bin.exe
        # -> .../QGIS 3.40.6/apps/Python312/python.exe
        for parent in current.parents:
            apps_dir = parent / "apps"

            if apps_dir.exists():
                candidates.extend(
                    apps_dir.glob("Python*/python.exe")
                )

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return str(current)

    def _start_installation(self):
        if not self.missing:
            return

        python_exe = self._python_executable()

        # No Windows/QGIS, evitamos gravar em Program Files.
        # O pip --user instala no diretório de usuário.
        if not getattr(site, "ENABLE_USER_SITE", True):
            self.message.setText(
                "<b>Não foi possível iniciar a instalação.</b>"
            )

            self.list_label.setText(
                "O ambiente Python do QGIS está com a instalação "
                "no diretório do usuário desabilitada.<br><br>"
                "Por segurança, o QMD Tools Erolorer não tentará "
                "gravar diretamente em Program Files."
            )

            self.yes_button.setEnabled(False)
            self.no_button.setText("Fechar")
            return

        self.yes_button.setEnabled(False)
        self.no_button.setText("Fechar")

        self.message.setText(
            "Instalando as dependências..."
        )

        self.output.show()
        self.output.setText(
            f"<b>Python utilizado:</b><br>{python_exe}<br><br>"
            "<b>Destino:</b> ambiente do usuário<br><br>"
            "O QGIS poderá ficar temporariamente ocupado. "
            "Aguarde a conclusão."
        )

        self.process = QProcess(self)
        self.process.setProgram(python_exe)

        self.process.setArguments([
            "-m",
            "pip",
            "install",
            "--user",
            *self.missing,
        ])

        self.process.setProcessChannelMode(
            QProcess.MergedChannels
        )

        self.process.readyReadStandardOutput.connect(
            self._read_output
        )

        self.process.finished.connect(
            self._installation_finished
        )

        self.process.start()

        if not self.process.waitForStarted(3000):
            self.message.setText(
                "<b>Não foi possível iniciar o instalador.</b>"
            )

            self.list_label.setText(
                "O Python do QGIS não conseguiu iniciar o pip.<br><br>"
                f"<b>Python:</b> {python_exe}"
            )

            self.yes_button.setEnabled(False)
            self.no_button.setText("Fechar")
            self.process = None


    def _read_output(self):
        if not self.process:
            return

        data = self.process.readAllStandardOutput()

        output = bytes(data).decode(
            "utf-8",
            errors="replace",
        )

        self.output.setText(
            output[-5000:].replace("\n", "<br>")
        )

    def _installation_finished(self, exit_code, exit_status):
        if exit_status == QProcess.CrashExit or exit_code != 0:
            self.message.setText(
                "<b>Não foi possível concluir a instalação.</b>"
            )

            self.list_label.setText(
                "O pip retornou um erro durante a instalação.<br><br>"
                "Consulte a saída abaixo para verificar o problema."
            )

            self.yes_button.setEnabled(False)
            self.no_button.setText("Fechar")
            self.process = None
            return

        # O pip terminou com sucesso. Isso ainda não significa que
        # o QGIS esteja usando a biblioteca correta. Agora verificamos
        # cada pacote no Python que executou o pip.
        self.process = None
        self._start_post_install_verification()

    def _start_post_install_verification(self):
        python_exe = self.install_python or self._python_executable()

        self.message.setText(
            "<b>Instalação concluída. Verificando dependências...</b>"
        )

        self.list_label.setText(
            "A instalação foi concluída. Agora o QMD está verificando "
            "versão e localização das bibliotecas instaladas."
        )

        self.output.show()
        self.output.setText(
            f"<b>Python verificado:</b><br>{python_exe}<br><br>"
            "Aguarde a verificação..."
        )

        # O subprocesso usa o mesmo Python que executou o pip.
        # Isso evita confundir o resultado com uma cópia fornecida
        # por outro plugin dentro do processo do QGIS.
        packages = " ".join(
            package.replace('"', '\\"')
            for package in self.missing
        )

        script = r
    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(2000)
            self.process = None

        event.accept()


__all__ = ["SystemWidget"]
