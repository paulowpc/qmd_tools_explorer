# -*- coding: utf-8 -*-

from pathlib import Path
import json
import urllib.request
import shutil
import tempfile
import os
from urllib.parse import quote

from ..scripts import avisos_inmet_qgis

from qgis.PyQt.QtCore import Qt, QVariant, QUrl, QDate
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtGui import QIcon

from qgis.PyQt.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QSizePolicy,
    QMessageBox,
    QScrollArea,
    QAbstractScrollArea,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QLabel,
)

from qgis.utils import iface

from qgis.core import (
    QgsApplication,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsRectangle,
    QgsFeatureRequest,
    QgsGeometry,
    QgsJsonUtils,
    QgsWkbTypes,
    QgsTask,
    QgsNetworkAccessManager,
    QgsField,
    QgsFeature,
)

from ..core.stac_core import log_message


class LayersWidget(QWidget):

    def __init__(self, parent=None, roi_manager=None):

        super().__init__(parent)

        # Usa o mesmo gerenciador de ROI/BBOX da busca de imagens e focos.
        # O plugin pode passar explicitamente o roi_manager. Se não passar,
        # _get_shared_roi_manager() tenta encontrá-lo na cadeia de pais.
        self.roi_manager = roi_manager

        self.setMinimumSize(0, 0)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self._build_ui()


    # ==========================================================
    # SEÇÕES RECOLHÍVEIS
    # ==========================================================

    def _create_collapsible_section(
        self,
        title,
        content_widget,
        expanded=False,
    ):

        section = QWidget()

        section_layout = QVBoxLayout(
            section
        )

        section_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        section_layout.setSpacing(
            2
        )

        toggle = QToolButton()

        toggle.setText(
            title
        )

        toggle.setCheckable(
            True
        )

        toggle.setChecked(
            expanded
        )

        toggle.setArrowType(
            Qt.DownArrow
            if expanded
            else Qt.RightArrow
        )

        toggle.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )

        toggle.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        toggle.setMinimumHeight(
            34
        )

        toggle.setStyleSheet(
            '''
            QToolButton {
                border: 1px solid #c8c8c8;
                border-radius: 3px;
                background: transparent;
                padding: 6px 8px;
                font-weight: bold;
                text-align: left;
            }

            QToolButton:hover {
                background: #f2f2f2;
            }
            '''
        )

        content_widget.setVisible(
            expanded
        )

        section_layout.addWidget(
            toggle
        )

        section_layout.addWidget(
            content_widget
        )

        def toggle_section(checked):

            content_widget.setVisible(
                checked
            )

            toggle.setArrowType(
                Qt.DownArrow
                if checked
                else Qt.RightArrow
            )

        toggle.toggled.connect(
            toggle_section
        )

        return section


    # ==========================================================
    # INTERFACE
    # ==========================================================

    def _build_ui(self):

        outer_layout = QVBoxLayout(
            self
        )

        outer_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        outer_layout.setSpacing(
            0
        )

        scroll = QScrollArea()

        scroll.setMinimumSize(
            0,
            0,
        )

        scroll.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        scroll.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustIgnored
        )

        scroll.setWidgetResizable(
            True
        )

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        content_widget = QWidget()

        content_widget.setMinimumSize(
            0,
            0,
        )

        content_widget.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        layout = QVBoxLayout(
            content_widget
        )

        layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        layout.setSpacing(
            6
        )

        outer_layout.addWidget(
            scroll
        )

        # Associa o conteúdo ao QScrollArea.
        # Sem isso a aba Camadas fica vazia.
        scroll.setWidget(
            content_widget
        )

        # ======================================================
        # BASEMAPS
        # ======================================================

        basemaps_content = QWidget()
        basemaps_layout = QVBoxLayout(basemaps_content)
        basemaps_layout.setContentsMargins(6, 4, 6, 4)
        basemaps_layout.setSpacing(4)
        basemaps_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        basemap_buttons = [
            ("osm_btn", "OSM", "osm.svg", "osm"),
            ("google_satellite_btn", "Google Satélite", "basemap.svg", "google_satellite"),
            ("google_hybrid_btn", "Google Hybrid", "basemap.svg", "google_hybrid"),
            ("esri_satellite_btn", "ESRI Satélite", "basemap.svg", "esri_satellite"),
            ("esri_shaded_relief_btn", "ESRI Shaded Relief", "basemap.svg", "esri_shaded_relief"),
        ]

        basemap_row = None  # 3 botões por linha
        for index, (attr_name, label, icon_name, layer_key) in enumerate(basemap_buttons):
            if index % 3 == 0:
                basemap_row = QHBoxLayout()
                basemap_row.setContentsMargins(0, 0, 0, 0)
                basemap_row.setSpacing(4)
                basemap_row.setAlignment(Qt.AlignLeft)
                basemaps_layout.addLayout(basemap_row)

            button = QToolButton()
            button.setText(label)
            button.setToolTip(f"Carregar {label}")
            button.setIcon(self._custom_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setMinimumHeight(28)
            setattr(self, attr_name, button)
            basemap_row.addWidget(button)
            button.clicked.connect(
                lambda checked=False, layer_key=layer_key: self.load_xyz_basemap(layer_key)
            )

        if basemap_row is not None:
            basemap_row.addStretch()

        basemaps_section = self._create_collapsible_section(
            "Basemaps",
            basemaps_content,
            expanded=False,
        )
        # layout.addWidget(basemaps_section)

        # ======================================================
        # LIMITES POLÍTICOS
        # ======================================================

        limites_content = QWidget()
        limites_layout = QVBoxLayout(limites_content)
        limites_layout.setContentsMargins(6, 4, 6, 4)
        limites_layout.setSpacing(4)
        limites_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        limites_buttons = [
            ("paises_ams_btn", "Países AMS", "state.svg", "paises_ams"),
            ("biomas_btn", "Biomas", "biome.svg", "biomas"),
            ("estados_btn", "Estados", "state.svg", "estados"),
            ("municipios_btn", "Municípios", "state.svg", "municipios"),
            ("amz_legal_btn", "AMZ Legal", "amazon.svg", "amz_legal"),
        ]

        limites_row = None  # 3 botões por linha
        for index, (attr_name, label, icon_name, layer_key) in enumerate(limites_buttons):
            if index % 3 == 0:
                limites_row = QHBoxLayout()
                limites_row.setContentsMargins(0, 0, 0, 0)
                limites_row.setSpacing(4)
                limites_row.setAlignment(Qt.AlignLeft)
                limites_layout.addLayout(limites_row)

            button = QToolButton()
            button.setText(label)
            button.setToolTip(f"Adicionar camada: {label}")
            button.setIcon(self._custom_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setMinimumHeight(28)
            setattr(self, attr_name, button)
            limites_row.addWidget(button)

            button.clicked.connect(
                lambda checked=False, layer_key=layer_key: self.load_limite_politico(layer_key)
            )

        if limites_row is not None:
            limites_row.addStretch()

        limites_section = self._create_collapsible_section(
            "Limites Políticos",
            limites_content,
            expanded=False,
        )

        # layout.addWidget(limites_section)

        # ======================================================
        # LOCALIDADES E ÁREAS URBANIZADAS
        # ======================================================

        localidades_content = QWidget()
        localidades_layout = QVBoxLayout(localidades_content)
        localidades_layout.setContentsMargins(6, 4, 6, 4)
        localidades_layout.setSpacing(4)
        localidades_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        localidades_buttons = [
            ("localidades_capitais_btn", "Localidades - Capitais", "state.svg", "localidades_capitais"),
            ("localidades_sedes_municipais_btn", "Localidades - Sedes Municipais", "state.svg", "localidades_sedes_municipais"),
            ("areas_urbanizadas_btn", "Áreas Urbanizadas", "state.svg", "areas_urbanizadas"),
        ]

        localidades_row = None  # 2 botões por linha
        for index, (attr_name, label, icon_name, layer_key) in enumerate(localidades_buttons):
            if index % 2 == 0:
                localidades_row = QHBoxLayout()
                localidades_row.setContentsMargins(0, 0, 0, 0)
                localidades_row.setSpacing(4)
                localidades_row.setAlignment(Qt.AlignLeft)
                localidades_layout.addLayout(localidades_row)

            button = QToolButton()
            button.setText(label)
            button.setToolTip(f"Adicionar camada: {label}")
            button.setIcon(self._custom_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setMinimumHeight(28)
            setattr(self, attr_name, button)
            localidades_row.addWidget(button)
            button.clicked.connect(
                lambda checked=False, layer_key=layer_key: self.load_geopackage_reference_layer(
                    layer_key, config_section="localidades_areas_urbanizadas"
                )
            )

        if localidades_row is not None:
            localidades_row.addStretch()

        localidades_section = self._create_collapsible_section(
            "Localidades e Áreas Urbanizadas",
            localidades_content,
            expanded=False,
        )

        # layout.addWidget(localidades_section)

        # ======================================================
        # GRADES DE SATÉLITES
        # ======================================================

        grades_content = QWidget()
        grades_layout = QVBoxLayout(grades_content)
        grades_layout.setContentsMargins(6, 4, 6, 4)
        grades_layout.setSpacing(4)
        grades_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        grades_buttons = [
            ("sentinel_2_btn", "Sentinel 2", "satellite.svg", "sentinel_2"),
            ("landsat_btn", "Landsat", "satellite.svg", "landsat"),
            ("landsat_util_btn", "Landsat Util", "satellite.svg", "landsat_util"),
        ]

        grades_row = None  # 3 botões por linha
        for index, (attr_name, label, icon_name, layer_key) in enumerate(grades_buttons):
            if index % 3 == 0:
                grades_row = QHBoxLayout()
                grades_row.setContentsMargins(0, 0, 0, 0)
                grades_row.setSpacing(4)
                grades_row.setAlignment(Qt.AlignLeft)
                grades_layout.addLayout(grades_row)

            button = QToolButton()
            button.setText(label)
            button.setToolTip(f"Adicionar camada: {label}")
            button.setIcon(self._custom_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setMinimumHeight(28)
            setattr(self, attr_name, button)
            grades_row.addWidget(button)
            button.clicked.connect(
                lambda checked=False, layer_key=layer_key: self.load_geopackage_reference_layer(
                    layer_key, config_section="grades_satelites"
                )
            )

        if grades_row is not None:
            grades_row.addStretch()

        grades_section = self._create_collapsible_section(
            "Grades de Satélites",
            grades_content,
            expanded=False,
        )

        # layout.addWidget(grades_section)

        # ======================================================
        # MAPEAMENTO DE COBERTURA E USO DA TERRA
        # ======================================================

        cobertura_content = QWidget()
        cobertura_layout = QVBoxLayout(cobertura_content)
        cobertura_layout.setContentsMargins(6, 4, 6, 4)
        cobertura_layout.setSpacing(4)
        cobertura_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.terraclass_2024_btn = QToolButton()
        self.terraclass_2024_btn.setText("Terraclass 2024")
        self.terraclass_2024_btn.setToolTip("Adicionar camada Terraclass 2024")
        self.terraclass_2024_btn.setIcon(self._custom_icon("satellite.svg"))
        self.terraclass_2024_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.terraclass_2024_btn.setMinimumHeight(28)
        cobertura_layout.addWidget(self.terraclass_2024_btn)
        cobertura_layout.addStretch()

        cobertura_section = self._create_collapsible_section(
            "Mapeamento de Cobertura e Uso da Terra",
            cobertura_content,
            expanded=False,
        )

        # layout.addWidget(cobertura_section)

        # ======================================================
        # TERRITÓRIO / ÁREAS PROTEGIDAS
        # ======================================================

        territory_content = QWidget()

        territory_layout = QVBoxLayout(
            territory_content
        )

        territory_layout.setContentsMargins(
            6,
            4,
            6,
            4,
        )

        territory_layout.setSpacing(
            4
        )

        territory_layout.setAlignment(
            Qt.AlignLeft | Qt.AlignTop
        )

        territory_row_1 = QHBoxLayout()
        territory_row_1.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        territory_row_1.setSpacing(
            4
        )

        territory_row_1.setAlignment(
            Qt.AlignLeft
        )

        self.uc_federal_btn = QToolButton()
        self.uc_federal_btn.setText(
            "UC Federal"
        )
        self.uc_federal_btn.setToolTip(
            "Adicionar Unidades de Conservação Federais"
        )
        self.uc_federal_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.uc_federal_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.uc_federal_btn.setMinimumHeight(28)

        self.uc_estadual_btn = QToolButton()
        self.uc_estadual_btn.setText(
            "UC Estadual"
        )
        self.uc_estadual_btn.setToolTip(
            "Adicionar Unidades de Conservação Estaduais"
        )
        self.uc_estadual_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.uc_estadual_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.uc_estadual_btn.setMinimumHeight(28)

        self.uc_municipal_btn = QToolButton()
        self.uc_municipal_btn.setText(
            "UC Municipal"
        )
        self.uc_municipal_btn.setToolTip(
            "Adicionar Unidades de Conservação Municipais"
        )
        self.uc_municipal_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.uc_municipal_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.uc_municipal_btn.setMinimumHeight(28)

        territory_row_1.addWidget(
            self.uc_federal_btn
        )
        territory_row_1.addWidget(
            self.uc_estadual_btn
        )
        territory_row_1.addWidget(
            self.uc_municipal_btn
        )
        territory_row_1.addStretch()

        territory_layout.addLayout(
            territory_row_1
        )

        territory_row_2 = QHBoxLayout()
        territory_row_2.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        territory_row_2.setSpacing(
            4
        )

        territory_row_2.setAlignment(
            Qt.AlignLeft
        )

        self.terras_indigenas_btn = QToolButton()
        self.terras_indigenas_btn.setText(
            "Terras Indígenas"
        )
        self.terras_indigenas_btn.setToolTip(
            "Adicionar Terras Indígenas"
        )
        self.terras_indigenas_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.terras_indigenas_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.terras_indigenas_btn.setMinimumHeight(28)

        self.assentamentos_btn = QToolButton()
        self.assentamentos_btn.setText(
            "Assentamentos"
        )
        self.assentamentos_btn.setToolTip(
            "Adicionar Assentamentos Federais"
        )
        self.assentamentos_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.assentamentos_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.assentamentos_btn.setMinimumHeight(28)

        territory_row_2.addWidget(
            self.terras_indigenas_btn
        )
        territory_row_2.addWidget(
            self.assentamentos_btn
        )
        territory_row_2.addStretch()

        territory_layout.addLayout(
            territory_row_2
        )

        self.quilombos_btn = QToolButton()
        self.quilombos_btn.setText(
            "Quilombos"
        )
        self.quilombos_btn.setToolTip(
            "Adicionar Territórios Quilombolas"
        )
        self.quilombos_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.quilombos_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.quilombos_btn.setMinimumHeight(28)

        territory_row_2.addWidget(
            self.quilombos_btn
        )

        territory_section = (
            self._create_collapsible_section(
                "Áreas Protegidas",
                territory_content,
                expanded=False,
            )
        )

        # layout.addWidget(territory_section)

        # ======================================================
        # CADASTRO AMBIENTAL RURAL (CAR)
        # ======================================================

        car_content = QWidget()

        car_layout = QVBoxLayout(
            car_content
        )

        car_layout.setContentsMargins(
            6,
            4,
            6,
            4,
        )

        car_layout.setSpacing(4)
        car_layout.setAlignment(
            Qt.AlignLeft | Qt.AlignTop
        )

        self.car_bbox_btn = QToolButton()
        self.car_bbox_btn.setText(
            "Consultar BBOX"
        )
        self.car_bbox_btn.setToolTip(
            "Consultar imóveis CAR na extensão atual do mapa"
        )
        self.car_bbox_btn.setIcon(
            self._custom_icon("protected.svg")
        )
        self.car_bbox_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.car_bbox_btn.setMinimumHeight(28)

        car_layout.addWidget(
            self.car_bbox_btn
        )

        car_code_row = QHBoxLayout()
        car_code_row.setContentsMargins(0, 0, 0, 0)
        car_code_row.setSpacing(4)

        self.car_code_edit = QLineEdit()
        self.car_code_edit.setPlaceholderText(
            "Código CAR (ex.: PA-1500602-...)"
        )
        self.car_code_edit.setToolTip(
            "Informe o código completo do imóvel CAR"
        )

        self.car_code_btn = QToolButton()
        self.car_code_btn.setText(
            "Buscar Código"
        )
        self.car_code_btn.setToolTip(
            "Buscar um imóvel CAR pelo código"
        )
        self.car_code_btn.setIcon(
            QgsApplication.getThemeIcon(
                "/mActionIdentify.svg"
            )
        )
        self.car_code_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.car_code_btn.setMinimumHeight(28)

        car_code_row.addWidget(
            self.car_code_edit
        )
        car_code_row.addWidget(
            self.car_code_btn
        )

        car_layout.addLayout(
            car_code_row
        )
        car_layout.addStretch()

        car_section = (
            self._create_collapsible_section(
                "Cadastro Ambiental Rural",
                car_content,
                expanded=False,
            )
        )

        # layout.addWidget(car_section)

        # ======================================================
        # SERVIÇOS WMS / WMTS
        # ======================================================

        service_content = QWidget()

        service_layout = QVBoxLayout(
            service_content
        )

        service_layout.setContentsMargins(
            6,
            4,
            6,
            4,
        )

        service_layout.setSpacing(
            4
        )

        service_layout.setAlignment(
            Qt.AlignLeft | Qt.AlignTop
        )

        service_buttons = [
            (
                "modis_aqua_btn",
                "MODIS Aqua 721",
                "satellite.svg",
                "nasa_gibs",
                "modis_aqua_bands721",
            ),
            (
                "modis_terra_btn",
                "MODIS Terra 721",
                "satellite.svg",
                "nasa_gibs",
                "modis_terra_bands721",
            ),
            (
                "viirs_snpp_btn",
                "VIIRS SNPP",
                "satellite.svg",
                "nasa_gibs",
                "viirs_snpp_m11_i2_i1",
            ),
            (
                "viirs_noaa20_btn",
                "VIIRS NOAA-20",
                "satellite.svg",
                "nasa_gibs",
                "viirs_noaa20_m11_i2_i1",
            ),
            (
                "viirs_noaa21_btn",
                "VIIRS NOAA-21",
                "satellite.svg",
                "nasa_gibs",
                "viirs_noaa21_m11_i2_i1",
            ),
            (
                "goes_fire_btn",
                "GOES-East Fire",
                "fire.svg",
                "nasa_gibs",
                "goes_east_firetemp",
            ),
            (
                "goes_geocolor_btn",
                "GOES-East GeoColor",
                "satellite.svg",
                "nasa_gibs",
                "goes_east_geocolor",
            ),
            (
                "goes19_inpe_btn",
                "GOES-19 B6-B3-B2",
                "fire.svg",
                "inpe_goes19",
                "goes19_composicao632",
            ),
        ]

        service_row = None  # 3 botões por linha

        for index, (
            attr_name,
            label,
            icon_name,
            service_key,
            layer_key,
        ) in enumerate(service_buttons):

            if index % 3 == 0:

                service_row = QHBoxLayout()

                service_row.setContentsMargins(
                    0,
                    0,
                    0,
                    0,
                )

                service_row.setSpacing(
                    4
                )

                service_row.setAlignment(
                    Qt.AlignLeft
                )

                service_layout.addLayout(
                    service_row
                )

            button = QToolButton()

            button.setText(
                label
            )

            button.setToolTip(
                f"Adicionar camada: {label}"
            )

            button.setIcon(
                self._custom_icon(icon_name)
            )

            button.setToolButtonStyle(
                Qt.ToolButtonTextBesideIcon
            )

            button.setMinimumHeight(
                28
            )

            setattr(
                self,
                attr_name,
                button
            )

            service_row.addWidget(
                button
            )

            button.clicked.connect(
                lambda checked=False,
                service_key=service_key,
                layer_key=layer_key:
                self._load_wms_wmts_from_button(
                    service_key,
                    layer_key,
                )
            )

        if service_row is not None:
            service_row.addStretch()

        service_section = (
            self._create_collapsible_section(
                "Imagens de Satélites",
                service_content,
                expanded=False,
            )
        )

        # layout.addWidget(service_section)

        # ======================================================
        # RISCO DE FOGO E METEOROLOGIA
        # ======================================================

        meteorologia_content = QWidget()

        meteorologia_layout = QVBoxLayout(
            meteorologia_content
        )

        meteorologia_layout.setContentsMargins(
            6,
            4,
            6,
            4,
        )

        meteorologia_layout.setSpacing(4)
        meteorologia_layout.setAlignment(
            Qt.AlignLeft | Qt.AlignTop
        )

        meteorologia_buttons = [
            (
                "fire_risk_btn",
                "Risco de Fogo",
                "fire.svg",
                "inpe_meteorologia",
                "fire_risk",
            ),
            (
                "fire_risk_monthly_btn",
                "Risco de Fogo Mensal",
                "fire.svg",
                "inpe_meteorologia",
                "fire_risk_monthly",
            ),
            (
                "precipitation_btn",
                "Precipitação",
                "weather_warning.svg",
                "inpe_meteorologia",
                "precipitation",
            ),
            (
                "days_without_rain_btn",
                "Dias Sem Chuva",
                "weather_warning.svg",
                "inpe_meteorologia",
                "days_without_rain",
            ),
            (
                "temperature_btn",
                "Temperatura Máxima",
                "weather_warning.svg",
                "inpe_meteorologia",
                "temperature",
            ),
            (
                "relative_humidity_btn",
                "Umidade Relativa",
                "weather_warning.svg",
                "inpe_meteorologia",
                "relative_humidity",
            ),
        ]

        meteorologia_row = None  # 3 botões por linha

        for index, (
            attr_name,
            label,
            icon_name,
            service_key,
            layer_key,
        ) in enumerate(meteorologia_buttons):

            if index % 3 == 0:
                meteorologia_row = QHBoxLayout()
                meteorologia_row.setContentsMargins(0, 0, 0, 0)
                meteorologia_row.setSpacing(4)
                meteorologia_row.setAlignment(Qt.AlignLeft)
                meteorologia_layout.addLayout(meteorologia_row)

            button = QToolButton()
            button.setText(label)
            if layer_key == "fire_risk_monthly":
                tooltip = f"Adicionar camada: {label} (mês atual por padrão)"
            else:
                tooltip = f"Adicionar camada: {label} (data de ontem por padrão)"

            button.setToolTip(tooltip)
            button.setIcon(self._custom_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setMinimumHeight(28)

            setattr(self, attr_name, button)
            meteorologia_row.addWidget(button)

            button.clicked.connect(
                lambda checked=False,
                service_key=service_key,
                layer_key=layer_key:
                self._load_wms_wmts_from_button(
                    service_key,
                    layer_key,
                )
            )

        if meteorologia_row is not None:
            meteorologia_row.addStretch()

        self.alertas_inmet_btn = QToolButton()
        self.alertas_inmet_btn.setText("Alertas INMET")
        self.alertas_inmet_btn.setToolTip(
            "Carregar Alertas Meteorológicos do INMET"
        )
        self.alertas_inmet_btn.setIcon(
            self._custom_icon("weather_warning.svg")
        )
        self.alertas_inmet_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.alertas_inmet_btn.setMinimumHeight(28)

        meteorologia_layout.addWidget(self.alertas_inmet_btn)
        meteorologia_layout.addStretch()

        meteorologia_section = (
            self._create_collapsible_section(
                "Risco de Fogo e Meteorologia",
                meteorologia_content,
                expanded=False,
            )
        )

        # layout.addWidget(meteorologia_section)

        # ======================================================
        # ORDEM DAS SEÇÕES
        # ======================================================

        layout.addWidget(basemaps_section)
        layout.addWidget(limites_section)
        layout.addWidget(territory_section)
        layout.addWidget(service_section)
        layout.addWidget(meteorologia_section)
        layout.addWidget(localidades_section)
        layout.addWidget(cobertura_section)
        layout.addWidget(car_section)
        layout.addWidget(grades_section)

        # ======================================================
        # CONEXÕES
        # ======================================================

        self.terraclass_2024_btn.clicked.connect(
            lambda: self._load_wms_wmts_from_button(
                "terraclass", "terraclass_2024"
            )
        )

        self.uc_federal_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("uc_federal")
        )

        self.uc_estadual_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("uc_estadual")
        )

        self.uc_municipal_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("uc_municipal")
        )

        self.terras_indigenas_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("terras_indigenas")
        )

        self.assentamentos_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("assentamentos")
        )

        self.quilombos_btn.clicked.connect(
            lambda: self.load_geopackage_reference_layer("quilombos")
        )

        self.car_bbox_btn.clicked.connect(
            self.load_car_by_bbox
        )

        self.car_code_btn.clicked.connect(
            self.load_car_by_code
        )

        self.car_code_edit.returnPressed.connect(
            self.load_car_by_code
        )

        self.alertas_inmet_btn.clicked.connect(
            self.load_alertas_inmet
        )

        layout.addStretch()



        ## Final do _build_

    # ==========================================================
    # FUNÇÕES DE CARREGAMENTO
    # ==========================================================
    # ==========================================================
    # UTILITÁRIOS DE CAMADAS
    # ==========================================================

    def _layer_exists(self, layer_name):

        return bool(
            QgsProject.instance().mapLayersByName(
                layer_name
            )
        )


    def _show_layer_exists(self, layer_name):

        QMessageBox.information(
            iface.mainWindow(),
            "QMD Tools Explorer",
            f'A camada "{layer_name}" já está adicionada ao projeto.'
        )


    def _add_reference_layer(
        self,
        layer,
        layer_name,
        is_basemap=False,
    ):

        if not layer.isValid():

            log_message(
                f"Erro ao carregar a camada: {layer_name}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                f'Não foi possível carregar a camada "{layer_name}".'
            )

            return False

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        project.addMapLayer(
            layer,
            False,
        )

        if is_basemap:

            root.insertLayer(
                -1,
                layer,
            )

        else:

            root.insertLayer(
                0,
                layer,
            )

        iface.mapCanvas().refresh()

        log_message(
            f"Camada carregada: {layer_name}"
        )

        return True


    # ==========================================================
    # GEOPACKAGES DE REFERÊNCIA
    # ==========================================================

    def _custom_icon(self, filename):

        icon_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "icons"
            / filename
        )

        if icon_path.exists():
            return QIcon(str(icon_path))

        return QgsApplication.getThemeIcon(
            "/mActionAddRasterLayer.svg"
        )


    def _plugin_dir(self):

        return Path(
            __file__
        ).resolve().parent.parent


    def _reference_layers_config_path(self):

        return (
            self._plugin_dir()
            / "config"
            / "reference_layers.json"
        )


    def _load_reference_layers_config(self):

        config_path = (
            self._reference_layers_config_path()
        )

        if not config_path.exists():

            raise FileNotFoundError(
                "Arquivo reference_layers.json "
                f"não encontrado em: {config_path}"
            )

        with config_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )


    def _geopackage_cache_dir(self):

        cache_dir = (
            self._plugin_dir()
            / "data"
            / "reference_layers_cache"
        )

        cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return cache_dir


    def _download_geopackage(
        self,
        url,
        local_path,
        layer_name,
    ):

        temp_path = local_path.with_suffix(
            local_path.suffix + ".part"
        )

        try:

            log_message(
                f"Baixando camada: {layer_name}..."
            )

            QApplication.processEvents()

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "QMD Tools Explorer"
                },
            )

            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=120,
            ) as response:

                with temp_path.open(
                    "wb"
                ) as output:

                    shutil.copyfileobj(
                        response,
                        output,
                    )

            temp_path.replace(
                local_path
            )

            return True

        except Exception as error:

            if temp_path.exists():

                try:
                    temp_path.unlink()
                except Exception as erro:
                    print(
                        f"[QMD Tools Explorer] "
                        f"Não foi possível remover o arquivo temporário "
                        f"{temp_path}: {erro}"
                    )

            log_message(
                f"Erro ao baixar {layer_name}: {error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                f"Não foi possível baixar a camada "
                f"{layer_name}.\n\n"
                f"Erro: {error}"
            )

            return False

        finally:

            log_message(
                f"Download finalizado: {layer_name}"
            )

            QApplication.processEvents()


    def load_geopackage_reference_layer(
        self,
        layer_key,
        config_section="territorio_areas_protegidas",
    ):

        try:

            config = (
                self._load_reference_layers_config()
            )

            layer_config = (
                config[
                    config_section
                ][
                    layer_key
                ]
            )

        except Exception as error:

            log_message(
                f"Erro ao ler reference_layers.json: "
                f"{error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a "
                "configuração da camada.\n\n"
                f"Erro: {error}"
            )

            return

        # Camadas vetoriais de áreas protegidas não são temporais.
        # Mantemos o nome definido na configuração, sem depender de
        # uma variável `date` que não existe neste método.
        base_layer_name = layer_config["name"]
        layer_name = base_layer_name

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

        cache_dir = (
            self._geopackage_cache_dir()
        )

        local_path = (
            cache_dir
            / layer_config["filename"]
        )

        if not local_path.exists():

            ok = self._download_geopackage(
                layer_config["url"],
                local_path,
                layer_name,
            )

            if not ok:

                return

        layer = QgsVectorLayer(
            str(local_path),
            layer_name,
            "ogr",
        )

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=False,
        )


    def _load_wfs_reference_layer(
        self,
        layer_name,
        type_name,
        cql_filter=None,
        base_url=None,
    ):

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

        if base_url is None:
            base_url = (
                "https://terrabrasilis.dpi.inpe.br/"
                "queimadas/geoserver/wfs"
            )

        uri = (
            f"{base_url}"
            "?service=WFS"
            "&version=1.1.0"
            "&request=GetFeature"
            f"&typeName={type_name}"
        )

        if cql_filter:

            uri += (
                f"&CQL_FILTER={cql_filter}"
            )

        uri += (
            "&srsname=EPSG:4326"
        )

        layer = QgsVectorLayer(
            uri,
            layer_name,
            "WFS",
        )

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=False,
        )


    def load_xyz_basemap(self, layer_key):
        """Carrega um basemap XYZ definido na seção ``basemaps`` do JSON."""

        try:
            config = self._load_reference_layers_config()
            layer_config = config["basemaps"][layer_key]
        except Exception as error:
            log_message(f"Erro ao ler configuração do basemap: {error}")
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a configuração do basemap.\n\n"
                f"Erro: {error}",
            )
            return

        layer_name = layer_config["name"]
        if self._layer_exists(layer_name):
            self._show_layer_exists(layer_name)
            return

        service_url = layer_config["url"]
        encoded_url = quote(service_url, safe=":/{}")
        uri = (
            "type=xyz"
            "&zmin=0"
            "&zmax=20"
            f"&url={encoded_url}"
        )

        layer = QgsRasterLayer(uri, layer_name, "wms")
        if not layer.isValid():
            log_message(f"Erro ao carregar basemap: {layer_name}")
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                f'Não foi possível carregar o basemap "{layer_name}".',
            )
            return

        QgsProject.instance().setCrs(
            QgsCoordinateReferenceSystem("EPSG:4326")
        )
        layer.setOpacity(1)
        self._add_reference_layer(layer, layer_name, is_basemap=True)


    def load_limite_politico(self, layer_key):
        """Carrega um limite político definido na seção ``limites_politicos``."""

        try:
            config = self._load_reference_layers_config()
            layer_config = config["limites_politicos"][layer_key]
        except Exception as error:
            log_message(f"Erro ao ler configuração dos limites políticos: {error}")
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a configuração do limite político.\n\n"
                f"Erro: {error}",
            )
            return

        self._load_wfs_reference_layer(
            layer_name=layer_config["name"],
            type_name=layer_config["layer"],
            cql_filter=layer_config.get("cql_filter"),
            base_url=layer_config.get("url"),
        )


    def load_google_hybrid(self):
        self.load_xyz_basemap("google_hybrid")


    def load_openstreetmap(self):
        self.load_xyz_basemap("osm")


    def load_biomas(self):
        self.load_limite_politico("biomas")


    def load_estados(self):
        self.load_limite_politico("estados")


    def load_amz_legal(self):
        self.load_limite_politico("amz_legal")


    # ==========================================================
    # CADASTRO AMBIENTAL RURAL (CAR)
    # ==========================================================

    CAR_WFS_URL = (
        "https://geoserver.car.gov.br/"
        "geoserver/sicar/wfs"
    )

    CAR_UF_BY_IBGE = {
        11: "ro", 12: "ac", 13: "am", 14: "rr", 15: "pa",
        16: "ap", 17: "to", 21: "ma", 22: "pi", 23: "ce",
        24: "rn", 25: "pb", 26: "pe", 27: "al", 28: "se",
        29: "ba", 31: "mg", 32: "es", 33: "rj", 35: "sp",
        41: "pr", 42: "sc", 43: "rs", 50: "ms", 51: "mt",
        52: "go", 53: "df",
    }

    CAR_UF_BY_CODE = {
        uf: uf for uf in CAR_UF_BY_IBGE.values()
    }

    CAR_FIELD_TYPES = {
        "cod_imovel": QVariant.String,
        "status_imovel": QVariant.String,
        "dat_criacao": QVariant.String,
        "data_atualizacao": QVariant.String,
        "area": QVariant.Double,
        "condicao": QVariant.String,
        "uf": QVariant.String,
        "municipio": QVariant.String,
        "cod_municipio_ibge": QVariant.String,
        "m_fiscal": QVariant.Double,
        "tipo_imovel": QVariant.String,
    }

    def _get_shared_roi_manager(self):
        """
        Retorna o mesmo ROI manager utilizado pela busca de focos/imagens.

        Preferimos o objeto recebido no construtor. Como proteção para
        versões em que o LayersWidget ainda é criado sem argumento,
        procuramos um atributo roi_manager na cadeia de widgets-pai.
        """
        if self.roi_manager is not None:
            return self.roi_manager

        parent = self.parent()
        visited = set()

        while parent is not None:
            object_id = id(parent)

            if object_id in visited:
                break

            visited.add(object_id)

            candidate = getattr(
                parent,
                "roi_manager",
                None,
            )

            if candidate is not None:
                self.roi_manager = candidate
                return candidate

            parent = parent.parent()

        return None

    def _car_analysis_bbox(self):
        """
        Obtém o BBOX da análise compartilhado com imagens e focos.

        O FireWidget usa roi_manager.get_bbox(), cujo BBOX é mantido em
        EPSG:4326. O CAR passa a consumir exatamente os mesmos quatro
        valores, sem capturar novamente a extensão do canvas.
        """
        manager = self._get_shared_roi_manager()

        if manager is None:
            return None

        bbox = manager.get_bbox()

        if not bbox or len(bbox) != 4:
            return None

        try:
            return tuple(
                float(value)
                for value in bbox
            )
        except (TypeError, ValueError):
            return None

    def _car_extent_4674(self, bbox=None):
        """
        Converte o BBOX compartilhado da análise de EPSG:4326 para EPSG:4674.

        Não usa iface.mapCanvas().extent(): o BBOX vem exclusivamente do
        roi_manager, o mesmo utilizado pela busca de focos e imagens.
        """
        if bbox is None:
            bbox = self._car_analysis_bbox()

        if not bbox or len(bbox) != 4:
            return None

        xmin, ymin, xmax, ymax = bbox

        if xmin >= xmax or ymin >= ymax:
            return None

        extent = QgsRectangle(
            xmin,
            ymin,
            xmax,
            ymax,
        )

        source_crs = QgsCoordinateReferenceSystem(
            "EPSG:4326"
        )

        target_crs = QgsCoordinateReferenceSystem(
            "EPSG:4674"
        )

        if source_crs != target_crs:
            transform = QgsCoordinateTransform(
                source_crs,
                target_crs,
                QgsProject.instance(),
            )

            extent = transform.transformBoundingBox(
                extent
            )

        return extent

    def _car_code_url(self, code):
        """Monta uma consulta WFS direta para um único código CAR."""
        from urllib.parse import urlencode

        uf = code[:2].lower()
        typename = f"sicar:sicar_imoveis_{uf}"

        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": typename,
            "outputFormat": "application/json",
            "srsName": "EPSG:4674",
            "CQL_FILTER": f"cod_imovel='{code}'",
            "maxFeatures": "10",
        }

        return self.CAR_WFS_URL + "?" + urlencode(params)

    def _car_geometry_from_geojson(self, geometry_json):
        """
        Converte uma geometria GeoJSON para QgsGeometry.

        O retorno do WFS pode trazer Polygon ou MultiPolygon. A API
        QgsGeometry.fromGeoJson() não existe nas versões do QGIS em que
        este plugin é executado; a conversão deve ser feita através de
        QgsJsonUtils.geometryFromGeoJson().
        """
        if not geometry_json:
            return None

        if isinstance(geometry_json, str):
            try:
                geometry_json = json.loads(geometry_json)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Geometria GeoJSON inválida: {error}"
                )

        if not isinstance(geometry_json, dict):
            raise ValueError(
                "A geometria retornada pelo CAR não está em formato "
                "GeoJSON válido."
            )

        geometry_type = geometry_json.get("type")

        if geometry_type == "Feature":
            geometry_json = geometry_json.get("geometry")
            if not geometry_json:
                return None
            geometry_type = geometry_json.get("type")

        if geometry_type == "GeometryCollection":
            geometries = []

            for item in geometry_json.get("geometries", []):
                geometry = self._car_geometry_from_geojson(item)

                if geometry and not geometry.isEmpty():
                    geometries.append(geometry)

            if not geometries:
                return None

            if len(geometries) == 1:
                return geometries[0]

            return QgsGeometry.collectGeometry(geometries)

        try:
            geometry = QgsJsonUtils.geometryFromGeoJson(
                json.dumps(
                    geometry_json,
                    ensure_ascii=False,
                )
            )
        except Exception as error:
            raise ValueError(
                f"Não foi possível converter a geometria "
                f"'{geometry_type}' retornada pelo CAR: {error}"
            )

        if geometry is None or geometry.isNull() or geometry.isEmpty():
            raise ValueError(
                f"A geometria '{geometry_type}' retornada pelo CAR "
                "está vazia ou é inválida."
            )

        return geometry

    def _car_create_result_from_ogr(self, geojson_path, layer_name):
        """
        Carrega um GeoJSON através do driver OGR e copia o resultado para
        uma camada de memória.

        Para a consulta por código CAR usamos OGR diretamente, pois o
        retorno normalmente contém uma única geometria e essa abordagem
        é significativamente mais leve do que reconstruir manualmente
        a geometria com QgsJsonUtils.
        """
        source = QgsVectorLayer(
            geojson_path,
            layer_name,
            "ogr",
        )

        if not source.isValid():
            raise RuntimeError(
                "O GeoJSON retornado pelo CAR não pôde ser carregado pelo QGIS."
            )

        result = QgsVectorLayer(
            "MultiPolygon?crs=EPSG:4674",
            layer_name,
            "memory",
        )

        if not result.isValid():
            raise RuntimeError(
                "Não foi possível criar a camada de memória do CAR."
            )

        provider = result.dataProvider()

        # Mantém os campos retornados pelo serviço.
        provider.addAttributes(
            source.fields()
        )
        result.updateFields()

        features = []

        for source_feature in source.getFeatures():
            geometry = source_feature.geometry()

            if geometry is None or geometry.isNull() or geometry.isEmpty():
                continue

            if QgsWkbTypes.geometryType(
                geometry.wkbType()
            ) == QgsWkbTypes.PolygonGeometry:
                if not geometry.convertToMultiType():
                    continue

            if QgsWkbTypes.geometryType(
                geometry.wkbType()
            ) != QgsWkbTypes.PolygonGeometry:
                continue

            feature = QgsFeature(
                result.fields()
            )
            feature.setGeometry(
                geometry
            )
            feature.setAttributes(
                source_feature.attributes()
            )
            features.append(feature)

        if features:
            added, _ = provider.addFeatures(
                features
            )

            if not added:
                raise RuntimeError(
                    "Não foi possível adicionar a geometria "
                    "do imóvel CAR à camada de memória."
                )

        result.updateExtents()

        return result, result.featureCount()

    def _car_create_result_from_geojson(self, geojson, layer_name="Imóveis CAR"):
        """
        Cria a camada de memória a partir do GeoJSON retornado pelo CAR.

        São tratados explicitamente Polygon e MultiPolygon. Caso o
        serviço retorne Polygon, ele é convertido para MultiPolygon
        antes de ser inserido na camada, que mantém o tipo MultiPolygon.
        """
        if not isinstance(geojson, dict):
            raise ValueError(
                "A resposta do serviço CAR não está em formato JSON."
            )

        features_json = geojson.get("features", [])

        if not isinstance(features_json, list):
            raise ValueError(
                "A resposta GeoJSON do CAR não possui uma lista "
                "válida de features."
            )

        layer = QgsVectorLayer(
            "MultiPolygon?crs=EPSG:4674",
            layer_name,
            "memory",
        )

        if not layer.isValid():
            raise RuntimeError(
                "Não foi possível criar a camada de resultado do CAR."
            )

        provider = layer.dataProvider()

        # ------------------------------------------------------
        # Campos
        # ------------------------------------------------------
        properties = {}

        for item in features_json:
            if not isinstance(item, dict):
                continue

            candidate = item.get("properties")

            if isinstance(candidate, dict):
                properties = candidate
                break

        fields = []

        for name in properties.keys():
            field_type = self.CAR_FIELD_TYPES.get(
                name,
                QVariant.String,
            )

            fields.append(
                QgsField(
                    name,
                    field_type,
                )
            )

        if fields:
            provider.addAttributes(fields)
            layer.updateFields()

        # ------------------------------------------------------
        # Geometrias
        # ------------------------------------------------------
        new_features = []
        skipped = 0

        for item in features_json:
            if not isinstance(item, dict):
                skipped += 1
                continue

            geometry_json = item.get("geometry")

            if not geometry_json:
                skipped += 1
                continue

            try:
                geometry = self._car_geometry_from_geojson(
                    geometry_json
                )
            except Exception as error:
                skipped += 1

                log_message(
                    "CAR: erro ao converter geometria: "
                    f"{error}"
                )

                continue

            if geometry is None or geometry.isNull() or geometry.isEmpty():
                skipped += 1
                continue

            # --------------------------------------------------
            # O serviço pode retornar Polygon ou MultiPolygon.
            # A camada de memória é MultiPolygon, portanto
            # convertemos Polygon para multipart.
            # --------------------------------------------------
            geometry_type = QgsWkbTypes.geometryType(
                geometry.wkbType()
            )

            if geometry_type == QgsWkbTypes.PolygonGeometry:
                if not geometry.convertToMultiType():
                    skipped += 1

                    log_message(
                        "CAR: não foi possível converter Polygon "
                        "para MultiPolygon."
                    )

                    continue

            # Proteção adicional: não inserir geometrias que não
            # sejam poligonais na camada MultiPolygon.
            if QgsWkbTypes.geometryType(
                geometry.wkbType()
            ) != QgsWkbTypes.PolygonGeometry:
                skipped += 1

                log_message(
                    "CAR: geometria ignorada porque não é poligonal: "
                    f"{QgsWkbTypes.displayString(geometry.wkbType())}"
                )

                continue

            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)

            props = item.get("properties", {}) or {}

            values = []

            for field in layer.fields():
                values.append(
                    props.get(field.name())
                )

            feature.setAttributes(values)
            new_features.append(feature)

        # ------------------------------------------------------
        # Adiciona as features
        # ------------------------------------------------------
        if new_features:
            added, _ = provider.addFeatures(
                new_features
            )

            if not added:
                raise RuntimeError(
                    "O QGIS não conseguiu adicionar as geometrias "
                    "retornadas pelo CAR à camada de memória."
                )

            layer.updateExtents()

        if skipped:
            log_message(
                f"CAR: {skipped} feição(ões) foram ignoradas "
                "durante o processamento da geometria."
            )

        return layer, len(new_features)

    def _car_add_result(self, result_layer, count, zoom=False):
        """Adiciona o resultado CAR ao projeto sem remover consultas anteriores."""
        if count == 0:
            QMessageBox.information(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Nenhum imóvel CAR foi encontrado para a consulta.",
            )
            return

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        project.addMapLayer(
            result_layer,
            False,
        )

        root.insertLayer(
            0,
            result_layer,
        )

        if zoom and not result_layer.extent().isEmpty():
            iface.mapCanvas().setExtent(
                result_layer.extent()
            )

        iface.mapCanvas().refresh()

        log_message(
            f"CAR: {count} imóvel(is) carregado(s) "
            f"na camada '{result_layer.name()}'."
        )

    def load_car_by_code(self):
        """Consulta um imóvel CAR pelo código, sem bloquear o QGIS."""
        code = self.car_code_edit.text().strip().upper()

        if not code:
            QMessageBox.information(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Informe o código do imóvel CAR.",
            )
            self.car_code_edit.setFocus()
            return

        parts = code.split("-", 2)

        if len(parts) < 3 or len(parts[0]) != 2:
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Código CAR inválido.\n\n"
                "Informe o código completo, por exemplo:\n"
                "PA-1500602-...",
            )
            self.car_code_edit.setFocus()
            return

        uf = parts[0].lower()
        if uf not in self.CAR_UF_BY_CODE:
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                f"A UF '{parts[0]}' não foi reconhecida no código CAR.",
            )
            return

        url = self._car_code_url(code)

        log_message(
            f"CAR: buscando imóvel pelo código {code}..."
        )
        QApplication.processEvents()

        self.car_code_btn.setEnabled(False)
        self.car_bbox_btn.setEnabled(False)

        task = _CARCodeTask(
            url,
            code,
            self,
        )
        self._car_code_task = task
        QgsApplication.taskManager().addTask(task)

    def _car_code_finished(self, task):
        """Finaliza a consulta CAR no thread principal do QGIS."""
        self.car_code_btn.setEnabled(True)
        self.car_bbox_btn.setEnabled(True)
        self._car_code_task = None

        if task.error:
            log_message(
                f"Erro na consulta CAR por código: {task.error}"
            )
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Não foi possível consultar o imóvel CAR.\n\n"
                f"Erro: {task.error}",
            )
            return

        temp_path = None

        try:
            code_name = (
                f"Imóvel CAR {task.code}"
            )

            temp_path = task.geojson_path

            if not temp_path or not os.path.exists(temp_path):
                raise RuntimeError(
                    "O arquivo GeoJSON temporário do imóvel não está disponível."
                )

            result_layer, count = self._car_create_result_from_ogr(
                temp_path,
                layer_name=code_name,
            )

            if count == 0:
                self._car_add_result(result_layer, 0)
                return

            self._car_add_result(
                result_layer,
                count,
                zoom=True,
            )

            # Limpa o campo após uma busca concluída, permitindo
            # informar imediatamente outro código CAR.
            self.car_code_edit.clear()

        except Exception as error:
            log_message(
                f"Erro ao processar resultado CAR: {error}"
            )
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "O imóvel foi localizado, mas não foi possível "
                "processar a geometria retornada.\n\n"
                f"Erro: {error}",
            )

        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _car_bbox_urls(self, extent):
        """
        Monta as URLs WFS para consultar as UFs que compõem o BBOX.

        O GeoServer do SICAR possui uma camada por UF, não existe uma
        camada nacional. Para manter a implementação simples e robusta
        na primeira versão do BBOX, são geradas consultas espaciais para
        as 27 camadas. O filtro espacial é aplicado no servidor.
        """
        from urllib.parse import urlencode

        if extent is None or extent.isEmpty():
            return []

        xmin = extent.xMinimum()
        ymin = extent.yMinimum()
        xmax = extent.xMaximum()
        ymax = extent.yMaximum()

        urls = []

        for uf in sorted(self.CAR_UF_BY_CODE.values()):
            typename = f"sicar:sicar_imoveis_{uf}"

            params = {
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typeName": typename,
                "outputFormat": "application/json",
                "srsName": "EPSG:4674",
                "CQL_FILTER": (
                    "BBOX(geo_area_imovel,"
                    f"{xmin},{ymin},{xmax},{ymax})"
                ),
                "maxFeatures": "5000",
            }

            urls.append(
                self.CAR_WFS_URL
                + "?"
                + urlencode(params)
            )

        return urls

    def load_car_by_bbox(self):
        """
        Consulta imóveis CAR usando o mesmo BBOX da análise.

        O BBOX não é obtido da extensão atual do canvas. Ele vem do
        roi_manager compartilhado com a busca de imagens e focos.
        """
        bbox = self._car_analysis_bbox()

        if bbox is None:
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Não existe uma Região de Interesse/BBOX disponível.\n\n"
                "Capture primeiro a área de análise na ferramenta de Busca.",
            )
            return

        extent = self._car_extent_4674(
            bbox
        )

        if extent is None or extent.isEmpty():
            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "O BBOX da área de análise é inválido.",
            )
            return

        width = extent.xMaximum() - extent.xMinimum()
        height = extent.yMaximum() - extent.yMinimum()

        # Evita uma consulta acidentalmente muito ampla.
        if width > 5 or height > 5:
            answer = QMessageBox.question(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "A área de análise é muito grande "
                f"({width:.2f}° x {height:.2f}° em SIRGAS 2000).\n\n"
                "A consulta pode retornar muitos imóveis e demorar. "
                "Deseja continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                return

        urls = self._car_bbox_urls(
            extent
        )

        if not urls:
            QMessageBox.information(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Não foi possível montar a consulta espacial.",
            )
            return

        log_message(
            "CAR: usando o BBOX compartilhado da área de análise."
        )

        log_message(
            "CAR: BBOX EPSG:4326 = "
            f"{bbox[0]:.6f}, "
            f"{bbox[1]:.6f}, "
            f"{bbox[2]:.6f}, "
            f"{bbox[3]:.6f}"
        )

        log_message(
            "CAR: BBOX transformado para EPSG:4674 = "
            f"{extent.xMinimum():.6f}, "
            f"{extent.yMinimum():.6f}, "
            f"{extent.xMaximum():.6f}, "
            f"{extent.yMaximum():.6f}"
        )

        self.car_code_btn.setEnabled(False)
        self.car_bbox_btn.setEnabled(False)

        task = _CARBBOXTask(
            urls,
            extent,
            self,
            bbox=bbox,
        )

        self._car_bbox_task = task
        QgsApplication.taskManager().addTask(
            task
        )

    def _car_bbox_finished(self, task):
        """Finaliza a consulta CAR por BBOX no thread principal."""
        self.car_code_btn.setEnabled(True)
        self.car_bbox_btn.setEnabled(True)
        self._car_bbox_task = None

        if task.error:
            log_message(
                f"Erro na consulta CAR por BBOX: {task.error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Não foi possível consultar os imóveis CAR "
                "na extensão atual do mapa.\n\n"
                f"Erro: {task.error}",
            )
            return

        try:
            bbox = task.bbox

            bbox_name = (
                "Imóveis CAR BBox - "
                f"[{bbox[0]:.6f},"
                f"{bbox[1]:.6f},"
                f"{bbox[2]:.6f},"
                f"{bbox[3]:.6f}]"
            )

            result_layer, count = (
                self._car_create_result_from_geojson(
                    task.geojson,
                    layer_name=bbox_name,
                )
            )

            if count == 0:
                self._car_add_result(
                    result_layer,
                    0,
                )
                return

            self._car_add_result(
                result_layer,
                count,
                zoom=False,
            )

            log_message(
                f"CAR BBOX: {count} imóvel(is) carregado(s)."
            )

        except Exception as error:
            log_message(
                f"Erro ao processar resultado CAR BBOX: {error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "Cadastro Ambiental Rural",
                "Os imóveis foram localizados, mas não foi "
                "possível processar as geometrias retornadas.\n\n"
                f"Erro: {error}",
            )


    # ==========================================================
    # ALERTAS INMET
    # ==========================================================

    def load_alertas_inmet(self):
        """Executa o script de alertas do INMET dentro do QGIS."""

        script_path = (
            self._plugin_dir()
            / "scripts"
            / "avisos_inmet_qgis.py"
        )

        if not script_path.exists():
            log_message(
                f"Script do INMET não encontrado: {script_path}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "O script de Alertas INMET não foi encontrado.\n\n"
                f"Arquivo esperado: {script_path}"
            )
            return

        try:
            log_message(
                "Executando script de Alertas INMET..."
            )

            avisos_inmet_qgis.executar()

            log_message(
                "Script de Alertas INMET finalizado."
            )

        except Exception as error:
            log_message(
                f"Erro ao executar Alertas INMET: {error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível executar os Alertas INMET.\n\n"
                f"Erro: {error}"
            )


    # ==========================================================
    # WMS / WMTS
    # ==========================================================

    def _select_layer_date(self, layer_name, temporal_granularity="day"):
        """Abre o seletor de data/mês conforme a granularidade da camada."""

        monthly = temporal_granularity == "month"

        dialog = QDialog(iface.mainWindow())
        dialog.setWindowTitle("Selecionar mês" if monthly else "Selecionar data")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        label = QLabel(
            f"{'Mês' if monthly else 'Data'} para carregar:\n{layer_name}"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("MM/yyyy" if monthly else "dd/MM/yyyy")
        initial_date = QDate.currentDate()
        if monthly:
            initial_date = QDate(initial_date.year(), initial_date.month(), 1)
        else:
            initial_date = initial_date.addDays(-1)
        date_edit.setDate(initial_date)
        date_edit.setMinimumWidth(130)
        layout.addWidget(date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        buttons.button(QDialogButtonBox.Ok).setText("Adicionar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return None

        selected_date = date_edit.date()
        if monthly:
            selected_date = QDate(
                selected_date.year(),
                selected_date.month(),
                1,
            )

        return selected_date.toString("yyyy-MM-dd")

    def _get_wms_service_config(self, service_key):
        """Retorna a configuração WMS/WMTS dos serviços existentes ou das novas áreas temáticas."""

        config = self._load_reference_layers_config()

        if service_key in config.get("servicos_wms_wmts", {}):
            return config["servicos_wms_wmts"][service_key]

        if service_key in config.get("mapeamento_cobertura_uso_terra", {}):
            return config["mapeamento_cobertura_uso_terra"][service_key]

        raise KeyError(f"Serviço WMS/WMTS não encontrado: {service_key}")


    def _load_wms_wmts_from_button(self, service_key, layer_key):
        """Carrega uma camada temporal após selecionar a data."""

        try:
            config = self._load_reference_layers_config()
            service = self._get_wms_service_config(service_key)
            layer_config = service["layers"][layer_key]
        except Exception as error:
            log_message(
                f"Erro ao ler configuração WMS/WMTS: {error}"
            )
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a configuração do serviço.\n\n"
                f"Erro: {error}"
            )
            return

        # Apenas camadas explicitamente temporais exibem o seletor de data.
        # As camadas GOES do GIBS são mantidas no comportamento anterior:
        # carregamento sem uma data escolhida pelo usuário.
        is_temporal = layer_config.get("temporal", False)

        if is_temporal:
            date = self._select_layer_date(
                layer_config.get("name", layer_key),
                layer_config.get("temporal_granularity", "day"),
            )
            if not date:
                return
        else:
            date = None

        self.load_wms_wmts_layer(
            service_key,
            layer_key,
            date=date,
        )

    def load_wms_wmts_layer(
        self,
        service_key,
        layer_key,
        date=None,
    ):

        try:
            config = self._load_reference_layers_config()
            service = self._get_wms_service_config(service_key)
            layer_config = service["layers"][layer_key]
        except Exception as error:
            log_message(
                "Erro ao ler configuração WMS/WMTS: "
                f"{error}"
            )
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a configuração do serviço.\n\n"
                f"Erro: {error}"
            )
            return

        base_layer_name = layer_config["name"]
        layer_name = (
            f"{base_layer_name} - {date}"
            if date
            else base_layer_name
        )

        if self._layer_exists(layer_name):
            self._show_layer_exists(layer_name)
            return

        service_type = service.get("type", "WMS").upper()
        crs = service.get("crs", "EPSG:4326")
        image_format = (
            layer_config.get("format")
            or service.get("format", "image/png")
        )
        layer_id = layer_config["layer"]
        service_url = service["url"]

        # ----------------------------------------------------------
        # INPE Meteorologia — WMS-T
        #
        # O WMS do BDQueimadas expõe a dimensão TIME. Quando a camada
        # é adicionada pelo diálogo WMS do QGIS, o provider cria uma URI
        # do tipo WMS-T (type=wmst), com temporalSource=provider e
        # timeDimensionExtent. É importante reproduzir essa estrutura
        # aqui; simplesmente colocar TIME dentro da URL gera uma camada
        # WMS comum e o QGIS não a reconhece como temporal.
        # ----------------------------------------------------------
        if service_key == "inpe_meteorologia":
            granularity = layer_config.get("temporal_granularity", "day")

            if granularity == "month":
                # A camada mensal usa o primeiro dia do mês como instante
                # de referência (ex.: 2026-08-01 para agosto/2026).
                period = "P1M"
            else:
                period = "P1D"

            # O QGIS exige um timeDimensionExtent para registrar a camada
            # como WMS-T. Para estas camadas do BDQueimadas, a dimensão
            # começa em 2001-01-01. O fim acompanha pelo menos a data
            # escolhida e a data atual, evitando deixar o intervalo
            # temporal artificialmente encerrado na data selecionada.
            current_date = QDate.currentDate().toString("yyyy-MM-dd")
            extent_end = max(date or current_date, current_date)

            if granularity == "month":
                current_qdate = QDate.currentDate()
                current_month = QDate(
                    current_qdate.year(),
                    current_qdate.month(),
                    1,
                ).toString("yyyy-MM-dd")
                extent_end = max(date or current_month, current_month)

            uri_parts = [
                "allowTemporalUpdates=true",
                "temporalSource=provider",
                "type=wmst",
                f"timeDimensionExtent=2001-01-01/{extent_end}/{period}",
                f"time={date}/{date}" if date else "",
                f"crs={crs}",
                f"format={image_format}",
                f"layers={layer_id}",
                "styles=",
                f"url={quote(service_url, safe=':/')}",
            ]

            uri = "&".join(part for part in uri_parts if part)

            layer = QgsRasterLayer(
                uri,
                layer_name,
                "wms",
            )

            if not layer.isValid():
                log_message(
                    f"Erro ao carregar {service_type}: "
                    f"{layer_name}"
                )
                QMessageBox.warning(
                    iface.mainWindow(),
                    "QMD Tools Explorer",
                    f'Não foi possível carregar a camada "{layer_name}".\n\n'
                    f"Serviço: {service_type}"
                )
                return

            self._add_reference_layer(
                layer,
                layer_name,
                is_basemap=False,
            )
            return

        # ----------------------------------------------------------
        # NASA GIBS
        #
        # Para MODIS/VIIRS usamos o WMS-T do QGIS. A versão anterior
        # colocava TIME dentro da URL do WMS. Isso carregava a data em
        # alguns casos, mas não fazia o provider WMS tratar a camada
        # como temporal de forma correta.
        #
        # Também não usamos XYZ/WMTS como XYZ aqui: a grade espacial
        # do GIBS não deve ser interpretada como uma grade XYZ comum,
        # pois isso provoca deslocamento/distorção da imagem.
        #
        # Com type=wmst + temporalSource=provider + timeDimensionExtent
        # + time, o QGIS monta a requisição WMS com TIME=... mantendo
        # a referência espacial correta do serviço.
        #
        # As camadas GOES continuam sem data e seguem como WMS comum.
        # ----------------------------------------------------------
        uri_parts = [
            f"crs={crs}",
            f"format={image_format}",
            f"layers={layer_id}",
            "styles=default",
        ]

        if date:
            # O GIBS trabalha com uma imagem diária para estas camadas.
            # Usamos o mesmo início/fim para representar uma única data.
            date_start = layer_config.get("date_min", "2000-01-01")
            date_end = layer_config.get("date_max", date)

            uri_parts.extend([
                "type=wmst",
                "temporalSource=provider",
                "allowTemporalUpdates=true",
                f"timeDimensionExtent={date_start}/{date_end}/P1D",
                f"time={date}/{date}",
            ])

        encoded_service_url = quote(
            service_url,
            safe=":/"
        )

        if service_type == "WMTS":
            tile_matrix_set = layer_config.get(
                "tile_matrix_set"
            )
            if tile_matrix_set:
                uri_parts.append(
                    f"tileMatrixSet={tile_matrix_set}"
                )

        uri_parts.append(
            f"url={encoded_service_url}"
        )

        uri = "&".join(uri_parts)

        layer = QgsRasterLayer(
            uri,
            layer_name,
            "wms",
        )

        if not layer.isValid():
            log_message(
                f"Erro ao carregar {service_type}: "
                f"{layer_name}"
            )
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                f'Não foi possível carregar a camada "{layer_name}".\n\n'
                f"Serviço: {service_type}"
            )
            return

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=False,
        )



