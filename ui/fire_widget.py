# -*- coding: utf-8 -*-

from pathlib import Path
from datetime import datetime, timedelta

import csv
import os
import unicodedata
import tempfile
import requests
from lxml import etree

from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsFeature,
    QgsWkbTypes,
)

from qgis.PyQt.QtCore import (
    Qt,
    QDateTime,
    QStringListModel,
    QTimer,
)

from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QCompleter,
    QMessageBox,
    QGroupBox,
    QToolButton,
    QSizePolicy,
    QButtonGroup,
)

from qgis.utils import iface

from ..core.stac_core import log_message


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

WFS_URL = (
    "https://terrabrasilis.dpi.inpe.br/"
    "queimadas/geoserver/wfs"
)

PLUGIN_DIR = Path(__file__).resolve().parents[1]
UTILS_DIR = PLUGIN_DIR / "utils"
CONFIG_DIR = PLUGIN_DIR / "config"
MUNICIPIOS_CSV = CONFIG_DIR / "municipios.csv"

QML_PATH_TODOSSAT = UTILS_DIR / "estilo_focos_todosat_wfs.qml"
QML_PATH_SATREF = UTILS_DIR / "estilo_focos_satref_wfs.qml"


# =============================================================================
# LISTAS
# =============================================================================

SATELITES = [
    "AQUA_M-M",
    "AQUA_M-T",
    "GOES-19",
    "METOP-B",
    "METOP-C",
    "MSG-03",
    "NOAA-20",
    "NOAA-21",
    "NPP-375",
    "NPP-375D",
    "TERRA_M-M",
    "TERRA_M-T",
]

ESTADOS = [
    "ACRE", "ALAGOAS", "AMAPÁ", "AMAZONAS", "BAHIA", "CEARÁ",
    "DISTRITO FEDERAL", "ESPÍRITO SANTO", "GOIÁS", "MARANHÃO",
    "MATO GROSSO", "MATO GROSSO DO SUL", "MINAS GERAIS", "PARÁ",
    "PARAÍBA", "PARANÁ", "PERNAMBUCO", "PIAUÍ", "RIO DE JANEIRO",
    "RIO GRANDE DO NORTE", "RIO GRANDE DO SUL", "RONDÔNIA", "RORAIMA",
    "SANTA CATARINA", "SÃO PAULO", "SERGIPE", "TOCANTINS",
]

BIOMAS = [
    "Amazônia",
    "Caatinga",
    "Cerrado",
    "Mata Atlântica",
    "Pampa",
    "Pantanal",
]


class CollapsibleBox(QWidget):
    """Seção expansível/recolhível para manter a interface compacta."""

    def __init__(self, title, parent=None, expanded=False):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.button = QToolButton()
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.button.setStyleSheet(
            """
            QToolButton {
                font-weight: bold;
                text-align: left;
                padding: 6px;
                border: 1px solid #c8c8c8;
                border-radius: 3px;
            }
            QToolButton:hover { background-color: #f2f2f2; }
            QToolButton:checked { background-color: #f7f7f7; }
            """
        )
        self.button.toggled.connect(self._toggle_content)
        layout.addWidget(self.button)

        self.content = QWidget()
        self.content.setVisible(expanded)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 6, 8, 8)
        self.content_layout.setSpacing(6)
        layout.addWidget(self.content)

    def _toggle_content(self, checked):
        self._expanded = checked
        self.content.setVisible(checked)
        self.button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def setExpanded(self, expanded):
        self.button.setChecked(expanded)

    def isExpanded(self):
        return self._expanded


