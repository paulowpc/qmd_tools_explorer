# -*- coding: utf-8 -*-
"""
AVISOS INMET -> GeoPackage para QGIS
"""

import os
import re
import html
from lxml import etree
from datetime import datetime, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QColor

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsSymbol,
    QgsSimpleFillSymbolLayer,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
)

XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

RSS_URL = "https://apiprevmet3.inmet.gov.br/avisos/rss"

# [] = descobrir automaticamente no RSS.
# ["55660"] = testar somente um aviso.
INMET_IDS = []

# hoje   = avisos cuja validade cruza o dia atual.
# ativos = somente avisos válidos neste momento.
# todos  = sem filtro temporal.
FILTRO_DATA = "hoje"

# Número de downloads simultâneos.
# Como a parte pesada é rede/XML, isso reduz bastante o tempo.
MAX_WORKERS = 8

# GeoPackage gerado pelo plugin:
PLUGIN_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

REFERENCE_CACHE_DIR = os.path.join(
    PLUGIN_DIR,
    "data",
    "reference_layers_cache"
)

os.makedirs(
    REFERENCE_CACHE_DIR,
    exist_ok=True
)

OUTPUT_GPKG = os.path.join(
    REFERENCE_CACHE_DIR,
    "avisos_inmet.gpkg"
)

LAYER_NAME = "avisos_inmet"

ADD_TO_PROJECT = True
OVERWRITE_GPKG = True


# ============================================================
# UTILITÁRIOS XML
# ============================================================

