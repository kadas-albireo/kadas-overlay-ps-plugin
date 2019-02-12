# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OverlayPS
                                 A QGIS plugin
 This plugin paints an overlay
                             -------------------
        begin                : 2018-12-17
        copyright            : (C) 2018 by Sourcepole AG
        email                : smani@sourcepole.ch
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


def classFactory(iface):
    from .overlay_ps import OverlayPS
    return OverlayPS(iface)
