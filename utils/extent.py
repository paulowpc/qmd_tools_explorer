# -*- coding: utf-8 -*-
"""Funções relacionadas ao extent do canvas do QGIS."""
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.utils import iface


def get_canvas_bbox(canvas=None):
    canvas = canvas or iface.mapCanvas()
    extent = canvas.extent()
    canvas_crs = canvas.mapSettings().destinationCrs()
    transform = QgsCoordinateTransform(
        canvas_crs,
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsProject.instance(),
    )
    p1 = transform.transform(extent.xMinimum(), extent.yMinimum())
    p2 = transform.transform(extent.xMaximum(), extent.yMaximum())
    return [p1.x(), p1.y(), p2.x(), p2.y()]
