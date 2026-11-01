"""Bounded, on-demand capture of one explicitly selected window, in memory."""
import ctypes as C
from ctypes import wintypes as W
import threading

from PySide6.QtCore import QObject, Signal, QRect
from PySide6.QtGui import QImage
from appbar import MonitorInfo


class BitmapHeader(C.Structure):
    _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG), ('planes', W.WORD),
                ('bits', W.WORD), ('compression', W.DWORD), ('image_size', W.DWORD),
                ('xppm', W.LONG), ('yppm', W.LONG), ('used', W.DWORD), ('important', W.DWORD)]


class BitmapInfo(C.Structure):
    _fields_ = [('header', BitmapHeader), ('color', W.DWORD)]


def logical_bounds(backend, window, screen, destination_hwnd):
    if not backend.valid(window) or backend.u.IsIconic(window['id']):
        return None
    user = backend.u
    user.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]
    user.MonitorFromWindow.restype = W.HMONITOR
    user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.GetMonitorInfoW.argtypes = [W.HMONITOR, C.POINTER(MonitorInfo)]
    monitor = user.MonitorFromWindow(window['id'], 2)
    if monitor != user.MonitorFromWindow(destination_hwnd, 2):
        return None
    info = MonitorInfo()
    info.cbSize = C.sizeof(info)
    rect = W.RECT()
    if not user.GetMonitorInfoW(monitor, C.byref(info)) or not user.GetWindowRect(window['id'], C.byref(rect)):
        return None
    ratio = screen.devicePixelRatio()
    base = screen.geometry()
    return QRect(round(base.x()+(rect.left-info.monitor.left)/ratio), round(base.y()+(rect.top-info.monitor.top)/ratio),
                 round((rect.right-rect.left)/ratio), round((rect.bottom-rect.top)/ratio))


def capture_window(window):
    user, gdi = C.WinDLL('user32'), C.WinDLL('gdi32')
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.GetWindowRect.restype = W.BOOL
    user.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    user.PrintWindow.restype = W.BOOL
    pid = W.DWORD()
    user.GetWindowThreadProcessId(window['id'], C.byref(pid))
    rect = W.RECT()
    if pid.value != window['pid'] or not user.GetWindowRect(window['id'], C.byref(rect)):
        return None
    width, height = rect.right-rect.left, rect.bottom-rect.top
    if width < 32 or height < 32 or width*height > 4_000_000:
        return None
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateDIBSection.argtypes = [W.HDC, C.POINTER(BitmapInfo), W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD]
    gdi.CreateDIBSection.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HANDLE]
    gdi.SelectObject.restype = W.HANDLE
    gdi.DeleteObject.argtypes = [W.HANDLE]
    gdi.DeleteDC.argtypes = [W.HDC]
    dc = gdi.CreateCompatibleDC(None)
    if not dc:
        return None
    bitmap, previous = None, None
    try:
        info = BitmapInfo()
        info.header = BitmapHeader(C.sizeof(BitmapHeader), width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
        pointer = C.c_void_p()
        bitmap = gdi.CreateDIBSection(dc, C.byref(info), 0, C.byref(pointer), None, 0)
        if not bitmap or not pointer.value:
            return None
        previous = gdi.SelectObject(dc, bitmap)
        if not user.PrintWindow(window['id'], dc, 0):
            return None
        gdi.GdiFlush()
        user.GetWindowThreadProcessId(window['id'], C.byref(pid))
        if pid.value != window['pid']:
            return None
        data = C.string_at(pointer, width*height*4)
        return QImage(data, width, height, width*4, QImage.Format_RGB32).copy()
    finally:
        if previous:
            gdi.SelectObject(dc, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        gdi.DeleteDC(dc)


class CaptureBroker(QObject):
    ready = Signal(int, object)

    def __init__(self, parent=None, capture=capture_window):
        super().__init__(parent)
        self.capture = capture
        self.busy = False
        self.counter = 0
        self.lock = threading.Lock()

    def request(self, window):
        with self.lock:
            if self.busy:
                return None
            self.busy = True
            self.counter += 1
            token = self.counter
        def run():
            image = None
            try:
                image = self.capture(window)
            except Exception:
                pass
            finally:
                with self.lock:
                    self.busy = False
            try:
                self.ready.emit(token, image)
            except RuntimeError:
                pass
        threading.Thread(target=run, daemon=True, name='BrisaWindowCapture').start()
        return token
