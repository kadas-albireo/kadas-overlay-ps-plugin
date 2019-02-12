import math
from geographiclib.geodesic import Geodesic

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *


class OverlayPSLayer(QgsPluginLayer):

    def __init__(self, layer_name):
        QgsPluginLayer.__init__(self, self.pluginLayerType(), layer_name)

        self.setValid(True)
        self.center = QgsPoint()
        self.azimut = 22.5
        self.color = Qt.black
        self.lineWidth = 3
        self.fontSize = 10
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

    def getFontSize(self):
        return self.fontSize

    def setColor(self, color):
        self.color = color

    def setLineWidth(self, lineWidth):
        self.lineWidth = lineWidth

    def setFontSize(self, fontSize):
        self.fontSize = fontSize

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
        self.fontSize = int(layerEl.attribute("fontSize"))

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
        layerEl.setAttribute("fontSize", self.getFontSize())
        return True


class Renderer(QgsMapLayerRenderer):
    def __init__(self, layer, rendererContext):
        QgsMapLayerRenderer.__init__(self, layer.id())

        # Constants
        self.ringRadius = 1750 # meters
        self.mainAxisLength = 7000 # meters
        self.flightLineLength = 6000 # meters

        self.layer = layer
        self.rendererContext = rendererContext
        self.geod = Geodesic.WGS84
        self.mDa = QgsDistanceArea()

        self.mDa.setEllipsoid("WGS84")
        self.mDa.setEllipsoidalMode(True)
        self.mDa.setSourceCrs(QgsCRSCache.instance().crsByAuthId("EPSG:4326"))

    def drawAxisMarks(self, rct, metrics, marks, axisbearing, flip):
        # draw kilometer marks
        mapToPixel = self.rendererContext.mapToPixel()
        for idx, mark in enumerate(marks):
            point, label = mark
            s = -1 if flip else 1
            p1 = self.mDa.computeDestination(point, 250, axisbearing + 90 * s)
            p2 = self.mDa.computeDestination(point, 250, axisbearing + 270 * s)
            poly = QPolygonF()
            poly.append(mapToPixel.transform(rct.transform(p1)).toQPointF())
            poly.append(mapToPixel.transform(rct.transform(point)).toQPointF())
            poly.append(mapToPixel.transform(rct.transform(p2)).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)

            # draw label
            if not label:
                continue
            dx = poly[0].x() - poly[2].x()
            dy = poly[0].y() - poly[2].y()
            l = math.sqrt(dx * dx + dy * dy)
            if l > 1E-6:
                dx /= l
                dy /= l
            w = metrics.width(label)
            h = self.rendererContext.painter().font().pixelSize()
            cx = poly[2].x() - dx * 0.6 * w
            cy = poly[2].y() - dy * 0.6 * w
            self.rendererContext.painter().drawText(
                cx - 0.5 * w, cy - 0.5 * h, w, h,
                Qt.AlignCenter | Qt.AlignHCenter, label
            )

    def render(self):
        azimut = self.layer.getAzimut()

        mapToPixel = self.rendererContext.mapToPixel()
        self.rendererContext.painter().save()
        self.rendererContext.painter().setOpacity((
            100. - self.layer.transparency) / 100.)
        self.rendererContext.painter().setCompositionMode(
            QPainter.CompositionMode_Source)
        self.rendererContext.painter().setPen(
            QPen(self.layer.color, self.layer.lineWidth))
        font = self.rendererContext.painter().font()
        font.setPixelSize(self.layer.getFontSize())
        self.rendererContext.painter().setFont(font)
        metrics = QFontMetrics(font)

        ct = QgsCoordinateTransformCache.instance().transform(
            self.layer.crs().authid(), "EPSG:4326")
        rct = QgsCoordinateTransformCache.instance().transform(
            "EPSG:4326", self.rendererContext.coordinateTransform().destCRS().authid() if self.rendererContext.coordinateTransform() else self.layer.crs().authid())

        # draw rings
        wgsCenter = ct.transform(self.layer.center)
        point = self.mDa.computeDestination(wgsCenter,
                                            self.ringRadius,
                                            azimut + 90)
        line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                     point.y(), point.x())
        newCenter = QgsPoint(line.Position(1750)["lon2"],
                             line.Position(1750)["lat2"])
        poly = QPolygonF()
        for a in range(-150, 151):
            wgsPoint = self.mDa.computeDestination(
                newCenter, self.ringRadius, a + azimut + 90)
            mapPoint = rct.transform(wgsPoint)
            poly.append(mapToPixel.transform(mapPoint).toQPointF())

        path = QPainterPath()
        path.addPolygon(poly)
        self.rendererContext.painter().drawPath(path)

        # draw main axis
        for bearing, flip in [(azimut, False), (azimut + 180, True)]:
            marks = []
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                    self.mainAxisLength, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            sdist = 1000
            nSegments = max(1, int(math.ceil(self.mainAxisLength / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments + 1):
                coords = line.Position(iseg * sdist)
                marks.append((
                    QgsPoint(coords["lon2"], coords["lat2"]),
                    "%s km" % iseg if iseg > 0 else None
                ))
                mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                  coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())
            line.Position(self.mainAxisLength)

            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)

            self.drawAxisMarks(rct, metrics, marks, bearing, flip)

        # draw flight lines
        for bearing, flip in [(azimut + 45, False), (azimut + 90, False), (azimut + 135, True)]:
            marks = []
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                                   self.flightLineLength, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            sdist = 500
            nSegments = max(1, int(math.ceil(self.flightLineLength / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments + 1):
                if iseg in range(3):
                    continue
                coords = line.Position(iseg * sdist)
                if iseg > 3 and iseg % 2 == 0:
                    marks.append((
                        QgsPoint(coords["lon2"], coords["lat2"]),
                        "%d km" % (iseg / 2)
                    ))
                mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                  coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())

            line.Position(self.flightLineLength)
            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)

            self.drawAxisMarks(rct, metrics, marks, bearing, flip)

        self.rendererContext.painter().restore()
        return True


class OverlayPSLayerType(QgsPluginLayerType):
    def __init__(self):
        QgsPluginLayerType.__init__(self, OverlayPSLayer.pluginLayerType())

    def createLayer(self):
        return OverlayPSLayer("OverlayPS")

    def hasLayerProperties(self):
        return 0
