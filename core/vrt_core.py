# -*- coding: utf-8 -*-
"""
Criação e carregamento dos VRTs individuais.
"""

import os
from typing import List

from osgeo import gdal

from qgis.core import (
    QgsRasterLayer,
    QgsProject,
)

from qgis.utils import iface

from .stac_core import (
    log_message,
    get_satellite_name,
    get_item_tile,
    get_relative_orbit,
    get_layer_name,
)


def create_vrt(
    vrt_path: str,
    hrefs: List[str],
    satellite: str,
    clip_extent=None,
) -> bool:

    try:

        # -------------------------------------------------
        # VRT DE ORIGEM
        # -------------------------------------------------

        source_vrt_path = vrt_path.replace(
            ".vrt",
            "_source.vrt"
        )

        # -------------------------------------------------
        # OPÇÕES DE RESOLUÇÃO
        # -------------------------------------------------

        if satellite == "Sentinel-2":

            options = gdal.BuildVRTOptions(
                resampleAlg="bilinear",
                addAlpha=False,
                separate=True,
                srcNodata=0,
                VRTNodata=0,
                xRes=10,
                yRes=10,
            )

        else:

            options = gdal.BuildVRTOptions(
                resampleAlg="nearest",
                addAlpha=False,
                separate=True,
                srcNodata=0,
                VRTNodata=0,
            )

        # -------------------------------------------------
        # CRIA O VRT DE ORIGEM
        # -------------------------------------------------

        if not os.path.exists(source_vrt_path):

            log_message(
                "[VRT] Criando VRT de origem."
            )

            ds = gdal.BuildVRT(
                source_vrt_path,
                hrefs,
                options=options,
            )

            if not ds:

                log_message(
                    "[VRT] Falha ao criar "
                    "VRT de origem."
                )

                return False

            ds = None

            log_message(
                f"[VRT] VRT de origem criado: "
                f"{source_vrt_path}"
            )

        else:

            log_message(
                "[VRT] Reutilizando VRT "
                "de origem existente."
            )

        # -------------------------------------------------
        # CENA COMPLETA
        # -------------------------------------------------

        if clip_extent is None:

            log_message(
                "[ÁREA] Cena completa selecionada."
            )

            translate_options = gdal.TranslateOptions(
                format="VRT"
            )

            ds = gdal.Translate(
                vrt_path,
                source_vrt_path,
                options=translate_options,
            )

            if not ds:

                log_message(
                    "[VRT] Falha ao criar "
                    "VRT final."
                )

                return False

            ds = None

            log_message(
                f"VRT criado com sucesso: "
                f"{vrt_path}"
            )

            return True

        # -------------------------------------------------
        # RECORTE PELO EXTENT
        # -------------------------------------------------

        log_message(
            "[ÁREA] Aplicando recorte "
            "pelo Extent."
        )

        xmin = clip_extent.xMinimum()
        ymin = clip_extent.yMinimum()
        xmax = clip_extent.xMaximum()
        ymax = clip_extent.yMaximum()

        log_message(
            "[ÁREA] BBOX do recorte: "
            f"{xmin:.8f}, "
            f"{ymin:.8f}, "
            f"{xmax:.8f}, "
            f"{ymax:.8f}"
        )

        # -------------------------------------------------
        # CRIA VRT RECORTADO
        # -------------------------------------------------

        translate_options = gdal.TranslateOptions(

            format="VRT",

            projWin=[
                xmin,
                ymax,
                xmax,
                ymin,
            ],

            projWinSRS="EPSG:4326",
        )

        ds = gdal.Translate(
            vrt_path,
            source_vrt_path,
            options=translate_options,
        )

        if not ds:

            log_message(
                "[ÁREA] Falha ao criar "
                "VRT recortado."
            )

            return False

        ds = None

        # -------------------------------------------------
        # SUCESSO
        # -------------------------------------------------

        log_message(
            f"[ÁREA] VRT recortado "
            f"com sucesso: {vrt_path}"
        )

        return True

    except Exception as e:

        log_message(
            f"Erro ao criar VRT: {e}"
        )

        return False
    
# =========================================================
# NOME DO ARQUIVO VRT
# =========================================================

def get_vrt_filename(
    item,
    satellite,
    query_bands=None,
):
    """
    Gera um nome de VRT único para a cena e composição.

    A composição é identificada pelas bandas na ordem em que
    serão usadas no VRT. Isso evita que True Color, False Color 1
    e False Color 2 compartilhem o mesmo arquivo físico.
    """

    scene_id = item.id

    safe_scene_id = "".join(
        c
        if c.isalnum() or c in "_-"
        else "_"
        for c in scene_id
    )

    if query_bands:
        band_signature = "_".join(
            str(band)
            .replace("/", "-")
            .replace(" ", "")
            for band in query_bands
        )

        return (
            f"{safe_scene_id}_"
            f"{band_signature}.vrt"
        )

    return f"{safe_scene_id}.vrt"



