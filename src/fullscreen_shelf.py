"""An input-shaped view of Brisa's own shelf above X11 fullscreen windows.

KWin keeps managed docks below active fullscreen clients. This short-lived,
non-focusing override-redirect surface only renders our QWidget; it never
captures, hides, restacks or changes a user's application window.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter,QRegion
from PySide6.QtWidgets import QWidget


class FullscreenShelf(QWidget):
    def __init__(self,dock):
        super().__init__(None,Qt.Tool | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.dock=dock
        self.setWindowTitle('BrisaDock — acceso desde pantalla completa')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_QuitOnClose,False)
        self.setMouseTracking(True);self.setAcceptDrops(True)
        self.image=None
    def refresh(self):
        self.setGeometry(self.dock.geometry())
        self.image=self.dock.grab()
        self.setMask(QRegion(self.image.mask()))
        if not self.isVisible():self.show();self.raise_()
        self.update()
    def paintEvent(self,event):
        if self.image is not None:
            painter=QPainter(self);painter.drawPixmap(0,0,self.image)
    def mousePressEvent(self,event):self.dock.mousePressEvent(event)
    def mouseMoveEvent(self,event):self.dock.mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):self.dock.mouseReleaseEvent(event)
    def contextMenuEvent(self,event):self.dock.contextMenuEvent(event)
    def dragEnterEvent(self,event):self.dock.dragEnterEvent(event)
    def dragMoveEvent(self,event):self.dock.dragMoveEvent(event)
    def dragLeaveEvent(self,event):self.dock.dragLeaveEvent(event)
    def dropEvent(self,event):self.dock.dropEvent(event)
