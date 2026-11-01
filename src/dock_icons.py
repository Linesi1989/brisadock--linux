"""Original vector artwork for the built-in launchers. MIT license."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QLinearGradient, QRadialGradient, QPainterPath, QPen, QPolygonF, QPainter


def gradient(top, bottom, y1=5, y2=95):
    value = QLinearGradient(0, y1, 0, y2)
    value.setColorAt(0, QColor(top))
    value.setColorAt(1, QColor(bottom))
    return value


def tile(painter, top, bottom):
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 38))
    painter.drawRoundedRect(QRectF(5, 8, 90, 89), 21, 21)
    painter.setBrush(gradient(top, bottom))
    painter.setPen(QPen(QColor(255, 255, 255, 125), .9))
    painter.drawRoundedRect(QRectF(5, 5, 90, 89), 21, 21)


def draw_builtin(painter, rectangle, symbol):
    painter.save()
    painter.translate(rectangle.x(), rectangle.y())
    painter.scale(rectangle.width()/100, rectangle.height()/100)
    painter.setRenderHint(QPainter.Antialiasing)
    if symbol == 'folder':
        # Authentic macOS Finder icon: two-tone face split seamlessly along the curved nose contour
        tile(painter, '#ffffff', '#b8d7ff')
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(5, 5, 90, 89), 21, 21)
        painter.save()
        painter.setClipPath(outline)
        left_face = QPainterPath(QPointF(50.0, 5.0))
        left_face.cubicTo(45.17, 21.14, 40.61, 37.07, 39.56, 50.39)
        left_face.cubicTo(39.42, 53.01, 39.65, 56.16, 41.84, 56.33)
        left_face.lineTo(50.43, 56.67)
        left_face.cubicTo(52.43, 56.75, 52.89, 57.43, 53.20, 60.34)
        left_face.cubicTo(54.19, 71.84, 55.09, 83.38, 57.92, 94.0)
        left_face.lineTo(5.0, 94.0)
        left_face.lineTo(5.0, 5.0)
        left_face.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient('#15c7f8', '#1b63dc'))
        painter.drawPath(left_face)
        painter.restore()
        # Subtle outer squircle border over both halves
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 135), .9))
        painter.drawRoundedRect(QRectF(5, 5, 90, 89), 21, 21)
        # Pill-shaped dark navy eyes
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(12, 24, 42, 198))
        painter.drawRoundedRect(QRectF(27.8, 30.8, 4.8, 9.8), 2.4, 2.4)
        painter.drawRoundedRect(QRectF(67.4, 30.8, 4.8, 9.8), 2.4, 2.4)
        # Unfilled smooth smile arc across both halves
        smile = QPainterPath(QPointF(26.8, 64.2))
        smile.cubicTo(36.2, 76.2, 63.8, 76.2, 73.6, 63.8)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(12, 24, 42, 198), 3.3, Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(smile)
    elif symbol == 'web':
        tile(painter, '#ffffff', '#e0e8f1')
        painter.translate(8, 8)
        painter.scale(.84, .84)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.drawEllipse(QRectF(5, 8, 90, 90))
        painter.setBrush(gradient('#ffffff', '#a8b3c1'))
        painter.drawEllipse(QRectF(5, 4, 90, 90))
        face = QRadialGradient(36, 25, 78)
        face.setColorAt(0, QColor('#45dcff'))
        face.setColorAt(1, QColor('#0069df'))
        painter.setBrush(face)
        painter.drawEllipse(QRectF(10, 9, 80, 80))
        for tick in range(36):
            angle = tick*math.tau/36
            inner = 31 if tick % 3 == 0 else 34
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1.3 if tick % 3 == 0 else .8))
            painter.drawLine(QPointF(50+inner*math.sin(angle), 49-inner*math.cos(angle)),
                             QPointF(50+37*math.sin(angle), 49-37*math.cos(angle)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#f9414c'))
        painter.drawPolygon(QPolygonF([QPointF(76, 22), QPointF(55, 55), QPointF(44, 44)]))
        painter.setBrush(gradient('#ffffff', '#d2e4f2'))
        painter.drawPolygon(QPolygonF([QPointF(24, 76), QPointF(44, 44), QPointF(55, 55)]))
        painter.setBrush(QColor('#eff8ff'))
        painter.drawEllipse(QPointF(50, 49), 2.2, 2.2)
    elif symbol == 'apps':
        tile(painter, '#eef2f7', '#9ca9b8')
        colors = ['#33baf1', '#ffbd36', '#ff6864', '#50c98c', '#8f77e5', '#44c4bb', '#f17fa9', '#3e93f1',
                  '#f5913e', '#699be4', '#70c54f', '#b67ade', '#45b5d9', '#ef7272', '#d4ab42', '#667ad7']
        painter.setPen(Qt.NoPen)
        for index, color in enumerate(colors):
            x, y = 17+(index % 4)*17, 17+(index//4)*17
            painter.setBrush(QColor(0, 0, 0, 28))
            painter.drawRoundedRect(QRectF(x, y+1, 14, 14), 3.5, 3.5)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, y, 14, 14), 3.5, 3.5)
            painter.setBrush(QColor(255, 255, 255, 125))
            painter.drawRoundedRect(QRectF(x+3, y+3, 8, 2), 1, 1)
    elif symbol == 'download':
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 32))
        painter.drawRoundedRect(QRectF(7, 28, 86, 65), 8, 8)
        back = QPainterPath(QPointF(8, 84))
        back.lineTo(8, 22)
        back.quadTo(8, 16, 14, 16)
        back.lineTo(36, 16)
        back.lineTo(44, 24)
        back.lineTo(86, 24)
        back.quadTo(92, 24, 92, 30)
        back.lineTo(92, 84)
        back.closeSubpath()
        painter.setBrush(gradient('#7bd5ff', '#359be8', 16, 48))
        painter.drawPath(back)
        front = QPainterPath(QPointF(7, 36))
        front.quadTo(7, 31, 12, 31)
        front.lineTo(88, 31)
        front.quadTo(93, 31, 93, 36)
        front.lineTo(91, 84)
        front.quadTo(91, 91, 84, 91)
        front.lineTo(16, 91)
        front.quadTo(9, 91, 9, 84)
        front.closeSubpath()
        painter.setBrush(gradient('#78d4ff', '#4cb8f6', 31, 91))
        painter.setPen(QPen(QColor(255, 255, 255, 145), .9))
        painter.drawPath(front)
        # macOS circular badge with downward arrow inside front folder flap (Ref D)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(26, 128, 198, 110))
        painter.drawEllipse(QPointF(50, 62), 16.5, 16.5)
        painter.setPen(QPen(QColor('#9ee2ff'), 3.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(QPointF(50, 52.5), QPointF(50, 69))
        painter.drawLine(QPointF(42.5, 62.5), QPointF(50, 70))
        painter.drawLine(QPointF(50, 70), QPointF(57.5, 62.5))
    elif symbol in ('trash', 'trash_full'):
        # macOS frosted translucent glass bin (Refs C & D)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 36))
        painter.drawEllipse(QRectF(23, 87, 54, 8))
        body = QPainterPath(QPointF(19, 20))
        body.lineTo(81, 20)
        body.lineTo(72, 85)
        body.quadTo(70, 92, 50, 92)
        body.quadTo(30, 92, 28, 85)
        body.closeSubpath()
        glass = QLinearGradient(19, 20, 81, 88)
        glass.setColorAt(0.0, QColor(235, 242, 252, 185))
        glass.setColorAt(0.45, QColor(195, 206, 222, 165))
        glass.setColorAt(1.0, QColor(225, 233, 245, 210))
        painter.setBrush(glass)
        painter.setPen(QPen(QColor(255, 255, 255, 165), 1.1))
        painter.drawPath(body)
        # Frosted base disk
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(240, 245, 252, 210))
        painter.drawEllipse(QRectF(28.5, 81, 43, 9.5))
        if symbol == 'trash_full':
            painter.save()
            painter.setClipPath(body)
            for fill, pts in (
                ('#e2e5ec', [(26, 82), (24, 52), (46, 46), (52, 84)]),
                ('#d5dae3', [(45, 84), (44, 48), (74, 54), (71, 83)]),
                ('#eef1f6', [(30, 62), (35, 34), (64, 36), (66, 68)]),
            ):
                painter.setBrush(QColor(fill))
                painter.setPen(QPen(QColor(130, 140, 155, 90), .8))
                painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
            painter.restore()
            # Crumpled paper pieces peeking over the top rim (Ref C)
            papers = [
                ('#f7f7f4', '#b8c0cc', [(23, 23), (20, 12), (33, 7), (43, 15), (40, 25)]),
                ('#dce8f7', '#8ea8c8', [(36, 24), (39, 6), (54, 4), (59, 16), (53, 26)]),
                ('#f3efe8', '#bfb6a8', [(51, 25), (57, 8), (72, 10), (78, 19), (71, 25)]),
                ('#e85d4a', '#b83c2c', [(44, 19), (48, 11), (56, 14), (52, 22)]),
                ('#55b36b', '#38854a', [(60, 21), (64, 13), (71, 16), (67, 23)]),
            ]
            for fill, stroke, pts in papers:
                painter.setBrush(QColor(fill))
                painter.setPen(QPen(QColor(stroke), .9))
                painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
            painter.setPen(QPen(QColor('#9aa6b5'), 1.1))
            painter.drawLine(QPointF(26, 14), QPointF(36, 18))
            painter.drawLine(QPointF(43, 11), QPointF(52, 15))
            painter.drawLine(QPointF(61, 14), QPointF(70, 18))
        # Subtle vertical glass highlight streaks
        painter.save()
        painter.setClipPath(body)
        sheen_left = QLinearGradient(22, 20, 34, 20)
        sheen_left.setColorAt(0, QColor(255, 255, 255, 95))
        sheen_left.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(sheen_left)
        painter.drawRect(QRectF(20, 22, 14, 68))
        painter.restore()
        # Top elliptical glass rim
        painter.setBrush(QColor(175, 188, 208, 95 if symbol == 'trash' else 55))
        painter.setPen(QPen(QColor(255, 255, 255, 235), 2.0))
        painter.drawEllipse(QRectF(19, 14, 62, 12))
    else:
        tile(painter, '#a7b0bc', '#657182')
        painter.setPen(QPen(QColor('white'), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(28, 50), QPointF(72, 50))
        painter.drawLine(QPointF(50, 28), QPointF(50, 72))
    painter.restore()
