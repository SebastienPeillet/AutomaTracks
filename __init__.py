# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AutomaTracks
                                 A QGIS plugin
 Automatic tracks with constraint with path point
                             -------------------
        begin                : 2018-01-25
        copyright            : (C) 2018 by Peillet Sébastien
        email                : peillet.seb@gmail.com
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


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load AutomaTracks class from file AutomaTracks.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .AutoTrack import AutomaTracks
    return AutomaTracks(iface)
