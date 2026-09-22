# -*- coding: utf-8 -*-
"""Configurações do QMD Tools Explorer."""

import json
import shutil
from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.core import QgsApplication


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

STAC_URL = "https://data.inpe.br/bdc/stac/v1/"

PLUGIN_DIR = Path(__file__).resolve().parent.parent
COLLECTIONS_FILE = PLUGIN_DIR / "config" / "collection_bdc.json"

SETTINGS_ORGANIZATION = "INPE"
SETTINGS_APPLICATION = "QMDToolsExplorer"
OUTPUT_DIR_KEY = "output_dir"


# =========================================================
# COLEÇÕES
# =========================================================

def load_collections():
    """Carrega as coleções do arquivo collection_bdc.json."""

    if not COLLECTIONS_FILE.exists():
        raise FileNotFoundError(
            "Arquivo collection_bdc.json não encontrado em: "
            f"{COLLECTIONS_FILE}"
        )

    with COLLECTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# =========================================================
# CACHE PADRÃO
# =========================================================

def get_cache_dir():
    """Retorna o diretório de cache padrão do QMD Tools Explorer."""

    qgis_dir = Path(
        QgsApplication.qgisSettingsDirPath()
    )

    cache_dir = (
        qgis_dir
        / "qmd_tools_explorer"
        / "cache"
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return cache_dir


# =========================================================
# DIRETÓRIO DE SAÍDA
# =========================================================

def get_output_dir():
    """
    Retorna o último diretório escolhido pelo usuário.

    Se nenhum diretório tiver sido configurado, utiliza o
    cache padrão do QMD Tools Explorer.
    """

    settings = QSettings(
        SETTINGS_ORGANIZATION,
        SETTINGS_APPLICATION,
    )

    value = settings.value(
        OUTPUT_DIR_KEY,
        "",
    )

    if value:
        return str(value)

    return str(get_cache_dir())


def get_saved_output_dir():
    """Retorna apenas o diretório de saída escolhido pelo usuário.

    Retorna string vazia quando o diretório padrão está sendo utilizado.
    """

    settings = QSettings(
        SETTINGS_ORGANIZATION,
        SETTINGS_APPLICATION,
    )

    value = settings.value(
        OUTPUT_DIR_KEY,
        "",
    )

    if value:
        try:
            saved_path = Path(str(value)).resolve()
            default_path = get_cache_dir().resolve()

            if saved_path == default_path:
                return ""
        except Exception:
            pass

        return str(value)

    return ""


def save_output_dir(path):
    """Salva o diretório de saída escolhido pelo usuário."""

    if not path:
        return

    settings = QSettings(
        SETTINGS_ORGANIZATION,
        SETTINGS_APPLICATION,
    )

    settings.setValue(
        OUTPUT_DIR_KEY,
        str(path),
    )

    settings.sync()


# =========================================================
# LIMPAR CACHE
# =========================================================

def clear_cache():
    """
    Remove todo o conteúdo do cache padrão.

    O diretório principal do cache é mantido para que possa
    ser reutilizado imediatamente pelo plugin.

    Retorna
    -------
    tuple
        (sucesso_total, lista_de_erros)
    """

    cache_dir = get_cache_dir()
    errors = []

    for child in list(cache_dir.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception as error:
            errors.append(
                f"{child}: {error}"
            )

    return len(errors) == 0, errors
