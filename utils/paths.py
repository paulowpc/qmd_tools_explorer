# -*- coding: utf-8 -*-
"""Gerenciamento de diretórios persistentes."""
from pathlib import Path
from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QDir

OUTPUT_DIR_KEY = "qmd_tools_explorer/output_dir"


def get_saved_output_dir():
    path = QgsSettings().value(OUTPUT_DIR_KEY, "", type=str) or ""
    if path and QDir(path).exists():
        return path
    return ""


def save_output_dir(path):
    QgsSettings().setValue(OUTPUT_DIR_KEY, path)


def ensure_output_dir(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
