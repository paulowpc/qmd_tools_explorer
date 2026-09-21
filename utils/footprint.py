# -*- coding: utf-8 -*-

import json
from pathlib import Path

from osgeo import gdal, ogr

from qgis.core import (
    QgsGeometry,
    QgsVectorLayer,
    QgsFeature,
    QgsProject,
    QgsCoordinateTransform,
    QgsField,
    QgsSingleSymbolRenderer,
    QgsFillSymbol,
)

from qgis.PyQt.QtCore import QVariant
from qgis.utils import iface

from ..core.stac_core import log_message


# ==========================================================
# CONFIGURAÇÃO GDAL
# ==========================================================

gdal.UseExceptions()


# ==========================================================
# DETECTA A FAMÍLIA DO ITEM
# ==========================================================

def get_item_family(item):

    try:

        item_id = (
            getattr(item, "id", "")
            or ""
        ).upper()

        collection_id = (
            getattr(item, "collection_id", "")
            or ""
        ).lower()

        collection_name = (
            item.properties.get(
                "_bdc_collection_name",
                ""
            )
            if hasattr(item, "properties")
            else ""
        )

        collection_name = (
            collection_name
            or ""
        ).lower()

        # --------------------------------------------------
        # LANDSAT
        # --------------------------------------------------

        if (
            "landsat" in collection_id
            or "landsat" in collection_name
            or item_id.startswith("LC")
            or item_id.startswith("LE")
            or item_id.startswith("LT")
        ):

            return "Landsat"

        # --------------------------------------------------
        # SENTINEL
        # --------------------------------------------------

        if (
            "sentinel" in collection_id
            or "sentinel" in collection_name
            or item_id.startswith("S2A")
            or item_id.startswith("S2B")
            or item_id.startswith("S2C")
        ):

            return "Sentinel-2"

        # --------------------------------------------------
        # CBERS
        # --------------------------------------------------

        if (
            "cbers" in collection_id
            or "cbers" in collection_name
            or item_id.startswith("CB4")
            or item_id.startswith("CBERS")
        ):

            return "CBERS-4"

        # --------------------------------------------------
        # AMAZÔNIA-1
        # --------------------------------------------------

        if (
            "amazonia" in collection_id
            or "amazônia" in collection_name
            or "amazonia" in collection_name
            or item_id.startswith("AMAZONIA")
            or item_id.startswith("AMZ")
        ):

            return "Amazônia-1"

        return None

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao identificar família: {e}"
        )

        return None


# ==========================================================
# FOOTPRINT A PARTIR DA GEOMETRIA DO ITEM STAC
# ==========================================================

def footprint_from_item(item):

    try:

        if not getattr(item, "geometry", None):

            log_message(
                "[FOOTPRINT] Item não possui geometria."
            )

            return None

        log_message(
            "[FOOTPRINT] Utilizando geometria original do STAC."
        )

        # --------------------------------------------------
        # GEOJSON DO ITEM STAC
        # --------------------------------------------------

        geojson_text = json.dumps(
            item.geometry
        )

        # --------------------------------------------------
        # GEOJSON -> OGR
        # --------------------------------------------------

        ogr_geometry = ogr.CreateGeometryFromJson(
            geojson_text
        )

        if ogr_geometry is None:

            log_message(
                "[FOOTPRINT] Não foi possível criar "
                "a geometria OGR."
            )

            return None

        # --------------------------------------------------
        # OGR -> WKT
        # --------------------------------------------------

        wkt = ogr_geometry.ExportToWkt()

        if not wkt:

            log_message(
                "[FOOTPRINT] Não foi possível "
                "converter a geometria para WKT."
            )

            return None

        # --------------------------------------------------
        # WKT -> QgsGeometry
        # --------------------------------------------------

        geometry = QgsGeometry.fromWkt(
            wkt
        )

        if (
            geometry is None
            or geometry.isNull()
            or geometry.isEmpty()
        ):

            log_message(
                "[FOOTPRINT] Geometria QGIS inválida."
            )

            return None

        log_message(
            "[FOOTPRINT] Geometria STAC convertida "
            "com sucesso."
        )

        return geometry

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao criar footprint "
            f"a partir do STAC: {e}"
        )

        return None


