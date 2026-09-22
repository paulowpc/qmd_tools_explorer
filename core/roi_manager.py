# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import (
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)


class ROIManager(QObject):
    """Mantém e exibe a Região de Interesse compartilhada pelo plugin."""

    roi_changed = pyqtSignal(object)

    ROI_LAYER_NAME = "ROI - Região de Interesse"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bbox = None
        self.source = None
        self.canvas_extent = None
        self.roi_layer_id = None

    def set_bbox(self, bbox, source="Canvas extent", canvas_extent=None):
        self.bbox = tuple(float(value) for value in bbox)
        self.source = source
        self.canvas_extent = canvas_extent

        self._draw_bbox_layer()
        self.roi_changed.emit(self.bbox)

    def clear(self):
        self.bbox = None
        self.source = None
        self.canvas_extent = None

        self._remove_bbox_layer()
        self.roi_changed.emit(None)

    def has_bbox(self):
        return self.bbox is not None

    def get_bbox(self):
        return self.bbox

    def _remove_bbox_layer(self):
        """Remove a camada temporária da ROI de forma segura."""
        project = QgsProject.instance()

        ids_to_remove = set()

        if self.roi_layer_id:
            ids_to_remove.add(self.roi_layer_id)

        # Recupera eventuais camadas ROI criadas por uma execução anterior.
        for layer in list(project.mapLayers().values()):
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.name() == self.ROI_LAYER_NAME
                and layer.customProperty(
                    "qmd_tools_explorer_roi", False
                )
            ):
                ids_to_remove.add(layer.id())

        for layer_id in ids_to_remove:
            if project.mapLayer(layer_id) is not None:
                project.removeMapLayer(layer_id)

        self.roi_layer_id = None

    def _draw_bbox_layer(self):
        """Cria/atualiza o retângulo temporário da ROI no QGIS."""
        if not self.bbox:
            return

        # Remove uma ROI anterior antes de criar a nova.
        self._remove_bbox_layer()

        xmin, ymin, xmax, ymax = self.bbox

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:4326",
            self.ROI_LAYER_NAME,
            "memory",
        )

        if not layer.isValid():
            return

        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromRect(
                QgsRectangle(xmin, ymin, xmax, ymax)
            )
        )

        provider = layer.dataProvider()
        provider.addFeature(feature)
        layer.updateExtents()

        # Aproximadamente 25% de opacidade para o preenchimento.
        symbol = QgsFillSymbol.createSimple({
            "color": "255,0,0,64",
            "outline_color": "255,0,0,220",
            "outline_width": "0.8",
        })
        layer.renderer().setSymbol(symbol)
        layer.setOpacity(1.0)
        layer.setCustomProperty(
            "qmd_tools_explorer_roi",
            True,
        )

        project = QgsProject.instance()
        project.addMapLayer(layer, True)
        self.roi_layer_id = layer.id()