# =========================================================
# DESCRIÇÕES DAS BANDAS
# =========================================================

def get_band_description(band_name, satellite):
    """
    Retorna uma descrição legível para a banda espectral.

    A descrição é usada somente na propriedade da banda do VRT,
    mantendo a numeração interna do VRT (Band 1, Band 2, ...).

    As composições/bandas disponíveis são definidas em collection_bdc.json.
    Aqui são acrescentadas apenas as descrições espectrais correspondentes.
    """

    band = str(band_name).upper().replace(" ", "")

    descriptions = {
        # Sentinel-2
        "SENTINEL-2": {
            "B01": "B01 – Coastal/Aerosol",
            "B02": "B02 – Blue",
            "B03": "B03 – Green",
            "B04": "B04 – Red",
            "B05": "B05 – Red Edge 1",
            "B06": "B06 – Red Edge 2",
            "B07": "B07 – Red Edge 3",
            "B08": "B08 – NIR",
            "B8A": "B8A – Narrow NIR",
            "B09": "B09 – Water Vapor",
            "B10": "B10 – Cirrus",
            "B11": "B11 – SWIR 1",
            "B12": "B12 – SWIR 2",
        },

        # Landsat / nomes de assets usados pelo BDC
        "LANDSAT-2": {
            "RED": "B4 – Red",
            "GREEN": "B3 – Green",
            "BLUE": "B2 – Blue",
            "NIR08": "B5 – NIR",
            "SWIR11": "B6 – SWIR 1",
            "SWIR22": "B7 – SWIR 2",
            "B1": "B1 – Coastal/Aerosol",
            "B2": "B2 – Blue",
            "B3": "B3 – Green",
            "B4": "B4 – Red",
            "B5": "B5 – NIR",
            "B6": "B6 – SWIR 1",
            "B7": "B7 – SWIR 2",
            "B8": "B8 – Panchromatic",
            "B9": "B9 – Cirrus",
            "B10": "B10 – Thermal Infrared 1",
            "B11": "B11 – Thermal Infrared 2",
        },

        # Amazonia-1 / WFI
        "AMAZONIA-1/WFI": {
            "BAND1": "BAND1 – Blue",
            "BAND2": "BAND2 – Green",
            "BAND3": "BAND3 – Red",
            "BAND4": "BAND4 – NIR",
        },

        # CBERS-4 / WFI
        "CBERS-4/WFI": {
            "BAND13": "BAND13 – Blue",
            "BAND14": "BAND14 – Green",
            "BAND15": "BAND15 – Red",
            "BAND16": "BAND16 – NIR",
        },

        # CBERS-4A / WFI
        "CBERS-4A/WFI": {
            "BAND13": "BAND13 – Blue",
            "BAND14": "BAND14 – Green",
            "BAND15": "BAND15 – Red",
            "BAND16": "BAND16 – NIR",
        },

        # CBERS-4 / MUX
        "CBERS-4/MUX": {
            "BAND5": "BAND5 – Blue",
            "BAND6": "BAND6 – Green",
            "BAND7": "BAND7 – Red",
            "BAND8": "BAND8 – NIR",
        },

        # CBERS-4A / MUX
        "CBERS-4A/MUX": {
            "BAND5": "BAND5 – Blue",
            "BAND6": "BAND6 – Green",
            "BAND7": "BAND7 – Red",
            "BAND8": "BAND8 – NIR",
        },
    }

    satellite_key = str(satellite).upper()
    satellite_descriptions = descriptions.get(satellite_key, {})

    return satellite_descriptions.get(
        band,
        str(band_name),
    )


def set_vrt_band_descriptions(vrt_path, band_names, satellite):
    """
    Adiciona a descrição espectral às bandas do VRT final.
    """

    ds = gdal.Open(
        vrt_path,
        gdal.GA_Update,
    )

    if not ds:
        log_message(
            f"[VRT] Não foi possível abrir o VRT "
            f"para adicionar descrições: {vrt_path}"
        )
        return

    try:
        for index, band_name in enumerate(
            band_names,
            start=1,
        ):
            band = ds.GetRasterBand(index)

            if not band:
                continue

            description = get_band_description(
                band_name,
                satellite,
            )

            band.SetDescription(description)

            log_message(
                f"[VRT] Banda {index}: {description}"
            )

    finally:
        ds = None


# =========================================================
# GERA VRTS INDIVIDUAIS
# =========================================================

