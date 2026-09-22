# -*- coding: utf-8 -*-
"""
Núcleo de acesso ao catálogo STAC.
"""

import sys
from pathlib import Path
from typing import List

from shapely.geometry import box, shape
from shapely import wkt as shapely_wkt


# =========================================================
# DEPENDÊNCIAS LOCAIS DO PLUGIN
# =========================================================

PLUGIN_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = PLUGIN_DIR / "vendor"

if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)

    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)


try:
    import pystac_client
except ImportError as e:
    raise ImportError(
        "Não foi possível carregar a dependência 'pystac_client'. "
        "Verifique se as pastas 'pystac' e 'pystac_client' estão "
        "dentro de qmd_tools_explorer/vendor/."
    ) from e


# =========================================================
# LOG
# =========================================================

_log_callback = None


def set_log_callback(callback):

    global _log_callback

    _log_callback = callback


def log_message(message: str):

    message = str(message)

    print(f"[DEBUG] {message}")

    if _log_callback is not None:

        try:
            _log_callback(message)

        except Exception as erro:
            print(f"[DEBUG] Falha no callback de log: {erro}")


# =========================================================
# CONEXÃO STAC
# =========================================================

def connect_to_stac(url: str):

    try:

        client = pystac_client.Client.open(url)

        log_message(
            f"Conectado ao STAC: {url}"
        )

        return client

    except Exception as e:

        log_message(
            f"Erro ao conectar ao STAC: {e}"
        )

        return None


# =========================================================
# BUSCA POR TILE
# =========================================================

def search_items(
    client,
    tile: str,
    start_date: str,
    end_date: str,
    collections: List[str],
    limit: int = 100,
):

    try:

        datetime_range = (
            f"{start_date}/{end_date}"
        )

        log_message(
            "======================================"
        )

        log_message(
            "BDC STAC - CONSULTA POR TILE"
        )

        log_message(
            f"Coleção: {collections}"
        )

        log_message(
            f"Tile: {tile}"
        )

        log_message(
            f"Período: {datetime_range}"
        )

        item_search = client.search(

            collections=collections,

            datetime=datetime_range,

            query={
                "bdc:tiles": {
                    "eq": tile
                }
            },

            limit=limit,
        )

        try:

            log_message(
                f"STAC matched(): "
                f"{item_search.matched()}"
            )

        except Exception as e:

            log_message(
                "Não foi possível obter "
                f"matched(): {e}"
            )

        items = list(
            item_search.get_items()
        )[::-1]

        log_message(
            f"Itens retornados: {len(items)}"
        )

        for item in items[:10]:

            log_message(
                f"  {item.id} | "
                f"{item.datetime}"
            )

        log_message(
            "======================================"
        )

        return items

    except Exception as e:

        log_message(
            f"Erro ao buscar itens: {e}"
        )

        return []


# =========================================================
# FOOTPRINT LANDSAT
# =========================================================

# Para Landsat, a validação espacial pode usar o mesmo footprint
# calculado a partir do raster utilizado pelo módulo de footprints.
#
# O BBOX continua sendo usado na consulta ao STAC para obter as
# cenas candidatas. Depois, somente as cenas cujo footprint real
# intersecta a AOI são mantidas.

VALIDAR_LANDSAT_PELO_FOOTPRINT = True


def _is_landsat_item(item):
    """Identifica cenas Landsat pelos prefixos dos IDs."""
    scene = str(getattr(item, "id", "")).upper()

    return scene.startswith(
        (
            "LC09",
            "LC08",
            "LE07",
            "LT05",
        )
    )


def _get_landsat_raster_asset_url(item):
    """
    Obtém uma URL raster do item Landsat.

    Prioriza a banda 'red', que é uma das bandas utilizadas pelo
    módulo de footprints, e usa outras bandas como fallback.
    """

    preferred = (
        "red",
        "green",
        "blue",
        "swir22",
        "nir08",
    )

    for key in preferred:
        asset = item.assets.get(key)

        if asset is not None:
            href = getattr(asset, "href", None)

            if href:
                return href

    # Fallback: procura qualquer asset GeoTIFF.
    for asset in item.assets.values():

        href = getattr(asset, "href", None)

        if (
            isinstance(href, str)
            and href.lower().split("?")[0].endswith(
                (".tif", ".tiff")
            )
        ):
            return href

    return None


