import os

from PyQt4 import uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

from overlay_ps_layer import OverlayPSLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'overlay_ps_dialog_base.ui'))


class OverlayPSTool(QgsMapTool):

    def __init__(self, iface):
        QgsMapTool.__init__(self, iface.mapCanvas())

        self.iface = iface
        self.picking = False
        self.layerTreeView = iface.layerTreeView()
        self.widget = OverlayPSWidget(self.iface)
        self.widget.setVisible(False)

        self.widget.requestPickCenter.connect(self.setPicking)
        self.widget.close.connect(self.close)

        self.actionEditLayer = QAction(self.tr("Edit"), self)
        self.actionEditLayer.setIcon(QIcon(
            ":/images/themes/default/mIconEditable.png"))
        self.actionEditLayer.triggered.connect(self.editCurrentLayer)
        self.layerTreeView.menuProvider().addLegendLayerAction(
            self.actionEditLayer, "", "edit_overlayps_layer",
            QgsMapLayer.PluginLayer, False)

        QgsMapLayerRegistry.instance().layerWasAdded.connect(
            self.addLayerTreeMenuAction)
        QgsMapLayerRegistry.instance().layerWillBeRemoved.connect(
            self.removeLayerTreeMenuAction)

    def activate(self):
        if isinstance(self.iface.mapCanvas().currentLayer(), OverlayPSLayer):
            self.widget.setLayer(self.iface.mapCanvas().currentLayer())
        else:
            found = False
            for layer in QgsMapLayerRegistry.instance().mapLayers().values():
                if isinstance(layer, OverlayPSLayer):
                    self.widget.setLayer(layer)
                    found = True
                    break
            if not found:
                self.widget.createLayer(self.tr("OpenlayPS"))
        self.widget.setVisible(True)
        # QgsMapTool.activate()

    def deactivate(self):
        self.widget.setVisible(False)
        self.picking = False
        self.setCursor(Qt.ArrowCursor)
        # QgsMapTool.deactivate()

    def canvasReleaseEvent(self, event):
        if self.picking:
            self.widget.centerPicked(self.toMapCoordinates(event.pos()))
            self.setPicking(False)
        elif event.button() == Qt.RightButton:
            self.iface.mapCanvas().unsetMapTool(self)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.picking:
                self.setPicking(False)
            else:
                self.iface.mapCanvas().unsetMapTool(self)

    def setPicking(self, picking=True):
        self.picking = picking
        self.setCursor(Qt.CrossCursor if picking else Qt.ArrowCursor)

    def close(self):
        self.iface.mapCanvas().unsetMapTool(self)

    def addLayerTreeMenuAction(self, mapLayer):
        if isinstance(mapLayer, OverlayPSLayer):
            self.layerTreeView.menuProvider().addLegendLayerActionForLayer(
                "edit_overlayps_layer", mapLayer)

    def removeLayerTreeMenuAction(self, mapLayerId):
        mapLayer = QgsMapLayerRegistry.instance().mapLayer(mapLayerId)
        if isinstance(mapLayer, OverlayPSLayer):
            self.layerTreeView.menuProvider().removeLegendLayerActionsForLayer(
                mapLayer)

    def editCurrentLayer(self):
        if isinstance(self.iface.mapCanvas().currentLayer(), OverlayPSLayer):
            self.iface.mapCanvas().setMapTool(self)

    def tr(self, message):
        return QCoreApplication.translate('OverlayPS', message)