def strip_namespace(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def find_text(element, *names):
    nomes = {n.lower() for n in names}

    for child in element.iter():
        if strip_namespace(child.tag).lower() in nomes:
            if child.text:
                return child.text.strip()

    return None


def find_all_elements(element, name):
    nome = name.lower()

    return [
        child
        for child in element.iter()
        if strip_namespace(child.tag).lower() == nome
    ]


def clean_text(value):
    if not value:
        return None

    value = html.unescape(value)

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.I
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value
    )

    value = re.sub(
        r"\r\n?",
        "\n",
        value
    )

    value = re.sub(
        r"[ \t]+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# DATAS
# ============================================================

def parse_datetime(value):
    if not value:
        return None

    value = value.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Tenta os formatos alternativos abaixo.
        pass

    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(
                value,
                formato
            )
        except ValueError:
            # Tenta o próximo formato de data.
            pass

    return None


def datetime_local(value):
    dt = parse_datetime(value)

    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt

    return dt.astimezone().replace(
        tzinfo=None
    )


def intervalo_hoje():
    hoje = datetime.now().date()

    return (
        datetime.combine(
            hoje,
            time.min
        ),
        datetime.combine(
            hoje,
            time.max
        ),
    )


def aviso_cruza_hoje(
    onset,
    expires
):
    inicio_dia, fim_dia = intervalo_hoje()

    inicio = datetime_local(
        onset
    )

    fim = datetime_local(
        expires
    )

    if inicio is None and fim is None:
        return True

    if inicio is None:
        return fim >= inicio_dia

    if fim is None:
        return inicio <= fim_dia

    return (
        inicio <= fim_dia
        and
        fim >= inicio_dia
    )


def aviso_ativo_agora(
    onset,
    expires
):
    agora = datetime.now()

    inicio = datetime_local(
        onset
    )

    fim = datetime_local(
        expires
    )

    if inicio is not None:
        if agora < inicio:
            return False

    if fim is not None:
        if agora > fim:
            return False

    return True


def passa_filtro_data(
    onset,
    expires
):
    if FILTRO_DATA == "todos":
        return True

    if FILTRO_DATA == "ativos":
        return aviso_ativo_agora(
            onset,
            expires
        )

    return aviso_cruza_hoje(
        onset,
        expires
    )


# ============================================================
# SEVERIDADE
# ============================================================

def nivel_inmet(severity):
    """
    CAP -> classificação exibida pelo INMET.

    Moderate = Perigo Potencial
    Severe   = Perigo
    Extreme  = Grande Perigo
    """

    if not severity:
        return "Não informado"

    valor = severity.strip().lower()

    if valor in (
        "extreme",
        "grande perigo"
    ):
        return "Grande Perigo"

    if valor in (
        "severe",
        "perigo"
    ):
        return "Perigo"

    if valor in (
        "moderate",
        "perigo potencial"
    ):
        return "Perigo Potencial"

    if valor in (
        "minor",
        "menor"
    ):
        return "Menor"

    return severity


# ============================================================
# POLYGON
# ============================================================

def parse_polygon_text(text):

    if not text:
        return []

    text = text.replace(
        "\n",
        " "
    )

    text = text.replace(
        "\r",
        " "
    )

    tokens = text.split()

    points = []

    for token in tokens:

        token = token.strip().strip(",")

        if not token:
            continue

        partes = token.split(",")

        if len(partes) != 2:
            continue

        try:
            lat = float(
                partes[0]
            )

            lon = float(
                partes[1]
            )

        except ValueError:
            continue

        if not (
            -90 <= lat <= 90
        ):
            continue

        if not (
            -180 <= lon <= 180
        ):
            continue

        # INMET fornece latitude,longitude.
        # QGIS utiliza x=longitude, y=latitude.
        points.append(
            (lon, lat)
        )

    return points


# ============================================================
# DOWNLOAD
# ============================================================

def baixar_xml(url):

    from urllib.request import (
        Request,
        urlopen
    )

    parsed_url = urlparse(url)

    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError(
            f"Esquema de URL não permitido: {parsed_url.scheme}"
        )

    request = Request(
        url,
        headers={
            "User-Agent":
                "QGIS-INMET-Alerts/1.0"
        }
    )

    with urlopen( # nosec B310
        request,
        timeout=30
    ) as response:

        return response.read()
    
# ============================================================
# RSS
# ============================================================

def obter_itens_rss():

    print(
        "\nConsultando RSS do INMET:"
    )

    print(
        RSS_URL
    )

    data = baixar_xml(
        RSS_URL
    )

    root = etree.fromstring(
        data,
        parser=XML_PARSER,
    )

    itens = []

    for item in root.iter():

        tag_item = (
            strip_namespace(
                item.tag
            ).lower()
        )

        if tag_item not in (
            "item",
            "entry"
        ):
            continue

        dados = {
            "id": None,
            "identifier": None,
            "msg_type": None,
            "link": None,
            "sent": None,
        }

        # Procura nos descendentes do item.
        for child in item.iter():

            tag = (
                strip_namespace(
                    child.tag
                ).lower()
            )

            texto = (
                child.text or ""
            ).strip()

            if tag in (
                "guid",
                "id"
            ):
                dados["identifier"] = (
                    texto
                )

            elif tag == "link":

                dados["link"] = (
                    texto
                    or
                    child.attrib.get(
                        "href"
                    )
                )

            elif tag == "msgtype":

                dados["msg_type"] = (
                    texto
                )

            elif tag == "sent":

                dados["sent"] = (
                    texto
                )

        # Descobre o ID pelo identifier/link.
        candidato = None

        for valor in (
            dados["identifier"],
            dados["link"],
        ):

            if not valor:
                continue

            # /avisos/rss/55660
            match = re.search(
                r"/(\d+)(?:/)?$",
                valor
            )

            if match:
                candidato = (
                    match.group(1)
                )
                break

            # Caso o guid termine em número.
            match = re.search(
                r"(\d+)\s*$",
                valor
            )

            if match:
                candidato = (
                    match.group(1)
                )
                break

        dados["id"] = candidato

        if dados["id"]:
            itens.append(
                dados
            )

    # Remove duplicados pelo ID.
    resultado = {}

    for item in itens:
        resultado[
            item["id"]
        ] = item

    return list(
        resultado.values()
    )


def obter_ids_rss():

    itens = obter_itens_rss()

    total = len(itens)

    # --------------------------------------------------------
    # Filtra Cancel/Update/qualquer coisa que não seja Alert
    # já no RSS quando msgType estiver disponível.
    # --------------------------------------------------------

    alertas = []

    desconhecidos = []

    for item in itens:

        msg_type = (
            item["msg_type"]
            or ""
        ).strip().lower()

        if msg_type == "alert":

            alertas.append(
                item
            )

        elif msg_type:

            # Cancel, Update, Ack, Error etc.
            continue

        else:

            # RSS não informou o msgType.
            # Nesse caso precisamos consultar o CAP individual.
            desconhecidos.append(
                item
            )

    print(
        f"\nItens encontrados no RSS: {total}"
    )

    print(
        f"Alert no RSS:              {len(alertas)}"
    )

    print(
        f"Sem msgType no RSS:        {len(desconhecidos)}"
    )

    print(
        f"Cancel/Update/etc. removidos no RSS: "
        f"{total - len(alertas) - len(desconhecidos)}"
    )

    # Se o RSS não fornecer msgType, mantemos esses IDs como
    # fallback. Eles serão filtrados depois, no CAP individual.
    return alertas + desconhecidos


# ============================================================
# AVISO INDIVIDUAL
# ============================================================

def obter_aviso(
    aviso_id,
    msg_type_rss=None
):

    url = (
        f"{RSS_URL}/{aviso_id}"
    )

    data = baixar_xml(
        url
    )

    root = etree.fromstring(
        data,
        parser=XML_PARSER,
    )

    # msgType no documento CAP.
    msg_type = clean_text(
        find_text(
            root,
            "msgType"
        )
    )

    # REGRA PRINCIPAL:
    # somente Alert.
    if (
        msg_type
        and
        msg_type.strip().lower()
        != "alert"
    ):

        return []

    infos = find_all_elements(
        root,
        "info"
    )

    if not infos:
        infos = [root]

    registros = []

    for info in infos:

        event = clean_text(
            find_text(
                info,
                "event"
            )
        )

        headline = clean_text(
            find_text(
                info,
                "headline"
            )
        )

        description = clean_text(
            find_text(
                info,
                "description"
            )
        )

        instruction = clean_text(
            find_text(
                info,
                "instruction"
            )
        )

        severity = clean_text(
            find_text(
                info,
                "severity"
            )
        )

        urgency = clean_text(
            find_text(
                info,
                "urgency"
            )
        )

        certainty = clean_text(
            find_text(
                info,
                "certainty"
            )
        )

        category = clean_text(
            find_text(
                info,
                "category"
            )
        )

        response_type = clean_text(
            find_text(
                info,
                "responseType"
            )
        )

        effective = clean_text(
            find_text(
                info,
                "effective"
            )
        )

        onset = clean_text(
            find_text(
                info,
                "onset"
            )
        )

        expires = clean_text(
            find_text(
                info,
                "expires"
            )
        )

        # ----------------------------------------------------
        # FILTRO TEMPORAL
        # ----------------------------------------------------

        if not passa_filtro_data(
            onset,
            expires
        ):
            continue

        sender = clean_text(
            find_text(
                root,
                "sender"
            )
        )

        sent = clean_text(
            find_text(
                root,
                "sent"
            )
        )

        status = clean_text(
            find_text(
                root,
                "status"
            )
        )

        scope = clean_text(
            find_text(
                root,
                "scope"
            )
        )

        identifier = clean_text(
            find_text(
                root,
                "identifier"
            )
        )

        areas = find_all_elements(
            info,
            "area"
        )

        if not areas:
            areas = [info]

        for area in areas:

            area_desc = clean_text(
                find_text(
                    area,
                    "areaDesc"
                )
            )

            polygons = find_all_elements(
                area,
                "polygon"
            )

            if not polygons:

                polygons = (
                    find_all_elements(
                        info,
                        "polygon"
                    )
                )

            for polygon in polygons:

                polygon_text = (
                    polygon.text
                    or ""
                )

                points = (
                    parse_polygon_text(
                        polygon_text
                    )
                )

                if len(points) < 3:
                    continue

                if points[0] == points[-1]:
                    points = points[:-1]

                if len(points) < 3:
                    continue

                registros.append({

                    "alert_id":
                        str(aviso_id),

                    "identifier":
                        identifier,

                    "sender":
                        sender,

                    "sent":
                        sent,

                    "status":
                        status,

                    "msg_type":
                        msg_type or "Alert",

                    "scope":
                        scope,

                    "category":
                        category,

                    "event":
                        event,

                    "response":
                        response_type,

                    "urgency":
                        urgency,

                    "severity":
                        severity,

                    "nivel_inmet":
                        nivel_inmet(
                            severity
                        ),

                    "certainty":
                        certainty,

                    "effective":
                        effective,

                    "onset":
                        onset,

                    "expires":
                        expires,

                    "headline":
                        headline,

                    "description":
                        description,

                    "instruction":
                        instruction,

                    "area_desc":
                        area_desc,

                    "polygon_txt":
                        polygon_text.strip(),

                    "source_url":
                        url,
                })

    return registros


# ============================================================
# CAMADA
# ============================================================

def criar_camada_memoria(
    registros
):

    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326",
        LAYER_NAME,
        "memory"
    )

    provider = (
        layer.dataProvider()
    )

    campos = [

        ("alert_id", QVariant.String, 20),
        ("identifier", QVariant.String, 120),
        ("sender", QVariant.String, 150),
        ("sent", QVariant.String, 40),
        ("status", QVariant.String, 30),
        ("msg_type", QVariant.String, 20),
        ("scope", QVariant.String, 30),

        ("category", QVariant.String, 50),
        ("event", QVariant.String, 100),
        ("response", QVariant.String, 100),
        ("urgency", QVariant.String, 50),
        ("severity", QVariant.String, 50),
        ("nivel_inmet", QVariant.String, 50),
        ("certainty", QVariant.String, 50),

        ("effective", QVariant.String, 40),
        ("onset", QVariant.String, 40),
        ("expires", QVariant.String, 40),

        ("headline", QVariant.String, 255),
        ("description", QVariant.String, 5000),
        ("instruction", QVariant.String, 5000),

        ("area_desc", QVariant.String, 5000),
        ("polygon_txt", QVariant.String, 10000),

        ("source_url", QVariant.String, 255),
    ]

    provider.addAttributes([
        QgsField(
            nome,
            tipo,
            len=tamanho
        )
        for nome, tipo, tamanho in campos
    ])

    layer.updateFields()

    features = []

    for registro in registros:

        points = parse_polygon_text(
            registro[
                "polygon_txt"
            ]
        )

        if len(points) < 3:
            continue

        qpoints = [
            QgsPointXY(
                lon,
                lat
            )
            for lon, lat in points
        ]

        if qpoints[0] != qpoints[-1]:
            qpoints.append(
                qpoints[0]
            )

        geom = (
            QgsGeometry.fromPolygonXY(
                [qpoints]
            )
        )

        if geom.isEmpty():
            continue

        feature = QgsFeature(
            layer.fields()
        )

        feature.setGeometry(
            geom
        )

        for campo in layer.fields():

            nome = campo.name()

            feature[nome] = (
                registro.get(
                    nome
                )
            )

        features.append(
            feature
        )

    provider.addFeatures(
        features
    )

    layer.updateExtents()

    return layer


