# -*- coding: utf-8 -*-

"""
Gerenciamento das dependências Python do QMD Tools Explorer.

Este módulo utiliza somente bibliotecas da biblioteca padrão
do Python para verificar e gerenciar as dependências externas
do plugin.

Importante:
    Não importar aqui bibliotecas como shapely, requests, lxml,
    pystac ou pystac-client diretamente.
"""

import importlib
from importlib import metadata
from pathlib import Path


DEPENDENCIES = [
    {
        "package": "pystac-client",
        "import_name": "pystac_client",
        "description": "Acesso a catálogos STAC",
        "modules": ["Busca / Imagens de Satélite"],
        "required": True,
        "installable": True,
    },
    {
        "package": "pystac",
        "import_name": "pystac",
        "description": "Estrutura e objetos STAC",
        "modules": ["Busca / Imagens de Satélite"],
        "required": True,
        "installable": True,
    },
    {
        "package": "shapely",
        "import_name": "shapely",
        "description": "Operações e análises geométricas",
        "modules": ["Busca / Imagens de Satélite"],
        "required": True,
        "installable": True,
    },
    {
        "package": "requests",
        "import_name": "requests",
        "description": "Acesso a serviços HTTP",
        "modules": ["Focos de Queimadas", "Resultados"],
        "required": True,
        "installable": True,
    },
    {
        "package": "lxml",
        "import_name": "lxml",
        "description": "Processamento XML",
        "modules": ["Focos de Queimadas"],
        "required": True,
        "installable": True,
    },
]


def get_dependency_origin(import_name):
    """
    Identifica a origem de uma biblioteca Python.

    Retorna:
        str: origem da biblioteca.
    """

    try:
        module = importlib.import_module(import_name)

    except ImportError:
        return "Não disponível"

    except Exception:
        return "Não disponível"

    module_file = Path(
        getattr(module, "__file__", "")
    ).resolve()

    path_text = str(module_file).replace("\\", "/").lower()

    if "/qmd_tools_explorer/vendor/" in path_text:
        return "QMD Tools Explorer"

    if "/plugins/qgis_stac/lib/" in path_text:
        return "STAC API Browser"

    if "/site-packages/" in path_text:
        return "Ambiente Python"

    return "Outro"


def check_dependency(dependency):
    """
    Verifica uma dependência Python.

    Retorna um dicionário contendo o estado da dependência,
    sua versão e sua origem.
    """

    package = dependency["package"]
    import_name = dependency["import_name"]

    result = {
        "package": package,
        "import_name": import_name,
        "description": dependency.get("description", ""),
        "modules": dependency.get("modules", []),
        "required": dependency.get("required", True),
        "installable": dependency.get("installable", False),
        "installed": False,
        "version": None,
        "origin": "Não disponível",
        "error": None,
    }

    try:
        module = importlib.import_module(import_name)
        result["installed"] = True

    except ImportError as exc:
        result["error"] = str(exc)
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result

    # Primeiro tenta a versão declarada pelo próprio módulo.
    version = getattr(module, "__version__", None)

    # Depois tenta a versão registrada nos metadados do pacote.
    if not version:
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = "desconhecida"
        except Exception:
            version = "desconhecida"

    result["version"] = str(version)
    result["origin"] = get_dependency_origin(import_name)

    return result


def check_dependencies():
    """
    Verifica todas as dependências do QMD Tools Explorer.

    Retorna uma lista de dicionários com o resultado da verificação.
    """

    return [
        check_dependency(dependency)
        for dependency in DEPENDENCIES
    ]


def missing_dependencies():
    """
    Retorna somente as dependências obrigatórias que não estão instaladas.
    """

    return [
        result
        for result in check_dependencies()
        if result["required"] and not result["installed"]
    ]


def missing_installable_dependencies():
    """
    Retorna somente as dependências obrigatórias que estão ausentes
    e podem ser instaladas pelo QMD Tools Explorer.
    """

    return [
        result
        for result in check_dependencies()
        if (
            result["required"]
            and result["installable"]
            and not result["installed"]
        )
    ]


def all_dependencies_installed():
    """
    Retorna True quando todas as dependências obrigatórias
    estão disponíveis.
    """

    return len(missing_dependencies()) == 0


__all__ = [
    "DEPENDENCIES",
    "check_dependency",
    "check_dependencies",
    "get_dependency_origin",
    "missing_dependencies",
    "missing_installable_dependencies",
    "all_dependencies_installed",
]
