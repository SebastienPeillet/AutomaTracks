# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AutomaTracks
                                 A QGIS plugin
 Automatic tracks with constraint with path point
                              -------------------
        begin                : 2018-01-25
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Peillet Sébastien
        email                : peillet.seb@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, \
    qVersion, QCoreApplication, Qt, QFileInfo
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsRasterLayer, QgsGeometry
import math
import Utils

# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from AutomaTracks_dockwidget import AutomaTracksDockWidget
from reOrder_Dock import reOrderDock
from ridgeToPoint_Dock import ridgeToPointDock
import os.path



class AutomaTracks:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AutomaTracks_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&AutomaTracks')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'AutomaTracks')
        self.toolbar.setObjectName(u'AutomaTracks')

        #print "** INITIALIZING AutomaTracks"

        self.pluginIsActive = False
        self.dockwidget = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('AutomaTracks', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/AutomaTracks/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'AutomaTracks'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.dockwidget = AutomaTracksDockWidget()
        self.listVectLayer()
        self.listRastLayer()
        self.dockwidget.DEMActButton.clicked.connect(self.listRastLayer)
        self.dockwidget.MaskActButton.clicked.connect(self.listRastLayerMask)
        self.dockwidget.PointActButton.clicked.connect(self.listVectLayer)
        self.dockwidget.reOrderButton.clicked.connect(self.reOrderScript)
        self.dockwidget.ridgeToPointButton.clicked.connect(self.ridgeToPointScript)
        self.dockwidget.LaunchButton.clicked.connect(self.launchAutomaTracks)
        self.canvas.layersChanged.connect(self.layersUpdate)
    #--------------------------------------------------------------------------
    def layersUpdate(self):
        track_text = self.dockwidget.PointInput.currentText()
        mask_text = self.dockwidget.MaskInput.currentText()
        dem_text = self.dockwidget.DEMInput.currentText()
        self.listRastLayer()
        self.listRastLayerMask()
        self.listVectLayer()
        track_ind = self.dockwidget.PointInput.findText(track_text)
        mask_ind = self.dockwidget.PointInput.findText(mask_text)
        print mask_ind
        dem_ind = self.dockwidget.DEMInput.findText(dem_text)
        if track_ind != -1 :
            self.dockwidget.PointInput.setCurrentIndex(track_ind)
        if mask_ind != -1 :
            self.dockwidget.PointInput.setCurrentIndex(mask_ind)
        if dem_ind != -1 :
            self.dockwidget.DEMInput.setCurrentIndex(dem_ind)
        return None

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING AutomaTracks"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD AutomaTracks"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&AutomaTracks'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    # AutomaTracks function
    def listRastLayer(self):
        """List raster inputs for the DEM selection"""

        # clear list and index
        self.dockwidget.DEMInput.clear()
        self.dockwidget.DEMInput.clearEditText()
        self.rast_list = []
        layers = self.iface.legendInterface().layers()
        self.rast_layer_list = []
        index = 0
        # fill the list layer
        for layer in layers:
            if layer.type() == 1:
                self.rast_layer_list.append(layer.name())
                self.rast_list.append(index)
            index += 1
        # fill comboBox with the list layer
        self.dockwidget.DEMInput.addItems(self.rast_layer_list)

    def listRastLayerMask(self):
        """List raster inputs for the DEM selection"""

        # clear list and index
        self.dockwidget.MaskInput.clear()
        self.dockwidget.MaskInput.clearEditText()
        self.rast_list = []
        layers = self.iface.legendInterface().layers()
        layer_list = []
        index = 0
        # fill the list layer
        for layer in layers:
            if layer.type() == 1:
                layer_list.append(layer.name())
                self.rast_list.append(index)
            index += 1
        layer_list.append('None')
        self.rast_list.append(-1)
        # fill comboBox with the list layer
        self.dockwidget.MaskInput.addItems(layer_list)

    def listVectLayer(self):
        """List line layer for the track selection"""

        # clear list and index
        self.dockwidget.PointInput.clear()
        self.dockwidget.PointInput.clearEditText()
        self.vect_list = []
        layers = self.iface.legendInterface().layers()
        self.vect_layer_list = []
        index = 0
        # fill the list layer
        for layer in layers:
            if layer.type() == 0:
                if layer.geometryType() == 0:
                    self.vect_layer_list.append(layer.name())
                    self.vect_list.append(index)
            index += 1
        # fill comboBox with the list layer
        self.dockwidget.PointInput.addItems(self.vect_layer_list)

    def listlineVectLayer(self):
        """List line layer for the track selection"""

        # clear list and index
        self.dockwidget.PointInput.clear()
        self.dockwidget.PointInput.clearEditText()
        self.line_vect_list = []
        layers = self.iface.legendInterface().layers()
        self.line_layer_list = []
        index = 0
        # fill the list layer
        for layer in layers:
            if layer.type() == 0:
                if layer.geometryType() == 1:
                    self.line_layer_list.append(layer.name())
                    self.line_vect_list.append(index)
            index += 1

    def launchAutomaTracks(self):
        """Process path between pairs of point"""
        # 1 Get the vector layer
        layers = self.iface.legendInterface().layers()
        selected_lignes = self.dockwidget.PointInput.currentIndex()
        pointsLayer = layers[self.vect_list[selected_lignes]]
        # 2 Get the raster layer
        selected_lignes = self.dockwidget.DEMInput.currentIndex()
        DEMLayer = layers[self.rast_list[selected_lignes]]

        # 3 Get the mask layer
        selected_lignes = self.dockwidget.MaskInput.currentIndex()
        mask_index = self.rast_list[selected_lignes]
        if mask_index != -1 :
            MaskLayer = layers[mask_index]
        else :
            MaskLayer = None

        # 4 Get the output path
        outpath = self.dockwidget.outPathEdit.text()

        # 5 Parameters
        try:
            edges = self.dockwidget.EdgesNumGroup.checkedButton().text()
            method = self.dockwidget.DirectionGroup.checkedButton().text()
            if method[0] == 'd' :
                method = 'a'
            elif method[0] == 'r' :
                method = 'r'
            threshold = self.dockwidget.MaxDirSpinBox.value()
            max_slope = self.dockwidget.MaxSlopeSpinBox.value()
            # Launch the path research
            Utils.launchAutomatracks(pointsLayer, DEMLayer, outpath, edges,method,threshold,max_slope, MaskLayer)
        except AttributeError as e:
            print "%s : No edges number or direction option" %e

    def reOrderScript(self):
        """Launch reorder from an outletscript"""
        #list layers
        self.listRastLayer()
        self.listVectLayer()
        #launch the dock
        self.reOrderDock = reOrderDock(self.iface, self.vect_layer_list, self.vect_list)
        self.reOrderDock.show()

    def ridgeToPointScript(self):
        """Launch ridge to point script"""
        #list layers
        self.listRastLayer()
        self.listlineVectLayer()
        #launch the dock
        self.ridgeToPointDock = ridgeToPointDock(self.iface, self.line_layer_list, self.line_vect_list, self.rast_layer_list, self.rast_list)
        self.ridgeToPointDock.show()

    #---------------------------------------------------------------------------
    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING AutomaTracks"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = AutomaTracksDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