def generate_individual_vrts(
    satellite,
    query_bands,
    selected_items,
    output_dir,
    create_mosaic=False,
    clip_extent=None,
):

    """
    Cria os VRTs individuais e retorna grupos
    (data, órbita) para mosaico.

    Parameters
    ----------
    satellite : str
        Família do satélite/sensor.

    query_bands : list
        Lista de bandas a utilizar.

    selected_items : list
        Itens STAC selecionados.

    output_dir : str
        Diretório de saída.

    create_mosaic : bool
        Indica se será criado mosaico.

    clip_extent : QgsRectangle, optional
        Extent em EPSG:4326 utilizado para
        recortar o VRT.
    """

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    mosaic_groups = {}

    # -----------------------------------------------------
    # MENSAGEM DA ÁREA
    # -----------------------------------------------------

    if clip_extent is None:

        log_message(
            "[ÁREA] Processando cena completa."
        )

    else:

        log_message(
            "[ÁREA] Processando somente "
            "o Extent selecionado."
        )

    # -----------------------------------------------------
    # PROCESSA CADA ITEM
    # -----------------------------------------------------

    for item in selected_items:

        date = item.datetime.strftime(
            "%Y-%m-%d"
        )

        relative_orbit = get_relative_orbit(
            item
        )

        satellite_name = get_satellite_name(
            item,
            satellite,
        )

        item_tile = get_item_tile(
            item,
            satellite,
        )

        layer_name = get_layer_name(
            item,
            satellite,
        )

        vrt_filename = get_vrt_filename(
            item,
            satellite,
            query_bands=query_bands,
        )

        # -------------------------------------------------
        # LOG
        # -------------------------------------------------

        log_message(
            f"Data: {date} | "
            f"Órbita: {relative_orbit}"
        )

        log_message(
            f"Processando: {item.id}"
        )

        log_message(
            f"Satélite: {satellite_name}"
        )

        log_message(
            f"Tile: {item_tile}"
        )

        log_message(
            f"Data: {date}"
        )

        log_message(
            f"VRT: {vrt_filename}"
        )

        log_message(
            f"Camada: {layer_name}"
        )

        # -------------------------------------------------
        # BANDAS
        # -------------------------------------------------

        available_bands = [
            band
            for band in query_bands
            if band in item.assets
        ]

        missing_bands = [
            band
            for band in query_bands
            if band not in item.assets
        ]

        if missing_bands:
            log_message(
                f"[VRT] Bandas ausentes: "
                f"{', '.join(missing_bands)}"
            )

        hrefs = [
            f"/vsicurl/{item.assets[band].href}"
            for band in available_bands
        ]

        if not hrefs:

            log_message(
                "Nenhuma das bandas solicitadas "
                f"foi encontrada no item {item.id}."
            )

            continue

        log_message(
            f"[VRT] Bandas solicitadas: "
            f"{', '.join(query_bands)}"
        )

        log_message(
            f"[VRT] Bandas encontradas: "
            f"{', '.join(available_bands)}"
        )

        # -------------------------------------------------
        # DIRETÓRIO DO TILE
        # -------------------------------------------------

        tile_dir = os.path.join(
            output_dir,
            item_tile,
        )

        os.makedirs(
            tile_dir,
            exist_ok=True,
        )

        vrt_path = os.path.join(
            tile_dir,
            vrt_filename,
        )

        # -------------------------------------------------
        # CRIA VRT
        # -------------------------------------------------

        if create_vrt(
            vrt_path,
            hrefs,
            satellite,
            clip_extent=clip_extent,
        ):

            # ---------------------------------------------
            # DESCRIÇÃO DAS BANDAS
            # ---------------------------------------------

            set_vrt_band_descriptions(
                vrt_path,
                available_bands,
                satellite,
            )

            mosaic_groups.setdefault(
                (
                    date,
                    relative_orbit,
                ),
                [],
            ).append(
                vrt_path
            )

            # ---------------------------------------------
            # CARREGA VRT
            # ---------------------------------------------

            if not create_mosaic:

                layer = QgsRasterLayer(
                    vrt_path,
                    layer_name,
                )

                if layer.isValid():

                    log_message(
                        f"Camada VRT "
                        f"'{vrt_filename}' "
                        "carregada com sucesso."
                    )

                    QgsProject.instance().addMapLayer(
                        layer
                    )

                else:

                    log_message(
                        f"A camada VRT "
                        f"'{vrt_filename}' "
                        "não é válida."
                    )

            else:

                log_message(
                    f"VRT individual criado: "
                    f"{vrt_filename} "
                    "(não carregado no QGIS porque "
                    "o mosaico está habilitado)"
                )

    return mosaic_groups


# =========================================================
# COMPATIBILIDADE COM MOTOR V1
# =========================================================

def generate_and_load_vrts(
    satellite,
    tile,
    query_bands,
    selected_items,
    output_dir,
    create_mosaic=False,
    clip_extent=None,
):

    """
    Compatibilidade com o motor V1;
    cria VRTs e, se solicitado,
    cria mosaicos.
    """

    from .mosaic_core import (
        create_mosaics_from_groups
    )

    groups = generate_individual_vrts(

        satellite=satellite,

        query_bands=query_bands,

        selected_items=selected_items,

        output_dir=output_dir,

        create_mosaic=create_mosaic,

        clip_extent=clip_extent,
    )

    if create_mosaic:

        create_mosaics_from_groups(
            satellite,
            groups,
            output_dir,
        )

    iface.mapCanvas().refresh()