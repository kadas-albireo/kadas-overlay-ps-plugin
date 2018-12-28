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
        font = self.rendererContext.painter().font()
        font.setPixelSize(self.layer.getFontSize())
        self.rendererContext.painter().setFont(font)

        ct = QgsCoordinateTransformCache.instance().transform(
            self.layer.crs().authid(), "EPSG:4326")
        rct = QgsCoordinateTransformCache.instance().transform(
            "EPSG:4326", self.rendererContext.coordinateTransform().destCRS().authid() if self.rendererContext.coordinateTransform() else self.layer.crs().authid())

        # draw rings
        wgsCenter = ct.transform(self.layer.center)
        radMeters = 1750
        point = self.mDa.computeDestination(wgsCenter,
                                            radMeters,
                                            self.layer.getAzimut() + 90)
        line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                     point.y(), point.x())
        newCenter = QgsPoint(line.Position(1750)["lon2"],
                             line.Position(1750)["lat2"])
        poly = QPolygonF()
        for a in range(210, 361):
            wgsPoint = self.mDa.computeDestination(
                newCenter, radMeters, a + self.layer.getAzimut() + 90)
            mapPoint = rct.transform(wgsPoint)
            poly.append(mapToPixel.transform(mapPoint).toQPointF())

        for a in range(0, 150):
            wgsPoint = self.mDa.computeDestination(
                newCenter, radMeters, a + self.layer.getAzimut() + 90)
            mapPoint = rct.transform(wgsPoint)
            poly.append(mapToPixel.transform(mapPoint).toQPointF())

        path = QPainterPath()
        path.addPolygon(poly)
        self.rendererContext.painter().drawPath(path)

        # draw axes
        axisRadiusMeters = 7000
        bearing = self.layer.getAzimut()
        for counter in range(2):
            labels = []
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                                   axisRadiusMeters, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            dist = 7000
            sdist = 1000
            nSegments = max(1, int(math.ceil(dist / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments + 1):
                coords = line.Position(iseg * sdist)
                labels.append(QgsPoint(coords["lon2"], coords["lat2"]))
                mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                  coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())
            line.Position(dist)

            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)
            bearing = self.layer.getAzimut() + 180

            # draw kilometer mark
            for point in labels:
                bear = self.layer.getAzimut() + 90
                for a in range(2):
                    wgsPoint = self.mDa.computeDestination(
                        point, 250,
                        bear)
                    line = self.geod.InverseLine(point.y(),
                                                 point.x(),
                                                 wgsPoint.y(), wgsPoint.x())
                    poly = QPolygonF()
                    for iseg in range(5):
                        coords = line.Position(iseg * 50)
                        mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                          coords["lat2"]))
                        poly.append(mapToPixel.transform(mapPoint).toQPointF())
                    line.Position(100)
                    mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                      coords["lat2"]))
                    poly.append(mapToPixel.transform(mapPoint).toQPointF())

                    # draw label
                    if a == 1:
                        metrics = QFontMetrics(
                            self.rendererContext.painter().font())
                        label = "%s km" % counter
                        n = poly.size()
                        dx = poly[n - 2].x() - poly[n - 4].x() if n > 1 else 0
                        dy = poly[n - 2].y() - poly[n - 4].y() if n > 1 else 0
                        l = math.sqrt(dx * dx + dy * dy)
                        d = self.layer.getFontSize()
                        w = metrics.width(label)
                        x = poly.last().x() if n < 2 else poly.last().x() + d * dx / l
                        y = poly.last().y() if n < 2 else poly.last().y() + d * dy / l
                        self.rendererContext.painter().drawText(
                            x - 0.5 * w, y - d, w, 2 * d,
                            Qt.AlignCenter | Qt.AlignHCenter, label)

                    path = QPainterPath()
                    path.addPolygon(poly)
                    self.rendererContext.painter().drawPath(path)
                    bear += 180

        # draw flight lines
        lineRadiusMeters = 6000
        bearing = self.layer.getAzimut() + 45
        for counter in range(3):
            labels = []
            wgsPoint = self.mDa.computeDestination(wgsCenter,
                                                   lineRadiusMeters, bearing)
            line = self.geod.InverseLine(wgsCenter.y(), wgsCenter.x(),
                                         wgsPoint.y(), wgsPoint.x())
            dist = 6000
            sdist = 500
            nSegments = max(1, int(math.ceil(dist / sdist)))
            poly = QPolygonF()
            for iseg in range(nSegments + 1):
                if iseg in range(3):
                    continue
                coords = line.Position(iseg * sdist)
                if iseg != 3 and iseg % 2 == 0:
                    labels.append(QgsPoint(coords["lon2"], coords["lat2"]))
                mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                  coords["lat2"]))
                poly.append(mapToPixel.transform(mapPoint).toQPointF())

            line.Position(dist)
            mapPoint = rct.transform(QgsPoint(coords["lon2"], coords["lat2"]))
            poly.append(mapToPixel.transform(mapPoint).toQPointF())
            path = QPainterPath()
            path.addPolygon(poly)
            self.rendererContext.painter().drawPath(path)
            bearing += 45

            # draw kilometer mark
            for point in labels:
                if counter == 0:
                    bear = self.layer.getAzimut() + 315
                elif counter == 1:
                    bear = self.layer.getAzimut()
                else:
                    bear = self.layer.getAzimut() + 45
                for a in range(2):
                    wgsPoint = self.mDa.computeDestination(
                        point, 250,
                        bear)
                    line = self.geod.InverseLine(point.y(),
                                                 point.x(),
                                                 wgsPoint.y(), wgsPoint.x())
                    poly = QPolygonF()
                    for iseg in range(5):
                        coords = line.Position(iseg * 50)
                        mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                          coords["lat2"]))
                        poly.append(mapToPixel.transform(mapPoint).toQPointF())
                    line.Position(100)
                    mapPoint = rct.transform(QgsPoint(coords["lon2"],
                                                      coords["lat2"]))
                    poly.append(mapToPixel.transform(mapPoint).toQPointF())
                    # draw label
                    if a == 0:
                        metrics = QFontMetrics(
                            self.rendererContext.painter().font())
                        label = "%s km" % counter
                        n = poly.size()
                        dx = poly[n - 2].x() - poly[n - 4].x() if n > 1 else 0
                        dy = poly[n - 2].y() - poly[n - 4].y() if n > 1 else 0
                        l = math.sqrt(dx * dx + dy * dy)
                        d = self.layer.getFontSize()
                        w = metrics.width(label)
                        x = poly.last().x() if n < 2 else poly.last().x() + d * dx / l
                        y = poly.last().y() if n < 2 else poly.last().y() + d * dy / l
                        self.rendererContext.painter().drawText(
                            x - 0.5 * w, y - d, w, 2 * d,
                            Qt.AlignCenter | Qt.AlignHCenter, label)

                    path = QPainterPath()
                    path.addPolygon(poly)
                    self.rendererContext.painter().drawPath(path)
                    bear += 180

        self.rendererContext.painter().restore()
        return True


class OverlayPSLayerType(QgsPluginLayerType):
    def __init__(self):
        QgsPluginLayerType.__init__(self, OverlayPSLayer.pluginLayerType())

    def createLayer(self):
        return OverlayPSLayer("OverlayPS")

    def hasLayerProperties(self):
        return 0