# ==========================================================
# LOCALIZA UM RASTER NOS ASSETS
# ==========================================================

def get_raster_asset_url(item):

    try:

        assets = (
            getattr(
                item,
                "assets",
                {}
            )
            or {}
        )

        log_message(
            f"[FOOTPRINT] Assets disponíveis: "
            f"{list(assets.keys())}"
        )

        preferred_assets = [

            "SR_B4",
            "SR_B3",
            "SR_B2",

            "B4",
            "B3",
            "B2",

            "red",
            "green",
            "blue",
        ]

        for key in preferred_assets:

            asset = assets.get(key)

            if asset is None:
                continue

            href = getattr(
                asset,
                "href",
                None
            )

            if href:

                log_message(
                    f"[FOOTPRINT] RASTER ESCOLHIDO: "
                    f"{key}"
                )

                log_message(
                    f"[FOOTPRINT] URL escolhida: "
                    f"{href}"
                )

                return href

        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------

        for key, asset in assets.items():

            href = getattr(
                asset,
                "href",
                None
            )

            if not href:
                continue

            href_lower = href.lower()

            if (
                href_lower.endswith(".tif")
                or href_lower.endswith(".tiff")
            ):

                log_message(
                    f"[FOOTPRINT] FALLBACK RASTER: "
                    f"{key}"
                )

                log_message(
                    f"[FOOTPRINT] URL escolhida: "
                    f"{href}"
                )

                return href

        log_message(
            "[FOOTPRINT] Nenhum raster encontrado."
        )

        return None

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao localizar raster: {e}"
        )

        return None


# ==========================================================
# FOOTPRINT A PARTIR DO RASTER
# ==========================================================

def footprint_from_raster(url):

    ds = None

    try:

        if not url:

            log_message(
                "[FOOTPRINT] URL raster inválida."
            )

            return None

        log_message(
            f"[FOOTPRINT] Abrindo raster: {url}"
        )

        ds = gdal.Open(
            f"/vsicurl/{url}"
        )

        if ds is None:

            raise RuntimeError(
                "Não foi possível abrir o raster."
            )

        # --------------------------------------------------
        # BANDA
        # --------------------------------------------------

        band = ds.GetRasterBand(1)

        if band is None:

            raise RuntimeError(
                "Não foi possível acessar a banda 1."
            )

        overview = int(
            band.GetOverviewCount() / 2
        )

        # --------------------------------------------------
        # NODATA
        # --------------------------------------------------

        if band.GetNoDataValue() is None:

            band.SetNoDataValue(
                0.0
            )

        # --------------------------------------------------
        # GEOREFERENCIAMENTO
        # --------------------------------------------------

        (
            _,
            res_x,
            _,
            _,
            _,
            res_y
        ) = ds.GetGeoTransform()

        mean_res = (
            res_x +
            (-1 * res_y)
        ) / 2

        mean_size = (
            ds.RasterXSize +
            ds.RasterYSize
        ) / 2

        factor = (
            mean_res *
            mean_size /
            100
        )

        factor /= 1120000

        # --------------------------------------------------
        # GDAL FOOTPRINT
        # --------------------------------------------------

        log_message(
            "[FOOTPRINT] Calculando footprint..."
        )

        wkt = gdal.Footprint(

            None,

            ds,

            format="WKT",

            dstSRS="EPSG:4326",

            bands=[1],

            ovr=overview,

            simplify=factor,

            maxPoints=4,

            minRingArea=(
                factor ** 2 / 2
            ),
        )

        if not wkt:

            raise RuntimeError(
                "GDAL não retornou um footprint."
            )

        # --------------------------------------------------
        # WKT -> QGIS
        # --------------------------------------------------

        geometry = QgsGeometry.fromWkt(
            wkt
        )

        if (
            geometry is None
            or geometry.isNull()
            or geometry.isEmpty()
        ):

            raise RuntimeError(
                "Não foi possível converter "
                "o footprint para QgsGeometry."
            )

        log_message(
            "[FOOTPRINT] Footprint calculado "
            "com sucesso."
        )

        return geometry

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao criar footprint "
            f"do raster: {e}"
        )

        return None

    finally:

        ds = None