# ============================================================
# SIMBOLOGIA
# ============================================================

CORES_INMET = {
    "Grande Perigo": "#FF0000",
    "Perigo": "#FFA500",
    "Perigo Potencial": "#FFFF00",
}


def criar_simbolo(cor):
    """
    Cria o símbolo do alerta com configurações independentes
    para o preenchimento e para a linha.

    Fill:
        opacidade = 0.25

    Linha:
        sólida
        opacidade = 1.00
        largura = 0.2 mm

    Importante:
    Não usamos symbol.setOpacity(), pois isso alteraria
    simultaneamente o fill e o contorno.
    """

    symbol = QgsSymbol.defaultSymbol(
        QgsWkbTypes.PolygonGeometry
    )

    fill = symbol.symbolLayer(0)

    if isinstance(fill, QgsSimpleFillSymbolLayer):

        # ----------------------------------------------------
        # FILL
        # ----------------------------------------------------
        #
        # QColor com alpha 25%:
        # 0   = totalmente transparente
        # 255 = totalmente opaco
        #
        # 0.25 * 255 = aproximadamente 64
        #

        fill_color = QColor(cor)
        fill_color.setAlpha(64)

        fill.setColor(
            fill_color
        )

        # ----------------------------------------------------
        # LINHA
        # ----------------------------------------------------
        #
        # Linha totalmente opaca.
        #

        stroke_color = QColor(cor)
        stroke_color.setAlpha(255)

        fill.setStrokeColor(
            stroke_color
        )

        # Largura em milímetros.
        fill.setStrokeWidth(
            0.2
        )

        # Linha sólida.
        try:
            fill.setStrokeStyle(
                Qt.SolidLine
            )

        except Exception as erro:
            print(
                f"[QMD Tools Explorer] "
                f"Não foi possível definir o estilo da linha: {erro}"
            )


    # NÃO usar symbol.setOpacity() aqui.
    #
    # A opacidade do fill já foi definida diretamente no
    # QColor do preenchimento, enquanto a linha permanece
    # 100% opaca.

    return symbol


