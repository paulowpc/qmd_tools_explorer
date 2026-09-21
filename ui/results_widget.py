# -*- coding: utf-8 -*-

from io import BytesIO
from qgis.PyQt.QtGui import QFont

import requests
from PIL import Image, ImageEnhance

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QImage, QPixmap

from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QDialog,
    QComboBox,
    QHeaderView,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsRectangle,
    QgsProject,
)

from qgis.utils import iface

from ..core.stac_core import (
    log_message,
    get_satellite_name,
)

from ..core.vrt_core import generate_individual_vrts
from ..core.mosaic_core import create_mosaics_from_groups
from ..config.config import load_collections

from ..utils.footprint import add_footprints


class ResultsWidget(QWidget):

    def __init__(self, parent=None, roi_manager=None):

        super().__init__(parent)

        self.roi_manager = roi_manager
        self.items = []
        self.output_dir = ""
        self.satellite_hint = ""

        self._build_ui()

    # =========================================================
    # INTERFACE
    # =========================================================

    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            6,
            6,
            6,
            6,
        )

        layout.setSpacing(5)

        # -----------------------------------------------------
        # CONTADOR
        # -----------------------------------------------------

        self.count = QLabel(
            "Nenhuma busca realizada."
        )

        layout.addWidget(
            self.count
        )

        # -----------------------------------------------------
        # TABELA
        # -----------------------------------------------------

        self.table = QTableWidget()

        # Fonte do conteúdo da tabela
        font = QFont()
        font.setPointSize(9)
        self.table.setFont(font)

        # Fonte do cabeçalho
        header_font = QFont()
        header_font.setPointSize(9)
        header_font.setBold(True)
        self.table.horizontalHeader().setFont(header_font)

        self.table.setColumnCount(10)

        self.table.setHorizontalHeaderLabels([
            "",                    # 0
            "Data",                # 1
            "Tile",                # 2
            "ROI (%)",             # 3
            "Nuvem (%)",           # 4
            "Satélite",            # 5
            "Sensor",              # 6
            "Composição",          # 7
            "Thumbnail",           # 8
            "Cena",                # 9
        ])

        
        # self.table.setHorizontalHeaderLabels([
        #     "",                    # 0
        #     "Data",                # 1
        #     "Satélite",            # 2
        #     "Sensor",              # 3
        #     "Tile",                # 4
        #     "ROI (%)",             # 5
        #     "Nuvem (%)",           # 6
        #     "Composição",          # 7
        #     "Thumbnail",           # 8
        #     "Cena",                # 9
        # ])

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.ExtendedSelection
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setWordWrap(
            False
        )

        self.table.setHorizontalScrollMode(
            QTableWidget.ScrollPerPixel
        )

        self.table.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        layout.addWidget(
            self.table,
            1,
        )

        # -----------------------------------------------------
        # CABEÇALHO DA TABELA
        # -----------------------------------------------------

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            QHeaderView.Interactive
        )

        header.setSectionResizeMode(
            9,
            QHeaderView.Stretch
        )

        header.setStretchLastSection(
            True
        )

        # -----------------------------------------------------
        # LARGURAS INICIAIS
        # -----------------------------------------------------

        self.table.setColumnWidth(
            0,
            32,
        )

        self.table.setColumnWidth(
            1,
            80,
        )

        self.table.setColumnWidth(
            2,
            80,
        )

        self.table.setColumnWidth(
            3,
            50,
        )

        self.table.setColumnWidth(
            4,
            80,
        )

        self.table.setColumnWidth(
            5,
            70,
        )

        self.table.setColumnWidth(
            6,
            115,
        )

        self.table.setColumnWidth(
            7,
            115,
        )

        # Largura da coluna Cena
        self.table.setColumnWidth(
            9,
            88,
        )

        # -----------------------------------------------------
        # PRIMEIRA LINHA DE BOTÕES
        # -----------------------------------------------------

        buttons_row_1 = QHBoxLayout()

        buttons_row_1.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        buttons_row_1.setSpacing(
            5
        )

        self.select_all = QPushButton(
            "Selecionar Tudo"
        )

        self.clear = QPushButton(
            "Limpar Seleção"
        )

        self.add_selected_footprints_btn = QPushButton(
            "Add select footprint(s)"
        )

        self.add_all_footprints_btn = QPushButton(
            "Add all footprint(s)"
        )

        buttons_row_1.addWidget(
            self.select_all
        )

        buttons_row_1.addWidget(
            self.clear
        )

        buttons_row_1.addWidget(
            self.add_selected_footprints_btn
        )

        buttons_row_1.addWidget(
            self.add_all_footprints_btn
        )

        layout.addLayout(
            buttons_row_1
        )

        # -----------------------------------------------------
        # ÁREA DE PROCESSAMENTO
        # -----------------------------------------------------

        area_layout = QVBoxLayout()

        area_layout.setContentsMargins(
            0,
            4,
            0,
            0,
        )

        area_layout.setSpacing(
            2
        )

        area_label = QLabel(
            "Área:"
        )

        area_label.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
            }
            """
        )

        self.full_scene_radio = QRadioButton(
            "Cena completa"
        )

        self.extent_clip_radio = QRadioButton(
            "Recortar pela Região de Interesse"
        )

        self.roi_info = QLabel(
            "Nenhuma Região de Interesse capturada."
        )
        self.roi_info.setWordWrap(True)

        # # Cena completa é o padrão
        # self.full_scene_radio.setChecked(
        #     True
        # )
        
        # # Cena pelo extent como padrão
        self.extent_clip_radio.setChecked(True)

        # Grupo exclusivo
        self.area_group = QButtonGroup(
            self
        )

        self.area_group.addButton(
            self.full_scene_radio
        )

        self.area_group.addButton(
            self.extent_clip_radio
        )

        area_layout.addWidget(
            area_label
        )

        area_layout.addWidget(
            self.full_scene_radio
        )

        area_layout.addWidget(
            self.extent_clip_radio
        )

        area_layout.addWidget(
            self.roi_info
        )

        layout.addLayout(
            area_layout
        )

        # -----------------------------------------------------
        # SEGUNDA LINHA DE BOTÕES
        # -----------------------------------------------------

        buttons_row_2 = QHBoxLayout()

        buttons_row_2.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        buttons_row_2.setSpacing(
            5
        )

        self.mosaic = QCheckBox(
            "Criar mosaico por data/órbita"
        )

        self.process = QPushButton(
            "Processar Selecionadas"
        )

        # Limpar Pesquisa fica na área de processamento para não aumentar
        # a largura mínima exigida pela primeira linha de botões.
        self.clear_search_btn = QPushButton(
            "Limpar Pesquisa"
        )

        buttons_row_2.addWidget(
            self.mosaic
        )

        buttons_row_2.addStretch()

        buttons_row_2.addWidget(
            self.clear_search_btn
        )

        buttons_row_2.addWidget(
            self.process
        )

        layout.addLayout(
            buttons_row_2
        )

        # -----------------------------------------------------
        # CONEXÕES
        # -----------------------------------------------------

        self.clear_search_btn.clicked.connect(
            self.clear_search
        )

        self.select_all.clicked.connect(
            self.select_all_items
        )

        self.clear.clicked.connect(
            self.clear_selection
        )

        self.add_selected_footprints_btn.clicked.connect(
            self.add_selected_footprints
        )

        self.add_all_footprints_btn.clicked.connect(
            self.add_all_footprints
        )

        self.process.clicked.connect(
            self.process_selected
        )

        if self.roi_manager is not None:
            self.roi_manager.roi_changed.connect(
                self._update_roi_info
            )
            self._update_roi_info(
                self.roi_manager.get_bbox()
            )

    # =========================================================
    # REGIÃO DE INTERESSE
    # =========================================================

    def _update_roi_info(self, bbox):
        """Atualiza a informação da Região de Interesse."""
        if bbox is None:
            self.roi_info.setText(
                "Nenhuma Região de Interesse capturada."
            )
            return

        self.roi_info.setText(
            "✓ Região de Interesse capturada: "
            f"[{bbox[0]:.8f}, {bbox[1]:.8f}, "
            f"{bbox[2]:.8f}, {bbox[3]:.8f}]"
        )

    def _get_roi_extent_wgs84(self):
        """Retorna o BBOX fixado no ROIManager como QgsRectangle."""
        if self.roi_manager is None:
            return None

        bbox = self.roi_manager.get_bbox()

        if not bbox:
            return None

        try:
            return QgsRectangle(
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )

        except Exception as e:
            log_message(
                f"[ÁREA] Erro ao converter Região de "
                f"Interesse para QgsRectangle: {e}"
            )
            return None

    # =========================================================
    # OBTÉM EXTENT ATUAL DO MAPA EM EPSG:4326
    # =========================================================

    def _get_canvas_extent_wgs84(self):

        canvas = iface.mapCanvas()

        source_extent = canvas.extent()

        source_crs = canvas.mapSettings().destinationCrs()

        wgs84 = QgsCoordinateReferenceSystem(
            "EPSG:4326"
        )

        # Se o canvas já estiver em WGS84
        if source_crs == wgs84:

            return source_extent

        try:

            transform = QgsCoordinateTransform(
                source_crs,
                wgs84,
                QgsProject.instance(),
            )

            return transform.transformBoundingBox(
                source_extent
            )

        except Exception as e:

            log_message(
                f"[ÁREA] Erro ao obter Extent "
                f"em EPSG:4326: {e}"
            )

            return None

    # =========================================================
    # IDENTIFICA SATÉLITE E SENSOR
    # =========================================================

    def _get_satellite_and_sensor(
        self,
        item,
        collection,
    ):

        if collection == "Sentinel 2":

            satellite = get_satellite_name(
                item,
                "Sentinel-2"
            )

            return satellite, "MSI"

        if collection == "Landsat 2":

            satellite = get_satellite_name(
                item,
                "Landsat"
            )

            return satellite, "OLI"

        if collection == "Amazonia-1/WFI":

            return "Amazônia-1", "WFI"

        if collection == "CBERS-4/WFI":

            return "CBERS-4", "WFI"

        if collection == "CBERS-4/MUX":

            return "CBERS-4", "MUX"

        if collection == "CBERS-4A/WFI":

            return "CBERS-4A", "WFI"

        if collection == "CBERS-4A/MUX":

            return "CBERS-4A", "MUX"

        return collection, "N/A"

    # =========================================================
    # TILE / ÓRBITA-PONTO
    # =========================================================

    def _get_tile_value(
        self,
        item,
        collection,
    ):

        properties = item.properties or {}

        tiles = properties.get(
            "bdc:tiles"
        )

        if tiles:

            if isinstance(
                tiles,
                list
            ):
                return str(
                    tiles[0]
                )

            return str(
                tiles
            )

        path = properties.get(
            "path"
        )

        row = properties.get(
            "row"
        )

        if (
            path is not None
            and row is not None
        ):

            path = str(
                path
            ).zfill(3)

            row = str(
                row
            ).zfill(3)

            return f"{path}_{row}"

        return "N/A"

    # =========================================================
    # NUVEM
    # =========================================================

    def _get_cloud_cover(
        self,
        item,
    ):

        cloud = item.properties.get(
            "eo:cloud_cover"
        )

        if cloud is None:

            return "N/A"

        try:

            return (
                f"{float(cloud):.2f}"
            )

        except Exception:

            return str(
                cloud
            )

    # =========================================================
    # COMPOSIÇÕES DISPONÍVEIS
    # =========================================================

    def _get_composites(
        self,
        collection,
    ):

        collections = load_collections()

        config = collections.get(
            collection,
            {}
        )

        return config.get(
            "composites",
            {}
        )

    # =========================================================
    # NOME AMIGÁVEL DA COMPOSIÇÃO
    # =========================================================

    def _composite_label(
        self,
        composite_name,
    ):

        labels = {

            "truecolor": "True Color",

            "falsecolor_1": "False Color 1",

            "falsecolor_2": "False Color 2",

        }

        return labels.get(
            composite_name,
            composite_name,
        )

    # =========================================================
    # COMBOBOX DE COMPOSIÇÃO
    # =========================================================

    def _create_composite_combobox(
        self,
        collection,
    ):

        combo = QComboBox()

        composites = self._get_composites(
            collection
        )

        for composite_name in composites.keys():

            combo.addItem(
                self._composite_label(
                    composite_name
                ),
                composite_name,
            )

        index = combo.findData(
            "falsecolor_1"
        )

        if index >= 0:

            combo.setCurrentIndex(
                index
            )

        return combo

    # =========================================================
    # RESULTADOS
    # =========================================================

    def set_results(
        self,
        items,
        output_dir,
    ):

        self.items = items or []

        self.output_dir = output_dir or ""

        self.table.setRowCount(
            len(self.items)
        )

        self.count.setText(
            f"Imagens Disponíveis: {len(self.items)}"
        )

        for row, item in enumerate(
            self.items
        ):

            collection = item.properties.get(
                "_bdc_collection_name",
                "N/A",
            )

            if item.datetime:

                date = item.datetime.strftime(
                    "%Y-%m-%d"
                )

            else:

                date = "N/A"

            satellite, sensor = (
                self._get_satellite_and_sensor(
                    item,
                    collection,
                )
            )

            tile = self._get_tile_value(
                item,
                collection,
            )

            cloud = self._get_cloud_cover(
                item
            )

            checkbox = QCheckBox()

            checkbox.setStyleSheet(
                """
                QCheckBox {
                    margin-left: 6px;
                }
                """
            )

            # -----------------------------------------------------
            # CHECKBOX
            # -----------------------------------------------------

            self.table.setCellWidget(
                row,
                0,
                checkbox,
            )

            # -----------------------------------------------------
            # DATA
            # -----------------------------------------------------

            date_item = QTableWidgetItem(
                str(date)
            )

            date_item.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                1,
                date_item,
            )

            # -----------------------------------------------------
            # TILE
            # -----------------------------------------------------

            tile_item = QTableWidgetItem(
                str(tile)
            )

            tile_item.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                2,
                tile_item,
            )

            # -----------------------------------------------------
            # ROI (%)
            # -----------------------------------------------------

            coverage = item.properties.get(
                "_qmd_roi_coverage"
            )

            if coverage is None:
                coverage_text = "N/A"
            else:
                try:
                    coverage_text = (
                        f"{float(coverage):.1f}%"
                    )
                except Exception:
                    coverage_text = "N/A"

            coverage_item = QTableWidgetItem(
                coverage_text
            )

            coverage_item.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                3,
                coverage_item,
            )

            # -----------------------------------------------------
            # NUVEM (%)
            # -----------------------------------------------------

            cloud_item = QTableWidgetItem(
                str(cloud)
            )

            cloud_item.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                4,
                cloud_item,
            )

            # -----------------------------------------------------
            # SATÉLITE
            # -----------------------------------------------------

            satellite_item = QTableWidgetItem(
                str(satellite)
            )

            self.table.setItem(
                row,
                5,
                satellite_item,
            )

            # -----------------------------------------------------
            # SENSOR
            # -----------------------------------------------------

            sensor_item = QTableWidgetItem(
                str(sensor)
            )

            sensor_item.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                6,
                sensor_item,
            )

            # -----------------------------------------------------
            # COMPOSIÇÃO
            # -----------------------------------------------------

            combo = self._create_composite_combobox(
                collection
            )

            self.table.setCellWidget(
                row,
                7,
                combo,
            )

            # -----------------------------------------------------
            # THUMBNAIL
            # -----------------------------------------------------

            thumb = item.assets.get(
                "thumbnail"
            )

            href = (
                thumb.href
                if thumb
                else None
            )

            if (
                isinstance(href, str)
                and href.startswith("http")
            ):

                button = QPushButton(
                    "Visualizar"
                )

                button.clicked.connect(
                    self._thumbnail_callback(
                        href,
                        collection,
                        date,
                    )
                )

                self.table.setCellWidget(
                    row,
                    8,
                    button,
                )

            else:

                self.table.setItem(
                    row,
                    8,
                    QTableWidgetItem(
                        "N/A"
                    ),
                )

            scene_item = QTableWidgetItem(
                item.id
            )

            scene_item.setToolTip(
                item.id
            )

            self.table.setItem(
                row,
                9,
                scene_item,
            )
    # ======================================================
    # LIMPAR PESQUISA
    # ======================================================

    def clear_search(self):

        self.table.setRowCount(0)

        self.items = []

        self.count.setText(
            "Nenhuma busca realizada."
        )

        if hasattr(self, "selected_items"):

            self.selected_items = []

        # self.count_label.setText(
        #     "Imagens Disponíveis: 0"
        # )

        self.extent_clip_radio.setChecked(True)

        if hasattr(self, "check_mosaic"):

            self.check_mosaic.setChecked(False)

        print(
            "[RESULTADOS] Pesquisa limpa."
        )

    # =========================================================
    # THUMBNAIL
    # =========================================================

    def _thumbnail_callback(
        self,
        url,
        collection,
        date,
    ):

        def cb():

            try:

                r = requests.get(
                    url,
                    timeout=15,
                )

                r.raise_for_status()

                img = Image.open(
                    BytesIO(
                        r.content
                    )
                )

                if collection == "Landsat 2":

                    img = (
                        ImageEnhance.Contrast(
                            ImageEnhance.Brightness(
                                img
                            ).enhance(
                                6.0
                            )
                        ).enhance(
                            0.7
                        )
                    )

                elif collection == "Sentinel 2":

                    img = (
                        ImageEnhance.Contrast(
                            ImageEnhance.Brightness(
                                img
                            ).enhance(
                                2.5
                            )
                        ).enhance(
                            1.8
                        )
                    )

                q = QImage.fromData(
                    BytesIO(
                        self._png(
                            img
                        )
                    ).getvalue()
                )

                pix = QPixmap.fromImage(
                    q
                )

                dlg = QDialog(
                    iface.mainWindow()
                )

                dlg.setWindowTitle(
                    f"Thumbnail - {date}"
                )

                dlg.resize(
                    550,
                    550,
                )

                lay = QVBoxLayout(
                    dlg
                )

                lab = QLabel()

                lab.setAlignment(
                    Qt.AlignCenter
                )

                lab.setPixmap(
                    pix.scaled(
                        800,
                        800,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

                lay.addWidget(
                    lab
                )

                dlg.exec_()

            except Exception as e:

                log_message(
                    f"Erro ao processar thumbnail: {e}"
                )

        return cb

    # =========================================================
    # PNG
    # =========================================================

    @staticmethod
    def _png(img):

        buffer = BytesIO()

        img.save(
            buffer,
            format="PNG",
        )

        return buffer.getvalue()

    # =========================================================
    # SELEÇÃO POR CHECKBOX
    # =========================================================

    def select_all_items(self):

        for row in range(
            self.table.rowCount()
        ):

            checkbox = self.table.cellWidget(
                row,
                0,
            )

            if checkbox is not None:

                checkbox.setChecked(
                    True
                )

    def clear_selection(self):

        for row in range(
            self.table.rowCount()
        ):

            checkbox = self.table.cellWidget(
                row,
                0,
            )

            if checkbox is not None:

                checkbox.setChecked(
                    False
                )

        self.table.clearSelection()

    def get_checked_items(self):

        selected = []

        for row in range(
            self.table.rowCount()
        ):

            checkbox = self.table.cellWidget(
                row,
                0,
            )

            if checkbox is None:

                continue

            if checkbox.isChecked():

                selected.append(
                    (
                        row,
                        self.items[row],
                    )
                )

        return selected

    # =========================================================
    # ADICIONAR FOOTPRINTS SELECIONADOS
    # =========================================================

    def add_selected_footprints(self):

        selected = self.get_checked_items()

        if not selected:

            log_message(
                "[FOOTPRINT] Nenhuma imagem selecionada."
            )

            return

        items = [
            item
            for row, item in selected
        ]

        log_message(
            f"[FOOTPRINT] Adicionando "
            f"{len(items)} footprint(s) selecionado(s)."
        )

        try:

            add_footprints(
                items
            )

        except Exception as e:

            log_message(
                f"[FOOTPRINT] Erro ao adicionar "
                f"footprints selecionados: {e}"
            )

    # =========================================================
    # ADICIONAR TODOS OS FOOTPRINTS
    # =========================================================

    def add_all_footprints(self):

        if not self.items:

            log_message(
                "[FOOTPRINT] Nenhuma imagem disponível."
            )

            return

        log_message(
            f"[FOOTPRINT] Adicionando todos os "
            f"{len(self.items)} footprint(s)."
        )

        try:

            add_footprints(
                self.items
            )

        except Exception as e:

            log_message(
                f"[FOOTPRINT] Erro ao adicionar "
                f"todos os footprints: {e}"
            )

    # =========================================================
    # PROCESSAR SELECIONADAS
    # =========================================================

    def process_selected(self):

        selected = self.get_checked_items()

        if not selected:

            log_message(
                "Nenhuma imagem selecionada."
            )

            return

        # -----------------------------------------------------
        # CONFIGURAÇÃO DA ÁREA
        # -----------------------------------------------------

        clip_extent = None

        if self.extent_clip_radio.isChecked():

            # Usa o BBOX fixado na Região de Interesse.
            # Não usa mais o extent atual do canvas.
            clip_extent = self._get_roi_extent_wgs84()

            if clip_extent is None:

                log_message(
                    "[ÁREA] Nenhuma Região de Interesse "
                    "foi capturada."
                )

                QMessageBox.warning(
                    self,
                    "Região de Interesse",
                    "Nenhuma Região de Interesse foi capturada.\n\n"
                    "Volte à aba Busca, selecione a região desejada "
                    "e clique em 'Capturar'."
                )

                return

            log_message(
                "[ÁREA] Recorte pela Região de Interesse ativado."
            )

            log_message(
                f"[ÁREA] BBOX fixado: "
                f"{clip_extent.xMinimum():.8f}, "
                f"{clip_extent.yMinimum():.8f}, "
                f"{clip_extent.xMaximum():.8f}, "
                f"{clip_extent.yMaximum():.8f}"
            )

        else:

            log_message(
                "[ÁREA] Processando cena completa."
            )

        # -----------------------------------------------------
        # AGRUPA POR COLEÇÃO E COMPOSIÇÃO
        # -----------------------------------------------------

        grouped = {}

        for row, item in selected:

            collection = item.properties.get(
                "_bdc_collection_name"
            )

            combo = self.table.cellWidget(
                row,
                7,
            )

            composite_name = (
                combo.currentData()
                if combo
                else "falsecolor_1"
            )

            key = (
                collection,
                composite_name,
            )

            grouped.setdefault(
                key,
                [],
            ).append(
                item
            )

        # -----------------------------------------------------
        # PROCESSA
        # -----------------------------------------------------

        collections = load_collections()

        for (
            collection,
            composite_name,
        ), items in grouped.items():

            # -------------------------------------------------
            # DEFINE FAMÍLIA
            # -------------------------------------------------

            family_map = {

                "Landsat 2": "Landsat",

                "Sentinel 2": "Sentinel-2",

                "Amazonia-1/WFI": "Amazonia-1",

                "CBERS-4/WFI": "CBERS-4",
                "CBERS-4/MUX": "CBERS-4",

                "CBERS-4A/WFI": "CBERS-4A",
                "CBERS-4A/MUX": "CBERS-4A",
            }

            family = family_map.get(
                collection
            )

            if family is None:

                log_message(
                    f"[VRT] {collection}: "
                    "processamento ainda não configurado."
                )

                continue

            # -------------------------------------------------
            # BANDAS DA COMPOSIÇÃO
            # -------------------------------------------------

            bands = (
                collections
                .get(
                    collection,
                    {},
                )
                .get(
                    "composites",
                    {},
                )
                .get(
                    composite_name,
                    [],
                )
            )

            if not bands:

                log_message(
                    f"[VRT] Nenhuma banda encontrada "
                    f"para {collection} / "
                    f"{composite_name}."
                )

                continue

            # -------------------------------------------------
            # DIRETÓRIO DE SAÍDA
            # -------------------------------------------------

            out = (
                f"{self.output_dir}/"
                f"{collection.replace('/', '_').replace(' ', '_')}"
            )

            log_message(
                f"[VRT] Processando "
                f"{collection} | "
                f"{composite_name}"
            )

            log_message(
                f"[VRT] Família: {family} | "
                f"Bandas: {', '.join(bands)}"
            )

            # -------------------------------------------------
            # GERA VRT
            # -------------------------------------------------

            groups = generate_individual_vrts(
                family,
                bands,
                items,
                out,
                create_mosaic=self.mosaic.isChecked(),
                clip_extent=clip_extent,
            )

            # -------------------------------------------------
            # MOSAICO
            # -------------------------------------------------

            if self.mosaic.isChecked():

                create_mosaics_from_groups(
                    family,
                    groups,
                    out,
                )