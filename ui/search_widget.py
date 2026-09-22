# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from pathlib import Path
import json
import urllib.request
import shutil

from qgis.PyQt.QtGui import QIcon

from qgis.PyQt.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QGroupBox,
    QCheckBox,
    QLineEdit,
    QPushButton,
    QDateTimeEdit,
    QMessageBox,
    QFileDialog,
    QToolButton,
    QLabel,
    QComboBox,
    QSizePolicy,
    QScrollArea,
    QAbstractScrollArea,
)

from qgis.PyQt.QtCore import (
    QDate,
    pyqtSignal,
    Qt,
)

from qgis.utils import iface

from qgis.gui import QgsMapToolExtent

from qgis.core import (
    QgsApplication,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsRectangle,
    QgsWkbTypes,
    QgsGeometry,
    QgsFeature,
)

from ..config.config import (
    load_collections,
    STAC_URL,
    get_output_dir,
    get_saved_output_dir,
    save_output_dir,
    get_cache_dir,
    clear_cache,
)

from ..core.stac_core import (
    connect_to_stac,
    search_items,
    search_items_by_bbox,
    log_message,
)

from ..core.dependencies import check_dependencies

from ..utils.extent import (
    get_canvas_bbox,
)

from ..core.roi_manager import ROIManager


class SearchWidget(QWidget):

    search_requested = pyqtSignal(object)

    def __init__(self, parent=None, roi_manager=None):

        super().__init__(parent)

        self.roi_manager = (
            roi_manager
            if roi_manager is not None
            else ROIManager(self)
        )

        # O conteúdo da Busca pode ser maior que a área disponível.
        # A altura deve ser determinada pelo dock, não pelo conteúdo.
        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self.collections = load_collections()

        # Ferramenta de desenho da Região de Interesse no canvas.
        self._roi_draw_tool = None
        self._roi_previous_map_tool = None

        self._build_ui()


    # ==========================================================
    # INTERFACE
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
            """
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
            """
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

    def _build_ui(self):

        # ======================================================
        # ÁREA PRINCIPAL COM ROLAGEM
        # ======================================================

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        outer_layout.setSpacing(0)

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
            6,
            5,
            6,
            5,
        )

        layout.setSpacing(4)

        outer_layout.addWidget(
            scroll
        )

        scroll.setWidget(
            content_widget
        )


        # ======================================================
        # COLEÇÕES
        # ======================================================

        group = QGroupBox(
            "Coleções de Imagens - Brasil Data Cube / INPE"
        )

        grid = QGridLayout(group)
        grid.setContentsMargins(6, 5, 6, 5)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)

        self.checkboxes = {}

        for i, name in enumerate(self.collections):

            cb = QCheckBox(name)

            cb.setChecked(
                i == 0
            )

            self.checkboxes[name] = cb

            grid.addWidget(
                cb,
                i // 3,
                i % 3,
            )

        layout.addWidget(
            group
        )


        # ======================================================
        # FORMULÁRIO
        # ======================================================

        form = QFormLayout()

        form.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        form.setSpacing(4)


        # ------------------------------------------------------
        # TILE / ÓRBITA-PONTO
        # ------------------------------------------------------

        self.tile = QLineEdit()
        self.tile.setFixedHeight(27)

        self.tile.setPlaceholderText(
            "Ex.: 223067 ou 22LCK"
        )

        form.addRow(
            "Tile / Órbita-Ponto:",
            self.tile,
        )


        # ------------------------------------------------------
        # DATAS
        # ------------------------------------------------------

        hoje = datetime.today()

        inicio = (
            hoje
            - timedelta(days=8)
        )


        self.start = QDateTimeEdit(
            QDate(
                inicio.year,
                inicio.month,
                inicio.day,
            )
        )

        self.start.setDisplayFormat(
            "yyyy-MM-dd"
        )
        self.start.setFixedHeight(27)

        self.start.setCalendarPopup(
            True
        )


        self.end = QDateTimeEdit(
            QDate(
                hoje.year,
                hoje.month,
                hoje.day,
            )
        )

        self.end.setDisplayFormat(
            "yyyy-MM-dd"
        )
        self.end.setFixedHeight(27)

        self.end.setCalendarPopup(
            True
        )


        form.addRow(
            "Data de Início:",
            self.start,
        )

        form.addRow(
            "Data de Fim:",
            self.end,
        )


        # ------------------------------------------------------
        # DIRETÓRIO DE SAÍDA
        # ------------------------------------------------------

        out_row = QHBoxLayout()

        out_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.output = QLineEdit()

        self.output.setFixedHeight(27)

        saved_output = get_saved_output_dir()

        if saved_output:
            self.output.setText(saved_output)
        else:
            self.output.setPlaceholderText(
                "System temp (default)"
            )


        choose = QToolButton()

        choose.setIcon(
            QgsApplication.getThemeIcon(
                "/mActionFileOpen.svg"
            )
        )

        choose.setToolTip(
            "Selecionar diretório de saída"
        )

        choose.setAutoRaise(
            False
        )

        choose.setFixedWidth(
            32
        )

        self.clear_cache_btn = QToolButton()
        self.clear_cache_btn.setText(
            "Limpar cache"
        )
        self.clear_cache_btn.setToolTip(
            "Apagar os arquivos do cache padrão do QMD Tools Explorer"
        )
        self.clear_cache_btn.setIcon(
            QgsApplication.getThemeIcon(
                "/mActionDeleteSelected.svg"
            )
        )
        self.clear_cache_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.clear_cache_btn.setFixedHeight(
            28
        )


        out_row.addWidget(
            self.output
        )

        out_row.addWidget(
            choose
        )

        out_row.addWidget(
            self.clear_cache_btn
        )


        form.addRow(
            "Diretório de Saída:",
            out_row,
        )


        choose.clicked.connect(
            self.choose_output
        )

        self.clear_cache_btn.clicked.connect(
            self.clear_cache_clicked
        )


        layout.addLayout(
            form
        )


        # ======================================================
        # REGIÃO DE INTERESSE
        # ======================================================

        roi_group = QGroupBox(
            "Região de Interesse"
        )

        roi_layout = QVBoxLayout(
            roi_group
        )

        roi_layout.setContentsMargins(
            6,
            5,
            6,
            5,
        )

        roi_row = QHBoxLayout()

        self.roi_source = QComboBox()
        self.roi_source.addItem(
            "Map Canvas Extent",
            "canvas",
        )
        self.roi_source.addItem(
            "Layers Extent",
            "layer",
        )

        roi_row.addWidget(
            self.roi_source,
            1
        )

        self.roi_capture_btn = QPushButton(
            "Capturar"
        )
        self.roi_capture_btn.setFixedHeight(28)

        self.roi_clear_btn = QPushButton(
            "Limpar Região de Interesse"
        )
        self.roi_clear_btn.setFixedHeight(28)

        self.roi_draw_btn = QPushButton(
            "Desenhar no mapa"
        )
        self.roi_draw_btn.setFixedHeight(28)
        self.roi_draw_btn.setToolTip(
            "Desenha um retângulo diretamente no mapa para definir a Região de Interesse."
        )

        roi_row.addWidget(
            self.roi_capture_btn
        )

        roi_row.addWidget(
            self.roi_draw_btn
        )

        roi_layout.addLayout(
            roi_row
        )

        # ------------------------------------------------------
        # CAMADA DA REGIÃO DE INTERESSE
        # ------------------------------------------------------

        self.roi_layer_combo = QComboBox()
        self.roi_layer_combo.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        self.roi_selected_features = QCheckBox(
            "Selected features only"
        )

        roi_layout.addWidget(
            self.roi_layer_combo
        )

        self.roi_buffer_label = QLabel(
            "Buffer da Região de Interesse:"
        )

        self.roi_buffer_combo = QComboBox()
        self.roi_buffer_combo.addItem(
            "Sem buffer",
            0,
        )
        self.roi_buffer_combo.addItem(
            "500 m",
            500,
        )
        self.roi_buffer_combo.addItem(
            "1 km",
            1000,
        )
        # 500 m como padrão para Layer Extent.
        self.roi_buffer_combo.setCurrentIndex(1)

        buffer_row = QHBoxLayout()
        buffer_row.addWidget(
            self.roi_buffer_label
        )
        buffer_row.addWidget(
            self.roi_buffer_combo,
            1,
        )
        roi_layout.addLayout(buffer_row)

        roi_layout.addWidget(
            self.roi_selected_features
        )

        self._populate_roi_layers()

        self.roi_source.currentIndexChanged.connect(
            self._roi_source_changed
        )

        self.roi_layer_combo.currentIndexChanged.connect(
            self._roi_layer_changed
        )

        self.roi_selected_features.toggled.connect(
            self._roi_features_option_changed
        )

        self.roi_status = QLabel(
            "Nenhuma região capturada."
        )

        self.roi_status.setWordWrap(
            True
        )

        self.roi_status.setStyleSheet(
            """
            QLabel {
                padding: 5px;
                background: #f0f0f0;
                border-radius: 2px;
            }
            """
        )

        roi_layout.addWidget(
            self.roi_status
        )

        # Botão de limpeza fica abaixo do status da ROI,
        # deixando a linha principal dedicada à captura/desenho.
        roi_layout.addWidget(
            self.roi_clear_btn
        )

        layout.addWidget(
            roi_group
        )

        # ======================================================
        # PESQUISAR IMAGENS
        # ======================================================

        self.search_btn = QPushButton(
            "🔍 Pesquisar Imagens"
        )

        self.search_btn.setFixedHeight(
            32
        )

        layout.addWidget(
            self.search_btn
        )

        # ======================================================
        # ESPAÇO FINAL
        # ======================================================

        layout.addStretch()

        # ======================================================
        # CONEXÕES
        # ======================================================

        self.roi_capture_btn.clicked.connect(
            self.capture_roi
        )

        self.roi_clear_btn.clicked.connect(
            self.clear_roi
        )

        self.roi_draw_btn.clicked.connect(
            self.start_draw_roi
        )

        self.roi_manager.roi_changed.connect(
            self._update_roi_status
        )

        self.search_btn.clicked.connect(
            lambda: self.execute_search(False)
        )

        self._roi_source_changed(
            self.roi_source.currentIndex()
        )

        self._update_roi_status(
            self.roi_manager.get_bbox()
        )


    # ==========================================================
    # REGIÃO DE INTERESSE
    # ==========================================================

    def _populate_roi_layers(self):
        """Atualiza a lista com as camadas atualmente carregadas no QGIS."""

        current_id = None

        active_layer = iface.activeLayer()
        if active_layer is not None:
            current_id = active_layer.id()

        self.roi_layer_combo.blockSignals(True)
        self.roi_layer_combo.clear()

        layers = list(
            QgsProject.instance().mapLayers().values()
        )

        for layer in layers:
            # Não oferecer a própria camada temporária da ROI.
            if layer.name() == "ROI - Região de Interesse":
                continue

            self.roi_layer_combo.addItem(
                layer.name(),
                layer.id(),
            )

        if current_id is not None:
            index = self.roi_layer_combo.findData(current_id)
            if index >= 0:
                self.roi_layer_combo.setCurrentIndex(index)

        self.roi_layer_combo.blockSignals(False)
        self._update_roi_features_state()

    def _selected_roi_layer(self):
        layer_id = self.roi_layer_combo.currentData()
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    def _roi_source_changed(self, index):
        is_layer = (
            self.roi_source.currentData() == "layer"
        )

        self.roi_layer_combo.setVisible(is_layer)
        self.roi_selected_features.setVisible(is_layer)
        self.roi_buffer_label.setVisible(is_layer)
        self.roi_buffer_combo.setVisible(is_layer)

        if is_layer:
            self._populate_roi_layers()

        self._update_roi_features_state()

    def _roi_layer_changed(self, index):
        self._update_roi_features_state()

    def _roi_features_option_changed(self, checked):
        self._update_roi_features_state()

    def _update_roi_features_state(self):
        is_layer = (
            self.roi_source.currentData() == "layer"
        )

        layer = self._selected_roi_layer()
        enabled = (
            is_layer
            and layer is not None
            and isinstance(layer, QgsVectorLayer)
        )

        self.roi_selected_features.setEnabled(enabled)

        if not enabled:
            self.roi_selected_features.setChecked(False)

    def _bbox_to_wgs84(self, rectangle, source_crs):
        if rectangle is None or rectangle.isEmpty():
            return None

        wgs84 = QgsCoordinateReferenceSystem(
            "EPSG:4326"
        )

        if source_crs == wgs84:
            return rectangle

        transform = QgsCoordinateTransform(
            source_crs,
            wgs84,
            QgsProject.instance(),
        )

        return transform.transformBoundingBox(
            rectangle
        )

    def _apply_roi_buffer(self, bbox, buffer_meters):
        """Aplica buffer métrico ao BBox WGS84 usando UTM local."""

        if not buffer_meters:
            return bbox

        xmin, ymin, xmax, ymax = bbox

        center_lon = (xmin + xmax) / 2.0
        center_lat = (ymin + ymax) / 2.0

        # Zona UTM correspondente ao centro da ROI.
        zone = int((center_lon + 180.0) / 6.0) + 1
        zone = max(1, min(60, zone))

        if center_lat >= 0:
            epsg = 32600 + zone
        else:
            epsg = 32700 + zone

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem(
            f"EPSG:{epsg}"
        )

        to_utm = QgsCoordinateTransform(
            wgs84,
            utm,
            QgsProject.instance(),
        )
        to_wgs84 = QgsCoordinateTransform(
            utm,
            wgs84,
            QgsProject.instance(),
        )

        geometry = QgsGeometry.fromRect(
            QgsRectangle(xmin, ymin, xmax, ymax)
        )

        result = geometry.transform(to_utm)
        if result != 0:
            raise ValueError(
                "Não foi possível transformar a ROI para aplicar o buffer."
            )

        buffered = geometry.buffer(
            float(buffer_meters),
            8,
        )

        if buffered is None or buffered.isEmpty():
            raise ValueError(
                "Não foi possível aplicar o buffer à Região de Interesse."
            )

        result = buffered.transform(to_wgs84)
        if result != 0:
            raise ValueError(
                "Não foi possível retornar a ROI para EPSG:4326."
            )

        rectangle = buffered.boundingBox()

        return (
            rectangle.xMinimum(),
            rectangle.yMinimum(),
            rectangle.xMaximum(),
            rectangle.yMaximum(),
        )

    def _get_layer_roi_bbox(self):
        layer = self._selected_roi_layer()

        if layer is None:
            raise ValueError(
                "Nenhuma camada foi selecionada para a Região de Interesse."
            )

        if (
            self.roi_selected_features.isChecked()
            and isinstance(layer, QgsVectorLayer)
        ):
            if not layer.selectedFeatureIds():
                raise ValueError(
                    f'A camada "{layer.name()}" não possui feições selecionadas.'
                )

            # Algumas versões do QGIS não expõem
            # boundingBoxOfSelectedFeatures() em QgsVectorLayer.
            # Calculamos o extent diretamente a partir das geometrias
            # das feições selecionadas para manter compatibilidade.
            rectangle = None

            for feature_id in layer.selectedFeatureIds():
                feature = layer.getFeature(feature_id)

                if not feature.isValid():
                    continue

                geometry = feature.geometry()

                if geometry is None or geometry.isEmpty():
                    continue

                feature_rect = geometry.boundingBox()

                if feature_rect.isEmpty():
                    continue

                if rectangle is None:
                    rectangle = QgsRectangle(feature_rect)
                else:
                    rectangle.combineExtentWith(feature_rect)

            if rectangle is None or rectangle.isEmpty():
                raise ValueError(
                    f'Não foi possível obter o extent das feições selecionadas da camada "{layer.name()}".'
                )

        else:
            rectangle = layer.extent()

        bbox_rect = self._bbox_to_wgs84(
            rectangle,
            layer.crs(),
        )

        if bbox_rect is None:
            raise ValueError(
                f'Não foi possível obter o extent da camada "{layer.name()}".'
            )

        bbox = (
            bbox_rect.xMinimum(),
            bbox_rect.yMinimum(),
            bbox_rect.xMaximum(),
            bbox_rect.yMaximum(),
        )

        buffer_meters = self.roi_buffer_combo.currentData() or 0

        if buffer_meters:
            bbox = self._apply_roi_buffer(
                bbox,
                buffer_meters,
            )

        return bbox, layer.name(), buffer_meters

    def capture_roi(self):

        try:
            source = self.roi_source.currentData()

            if source == "canvas":
                bbox = get_canvas_bbox()

                if bbox is None:
                    raise ValueError(
                        "Não foi possível obter o extent do canvas."
                    )

                source_label = "Map Canvas Extent"

            else:
                bbox, layer_name, buffer_meters = (
                    self._get_layer_roi_bbox()
                )

                if self.roi_selected_features.isChecked():
                    source_label = (
                        f"Layers Extent — {layer_name} "
                        "(Selected features only)"
                    )
                else:
                    source_label = (
                        f"Layers Extent — {layer_name}"
                    )

                if buffer_meters:
                    source_label += f" — Buffer {buffer_meters} m"

            self.roi_manager.set_bbox(
                bbox,
                source=source_label,
                canvas_extent=iface.mapCanvas().extent(),
            )

            # A captura também materializa a ROI no QGIS como uma
            # camada vetorial temporária, como no comportamento anterior.
            self._create_or_update_roi_temp_layer(bbox)

            log_message(
                f"[ROI] Região de interesse capturada: {bbox}"
            )

        except Exception as error:

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível capturar a Região de Interesse.\n\n"
                f"{error}"
            )

    def clear_roi(self):

        # Remove a ROI armazenada.
        self.roi_manager.clear()

        if self._roi_draw_tool is not None:
            try:
                self._roi_draw_tool.clearRubberBand()
            except Exception as erro:
                print(
                    f"[QMD Tools Explorer] "
                    f"Não foi possível limpar o desenho da área de interesse: {erro}"
                )

        # Retorna os controles da ROI ao estado inicial.
        # O padrão é voltar para o extent do canvas, sem seleção de
        # feições e sem buffer.
        self.roi_source.setCurrentIndex(0)
        self.roi_buffer_combo.setCurrentIndex(0)
        self.roi_selected_features.setChecked(False)

        # Garante que a interface reflita imediatamente que não há ROI.
        self._update_roi_status(None)

        log_message(
            "[ROI] Região de interesse removida e configurações restauradas."
        )

    def _update_roi_status(self, bbox):

        if bbox is None:
            self.roi_status.setText(
                "Nenhuma região capturada."
            )
            return

        xmin, ymin, xmax, ymax = bbox

        self.roi_status.setText(
            "✓ Região de interesse capturada\n"
            f"BBox: [{xmin:.6f}, {ymin:.6f}, "
            f"{xmax:.6f}, {ymax:.6f}]"
        )

    def _create_or_update_roi_temp_layer(self, bbox):
        """Cria/atualiza a camada temporária correspondente ao BBox da ROI."""

        if bbox is None:
            return

        xmin, ymin, xmax, ymax = bbox

        rectangle = QgsRectangle(
            float(xmin),
            float(ymin),
            float(xmax),
            float(ymax),
        )

        geometry = QgsGeometry.fromRect(
            rectangle
        )

        layer_name = "ROI - Região de Interesse"
        project = QgsProject.instance()

        layer = None
        for candidate in project.mapLayers().values():
            if (
                candidate.name() == layer_name
                and isinstance(candidate, QgsVectorLayer)
            ):
                layer = candidate
                break

        if layer is None:
            layer = QgsVectorLayer(
                "Polygon?crs=EPSG:4326",
                layer_name,
                "memory",
            )

            if not layer.isValid():
                raise ValueError(
                    "Não foi possível criar a camada vetorial temporária."
                )

            project.addMapLayer(layer)

        provider = layer.dataProvider()

        # Mantém uma única feição representando a ROI atual.
        provider.truncate()

        feature = QgsFeature()
        feature.setGeometry(geometry)
        provider.addFeature(feature)

        layer.updateExtents()
        layer.triggerRepaint()

    def start_draw_roi(self):
        """Ativa a ferramenta nativa de desenho de extent do QGIS."""

        canvas = iface.mapCanvas()

        if canvas is None:
            return

        # Guarda a ferramenta atual para restaurá-la após o desenho.
        self._roi_previous_map_tool = canvas.mapTool()

        # Reutiliza a ferramenta enquanto ela existir.
        if self._roi_draw_tool is None:
            self._roi_draw_tool = QgsMapToolExtent(canvas)
            self._roi_draw_tool.extentChanged.connect(
                self._draw_roi_extent_changed
            )

        self.roi_draw_btn.setEnabled(False)
        self.roi_draw_btn.setText(
            "Desenhe um retângulo..."
        )

        canvas.setMapTool(
            self._roi_draw_tool
        )

        log_message(
            "[ROI] Ferramenta de desenho ativada. Desenhe um retângulo no mapa."
        )

    def _draw_roi_extent_changed(self, rectangle):
        """Recebe o retângulo desenhado no canvas e fixa a ROI."""

        try:
            if rectangle is None or rectangle.isEmpty():
                return

            canvas = iface.mapCanvas()
            canvas_crs = canvas.mapSettings().destinationCrs()

            bbox_rect = self._bbox_to_wgs84(
                rectangle,
                canvas_crs,
            )

            if bbox_rect is None or bbox_rect.isEmpty():
                raise ValueError(
                    "Não foi possível converter o retângulo desenhado para EPSG:4326."
                )

            bbox = (
                bbox_rect.xMinimum(),
                bbox_rect.yMinimum(),
                bbox_rect.xMaximum(),
                bbox_rect.yMaximum(),
            )

            self.roi_manager.set_bbox(
                bbox,
                source="Desenhado no mapa",
                canvas_extent=canvas.extent(),
            )

            # O desenho também cria/atualiza a camada temporária da ROI.
            self._create_or_update_roi_temp_layer(
                bbox
            )

            log_message(
                f"[ROI] Região desenhada no mapa: {bbox}"
            )

        except Exception as error:
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível definir a Região de Interesse pelo desenho.\n\n"
                f"{error}"
            )

        finally:
            canvas = iface.mapCanvas()

            # Volta para a ferramenta que estava ativa antes do desenho.
            if (
                self._roi_previous_map_tool is not None
                and self._roi_previous_map_tool is not self._roi_draw_tool
            ):
                canvas.setMapTool(
                    self._roi_previous_map_tool
                )

            self.roi_draw_btn.setEnabled(True)
            self.roi_draw_btn.setText(
                "Desenhar no mapa"
            )

    # ==========================================================
    # SELECIONAR DIRETÓRIO
    # ==========================================================

    def choose_output(self):

        path = QFileDialog.getExistingDirectory(
            iface.mainWindow(),
            "Selecione o Diretório de Saída",
            self.output.text(),
        )

        if path:

            try:
                selected_path = Path(path).resolve()
                default_path = get_cache_dir().resolve()
            except Exception:
                selected_path = None
                default_path = None

            if (
                selected_path is not None
                and default_path is not None
                and selected_path == default_path
            ):
                self.output.clear()
                self.output.setPlaceholderText(
                    "System temp (default)"
                )
                save_output_dir(
                    str(default_path)
                )
            else:
                self.output.setText(
                    path
                )
                save_output_dir(
                    path
                )


    # ==========================================================
    # LIMPAR CACHE PADRÃO
    # ==========================================================

    def clear_cache_clicked(self):

        cache_dir = get_cache_dir()

        answer = QMessageBox.question(
            iface.mainWindow(),
            "QMD Tools Explorer",
            (
                "Deseja realmente limpar o cache do QMD Tools Explorer?\n\n"
                f"Local: {cache_dir}\n\n"
                "Os arquivos armazenados no cache padrão serão removidos.\n"
                "Arquivos de um diretório de saída personalizado não serão afetados."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        ok, errors = clear_cache()

        if ok:
            log_message(
                f"[CACHE] Cache limpo: {cache_dir}"
            )
            QMessageBox.information(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Cache limpo com sucesso."
            )
        else:
            log_message(
                "[CACHE] Cache limpo parcialmente."
            )
            detalhes = "\n".join(errors[:5])
            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                (
                    "O cache foi limpo parcialmente.\n\n"
                    "Alguns arquivos podem estar em uso pelo QGIS.\n\n"
                    f"{detalhes}"
                )
            )


    # ==========================================================
    # EXECUTAR BUSCA
    # ==========================================================

    def execute_search(
        self,
        force_extent=False,
    ):

        selected = [
            name
            for name, checkbox
            in self.checkboxes.items()
            if checkbox.isChecked()
        ]


        if not selected:

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Selecione pelo menos uma coleção.",
            )

            return


        start = self.start.date().toString(
            "yyyy-MM-dd"
        )

        end = self.end.date().toString(
            "yyyy-MM-dd"
        )


        tile = (
            self.tile.text()
            .strip()
        )


        output = (
            self.output.text()
            .strip()
        )


        if output:

            save_output_dir(
                output
            )

        else:

            output = get_output_dir()


        # ------------------------------------------------------
        # CONECTAR AO STAC
        # ------------------------------------------------------

        client = connect_to_stac(
            STAC_URL
        )


        if not client:

            return


        # ------------------------------------------------------
        # IDs DAS COLEÇÕES
        # ------------------------------------------------------

        ids = [

            self.collections[name].get(
                "id"
            )

            for name in selected

            if self.collections[name].get(
                "id"
            )

        ]


        # ------------------------------------------------------
        # DEFINIR TIPO DE BUSCA
        # ------------------------------------------------------

        use_extent = (
            force_extent
            or not tile
        )

        bbox = None

        if use_extent:

            if not self.roi_manager.has_bbox():

                QMessageBox.warning(
                    iface.mainWindow(),
                    "QMD Tools Explorer",
                    "Nenhuma Região de Interesse foi capturada.\n\n"
                    "Navegue até a área desejada no mapa e clique em "
                    "\"Capturar\"."
                )

                return

            bbox = self.roi_manager.get_bbox()


        # ------------------------------------------------------
        # LOG
        # ------------------------------------------------------

        log_message(
            "----------------------------------------"
        )

        log_message(
            "QMD Tools Explorer - iniciando busca"
        )

        log_message(
            f"Coleções: {selected}"
        )


        # ------------------------------------------------------
        # BUSCAR ITENS
        # ------------------------------------------------------

        if use_extent:

            items = search_items_by_bbox(
                client,
                bbox,
                start,
                end,
                ids,
            )

        else:

            items = search_items(
                client,
                tile,
                start,
                end,
                ids,
            )


        # ------------------------------------------------------
        # SEM RESULTADOS
        # ------------------------------------------------------

        if not items:

            QMessageBox.information(
                iface.mainWindow(),
                "QMD Tools Explorer",
                (
                    "Nenhuma imagem disponível "
                    "para os parâmetros fornecidos."
                ),
            )

            return


        # ------------------------------------------------------
        # MAPEAR COLLECTION ID
        # ------------------------------------------------------

        collection_by_id = {

            config.get("id"): name

            for name, config
            in self.collections.items()

            if config.get("id")

        }


        filtered = []


        for item in items:

            collection_id = (
                getattr(
                    item,
                    "collection_id",
                    None,
                )

                or item.properties.get(
                    "collection"
                )
            )


            name = collection_by_id.get(
                collection_id
            )


            if (
                name is None
                and len(selected) == 1
            ):

                name = selected[0]


            if name is not None:

                item.properties[
                    "_bdc_collection_name"
                ] = name


                filtered.append(
                    item
                )


        # ------------------------------------------------------
        # LOG
        # ------------------------------------------------------

        log_message(
            f"{len(filtered)} imagem(ns) encontrada(s)."
        )


        # ------------------------------------------------------
        # EMITIR RESULTADOS
        # ------------------------------------------------------

        self.search_requested.emit(
            {
                "items": filtered,
                "collections": selected,
                "output_dir": output,
                "tile": tile,
            }
        )


    # ==========================================================
    # CAMADAS DE REFERÊNCIA
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

            self.count_label.setText(
                f"Baixando {layer_name}..."
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

            self.count_label.setText(
                "Pronto."
            )

            QApplication.processEvents()


    def load_geopackage_reference_layer(
        self,
        layer_key,
    ):

        try:

            config = (
                self._load_reference_layers_config()
            )

            layer_config = (
                config[
                    "territorio_areas_protegidas"
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

        layer_name = (
            layer_config["name"]
        )

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
    ):

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

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


    def load_openstreetmap(self):

        layer_name = "OpenStreetMap"

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

        url = (
            "type=xyz"
            "&zmin=0"
            "&zmax=19"
            "&url=https://tile.openstreetmap.org/"
            "{z}/{x}/{y}.png"
        )

        layer = QgsRasterLayer(
            url,
            layer_name,
            "wms",
        )

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=True,
        )


    def load_biomas(self):

        self._load_wfs_reference_layer(
            layer_name="Biomas",
            type_name=(
                "bdqueimadas:"
                "biomas_brasileiros"
            ),
        )


    def load_estados(self):

        self._load_wfs_reference_layer(
            layer_name="Estados",
            type_name=(
                "bdqueimadas:"
                "estados"
            ),
            cql_filter="id_0 = 33",
        )


    def load_amz_legal(self):

        self._load_wfs_reference_layer(
            layer_name="Amazônia Legal",
            type_name=(
                "bdqueimadas:"
                "regioes_especiais"
            ),
            cql_filter=(
                "nome = 'Amazônia Legal'"
            ),
        )


    # ==========================================================
    # WMS / WMTS
    # ==========================================================

    def load_wms_wmts_layer(
        self,
        service_key,
        layer_key,
    ):

        try:

            config = (
                self._load_reference_layers_config()
            )

            service = (
                config[
                    "servicos_wms_wmts"
                ][
                    service_key
                ]
            )

            layer_config = (
                service[
                    "layers"
                ][
                    layer_key
                ]
            )

        except Exception as error:

            log_message(
                "Erro ao ler configuração "
                f"WMS/WMTS: {error}"
            )

            QMessageBox.warning(
                iface.mainWindow(),
                "QMD Tools Explorer",
                "Não foi possível carregar a "
                "configuração do serviço.\n\n"
                f"Erro: {error}"
            )

            return

        layer_name = (
            layer_config["name"]
        )

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

        service_type = (
            service.get(
                "type",
                "WMS"
            )
            .upper()
        )

        crs = service.get(
            "crs",
            "EPSG:4326"
        )

        image_format = (
            layer_config.get(
                "format"
            )
            or service.get(
                "format",
                "image/png"
            )
        )

        layer_id = layer_config[
            "layer"
        ]

        uri_parts = [
            f"crs={crs}",
            f"format={image_format}",
            f"layers={layer_id}",
            "styles=",
        ]

        if service_type == "WMTS":

            tile_matrix_set = layer_config.get(
                "tile_matrix_set"
            )

            if tile_matrix_set:
                uri_parts.append(
                    f"tileMatrixSet={tile_matrix_set}"
                )

        uri_parts.append(
            f"url={service['url']}"
        )

        uri = "&".join(
            uri_parts
        )

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
                f'Não foi possível carregar '
                f'a camada "{layer_name}".\n\n'
                f"Serviço: {service_type}"
            )

            return

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=False,
        )


    # ==========================================================
    # GOOGLE HYBRID
    # ==========================================================

    def load_google_hybrid(self):

        layer_name = "Google Hybrid"

        if self._layer_exists(
            layer_name
        ):

            self._show_layer_exists(
                layer_name
            )

            return

        url = (
            "type=xyz"
            "&zmin=0"
            "&zmax=20"
            "&url=https://mt1.google.com/vt/"
            "lyrs%3Dy"
            "%26x%3D{x}"
            "%26y%3D{y}"
            "%26z%3D{z}"
        )

        layer = QgsRasterLayer(
            url,
            layer_name,
            "wms",
        )

        if not layer.isValid():

            log_message(
                "Erro ao carregar Google Hybrid."
            )

            return

        QgsProject.instance().setCrs(
            QgsCoordinateReferenceSystem(
                "EPSG:4326"
            )
        )

        layer.setOpacity(
            1
        )

        self._add_reference_layer(
            layer,
            layer_name,
            is_basemap=True,
        )