def aplicar_simbologia_classe(layer, classe):
    """
    Aplica a simbologia de uma única classe.

    As camadas são filtradas por nivel_inmet, portanto cada camada
    possui apenas uma categoria:
        Grande Perigo
        Perigo
        Perigo Potencial
    """

    cor = CORES_INMET[classe]

    symbol = criar_simbolo(cor)

    renderer = QgsSingleSymbolRenderer(symbol)

    layer.setRenderer(renderer)
    layer.triggerRepaint()


# ============================================================
# CAMADAS POR SEVERIDADE
# ============================================================

def criar_camadas_severidade(gpkg_path):
    """
    Cria três camadas apontando para o mesmo GeoPackage.

    Ordem visual no QGIS:
        Grande Perigo       -> por cima
        Perigo              -> meio
        Perigo Potencial    -> por baixo

    Não duplica os dados no GeoPackage. São três referências à
    mesma camada física, cada uma com um filtro diferente.
    """

    classes = [
        ("Grande Perigo", '"nivel_inmet" = \'Grande Perigo\''),
        ("Perigo", '"nivel_inmet" = \'Perigo\''),
        ("Perigo Potencial", '"nivel_inmet" = \'Perigo Potencial\''),
    ]

    layers = []

    for nome, filtro in classes:

        uri = (
            f"{gpkg_path}|"
            f"layername={LAYER_NAME}"
        )

        layer = QgsVectorLayer(
            uri,
            nome,
            "ogr"
        )

        if not layer.isValid():
            raise RuntimeError(
                f"Não foi possível abrir a camada "
                f"para a classe: {nome}"
            )

        layer.setSubsetString(filtro)

        aplicar_simbologia_classe(
            layer,
            nome
        )

        configurar_maptip(layer)

        layers.append(layer)

    return layers


