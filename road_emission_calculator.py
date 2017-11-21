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
from PyQt4.QtGui import QAction, QIcon, QColor, QWidget, QListWidget, QListWidgetItem
from qgis.core import QGis, QgsCoordinateTransform, QgsRectangle, QgsPoint, QgsGeometry, QgsCoordinateReferenceSystem
from qgis.gui import QgsRubberBand
from Overlay import Overlay

from qgis.core import QgsVectorLayer, QgsField, QgsMapLayerRegistry, QgsFeature, QgsGeometry

from copyLatLonTool import CopyLatLonTool
from settings import SettingsWidget
import sys
import pip
import os.path
import matplotlib.pyplot as plt
from thewidgetitem import TheWidgetItem

plugin_dir = os.path.dirname(__file__)
emissionCalculator_dir = os.path.join(plugin_dir, 'emission')
try:
    import emission
    from RoadEmissionPlannerThread import RoadEmissionPlannerThread
except:
    pip.main(['install', '--target=%s' % emissionCalculator_dir, 'emission'])
    if emissionCalculator_dir not in sys.path:
        sys.path.append(emissionCalculator_dir)
    import emission
    from RoadEmissionPlannerThread import RoadEmissionPlannerThread

# from PyQt4.QtCore import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from road_emission_calculator_dialog import RoadEmissionCalculatorDialog



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
        self.planner = emission
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
        self.categories = []
        self.selected_category = []
        self.selected_fuel = []
        self.selected_segment = []
        self.selected_euro_std = []
        self.selected_mode = []
        # self.fuels = []
        # self.segments = []
        self.menu = self.tr(u'&Road Emission Calculator')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadEmissionCalculator')
        self.toolbar.setObjectName(u'RoadEmissionCalculator')

        # matplolib generate lines in color sequence: blue, green, red, cyan, magenta, yellow, black, white
        # same color schema will be use for proposal roads
        self.color_list = {0:[0, 0, 255], 1:[0, 255, 0], 2:[255, 0, 0], 3:[0, 255, 255],
                           4:[255, 0, 255], 5:[255, 255, 0], 6:[0, 0, 0], 7:[255, 255, 255]}

        self.selected_route_id = -1

        self.dlg.btnAddStartPoint.clicked.connect(self.add_start_point)
        self.dlg.btnAddEndPoint.clicked.connect(self.add_end_point)
        self.dlg.btnRemoveStartPoint.clicked.connect(self.remove_start_point)
        self.dlg.btnRemoveEndPoint.clicked.connect(self.remove_end_point)

        self.dlg.widgetLoading.setShown(False)
        self.overlay = Overlay(self.dlg.widgetLoading)
        self.overlay.resize(700,445)
        self.overlay.hide()

        self.roadEmissionPlanner = RoadEmissionPlannerThread()
        self.roadEmissionPlanner.plannerFinished.connect(self.on_road_emission_planner_finished)

        self.dlg.btnGetEmissions.clicked.connect(self.on_road_emission_planner_start)
        self.dlg.cmbBoxVehicleType.currentIndexChanged.connect(self.set_fuels)
        self.dlg.cmbBoxFuelType.currentIndexChanged.connect(self.set_segments)
        self.dlg.cmbBoxSubsegment.currentIndexChanged.connect(self.set_euro_std)
        self.dlg.cmbBoxEuroStd.currentIndexChanged.connect(self.set_mode)
        self.dlg.cmbBoxMode.currentIndexChanged.connect(self.set_pollutants)
        self.dlg.listWidget.itemClicked.connect(self.select_route)
        self.dlg.cmbBoxSortBy.currentIndexChanged.connect(self.sort_routes_by)

        self.dlg.checkBoxShowInGraph.clicked.connect(self.activate_cumulative)

        # init with default values
        self.dlg.lineEditLength.setText('12')
        self.dlg.lineEditHeight.setText('4.4')

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
        self.dlg.btnAddStartPoint.setIcon(QIcon(os.path.dirname(__file__) + "/images/pencil_64.png"))
        self.dlg.btnAddEndPoint.setIcon(QIcon(os.path.dirname(__file__) + "/images/pencil_64.png"))
        self.dlg.btnRemoveStartPoint.setIcon(QIcon(os.path.dirname(__file__) + "/images/trash_64.png"))
        self.dlg.btnRemoveEndPoint.setIcon(QIcon(os.path.dirname(__file__) + "/images/trash_64.png"))
        # self.dlg.textEditSummary.setReadOnly(True)
        self.dlg.lineEditStartX.setReadOnly(True)
        self.dlg.lineEditStartY.setReadOnly(True)
        self.dlg.lineEditEndX.setReadOnly(True)
        self.dlg.lineEditEndY.setReadOnly(True)
        self.activate_cumulative()

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

    def set_vehicle_subsegment(self):
        self.dlg.cmbBoxSubsegment.clear()
        if self.dlg.cmbBoxVehicleType.currentText() == 'CAR':
            segments = emission.vehicles.Car.type
            self.dlg.cmbBoxSubsegment.addItems([list(d)[0] for d in segments])

    def set_vehicle_euro_std(self):

        self.dlg.cmbBoxEuroStd.clear()
        if self.dlg.cmbBoxVehicleType.currentText() == 'CAR':
            segments = emission.vehicles.Car.type
            self.dlg.cmbBoxEuroStd.addItems(list(filter(lambda y: y != None, [x.get(self.dlg.cmbBoxSubsegment.currentText()) for x in segments]))[0])

    def activate_cumulative(self):
        self.dlg.checkBoxCumulative.setEnabled(self.dlg.checkBoxShowInGraph.isChecked())

    def set_new_point(self, point_name):
        self.mapTool.point_name = point_name
        self.canvas.setMapTool(self.mapTool)

    def add_start_point(self):
        # only one start point can be in canvas/legend
        self.remove_start_point()
        self.set_new_point("Start_point")

    def add_end_point(self):
        # only one end point can be in canvas/legend
        self.remove_end_point()
        self.set_new_point("End_point")

    @staticmethod
    def remove_layer(id_name):
        lrs = QgsMapLayerRegistry.instance().mapLayers()
        for i in range(len(lrs.keys())):
            if id_name in lrs.keys()[i]:
                QgsMapLayerRegistry.instance().removeMapLayer(lrs.keys()[i])

    def remove_start_point(self):
        self.dlg.lineEditStartX.setText("")
        self.dlg.lineEditStartY.setText("")
        self.remove_layer("Start_point")

    def remove_end_point(self):
        self.dlg.lineEditEndX.setText("")
        self.dlg.lineEditEndY.setText("")
        self.remove_layer("End_point")

    'set new Layers to use the Project-CRS'

    def enableUseOfGlobalCrs(self):
        self.s = QSettings()
        self.oldValidation = str(self.s.value("/Projections/defaultBehaviour"))
        self.s.setValue("/Projections/defaultBehaviour", "useProject")

    'enable old settings again'

    def disableUseOfGlobalCrs(self):
        self.s.setValue("/Projections/defaultBehaviour", self.oldValidation)

    def on_road_emission_planner_start(self):
        self.dlg.widgetLoading.setShown(True)
        start = [float(self.dlg.lineEditStartX.text()), float(self.dlg.lineEditStartY.text())]
        stop = [float(self.dlg.lineEditEndX.text()), float(self.dlg.lineEditEndY.text())]
        fuel_diesel = emission.vehicles.FuelTypes.DIESEL

        # print ("Fuel diesel {}". format(fuel_diesel))
        # print ("Selected fuel {}").format(self.dlg.cmbBoxFuelType.currentText())
        vehicle = emission.vehicles.Vehicle

        type_category = emission.vehicles.Vehicle.get_type_for_category(self.dlg.cmbBoxVehicleType.currentText())
        if type_category == emission.vehicles.VehicleTypes.CAR:
            vehicle = emission.vehicles.Car()
        if type_category == emission.vehicles.VehicleTypes.BUS:
            vehicle = emission.vehicles.Bus()
            vehicle.length = self.dlg.lineEditLength.text()
            vehicle.height = self.dlg.lineEditHeight.text()
            vehicle.load = self.dlg.cmbBoxLoad.currentText()
        if type_category == emission.vehicles.VehicleTypes.TRUCK:
            vehicle = emission.vehicles.Truck()
            vehicle.length = self.dlg.lineEditLength.text()
            vehicle.height = self.dlg.lineEditHeight.text()
            vehicle.load = self.dlg.cmbBoxLoad.currentText()
        if type_category == emission.vehicles.VehicleTypes.LCATEGORY:
            vehicle = emission.vehicles.LCategory()
        if type_category == emission.vehicles.VehicleTypes.VAN:
            vehicle = emission.vehicles.Van()

        vehicle.fuel_type = self.dlg.cmbBoxFuelType.currentText()
        vehicle.segment = self.dlg.cmbBoxSubsegment.currentText()
        vehicle.euro_std = self.dlg.cmbBoxEuroStd.currentText()
        vehicle.mode = self.dlg.cmbBoxMode.currentText()

        self.planner = emission.Planner(start, stop, vehicle)

        if self.dlg.checkBoxCo.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.CO)
        if self.dlg.checkBoxNox.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.NOx)
        if self.dlg.checkBoxVoc.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.VOC)
        if self.dlg.checkBoxEc.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.EC)
        if self.dlg.checkBoxPmExhaust.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.PM_EXHAUST)
        if self.dlg.checkBoxCh4.isEnabled():
            self.planner.add_pollutant(emission.PollutantTypes.CH4)

        self.overlay.show()
        self.roadEmissionPlanner.set_planner(self.planner)
        self.roadEmissionPlanner.start()

    def on_road_emission_planner_finished(self):
        self.overlay.hide()
        self.remove_layer("Route")
        self.road_emission_planner_finished()
        self.dlg.widgetLoading.setShown(False)

    def road_emission_planner_finished(self):
        # self.dlg.textEditSummary.clear()
        self.dlg.cmbBoxSortBy.clear()
        # self.dlg.listWidget.clear()
        routes = self.planner.routes
        pollutant_types = self.planner.pollutants.keys()
        if len(routes) > 0:
            self.dlg.cmbBoxSortBy.addItem("Distance")
            self.dlg.cmbBoxSortBy.addItem("Time")
            self.dlg.cmbBoxSortBy.addItems(pollutant_types)
            # self.dlg.cmbBoxSortBy.append
            # self.sort_routes_by()
            for route in routes:
                # self.dlg.textEditSummary.append("Route" + str(idx + 1) + ":")

                # self.dlg.textEditSummary.append(
                #     "Length: " + str(distance) + " km, driving time: " + str(hours) + " hours and " + str(
                #         minutes) + " minutes.")
                # self.dlg.textEditSummary.append("")
                # for pt in pollutant_types:
                #     self.dlg.textEditSummary.append(("    {} = {}".format(pt, route.total_emission(pt))))
                #
                # self.dlg.textEditSummary.append("")
                # self.dlg.textEditSummary.append("")

                # distance = route.distance / 1000
                # hours, minutes = divmod(route.minutes, 60)
                # hours = int(hours)
                # minutes = int(minutes)
                #
                # myQCustomQWidget = TheWidgetItem()
                # myQCustomQWidget.set_route_name("Route" + str(idx + 1))
                # myQCustomQWidget.set_distance_time(str(distance) + " km", str(hours) + " hours and " + str(
                #         minutes) + " minutes.")
                # myQCustomQWidget.hide_all_lbl_pollutants()
                # for idxPlt, pt in enumerate(pollutant_types):
                #     myQCustomQWidget.set_pollutants(idxPlt, pt, round(route.total_emission(pt),2))
                # myQListWidgetItem = QListWidgetItem(self.dlg.listWidget)
                # myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
                # self.dlg.listWidget.addItem(myQListWidgetItem)
                # self.dlg.listWidget.setItemWidget(myQListWidgetItem, myQCustomQWidget)


                ## create an empty memory layer
                vl = QgsVectorLayer("LineString", "Route" + str(route.id + 1), "memory")
                ## define and add a field ID to memory layer "Route"
                provider = vl.dataProvider()
                provider.addAttributes([QgsField("ID", QVariant.Int)])
                ## create a new feature for the layer "Route"
                ft = QgsFeature()
                ## set the value 1 to the new field "ID"
                ft.setAttributes([1])
                line_points = []
                for i in range(len(route.path)):
                    # if j == 0:
                    if (i + 1) < len(route.path):
                        line_points.append(QgsPoint(route.path[i][0], route.path[i][1]))
                ## set the geometry defined from the point X: 50, Y: 100
                ft.setGeometry(QgsGeometry.fromPolyline(line_points))
                ## finally insert the feature
                provider.addFeatures([ft])

                ## set color
                symbols = vl.rendererV2().symbols()
                sym = symbols[0]
                # if idx < (len(self.color_list) - 1):
                print ("Route id: {}".format(route.id))
                print ("Route color: {}".format(self.color_list[route.id]))
                # print ("Route color: {}".format(self.color_list[route.id]))

                color = self.color_list[route.id]
                print ("Color: {}.{}.{}".format(color[0], color[1], color[2]))
                sym.setColor(QColor.fromRgb(color[0], color[1], color[2]))
                sym.setWidth(2)

                ## add layer to the registry and over the map canvas
                QgsMapLayerRegistry.instance().addMapLayer(vl)

            self.sort_routes_by()

            ## Show pollutant results in graph
            if self.dlg.checkBoxShowInGraph.isChecked():
                fig = plt.figure()
                figs = []

                grafIdx = 0
                active_graphs = 0

                for pt in pollutant_types:
                    if self.pollutant_checked(pt):
                        active_graphs += 1

                for pt in pollutant_types:
                    if self.pollutant_checked(pt):
                        num_plots = 100 * active_graphs + 10 + grafIdx + 1
                        ax = fig.add_subplot(num_plots)
                        ax.set_title(pt)
                        ax.set_ylim(0, max(max(x.pollutants[pt] for x in routes)) + 0.2)
                        figs.append(ax)
                        grafIdx += 1

                for r in routes:
                    grafIdx = 0
                    for pt in pollutant_types:
                        if self.pollutant_checked(pt):
                            ax = figs[grafIdx]
                            ax.plot(r.distances[0], r.pollutants[pt])
                            grafIdx += 1

                # print("Fig length: {}".format(len(figs)))

                ax = figs[-1]
                labels = ["Route " + str(i + 1) for i in range(len(routes))]
                pos = (len(figs) / 10.0) * (-1)
                ax.legend(labels, loc=(0, pos), ncol=len(routes))
                plt.show()


        else:
            # if "Fail" in self.emission_calculator.emission_summary:
            #     self.dlg.textEditSummary.append(self.emission_calculator.emission_summary["Fail"])
            #     self.dlg.textEditSummary.append("")
            # # self.dlg.textEditSummary.append("Sorry, for defined parameters no road is available.")
            # # self.dlg.textEditSummary.append("")
            pass

    def pollutant_checked(self, plt):
        if plt == emission.PollutantTypes.CO:
            return self.dlg.checkBoxCo.isEnabled() and self.dlg.checkBoxCo.isChecked()
        if plt == emission.PollutantTypes.NOx:
            return self.dlg.checkBoxNox.isEnabled() and self.dlg.checkBoxNox.isChecked()
        if plt == emission.PollutantTypes.VOC:
            return self.dlg.checkBoxVoc.isEnabled() and self.dlg.checkBoxVoc.isChecked()
        if plt == emission.PollutantTypes.EC:
            return self.dlg.checkBoxEc.isEnabled() and self.dlg.checkBoxEc.isChecked()
        if plt == emission.PollutantTypes.PM_EXHAUST:
            return self.dlg.checkBoxPmExhaust.isEnabled() and self.dlg.checkBoxPmExhaust.isChecked()
        if plt == emission.PollutantTypes.CH4:
            return self.dlg.checkBoxCh4.isEnabled() and self.dlg.checkBoxCh4.isChecked()

    def select_route(self):
        if self.dlg.listWidget.currentItem():
            route_item = self.dlg.listWidget.itemWidget(self.dlg.listWidget.currentItem())
            if (route_item.route_id == self.selected_route_id):
                self.clear_selection()
                return
            self.remove_layer("Selected")
            self.selected_route_id = route_item.route_id
            route = self.planner.routes[route_item.route_id]
            ## create an empty memory layer
            vl = QgsVectorLayer("LineString", "Selected route" + str(route.id + 1), "memory")
            ## define and add a field ID to memory layer "Route"
            provider = vl.dataProvider()
            provider.addAttributes([QgsField("ID", QVariant.Int)])
            ## create a new feature for the layer "Route"
            ft = QgsFeature()
            ## set the value 1 to the new field "ID"
            ft.setAttributes([1])
            line_points = []

            for i in range(len(route.path)):
                # if j == 0:
                if (i + 1) < len(route.path):
                    line_points.append(QgsPoint(route.path[i][0], route.path[i][1]))
            ## set the geometry defined from the point X: 50, Y: 100
            ft.setGeometry(QgsGeometry.fromPolyline(line_points))
            ## finally insert the feature
            provider.addFeatures([ft])

            ## set color
            symbols = vl.rendererV2().symbols()
            sym = symbols[0]
            # if selected_idx < (len(self.color_list) - 1):
            color = self.color_list[route.id]
            sym.setColor(QColor.fromRgb(color[0], color[1], color[2]))
            sym.setWidth(4)

            ## add layer to the registry and over the map canvas
            QgsMapLayerRegistry.instance().addMapLayer(vl)

    def clear_selection(self):
        self.remove_layer("Selected")
        self.dlg.listWidget.clearSelection()
        self.selected_route_id = -1

    def sort_routes_by(self):
        # pass
        routes = self.planner.routes
        print ("Sort by items count: {} and current name: {}".format(self.dlg.cmbBoxSortBy.count(), self.dlg.cmbBoxSortBy.currentText()))
        self.dlg.listWidget.clear()
        self.clear_selection()
        if len(routes) > 0 and self.dlg.cmbBoxSortBy.count() > 0:
            print ("Current text: {}".format(self.dlg.cmbBoxSortBy.currentText()))
            if self.dlg.cmbBoxSortBy.currentText() == "Distance":
                sorted_after_distance = sorted(routes, key=lambda x: x.distance)
                for r in sorted_after_distance:
                    self.add_route_item_to_list_widget(r)
            elif self.dlg.cmbBoxSortBy.currentText() == "Time":
                routes.sort()
                for r in routes:
                    self.add_route_item_to_list_widget(r)
            else:
                sorted_after_pollutant = sorted(routes, key=lambda x: x.total_emission(self.dlg.cmbBoxSortBy.currentText()))
                for r in sorted_after_pollutant:
                    self.add_route_item_to_list_widget(r)

    def add_route_item_to_list_widget(self, route):
        pollutant_types = self.planner.pollutants.keys()
        distance = route.distance / 1000
        hours, minutes = divmod(route.minutes, 60)
        hours = int(hours)
        minutes = int(minutes)

        myQCustomQWidget = TheWidgetItem()
        myQCustomQWidget.set_route_name("Route" + str(route.id + 1))
        myQCustomQWidget.set_route_id(route.id)
        myQCustomQWidget.set_distance_time(str(distance) + " km", str(hours) + " hours and " + str(
            minutes) + " minutes.")
        myQCustomQWidget.hide_all_lbl_pollutants()
        for idxPlt, pt in enumerate(pollutant_types):
            myQCustomQWidget.set_pollutants(idxPlt, pt, round(route.total_emission(pt), 2))
        myQListWidgetItem = QListWidgetItem(self.dlg.listWidget)
        myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
        self.dlg.listWidget.addItem(myQListWidgetItem)
        self.dlg.listWidget.setItemWidget(myQListWidgetItem, myQCustomQWidget)

    def set_categories(self):
        self.categories = emission.session.query(emission.models.Category).all()
        list_categories = list(map(lambda category: category.name, self.categories))
        list_categories.sort()
        self.dlg.cmbBoxVehicleType.addItems(list_categories)
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())

    def set_fuels(self):
        self.dlg.cmbBoxFuelType.clear()
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())
        if len(self.selected_category) > 0:
            filtred_fuels = emission.models.filter_parms(cat=self.selected_category[0])
            self.fuels = set(x.fuel for x in filtred_fuels)
            list_fuels = list(map(lambda fuel: fuel.name, self.fuels))
            list_fuels.sort()
            self.dlg.cmbBoxFuelType.addItems(list_fuels)

    def set_segments(self):
        self.dlg.cmbBoxSubsegment.clear()
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())
        self.selected_fuel = self.get_object_from_array_by_name(self.fuels, self.dlg.cmbBoxFuelType.currentText())
        if len(self.selected_category) > 0 and len(self.selected_fuel) > 0:
            filtred_segments = emission.models.filter_parms(cat=self.selected_category[0], fuel=self.selected_fuel[0])
            self.segments = set(x.segment for x in filtred_segments)
            list_segments = list(map(lambda segment: str(segment.name), self.segments))
            list_segments.sort()
            self.dlg.cmbBoxSubsegment.addItems(list_segments)
            self.selected_segment = self.get_object_from_array_by_name(self.segments,
                                                                       self.dlg.cmbBoxSubsegment.currentText())

    def set_euro_std(self):
        self.dlg.cmbBoxEuroStd.clear()
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())
        self.selected_fuel = self.get_object_from_array_by_name(self.fuels, self.dlg.cmbBoxFuelType.currentText())
        self.selected_segment = self.get_object_from_array_by_name(self.segments, self.dlg.cmbBoxSubsegment.currentText())
        if len(self.selected_category) > 0 and len(self.selected_fuel) > 0 and len(self.selected_segment) > 0:
            filtred_euro_stds = emission.models.filter_parms(cat=self.selected_category[0], fuel=self.selected_fuel[0],segment=self.selected_segment[0])
            self.euro_stds = set(x.eurostd for x in filtred_euro_stds)
            list_euro_stds = list(map(lambda eurostd: eurostd.name, self.euro_stds))
            list_euro_stds.sort()
            self.dlg.cmbBoxEuroStd.addItems(list_euro_stds)

    def set_mode(self):
        self.dlg.cmbBoxMode.clear()
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())
        self.selected_fuel = self.get_object_from_array_by_name(self.fuels, self.dlg.cmbBoxFuelType.currentText())
        self.selected_segment = self.get_object_from_array_by_name(self.segments,
                                                                   self.dlg.cmbBoxSubsegment.currentText())
        self.selected_euro_std = self.get_object_from_array_by_name(self.euro_stds, self.dlg.cmbBoxEuroStd.currentText())
        if len(self.selected_category) > 0 and len(self.selected_fuel) > 0 and len(self.selected_segment) > 0 and len(self.selected_euro_std) > 0:
            filtred_modes = emission.models.filter_parms(cat=self.selected_category[0], fuel=self.selected_fuel[0], segment=self.selected_segment[0],
                                                             eurostd=self.selected_euro_std[0])
            self.modes = set(x.mode for x in filtred_modes)
            list_modes = list(map(lambda mode: mode.name, self.modes))
            list_modes.sort()
            self.dlg.cmbBoxMode.addItems(list_modes)

    def set_pollutants(self):
        self.disable_all_pollutants()
        self.selected_category = self.get_object_from_array_by_name(self.categories,
                                                                    self.dlg.cmbBoxVehicleType.currentText())
        self.selected_fuel = self.get_object_from_array_by_name(self.fuels, self.dlg.cmbBoxFuelType.currentText())
        self.selected_segment = self.get_object_from_array_by_name(self.segments,
                                                                   self.dlg.cmbBoxSubsegment.currentText())
        self.selected_euro_std = self.get_object_from_array_by_name(self.euro_stds,
                                                                    self.dlg.cmbBoxEuroStd.currentText())
        self.selected_mode = self.get_object_from_array_by_name(self.modes, self.dlg.cmbBoxMode.currentText())
        if len(self.selected_category) > 0 and len(self.selected_fuel) > 0 and len(self.selected_segment) > 0 and len(self.selected_euro_std) > 0 and len(self.selected_mode):
            filtred_pollutants = emission.models.filter_parms(cat=self.selected_category[0], fuel=self.selected_fuel[0],
                                                              segment=self.selected_segment[0],
                                                         eurostd=self.selected_euro_std[0], mode=self.selected_mode[0])
            pollutants = list(map(lambda pollutant: pollutant.name, set(x.pollutant for x in filtred_pollutants)))
            self.enable_pollutants(pollutants)

    def enable_pollutants(self, pollutants):
        if emission.PollutantTypes.CO in pollutants:
            self.dlg.checkBoxCo.setEnabled(True)
        if emission.PollutantTypes.NOx in pollutants:
            self.dlg.checkBoxNox.setEnabled(True)
        if emission.PollutantTypes.VOC in pollutants:
            self.dlg.checkBoxVoc.setEnabled(True)
        if emission.PollutantTypes.EC in pollutants:
            self.dlg.checkBoxEc.setEnabled(True)
        if emission.PollutantTypes.PM_EXHAUST in pollutants:
            self.dlg.checkBoxPmExhaust.setEnabled(True)
        if emission.PollutantTypes.CH4 in pollutants:
            self.dlg.checkBoxCh4.setEnabled(True)

    def disable_all_pollutants(self):
        self.dlg.checkBoxCo.setEnabled(False)
        self.dlg.checkBoxNox.setEnabled(False)
        self.dlg.checkBoxVoc.setEnabled(False)
        self.dlg.checkBoxEc.setEnabled(False)
        self.dlg.checkBoxPmExhaust.setEnabled(False)
        self.dlg.checkBoxCh4.setEnabled(False)


    def get_object_from_array_by_name(self, array, name):
        if len(array) == 0:
            return []
        else:
            return list(filter(lambda obj: obj.name == name, array))


    def run(self):
        """Run method that performs all the real work"""
        # set input parameters to default when the dialog has been closed and open again
        self.dlg.cmbBoxVehicleType.clear()
        self.dlg.cmbBoxFuelType.clear()
        self.dlg.cmbBoxSubsegment.clear()
        self.dlg.cmbBoxEuroStd.clear()
        self.dlg.cmbBoxMode.clear()

        self.set_categories()
        self.set_fuels()
        self.set_segments()
        self.set_euro_std()
        self.set_mode()
        self.set_pollutants()

        self.dlg.cmbBoxLoad.clear()
        self.dlg.cmbBoxLoad.addItems(["0", "50", "100"])
        self.dlg.lineEditStartX.setText("")
        self.dlg.lineEditStartY.setText("")
        self.dlg.lineEditEndX.setText("")
        self.dlg.lineEditEndY.setText("")
        # self.dlg.textEditSummary.clear()

        # Create QCustomQWidget
        # self.myQCustomQWidget = TheWidgetItem()

        # Create QListWidgetItem
        # myQCustomQWidget = TheWidgetItem()
        # myQCustomQWidget.set_route_name("Route1")
        # myQCustomQWidget.set_distance_time("35 km", "0 hours 20 minutes")
        # myQListWidgetItem = QListWidgetItem(self.dlg.listWidget)
        # myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
        # self.dlg.listWidget.addItem(myQListWidgetItem)
        # self.dlg.listWidget.setItemWidget(myQListWidgetItem, myQCustomQWidget)
        #
        # myQCustomQWidget = TheWidgetItem()
        # myQCustomQWidget.set_route_name("Route2")
        # myQCustomQWidget.set_distance_time("45 km", "0 hours 49 minutes")
        # myQListWidgetItem = QListWidgetItem(self.dlg.listWidget)
        # myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
        # self.dlg.listWidget.addItem(myQListWidgetItem)
        # self.dlg.listWidget.setItemWidget(myQListWidgetItem, myQCustomQWidget)


        # for index, name, icon in [
        #     ('No.1', 'Meyoko', 'icon.png'),
        #     ('No.2', 'Nyaruko', 'icon.png'),
        #     ('No.3', 'Louise', 'icon.png')]:
        #     # Create QCustomQWidget
        #     myQCustomQWidget = TheWidgetItem()
        #     myQCustomQWidget.setTextUp(index)
        #     myQCustomQWidget.setTextDown(name)
        #     myQCustomQWidget.setIcon(icon)
        #     # Create QListWidgetItem
        #     myQListWidgetItem = QListWidgetItem(self.dlg.listWidget)
        #     # Set size hint
        #     myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
        #     # Add QListWidgetItem into QListWidget
        #     self.dlg.listWidget.addItem(myQListWidgetItem)
        #     self.dlg.listWidget.setItemWidget(myQListWidgetItem, myQCustomQWidget)


        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            self.canvas.unsetMapTool(self.mapTool)
        else:
            self.dlg.widgetLoading.setShown(False)
            # pass