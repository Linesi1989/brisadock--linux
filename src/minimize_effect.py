"""Optional shrink animation for minimize/restore requests made through Brisa."""
import ctypes as C
import os
import time

from PySide6.QtCore import Qt, QRect, QRectF, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QWidget


class MinimizeEffect(QWidget):
    finished = Signal()

    def __init__(self, backend, window, target, screen, destination_hwnd, reverse=False, origin=None, image=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        if os.name == 'nt':
            self.setStyleSheet('background: #202938;')
        else:
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.backend, self.window, self.target, self.screen = backend, window, QRect(target), screen
        self.destination_hwnd = destination_hwnd
        self.reverse = reverse
        self.image = image
        self.target_provider = None
        self.suppress_restore = False
        self.saved_origin = QRect(origin) if origin is not None else None
        self.thumbnails = None
        self.restore_transitions = None
        self.progress = 0.
        self.started = False
        self.completed = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)

    def redirect(self, reverse):
        if not self.started or self.completed:
            return False
        if self.reverse == reverse:
            return True
        self.reverse = reverse
        if not reverse:
            self.backend.minimize(self.window)
            self.window['minimized'] = True
        self.start_time = time.monotonic() - (1. - self.progress) * .34
        return True

    def begin(self):
        if not self.backend.valid(self.window):
            return False
        if os.name != 'nt':
            minimized = bool(self.window.get('minimized'))
            if (not self.reverse and minimized) or (self.reverse and (not minimized or self.saved_origin is None)):
                return False
            if self.reverse:
                self.origin = QRect(self.saved_origin)
            else:
                geometry = self.window.get('geometry')
                if not geometry or len(geometry) != 4:
                    return False
                self.origin = QRect(*[int(v) for v in geometry])
            if self.origin.width() < 20 or self.origin.height() < 20:
                return False
            self.setGeometry(self.target if self.reverse else self.origin)
            self.show()
            if not self.reverse:
                self.backend.minimize(self.window)
                self.window['minimized'] = True
            self.started = True
            self.start_time = time.monotonic()
            self.timer.start(16)
            return True
        from ctypes import wintypes as W
        from native_previews import DwmThumbnails
        minimized = bool(self.backend.u.IsIconic(self.window['id']))
        if (not self.reverse and minimized) or (self.reverse and (not minimized or self.saved_origin is None)):
            return False
        api = self.backend.u
        api.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        api.GetWindowRect.restype = W.BOOL
        rect = W.RECT()
        if not api.GetWindowRect(self.window['id'], C.byref(rect)):
            return False
        from appbar import MonitorInfo
        api.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]
        api.MonitorFromWindow.restype = W.HMONITOR
        if api.MonitorFromWindow(self.window['id'], 2) != api.MonitorFromWindow(self.destination_hwnd, 2):
            return False
        api.GetMonitorInfoW.argtypes = [W.HMONITOR, C.POINTER(MonitorInfo)]
        api.GetMonitorInfoW.restype = W.BOOL
        monitor = MonitorInfo()
        monitor.cbSize = C.sizeof(monitor)
        if not api.GetMonitorInfoW(api.MonitorFromWindow(self.window['id'], 2), C.byref(monitor)):
            return False
        geometry = self.screen.geometry()
        ratio = self.screen.devicePixelRatio()
        if abs(round(geometry.width()*ratio) - (monitor.monitor.right-monitor.monitor.left)) > 2:
            return False
        self.origin = QRect(round(geometry.x()+(rect.left-monitor.monitor.left)/ratio),
                            round(geometry.y()+(rect.top-monitor.monitor.top)/ratio),
                            round((rect.right-rect.left)/ratio), round((rect.bottom-rect.top)/ratio))
        if self.reverse:
            self.origin = self.saved_origin
        if self.origin.width() < 20 or self.origin.height() < 20:
            return False
        self.setGeometry(self.target if self.reverse else self.origin)
        self.show()
        self.thumbnails = DwmThumbnails(int(self.winId()))
        if not self.thumbnails.add(self.window['id'], [0, 0, round(self.width()*ratio), round(self.height()*ratio)]):
            self.close()
            return False
        self.backend.dwm.DwmSetWindowAttribute.argtypes = [W.HWND, W.DWORD, C.c_void_p, W.DWORD]
        self.backend.dwm.DwmSetWindowAttribute.restype = W.LONG
        previous = W.BOOL()
        if self.backend.dwm.DwmGetWindowAttribute(self.window['id'], 3, C.byref(previous), C.sizeof(previous)) == 0:
            disabled = W.BOOL(True)
            if self.backend.dwm.DwmSetWindowAttribute(self.window['id'], 3, C.byref(disabled), C.sizeof(disabled)) == 0:
                self.restore_transitions = previous.value
        if not self.reverse:
            self.backend.minimize(self.window)
        self.started = True
        self.start_time = time.monotonic()
        self.timer.start(16)
        return True

    def advance(self):
        if self.target_provider is not None:
            updated = self.target_provider()
            if updated is not None:
                self.target = QRect(updated)
        progress = min(1., (time.monotonic()-self.start_time)/.34)
        self.progress = progress
        eased = 1-(1-progress)**3
        def lerp(a, b):
            return round(a+(b-a)*eased)
        start, end = (self.target, self.origin) if self.reverse else (self.origin, self.target)
        bounds = QRect(lerp(start.x(), end.x()), lerp(start.y(), end.y()),
                       max(2, lerp(start.width(), end.width())),
                       max(2, lerp(start.height(), end.height())))
        self.setGeometry(bounds)
        if os.name == 'nt' and self.thumbnails and self.thumbnails.handles:
            from ctypes import wintypes as W
            from native_previews import ThumbnailProperties
            ratio = self.devicePixelRatioF()
            properties = ThumbnailProperties()
            properties.flags = 1 | 4 | 8
            properties.destination = W.RECT(0, 0, round(bounds.width()*ratio), round(bounds.height()*ratio))
            properties.opacity = round(255*(.75+progress*.25 if self.reverse else 1-progress*.25))
            properties.visible = True
            self.thumbnails.api.DwmUpdateThumbnailProperties(self.thumbnails.handles[0], C.byref(properties))
        else:
            self.update()
        if progress >= 1 or not self.backend.valid(self.window):
            self.completed = True
            if self.reverse and not self.suppress_restore and self.backend.valid(self.window):
                self.backend.activate(self.window)
                self.window['minimized'] = False
            self.close()

    def paintEvent(self, event):
        if os.name != 'nt' and self.image is not None and not self.image.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.setOpacity(.75+self.progress*.25 if self.reverse else 1-self.progress*.2)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
            painter.setClipPath(clip)
            painter.drawImage(QRectF(0, 0, self.width(), self.height()), self.image)

    def closeEvent(self, event):
        self.timer.stop()
        if self.thumbnails:
            self.thumbnails.clear()
        if os.name == 'nt' and self.restore_transitions is not None and self.backend.valid(self.window):
            from ctypes import wintypes as W
            value = W.BOOL(self.restore_transitions)
            self.backend.dwm.DwmSetWindowAttribute(self.window['id'], 3, C.byref(value), C.sizeof(value))
        if self.started and self.reverse and not self.completed and not self.suppress_restore and self.backend.valid(self.window):
            self.backend.activate(self.window)
        self.finished.emit()
        super().closeEvent(event)