def adicionar_camadas_ordenadas(gpkg_path):
    """
    Adiciona três referências à mesma camada do GeoPackage.

    Ordem no painel e ordem de desenho:

        Grande Perigo       -> topo / por cima
        Perigo              -> meio
        Perigo Potencial    -> baixo / por baixo

    O GeoPackage continua contendo somente uma camada física:
        avisos_inmet

    As três camadas no projeto usam filtros diferentes sobre essa
    mesma camada, portanto não há duplicação dos dados no arquivo.
    """

    project = QgsProject.instance()
    root = project.layerTreeRoot()

    nomes = [
        "Grande Perigo",
        "Perigo",
        "Perigo Potencial",
    ]

    # --------------------------------------------------------
    # Remove grupo antigo e suas camadas.
    # --------------------------------------------------------

    ids_para_remover = []

    for layer in project.mapLayers().values():

        if layer.name() in nomes:
            ids_para_remover.append(layer.id())

    if ids_para_remover:
        project.removeMapLayers(
            ids_para_remover
        )

    for child in list(root.children()):

        if child.name() == "Avisos INMET":
            root.removeChildNode(child)

    # --------------------------------------------------------
    # Cria grupo.
    # --------------------------------------------------------

    group = root.insertGroup(
        0,
        "Avisos INMET"
    )

    # --------------------------------------------------------
    # Ordem desejada.
    #
    # O primeiro item fica no topo do painel.
    # No QGIS, camadas inferiores são desenhadas primeiro.
    # Portanto Perigo Potencial fica por baixo.
    # --------------------------------------------------------

    ordem = [

        (
            "Grande Perigo",
            '"nivel_inmet" = \'Grande Perigo\''
        ),

        (
            "Perigo",
            '"nivel_inmet" = \'Perigo\''
        ),

        (
            "Perigo Potencial",
            '"nivel_inmet" = \'Perigo Potencial\''
        ),
    ]

    camadas = []

    for nome, filtro in ordem:

        uri = (
            f"{gpkg_path}|"
            f"layername={LAYER_NAME}"
        )

        layer = QgsVectorLayer(
            uri,
            nome,
            "ogr"
        )

        if not layer.isValid():

            raise RuntimeError(
                f"Camada inválida: {nome}"
            )

        layer.setSubsetString(
            filtro
        )

        aplicar_simbologia_classe(
            layer,
            nome
        )

        configurar_maptip(
            layer
        )

        project.addMapLayer(
            layer,
            False
        )

        camadas.append(
            layer
        )

    # --------------------------------------------------------
    # Insere exatamente na ordem desejada.
    # --------------------------------------------------------

    for layer in camadas:
        group.addLayer(layer)

    # --------------------------------------------------------
    # Visibilidade.
    # --------------------------------------------------------

    for node in group.children():
        node.setItemVisibilityChecked(
            True
        )

    print(
        "\nOrdem das camadas no QGIS:"
    )

    for node in group.children():
        print(
            f"  {node.name()}"
        )

    print(
        "\nGrande Perigo = por cima"
    )

    print(
        "Perigo = intermediária"
    )

    print(
        "Perigo Potencial = por baixo"
    )

    return group


