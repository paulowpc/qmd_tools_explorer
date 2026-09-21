# -*- coding: utf-8 -*-

from pathlib import Path
import json
import shutil
import urllib.request
import os

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsWkbTypes,
    QgsRectangle,
    QgsFields,
    QgsField,
)

from ..core.stac_core import (
    log_message,
)

from qgis.PyQt.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    QVariant,
)

from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QApplication,
    QProgressBar,
    QGroupBox,
    QFormLayout,
    QDialog,
    QSizePolicy,
)

from qgis.utils import iface

from ..core.analisar_pontos_goes import (
    AnalisadorPontosAtencaoGOES
)

from ..core.analisar_areas_ciman import (
    AnalisadorAreasCIMAN
)

from .resultado_areas_ciman_dialog import (
    ResultadoAreasCIMANDialog
)


# ==========================================================
# WORKER DE ANÁLISE
# ==========================================================

class AnaliseGoesWorker(QThread):

    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        goes_path,
        eventos_path,
        parent=None
    ):

        super().__init__(parent)

        self.goes_path = goes_path
        self.eventos_path = eventos_path

    def run(self):

        try:

            analisador = AnalisadorPontosAtencaoGOES(
                goes_path=str(self.goes_path),
                eventos_path=str(self.eventos_path),
                iface=iface,
            )

            resultado = analisador.executar(
                adicionar_ao_projeto=False
            )

            self.finished_ok.emit(
                resultado
            )

        except Exception as error:

            self.failed.emit(
                str(error)
            )


# ==========================================================
# WIDGET PRINCIPAL
# ==========================================================