# ==========================================================
# DEFINE A MELHOR ESTRATÉGIA
# ==========================================================

def get_item_footprint(item, family=None):

    try:

        item_id = getattr(
            item,
            "id",
            "N/A"
        )

        if not family:

            family = get_item_family(
                item
            )

        log_message("")

        log_message(
            f"[FOOTPRINT] Processando cena: "
            f"{item_id}"
        )

        log_message(
            f"[FOOTPRINT] Família: "
            f"{family}"
        )

        # --------------------------------------------------
        # LANDSAT
        # --------------------------------------------------

        if family == "Landsat":

            log_message(
                "[FOOTPRINT] Estratégia: "
                "footprint calculado a partir do raster."
            )

            raster_url = get_raster_asset_url(
                item
            )

            if not raster_url:

                log_message(
                    "[FOOTPRINT] Raster Landsat "
                    "não encontrado."
                )

                return None

            geometry = footprint_from_raster(
                raster_url
            )

        # --------------------------------------------------
        # SENTINEL / CBERS / AMAZÔNIA-1
        # --------------------------------------------------

        else:

            log_message(
                "[FOOTPRINT] Estratégia: "
                "geometria original do STAC."
            )

            geometry = footprint_from_item(
                item
            )

        # --------------------------------------------------
        # VALIDAÇÃO
        # --------------------------------------------------

        if geometry is None:

            log_message(
                "[FOOTPRINT] Nenhuma geometria retornada."
            )

            return None

        if geometry.isNull():

            log_message(
                "[FOOTPRINT] Geometria retornada é nula."
            )

            return None

        if geometry.isEmpty():

            log_message(
                "[FOOTPRINT] Geometria retornada está vazia."
            )

            return None

        log_message(
            f"[FOOTPRINT] Footprint pronto: "
            f"{item_id}"
        )

        return geometry

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro geral: {e}"
        )

        return None


# ==========================================================
# IDENTIFICA SATÉLITE
# ==========================================================

def get_satellite_name(item):

    item_id = (
        getattr(item, "id", "")
        or ""
    ).upper()

    if item_id.startswith("LC09"):
        return "Landsat-9"

    if item_id.startswith("LC08"):
        return "Landsat-8"

    if item_id.startswith("LE07"):
        return "Landsat-7"

    if item_id.startswith("LT05"):
        return "Landsat-5"

    if item_id.startswith("S2A"):
        return "Sentinel-2A"

    if item_id.startswith("S2B"):
        return "Sentinel-2B"

    if item_id.startswith("S2C"):
        return "Sentinel-2C"

    if item_id.startswith("CB4"):
        return "CBERS-4"

    if (
        item_id.startswith("AMZ")
        or item_id.startswith("AMAZONIA")
    ):
        return "Amazônia-1"

    return (
        get_item_family(item)
        or "Desconhecido"
    )


# ==========================================================
# OBTÉM LOCALIZAÇÃO
# ==========================================================

def get_item_location(item):

    try:

        properties = (
            getattr(
                item,
                "properties",
                {}
            )
            or {}
        )

        tiles = properties.get(
            "bdc:tiles"
        )

        if tiles:

            if isinstance(
                tiles,
                list
            ):

                tile = str(
                    tiles[0]
                )

            else:

                tile = str(
                    tiles
                )

            if (
                tile.isdigit()
                and len(tile) == 6
            ):

                return (
                    f"{tile[:3]}/"
                    f"{tile[3:]}"
                )

            return tile

        path = properties.get(
            "path"
        )

        row = properties.get(
            "row"
        )

        if path and row:

            return (
                f"{path}/{row}"
            )

        return "-"

    except Exception:

        return "-"


# ==========================================================
# CRIA OU REUTILIZA CAMADA
# ==========================================================