class _CARBBOXTask(QgsTask):
    """
    Consulta imóveis CAR por BBOX.

    Como o SICAR publica uma camada por UF, a tarefa recebe uma lista
    de URLs e consulta cada camada sequencialmente. Isso mantém apenas
    uma requisição CAR em andamento por vez e deixa a interface do QGIS
    responsiva.
    """

    def __init__(self, urls, extent, owner, bbox=None):
        super().__init__(
            "Consultar imóveis CAR por BBOX",
            QgsTask.CanCancel,
        )

        self.urls = urls
        self.extent = extent
        self.owner = owner

        # Mantém o BBOX original compartilhado com imagens/focos.
        # Ele é usado apenas para nomear a camada de forma legível.
        if bbox is not None:
            self.bbox = tuple(
                float(value)
                for value in bbox
            )
        else:
            self.bbox = (
                float(extent.xMinimum()),
                float(extent.yMinimum()),
                float(extent.xMaximum()),
                float(extent.yMaximum()),
            )

        self.geojson = {
            "type": "FeatureCollection",
            "features": [],
        }

        self.error = None
        self.requested_urls = 0
        self.successful_requests = 0

    def _get_json(self, url):
        """Executa uma requisição WFS usando a infraestrutura do QGIS."""
        request = QNetworkRequest(
            QUrl(url)
        )

        request.setRawHeader(
            b"User-Agent",
            b"QMD Tools Explorer",
        )

        request.setRawHeader(
            b"Accept",
            b"application/json",
        )

        reply = QgsNetworkAccessManager.blockingGet(
            request,
            "",
            True,
        )

        if reply.error() != 0:
            raise RuntimeError(
                reply.errorString()
                or "Erro de rede ao consultar o serviço CAR."
            )

        data = bytes(reply.content())

        if not data:
            raise RuntimeError(
                "O serviço CAR retornou uma resposta vazia."
            )

        return json.loads(
            data.decode("utf-8-sig")
        )

    def run(self):
        try:
            for index, url in enumerate(self.urls, start=1):

                if self.isCanceled():
                    return False

                self.requested_urls = index

                try:
                    response = self._get_json(url)

                    if not isinstance(response, dict):
                        continue

                    features = response.get(
                        "features",
                        [],
                    )

                    if not isinstance(features, list):
                        continue

                    self.geojson["features"].extend(
                        features
                    )

                    self.successful_requests += 1

                except Exception as error:
                    # Uma UF sem resposta não deve impedir que as
                    # demais sejam consultadas.
                    log_message(
                        "CAR BBOX: erro em uma camada: "
                        f"{error}"
                    )

                    continue

            if self.isCanceled():
                return False

            if not self.geojson["features"]:
                # Não tratar ausência de feições como erro.
                # O resultado válido pode simplesmente ser vazio.
                return True

            return True

        except Exception as error:
            self.error = str(error)
            return False

    def finished(self, result):
        if self.owner is not None:
            self.owner._car_bbox_finished(
                self
            )


