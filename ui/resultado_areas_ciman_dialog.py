# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import Qt

from qgis.PyQt.QtGui import (
    QColor,
)

from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QFrame,
)

from ..core.stac_core import (
    log_message,
)


# =========================================================
# DIÁLOGO DE RESULTADO DA ANÁLISE CIMAN
# =========================================================

class ResultadoAreasCIMANDialog(QDialog):

    # =====================================================
    # INICIALIZAR
    # =====================================================

    def __init__(
        self,
        resultados_ciman,
        parent=None,
    ):

        super().__init__(
            parent
        )

        # -------------------------------------------------
        # RESULTADOS
        # -------------------------------------------------

        if isinstance(
            resultados_ciman,
            list
        ):

            self.resultados_ciman = (
                resultados_ciman
            )

        elif isinstance(
            resultados_ciman,
            dict
        ):

            # Mantém compatibilidade com o formato antigo
            self.resultados_ciman = [
                {
                    "id_evento": (
                        resultados_ciman.get(
                            "id_evento",
                            "-"
                        )
                    ),

                    "resultado": (
                        resultados_ciman
                    ),
                }
            ]

        else:

            self.resultados_ciman = []

        # -------------------------------------------------
        # CONFIGURAÇÃO DA JANELA
        # -------------------------------------------------

        self.setWindowTitle(
            "Resultados da Análise CIMAN"
        )

        self.setModal(
            True
        )

        self.resize(
            1050,
            560
        )

        # -------------------------------------------------
        # INTERFACE
        # -------------------------------------------------

        self._criar_interface()

        # -------------------------------------------------
        # PREENCHER RESULTADOS
        # -------------------------------------------------

        self._preencher_resultado()


    # =====================================================
    # CRIAR INTERFACE
    # =====================================================

    def _criar_interface(
        self,
    ):

        layout_principal = QVBoxLayout(
            self
        )

        layout_principal.setContentsMargins(
            15,
            15,
            15,
            15
        )

        layout_principal.setSpacing(
            10
        )

        # -------------------------------------------------
        # TÍTULO
        # -------------------------------------------------

        titulo = QLabel(
            "RESULTADO DA ANÁLISE DE ÁREAS CIMAN"
        )

        titulo.setAlignment(
            Qt.AlignCenter
        )

        fonte_titulo = titulo.font()

        fonte_titulo.setBold(
            True
        )

        fonte_titulo.setPointSize(
            12
        )

        titulo.setFont(
            fonte_titulo
        )

        layout_principal.addWidget(
            titulo
        )

        # -------------------------------------------------
        # SEPARADOR
        # -------------------------------------------------

        separador = QFrame()

        separador.setFrameShape(
            QFrame.HLine
        )

        separador.setFrameShadow(
            QFrame.Sunken
        )

        layout_principal.addWidget(
            separador
        )

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        self.status_label = QLabel()

        self.status_label.setAlignment(
            Qt.AlignCenter
        )

        fonte_status = (
            self.status_label.font()
        )

        fonte_status.setBold(
            True
        )

        self.status_label.setFont(
            fonte_status
        )

        self.status_label.setWordWrap(
            True
        )

        layout_principal.addWidget(
            self.status_label
        )

        # -------------------------------------------------
        # TABELA
        # -------------------------------------------------

        self.table = QTableWidget()

        self.table.setColumnCount(
            5
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Evento",
                "Nome da área",
                "Tipo da área",
                "Status CIMAN",
                "Área CIMAN próxima",
            ]
        )

        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.verticalHeader().setVisible(
            False
        )

        header = (
            self.table.horizontalHeader()
        )

        header.setStretchLastSection(
            False
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.Stretch
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeToContents
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.Stretch
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.Stretch
        )

        layout_principal.addWidget(
            self.table,
            1
        )

        # -------------------------------------------------
        # LEGENDA
        # -------------------------------------------------

        legenda = QLabel(
            "● Dentro da área monitorada    "
            "● Próximo de área CIMAN    "
            "● Sem área CIMAN associada"
        )

        legenda.setAlignment(
            Qt.AlignCenter
        )

        legenda.setStyleSheet(
            """
            QLabel {
                padding: 6px;
            }
            """
        )

        layout_principal.addWidget(
            legenda
        )

        # -------------------------------------------------
        # BOTÕES
        # -------------------------------------------------

        layout_botoes = QHBoxLayout()

        layout_botoes.addStretch()

        self.fechar_btn = QPushButton(
            "Fechar"
        )

        self.fechar_btn.setMinimumWidth(
            130
        )

        self.fechar_btn.clicked.connect(
            self.accept
        )

        layout_botoes.addWidget(
            self.fechar_btn
        )

        layout_principal.addLayout(
            layout_botoes
        )


    # =====================================================
    # PREENCHER RESULTADO
    # =====================================================

    def _preencher_resultado(
        self,
    ):
        # -------------------------------------------------
        # LINHAS
        # -------------------------------------------------

        linhas = []

        ### inicio log
    
        # -------------------------------------------------
        # DEBUG TEMPORÁRIO
        # -------------------------------------------------

        log_message(
            "========================================"
        )

        log_message(
            "DEBUG RESULTADOS CIMAN"
        )

        log_message(
            f"RESULTADOS: {self.resultados_ciman}"
        )

        log_message(
            f"TIPO: {type(self.resultados_ciman)}"
        )

        log_message(
            "========================================"
        )


        total_eventos = len(
            self.resultados_ciman
        )

        eventos_com_resultado = 0


        for item in self.resultados_ciman:

            log_message(
                f"ITEM: {item}"
            )

            log_message(
                f"TIPO DO ITEM: {type(item)}"
            )

            if not isinstance(
                item,
                dict
            ):
                log_message(
                    "ITEM NÃO É DICT — IGNORADO"
                )

                continue

            id_evento = item.get(
                "id_evento",
                "-"
            )

            resultado = item.get(
                "resultado",
                {}
            )

            log_message(
                f"ID EVENTO: {id_evento}"
            )

            log_message(
                f"RESULTADO: {resultado}"
            )

            log_message(
                f"TIPO RESULTADO: {type(resultado)}"
            )

        ### fim log

        total_eventos = len(
            self.resultados_ciman
        )

        eventos_com_resultado = 0

        for item in self.resultados_ciman:

            if not isinstance(
                item,
                dict
            ):
                continue

            id_evento = item.get(
                "id_evento",
                "-"
            )

            resultado = item.get(
                "resultado",
                {}
            )

            if not isinstance(
                resultado,
                dict
            ):
                continue

            linhas_evento = resultado.get(
                "linhas",
                []
            )

            if not isinstance(
                linhas_evento,
                list
            ):
                continue

            if linhas_evento:

                eventos_com_resultado += 1

            for linha in linhas_evento:

                if not isinstance(
                    linha,
                    dict
                ):
                    continue

                linha = linha.copy()

                linha[
                    "id_evento"
                ] = id_evento

                linhas.append(
                    linha
                )


        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        if total_eventos == 0:

            status = (
                "Nenhum evento foi analisado."
            )

        elif not linhas:

            status = (
                f"{total_eventos} evento(s) analisado(s). "
                "Nenhuma área CIMAN associada foi encontrada."
            )

        else:

            status = (
                f"{total_eventos} evento(s) analisado(s) • "
                f"{eventos_com_resultado} com resultado(s) CIMAN • "
                f"{len(linhas)} ocorrência(s) encontrada(s)"
            )

        self.status_label.setText(
            status
        )


        # -------------------------------------------------
        # LIMPAR TABELA
        # -------------------------------------------------

        self.table.setRowCount(
            0
        )


        # -------------------------------------------------
        # SEM LINHAS
        # -------------------------------------------------

        if not linhas:

            return


        # -------------------------------------------------
        # ADICIONAR LINHAS
        # -------------------------------------------------

        for linha in linhas:

            self._adicionar_linha(
                linha
            )


        # -------------------------------------------------
        # ALTURA DAS LINHAS
        # -------------------------------------------------

        self.table.resizeRowsToContents()


    # =====================================================
    # ADICIONAR LINHA
    # =====================================================

    def _adicionar_linha(
        self,
        linha,
    ):

        # -------------------------------------------------
        # NOVA LINHA
        # -------------------------------------------------

        row = (
            self.table.rowCount()
        )

        self.table.insertRow(
            row
        )

        # -------------------------------------------------
        # VALORES
        # -------------------------------------------------

        id_evento = (
            linha.get(
                "id_evento",
                "-"
            )
        )

        nome_area = (
            linha.get(
                "nome_area",
                "-"
            )
        )

        tipo_area = (
            linha.get(
                "tipo_area",
                "-"
            )
        )

        status_proximidade = (
            linha.get(
                "status_proximidade",
                "-"
            )
        )

        area_ciman_proxima = (
            linha.get(
                "area_ciman_proxima",
                "-"
            )
        )

        # -------------------------------------------------
        # NORMALIZAR VALORES
        # -------------------------------------------------

        id_evento = (
            self._normalizar_valor(
                id_evento
            )
        )

        nome_area = (
            self._normalizar_valor(
                nome_area
            )
        )

        tipo_area = (
            self._normalizar_valor(
                tipo_area
            )
        )

        status_proximidade = (
            self._normalizar_valor(
                status_proximidade
            )
        )

        area_ciman_proxima = (
            self._normalizar_valor(
                area_ciman_proxima
            )
        )

        # -------------------------------------------------
        # CLASSIFICAR STATUS
        # -------------------------------------------------

        classe_status = (
            self._classificar_status_ciman(
                status_proximidade,
                area_ciman_proxima
            )
        )

        # -------------------------------------------------
        # COLUNA 1
        # EVENTO
        # -------------------------------------------------

        item_evento = QTableWidgetItem(
            id_evento
        )

        item_evento.setTextAlignment(
            Qt.AlignCenter
        )

        self.table.setItem(
            row,
            0,
            item_evento
        )

        # -------------------------------------------------
        # COLUNA 2
        # NOME DA ÁREA
        # -------------------------------------------------

        item_nome = QTableWidgetItem(
            nome_area
        )

        self.table.setItem(
            row,
            1,
            item_nome
        )

        # -------------------------------------------------
        # COLUNA 3
        # TIPO DA ÁREA
        # -------------------------------------------------

        item_tipo = QTableWidgetItem(
            tipo_area
        )

        self.table.setItem(
            row,
            2,
            item_tipo
        )

        # -------------------------------------------------
        # COLUNA 4
        # STATUS CIMAN
        # -------------------------------------------------

        item_status = QTableWidgetItem(
            classe_status["texto"]
        )

        item_status.setTextAlignment(
            Qt.AlignCenter
        )

        item_status.setForeground(
            classe_status["cor"]
        )

        fonte_status = (
            item_status.font()
        )

        fonte_status.setBold(
            True
        )

        item_status.setFont(
            fonte_status
        )

        self.table.setItem(
            row,
            3,
            item_status
        )

        # -------------------------------------------------
        # COLUNA 5
        # ÁREA CIMAN PRÓXIMA
        # -------------------------------------------------

        item_area_proxima = QTableWidgetItem(
            area_ciman_proxima
        )

        self.table.setItem(
            row,
            4,
            item_area_proxima
        )


    # =====================================================
    # CLASSIFICAR STATUS CIMAN
    # =====================================================

    def _classificar_status_ciman(
        self,
        status_proximidade,
        area_ciman_proxima,
    ):

        texto_status = (
            str(
                status_proximidade
            ).strip().lower()
        )

        texto_area = (
            str(
                area_ciman_proxima
            ).strip().lower()
        )

        # -------------------------------------------------
        # DENTRO DA ÁREA
        # AZUL
        # -------------------------------------------------

        if (
            "dentro" in texto_status
            or "monitorada" in texto_status
        ):

            return {
                "texto": (
                    "● Dentro da área monitorada"
                ),

                "cor": QColor(
                    "#1565C0"
                ),
            }

        # -------------------------------------------------
        # PRÓXIMO DE ÁREA CIMAN
        # ROXO
        # -------------------------------------------------

        if (
            "próxim" in texto_status
            or "proxim" in texto_status
            or (
                texto_area
                not in (
                    "",
                    "-",
                    "none",
                    "null",
                )
            )
        ):

            return {
                "texto": (
                    "● Próximo de área CIMAN"
                ),

                "cor": QColor(
                    "#7B1FA2"
                ),
            }

        # -------------------------------------------------
        # SEM ÁREA ASSOCIADA
        # CINZA
        # -------------------------------------------------

        return {
            "texto": (
                "○ Sem área CIMAN associada"
            ),

            "cor": QColor(
                "#616161"
            ),
        }


    # =====================================================
    # NORMALIZAR VALOR
    # =====================================================

    def _normalizar_valor(
        self,
        valor,
    ):

        if valor is None:

            return "-"

        valor = str(
            valor
        ).strip()

        if not valor:

            return "-"

        return valor