def create_footprints_layer():

    layer_name = (
        "QMD - Footprints das Cenas"
    )

    # --------------------------------------------------
    # PROCURA CAMADA EXISTENTE
    # --------------------------------------------------

    existing_layers = (
        QgsProject.instance().mapLayersByName(
            layer_name
        )
    )

    if existing_layers:

        layer = existing_layers[0]

        log_message(
            "[FOOTPRINT] Utilizando camada existente."
        )

        return layer

    # --------------------------------------------------
    # CRIA NOVA CAMADA
    # --------------------------------------------------

    log_message(
        "[FOOTPRINT] Criando nova camada de footprints."
    )

    layer = QgsVectorLayer(

        "MultiPolygon?crs=EPSG:4326",

        layer_name,

        "memory"
    )

    if not layer.isValid():

        raise RuntimeError(
            "Não foi possível criar "
            "a camada de footprints."
        )

    provider = layer.dataProvider()

    # --------------------------------------------------
    # ATRIBUTOS
    # --------------------------------------------------

    provider.addAttributes([

        QgsField(
            "satellite",
            QVariant.String
        ),

        QgsField(
            "scene_id",
            QVariant.String
        ),

        QgsField(
            "family",
            QVariant.String
        ),

        QgsField(
            "location",
            QVariant.String
        ),

        QgsField(
            "date",
            QVariant.String
        ),

    ])

    layer.updateFields()

    # --------------------------------------------------
    # ADICIONA AO PROJETO
    # --------------------------------------------------

    QgsProject.instance().addMapLayer(
        layer
    )

    # --------------------------------------------------
    # APLICA ESTILO QML
    # --------------------------------------------------

    qml_path = (
        Path(__file__).parent
        / "qmd_footprint.qml"
    )

    if qml_path.exists():

        ok, error_message = layer.loadNamedStyle(
            str(qml_path)
        )

        if ok:

            layer.triggerRepaint()

            log_message(
                f"[FOOTPRINT] Estilo QML aplicado: "
                f"{qml_path.name}"
            )

        else:

            log_message(
                f"[FOOTPRINT] Erro ao aplicar QML: "
                f"{error_message}"
            )

    else:

        log_message(
            f"[FOOTPRINT] Arquivo QML não encontrado: "
            f"{qml_path}"
        )

    return layer


# ==========================================================
# OBTÉM CENAS JÁ EXISTENTES NA CAMADA
# ==========================================================

def get_existing_scene_ids(layer):

    existing_scene_ids = set()

    try:

        scene_id_index = (
            layer.fields().indexFromName(
                "scene_id"
            )
        )

        if scene_id_index < 0:

            log_message(
                "[FOOTPRINT] Campo scene_id "
                "não encontrado na camada."
            )

            return existing_scene_ids

        for feature in layer.getFeatures():

            scene_id = feature.attribute(
                scene_id_index
            )

            if scene_id:

                existing_scene_ids.add(
                    str(scene_id)
                )

        log_message(
            f"[FOOTPRINT] "
            f"{len(existing_scene_ids)} cena(s) "
            f"já existente(s) na camada."
        )

        return existing_scene_ids

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao verificar "
            f"cenas existentes: {e}"
        )

        return existing_scene_ids


# ==========================================================
# ADICIONA VÁRIOS FOOTPRINTS
# ==========================================================