# ============================================================
# MAP TIP
# ============================================================

def configurar_maptip(
    layer
):

    html_template = """
    <div style="
        font-family: Arial, sans-serif;
        min-width: 320px;
        max-width: 500px;
        padding: 8px;
    ">

        <h2 style="margin-bottom: 4px;">
            INMET — [% "event" %]
        </h2>

        <div style="
            font-size: 15px;
            font-weight: bold;
            margin-bottom: 8px;
        ">
            [% "nivel_inmet" %]
        </div>

        <hr>

        <b>Início:</b>
        [% "onset" %]
        <br>

        <b>Fim:</b>
        [% "expires" %]
        <br><br>

        <b>Área:</b>
        <br>
        [% "area_desc" %]
        <br><br>

        <b>Descrição:</b>
        <br>
        [% "description" %]
        <br><br>

        <b>Instruções:</b>
        <br>
        [% "instruction" %]
        <br><br>

        <b>Fonte:</b> INMET
        <br><br>

        <a href="[% "source_url" %]">
            Abrir aviso no INMET
        </a>

    </div>
    """

    layer.setMapTipTemplate(
        html_template
    )


# ============================================================
# GEOPACKAGE
# ============================================================

def salvar_geopackage(
    layer,
    caminho
):

    caminho = os.path.abspath(
        caminho
    )

    pasta = os.path.dirname(
        caminho
    )

    if (
        pasta
        and
        not os.path.exists(pasta)
    ):
        os.makedirs(pasta)

    if (
        OVERWRITE_GPKG
        and
        os.path.exists(caminho)
    ):

        try:
            os.remove(caminho)

        except Exception as exc:

            raise RuntimeError(
                "Não foi possível substituir "
                "o GeoPackage existente:\n"
                f"{caminho}\n\n"
                f"{exc}"
            )

    options = (
        QgsVectorFileWriter
        .SaveVectorOptions()
    )

    options.driverName = "GPKG"
    options.layerName = LAYER_NAME

    options.actionOnExistingFile = (
        QgsVectorFileWriter
        .CreateOrOverwriteFile
    )

    result = (
        QgsVectorFileWriter
        .writeAsVectorFormatV3(
            layer,
            caminho,
            QgsProject.instance()
            .transformContext(),
            options
        )
    )

    if (
        result[0]
        != QgsVectorFileWriter.NoError
    ):

        raise RuntimeError(
            f"Erro ao salvar GeoPackage: "
            f"{result}"
        )

    print(
        "\nGeoPackage:"
    )

    print(
        caminho
    )


