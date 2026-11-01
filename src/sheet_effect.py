"""Single-frame curved contraction. Images stay in application memory only."""
import time
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget
from sheet_geometry import sheet_mesh, canonical


class SheetEffect(QWidget):
    finished = Signal()

    def __init__(self, backend, window, target, screen, origin, image, edge='bottom', reverse=False):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.backend, self.window, self.target, self.screen = backend, window, QRect(target), screen
        self.origin, self.image, self.edge, self.reverse = QRect(origin), image, edge, reverse
        self.target_provider = None
        self.suppress_restore = False
        self.started, self.completed, self.progress = False, False, 1. if reverse else 0.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.box = self.origin.united(self.target).adjusted(-2, -2, 2, 2)
        self.setGeometry(self.box)

    def window_minimized(self):
        if hasattr(self.backend, 'u'):
            return bool(self.backend.u.IsIconic(self.window['id']))
        return bool(self.window.get('minimized'))

    def begin(self):
        if self.image is None or self.image.isNull() or not self.backend.valid(self.window):
            return False
        if self.window_minimized() != self.reverse:
            return False
        _, oy, _, oh = canonical(self.origin.getRect(), self.edge)
        _, ty, _, th = canonical(self.target.getRect(), self.edge)
        if ty+th < oy+oh*.6:
            return False
        self.show()
        if not self.reverse:
            self.backend.minimize(self.window)
            self.window['minimized'] = True
        self.started = True
        self.start_time = time.monotonic()
        self.timer.start(16)
        self.update()
        return True

    def redirect(self, reverse):
        if not self.started or self.completed:
            return False
        if self.reverse == reverse:
            return True
        self.reverse = reverse
        if not reverse:
            self.backend.minimize(self.window)
            self.window['minimized'] = True
        elapsed = (1. - self.progress) if reverse else self.progress
        self.start_time = time.monotonic() - elapsed * .55
        return True

    def advance(self):
        if self.target_provider is not None:
            updated = self.target_provider()
            if updated is not None and updated != self.target:
                self.target = QRect(updated)
                self.box = self.origin.united(self.target).adjusted(-2, -2, 2, 2)
                self.setGeometry(self.box)
        elapsed = min(1., (time.monotonic()-self.start_time)/.55)
        self.progress = 1-elapsed if self.reverse else elapsed
        self.update()
        if elapsed >= 1 or not self.backend.valid(self.window):
            self.completed = True
            if self.reverse and not self.suppress_restore and self.backend.valid(self.window):
                self.backend.activate(self.window)
                self.window['minimized'] = False
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for v0, v1, points in sheet_mesh(self.origin.getRect(), self.target.getRect(), self.progress, self.edge, overlap=.0015):
            if self.edge == 'bottom':
                source = QRectF(0, v0*self.image.height(), self.image.width(), (v1-v0)*self.image.height())
            elif self.edge == 'right':
                source = QRectF(v0*self.image.width(), 0, (v1-v0)*self.image.width(), self.image.height())
            else:
                source = QRectF((1-v1)*self.image.width(), 0, (v1-v0)*self.image.width(), self.image.height())
            destination = QPolygonF([QPointF(x-self.box.x(), y-self.box.y()) for x, y in points])
            src = QPolygonF([source.topLeft(), source.topRight(), source.bottomRight(), source.bottomLeft()])
            transform = QTransform()
            if not QTransform.quadToQuad(src, destination, transform):
                continue
            clip = QPainterPath()
            clip.addPolygon(destination)
            painter.save()
            painter.setClipPath(clip)
            painter.setTransform(transform)
            painter.drawImage(source, self.image, source)
            painter.restore()

    def closeEvent(self, event):
        self.timer.stop()
        if self.started and self.reverse and not self.completed and not self.suppress_restore and self.backend.valid(self.window):
            self.backend.activate(self.window)
        self.finished.emit()
        super().closeEvent(event)
