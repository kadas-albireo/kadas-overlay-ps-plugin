import os
import math
from enum import Enum
from geographiclib.geodesic import Geodesic

from PyQt4 import uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *


class OverlayPSLayer(QgsPluginLayer):

    def __init__(self, layer_name):
        QgsPluginLayer.__init__(self, self.pluginLayerType(), layer_name)

        self.setValid(True)
        self.center = QgsPoint()
        self.azimut = None
        self.color = Qt.red
        self.lineWidth = 3
        self.transparency = 0
        self.layer_name = layer_name

    @classmethod
    def pluginLayerType(self):
        return "overlayps"

    def setup(self, center, crs, azimut):
        self.center = center
        self.azimut = azimut

        self.setCrs(crs, False)

    def writeSymbology(self, node, doc, errorMsg):
        return True

    def readSymbology(self, node, errorMsg):
        return True

    def createMapRenderer(self, rendererContext):
        return Renderer(self, rendererContext)

    def extent(self):
        radius = 230
        radius *= QGis.fromUnitToUnitFactor(QGis.Meters, self.crs().mapUnits())

        return QgsRectangle(self.center.x() - radius, self.center.y() - radius,
                            self.center.x() + radius, self.center.y() + radius)

    def getCenter(self):
        return self.center

    def getAzimut(self):
        return self.azimut

    def getColor(self):
        return self.color

    def getLineWidth(self):
        return self.lineWidth

    def setColor(self, color):
        self.color = color

    def setLineWidth(self, lineWidth):
        self.lineWidth = lineWidth

    def readXml(self, layer_node):
        layerEl = layer_node.toElement()
        self.layer_name = layerEl.attribute("title")
        self.transparency = int(layerEl.attribute("transparency"))
        self.center.setX(float(layerEl.attribute("x")))
        self.center.setY(float(layerEl.attribute("y")))
        self.azimut = float(layerEl.attribute("azimut"))
        self.color = QgsSymbolLayerV2Utils.decodeColor(layerEl.attribute(
            "color"))
        self.lineWidth = int(layerEl.attribute("lineWidth"))

        self.setCrs(QgsCRSCache.instance().crsByAuthId(layerEl.attribute(
            "crs")))
        return True

    def writeXml(self, layer_node, document):
        layerEl = layer_node.toElement()
        layerEl.setAttribute("type", "plugin")
        layerEl.setAttribute("name", self.pluginLayerType())
        layerEl.setAttribute("title", self.layer_name)
        layerEl.setAttribute("transparency", self.transparency)
        layerEl.setAttribute("x", self.center.x())
        layerEl.setAttribute("y", self.center.y())
        layerEl.setAttribute("azimut", self.azimut)
        layerEl.setAttribute("crs", self.crs().authid())
        layerEl.setAttribute("color", QgsSymbolLayerV2Utils.encodeColor(
            self.color))
        layerEl.setAttribute("lineWidth", self.getLineWidth())
        return True


class Renderer(QgsMapLayerRenderer):
    def __init__(self, layer, rendererContext):
        QgsMapLayerRenderer.__init__(self, layer.id())

        self.layer = layer
        self.rendererContext = rendererContext
        self.geod = Geodesic.WGS84
        self.mDa = QgsDistanceArea()

        self.mDa.setEllipsoid("WGS84")
        self.mDa.setEllipsoidalMode(True)
        self.mDa.setSourceCrs(QgsCRSCache.instance().crsByAuthId("EPSG:4326"))

    def render(self):
        mapToPixel = self.rendererContext.mapToPixel()
        self.rendererContext.painter().save()
        self.rendererContext.painter().setOpacity((
            100. - self.layer.transparency) / 100.)
        self.rendererContext.painter().setCompositionMode(
            QPainter.CompositionMode_Source)
        self.rendererContext.painter().setPen(
            QPen(self.layer.color, self.layer.lineWidth))

        ct = QgsCoordinateTransformCache.instance().transform(
            self.layer.crs().authid(), "EPSG:4326")
        rct = QgsCoordinateTransformCache.instance().transform(
            "EPSG:4326", self.rendererContext.coordinateTransform().destCRS().authid() if self.rendererContext.coordinateTransform() else self.layer.crs().authid())

        # draw rings
        wgsCenter = ct.transform(self.layer.center)

        radMeters = 230
        poly = QPolygonF()
        for a in range(361):
            wgsPoint = self.mDa.computeDestination(wgsCenter, radMeters, a)
            mapPoint = rct.transform(wgsPoint)
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
        path = QPainterPath()
        path.addPolygon(poly)
        self.rendererContext.painter().drawPath(path)

        # draw axes
        axisRadiusMeters = 1 * QGis.fromUnitToUnitFactor(QGis.NauticalMiles, QGis.Meters)
        bearing = self.layer.getAzimut()
        for counter in range(2):
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                                   axisRadiusMeters, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            dist = line.s13
            sdist = 50
            nSegments = max(1, int(math.ceil(dist / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments):
                coords = line.Position(iseg * sdist)
                mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())
            line.Position(dist)
            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)
            bearing = self.layer.getAzimut() + 180

        # draw flight lines
        self.rendererContext.painter().setPen(QPen(
            self.layer.color, self.layer.lineWidth, Qt.DashLine))
        lineRadiusMeters = 1.5 * QGis.fromUnitToUnitFactor(QGis.NauticalMiles, QGis.Meters)
        bearing = self.layer.getAzimut() + 45
        for counter in range(2):
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                                   lineRadiusMeters, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            dist = line.s13
            sdist = 50
            nSegments = max(1, int(math.ceil(dist / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments):
                if iseg in range(2):
                    continue
                coords = line.Position(iseg * sdist)
                mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())
            line.Position(dist)
            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)
            bearing += 90

        self.rendererContext.painter().restore()
        return True


class OverlayPSLayerType(QgsPluginLayerType):
    def __init__(self):
        QgsPluginLayerType.__init__(self, OverlayPSLayer.pluginLayerType())

    def createLayer(self):
        return OverlayPSLayer("OverlayPS")

    def hasLayerProperties(self):
        return 0
