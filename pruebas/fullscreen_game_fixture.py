"""Own disposable fullscreen client; record physical X11 clicks, no user files."""
import sys,json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QVBoxLayout
from PySide6.QtCore import Qt,QTimer,QSocketNotifier
from Xlib import display
app=QApplication(['BrisaFullscreenFixture']);folder=Path(sys.argv[1]);count=0
class Game(QWidget):
 def mousePressEvent(self,event):
  global count
  count+=1;(folder/'clicks.json').write_text(json.dumps({'count':count}));event.accept()
w=Game();w.setWindowTitle('Brisa fullscreen input fixture');w.resize(500,300);w.setStyleSheet('background:#164461;color:white;font-size:24px');box=QVBoxLayout(w);label=QLabel('Prueba de pantalla completa\nEl borde debe seguir perteneciendo a esta ventana.');label.setAttribute(Qt.WA_TransparentForMouseEvents);box.addWidget(label);w.show()
def ready():
 d=display.Display();d.create_resource_object('window',int(w.winId())).set_wm_class('BrisaFullscreenFixture','BrisaFullscreenFixture');d.sync();d.close();(folder/'window.json').write_text(json.dumps({'id':int(w.winId())}));(folder/'clicks.json').write_text('{"count":0}')
QTimer.singleShot(250,ready);notifier=QSocketNotifier(sys.stdin.fileno(),QSocketNotifier.Read)
def command(*_):
 if sys.stdin.readline().strip()=='quit':app.quit()
notifier.activated.connect(command);app.exec()
