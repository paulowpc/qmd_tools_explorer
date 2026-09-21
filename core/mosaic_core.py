# -*- coding: utf-8 -*-
"""Criação dos mosaicos VRT."""
import os
from datetime import datetime
from osgeo import gdal
from qgis.core import QgsRasterLayer, QgsProject
from qgis.utils import iface
from .stac_core import log_message


def create_mosaic_vrt(mosaic_path, vrt_paths, satellite):
    try:
        if not vrt_paths:
            log_message("Nenhum VRT disponível para criar o mosaico.")
            return False
        log_message(f"Criando mosaico com {len(vrt_paths)} cenas...")
        if os.path.exists(mosaic_path):
            try:
                os.remove(mosaic_path)
            except Exception as e:
                log_message(f"Não foi possível remover o mosaico existente: {e}")
                return False
        options = gdal.BuildVRTOptions(resampleAlg="bilinear" if satellite == "Sentinel-2" else "nearest", separate=False)
        ds = gdal.BuildVRT(mosaic_path, vrt_paths, options=options)
        if ds is None:
            log_message(f"Erro ao criar mosaico: {mosaic_path}")
            return False
        ds = None
        log_message(f"Mosaico criado com sucesso: {mosaic_path}")
        return True
    except Exception as e:
        log_message(f"Erro ao criar mosaico: {e}")
        return False


def create_mosaics_from_groups(satellite, mosaic_groups, output_dir):
    mosaic_dir = os.path.join(output_dir, "mosaicos")
    os.makedirs(mosaic_dir, exist_ok=True)
    log_message("==========================================")
    log_message("CRIANDO MOSAICOS POR DATA + ÓRBITA")
    log_message(f"Diretório dos mosaicos: {mosaic_dir}")
    for (date, relative_orbit), vrt_paths in mosaic_groups.items():
        log_message("------------------------------------------")
        log_message(f"Grupo: {date} | {relative_orbit}")
        log_message(f"Número de cenas: {len(vrt_paths)}")
        date_compact = date.replace("-", "")
        mosaic_filename = f"{satellite}_{date_compact}_{relative_orbit}_mosaic.vrt"
        mosaic_path = os.path.join(mosaic_dir, mosaic_filename)
        log_message(f"Mosaico: {mosaic_filename}")
        if create_mosaic_vrt(mosaic_path, vrt_paths, satellite):
            display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
            name = f"{satellite} | {display_date} | {relative_orbit} | Mosaico"
            layer = QgsRasterLayer(mosaic_path, name)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                log_message(f"Mosaico carregado: {name}")
            else:
                log_message(f"Mosaico criado, mas camada não é válida: {mosaic_path}")
    iface.mapCanvas().refresh()
