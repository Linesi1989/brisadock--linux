import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPointF,QEvent,QMimeData,QUrl
from PySide6.QtGui import QMouseEvent,QKeyEvent,QDropEvent
from PySide6.QtTest import QTest
from dock import Dock
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
folder=ROOT/'perfiles/bloque-arrastre';folder.mkdir(parents=True,exist_ok=True)
pins=[]
for i in range(3):
 p=folder/f'app{i}.desktop';p.write_text(f'[Desktop Entry]\nType=Application\nName=App {i}\nExec=/bin/true\nIcon=utilities-terminal\n');pins.append(dict(name=f'App {i}',path=str(p)))
(folder/'settings.json').write_text(json.dumps(dict(pins=pins,edge='bottom',show_recent=False)))
app.setProperty('brisaProfileDir',str(folder));dock=Dock();QTest.qWait(500);report={}
def event(kind,pos,button,buttons):return QMouseEvent(kind,QPointF(pos),QPointF(dock.mapToGlobal(pos.toPoint())),button,buttons,Qt.NoModifier)
def drag(cancel=False):
 source=next(rect.center() for item,rect in zip(dock.items,dock.rects) if item.get('pin_index')==0)
 target=next(rect.center() for item,rect in zip(dock.items,dock.rects) if item.get('pin_index')==2)
 before=(folder/'settings.json').read_bytes();original=[p['path'] for p in dock.pins]
 dock.mousePressEvent(event(QEvent.MouseButtonPress,source,Qt.LeftButton,Qt.LeftButton))
 dock.mouseMoveEvent(event(QEvent.MouseMove,target,Qt.NoButton,Qt.LeftButton));QTest.qWait(100)
 assert [p['path'] for p in dock.pins]!=original,'No hay vista previa'
 assert (folder/'settings.json').read_bytes()==before,'Se guardó antes de soltar'
 if cancel:dock.keyPressEvent(QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
 dock.mouseReleaseEvent(event(QEvent.MouseButtonRelease,target,Qt.LeftButton,Qt.NoButton));QTest.qWait(100)
 if cancel:
  assert [p['path'] for p in dock.pins]==original
  assert (folder/'settings.json').read_bytes()==before
 else:
  assert json.loads((folder/'settings.json').read_text())['pins']==dock.pins
try:
 for edge in ['bottom','left','right']:
  dock.set_preference('edge',edge);QTest.qWait(100);drag(True);drag(False)
 report['preview_cancel_commit_three_edges']=True
 path=folder/'archivo exacto.txt';path.write_text('Original conservado')
 data=QMimeData();data.setUrls([QUrl.fromLocalFile(str(path))])
 drop=QDropEvent(QPointF(5,5),Qt.CopyAction,data,Qt.LeftButton,Qt.NoModifier)
 dock.dropEvent(drop)
 assert any(pin['path']==str(path) for pin in dock.pins) and path.read_text()=='Original conservado'
 report['file_pinned_without_execution_or_move']=True
 report['result']='PASS'
except Exception as error:report.update(result='FAIL',error=repr(error))
finally:dock.close();QTest.qWait(200)
(ROOT/'pruebas/bloque-arrastre.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));sys.exit(report['result']!='PASS')
