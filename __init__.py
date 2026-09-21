# -*- coding: utf-8 -*-
"""
/***************************************************************************

QMD Tools Explorer - Um plugin do QGIS para acessar o Brasil
Cubo de dados para exibir as cenas no formato COG (Cloud Optimized GeoTIFF) 
e produtos do Programa Queimadas do INPE.

---------------------------------------------------------------------------
begin                : 2026-09-21
copyright            : (C) 2026 by Paulo Cunha
email                : paulowpc@gmail.com
---------------------------------------------------------------------------

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

Este script inicializa o plugin, tornando-o conhecido pelo QGIS.

"""

__author__ = "Paulo Cunha"
__date__ = "2026-09-21"
__copyright__ = "(C) 2026, Paulo Cunha"
__revision__ = "$Format:%H$"


def classFactory(iface):
    from .plugin import QMDToolsExplorerPlugin
    return QMDToolsExplorerPlugin(iface)