class _CARCodeTask(QgsTask):
    """Busca um imóvel CAR em segundo plano para não travar o QGIS."""

    def __init__(self, url, code, owner):
        super().__init__(
            f"Buscar imóvel CAR {code}",
            QgsTask.CanCancel,
        )
        self.url = url
        self.code = code
        self.owner = owner
        self.geojson = None
        self.geojson_path = None
        self.error = None

    def run(self):
        try:
            # Usa a infraestrutura de rede do próprio QGIS.
            # Isso evita o urllib/OpenSSL do Python embutido no QGIS,
            # que pode falhar no Windows com SSLV3_ALERT_HANDSHAKE_FAILURE.
            request = QNetworkRequest(QUrl(self.url))
            request.setRawHeader(
                b"User-Agent",
                b"QMD Tools Explorer",
            )
            request.setRawHeader(
                b"Accept",
                b"application/json",
            )

            reply = QgsNetworkAccessManager.blockingGet(
                request,
                "",
                True,
            )

            if self.isCanceled():
                return False

            if reply.error() != 0:
                self.error = (
                    reply.errorString()
                    or "Erro de rede ao consultar o serviço CAR."
                )
                return False

            data = bytes(reply.content())

            if not data:
                self.error = "O serviço CAR retornou uma resposta vazia."
                return False

            # Mantém o GeoJSON em arquivo temporário e deixa o driver
            # OGR do QGIS interpretar a geometria. Para a busca por código,
            # isso evita a etapa pesada de reconstrução manual do GeoJSON.
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".geojson",
                delete=False,
            ) as arquivo:
                arquivo.write(data)
                self.geojson_path = arquivo.name

            return True

        except Exception as error:
            self.error = str(error)

            if self.geojson_path:
                try:
                    os.remove(self.geojson_path)
                except OSError:
                    pass

                self.geojson_path = None

            return False

    def finished(self, result):
        if self.owner is not None:
            self.owner._car_code_finished(self)



__all__ = [
    "LayersWidget"
]