class OverlayPSWidget(QgsBottomBar, FORM_CLASS):

    requestPickCenter = pyqtSignal()
    close = pyqtSignal()

    def __init__(self, iface):
        QgsBottomBar.__init__(self, iface.mapCanvas())

        self.iface = iface
        self.layerTreeView = iface.layerTreeView()
        self.currentLayer = None

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(10)

        base = QWidget()
        self.setupUi(base)
        self.layout().addWidget(base)

        closeButton = QPushButton()
        closeButton.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        closeButton.setIcon(QIcon(":/images/themes/default/mIconClose.png"))
        closeButton.setToolTip(self.tr("Close"))
        closeButton.clicked.connect(self.close)
        self.layout().addWidget(closeButton)
        self.layout().setAlignment(closeButton, Qt.AlignTop)

        self.toolButtonAddLayer.clicked.connect(self.createLayer)
        self.inputCenter.coordinateChanged.connect(self.updateLayer)
        self.toolButtonPickCenter.clicked.connect(self.requestPickCenter)
        self.spinBoxAzimut.valueChanged.connect(self.updateLayer)
        self.spinBoxLineWidth.valueChanged.connect(self.updateLineWidth)
        self.toolButtonColor.colorChanged.connect(self.updateColor)

        QgsMapLayerRegistry.instance().layersAdded.connect(
            self.repopulateLayers)
        QgsMapLayerRegistry.instance().layersRemoved.connect(
            self.repopulateLayers)
        self.iface.mapCanvas().currentLayerChanged.connect(
            self.updateSelectedLayer)

        self.repopulateLayers()
        self.comboBoxLayer.currentIndexChanged.connect(
            self.currentLayerChanged)

    def centerPicked(self, pos):
        self.inputCenter.setCoordinate(
            pos, self.iface.mapCanvas().mapSettings().destinationCrs())

    def createLayer(self, layerName):
        if not layerName:
            layerName = QInputDialog.getText(
                self, self.tr("Layer Name"),
                self.tr("Enter name of new layer:"))[0]
        if layerName:
            OverlayPsLayer = OverlayPSLayer(layerName)
            OverlayPsLayer.setup(
                self.iface.mapCanvas().extent().center(),
                self.iface.mapCanvas().mapSettings().destinationCrs(),
                22.5)
            QgsMapLayerRegistry.instance().addMapLayer(OverlayPSLayer)
            self.setLayer(OverlayPSLayer)

    def setLayer(self, layer):
        if layer == self.currentLayer:
            return
        self.currentLayer = layer if isinstance(layer, OverlayPSLayer) else False
        if not self.currentLayer:
            self.widgetLayerSetup.setEnabled(False)
            return
        self.comboBoxLayer.blockSignals(True)
        self.comboBoxLayer.setCurrentIndex(self.comboBoxLayer.findData(
            self.currentLayer.id()))
        self.comboBoxLayer.blockSignals(False)
        self.layerTreeView.setLayerVisible(self.currentLayer, True)
        self.iface.mapCanvas().setCurrentLayer(self.currentLayer)

        self.inputCenter.blockSignals(True)
        self.inputCenter.setCoordinate(self.currentLayer.getCenter(),
                                       self.currentLayer.crs())
        self.inputCenter.blockSignals(False)
        self.spinBoxAzimut.blockSignals(True)
        self.spinBoxAzimut.setValue(self.currentLayer.getAzimut())
        self.spinBoxAzimut.blockSignals(False)
        self.spinBoxLineWidth.blockSignals(True)
        self.spinBoxLineWidth.setValue(self.currentLayer.getLineWidth())
        self.spinBoxLineWidth.blockSignals(False)
        self.toolButtonColor.blockSignals(True)
        self.toolButtonColor.setColor(self.currentLayer.getColor())
        self.toolButtonColor.blockSignals(False)
        self.widgetLayerSetup.setEnabled(True)

    def updateLayer(self):
        if not self.currentLayer or self.inputCenter.isEmpty():
            return
        center = self.inputCenter.getCoordinate()
        crs = self.inputCenter.getCrs()
        azimut = self.spinBoxAzimut.value()
        self.currentLayer.setup(center, crs, azimut)
        self.currentLayer.triggerRepaint()

    def updateColor(self, color):
        if self.currentLayer:
            self.currentLayer.setColor(color)
            self.currentLayer.triggerRepaint()

    def updateLineWidth(self, width):
        if self.currentLayer:
            self.currentLayer.setLineWidth(width)
            self.currentLayer.triggerRepaint()

    def repopulateLayers(self):
        if self.comboBoxLayer.signalsBlocked():
            return
        self.comboBoxLayer.blockSignals(True)
        self.comboBoxLayer.clear()
        idx = 0
        current = 0
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if isinstance(layer, OverlayPSLayer):
                layer.layerNameChanged.connect(self.repopulateLayers)
                self.comboBoxLayer.addItem(layer.name(), layer.id())
                if self.iface.mapCanvas().currentLayer() == layer:
                    current = idx
                idx += 1
        self.comboBoxLayer.setCurrentIndex(-1)
        self.comboBoxLayer.blockSignals(False)
        self.comboBoxLayer.setCurrentIndex(current)
        self.widgetLayerSetup.setEnabled(self.comboBoxLayer.count() > 0)

    def currentLayerChanged(self, cur):
        layer = QgsMapLayerRegistry.instance().mapLayer(
            self.comboBoxLayer.itemData(cur))
        if isinstance(layer, OverlayPSLayer):
            self.setLayer(layer)
        else:
            self.widgetLayerSetup.setEnabled(False)

    def updateSelectedLayer(self, layer):
        if isinstance(layer, OverlayPSLayer):
            self.setLayer(layer)

    def tr(self, message):
        return QCoreApplication.translate('OverlayPS', message)
