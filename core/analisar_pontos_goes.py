from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsSpatialIndex,
    QgsFeature,
    QgsField,
    QgsWkbTypes
)

from qgis.PyQt.QtCore import QVariant


class AnalisadorPontosAtencaoGOES:
    """
    Analisa pontos de atenção GOES e identifica eventos ativos
    intersectados pelos pontos das classes prioritárias.

    O módulo recebe caminhos LOCAIS para os arquivos.

    Classes prioritárias:
        - 72 até 143 repetições
        - 144 até 288 repetições
    """

    CLASSES_PRIORITARIAS = (
        "72 até 143 repetições",
        "144 até 288 repetições",
    )

    CAMPOS_ID_EVENTO = (
        "id_evento",
        "evento_id",
        "cod_evento",
        "evento",
        "id",
    )

    def __init__(
        self,
        goes_path,
        eventos_path,
        iface=None
    ):

        self.goes_path = goes_path
        self.eventos_path = eventos_path
        self.iface = iface

        self.goes_layers = []
        self.eventos_layer = None

    # =========================================================
    # LOG
    # =========================================================

    def _log(self, mensagem):

        print(
            f"[ANALISAR GOES] {mensagem}"
        )

    # =========================================================
    # CARREGAR CAMADAS GOES
    # =========================================================

    def carregar_goes(self):

        self.goes_layers = []

        self._log(
            f"Arquivo GOES: {self.goes_path}"
        )

        for classe in self.CLASSES_PRIORITARIAS:

            uri = (
                f"{self.goes_path}"
                f"|layername={classe}"
            )

            layer = QgsVectorLayer(
                uri,
                classe,
                "ogr"
            )

            if not layer.isValid():

                self._log(
                    f"Classe não encontrada: {classe}"
                )

                continue

            quantidade = layer.featureCount()

            self._log(
                f"Classe encontrada: {classe} "
                f"({quantidade} pontos)"
            )

            if quantidade > 0:

                self.goes_layers.append(
                    layer
                )

        if not self.goes_layers:

            raise RuntimeError(
                "Nenhuma camada GOES prioritária "
                "foi encontrada no KML."
            )

        return self.goes_layers

    # =========================================================
    # CARREGAR EVENTOS
    # =========================================================

    def carregar_eventos(self):

        self._log(
            f"Arquivo eventos: {self.eventos_path}"
        )

        layer = QgsVectorLayer(
            self.eventos_path,
            "Eventos ativos",
            "ogr"
        )

        if not layer.isValid():

            raise RuntimeError(
                "Não foi possível carregar "
                "o arquivo de eventos ativos."
            )

        self.eventos_layer = layer

        self._log(
            f"Eventos carregados: "
            f"{layer.featureCount()}"
        )

        return layer

    # =========================================================
    # IDENTIFICAR ID DO EVENTO
    # =========================================================

    def _obter_id_evento(self, feature):

        nomes_campos = [
            field.name().lower()
            for field in feature.fields()
        ]

        for campo_preferido in self.CAMPOS_ID_EVENTO:

            if campo_preferido.lower() in nomes_campos:

                indice = nomes_campos.index(
                    campo_preferido.lower()
                )

                campo_real = (
                    feature.fields()
                    .at(indice)
                    .name()
                )

                valor = feature[campo_real]

                if valor not in (
                    None,
                    ""
                ):
                    return valor

        return feature.id()

    

    # =========================================================
    # ANALISAR
    # =========================================================

    def analisar(self):

        if not self.goes_layers:

            self.carregar_goes()

        if self.eventos_layer is None:

            self.carregar_eventos()

        self._log(
            "Criando índice espacial dos eventos..."
        )

        indice_eventos = QgsSpatialIndex(
            self.eventos_layer.getFeatures()
        )

        resultados = {}

        total_pontos = 0
        pontos_com_evento = 0

        for goes_layer in self.goes_layers:

            classe = goes_layer.name()

            self._log(
                f"Analisando classe: {classe}"
            )

            for ponto in goes_layer.getFeatures():

                total_pontos += 1

                geom_ponto = ponto.geometry()

                if (
                    geom_ponto is None
                    or geom_ponto.isEmpty()
                ):
                    continue

                candidatos = (
                    indice_eventos.intersects(
                        geom_ponto.boundingBox()
                    )
                )

                encontrou_evento = False

                for fid_evento in candidatos:

                    evento = (
                        self.eventos_layer
                        .getFeature(fid_evento)
                    )

                    geom_evento = evento.geometry()

                    if (
                        geom_evento is None
                        or geom_evento.isEmpty()
                    ):
                        continue

                    if not geom_evento.intersects(
                        geom_ponto
                    ):
                        continue

                    encontrou_evento = True

                    id_evento = (
                        self._obter_id_evento(evento)
                    )

                    if id_evento not in resultados:

                        resultados[id_evento] = {
                            "feature": QgsFeature(evento),
                            "pontos": [],
                            # "classes": set(),
                            "pontos_classes": [],
                            "classes": set(),
                        }

                    resultados[id_evento]["pontos"].append(
                        QgsFeature(ponto)
                    )

                    resultados[id_evento]["pontos_classes"].append(
                        classe
                    )

                    resultados[id_evento]["classes"].add(
                        classe
                    )

                if encontrou_evento:

                    pontos_com_evento += 1

        self._log("=" * 50)

        self._log(
            f"Total de pontos analisados: "
            f"{total_pontos}"
        )

        self._log(
            f"Pontos com evento associado: "
            f"{pontos_com_evento}"
        )

        self._log(
            f"Eventos únicos encontrados: "
            f"{len(resultados)}"
        )

        self._log("=" * 50)

        # =========================================================
        # DEFINIR CLASSE VISUAL DOS EVENTOS
        # =========================================================

        for id_evento, dados in resultados.items():

            dados["classe_visual"] = (
                self._obter_classe_visual_evento(
                    dados["classes"]
                )
            )

        return resultados

    # =========================================================
    # OBTER CLASSE VISUAL DO EVENTO
    # =========================================================

    def _obter_classe_visual_evento(
        self,
        classes
    ):

        classes_texto = {
            str(classe).lower().strip()
            for classe in classes
        }

        # -----------------------------------------------------
        # PRIORIDADE MÁXIMA: 144 até 288
        # -----------------------------------------------------

        if any(
            "144" in classe
            and "288" in classe
            for classe in classes_texto
        ):

            return "vermelho"

        # -----------------------------------------------------
        # SEGUNDA CLASSE: 72 até 143
        # -----------------------------------------------------

        if any(
            "72" in classe
            and "143" in classe
            for classe in classes_texto
        ):

            return "laranja"

        # -----------------------------------------------------
        # SEM CLASSIFICAÇÃO
        # -----------------------------------------------------

        return None

    # =========================================================
    # CAMADA RESULTADO
    # =========================================================

    def criar_camada_resultado(
        self,
        resultados,
        adicionar_ao_projeto=True
    ):

        if self.eventos_layer is None:

            raise RuntimeError(
                "A camada de eventos "
                "não foi carregada."
            )

        geometry_type = (
            QgsWkbTypes.displayString(
                self.eventos_layer.wkbType()
            )
        )

        uri = (
            f"{geometry_type}?"
            f"crs="
            f"{self.eventos_layer.crs().authid()}"
        )

        camada_saida = QgsVectorLayer(
            uri,
            "EVENTOS COM PONTOS DE ATENÇÃO GOES",
            "memory"
        )

        provider = (
            camada_saida.dataProvider()
        )

        # Copia campos originais
        provider.addAttributes(
            self.eventos_layer.fields()
        )

        # # Campos calculados
        # provider.addAttributes([
        #     QgsField(
        #         "goes_qtd",
        #         QVariant.Int
        #     ),
        #     QgsField(
        #         "goes_classes",
        #         QVariant.String
        #     ),
        # ])

        provider.addAttributes([
            QgsField(
                "goes_qtd",
                QVariant.Int
            ),
            QgsField(
                "goes_classes",
                QVariant.String
            ),
            QgsField(
                "classe_visual",
                QVariant.String
            ),
        ])

        camada_saida.updateFields()

        features_saida = []

        for _, dados in resultados.items():

            evento_original = dados["feature"]

            nova_feature = QgsFeature(
                camada_saida.fields()
            )

            nova_feature.setGeometry(
                evento_original.geometry()
            )

            # Copiar atributos originais
            for field in (
                self.eventos_layer.fields()
            ):

                nova_feature[
                    field.name()
                ] = evento_original[
                    field.name()
                ]

            # Campos GOES
            nova_feature[
                "goes_qtd"
            ] = len(dados["pontos"])

            nova_feature[
                "goes_classes"
            ] = " | ".join(
                sorted(dados["classes"])
            )

            nova_feature["classe_visual"] = (
                self._obter_classe_visual_evento(
                    dados["classes"]
                )
            )

            features_saida.append(
                nova_feature
            )

        provider.addFeatures(
            features_saida
        )

        camada_saida.updateExtents()

        if adicionar_ao_projeto:

            QgsProject.instance().addMapLayer(
                camada_saida
            )

        self._log(
            "Camada de resultado criada: "
            f"{camada_saida.featureCount()} eventos"
        )

        return camada_saida

    # =========================================================
    # EXECUTAR
    # =========================================================

    def executar(
        self,
        adicionar_ao_projeto=True
    ):

        self._log(
            "Iniciando análise dos Pontos de Atenção GOES"
        )

        self.carregar_goes()

        self.carregar_eventos()

        resultados = self.analisar()

        camada_resultado = (
            self.criar_camada_resultado(
                resultados,
                adicionar_ao_projeto
            )
        )

        return {
            "resultados": resultados,
            "camada": camada_resultado,
            "total_eventos": len(resultados),
            "total_pontos": sum(
                len(
                    dados["pontos"]
                )
                for dados in resultados.values()
            ),
        }