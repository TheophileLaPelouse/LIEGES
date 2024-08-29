# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cycle
                                 A QGIS plugin
 This plugins helps hydraulics engineers to quantify the emission in any given project. It is compatible with Hydra and Expresseau.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-08-21
        copyright            : (C) 2024 by Setec Hydratec
        email                : theophile.mounier@setec.com
        git sha              : $Format:%H$
 ***************************************************************************/

 This script initializes the plugin, making it known to QGIS.
"""
import os 


# ENVIRONMENTS
if 'PGSERVICEFILE' not in os.environ: # .pg_service.conf not set in environment
    os.environ['PGSERVICEFILE'] = os.path.join(os.path.expanduser('~'), ".pg_service.conf")
    

def classFactory(iface):  # pylint: disable=invalid-name
    """Load Cycle class from file Cycle.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .cycle import Cycle
    return Cycle(iface)