def add_footprints(items):

    """
    Adiciona vários footprints em uma única camada.

    Não adiciona novamente cenas cujo scene_id já existe.

    Sentinel / CBERS / Amazônia:
        Utiliza item.geometry.

    Landsat:
        Calcula o footprint a partir do raster.
    """

    try:

        if not items:

            log_message(
                "[FOOTPRINT] Nenhum item recebido."
            )

            return None

        log_message(
            f"[FOOTPRINT] Processando "
            f"{len(items)} footprint(s)."
        )

        # --------------------------------------------------
        # CRIA OU REUTILIZA CAMADA
        # --------------------------------------------------

        layer = create_footprints_layer()

        provider = layer.dataProvider()

        # --------------------------------------------------
        # CENAS JÁ EXISTENTES
        # --------------------------------------------------

        existing_scene_ids = (
            get_existing_scene_ids(
                layer
            )
        )

        # --------------------------------------------------
        # CONTADORES
        # --------------------------------------------------

        features = []

        added_count = 0

        skipped_count = 0

        failed_count = 0

        total = len(
            items
        )

        # --------------------------------------------------
        # PROCESSA ITENS
        # --------------------------------------------------

        for index, item in enumerate(
            items,
            start=1
        ):

            item_id = str(
                getattr(
                    item,
                    "id",
                    ""
                )
                or ""
            )

            if not item_id:

                failed_count += 1

                log_message(
                    "[FOOTPRINT] Item sem ID. "
                    "Ignorando."
                )

                continue

            # ----------------------------------------------
            # VERIFICA DUPLICIDADE
            # ----------------------------------------------

            if item_id in existing_scene_ids:

                skipped_count += 1

                log_message(
                    f"[FOOTPRINT] ({index}/{total}) "
                    f"Footprint já adicionado: "
                    f"{item_id}"
                )

                continue

            try:

                log_message("")

                log_message(
                    f"[FOOTPRINT] "
                    f"({index}/{total}) Processando: "
                    f"{item_id}"
                )

                # ------------------------------------------
                # IDENTIFICA FAMÍLIA
                # ------------------------------------------

                family = get_item_family(
                    item
                )

                # ------------------------------------------
                # GERA FOOTPRINT
                # ------------------------------------------

                geometry = get_item_footprint(
                    item,
                    family
                )

                if geometry is None:

                    failed_count += 1

                    log_message(
                        f"[FOOTPRINT] "
                        f"Não foi possível gerar: "
                        f"{item_id}"
                    )

                    continue

                # ------------------------------------------
                # MULTIPOLYGON
                # ------------------------------------------

                if not geometry.isMultipart():

                    geometry.convertToMultiType()

                # ------------------------------------------
                # FEATURE
                # ------------------------------------------

                feature = QgsFeature(
                    layer.fields()
                )

                feature.setGeometry(
                    geometry
                )

                # ------------------------------------------
                # DATA
                # ------------------------------------------

                item_date = ""

                item_datetime = getattr(
                    item,
                    "datetime",
                    None
                )

                if item_datetime:

                    try:

                        item_date = (
                            item_datetime.strftime(
                                "%Y-%m-%d"
                            )
                        )

                    except Exception:

                        item_date = str(
                            item_datetime
                        )

                # ------------------------------------------
                # ATRIBUTOS
                # ------------------------------------------

                feature.setAttributes([

                    get_satellite_name(
                        item
                    ),

                    item_id,

                    family or "",

                    get_item_location(
                        item
                    ),

                    item_date,
                ])

                features.append(
                    feature
                )

                # ------------------------------------------
                # MARCA COMO JÁ ADICIONADO
                # ------------------------------------------

                existing_scene_ids.add(
                    item_id
                )

                added_count += 1

                log_message(
                    f"[FOOTPRINT] Footprint preparado: "
                    f"{item_id}"
                )

            except Exception as e:

                failed_count += 1

                log_message(
                    f"[FOOTPRINT] Erro na cena "
                    f"{item_id}: {e}"
                )

        # --------------------------------------------------
        # NENHUM NOVO FOOTPRINT
        # --------------------------------------------------

        if not features:

            if skipped_count > 0:

                log_message(
                    "[FOOTPRINT] Nenhum novo footprint "
                    "foi criado."
                )

                log_message(
                    "[FOOTPRINT] Todas as cenas "
                    "selecionadas já possuem footprint."
                )

            else:

                log_message(
                    "[FOOTPRINT] Nenhum footprint "
                    "foi gerado."
                )

            return layer

        # --------------------------------------------------
        # ADICIONA FEATURES
        # --------------------------------------------------

        success = provider.addFeatures(
            features
        )

        if not success:

            log_message(
                "[FOOTPRINT] Erro ao adicionar "
                "as feições à camada."
            )

            return layer

        layer.updateExtents()

        layer.triggerRepaint()

        # --------------------------------------------------
        # RESULTADO
        # --------------------------------------------------

        log_message(
            f"[FOOTPRINT] "
            f"{added_count} novo(s) footprint(s) "
            f"adicionado(s) à camada."
        )

        if skipped_count > 0:

            log_message(
                f"[FOOTPRINT] "
                f"{skipped_count} footprint(s) "
                f"já existiam e foram ignorados."
            )

        if failed_count > 0:

            log_message(
                f"[FOOTPRINT] "
                f"{failed_count} cena(s) "
                f"não puderam ser processadas."
            )

        return layer

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao adicionar "
            f"footprints: {e}"
        )

        return None