# ============================================================
# EXECUÇÃO
# ============================================================

def executar():

    print("\n")
    print("=" * 72)
    print("AVISOS INMET -> GEOPACKAGE V3")
    print("=" * 72)

    print(
        "Data local:",
        datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )
    )

    print(
        "Filtro:",
        FILTRO_DATA
    )

    # --------------------------------------------------------
    # IDs
    # --------------------------------------------------------

    if INMET_IDS:

        candidatos = [
            {
                "id": str(x),
                "msg_type": "Alert"
            }
            for x in INMET_IDS
        ]

        print(
            "\nIDs informados manualmente:",
            len(candidatos)
        )

    else:

        candidatos = (
            obter_ids_rss()
        )

        print(
            "\nCandidatos após filtro "
            "do RSS:",
            len(candidatos)
        )

    if not candidatos:

        print(
            "\nNenhum candidato encontrado."
        )

        return None

    # --------------------------------------------------------
    # Download paralelo
    # --------------------------------------------------------

    registros = []

    total = len(candidatos)

    print(
        f"\nConsultando {total} "
        "aviso(s) individualmente..."
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futuros = {}

        for item in candidatos:

            futuro = executor.submit(
                obter_aviso,
                item["id"],
                item.get(
                    "msg_type"
                )
            )

            futuros[futuro] = item["id"]

        concluidos = 0

        for futuro in as_completed(
            futuros
        ):

            aviso_id = futuros[
                futuro
            ]

            concluidos += 1

            try:

                dados = (
                    futuro.result()
                )

                registros.extend(
                    dados
                )

                if dados:
                    print(
                        f"[{concluidos}/{total}] "
                        f"{aviso_id}: "
                        f"{len(dados)} polígono(s)"
                    )

            except Exception as exc:

                print(
                    f"[{concluidos}/{total}] "
                    f"{aviso_id}: ERRO - "
                    f"{exc}"
                )

    # --------------------------------------------------------
    # Segurança: somente Alert
    # --------------------------------------------------------

    registros = [
        r
        for r in registros
        if str(
            r.get(
                "msg_type",
                ""
            )
        ).lower()
        == "alert"
    ]

    if not registros:

        print(
            "\nNenhum alerta válido "
            "após os filtros."
        )

        return None

    # --------------------------------------------------------
    # Camada
    # --------------------------------------------------------

    layer = (
        criar_camada_memoria(
            registros
        )
    )

    # A simbologia das camadas do projeto é aplicada
    # individualmente em adicionar_camadas_ordenadas().

    configurar_maptip(
        layer
    )

    # --------------------------------------------------------
    # GPKG
    # --------------------------------------------------------

    salvar_geopackage(
        layer,
        OUTPUT_GPKG
    )

    # --------------------------------------------------------
    # QGIS
    # --------------------------------------------------------

    if ADD_TO_PROJECT:

        adicionar_camadas_ordenadas(
            OUTPUT_GPKG
        )

        print(
            "\nGrupo 'Avisos INMET' adicionado ao projeto."
        )

    # --------------------------------------------------------
    # Resumo
    # --------------------------------------------------------

    alert_ids = sorted(
        set(
            r["alert_id"]
            for r in registros
        )
    )

    severidades = {}

    for r in registros:

        nivel = r.get(
            "nivel_inmet",
            "Não informado"
        )

        severidades[nivel] = (
            severidades.get(
                nivel,
                0
            ) + 1
        )

    print("\n")
    print("=" * 72)
    print("CONCLUÍDO")
    print("=" * 72)

    print(
        "Alertas:",
        len(alert_ids)
    )

    print(
        "Polígonos:",
        len(registros)
    )

    print(
        "Classificação:"
    )

    for nivel, quantidade in sorted(
        severidades.items()
    ):

        print(
            f"  {nivel}: {quantidade}"
        )

    print(
        "GeoPackage:",
        OUTPUT_GPKG
    )

    print("=" * 72)

    return layer


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    executar()
