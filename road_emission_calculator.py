# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadEmissionCalculator
                                 A QGIS plugin
 The plugin calculate emissons for selected roads.
                              -------------------
        begin                : 2017-08-08
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Statens Vegvesen
        email                : tomas.levin@vegvesen.no
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QVariant, QObject
from PyQt4.QtGui import QAction, QIcon, QColor
# from qgis.core import QgsVectorLayer, QgsField, QgsMapLayerRegistry, QgsFeature, QgsGeometry, QgsPoint
from qgis.core import QGis, QgsCoordinateTransform, QgsRectangle, QgsPoint, QgsGeometry, QgsCoordinateReferenceSystem
from qgis.gui import QgsRubberBand

from qgis.core import QgsVectorLayer, QgsField, QgsMapLayerRegistry, QgsFeature, QgsGeometry

from copyLatLonTool import CopyLatLonTool
from settings import SettingsWidget
from EmissionCalculatorLib import EmissionCalculatorLib

# from PyQt4.QtCore import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from road_emission_calculator_dialog import RoadEmissionCalculatorDialog
import os.path


class RoadEmissionCalculator:
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
        self.crossRb = QgsRubberBand(self.canvas, QGis.Line)
        self.crossRb.setColor(Qt.red)
        self.emission_calculator = EmissionCalculatorLib()
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        self.s = QSettings()
        self.enableUseOfGlobalCrs()
        self.oldValidation = ""
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RoadEmissionCalculator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = RoadEmissionCalculatorDialog()


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Road Emission Calculator')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadEmissionCalculator')
        self.toolbar.setObjectName(u'RoadEmissionCalculator')

        self.dlg.checkBoxNox.setChecked(True)
        self.dlg.checkBoxCo.setChecked(True)
        self.dlg.checkBoxHc.setChecked(True)
        self.dlg.checkBoxPm.setChecked(True)
        self.dlg.checkBoxFc.setChecked(True)

        self.dlg.checkBoxCumulative.setChecked(True)

        self.dlg.btnEndAddPoint.clicked.connect(self.end_add_point)

        self.dlg.btnAddStartPoint.clicked.connect(self.add_start_point)
        self.dlg.btnAddEndPoint.clicked.connect(self.add_end_point)
        self.dlg.btnGetRoads.clicked.connect(self.get_roads)
        self.dlg.btnGetEmissions.clicked.connect(self.get_emissions)
        self.dlg.cmbBoxType.currentIndexChanged.connect(self.set_vehicle_type)

        # self.clickTool.canvasClicked.connect(self.handleMouseDown)

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
        return QCoreApplication.translate('RoadEmissionCalculator', message)


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

        # Create the dialog (after translation) and keep reference
        # self.dlg = RoadEmissionCalculatorDialog()

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
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/RoadEmissionCalculator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.settingsDialog = SettingsWidget(self, self.iface, self.iface.mainWindow())
        self.mapTool = CopyLatLonTool(self.settingsDialog, self.iface, self.dlg)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Road Emission Calculator'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
        self.canvas.unsetMapTool(self.mapTool)

    def set_vehicle_type(self):
        print self.dlg.cmbBoxType.currentText()

    def end_add_point(self):
        self.canvas.unsetMapTool(self.mapTool)
        self.canvas.setCursor(Qt.ArrowCursor)


    def add_start_point(self):
        self.mapTool.point_name = "Start point"
        self.canvas.setMapTool(self.mapTool)

    def add_end_point(self):
        self.mapTool.point_name = "End point"
        self.canvas.setMapTool(self.mapTool)

    'set new Layers to use the Project-CRS'

    def enableUseOfGlobalCrs(self):
        self.s = QSettings()
        self.oldValidation = str(self.s.value("/Projections/defaultBehaviour"))
        self.s.setValue("/Projections/defaultBehaviour", "useProject")

    'enable old settings again'

    def disableUseOfGlobalCrs(self):
        self.s.setValue("/Projections/defaultBehaviour", self.oldValidation)

    def get_roads(self):
        # print self.dlg.lblStartPoint.text()+";"+self.dlg.lblEndPoint.text()

        self.emission_calculator.coordinates = self.dlg.lblStartPoint.text() + ";" + self.dlg.lblEndPoint.text()
        self.emission_calculator.get_json_from_url()

        paths = self.emission_calculator.paths

        for j in range(len(paths)):
            ## create an empty memory layer
            vl = QgsVectorLayer("LineString", "Route" + str(j + 1), "memory")
            ## define and add a field ID to memory layer "Route"
            provider = vl.dataProvider()
            provider.addAttributes([QgsField("ID", QVariant.Int)])
            ## create a new feature for the layer "Route"
            ft = QgsFeature()
            ## set the value 1 to the new field "ID"
            ft.setAttributes([1])
            line_points = []
            for i in range(len(paths[j])):
                # if j == 0:
                if (i + 1) < len(paths[j]):
                    line_points.append(QgsPoint(paths[j][i][0], paths[j][i][1]))
            ## set the geometry defined from the point X: 50, Y: 100
            ft.setGeometry(QgsGeometry.fromPolyline(line_points))
            ## finally insert the feature
            provider.addFeatures([ft])

            ## set color
            symbols = vl.rendererV2().symbols()
            sym = symbols[0]
            # sym.setColor(QColor.fromRgb(255, 0, 0))
            sym.setWidth(2)

            ## add layer to the registry and over the map canvas
            QgsMapLayerRegistry.instance().addMapLayer(vl)

    def get_emissions(self):

        self.emission_calculator.calculate_nox = self.dlg.checkBoxNox.isChecked()
        self.emission_calculator.calculate_co = self.dlg.checkBoxCo.isChecked()
        self.emission_calculator.calculate_hc = self.dlg.checkBoxHc.isChecked()
        self.emission_calculator.calculate_pm = self.dlg.checkBoxPm.isChecked()
        self.emission_calculator.calculate_fc = self.dlg.checkBoxFc.isChecked()

        self.emission_calculator.cumulative = self.dlg.checkBoxCumulative.isChecked()

        self.emission_calculator.calculate_emissions()


    def run(self):
        """Run method that performs all the real work"""

        types = self.emission_calculator.emissionJson.get_types()
        self.dlg.cmbBoxType.addItems(types)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            self.canvas.unsetMapTool(self.mapTool)
            pass
