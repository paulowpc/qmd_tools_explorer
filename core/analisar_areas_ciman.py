# -*- coding: utf-8 -*-

"""
Analisador de Áreas CIMAN.

Este módulo analisa a relação espacial entre um Evento de Fogo e as
áreas monitoradas pelo CIMAN.

Fluxo:
    1. Carrega as camadas CIMAN configuradas.
    2. Verifica se o evento intersecta alguma área monitorada.
    3. Se intersectar:
         - Status: "Dentro de área monitorada"
         - Nome da área: área intersectada
         - Área CIMAN próxima: "-"
    4. Se não intersectar:
         - Cria um buffer métrico de 2 km.
         - Procura áreas CIMAN dentro desse raio.
    5. Se encontrar área próxima:
         - Nome da área: município do evento
         - Tipo da área: Município
         - Status: "Próximo a área monitorada"
         - Área CIMAN próxima: nome da(s) área(s)
    6. Se não encontrar:
         - Nome da área: município do evento
         - Tipo da área: Município
         - Status: "Sem área CIMAN próxima"
         - Área CIMAN próxima: "-"
"""

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsMessageLog,
    Qgis,
)

from ..core.stac_core import (
    log_message,
)


class AnalisadorAreasCIMAN:
    """
    Analisa a relação espacial entre um Evento de Fogo e as áreas
    monitoradas pelo CIMAN.
    """

    # =========================================================
    # CONFIGURAÇÃO
    # =========================================================

    RAIO_PADRAO_METROS = 2000

    # =========================================================
    # CAMPOS POSSÍVEIS PARA O NOME DA ÁREA
    # =========================================================

    CAMPOS_NOME_AREA = (
        "nome",
        "nome_area",
        "nome_uc",
        "nome_ucs",
        "nm_uc",
        "nome_terra",
        "terra_indigena",
        "nome_ti",
        "nm_ti",
        "nome_assentamento",
        "nome_pa",
        "nome_quilombo",
        "nome_comunidade",
        "regioes",
        "regiao",
        "name",
        "descricao",
        "denominacao",
    )

    # =========================================================
    # CAMPOS POSSÍVEIS PARA O MUNICÍPIO
    # =========================================================

    CAMPOS_MUNICIPIO = (
        "municipios",
        "municipio",
        "nome_municipio",
        "município",
    )

    # =========================================================
    # CONSTRUTOR
    # =========================================================

    def __init__(
        self,
        evento_feature,
        camadas_ciman,
        raio_metros=None,
        iface=None,
    ):

        self.evento_feature = QgsFeature(
            evento_feature
        )

        self.camadas_ciman = (
            camadas_ciman or []
        )

        self.raio_metros = (
            raio_metros
            if raio_metros is not None
            else self.RAIO_PADRAO_METROS
        )

        self.iface = iface

        self.evento_geom = (
            self.evento_feature.geometry()
        )

        self.camadas_carregadas = []

        self._validar_evento()

    # =========================================================
    # LOG
    # =========================================================

    def _log(
        self,
        mensagem,
        nivel=Qgis.Info,
    ):

        texto = (
            f"[ANALISAR ÁREAS CIMAN] {mensagem}"
        )

        try:

            log_message(
                texto
            )

        except Exception:

            pass

        QgsMessageLog.logMessage(
            texto,
            "QMD Image Explorer",
            nivel,
        )

    # =========================================================
    # DESCREVER OBJETO
    # =========================================================

    def _descrever_objeto(
        self,
        nome,
        valor,
    ):

        try:

            texto = str(
                valor
            )

        except Exception as erro:

            texto = (
                f"<erro ao converter para texto: {erro}>"
            )

        self._log(
            f"{nome}: "
            f"tipo={type(valor).__name__} | "
            f"valor={texto}"
        )

    # =========================================================
    # VALIDAR EVENTO
    # =========================================================

    def _validar_evento(
        self,
    ):

        if (
            self.evento_feature is None
            or not self.evento_feature.isValid()
        ):

            raise RuntimeError(
                "Evento selecionado inválido."
            )

        if (
            self.evento_geom is None
            or self.evento_geom.isNull()
            or self.evento_geom.isEmpty()
        ):

            raise RuntimeError(
                "O evento selecionado não possui "
                "geometria válida."
            )

    # =========================================================
    # ENCONTRAR CAMPO
    # =========================================================

    def _encontrar_campo(
        self,
        feature,
        candidatos,
    ):

        if feature is None:

            return None

        campos = {
            field.name().lower(): field.name()
            for field in feature.fields()
        }

        for candidato in candidatos:

            candidato_lower = (
                candidato.lower()
            )

            if candidato_lower in campos:

                return campos[
                    candidato_lower
                ]

        return None

    # =========================================================
    # OBTER VALOR DE CAMPO
    # =========================================================

    def _obter_valor(
        self,
        feature,
        candidatos,
    ):

        campo = self._encontrar_campo(
            feature,
            candidatos,
        )

        if campo is None:

            return None

        valor = feature[
            campo
        ]

        if valor is None:

            return None

        texto = str(
            valor
        ).strip()

        if not texto:

            return None

        return texto

    # =========================================================
    # OBTER NOME DA ÁREA
    # =========================================================

    def _obter_nome_area(
        self,
        feature,
    ):

        nome = self._obter_valor(
            feature,
            self.CAMPOS_NOME_AREA,
        )

        if nome:

            return nome

        for field in feature.fields():

            nome_campo = (
                field.name().lower()
            )

            if (
                "nome" in nome_campo
                or "name" in nome_campo
            ):

                valor = feature[
                    field.name()
                ]

                if valor not in (
                    None,
                    "",
                ):

                    return str(
                        valor
                    ).strip()

        return (
            "Área CIMAN sem nome identificado"
        )

    # =========================================================
    # OBTER MUNICÍPIO DO EVENTO
    # =========================================================

    def _obter_municipio_evento(
        self,
    ):

        municipio = self._obter_valor(
            self.evento_feature,
            self.CAMPOS_MUNICIPIO,
        )

        if municipio:

            return municipio

        return (
            "Município não informado"
        )

    # =========================================================
    # OBTER CRS DO EVENTO
    # =========================================================

    def _obter_crs_evento(
        self,
    ):

        """
        Retorna o CRS conhecido dos Eventos Ativos utilizados
        nesta análise.

        Todas as camadas envolvidas nesta integração estão em
        EPSG:4326, portanto este é o CRS de entrada do evento.
        """

        crs = QgsCoordinateReferenceSystem(
            "EPSG:4326"
        )

        if not crs.isValid():

            raise RuntimeError(
                "Não foi possível criar o CRS padrão "
                "EPSG:4326 para o evento."
            )

        return crs

    # =========================================================
    # NORMALIZAR CRS DO EVENTO
    # =========================================================

    def _normalizar_crs_evento(
        self,
        crs_evento,
    ):

        if crs_evento is None:

            crs_evento = (
                self._obter_crs_evento()
            )

        elif isinstance(
            crs_evento,
            str,
        ):

            crs_evento = (
                QgsCoordinateReferenceSystem(
                    crs_evento
                )
            )

        if not isinstance(
            crs_evento,
            QgsCoordinateReferenceSystem,
        ):

            raise RuntimeError(
                "CRS do evento inválido.\n\n"
                f"Tipo recebido: "
                f"{type(crs_evento).__name__}\n"
                f"Valor: {crs_evento}"
            )

        if not crs_evento.isValid():

            raise RuntimeError(
                "CRS do evento inválido.\n\n"
                f"CRS: {crs_evento}"
            )

        return crs_evento

    # =========================================================
    # CARREGAR CAMADAS CIMAN
    # =========================================================

    def carregar_camadas(
        self,
    ):

        self.camadas_carregadas = []

        for config in self.camadas_ciman:

            if not isinstance(
                config,
                dict,
            ):

                continue

            caminho = config.get(
                "path"
            )

            if not caminho:

                self._log(
                    "Camada sem caminho configurado.",
                    Qgis.Warning,
                )

                continue

            nome = config.get(
                "name",
                "Área CIMAN",
            )

            tipo = config.get(
                "tipo",
                nome,
            )

            chave = config.get(
                "key",
                nome,
            )

            self._log(
                f"Carregando camada: {nome}"
            )

            layer = QgsVectorLayer(
                str(caminho),
                nome,
                "ogr",
            )

            if not layer.isValid():

                self._log(
                    f"Camada inválida: {nome}",
                    Qgis.Warning,
                )

                continue

            quantidade = (
                layer.featureCount()
            )

            self._log(
                f"Camada carregada: {nome} "
                f"({quantidade} feições)"
            )

            if quantidade == 0:

                continue

            indice = QgsSpatialIndex(
                layer.getFeatures()
            )

            self.camadas_carregadas.append(
                {
                    "key": chave,
                    "name": nome,
                    "tipo": tipo,
                    "layer": layer,
                    "index": indice,
                }
            )

        if not self.camadas_carregadas:

            raise RuntimeError(
                "Nenhuma camada CIMAN válida foi carregada."
            )

        return self.camadas_carregadas

    # =========================================================
    # TRANSFORMAR GEOMETRIA
    # =========================================================

    def _transformar_geometria(
        self,
        geometria,
        crs_origem,
        crs_destino,
    ):

        if geometria is None:

            raise RuntimeError(
                "Geometria não informada para transformação."
            )

        if not isinstance(
            crs_origem,
            QgsCoordinateReferenceSystem,
        ):

            raise RuntimeError(
                "CRS de origem inválido na transformação.\n\n"
                f"Tipo recebido: "
                f"{type(crs_origem).__name__}\n"
                f"Valor: {crs_origem}"
            )

        if not crs_origem.isValid():

            raise RuntimeError(
                "CRS de origem inválido na transformação."
            )

        if not isinstance(
            crs_destino,
            QgsCoordinateReferenceSystem,
        ):

            raise RuntimeError(
                "CRS de destino inválido na transformação.\n\n"
                f"Tipo recebido: "
                f"{type(crs_destino).__name__}\n"
                f"Valor: {crs_destino}"
            )

        if not crs_destino.isValid():

            raise RuntimeError(
                "CRS de destino inválido na transformação."
            )

        geom = QgsGeometry(
            geometria
        )

        if (
            geom.isNull()
            or geom.isEmpty()
        ):

            raise RuntimeError(
                "Geometria inválida para transformação."
            )

        if (
            crs_origem.authid()
            == crs_destino.authid()
        ):

            return geom

        transform = QgsCoordinateTransform(
            crs_origem,
            crs_destino,
            QgsProject.instance(),
        )

        resultado = geom.transform(
            transform
        )

        if resultado != 0:

            raise RuntimeError(
                "Não foi possível transformar a geometria."
            )

        return geom

    # =========================================================
    # OBTER CRS MÉTRICO PARA BUFFER
    # =========================================================

    def _obter_crs_metrico(
        self,
        geometria,
        crs_origem,
    ):

        crs_geografico = (
            QgsCoordinateReferenceSystem(
                "EPSG:4326"
            )
        )

        geom_wgs84 = (
            self._transformar_geometria(
                geometria,
                crs_origem,
                crs_geografico,
            )
        )

        centroide = (
            geom_wgs84.centroid()
        )

        if (
            centroide.isNull()
            or centroide.isEmpty()
        ):

            raise RuntimeError(
                "Não foi possível calcular o centroide "
                "do evento."
            )

        ponto = (
            centroide.asPoint()
        )

        longitude = ponto.x()
        latitude = ponto.y()

        zona = int(
            (longitude + 180) / 6
        ) + 1

        if latitude >= 0:

            epsg = (
                32600 + zona
            )

        else:

            epsg = (
                32700 + zona
            )

        crs_metrico = (
            QgsCoordinateReferenceSystem(
                f"EPSG:{epsg}"
            )
        )

        if not crs_metrico.isValid():

            raise RuntimeError(
                "Não foi possível criar o CRS métrico "
                f"EPSG:{epsg}."
            )

        return crs_metrico

    # =========================================================
    # GEOMETRIA DO EVENTO NO CRS DA CAMADA
    # =========================================================

    def _geometria_evento_na_camada(
        self,
        crs_destino,
        crs_evento,
    ):

        return self._transformar_geometria(
            self.evento_geom,
            crs_evento,
            crs_destino,
        )

    # =========================================================
    # ANÁLISE DE INTERSEÇÕES DIRETAS
    # =========================================================

    def _analisar_intersecoes(
        self,
        crs_evento,
    ):

        resultados = []

        self._log(
            "Verificando interseções diretas..."
        )

        for dados_camada in (
            self.camadas_carregadas
        ):

            layer = (
                dados_camada["layer"]
            )

            indice = (
                dados_camada["index"]
            )

            crs_camada = (
                layer.crs()
            )

            if not crs_camada.isValid():

                self._log(
                    f"CRS inválido na camada: "
                    f"{dados_camada['name']}",
                    Qgis.Warning,
                )

                continue

            geom_evento = (
                self._geometria_evento_na_camada(
                    crs_camada,
                    crs_evento,
                )
            )

            candidatos = (
                indice.intersects(
                    geom_evento.boundingBox()
                )
            )

            for fid in candidatos:

                feature_area = (
                    layer.getFeature(
                        fid
                    )
                )

                if (
                    feature_area is None
                    or not feature_area.isValid()
                ):

                    continue

                geom_area = (
                    feature_area.geometry()
                )

                if (
                    geom_area is None
                    or geom_area.isNull()
                    or geom_area.isEmpty()
                ):

                    continue

                if not geom_evento.intersects(
                    geom_area
                ):

                    continue

                nome_area = (
                    self._obter_nome_area(
                        feature_area
                    )
                )

                resultados.append(
                    {
                        "nome_area": nome_area,
                        "tipo_area": dados_camada[
                            "tipo"
                        ],
                        "status_proximidade":
                            "Dentro de área monitorada",
                        "area_ciman_proxima": "-",
                        "distancia_m": 0.0,
                        "camada_key": dados_camada[
                            "key"
                        ],
                        "camada_nome": dados_camada[
                            "name"
                        ],
                        "feature": QgsFeature(
                            feature_area
                        ),
                    }
                )

                self._log(
                    f"Interseção encontrada: "
                    f"{nome_area}"
                )

        return resultados

    # =========================================================
    # ANÁLISE DE PROXIMIDADE
    # =========================================================

    def _analisar_proximidade(
        self,
        crs_evento,
    ):

        self._log(
            f"Verificando proximidade em "
            f"{self.raio_metros} metros..."
        )

        municipio = (
            self._obter_municipio_evento()
        )

        crs_metrico = (
            self._obter_crs_metrico(
                self.evento_geom,
                crs_evento,
            )
        )

        geom_evento_metrico = (
            self._transformar_geometria(
                self.evento_geom,
                crs_evento,
                crs_metrico,
            )
        )

        buffer_evento = (
            geom_evento_metrico.buffer(
                self.raio_metros,
                24,
            )
        )

        areas_proximas = []

        for dados_camada in (
            self.camadas_carregadas
        ):

            layer = (
                dados_camada["layer"]
            )

            indice = (
                dados_camada["index"]
            )

            crs_camada = (
                layer.crs()
            )

            if not crs_camada.isValid():

                continue

            geom_buffer_camada = (
                self._transformar_geometria(
                    buffer_evento,
                    crs_metrico,
                    crs_camada,
                )
            )

            candidatos = (
                indice.intersects(
                    geom_buffer_camada.boundingBox()
                )
            )

            for fid in candidatos:

                feature_area = (
                    layer.getFeature(
                        fid
                    )
                )

                if (
                    feature_area is None
                    or not feature_area.isValid()
                ):

                    continue

                geom_area = (
                    feature_area.geometry()
                )

                if (
                    geom_area is None
                    or geom_area.isNull()
                    or geom_area.isEmpty()
                ):

                    continue

                if not geom_buffer_camada.intersects(
                    geom_area
                ):

                    continue

                geom_area_metrica = (
                    self._transformar_geometria(
                        geom_area,
                        crs_camada,
                        crs_metrico,
                    )
                )

                distancia = (
                    geom_evento_metrico.distance(
                        geom_area_metrica
                    )
                )

                if distancia > self.raio_metros:

                    continue

                nome_area = (
                    self._obter_nome_area(
                        feature_area
                    )
                )

                areas_proximas.append(
                    {
                        "nome_area": nome_area,
                        "tipo_area": dados_camada[
                            "tipo"
                        ],
                        "distancia_m": distancia,
                        "camada_key": dados_camada[
                            "key"
                        ],
                        "camada_nome": dados_camada[
                            "name"
                        ],
                        "feature": QgsFeature(
                            feature_area
                        ),
                    }
                )

                self._log(
                    f"Área próxima encontrada: "
                    f"{nome_area} "
                    f"({distancia:.0f} m)"
                )

        # -----------------------------------------------------
        # REMOVER DUPLICADOS
        # -----------------------------------------------------

        areas_unicas = {}

        for area in areas_proximas:

            chave = (
                area["camada_key"],
                area["nome_area"],
            )

            if chave not in areas_unicas:

                areas_unicas[chave] = area

                continue

            if (
                area["distancia_m"]
                < areas_unicas[chave][
                    "distancia_m"
                ]
            ):

                areas_unicas[chave] = area

        areas_proximas = list(
            areas_unicas.values()
        )

        areas_proximas.sort(
            key=lambda item: item[
                "distancia_m"
            ]
        )

        # -----------------------------------------------------
        # SEM ÁREA PRÓXIMA
        # -----------------------------------------------------

        if not areas_proximas:

            return {
                "nome_area": municipio,
                "tipo_area": "Município",
                "status_proximidade":
                    "Sem área CIMAN próxima",
                "area_ciman_proxima": "-",
                "areas_proximas": [],
                "buffer": buffer_evento,
            }

        # -----------------------------------------------------
        # ÁREAS PRÓXIMAS ENCONTRADAS
        # -----------------------------------------------------

        nomes_areas = [
            area["nome_area"]
            for area in areas_proximas
        ]

        area_ciman_proxima = (
            " | ".join(
                nomes_areas
            )
        )

        return {
            "nome_area": municipio,
            "tipo_area": "Município",
            "status_proximidade":
                "Próximo a área monitorada",
            "area_ciman_proxima":
                area_ciman_proxima,
            "areas_proximas":
                areas_proximas,
            "buffer": buffer_evento,
        }

    # =========================================================
    # EXECUTAR ANÁLISE
    # =========================================================

    def analisar(
        self,
    ):

        self._log(
            "=" * 60
        )

        self._log(
            "INICIANDO ANÁLISE DE ÁREAS CIMAN"
        )

        self._log(
            "=" * 60
        )

        # -----------------------------------------------------
        # CRS DO EVENTO
        # -----------------------------------------------------
        #
        # O QgsFeature não armazena o CRS. Nesta integração,
        # todas as camadas e o evento estão em EPSG:4326.
        #
        # Por isso o CRS é definido internamente e nenhum
        # parâmetro externo é aceito aqui. Isso evita que objetos
        # como QgsRectangle (boundingBox) sejam recebidos por
        # engano como se fossem um CRS.

        crs_evento = (
            self._obter_crs_evento()
        )

        self._log(
            f"CRS do evento: "
            f"{crs_evento.authid()}"
        )

        # -----------------------------------------------------
        # CARREGAR CAMADAS
        # -----------------------------------------------------

        if not self.camadas_carregadas:

            self.carregar_camadas()

        # -----------------------------------------------------
        # INTERSEÇÃO DIRETA
        # -----------------------------------------------------

        areas_diretas = (
            self._analisar_intersecoes(
                crs_evento
            )
        )

        if areas_diretas:

            self._log(
                f"Resultado: "
                f"{len(areas_diretas)} "
                f"área(s) intersectada(s)."
            )

            self._log(
                "=" * 60
            )

            return {
                "status":
                    "Dentro de área monitorada",
                "tem_intersecao":
                    True,
                "tem_proximidade":
                    False,
                "raio_metros":
                    self.raio_metros,
                "linhas":
                    areas_diretas,
                "areas_diretas":
                    areas_diretas,
                "areas_proximas":
                    [],
                "buffer":
                    None,
            }

        # -----------------------------------------------------
        # NÃO INTERSECTA
        # VERIFICAR PROXIMIDADE
        # -----------------------------------------------------

        resultado_proximidade = (
            self._analisar_proximidade(
                crs_evento
            )
        )

        status = (
            resultado_proximidade[
                "status_proximidade"
            ]
        )

        self._log(
            f"Resultado: {status}"
        )

        self._log(
            "=" * 60
        )

        return {
            "status": status,
            "tem_intersecao": False,
            "tem_proximidade": bool(
                resultado_proximidade[
                    "areas_proximas"
                ]
            ),
            "raio_metros":
                self.raio_metros,
            "linhas": [
                {
                    "nome_area":
                        resultado_proximidade[
                            "nome_area"
                        ],
                    "tipo_area":
                        resultado_proximidade[
                            "tipo_area"
                        ],
                    "status_proximidade":
                        resultado_proximidade[
                            "status_proximidade"
                        ],
                    "area_ciman_proxima":
                        resultado_proximidade[
                            "area_ciman_proxima"
                        ],
                }
            ],
            "areas_diretas": [],
            "areas_proximas":
                resultado_proximidade[
                    "areas_proximas"
                ],
            "buffer":
                resultado_proximidade[
                    "buffer"
                ],
        }