class FireWidget(QWidget):
    """
    Interface de consulta de focos.

    A camada WFS deixou de ser uma escolha do usuário. O widget descobre as
    camadas disponíveis no GetCapabilities e escolhe internamente a(s) camada(s)
    necessárias para atender ao período solicitado.
    """

    def __init__(self, parent=None, roi_manager=None):
        super().__init__(parent)
        self.roi_manager = roi_manager
        self._geometry_name_cache = {}
        self._camadas_wfs = []
        self._municipios_cache = {}
        self._municipios_por_estado = {}
        self._municipios_todos = []
        self._municipios_model = QStringListModel([], self)
        self._municipios_selecionando = False

        self._build_ui()

        if self.roi_manager is not None:
            self.roi_manager.roi_changed.connect(self._atualizar_status_roi)

        # O GetCapabilities do WFS não é consultado na inicialização.
        # A consulta será feita somente quando o usuário clicar em
        # "🔥 Buscar Focos". Isso evita que a abertura do plugin fique
        # bloqueada quando o serviço do INPE estiver lento ou indisponível.
        # Carrega a lista de municípios depois que a interface já foi criada.
        # Isso evita tentar acessar o WFS de municípios durante a construção
        # do widget, quando o provedor ainda pode não estar pronto.
        QTimer.singleShot(0, self._carregar_municipios_csv)
        self._definir_periodo_inicial()

    # =========================================================================
    # INTERFACE
    # =========================================================================

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ---------------------------------------------------------------------
        # PERÍODO / REGIÃO DE INTERESSE
        # ---------------------------------------------------------------------
        self.section_periodo = CollapsibleBox("Período", expanded=True)
        periodo_layout = self.section_periodo.content_layout

        # O intervalo fica acima dos atalhos para facilitar a leitura e
        # permitir que o usuário ajuste manualmente a consulta.
        date_layout = QHBoxLayout()
        self.data_min = QDateTimeEdit()
        self.data_min.setDisplayFormat("dd/MM/yyyy")
        self.data_min.setCalendarPopup(True)
        self.data_max = QDateTimeEdit()
        self.data_max.setDisplayFormat("dd/MM/yyyy")
        self.data_max.setCalendarPopup(True)
        date_layout.addWidget(self.data_min)
        date_layout.addWidget(self.data_max)
        periodo_layout.addLayout(date_layout)

        roi_layout = QHBoxLayout()
        roi_layout.setContentsMargins(0, 0, 0, 0)
        roi_layout.setSpacing(6)
        self.checkbox_usar_roi = QCheckBox("Usar Região de Interesse")
        self.label_roi = QLabel()
        self.label_roi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        roi_layout.addWidget(self.checkbox_usar_roi)
        roi_layout.addWidget(self.label_roi)
        periodo_layout.addLayout(roi_layout)

        botoes_layout1 = QHBoxLayout()
        botoes_layout2 = QHBoxLayout()
        self.btn_hoje = QPushButton("Hoje")
        self.btn_ontem = QPushButton("Ontem")
        self.btn_48h = QPushButton("48 h")
        self.btn_7dias = QPushButton("7 dias")
        self.btn_mes = QPushButton("Mês Atual")
        self.btn_ano = QPushButton("Ano Atual")
        self.btn_1ano = QPushButton("1 ano")

        # Os atalhos de período funcionam como uma seleção exclusiva:
        # apenas um preset pode ficar ativo por vez.
        self._grupo_presets_periodo = QButtonGroup(self)
        self._grupo_presets_periodo.setExclusive(True)
        for botao in (
            self.btn_hoje,
            self.btn_ontem,
            self.btn_48h,
            self.btn_7dias,
            self.btn_mes,
            self.btn_ano,
            self.btn_1ano,
        ):
            botao.setCheckable(True)
            botao.setFixedHeight(23)
            self._grupo_presets_periodo.addButton(botao)
            botao.setStyleSheet(
                """
                QPushButton:checked {
                    background-color: #d9eaf7;
                    border: 1px solid #4a90d9;
                    font-weight: bold;
                }
                """
            )

        # Se o usuário alterar manualmente qualquer uma das datas,
        # deixa de existir um preset ativo.
        self._alterando_periodo_preset = False
        self.data_min.dateChanged.connect(self._periodo_manual_alterado)
        self.data_max.dateChanged.connect(self._periodo_manual_alterado)

        botoes_layout1.addWidget(self.btn_hoje)
        botoes_layout1.addWidget(self.btn_ontem)
        botoes_layout1.addWidget(self.btn_48h)
        botoes_layout2.addWidget(self.btn_7dias)
        botoes_layout2.addWidget(self.btn_mes)
        botoes_layout2.addWidget(self.btn_ano)
        periodo_layout.addLayout(botoes_layout1)
        periodo_layout.addLayout(botoes_layout2)
        layout.addWidget(self.section_periodo)

        self.btn_hoje.clicked.connect(lambda: self._aplicar_preset("hoje"))
        self.btn_ontem.clicked.connect(lambda: self._aplicar_preset("ontem"))
        self.btn_48h.clicked.connect(lambda: self._aplicar_preset("48h"))
        self.btn_7dias.clicked.connect(lambda: self._aplicar_preset("7dias"))
        self.btn_mes.clicked.connect(lambda: self._aplicar_preset("mes"))
        self.btn_ano.clicked.connect(lambda: self._aplicar_preset("ano"))
        self.btn_1ano.clicked.connect(lambda: self._aplicar_preset("1ano"))

        # ---------------------------------------------------------------------
        # FILTROS BÁSICOS
        # ---------------------------------------------------------------------
        self.section_filtros = CollapsibleBox("Áreas de Interesse", expanded=False)
        filtros_layout = self.section_filtros.content_layout

        # Bioma e Estado ficam lado a lado para deixar a interface mais compacta.
        linha_bioma_estado = QHBoxLayout()
        col_bioma = QVBoxLayout()
        col_estado = QVBoxLayout()

        col_bioma.addWidget(QLabel("Bioma:"))
        self.combo_bioma = QComboBox()
        self.combo_bioma.addItem("Todos os Biomas")
        self.combo_bioma.addItems(BIOMAS)
        col_bioma.addWidget(self.combo_bioma)

        col_estado.addWidget(QLabel("Estado:"))
        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos os Estados")
        self.combo_estado.addItems(ESTADOS)
        self.combo_estado.currentIndexChanged.connect(self._estado_changed)
        col_estado.addWidget(self.combo_estado)

        linha_bioma_estado.addLayout(col_bioma)
        linha_bioma_estado.addLayout(col_estado)
        filtros_layout.addLayout(linha_bioma_estado)

        filtros_layout.addWidget(QLabel("Município:"))
        self.input_municipio = QLineEdit()
        self.input_municipio.setPlaceholderText("Digite um município")
        self.completer = QCompleter(self._municipios_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        # O filtro é feito manualmente em _filtrar_municipios_autocomplete,
        # permitindo ignorar acentos e maiúsculas/minúsculas.
        # O modo Unfiltered evita que o QCompleter aplique uma segunda
        # filtragem acentuada sobre os resultados já normalizados.
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setCompletionRole(Qt.DisplayRole)
        self.completer.activated[str].connect(self._municipio_selecionado)
        self.input_municipio.textChanged.connect(
            self._filtrar_municipios_autocomplete
        )
        self.input_municipio.setCompleter(self.completer)
        filtros_layout.addWidget(self.input_municipio)

        # layout.addWidget(self.section_filtros)

        # ---------------------------------------------------------------------
        # FILTROS AVANÇADOS
        # ---------------------------------------------------------------------
        self.section_avancados = CollapsibleBox("Parâmetros da Busca", expanded=True)
        avancados_layout = self.section_avancados.content_layout

        # AQUA_M-T é o padrão. O usuário só abre esta seção quando quiser
        # consultar todos os satélites ou selecionar satélites específicos.
        avancados_layout.addWidget(QLabel("Satélites:"))
        self.combo_modo_satelite = QComboBox()
        self.combo_modo_satelite.addItems([
            "AQUA_M-T (padrão)",
            "Todos os Satélites",
            "Selecionar Satélites",
        ])
        self.combo_modo_satelite.currentIndexChanged.connect(self.atualizar_filtro_satelite)
        avancados_layout.addWidget(self.combo_modo_satelite)

        self.list_satellites = QListWidget()
        self.list_satellites.setMaximumHeight(145)
        for sat in SATELITES:
            item = QListWidgetItem(sat)
            item.setCheckState(Qt.Unchecked)
            self.list_satellites.addItem(item)
        self.list_satellites.setEnabled(False)
        avancados_layout.addWidget(self.list_satellites)

        avancados_layout.addWidget(QLabel("Órbita/Ponto:"))
        self.input_wrs = QLineEdit()
        self.input_wrs.setPlaceholderText("Ex.: 223_067")
        self.input_wrs.setMaxLength(7)
        avancados_layout.addWidget(self.input_wrs)

        layout.addWidget(self.section_avancados)
        layout.addWidget(self.section_filtros)

        # ---------------------------------------------------------------------
        # BOTÃO
        # ---------------------------------------------------------------------
        self.btn_carregar = QPushButton("🔥 Buscar Focos")
        self.btn_carregar.clicked.connect(self.carregar_camada)
        self.btn_carregar.setStyleSheet(
            "font-weight: bold; font-size: 16px; padding: 8px;"
        )
        layout.addWidget(self.btn_carregar)
        layout.addStretch()

        self.atualizar_filtro_satelite()
        self._atualizar_status_roi()

    # =========================================================================
    # ROI
    # =========================================================================

    def _atualizar_status_roi(self, bbox=None):
        if bbox is None and self.roi_manager is not None:
            bbox = self.roi_manager.get_bbox()

        if bbox:
            self.checkbox_usar_roi.setEnabled(True)
            self.checkbox_usar_roi.setChecked(True)
            self.label_roi.setText("✓ BBox disponível")
            self.label_roi.setStyleSheet("color: #176b2c; font-weight: bold;")
            self.label_roi.setToolTip(
                "Região de Interesse:\n"
                f"[{bbox[0]:.6f}, {bbox[1]:.6f}, "
                f"{bbox[2]:.6f}, {bbox[3]:.6f}]"
            )
        else:
            self.checkbox_usar_roi.setChecked(False)
            self.checkbox_usar_roi.setEnabled(False)
            self.label_roi.setText("Nenhuma ROI")
            self.label_roi.setStyleSheet("color: #777777;")
            self.label_roi.setToolTip("Capture uma Região de Interesse na aba Busca.")

    # =========================================================================
    # PERÍODO
    # =========================================================================

    def _definir_periodo_inicial(self):
        self._aplicar_preset("48h")

    def _aplicar_preset(self, preset):
        agora = datetime.now()

        if preset == "hoje":
            inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        elif preset == "ontem":
            inicio = (agora - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            agora = inicio.replace(hour=23, minute=59, second=59)
        elif preset == "48h":
            inicio = agora - timedelta(hours=48)
        elif preset == "7dias":
            inicio = (agora - timedelta(days=7)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif preset == "mes":
            inicio = agora.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        elif preset == "ano":
            inicio = agora.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            return

        # A interface trabalha somente com datas: toda consulta começa
        # às 00:00:00 e termina às 23:59:59 do dia final.
        inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
        fim = agora.replace(hour=23, minute=59, second=59, microsecond=0)

        # As alterações programáticas das datas não devem ser interpretadas
        # como edição manual do período.
        self._alterando_periodo_preset = True
        try:
            self.data_min.setDateTime(QDateTime(inicio))
            self.data_max.setDateTime(QDateTime(fim))
        finally:
            self._alterando_periodo_preset = False

        # Deixa visualmente ativo o preset que originou o intervalo.
        botoes_preset = {
            "hoje": self.btn_hoje,
            "ontem": self.btn_ontem,
            "48h": self.btn_48h,
            "7dias": self.btn_7dias,
            "mes": self.btn_mes,
            "ano": self.btn_ano,
            "1ano": self.btn_1ano,
        }
        botao = botoes_preset.get(preset)
        if botao is not None:
            botao.setChecked(True)

    def _periodo_manual_alterado(self, _data):
        """Remove o destaque do preset quando a data é alterada manualmente."""
        if self._alterando_periodo_preset:
            return

        self._grupo_presets_periodo.setExclusive(False)
        for botao in self._grupo_presets_periodo.buttons():
            botao.setChecked(False)
        self._grupo_presets_periodo.setExclusive(True)

    def _validar_periodo(self):
        # Normaliza os limites independentemente do horário interno do widget.
        inicio = self.data_min.dateTime().toPyDateTime().replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        fim = self.data_max.dateTime().toPyDateTime().replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=None
        )

        # Mantém os campos internos sincronizados com os limites da consulta.
        self.data_min.setDateTime(QDateTime(inicio))
        self.data_max.setDateTime(QDateTime(fim))

        if inicio > fim:
            QMessageBox.warning(
                self, "Período inválido", "A data inicial deve ser anterior à data final."
            )
            return None

        if fim - inicio > timedelta(days=365):
            QMessageBox.warning(
                self,
                "Período máximo",
                "O período máximo permitido para uma consulta é de 1 ano.",
            )
            return None

        return inicio, fim

    # =========================================================================
    # WFS / CAPABILITIES
    # =========================================================================

    def carregar_camadas_wfs(self):
        self._camadas_wfs = []
        try:
            response = requests.get(
                WFS_URL,
                params={
                    "service": "WFS",
                    "version": "1.1.0",
                    "request": "GetCapabilities",
                },
                timeout=30,
            )
            response.raise_for_status()
            root = etree.fromstring(response.content)
            features = root.xpath(
                "//wfs:FeatureType/wfs:Name",
                namespaces={"wfs": "http://www.opengis.net/wfs"},
            )

            for feature in features:
                nome = (feature.text or "").strip()
                if nome.startswith("dados_abertos:focos"):
                    self._camadas_wfs.append(nome)

            self._camadas_wfs = sorted(set(self._camadas_wfs))
            log_message(
                f"[FOCOS] GetCapabilities: {len(self._camadas_wfs)} camadas de focos encontradas."
            )
            for camada in self._camadas_wfs:
                log_message(f"[FOCOS] Camada disponível: {camada}")

            self._preencher_wrs()

        except Exception as error:
            log_message(f"[FOCOS] Erro ao acessar WFS: {error}")
            self._camadas_wfs = []

    def _camadas_por_tipo(self, satref=False):
        sufixo = "_satref" if satref else "_todosats"
        return [c for c in self._camadas_wfs if c.lower().endswith(sufixo)]

    def _camada_com_padrao(self, padrao, satref=False):
        candidatos = self._camadas_por_tipo(satref=satref)
        padrao = padrao.lower()
        for camada in candidatos:
            if padrao in camada.lower():
                return camada
        return None

    def _camada_anual(self, ano, satref=False):
        # Para o ano corrente o serviço não cria "focos_2026..."; a camada
        # equivalente é "focos_ano_atual...". Isso também é usado em consultas
        # de 7 dias ou intervalos personalizados que estejam no ano corrente.
        if ano == datetime.now().year:
            return self._camada_com_padrao("focos_ano_atual_br", satref=satref)

        candidatos = self._camadas_por_tipo(satref=satref)
        encontrados = [c for c in candidatos if str(ano) in c]

        # Evita confundir uma camada de período corrente com a camada anual.
        encontrados = [
            c for c in encontrados
            if all(x not in c.lower() for x in ("48h", "hoje", "mesatual", "ano_atual"))
        ]

        if encontrados:
            return sorted(encontrados)[0]
        return None

    def _camadas_para_periodo(self, inicio, fim, modo_satelite=0):
        # AQUA_M-T usa as camadas *_satref. Todos os satélites e seleções
        # específicas usam as camadas *_todosats.
        satref = modo_satelite == 0

        resultado = []
        agora = datetime.now()

        hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ano_inicio = agora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # Atalhos internos: usam as camadas pequenas e atuais somente quando
        # o intervalo realmente corresponde ao período natural da camada.
        # Uma janela histórica de 48 h, por exemplo 08/09/2026 -> 09/09/2026,
        # NÃO pode usar focos_48h_br, pois essa camada contém somente as últimas
        # 48 h contadas a partir de agora. Nesse caso usamos a camada anual atual.
        if inicio == hoje_inicio and fim <= agora:
            camada = self._camada_com_padrao("focos_hoje_br", satref=satref)
            if camada:
                return [camada]

        inicio_48h_atual = agora - timedelta(hours=48)
        if (
            abs((inicio - inicio_48h_atual).total_seconds()) <= 120
            and abs((fim - agora).total_seconds()) <= 120
        ):
            camada = self._camada_com_padrao("focos_48h_br", satref=satref)
            if camada:
                return [camada]

        if inicio == mes_inicio and fim <= agora:
            camada = self._camada_com_padrao("focos_mesatual_br", satref=satref)
            if camada:
                return [camada]

        if inicio == ano_inicio and fim <= agora:
            camada = self._camada_com_padrao("focos_ano_atual_br", satref=satref)
            if camada:
                return [camada]

        # Consulta histórica/customizada: uma camada anual por ano envolvido.
        ano_atual = inicio.year
        while ano_atual <= fim.year:
            camada = self._camada_anual(ano_atual, satref=satref)
            if camada:
                resultado.append(camada)
            ano_atual += 1

        return resultado

    def _preencher_wrs(self):
        # O WRS agora é informado diretamente pelo usuário.
        # Ex.: 223_067
        return

    # =========================================================================
    # MUNICÍPIOS
    # =========================================================================

    @staticmethod
    def _normalizar_texto(texto):
        texto = "" if texto is None else str(texto)
        return "".join(
            caractere
            for caractere in unicodedata.normalize("NFD", texto)
            if unicodedata.category(caractere) != "Mn"
        ).casefold()

    def _carregar_municipios_csv(self):
        """Carrega a lista local; se ainda não existir, cria a partir do WFS."""
        municipios = []
        por_estado = {}

        if MUNICIPIOS_CSV.exists():
            try:
                with MUNICIPIOS_CSV.open("r", encoding="utf-8-sig", newline="") as arquivo:
                    leitor = csv.DictReader(arquivo)
                    for linha in leitor:
                        municipio = (linha.get("municipio") or "").strip()
                        estado = (linha.get("estado") or "").strip()
                        if not municipio or not estado:
                            continue
                        municipios.append(municipio)
                        por_estado.setdefault(estado, []).append(municipio)
            except Exception as exc:
                log_message(f"[FOCOS] Erro ao ler {MUNICIPIOS_CSV.name}: {exc}")

        # Se o CSV ainda não foi populado, consulta uma única vez a camada de
        # municípios do próprio serviço de focos e salva os nomes localmente.
        if len(municipios) < 1000:
            gerados = self._gerar_municipios_csv_wfs()
            if gerados:
                municipios, por_estado = gerados

        self._municipios_todos = sorted(set(municipios), key=self._normalizar_texto)
        self._municipios_por_estado = {
            estado: sorted(set(valores), key=self._normalizar_texto)
            for estado, valores in por_estado.items()
        }
        self._atualizar_modelo_municipios(self._municipios_todos)
        log_message(
            f"[FOCOS] Municípios disponíveis no autocomplete: {len(self._municipios_todos)}"
        )

    def _gerar_municipios_csv_wfs(self):
        """Obtém município/estado diretamente do WFS e cria o CSV local."""
        try:
            params = {
                "service": "WFS",
                "version": "1.1.0",
                "request": "GetFeature",
                "typeName": "bdqueimadas:municipios",
                "srsname": "EPSG:4326",
                "outputFormat": "application/json",
            }
            resposta = requests.get(WFS_URL, params=params, timeout=60)
            resposta.raise_for_status()
            dados = resposta.json()

            pares = set()
            for feature in dados.get("features", []):
                props = feature.get("properties", {}) or {}
                campos = {str(k).lower(): k for k in props.keys()}
                campo_municipio = campos.get("nome") or campos.get("municipio")
                campo_estado = campos.get("estado")
                if not campo_municipio or not campo_estado:
                    continue
                municipio = props.get(campo_municipio)
                estado = props.get(campo_estado)
                if municipio and estado:
                    pares.add((str(municipio).strip(), str(estado).strip()))

            if not pares:
                log_message(
                    "[FOCOS] O WFS de municípios não retornou registros com "
                    "os campos esperados nome/municipio e estado."
                )
                return None

            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with MUNICIPIOS_CSV.open("w", encoding="utf-8-sig", newline="") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=["municipio", "estado"])
                escritor.writeheader()
                for municipio, estado in sorted(
                    pares,
                    key=lambda item: (
                        self._normalizar_texto(item[1]),
                        self._normalizar_texto(item[0]),
                    ),
                ):
                    escritor.writerow({"municipio": municipio, "estado": estado})

            por_estado = {}
            municipios = []
            for municipio, estado in pares:
                municipios.append(municipio)
                por_estado.setdefault(estado, []).append(municipio)

            log_message(
                f"[FOCOS] {len(pares)} municípios gravados em {MUNICIPIOS_CSV.name}."
            )
            return municipios, por_estado

        except Exception as exc:
            log_message(f"[FOCOS] Erro ao gerar {MUNICIPIOS_CSV.name}: {exc}")
            return None

    def _municipios_do_estado(self, estado):
        """Retorna os municípios do estado ignorando maiúsculas e acentos."""
        estado_normalizado = self._normalizar_texto(estado)
        if not estado_normalizado or estado_normalizado == self._normalizar_texto("Todos os Estados"):
            return self._municipios_todos

        for nome_estado, municipios in self._municipios_por_estado.items():
            if self._normalizar_texto(nome_estado) == estado_normalizado:
                return municipios

        return []

    def _atualizar_modelo_municipios(self, municipios):
        """Atualiza a lista exibida pelo autocomplete."""
        lista = sorted(
            set(str(m).strip() for m in municipios if str(m).strip()),
            key=self._normalizar_texto,
        )
        self._municipios_model.setStringList(lista)

    def _filtrar_municipios_autocomplete(self, texto):
        """Filtra o autocomplete ignorando maiúsculas e acentos."""
        if self._municipios_selecionando:
            return

        consulta = self._normalizar_texto(texto)
        estado = self.combo_estado.currentText().strip()

        candidatos = self._municipios_do_estado(estado)

        if not consulta:
            self._atualizar_modelo_municipios(candidatos)
            self.completer.popup().hide()
            return

        encontrados = [
            municipio
            for municipio in candidatos
            if consulta in self._normalizar_texto(municipio)
        ]

        self._atualizar_modelo_municipios(encontrados)

        if encontrados:
            # O modelo já foi filtrado de forma acentuacao-insensitive.
            # Prefixo vazio faz o QCompleter mostrar todos os resultados
            # filtrados sem aplicar uma segunda comparação sobre os acentos.
            self.completer.setCompletionPrefix("")
            self.completer.complete()
        else:
            self.completer.popup().hide()

    def _municipio_selecionado(self, municipio):
        """Coloca no campo o nome canônico exatamente como no banco."""
        self._municipios_selecionando = True
        try:
            self.input_municipio.setText(str(municipio))
        finally:
            self._municipios_selecionando = False
        self.completer.popup().hide()

    def _estado_changed(self):
        estado = self.combo_estado.currentText().strip()
        municipios = self._municipios_do_estado(estado)

        self._atualizar_modelo_municipios(municipios)
        self.input_municipio.clear()

    def obter_municipios_por_estado(self, estados):
        """Compatibilidade com versões anteriores; agora a fonte é o CSV local."""
        if not estados:
            return self._municipios_todos
        resultado = []
        for estado in estados:
            resultado.extend(self._municipios_por_estado.get(estado, []))
        return sorted(set(resultado), key=self._normalizar_texto)

    def _municipio_canonico(self):
        """Retorna o nome exatamente como está no CSV/banco.

        Permite que o usuário digite sem se preocupar com maiúsculas ou
        acentos, por exemplo 'altamira', enquanto a consulta usa 'ALTAMIRA'.
        Quando o Estado está selecionado, a busca prioriza os municípios
        daquele estado.
        """
        texto = self.input_municipio.text().strip()
        if not texto:
            return ""

        normalizado = self._normalizar_texto(texto)
        estado = self.combo_estado.currentText().strip()

        candidatos = self._municipios_do_estado(estado)

        for municipio in candidatos:
            if self._normalizar_texto(municipio) == normalizado:
                return municipio

        return texto

    # =========================================================================
    # FILTROS
    # =========================================================================

    def atualizar_filtro_satelite(self):
        modo = self.combo_modo_satelite.currentIndex()
        self.list_satellites.setEnabled(modo == 2)

    def _atualizar_wrs(self):
        # Mantido por compatibilidade com versões anteriores.
        # O filtro agora é feito diretamente pelo campo de texto.
        return

    def _modo_satelite(self):
        # 0 = AQUA_M-T (camada satref), 1 = todos, 2 = seleção específica.
        return self.combo_modo_satelite.currentIndex()

    def _obter_satelites_selecionados(self):
        if self._modo_satelite() != 2:
            return []
        return [
            self.list_satellites.item(i).text()
            for i in range(self.list_satellites.count())
            if self.list_satellites.item(i).checkState() == Qt.Checked
        ]

    # =========================================================================
    # FILTROS / CQL
    # =========================================================================

    @staticmethod
    def _escapar(valor):
        return str(valor).replace("'", "''")

    def _montar_cql(self, inicio, fim, satelites):
        partes = [
            "data_hora_gmt >= '" + inicio.strftime("%Y-%m-%dT%H:%M:%S.000") + "'",
            "data_hora_gmt <= '" + fim.strftime("%Y-%m-%dT%H:%M:%S.000") + "'",
        ]

        if satelites:
            sat_str = ", ".join(f"'{self._escapar(s)}'" for s in satelites)
            partes.append(f"satelite IN ({sat_str})")

        bioma = self.combo_bioma.currentText().strip()
        if bioma and bioma != "Todos os Biomas":
            partes.append(f"bioma = '{self._escapar(bioma)}'")

        estado = self.combo_estado.currentText().strip()
        if estado and estado != "Todos os Estados":
            partes.append(f"estado = '{self._escapar(estado)}'")

        municipio = self._municipio_canonico()
        if municipio:
            partes.append(f"municipio = '{self._escapar(municipio)}'")

        wrs = self.input_wrs.text().strip()
        if wrs:
            partes.append(f"grade_wrs = '{self._escapar(wrs)}'")

        return " AND ".join(partes)

    # =========================================================================
    # ROI: CONSULTA DIRETA COM BBOX
    # =========================================================================

    def _baixar_camada_bbox(self, camada, bbox):
        minx, miny, maxx, maxy = bbox
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": camada,
            "srsname": "EPSG:4326",
            "bbox": f"{minx},{miny},{maxx},{maxy},EPSG:4326",
            "outputFormat": "application/json",
        }

        resposta = requests.get(WFS_URL, params=params, timeout=60)
        resposta.raise_for_status()

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".geojson", delete=False) as arquivo:
            arquivo.write(resposta.content)
            caminho = arquivo.name

        layer = QgsVectorLayer(caminho, "Focos ROI", "ogr")
        if not layer.isValid():
            try:
                os.remove(caminho)
            except OSError:
                pass
            raise RuntimeError("O GeoJSON retornado pelo WFS não pôde ser carregado pelo QGIS.")

        return layer, caminho

    # =========================================================================
    # FILTRAGEM LOCAL
    # =========================================================================

    @staticmethod
    def _datetime_atributo(valor):
        if isinstance(valor, datetime):
            return valor.replace(tzinfo=None)
        if isinstance(valor, QDateTime):
            return valor.toPyDateTime().replace(tzinfo=None)
        if valor is None:
            return None

        texto = str(valor).strip().replace("Z", "")
        for formato in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(texto, formato)
            except ValueError:
                pass
        return None

    @staticmethod
    def _texto_feature(feature, nome):
        try:
            valor = feature[nome]
        except Exception:
            return ""
        return "" if valor is None else str(valor).strip()

    def _filtrar_features(self, layer, inicio, fim, satelites):
        bioma = self.combo_bioma.currentText().strip()
        if bioma == "Todos os Biomas":
            bioma = ""

        estado = self.combo_estado.currentText().strip()
        if estado == "Todos os Estados":
            estado = ""

        municipio = self._municipio_canonico()
        wrs = self.input_wrs.text().strip()

        resultado = []
        for feature in layer.getFeatures():
            data = self._datetime_atributo(feature["data_hora_gmt"])
            if data is None or data < inicio or data > fim:
                continue
            if satelites and self._texto_feature(feature, "satelite") not in satelites:
                continue
            if bioma and self._texto_feature(feature, "bioma") != bioma:
                continue
            if estado and self._texto_feature(feature, "estado") != estado:
                continue
            if municipio and self._texto_feature(feature, "municipio") != municipio:
                continue
            if wrs and self._texto_feature(feature, "grade_wrs") != wrs:
                continue
            resultado.append(feature)
        return resultado

    # =========================================================================
    # CRIAÇÃO DA CAMADA FINAL
    # =========================================================================

    def _criar_memoria(self, features, referencia_layer, nome):
        tipo_geom = QgsWkbTypes.displayString(referencia_layer.wkbType())
        crs_authid = referencia_layer.crs().authid() or "EPSG:4326"
        camada = QgsVectorLayer(
            f"{tipo_geom}?crs={crs_authid}", nome, "memory"
        )
        camada.dataProvider().addAttributes(referencia_layer.fields())
        camada.updateFields()

        novos = []
        for feature in features:
            nova = QgsFeature(camada.fields())
            nova.setGeometry(feature.geometry())
            nova.setAttributes(feature.attributes())
            novos.append(nova)

        if novos:
            camada.dataProvider().addFeatures(novos)
        camada.updateExtents()
        return camada

    def _aplicar_estilo(self, camada, usar_todosats=True):
        qml_path = QML_PATH_TODOSSAT if usar_todosats else QML_PATH_SATREF
        if not qml_path.exists():
            log_message(f"[FOCOS] Arquivo de estilo não encontrado: {qml_path}")
            return
        sucesso, mensagem = camada.loadNamedStyle(str(qml_path))
        if sucesso:
            camada.triggerRepaint()
            log_message(f"[FOCOS] Estilo aplicado: {qml_path.name}")
        else:
            log_message(f"[FOCOS] Erro ao aplicar estilo: {mensagem}")

    # =========================================================================
    # CONSULTA PRINCIPAL
    # =========================================================================

    def carregar_camada(self):
        periodo = self._validar_periodo()
        if not periodo:
            return
        inicio, fim = periodo

        # Atualiza capabilities para trabalhar sempre com a estrutura atual do
        # GeoServer. Assim o usuário nunca precisa conhecer os nomes das camadas.
        self.carregar_camadas_wfs()
        if not self._camadas_wfs:
            QMessageBox.warning(
                self,
                "WFS",
                "Não foi possível obter as camadas de focos disponíveis no serviço.",
            )
            return

        usa_roi = (
            self.checkbox_usar_roi.isChecked()
            and self.roi_manager is not None
            and self.roi_manager.get_bbox()
        )
        if self.checkbox_usar_roi.isChecked() and not usa_roi:
            QMessageBox.warning(
                self,
                "Região de Interesse",
                "Não existe uma Região de Interesse disponível.",
            )
            return

        modo_satelite = self._modo_satelite()
        satelites = self._obter_satelites_selecionados()
        if modo_satelite == 2 and not satelites:
            QMessageBox.warning(
                self,
                "Satélites",
                "Selecione pelo menos um satélite em Filtros avançados.",
            )
            return
        usar_todosats = modo_satelite != 0

        camadas = self._camadas_para_periodo(
            inicio, fim, modo_satelite=modo_satelite
        )

        if not camadas:
            QMessageBox.warning(
                self,
                "Camadas de focos",
                "Não foi encontrada uma camada WFS compatível com todos os anos do período informado.\n\n"
                "O serviço precisa disponibilizar uma camada anual para cada ano consultado.",
            )
            return

        # Se houver anos sem camada, interrompe a consulta para não entregar um
        # resultado incompleto.
        anos_necessarios = set(range(inicio.year, fim.year + 1))
        ano_corrente = datetime.now().year
        anos_encontrados = set()
        for camada in camadas:
            nome = camada.lower()
            if any(x in nome for x in ("48h", "hoje", "mesatual", "ano_atual")):
                # As camadas de período corrente representam o ano corrente;
                # o nome não contém "2026", por exemplo.
                anos_encontrados.add(ano_corrente)
            else:
                for ano in anos_necessarios:
                    if str(ano) in nome:
                        anos_encontrados.add(ano)

        if anos_encontrados != anos_necessarios:
            faltantes = ", ".join(
                str(a) for a in sorted(anos_necessarios - anos_encontrados)
            )
            QMessageBox.warning(
                self,
                "Camada anual ausente",
                f"Não foi possível localizar a camada de focos para: {faltantes}.",
            )
            return

        log_message("\n========================================")
        log_message("[FOCOS] Nova consulta de Focos")
        log_message(
            f"[FOCOS] Período: {inicio:%d/%m/%Y %H:%M:%S} → {fim:%d/%m/%Y %H:%M:%S}"
        )
        log_message(f"[FOCOS] Região de Interesse: {'Sim' if usa_roi else 'Não'}")
        log_message(f"[FOCOS] Camadas internas: {', '.join(camadas)}")
        log_message(
            f"[FOCOS] Bioma: {self.combo_bioma.currentText()}"
        )
        log_message(
            f"[FOCOS] Estado: {self.combo_estado.currentText()}"
        )
        log_message(
            f"[FOCOS] Município: {self._municipio_canonico() or 'Todos'}"
        )
        descricao_sat = (
            "AQUA_M-T (padrão)" if modo_satelite == 0
            else "Todos os Satélites" if modo_satelite == 1
            else ", ".join(satelites)
        )
        log_message(f"[FOCOS] Satélites: {descricao_sat}")
        log_message(
            f"[FOCOS] Órbita/Ponto: {self.input_wrs.text().strip() or 'Todos'}"
        )

        bbox = self.roi_manager.get_bbox() if usa_roi else None
        todos_features = []
        referencia = None
        arquivos_temp = []

        try:
            for camada in camadas:
                log_message(f"[FOCOS] Consultando camada interna: {camada}")

                if bbox:
                    layer, arquivo_temp = self._baixar_camada_bbox(camada, bbox)
                    arquivos_temp.append(arquivo_temp)
                    features = self._filtrar_features(
                        layer, inicio, fim, satelites
                    )
                    log_message(
                        f"[FOCOS] {camada}: {layer.featureCount()} feições no BBOX; "
                        f"{len(features)} após filtros."
                    )
                else:
                    cql = self._montar_cql(inicio, fim, satelites)
                    uri = (
                        f"{WFS_URL}?service=WFS&version=1.1.0&request=GetFeature"
                        f"&typeName={camada}&CQL_FILTER={cql}&srsname=EPSG:4326"
                    )
                    layer = QgsVectorLayer(uri, "Temp_Focos", "WFS")
                    if not layer.isValid():
                        raise RuntimeError(f"Não foi possível carregar a camada WFS: {camada}")
                    features = list(layer.getFeatures())
                    log_message(
                        f"[FOCOS] {camada}: {len(features)} feições recebidas após filtros do WFS."
                    )

                if referencia is None:
                    referencia = layer
                todos_features.extend(features)

        except Exception as erro:
            log_message(f"[FOCOS] Erro na consulta: {erro}")
            QMessageBox.warning(
                self,
                "Erro na consulta de Focos",
                f"Não foi possível concluir a consulta.\n\nDetalhes: {erro}",
            )
            for caminho in arquivos_temp:
                try:
                    os.remove(caminho)
                except OSError:
                    pass
            return

        if referencia is None:
            QMessageBox.information(
                self, "Focos", "Nenhum foco encontrado para os filtros selecionados."
            )
            return

        # Remove duplicidades quando a divisão interna produzir sobreposição.
        vistos = set()
        features_unicas = []
        for feature in todos_features:
            try:
                fid = str(feature["id"])
            except Exception:
                fid = ""
            if not fid:
                fid = (
                    f"{self._texto_feature(feature, 'data_hora_gmt')}|"
                    f"{self._texto_feature(feature, 'latitude')}|"
                    f"{self._texto_feature(feature, 'longitude')}|"
                    f"{self._texto_feature(feature, 'satelite')}"
                )
            if fid in vistos:
                continue
            vistos.add(fid)
            features_unicas.append(feature)

        nome = (
            f"Focos da Consulta - {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
        )
        camada_final = self._criar_memoria(features_unicas, referencia, nome)
        self._aplicar_estilo(camada_final, usar_todosats=usar_todosats)

        projeto = QgsProject.instance()
        root = projeto.layerTreeRoot()
        projeto.addMapLayer(camada_final, False)
        root.insertLayer(0, camada_final)

        for caminho in arquivos_temp:
            try:
                os.remove(caminho)
            except OSError:
                pass

        log_message(
            f"[FOCOS] Total final: {len(features_unicas)} feições."
        )
        log_message(
            f"[FOCOS] Camada '{nome}' carregada com sucesso."
        )

        # Os campos de filtro textual são usados apenas para a consulta atual.
        # Após concluir a busca, limpamos os campos para que a próxima consulta
        # não fique inadvertidamente restrita ao mesmo município ou WRS.
        self.input_wrs.clear()
        self.input_municipio.clear()

        # Limpa os filtros de área após concluir a consulta.
        # A busca já foi executada com os valores selecionados; a próxima
        # consulta começa novamente sem restrição de bioma ou estado.
        self.combo_bioma.setCurrentIndex(0)
        self.combo_estado.setCurrentIndex(0)

        iface.setActiveLayer(camada_final)
        QTimer.singleShot(
            1000,
            lambda: (
                iface.setActiveLayer(camada_final),
                iface.actionZoomToLayer().trigger(),
            ),
        )