class AnalisarPontosGoesDialog(QWidget):

    """
    Aba responsável pela análise dos Pontos de Atenção GOES.

    Fluxo:

        Pontos GOES
             +
        Eventos Ativos
             ↓
        Cruzamento espacial
             ↓
        Eventos associados
             ↓
        Seleção do evento
             ↓
        Informações completas do evento
             ↓
        Analisar Áreas CIMAN
             +
        Buscar imagens
    """

    def __init__(
        self,
        parent=None
    ):

        super().__init__(parent)

        self.resultado = None
        self.worker = None
        self.evento_selecionado = None
        self.goes_path = None
        self.eventos_path = None

        self._build_ui()

    # ======================================================
    # INTERFACE
    # ======================================================

    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        layout.setSpacing(4)
       
        # --------------------------------------------------
        # TÍTULO
        # --------------------------------------------------

        title = QLabel(
            "ANALISAR PONTOS DE ATENÇÃO GOES (48h)"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setFixedHeight(
            28
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            """
        )

        layout.addWidget(
            title
        )

        # --------------------------------------------------
        # CLASSES ANALISADAS
        # --------------------------------------------------

        classes_label = QLabel(
            "Classes: 72–144 | 144–288 repetições"
        )

        classes_label.setAlignment(
            Qt.AlignCenter
        )

        classes_label.setFixedHeight(
            22
        )

        classes_label.setStyleSheet(
            """
            QLabel {
                color: #555555;
                padding: 0px;
            }
            """
        )

        layout.addWidget(
            classes_label
        )

        # --------------------------------------------------
        # BOTÃO ANALISAR
        # --------------------------------------------------

        self.analisar_btn = QPushButton(
            "🔥 Analisar Pontos de Atenção GOES"
        )

        self.analisar_btn.setFixedHeight(
            34
        )

        self.analisar_btn.clicked.connect(
            self.analisar_pontos_goes
        )

        layout.addWidget(
            self.analisar_btn
        )

        # --------------------------------------------------
        # PROGRESSO
        # --------------------------------------------------

        self.progress = QProgressBar()

        self.progress.setVisible(
            False
        )

        self.progress.setTextVisible(
            False
        )

        layout.addWidget(
            self.progress
        )

        # --------------------------------------------------
        # RESULTADO DA ANÁLISE
        # --------------------------------------------------

        self.summary_label = QLabel(
            "RESULTADO DA ANÁLISE\n"
            "Aguardando análise..."
        )

        self.summary_label.setWordWrap(
            True
        )

        self.summary_label.setFixedHeight(
            52
        )


        self.summary_label.setStyleSheet(
            """
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #d8d8d8;
                border-left: 3px solid #e67e22;
                padding: 7px 10px;
            }
            """
        )

        layout.addWidget(
            self.summary_label
        )

        # --------------------------------------------------
        # TÍTULO DA TABELA
        # --------------------------------------------------

        table_title = QLabel(
            "EVENTOS ASSOCIADOS"
        )

        table_title.setFixedHeight(
            22
        )

        table_title.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
                padding-top: 4px;
            }
            """
        )

        layout.addWidget(
            table_title
        )

        layout.setSpacing(
            4
        )

        # --------------------------------------------------
        # TABELA
        # --------------------------------------------------

        self.table = QTableWidget()

        self.table.setColumnCount(
            10
        )

        self.table.setHorizontalHeaderLabels([
            "Selecionar",
            "Status",
            "Evento",
            "Região / Área",
            "Município",
            "UF",
            "Frentes",
            "Pontos GOES",
            "Classes",
            "Info",
        ])

        # --------------------------------------------------
        # ALTERAÇÃO DO CHECKBOX
        # --------------------------------------------------

        self.table.itemChanged.connect(
            self._ao_checkbox_alterado
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.itemChanged.connect(
            self._atualizar_botoes_selecao
        )

        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setWordWrap(
            False
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            QHeaderView.Interactive
        )

        header.setStretchLastSection(
            True
        )
        
        self.table.setColumnWidth(0, 75)   # Selecionar
        self.table.setColumnWidth(1, 55)   # Status
        self.table.setColumnWidth(2, 80)   # Evento
        self.table.setColumnWidth(3, 180)  # Região / Área
        self.table.setColumnWidth(4, 130)  # Município
        self.table.setColumnWidth(5, 40)   # UF
        self.table.setColumnWidth(6, 60)   # Frentes
        self.table.setColumnWidth(7, 85)   # Pontos GOES
        self.table.setColumnWidth(8, 150)  # Classes
        self.table.setColumnWidth(9, 58)   # Info

    
        # --------------------------------------------------
        # ALTURA DA TABELA
        # --------------------------------------------------

        # Aproximadamente 7 linhas visíveis
        altura_linha = 24
        numero_linhas_visiveis = 5

        altura_cabecalho = 24

        altura_tabela = (
            altura_cabecalho
            + (altura_linha * numero_linhas_visiveis)
            + 10
        )

        self.table.setMinimumHeight(
            altura_tabela
        )

        self.table.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        layout.addWidget(
            self.table,
            1
        )

        # A seleção da linha continua sendo usada visualmente.
        # As informações completas são abertas pelo botão "Info".
        self.table.itemChanged.connect(
            self._atualizar_botao_adicionar_mapa
        )
        
        # ==================================================
        # INFORMAÇÕES DO EVENTO
        # ==================================================
        # Os detalhes são exibidos sob demanda pelo botão
        # "Info" presente em cada linha da tabela.

        # ==================================================
        # CONTROLES DE SELEÇÃO
        # ==================================================

        selecao_layout = QHBoxLayout()

        self.selecionar_tudo_btn = QPushButton(
            "Selecionar Tudo"
        )

        self.selecionar_tudo_btn.clicked.connect(
            self.selecionar_todos_eventos
        )

        self.limpar_selecao_btn = QPushButton(
            "Limpar Seleção"
        )

        self.limpar_selecao_btn.clicked.connect(
            self.limpar_selecao_eventos
        )

        selecao_layout.addWidget(
            self.selecionar_tudo_btn
        )

        selecao_layout.addWidget(
            self.limpar_selecao_btn
        )

        selecao_layout.addStretch()

        layout.addLayout(
            selecao_layout
        )

        # ==================================================
        # AÇÕES
        # ==================================================

        bottom_layout = QHBoxLayout()

        self.add_map_btn = QPushButton(
            "Adicionar ao Mapa"
        )

        self.add_map_btn.setEnabled(
            False
        )

        self.add_map_btn.clicked.connect(
            self.adicionar_eventos_selecionados_mapa
        )

        self.areas_ciman_btn = QPushButton(
            "Analisar Áreas CIMAN →"
        )

        self.areas_ciman_btn.setEnabled(
            False
        )

        self.areas_ciman_btn.clicked.connect(
            self.abrir_analise_areas_ciman
        )

        bottom_layout.addWidget(
            self.add_map_btn
        )

        bottom_layout.addWidget(
            self.areas_ciman_btn
        )

        layout.addLayout(
            bottom_layout
        )

    # ======================================================
    # CAMINHO DO PLUGIN
    # ======================================================

    def _plugin_dir(self):

        return (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

    # ======================================================
    # CONFIG
    # ======================================================

    def _config_path(self):

        return (
            self._plugin_dir()
            / "config"
            / "reference_layers.json"
        )

    # ======================================================
    # CACHE
    # ======================================================

    def _cache_dir(self):

        cache_dir = (
            self._plugin_dir()
            / "data"
            / "reference_layers_cache"
        )

        cache_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        return cache_dir

    # ======================================================
    # CARREGAR CONFIG
    # ======================================================

    def _load_config(self):

        config_path = self._config_path()

        with config_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    # ======================================================
    # OBTER ARQUIVO LOCAL
    # ======================================================

    def _get_local_file(
        self,
        layer_config
    ):

        cache_dir = self._cache_dir()

        local_path = (
            cache_dir
            / layer_config["filename"]
        )

        # --------------------------------------------------------------------------------
        # USA CACHE EXISTENTE Só para as camadas não estiverem com "force_download": true
        # --------------------------------------------------------------------------------

        # --------------------------------------------------
        # VERIFICAR SE DEVE FORÇAR NOVO DOWNLOAD
        # --------------------------------------------------

        force_download = layer_config.get(
            "force_download",
            False
        )

        # --------------------------------------------------
        # USA CACHE EXISTENTE
        # --------------------------------------------------

        if (
            local_path.exists()
            and not force_download
        ):

            return local_path

        # if local_path.exists():

        #     return local_path

        # --------------------------------------------------
        # DOWNLOAD
        # --------------------------------------------------

        temp_path = local_path.with_suffix(
            local_path.suffix + ".part"
        )

        request = urllib.request.Request(
            layer_config["url"],
            headers={
                "User-Agent":
                    "QMD Tools Explorer"
            }
        )

        try:

            QApplication.setOverrideCursor(
                Qt.WaitCursor
            )

            with urllib.request.urlopen(
                request,
                timeout=120
            ) as response:

                with temp_path.open(
                    "wb"
                ) as output:

                    shutil.copyfileobj(
                        response,
                        output
                    )

            temp_path.replace(
                local_path
            )

            return local_path

        except Exception:

            if temp_path.exists():

                try:
                    temp_path.unlink()

                except Exception:
                    pass

            raise

        finally:

            QApplication.restoreOverrideCursor()

        # ======================================================
   
    # ======================================================
    # OBTER CAMADAS CIMAN
    # ======================================================

    def _obter_camadas_ciman(self):

        config = self._load_config()

        grupo = config.get(
            "territorio_areas_protegidas",
            {}
        )

        camadas_ciman = []

        for chave, layer_config in grupo.items():

            if not layer_config.get(
                "enabled",
                True
            ):
                continue

            try:

                caminho_local = self._get_local_file(
                    layer_config
                )

                camada = {
                    "key": chave,

                    "name": layer_config.get(
                        "name",
                        chave
                    ),

                    "tipo": layer_config.get(
                        "tipo_area",
                        layer_config.get(
                            "name",
                            chave
                        )
                    ),

                    "path": str(
                        caminho_local
                    ),
                }

                camadas_ciman.append(
                    camada
                )

            except Exception as e:

                print(
                    f"[ÁREAS CIMAN] "
                    f"Erro ao preparar camada "
                    f"{chave}: {e}"
                )

        if not camadas_ciman:

            raise RuntimeError(
                "Nenhuma camada CIMAN pôde ser preparada."
            )

        return camadas_ciman

    # ======================================================
    # MOSTRAR RESULTADO ÁREAS CIMAN
    # ======================================================

    # def _mostrar_resultado_areas_ciman(
    #     self,
    #     resultado_ciman,
    # ):

    #     try:

    #         # --------------------------------------------------
    #         # VALIDAR RESULTADO
    #         # --------------------------------------------------

    #         if resultado_ciman is None:

    #             raise RuntimeError(
    #                 "A análise CIMAN não retornou resultado."
    #             )

    #         # --------------------------------------------------
    #         # GUARDAR RESULTADO
    #         # --------------------------------------------------

    #         self.resultado_ciman = resultado_ciman

    #         # --------------------------------------------------
    #         # DEBUG
    #         # --------------------------------------------------

    #         print("")
    #         print("=" * 60)
    #         print("MOSTRAR RESULTADO ÁREAS CIMAN")
    #         print("=" * 60)
    #         print("Resultado recebido:")
    #         print(resultado_ciman)
    #         print("=" * 60)
    #         print("")

    #         # --------------------------------------------------
    #         # ABRIR JANELA DE RESULTADO
    #         # --------------------------------------------------

    #         from .resultado_areas_ciman_dialog import (
    #             ResultadoAreasCIMANDialog
    #         )

    #         dialog = ResultadoAreasCIMANDialog(
    #             resultado_ciman=resultado_ciman,
    #             parent=self,
    #         )

    #         dialog.exec()

    #     except Exception:

    #         raise

    #até aqui

    # ======================================================
    # MOSTRAR RESULTADOS ÁREAS CIMAN
    # ======================================================

    def _mostrar_resultado_areas_ciman(
        self,
        resultados_ciman,
    ):

        try:

            # --------------------------------------------------
            # VALIDAR RESULTADOS
            # --------------------------------------------------

            if not resultados_ciman:

                raise RuntimeError(
                    "A análise CIMAN não retornou resultados."
                )

            # --------------------------------------------------
            # GUARDAR RESULTADOS
            # --------------------------------------------------

            self.resultado_ciman = (
                resultados_ciman
            )

            # --------------------------------------------------
            # DEBUG
            # --------------------------------------------------

            print("")
            print("=" * 60)
            print("MOSTRAR RESULTADOS ÁREAS CIMAN")
            print("=" * 60)
            print(
                f"Total de resultados: "
                f"{len(resultados_ciman)}"
            )

            for item in resultados_ciman:

                print("")
                print(
                    f"Evento: "
                    f"{item.get('id_evento')}"
                )

                print(
                    "Resultado:"
                )

                print(
                    item.get("resultado")
                )

            print("=" * 60)
            print("")

            # --------------------------------------------------
            # ABRIR JANELA DE RESULTADOS
            # --------------------------------------------------

            from .resultado_areas_ciman_dialog import (
                ResultadoAreasCIMANDialog
            )

            dialog = ResultadoAreasCIMANDialog(
                resultados_ciman=resultados_ciman,
                parent=self,
            )

            dialog.exec()

        except Exception:
            raise
    
    # ======================================================
    # ANALISAR ÁREAS CIMAN
    # ======================================================

    def abrir_analise_areas_ciman(self):

        # --------------------------------------------------
        # OBTER EVENTOS MARCADOS
        # --------------------------------------------------

        ids_eventos = self._obter_eventos_marcados()

        if not ids_eventos:

            QMessageBox.information(
                self,
                "QMD Tools Explorer",
                "Marque pelo menos um evento para "
                "analisar as Áreas CIMAN."
            )

            return

        try:

            self.areas_ciman_btn.setEnabled(
                False
            )

            QApplication.setOverrideCursor(
                Qt.WaitCursor
            )

            # ----------------------------------------------
            # PREPARAR CAMADAS
            # ----------------------------------------------

            camadas_ciman = (
                self._obter_camadas_ciman()
            )

            # ----------------------------------------------
            # LISTA DE RESULTADOS
            # ----------------------------------------------

            resultados_ciman = []

            # ----------------------------------------------
            # ANALISAR EVENTOS MARCADOS
            # ----------------------------------------------

            for id_evento in ids_eventos:

                dados = self._obter_dados_resultado(
                    id_evento
                )

                if dados is None:
                    continue

                feature = dados.get(
                    "feature"
                )

                if feature is None:
                    continue

                # ------------------------------------------
                # CRIAR ANALISADOR
                # ------------------------------------------

                analisador = AnalisadorAreasCIMAN(
                    evento_feature=feature,
                    camadas_ciman=camadas_ciman,
                    raio_metros=10000,
                    iface=iface,
                )

                # ------------------------------------------
                # EXECUTAR ANÁLISE
                # ------------------------------------------

                resultado = analisador.analisar()

                # ------------------------------------------
                # GUARDAR RESULTADO DO EVENTO
                # ------------------------------------------

                resultados_ciman.append(
                    {
                        "id_evento": id_evento,
                        "resultado": resultado,
                    }
                )

            # ----------------------------------------------
            # VERIFICAR RESULTADOS
            # ----------------------------------------------

            if not resultados_ciman:

                QMessageBox.warning(
                    self,
                    "QMD Tools Explorer",
                    "Não foi possível analisar os eventos "
                    "selecionados."
                )

                return

            # ----------------------------------------------
            # GUARDAR RESULTADOS
            # ----------------------------------------------

            self.resultado_ciman = (
                resultados_ciman
            )

            # ----------------------------------------------
            # MOSTRAR RESULTADOS
            # ----------------------------------------------

            self._mostrar_resultado_areas_ciman(
                resultados_ciman
            )
        except Exception:

            import traceback

            erro_completo = traceback.format_exc()

            log_message(
                erro_completo
            )

            QMessageBox.critical(
                self,
                "Erro na análise das Áreas CIMAN",
                erro_completo
            )

        # except Exception as e:

        #     QMessageBox.critical(
        #         self,
        #         "Erro na análise das Áreas CIMAN",
        #         str(e)
        #     )

        finally:

            QApplication.restoreOverrideCursor()

            self.areas_ciman_btn.setEnabled(
                True
            )

    # ======================================================
    # ANALISAR PONTOS GOES
    # ======================================================

    def analisar_pontos_goes(self):

        try:

            self.analisar_btn.setEnabled(
                False
            )

            self.add_map_btn.setEnabled(
                False
            )

            self.areas_ciman_btn.setEnabled(
                False
            )

            self.evento_selecionado = None

            self._limpar_informacoes_evento()

            self.table.setRowCount(
                0
            )

            self.progress.setVisible(
                True
            )

            self.progress.setRange(
                0,
                0
            )

            self.summary_label.setText(
                "Preparando arquivos GOES e Eventos Ativos..."
            )

            QApplication.processEvents()

            # --------------------------------------------------
            # CONFIG
            # --------------------------------------------------

            config = self._load_config()

            monitoramento = config.get(
                "monitoramento_goes",
                {}
            )

            if not monitoramento:

                raise Exception(
                    "Grupo 'monitoramento_goes' não encontrado "
                    "no reference_layers.json."
                )

            goes_config = monitoramento.get(
                "pontos_atencao_48h"
            )

            eventos_config = monitoramento.get(
                "eventos_ativos"
            )

            if goes_config is None:

                raise Exception(
                    "Configuração 'pontos_atencao_48h' "
                    "não encontrada."
                )

            if eventos_config is None:

                raise Exception(
                    "Configuração 'eventos_ativos' "
                    "não encontrada."
                )

            # --------------------------------------------------
            # GOES
            # --------------------------------------------------

            self.summary_label.setText(
                "Obtendo Pontos de Atenção GOES..."
            )

            QApplication.processEvents()

            goes_path = self._get_local_file(
                goes_config
            )

            self.goes_path = goes_path

            # --------------------------------------------------
            # EVENTOS
            # --------------------------------------------------

            self.summary_label.setText(
                "Obtendo Eventos Ativos..."
            )

            QApplication.processEvents()

            eventos_path = self._get_local_file(
                eventos_config
            )

            self.eventos_path = eventos_path

            # --------------------------------------------------
            # ANÁLISE
            # --------------------------------------------------

            self.summary_label.setText(
                "Analisando interseções entre "
                "Pontos GOES e Eventos Ativos..."
            )

            QApplication.processEvents()

            self.worker = AnaliseGoesWorker(
                goes_path,
                eventos_path,
                self
            )

            self.worker.finished_ok.connect(
                self._analise_concluida
            )

            self.worker.failed.connect(
                self._analise_erro
            )

            self.worker.start()

        except Exception as error:

            self._analise_erro(
                str(error)
            )

    # ======================================================
    # ANÁLISE CONCLUÍDA
    # ======================================================

    def _analise_concluida(
        self,
        resultado
    ):

        self.resultado = resultado

        self.progress.setVisible(
            False
        )

        self.analisar_btn.setEnabled(
            True
        )

        resultados = resultado.get(
            "resultados",
            {}
        )

        total_eventos = resultado.get(
            "total_eventos",
            len(resultados)
        )

        total_pontos = resultado.get(
            "total_pontos",
            0
        )


        self.summary_label.setText(
            "RESULTADO DA ANÁLISE\n"
            f"{total_eventos} eventos associados "
            f"• {total_pontos} pontos GOES"
        )

        self._preencher_tabela(
            resultados
        )

    # ======================================================
    # ERRO
    # ======================================================

    def _analise_erro(
        self,
        mensagem
    ):

        self.progress.setVisible(
            False
        )

        self.analisar_btn.setEnabled(
            True
        )

        self.summary_label.setText(
            "Erro durante a análise."
        )

        QMessageBox.critical(
            self,
            "QMD Tools Explorer",
            mensagem
        )

    # ======================================================
    # PREENCHER TABELA
    # ======================================================

    def _preencher_tabela(
        self,
        resultados
    ):
        
        # ======================================================
        # GUARDAR RESULTADOS DA ANÁLISE GOES
        # ======================================================

        self.resultados_eventos = resultados

        self.table.blockSignals(
            True
        )

        self.table.setRowCount(
            0
        )

        resultados_ordenados = sorted(
            resultados.items(),
            key=lambda item: (
                item[1]
                .get("feature")
                .attribute("qtd_frente")
                if item[1].get("feature") is not None
                and "qtd_frente" in item[1].get("feature").fields().names()
                and item[1].get("feature").attribute("qtd_frente") is not None
                else 0
            ),
            reverse=True
        )

        for row, (
            id_evento,
            dados
        ) in enumerate(
            resultados_ordenados
        ):

            feature = dados.get(
                "feature"
            )

            if feature is None:
                continue

            self.table.insertRow(
                row
            )

            regiao = self._get_feature_value(
                feature,
                "regioes"
            )

            municipio = self._get_feature_value(
                feature,
                "municipios"
            )

            estado = self._get_feature_value(
                feature,
                "estados"
            )

            qtd_pontos = len(
                dados.get(
                    "pontos",
                    []
                )
            )

            classes_lista = dados.get(
                "classes",
                []
            )

            classes = self._formatar_classes(
                classes_lista
            )

            qtd_frente = self._get_feature_value(
                feature,
                "qtd_frente"
            )

            # --------------------------------------------------
            # SELEÇÃO POR CHECKBOX
            # --------------------------------------------------

            item_check = QTableWidgetItem()

            item_check.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsUserCheckable
            )

            item_check.setCheckState(
                Qt.Unchecked
            )

            item_check.setData(
                Qt.UserRole,
                id_evento
            )

            item_check.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                0,
                item_check
            )

            # --------------------------------------------------
            # STATUS VISUAL
            # --------------------------------------------------

            item_status = QTableWidgetItem()

            if "144" in classes and "288" in classes:
                item_status.setText("🔴")

            elif "72" in classes and "143" in classes:
                item_status.setText("🟠")

            else:
                item_status.setText("")

            item_status.setData(
                Qt.UserRole,
                id_evento
            )

            item_status.setTextAlignment(
                Qt.AlignCenter
            )

            self.table.setItem(
                row,
                1,
                item_status
            )

            # --------------------------------------------------
            # DEMAIS COLUNAS
            # --------------------------------------------------

            valores = [
                str(id_evento),
                self._formatar_texto(regiao),
                self._formatar_texto(municipio),
                self._formatar_texto(estado),
                self._formatar_texto(qtd_frente),
                str(qtd_pontos),
                classes,
            ]

            for column, value in enumerate(
                valores,
                start=2
            ):

                item = QTableWidgetItem(
                    value
                )

                item.setData(
                    Qt.UserRole,
                    id_evento
                )

                if column in (
                    2,
                    5,
                    6,
                    7,
                ):

                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                self.table.setItem(
                    row,
                    column,
                    item
                )

            # --------------------------------------------------
            # BOTÃO INFO
            # --------------------------------------------------
            info_btn = QPushButton(
                "Info"
            )

            info_btn.setFixedHeight(
                22
            )

            info_btn.setToolTip(
                f"Mostrar informações do evento {id_evento}"
            )

            info_btn.clicked.connect(
                lambda checked=False, event_id=id_evento:
                    self.mostrar_informacoes_evento(event_id)
            )

            self.table.setCellWidget(
                row,
                9,
                info_btn
            )

        self.table.blockSignals(
            False
        )

        self.table.resizeRowsToContents()

        self._atualizar_botao_adicionar_mapa()

        self._atualizar_botoes_selecao()

    # ======================================================
    # ATUALIZAR BOTÕES CONFORME SELEÇÃO
    # ======================================================

    def _atualizar_botoes_selecao(
        self,
        item=None
    ):

        ids_eventos = (
            self._obter_eventos_marcados()
        )

        tem_eventos = bool(
            ids_eventos
        )

        self.add_map_btn.setEnabled(
            tem_eventos
        )

        self.areas_ciman_btn.setEnabled(
            tem_eventos
        )


    # ======================================================
    # INFORMAÇÕES DO EVENTO
    # ======================================================

    def mostrar_informacoes_evento(self, id_evento=None):

        # --------------------------------------------------
        # Compatibilidade: se chamado sem ID, usa a linha
        # atualmente selecionada.
        # --------------------------------------------------

        if id_evento is None:

            selected_rows = sorted({
                index.row()
                for index in self.table.selectedIndexes()
            })

            if not selected_rows:
                return

            row = selected_rows[0]

            item = self.table.item(
                row,
                2
            )

            if item is None:
                return

            id_evento = item.data(
                Qt.UserRole
            )

        # --------------------------------------------------
        # RECUPERAR DADOS DO EVENTO
        # --------------------------------------------------

        dados = self._obter_dados_resultado(
            id_evento
        )

        if dados is None:

            QMessageBox.warning(
                self,
                "QMD Tools Explorer",
                f"Não foi possível recuperar os dados "
                f"do evento {id_evento}."
            )

            return

        feature = dados.get(
            "feature"
        )

        if feature is None:

            QMessageBox.warning(
                self,
                "QMD Tools Explorer",
                f"Não foi possível recuperar as informações "
                f"do evento {id_evento}."
            )

            return

        # --------------------------------------------------
        # GUARDAR O EVENTO COMPLETO
        # --------------------------------------------------

        self.evento_selecionado = {

            "id_evento": self._get_feature_value(
                feature,
                "id_evento"
            ),

            "tipo_fogo": self._get_feature_value(
                feature,
                "tipo_fogo"
            ),

            "status_nome": self._get_feature_value(
                feature,
                "status_nome"
            ),

            "status_agregado": self._get_feature_value(
                feature,
                "status_agregado"
            ),

            "data_min": self._get_feature_value(
                feature,
                "data_min"
            ),

            "data_max": self._get_feature_value(
                feature,
                "data_max"
            ),

            "duracao_dias": self._get_feature_value(
                feature,
                "duracao_dias"
            ),

            "area_ha": self._get_feature_value(
                feature,
                "area_ha"
            ),

            "regioes": self._get_feature_value(
                feature,
                "regioes"
            ),

            "municipios": self._get_feature_value(
                feature,
                "municipios"
            ),

            "estados": self._get_feature_value(
                feature,
                "estados"
            ),

            "desmatamento_pct": self._get_feature_value(
                feature,
                "desmatamento_pct"
            ),

            "vegetacao_pct": self._get_feature_value(
                feature,
                "vegetacao_pct"
            ),

            "transicao_pct": self._get_feature_value(
                feature,
                "transicao_pct"
            ),

            "qtd_frente": self._get_feature_value(
                feature,
                "qtd_frente"
            ),

            "max_frp": self._get_feature_value(
                feature,
                "max_frp"
            ),

            "pontos_goes": len(
                dados.get(
                    "pontos",
                    []
                )
            ),

            "classes_goes": list(
                dados.get(
                    "classes",
                    []
                )
            ),

            "geometry": feature.geometry(),

            "feature": feature,
        }

        evento = self.evento_selecionado

        # --------------------------------------------------
        # JANELA
        # --------------------------------------------------

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            f"Informações do Evento {id_evento}"
        )

        dialog.setModal(
            True
        )

        dialog.setMinimumWidth(
            560
        )

        dialog_layout = QVBoxLayout(
            dialog
        )

        dialog_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        dialog_layout.setSpacing(
            8
        )

        title = QLabel(
            f"INFORMAÇÕES DO EVENTO {id_evento}"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        dialog_layout.addWidget(
            title
        )

        # --------------------------------------------------
        # DUAS COLUNAS
        # --------------------------------------------------

        columns_layout = QHBoxLayout()

        columns_layout.setSpacing(
            25
        )

        left_form = QFormLayout()

        left_form.setLabelAlignment(
            Qt.AlignRight
        )

        left_form.setFormAlignment(
            Qt.AlignTop
        )

        left_form.setVerticalSpacing(
            5
        )

        right_form = QFormLayout()

        right_form.setLabelAlignment(
            Qt.AlignRight
        )

        right_form.setFormAlignment(
            Qt.AlignTop
        )

        right_form.setVerticalSpacing(
            5
        )

        def adicionar_campo(
            form_layout,
            titulo,
            valor
        ):

            label = QLabel(
                valor
            )

            label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )

            label.setWordWrap(
                True
            )

            form_layout.addRow(
                f"{titulo}:",
                label
            )

        # --------------------------------------------------
        # COLUNA ESQUERDA
        # --------------------------------------------------

        adicionar_campo(
            left_form,
            "Evento",
            self._formatar_texto(
                evento.get("id_evento")
            )
        )

        adicionar_campo(
            left_form,
            "Tipo de fogo",
            self._formatar_texto(
                evento.get("tipo_fogo")
            )
        )

        adicionar_campo(
            left_form,
            "Status",
            self._formatar_texto(
                evento.get("status_nome")
            )
        )

        adicionar_campo(
            left_form,
            "Status agregado",
            self._formatar_texto(
                evento.get("status_agregado")
            )
        )

        adicionar_campo(
            left_form,
            "Qtd Frentes",
            self._formatar_texto(
                evento.get("qtd_frente")
            )
        )

        adicionar_campo(
            left_form,
            "Início",
            self._formatar_data(
                evento.get("data_min")
            )
        )

        adicionar_campo(
            left_form,
            "Fim",
            self._formatar_data(
                evento.get("data_max")
            )
        )

        adicionar_campo(
            left_form,
            "Duração",
            self._formatar_duracao(
                evento.get("duracao_dias")
            )
        )

        adicionar_campo(
            left_form,
            "Área",
            self._formatar_area(
                evento.get("area_ha")
            )
        )

        # --------------------------------------------------
        # COLUNA DIREITA
        # --------------------------------------------------

        adicionar_campo(
            right_form,
            "Região / Área",
            self._formatar_texto(
                evento.get("regioes")
            )
        )

        adicionar_campo(
            right_form,
            "Município",
            self._formatar_texto(
                evento.get("municipios")
            )
        )

        adicionar_campo(
            right_form,
            "Estado",
            self._formatar_texto(
                evento.get("estados")
            )
        )

        adicionar_campo(
            right_form,
            "FRP Máx",
            self._formatar_texto(
                evento.get("max_frp")
            )
        )

        adicionar_campo(
            right_form,
            "Desmatamento",
            self._formatar_percentual(
                evento.get("desmatamento_pct")
            )
        )

        adicionar_campo(
            right_form,
            "Vegetação",
            self._formatar_percentual(
                evento.get("vegetacao_pct")
            )
        )

        adicionar_campo(
            right_form,
            "Transição",
            self._formatar_percentual(
                evento.get("transicao_pct")
            )
        )

        adicionar_campo(
            right_form,
            "Pontos GOES",
            self._formatar_texto(
                evento.get("pontos_goes")
            )
        )

        adicionar_campo(
            right_form,
            "Classes GOES",
            self._formatar_classes(
                evento.get("classes_goes")
            )
        )

        columns_layout.addLayout(
            left_form,
            1
        )

        columns_layout.addLayout(
            right_form,
            1
        )

        dialog_layout.addLayout(
            columns_layout
        )

        # --------------------------------------------------
        # BOTÃO FECHAR
        # --------------------------------------------------

        buttons_layout = QHBoxLayout()

        buttons_layout.addStretch()

        fechar_btn = QPushButton(
            "Fechar"
        )

        fechar_btn.setMinimumWidth(
            90
        )

        fechar_btn.clicked.connect(
            dialog.accept
        )

        buttons_layout.addWidget(
            fechar_btn
        )

        dialog_layout.addLayout(
            buttons_layout
        )

        dialog.exec()

    # ======================================================
    # LIMPAR EVENTO SELECIONADO
    # ======================================================

    def _limpar_informacoes_evento(self):

        self.evento_selecionado = None

    # ======================================================
    # OBTER VALOR DO FEATURE
    # ======================================================

    def _get_feature_value(
        self,
        feature,
        field_name
    ):

        if feature is None:

            return None

        field_names = feature.fields().names()

        if field_name not in field_names:

            return None

        value = feature[
            field_name
        ]

        if value is None:

            return None

        return value

    # ======================================================
    # FORMATAR TEXTO
    # ======================================================

    def _formatar_texto(
        self,
        value
    ):

        if value is None:

            return "-"

        texto = str(value).strip()

        if not texto:

            return "-"

        return texto

    # ======================================================
    # FORMATAR DATA
    # ======================================================

    def _formatar_data(
        self,
        value
    ):

        if value is None:

            return "-"

        try:

            return value.toString(
                "dd/MM/yyyy"
            )

        except Exception:

            texto = str(value)

            if len(texto) >= 10:

                try:

                    ano, mes, dia = (
                        texto[:10]
                        .split("-")
                    )

                    return (
                        f"{dia}/{mes}/{ano}"
                    )

                except Exception:
                    pass

            return texto

    # ======================================================
    # FORMATAR DURAÇÃO
    # ======================================================

    def _formatar_duracao(
        self,
        value
    ):

        if value is None:

            return "-"

        try:

            dias = int(value)

            if dias == 1:

                return "1 dia"

            return f"{dias} dias"

        except Exception:

            return str(value)

    # ======================================================
    # FORMATAR ÁREA
    # ======================================================

    def _formatar_area(
        self,
        value
    ):

        if value is None:

            return "-"

        try:

            area = float(value)

            return (
                f"{area:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
                + " ha"
            )

        except Exception:

            return f"{value} ha"

    # ======================================================
    # FORMATAR PERCENTUAL
    # ======================================================

    def _formatar_percentual(
        self,
        value
    ):

        if value is None:

            return "-"

        try:

            percentual = float(value)

            return (
                f"{percentual:.2f}"
                .replace(".", ",")
                + " %"
            )

        except Exception:

            return f"{value} %"

    # ======================================================
    # FORMATAR CLASSES GOES
    # ======================================================

    def _formatar_classes(
        self,
        classes
    ):

        if not classes:

            return "-"

        classes_formatadas = []

        for classe in classes:

            texto = str(classe)

            if texto in (
                "72-143",
                "72_143",
                "72 a 143",
            ):

                classes_formatadas.append(
                    "72 até 143 repetições"
                )

            elif texto in (
                "144-288",
                "144_288",
                "144 a 288",
            ):

                classes_formatadas.append(
                    "144 até 288 repetições"
                )

            else:

                classes_formatadas.append(
                    texto
                )

        return " | ".join(
            sorted(
                classes_formatadas
            )
        )

    # ======================================================
    # SELECIONAR TODOS OS EVENTOS
    # ======================================================

    def selecionar_todos_eventos(self):

        self.table.blockSignals(
            True
        )

        try:

            for row in range(
                self.table.rowCount()
            ):

                item = self.table.item(
                    row,
                    0
                )

                if item is not None:
                    item.setCheckState(
                        Qt.Checked
                    )

        finally:

            self.table.blockSignals(
                False
            )

        self._atualizar_botao_adicionar_mapa()

    # ======================================================
    # ALTERAÇÃO DO CHECKBOX
    # ======================================================

    def _ao_checkbox_alterado(
        self,
        item
    ):

        # Só trata alterações da coluna Selecionar
        if item.column() != 0:
            return

        # Atualizar botões
        self._atualizar_botao_adicionar_mapa()

        self._atualizar_botoes_selecao()

        # Se o checkbox foi marcado
        if item.checkState() == Qt.Checked:

            id_evento = item.data(
                Qt.UserRole
            )

            if id_evento is None:
                return

            dados = self.resultados_eventos.get(
                id_evento
            )

            # Tentar também como string
            if dados is None:

                dados = self.resultados_eventos.get(
                    str(id_evento)
                )
                
            if dados is None:

                dados = self.resultados_eventos.get(
                    str(id_evento)
                )

            if dados is None:
                return

            feature = dados.get(
                "feature"
            )

            if feature is None:
                return

            # Atualizar evento selecionado
            # self.evento_selecionado = {

            #     "id_evento": id_evento,

            #     "feature": feature,

            #     "dados": dados,

            # }

            # --------------------------------------------------
            # ATUALIZAR EVENTO SELECIONADO
            # --------------------------------------------------

            self.evento_selecionado = {

                "id_evento": self._get_feature_value(
                    feature,
                    "id_evento"
                ),

                "tipo_fogo": self._get_feature_value(
                    feature,
                    "tipo_fogo"
                ),

                "status_nome": self._get_feature_value(
                    feature,
                    "status_nome"
                ),

                "status_agregado": self._get_feature_value(
                    feature,
                    "status_agregado"
                ),

                "data_min": self._get_feature_value(
                    feature,
                    "data_min"
                ),

                "data_max": self._get_feature_value(
                    feature,
                    "data_max"
                ),

                "duracao_dias": self._get_feature_value(
                    feature,
                    "duracao_dias"
                ),

                "area_ha": self._get_feature_value(
                    feature,
                    "area_ha"
                ),

                "regioes": self._get_feature_value(
                    feature,
                    "regioes"
                ),

                "municipios": self._get_feature_value(
                    feature,
                    "municipios"
                ),

                "estados": self._get_feature_value(
                    feature,
                    "estados"
                ),

                "desmatamento_pct": self._get_feature_value(
                    feature,
                    "desmatamento_pct"
                ),

                "vegetacao_pct": self._get_feature_value(
                    feature,
                    "vegetacao_pct"
                ),

                "transicao_pct": self._get_feature_value(
                    feature,
                    "transicao_pct"
                ),

                "qtd_frente": self._get_feature_value(
                    feature,
                    "qtd_frente"
                ),

                "max_frp": self._get_feature_value(
                    feature,
                    "max_frp"
                ),

                "pontos_goes": len(
                    dados.get(
                        "pontos",
                        []
                    )
                ),

                "classes_goes": list(
                    dados.get(
                        "classes",
                        []
                    )
                ),

                "geometry": feature.geometry(),

                "feature": feature,
            }

            # --------------------------------------------------
            # SELECIONAR A LINHA VISUALMENTE
            # --------------------------------------------------

            self.table.selectRow(
                item.row()
            )

            # Atualizar card de informações
            # self._atualizar_informacoes_evento(
            #     feature
            # )

    # ======================================================
    # LIMPAR SELEÇÃO DOS EVENTOS
    # ======================================================

    def limpar_selecao_eventos(self):

        self.table.blockSignals(
            True
        )

        try:

            for row in range(
                self.table.rowCount()
            ):

                item = self.table.item(
                    row,
                    0
                )

                if item is not None:
                    item.setCheckState(
                        Qt.Unchecked
                    )

            self.table.clearSelection()

        finally:

            self.table.blockSignals(
                False
            )

        self._atualizar_botao_adicionar_mapa()

    # ======================================================
    # ATUALIZAR BOTÃO ADICIONAR AO MAPA
    # ======================================================

    def _atualizar_botao_adicionar_mapa(self):

        possui_selecao = False

        for row in range(
            self.table.rowCount()
        ):

            item = self.table.item(
                row,
                0
            )

            if (
                item is not None
                and item.checkState() == Qt.Checked
            ):

                possui_selecao = True
                break

        self.add_map_btn.setEnabled(
            possui_selecao
        )

    # ======================================================
    # OBTER EVENTOS MARCADOS
    # ======================================================

    def _obter_eventos_marcados(self):

        ids_eventos = []

        for row in range(
            self.table.rowCount()
        ):

            item_check = self.table.item(
                row,
                0
            )

            if item_check is None:
                continue

            if item_check.checkState() != Qt.Checked:
                continue

            id_evento = item_check.data(
                Qt.UserRole
            )

            if id_evento is None:
                continue

            ids_eventos.append(
                id_evento
            )

        return ids_eventos

    # ======================================================
    # OBTER DADOS DO RESULTADO
    # ======================================================

    def _obter_dados_resultado(
        self,
        id_evento
    ):

        if not self.resultado:
            return None
          
        resultados = self.resultado.get(
            "resultados",
            {}
        )

        dados = resultados.get(
            id_evento
        )

        if dados is None:

            dados = resultados.get(
                str(id_evento)
            )

        if dados is None:

            try:

                dados = resultados.get(
                    int(id_evento)
                )

            except Exception:

                pass

        return dados

        # dados = resultados.get(
        #     id_evento
        # )

        # if dados is None:
        #     dados = resultados.get(
        #         str(id_evento)
        #     )

        # if dados is None:
        #     try:
        #         dados = resultados.get(
        #             int(id_evento)
        #         )
        #     except Exception:
        #         pass

        # return dados

    # ======================================================
    # CRIAR CAMADA TEMPORÁRIA
    # ======================================================

    def _criar_camada_temporaria(
        self,
        nome,
        features,
        classes_visuais=None
    ):

        features = [
            feature
            for feature in features
            if feature is not None
            and feature.hasGeometry()
            and not feature.geometry().isEmpty()
        ]

        if not features:
            return None

        primeiro = features[0]

        geometry_type = QgsWkbTypes.displayString(
            primeiro.geometry().wkbType()
        )

        crs_authid = "EPSG:4326"

        if primeiro.geometry() is not None:
            crs_authid = "EPSG:4326"

        uri = (
            f"{geometry_type}?crs={crs_authid}"
        )

        camada = QgsVectorLayer(
            uri,
            nome,
            "memory"
        )

        if not camada.isValid():
            raise RuntimeError(
                f"Não foi possível criar a camada '{nome}'."
            )

        provider = camada.dataProvider()

        # provider.addAttributes(
        #     primeiro.fields()
        # )

        # camada.updateFields()
        provider.addAttributes(
            primeiro.fields()
        )

        # --------------------------------------------------
        # CAMPO PARA CLASSIFICAÇÃO VISUAL
        # --------------------------------------------------

        if "classe_visual" not in primeiro.fields().names():

            provider.addAttributes([
                QgsField(
                    "classe_visual",
                    QVariant.String
                )
            ])

        camada.updateFields()

        novas_features = []

        for feature in features:

            nova_feature = QgsFeature(
                camada.fields()
            )

            nova_feature.setGeometry(
                feature.geometry()
            )

            atributos = []

            for field in camada.fields():

                field_name = field.name()

                if field_name in feature.fields().names():
                    atributos.append(
                        feature[field_name]
                    )
                else:
                    atributos.append(
                        None
                    )

            nova_feature.setAttributes(
                atributos
            )

            novas_features.append(
                nova_feature
            )

        provider.addFeatures(
            novas_features
        )

        camada.updateExtents()

        return camada

    # ======================================================
    # OBTER CAMPO ID DO EVENTO
    # ======================================================

    def _obter_campo_id_evento(
        self,
        camada
    ):

        candidatos = [
            "id_evento",
            "evento_id",
            "id_event",
        ]

        campos = camada.fields().names()

        for candidato in candidatos:

            if candidato in campos:
                return candidato

        return None

    # ======================================================
    # CARREGAR FOCOS DOS EVENTOS SELECIONADOS
    # ======================================================

    def _obter_focos_eventos_selecionados(
        self,
        ids_eventos
    ):

        if not self.eventos_path:
            return []

        uri = (
            f"{self.eventos_path}|layername=focos_ativos"
        )

        camada_focos = QgsVectorLayer(
            uri,
            "focos_ativos",
            "ogr"
        )

        if not camada_focos.isValid():
            return []

        campo_id = self._obter_campo_id_evento(
            camada_focos
        )

        if campo_id is None:
            return []

        ids_texto = {
            str(valor)
            for valor in ids_eventos
        }

        focos = []

        for feature in camada_focos.getFeatures():

            valor = feature[campo_id]

            if str(valor) in ids_texto:
                focos.append(
                    QgsFeature(feature)
                )

        return focos

    # ==================================================
    # APLICAR ESTILO QML
    # ==================================================

    def _aplicar_estilo_qml(
        self,
        camada,
        nome_arquivo_qml
    ):
        """
        Aplica um estilo QML localizado
        no diretório utils do plugin.
        """

        if camada is None:
            return

        plugin_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        caminho_estilo = os.path.join(
            plugin_dir,
            "utils",
            nome_arquivo_qml
        )

        if not os.path.exists(
            caminho_estilo
        ):
            print(
                f"Estilo não encontrado: {caminho_estilo}"
            )
            return

        sucesso, mensagem = (
            camada.loadNamedStyle(
                caminho_estilo
            )
        )

        if not sucesso:
            print(
                f"Erro ao carregar estilo "
                f"{nome_arquivo_qml}: {mensagem}"
            )
            return

        camada.triggerRepaint()

    # ======================================================
    # ADICIONAR SELECIONADOS AO MAPA
    # ======================================================

    def adicionar_eventos_selecionados_mapa(self):

        ids_eventos = self._obter_eventos_marcados()

        if not ids_eventos:

            QMessageBox.information(
                self,
                "QMD Tools Explorer",
                "Marque pelo menos um evento."
            )

            return

        eventos = []
        pontos_goes = []

        for id_evento in ids_eventos:

            dados = self._obter_dados_resultado(
                id_evento
            )

            if dados is None:
                continue

            feature_evento = dados.get(
                "feature"
            )

            # if feature_evento is not None:
            #     eventos.append(
            #         QgsFeature(feature_evento)
            #     )
            if feature_evento is not None:

                campos = QgsFields(
                    feature_evento.fields()
                )

                campos.append(
                    QgsField(
                        "classe_visual",
                        QVariant.String
                    )
                )

                evento_copia = QgsFeature(
                    campos
                )

                evento_copia.setGeometry(
                    feature_evento.geometry()
                )

                for campo in feature_evento.fields():

                    nome_campo = campo.name()

                    evento_copia.setAttribute(
                        nome_campo,
                        feature_evento.attribute(
                            nome_campo
                        )
                    )

                evento_copia.setAttribute(
                    "classe_visual",
                    dados.get(
                        "classe_visual"
                    )
                )

                eventos.append(
                    evento_copia
                )

            pontos = dados.get(
                "pontos",
                []
            )

            pontos_classes = dados.get(
                "pontos_classes",
                []
            )

            for indice, ponto in enumerate(
                pontos
            ):

                campos = QgsFields(
                    ponto.fields()
                )

                campos.append(
                    QgsField(
                        "classe_visual",
                        QVariant.String
                    )
                )

                ponto_copia = QgsFeature(
                    campos
                )

                ponto_copia.setGeometry(
                    ponto.geometry()
                )

                # Copia todos os atributos originais
                for campo in ponto.fields():

                    nome_campo = campo.name()

                    ponto_copia.setAttribute(
                        nome_campo,
                        ponto.attribute(
                            nome_campo
                        )
                    )

                # Classe correspondente a este ponto
                classe_ponto = None

                if indice < len(
                    pontos_classes
                ):
                    classe_ponto = (
                        pontos_classes[indice]
                    )

                texto_classe = str(
                    classe_ponto
                ).lower()

                if (
                    "144" in texto_classe
                    and "288" in texto_classe
                ):

                    classe_visual = "vermelho"

                elif (
                    "72" in texto_classe
                    and "143" in texto_classe
                ):

                    classe_visual = "laranja"

                else:

                    classe_visual = None

                ponto_copia.setAttribute(
                    "classe_visual",
                    classe_visual
                )

                pontos_goes.append(
                    ponto_copia
                )

        if not eventos:

            QMessageBox.warning(
                self,
                "QMD Tools Explorer",
                "Não foi possível recuperar os eventos selecionados."
            )

            return

        # --------------------------------------------------
        # REMOVER CAMADAS ANTERIORES COM O MESMO NOME
        # --------------------------------------------------

        nomes_camadas = [
            "Eventos Selecionados",
            "Focos dos Eventos",
            "Pontos de Atenção GOES",
        ]

        projeto = QgsProject.instance()

        for nome in nomes_camadas:

            for camada_antiga in projeto.mapLayersByName(nome):
                projeto.removeMapLayer(
                    camada_antiga.id()
                )

        # --------------------------------------------------
        # CRIAR CAMADA DE EVENTOS
        # --------------------------------------------------

        classes_visuais_eventos = {}

        for id_evento in ids_eventos:

            dados = self._obter_dados_resultado(
                id_evento
            )

            if dados is not None:

                classes_visuais_eventos[
                    str(id_evento)
                ] = dados.get(
                    "classe_visual"
                )


        camada_eventos = self._criar_camada_temporaria(
            "Eventos Ativos",
            eventos,
            classes_visuais_eventos
        )

        # --------------------------------------------------
        # CRIAR CAMADA DE FOCOS
        # --------------------------------------------------

        focos = self._obter_focos_eventos_selecionados(
            ids_eventos
        )

        camada_focos = self._criar_camada_temporaria(
            "Focos dos Eventos",
            focos
        )

        # --------------------------------------------------
        # CRIAR CAMADA DE PONTOS GOES
        # --------------------------------------------------

        camada_goes = self._criar_camada_temporaria(
            "Pontos de Atenção GOES",
            pontos_goes
        )

        # ==================================================
        # Aplicar o Estilo das Camadas
        # ==================================================

        self._aplicar_estilo_qml(
            camada_eventos,
            "estilo_eventos_ativos_48h.qml"
        )

        self._aplicar_estilo_qml(
            camada_focos,
            "estilo_focos_todosat_wfs.qml"
        )

        self._aplicar_estilo_qml(
            camada_goes,
            "estilo_pontos_atencao_goes_48h.qml"
        )

        # --------------------------------------------------
        # ADICIONAR AO PROJETO EM UM GRUPO
        # --------------------------------------------------

        # Remove um grupo anterior, caso exista.
        raiz = projeto.layerTreeRoot()
        grupo_antigo = raiz.findGroup(
            "Análise GOES (48h)"
        )

        if grupo_antigo is not None:
            raiz.removeChildNode(
                grupo_antigo
            )

        # --------------------------------------------------
        # ADICIONAR AO PROJETO
        # --------------------------------------------------

        for camada in (
            camada_goes,
            camada_focos,
            camada_eventos,
        ):

            if camada is not None:
                projeto.addMapLayer(
                    camada,
                    False
                )

        # Cria um único grupo para controlar as três camadas.
        grupo_goes = raiz.addGroup(
            "Análise GOES (48h)"
        )

        for camada in (
            camada_goes,
            camada_focos,
            camada_eventos,
            
        ):

            if camada is not None:
                grupo_goes.addLayer(
                    camada
                )
                
        # --------------------------------------------------
        # ZOOM PARA OS EVENTOS SELECIONADOS
        # --------------------------------------------------

        extent = QgsRectangle()

        for feature in eventos:
            extent.combineExtentWith(
                feature.geometry().boundingBox()
            )

        if not extent.isNull():
            extent.scale(
                1.10
            )
            iface.mapCanvas().setExtent(
                extent
            )

        iface.mapCanvas().refresh()

        total_focos = len(
            focos
        )

        total_goes = len(
            pontos_goes
        )

        QMessageBox.information(
            self,
            "QMD Tools Explorer",
            f"Foram adicionados ao mapa:\n\n"
            f"• {len(eventos)} evento(s)\n"
            f"• {total_focos} foco(s)\n"
            f"• {total_goes} ponto(s) de atenção GOES"
        )


    # ======================================================
    # RETORNAR EVENTO SELECIONADO
    # ======================================================

    def obter_evento_selecionado(self):

        return self.evento_selecionado