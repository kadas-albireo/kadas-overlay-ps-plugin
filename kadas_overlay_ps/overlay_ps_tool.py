import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from kadas.kadasgui import *

from .overlay_ps_layer import OverlayPSLayer

OverlayPSWidgetBase = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'overlay_ps_dialog_base.ui'))[0]


class OverlayPSTool(QgsMapTool):

    def __init__(self, iface):
        QgsMapTool.__init__(self, iface.mapCanvas())

        self.iface = iface
        self.picking = False

        layer = iface.layerTreeView().currentLayer()
        if not layer:
            for layerId  in QgsProject.instance().mapLayers():
                projLayer = QgsProject.instance().mapLayer(layerId)
                if isinstance(projLayer, OverlayPSLayer):
                    layer = projLayer
                    break

        self.widget = OverlayPSWidget(self.iface, layer)

        self.setCursor(Qt.ArrowCursor)
        self.widget.requestPickCenter.connect(self.setPicking)
        self.widget.close.connect(self.close)

    def activate(self):
        self.widget.show()
        QgsMapTool.activate(self)

    def deactivate(self):
        self.widget.hide()
        QgsMapTool.deactivate(self)

    def setPicking(self, picking=True):
        self.picking = picking
        self.setCursor(Qt.CrossCursor if picking else Qt.ArrowCursor)

    def close(self):
        self.iface.mapCanvas().unsetMapTool(self)

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


class OverlayPSWidget(KadasBottomBar, OverlayPSWidgetBase):

    requestPickCenter = pyqtSignal()
    close = pyqtSignal()

    def __init__(self, iface, layer):
        KadasBottomBar.__init__(self, iface.mapCanvas())

        self.iface = iface
        self.layerTreeView = iface.layerTreeView()
        self.currentLayer = None

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(10)

        base = QWidget()
        self.setupUi(base)
        self.layout().addWidget(base)

        layerFilter = lambda layer: isinstance(layer, OverlayPSLayer)
        layerCreator = lambda name: self.createLayer(name)
        self.layerSelectionWidget = KadasLayerSelectionWidget(iface.mapCanvas(), iface.layerTreeView(), layerFilter, layerCreator)
        self.layerSelectionWidgetHolder.addWidget(self.layerSelectionWidget)

        closeButton = QPushButton()
        closeButton.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        closeButton.setIcon(QIcon(":/kadas/icons/close"))
        closeButton.setToolTip(self.tr("Close"))
        closeButton.clicked.connect(self.close)
        self.layout().addWidget(closeButton)
        self.layout().setAlignment(closeButton, Qt.AlignTop)

        self.inputCenter.coordinateChanged.connect(self.updateLayer)
        self.toolButtonPickCenter.clicked.connect(self.requestPickCenter)
        self.spinBoxAzimut.valueChanged.connect(self.updateLayer)
        self.spinBoxLineWidth.valueChanged.connect(self.updateLineWidth)
        self.toolButtonColor.colorChanged.connect(self.updateColor)
        self.spinBoxFontSize.valueChanged.connect(self.updateFontSize)
        self.layerSelectionWidget.selectedLayerChanged.connect(self.setCurrentLayer)

        self.layerSelectionWidget.setSelectedLayer(layer)
        self.layerSelectionWidget.createLayerIfEmpty(self.tr("Overlay PS"))

    def createLayer(self, layerName):
        layer = OverlayPSLayer(layerName)
        layer.setup(
            self.iface.mapCanvas().extent().center(),
            self.iface.mapCanvas().mapSettings().destinationCrs(),
            22.5)
        return layer

    def setCurrentLayer(self, layer):
        if layer == self.currentLayer:
            return

        self.currentLayer = layer if isinstance(layer, OverlayPSLayer) else False

        if not self.currentLayer:
            self.widgetLayerSetup.setEnabled(False)
            return

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
        self.spinBoxFontSize.setValue(self.currentLayer.getFontSize())

    def centerPicked(self, pos):
        self.inputCenter.setCoordinate(
            pos, self.iface.mapCanvas().mapSettings().destinationCrs())

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

    def updateFontSize(self, fontSize):
        if self.currentLayer:
            self.currentLayer.setFontSize(fontSize)
            self.currentLayer.triggerRepaint()