def _landsat_footprint_from_raster(item):
    """
    Calcula o footprint Landsat diretamente do raster.

    A lógica segue o cálculo utilizado pelo módulo footprint.py:
    GDAL Footprint em EPSG:4326, simplificação e maxPoints=4.
    """

    from osgeo import gdal

    raster_url = _get_landsat_raster_asset_url(item)

    if not raster_url:
        raise RuntimeError(
            "Nenhum asset raster foi encontrado no item."
        )

    ds = None

    try:

        gdal.UseExceptions()

        ds = gdal.Open(
            f"/vsicurl/{raster_url}"
        )

        if ds is None:
            raise RuntimeError(
                "Não foi possível abrir o raster Landsat."
            )

        band = ds.GetRasterBand(1)

        if band is None:
            raise RuntimeError(
                "Não foi possível acessar a banda 1."
            )

        overview = int(
            band.GetOverviewCount() / 2
        )

        if band.GetNoDataValue() is None:
            band.SetNoDataValue(0.0)

        _, res_x, _, _, _, res_y = (
            ds.GetGeoTransform()
        )

        mean_res = (
            res_x + (-1 * res_y)
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

        footprint_wkt = gdal.Footprint(
            None,
            ds,
            format="WKT",
            dstSRS="EPSG:4326",
            bands=[1],
            ovr=overview,
            simplify=factor,
            maxPoints=4,
            minRingArea=factor ** 2 / 2,
        )

        if not footprint_wkt:
            raise RuntimeError(
                "GDAL não retornou o footprint Landsat."
            )

        return shapely_wkt.loads(
            footprint_wkt
        )

    finally:
        ds = None


def _calculate_roi_coverage(aoi_geom, item_geom):
    """
    Calcula quanto da AOI/BBOX está coberto pelo footprint da cena.

    Retorna percentual de 0 a 100, usando como denominador a área
    da AOI. A geometria da AOI e o footprint estão no mesmo CRS
    (EPSG:4326) nesta etapa.
    """

    if aoi_geom is None or item_geom is None:
        return 0.0

    aoi_area = aoi_geom.area

    if aoi_area <= 0:
        return 0.0

    intersection = aoi_geom.intersection(item_geom)

    if intersection.is_empty:
        return 0.0

    percentage = (
        intersection.area / aoi_area
    ) * 100.0

    return max(0.0, min(100.0, percentage))


# =========================================================
# BUSCA POR EXTENT / BBOX
# =========================================================

def search_items_by_bbox(
    client,
    bbox,
    start_date: str,
    end_date: str,
    collections: List[str],
    limit: int = 100,
):

    try:

        datetime_range = (
            f"{start_date}/{end_date}"
        )

        log_message(
            "======================================"
        )

        log_message(
            "BDC STAC - CONSULTA POR EXTENT"
        )

        log_message(
            f"Coleção: {collections}"
        )

        log_message(
            f"BBOX: {bbox}"
        )

        log_message(
            f"Período: {datetime_range}"
        )

        item_search = client.search(

            collections=collections,

            datetime=datetime_range,

            bbox=bbox,

            limit=limit,
        )

        try:

            log_message(
                f"STAC matched(): "
                f"{item_search.matched()}"
            )

        except Exception as e:

            log_message(
                "Não foi possível obter "
                f"matched(): {e}"
            )

        items_stac = list(
            item_search.get_items()
        )

        log_message(
            f"Itens retornados pelo STAC: {len(items_stac)}"
        )

        log_message(
            f"BBOX consultado: {bbox}"
        )

        # -----------------------------------------------------
        # VALIDAÇÃO GEOMÉTRICA DA AOI
        # -----------------------------------------------------
        # O STAC pode retornar itens pelo BBOX do Item. Aqui
        # verificamos a geometria real (footprint) de cada cena
        # para garantir que ela realmente intersecta a AOI.
        # -----------------------------------------------------

        aoi_geom = box(
            bbox[0],
            bbox[1],
            bbox[2],
            bbox[3],
        )

        items = []
        descartados = 0

        for item in items_stac:

            item_id = item.id

            # -----------------------------------------------------
            # LANDSAT
            # -----------------------------------------------------
            # Para Landsat, usamos o footprint calculado a partir
            # do raster, que é a mesma geometria exibida no mapa.
            #
            # Assim, a busca e a visualização passam a usar a
            # mesma definição espacial da cena.
            # -----------------------------------------------------

            if (
                VALIDAR_LANDSAT_PELO_FOOTPRINT
                and _is_landsat_item(item)
            ):

                try:

                    item_geom = (
                        _landsat_footprint_from_raster(
                            item
                        )
                    )

                    intersects = (
                        aoi_geom.intersects(
                            item_geom
                        )
                    )

                    roi_coverage = _calculate_roi_coverage(
                        aoi_geom,
                        item_geom,
                    )

                    # Guarda a cobertura para a tabela de resultados.
                    item.properties[
                        "_qmd_roi_coverage"
                    ] = roi_coverage

                    log_message(
                        f"ID: {item_id}"
                    )

                    log_message(
                        "  Família: Landsat"
                    )

                    log_message(
                        f"  BBOX da cena: {item.bbox}"
                    )

                    log_message(
                        "  Validação: footprint "
                        "calculado do raster"
                    )

                    log_message(
                        f"  Intersecta AOI: {intersects}"
                    )

                    log_message(
                        f"  Cobertura da AOI: "
                        f"{roi_coverage:.2f}%"
                    )

                    if intersects:
                        items.append(item)
                    else:
                        descartados += 1

                    continue

                except Exception as e:

                    # Não deixa uma falha no cálculo do footprint
                    # interromper toda a pesquisa. Nesse caso usamos
                    # a geometria do STAC como fallback.
                    log_message(
                        f"Falha ao calcular footprint Landsat "
                        f"de {item_id}: {e}"
                    )

                    log_message(
                        "  Fallback: item.geometry"
                    )

            # -----------------------------------------------------
            # DEMAIS COLEÇÕES
            # -----------------------------------------------------

            if not item.geometry:

                log_message(
                    f"Item sem geometry descartado: {item_id}"
                )

                descartados += 1
                continue

            try:

                item_geom = shape(
                    item.geometry
                )

                intersects = (
                    aoi_geom.intersects(
                        item_geom
                    )
                )

                roi_coverage = _calculate_roi_coverage(
                    aoi_geom,
                    item_geom,
                )

                # Guarda a cobertura para a tabela de resultados.
                item.properties[
                    "_qmd_roi_coverage"
                ] = roi_coverage

            except Exception as e:

                log_message(
                    f"Erro ao validar geometria de "
                    f"{item_id}: {e}"
                )

                descartados += 1
                continue

            log_message(
                f"ID: {item_id}"
            )

            log_message(
                f"  Tile: "
                f"{item.properties.get('bdc:tiles')}"
            )

            log_message(
                f"  BBOX da cena: {item.bbox}"
            )

            log_message(
                f"  Geometry: "
                f"{item.geometry is not None}"
            )

            log_message(
                "  Validação: item.geometry"
            )

            log_message(
                f"  Intersecta AOI: {intersects}"
            )

            log_message(
                f"  Cobertura da AOI: "
                f"{roi_coverage:.2f}%"
            )

            if intersects:
                items.append(item)
            else:
                descartados += 1

        # Mantém a ordem anterior dos resultados.
        items = items[::-1]

        log_message(
            f"Itens após validação espacial: {len(items)}"
        )
        log_message(
            f"Itens descartados por não intersectarem a AOI: {descartados}"
        )
        log_message(
            "======================================"
        )

        return items

    except Exception as e:

        log_message(
            f"Erro ao buscar itens por extent: {e}"
        )

        return []


# =========================================================
# IDENTIFICA FAMÍLIA / SATÉLITE
# =========================================================

def get_satellite_name(item, satellite):

    scene = item.id.upper()

    satellite = (
        satellite or ""
    ).strip()


    # -----------------------------------------------------
    # SENTINEL-2
    # -----------------------------------------------------

    if satellite == "Sentinel-2":

        if scene.startswith("S2A"):

            return "Sentinel-2A"

        if scene.startswith("S2B"):

            return "Sentinel-2B"

        if scene.startswith("S2C"):

            return "Sentinel-2C"

        return "Sentinel-2"


    # -----------------------------------------------------
    # LANDSAT
    # -----------------------------------------------------

    if satellite == "Landsat":

        if scene.startswith("LC09"):

            return "Landsat-9"

        if scene.startswith("LC08"):

            return "Landsat-8"

        if scene.startswith("LE07"):

            return "Landsat-7"

        if scene.startswith("LT05"):

            return "Landsat-5"

        return "Landsat"


    # -----------------------------------------------------
    # AMAZONIA-1
    # -----------------------------------------------------

    if satellite == "Amazonia-1":

        return "Amazonia-1"


    # -----------------------------------------------------
    # CBERS-4
    # -----------------------------------------------------

    if satellite == "CBERS-4":

        return "CBERS-4"


    # -----------------------------------------------------
    # CBERS-4A
    # -----------------------------------------------------

    if satellite == "CBERS-4A":

        return "CBERS-4A"


    # -----------------------------------------------------
    # FALLBACK PELO ID
    # -----------------------------------------------------

    if scene.startswith("AMAZONIA_1"):

        return "Amazonia-1"

    if scene.startswith("CBERS_4A"):

        return "CBERS-4A"

    if scene.startswith("CBERS_4"):

        return "CBERS-4"

    return satellite or "Desconhecido"


# =========================================================
# TILE / ÓRBITA-PONTO
# =========================================================

def get_item_tile(item, satellite):

    scene = item.id.upper()

    satellite = (
        satellite or ""
    ).strip()


    # -----------------------------------------------------
    # SENTINEL-2
    # -----------------------------------------------------

    if satellite == "Sentinel-2":

        tiles = item.properties.get(
            "bdc:tiles"
        )

        if tiles:

            return tiles[0]

        return "N/A"


    # -----------------------------------------------------
    # AMAZONIA-1
    #
    # Exemplo:
    #
    # AMAZONIA_1_WFI_20260820_036_017_L4
    #
    # Resultado:
    #
    # 036_017
    # -----------------------------------------------------

    if satellite == "Amazonia-1":

        parts = item.id.split("_")

        if len(parts) >= 7:

            path = parts[4]
            row = parts[5]

            return f"{path}_{row}"

        return "N/A"


    # -----------------------------------------------------
    # CBERS-4 / CBERS-4A
    #
    # Tenta obter path_row do identificador.
    # -----------------------------------------------------

    if satellite in [
        "CBERS-4",
        "CBERS-4A",
    ]:

        parts = item.id.split("_")

        # Primeiro tenta localizar dois valores
        # numéricos consecutivos após a data.
        for i, part in enumerate(parts):

            if (
                len(part) == 8
                and part.isdigit()
            ):

                if i + 2 < len(parts):

                    path = parts[i + 1]
                    row = parts[i + 2]

                    if (
                        path.isdigit()
                        and row.isdigit()
                    ):

                        return (
                            f"{path}_{row}"
                        )

        # Fallback anterior
        if len(parts) > 2:

            return parts[2]

        return "N/A"


    # -----------------------------------------------------
    # LANDSAT
    # -----------------------------------------------------

    if satellite == "Landsat":

        parts = item.id.split("_")

        if len(parts) > 2:

            return parts[2]

        return "N/A"


    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    tiles = item.properties.get(
        "bdc:tiles"
    )

    if tiles:

        return tiles[0]

    return "N/A"


# =========================================================
# SENSOR
# =========================================================

def get_sensor_name(item, satellite):

    scene = item.id.upper()


    # -----------------------------------------------------
    # AMAZONIA-1
    # -----------------------------------------------------

    if satellite == "Amazonia-1":

        if "_WFI_" in scene:

            return "WFI"

        return "WFI"


    # -----------------------------------------------------
    # CBERS-4
    # -----------------------------------------------------

    if satellite == "CBERS-4":

        if "_WFI_" in scene:

            return "WFI"

        if "_MUX_" in scene:

            return "MUX"

        return "CBERS"


    # -----------------------------------------------------
    # CBERS-4A
    # -----------------------------------------------------

    if satellite == "CBERS-4A":

        if "_WFI_" in scene:

            return "WFI"

        if "_MUX_" in scene:

            return "MUX"

        return "CBERS"


    # -----------------------------------------------------
    # SENTINEL
    # -----------------------------------------------------

    if satellite == "Sentinel-2":

        return "MSI"


    # -----------------------------------------------------
    # LANDSAT
    # -----------------------------------------------------

    if satellite == "Landsat":

        return "OLI"


    return ""


# =========================================================
# ÓRBITA RELATIVA
# =========================================================

def get_relative_orbit(item):

    for part in item.id.split("_"):

        if (
            part.startswith("R")
            and part[1:].isdigit()
        ):

            return part

    return "R000"


# =========================================================
# NOME DA CAMADA NO QGIS
# =========================================================

def get_layer_name(item, satellite):

    satellite_name = get_satellite_name(
        item,
        satellite,
    )

    tile = get_item_tile(
        item,
        satellite,
    )

    sensor = get_sensor_name(
        item,
        satellite,
    )

    date = item.datetime.strftime(
        "%d/%m/%Y"
    )


    # -----------------------------------------------------
    # AMAZONIA-1 / CBERS
    #
    # Formato:
    #
    # Amazonia-1 | 20/08/2026 | 036_017 | WFI | Falsa Cor
    # -----------------------------------------------------

    if satellite in [
        "Amazonia-1",
        "CBERS-4",
        "CBERS-4A",
    ]:

        return (
            f"{satellite_name} | "
            f"{date} | "
            f"{tile} | "
            f"{sensor} | "
            f"Falsa Cor"
        )


    # -----------------------------------------------------
    # SENTINEL / LANDSAT
    #
    # Mantém o padrão anterior.
    # -----------------------------------------------------

    return (
        f"{satellite_name} | "
        f"{date} | "
        f"{tile} | "
        f"Falsa Cor"
    )