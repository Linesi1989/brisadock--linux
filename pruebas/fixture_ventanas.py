import json,sys
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QVBoxLayout
from PySide6.QtCore import QTimer,QSocketNotifier
from Xlib import display
app=QApplication(['BrisaFixture'])
windows=[]
for i,color in enumerate(('#e84040','#3285db')):
 w=QWidget();w.setWindowTitle('Brisa ensayo '+str(i+1));w.resize(520,330);w.move(180+i*40,170+i*40)
 layout=QVBoxLayout(w);layout.addWidget(QLabel('Ventana propia de ensayo '+str(i+1)))
 w.setStyleSheet('background:'+color+';color:white;font-size:24px');w.show();windows.append(w)
def ready():
 d=display.Display()
 for w in windows:d.create_resource_object('window',int(w.winId())).set_wm_class('brisa-fixture','BrisaFixture')
 d.sync();d.close()
 Path(sys.argv[1]).write_text(json.dumps([int(w.winId()) for w in windows]))
QTimer.singleShot(250,ready)
notifier=QSocketNotifier(sys.stdin.fileno(),QSocketNotifier.Read)
def command(*_):
 line=sys.stdin.readline().strip()
 if line=='green':windows[0].setStyleSheet('background:#20c060;color:white;font-size:24px')
 elif line=='quit' or not line:app.quit()
notifier.activated.connect(command)
app.exec()