# ==========================================================
# APLICA ESTILO DA CAMADA
# ==========================================================

def apply_footprint_style(layer):

    """
    Estilo simples de fallback.

    O estilo principal da camada coletiva é o
    qmd_footprint.qml.
    """

    try:

        symbol = QgsFillSymbol.createSimple({

            "color": "255,255,255,0",

            "outline_color": "255,0,0,255",

            "outline_width": "0.8",

        })

        renderer = QgsSingleSymbolRenderer(
            symbol
        )

        layer.setRenderer(
            renderer
        )

        layer.triggerRepaint()

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao aplicar estilo: {e}"
        )


# ==========================================================
# EXIBE FOOTPRINT INDIVIDUAL NO QGIS
# ==========================================================

def show_item_footprint(
    item,
    family=None
):

    """
    Gera o footprint de uma cena e adiciona uma camada
    temporária individual ao projeto QGIS.
    """

    try:

        layer_name = (
            "QMD - Footprint da Cena"
        )

        # --------------------------------------------------
        # REMOVE CAMADA ANTERIOR
        # --------------------------------------------------

        existing_layers = (
            QgsProject.instance().mapLayersByName(
                layer_name
            )
        )

        for existing_layer in existing_layers:

            QgsProject.instance().removeMapLayer(
                existing_layer.id()
            )

        # --------------------------------------------------
        # GERA FOOTPRINT
        # --------------------------------------------------

        geometry = get_item_footprint(
            item,
            family
        )

        if geometry is None:

            log_message(
                "[FOOTPRINT] Não foi possível "
                "gerar o footprint."
            )

            return None

        # --------------------------------------------------
        # TIPO DE GEOMETRIA
        # --------------------------------------------------

        if geometry.isMultipart():

            geometry_type = (
                "MultiPolygon"
            )

        else:

            geometry_type = (
                "Polygon"
            )

        # --------------------------------------------------
        # CRIA CAMADA
        # --------------------------------------------------

        layer = QgsVectorLayer(

            f"{geometry_type}?crs=EPSG:4326",

            layer_name,

            "memory"
        )

        if not layer.isValid():

            log_message(
                "[FOOTPRINT] Não foi possível criar "
                "a camada temporária."
            )

            return None

        provider = layer.dataProvider()

        # --------------------------------------------------
        # FEATURE
        # --------------------------------------------------

        feature = QgsFeature()

        feature.setGeometry(
            geometry
        )

        provider.addFeatures(
            [feature]
        )

        layer.updateExtents()

        # --------------------------------------------------
        # ESTILO
        # --------------------------------------------------

        apply_footprint_style(
            layer
        )

        # --------------------------------------------------
        # ADICIONA AO PROJETO
        # --------------------------------------------------

        QgsProject.instance().addMapLayer(
            layer
        )

        # --------------------------------------------------
        # ZOOM
        # --------------------------------------------------

        canvas = iface.mapCanvas()

        source_crs = layer.crs()

        destination_crs = (
            canvas.mapSettings().destinationCrs()
        )

        transform = QgsCoordinateTransform(

            source_crs,

            destination_crs,

            QgsProject.instance()
        )

        canvas_extent = (
            transform.transformBoundingBox(
                layer.extent()
            )
        )

        canvas.setExtent(
            canvas_extent
        )

        canvas.refresh()

        log_message(
            f"[FOOTPRINT] Footprint exibido: "
            f"{item.id}"
        )

        return layer

    except Exception as e:

        log_message(
            f"[FOOTPRINT] Erro ao exibir "
            f"footprint: {e}"
        )

        return None