import json,sys,subprocess,time,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from dock import Dock
from desktop_backend import X11Backend,merge_items,canonical
from linux_desktop import DesktopIndex
from panels import WindowPanel
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
folder=ROOT/'perfiles/bloque-ventanas';folder.mkdir(parents=True,exist_ok=True)
(folder/'settings.json').write_text(json.dumps(dict(pins=[],edge='left',show_recent=False)))
app.setProperty('brisaProfileDir',str(folder))
ids=folder/'fixture.json';ids.unlink(missing_ok=True)
fixture=subprocess.Popen([sys.executable,str(ROOT/'pruebas/fixture_ventanas.py'),str(ids)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
dock=None;panel=None;backend=None;report={}
try:
 for _ in range(50):
  if ids.exists():break
  QTest.qWait(100)
 assert ids.exists(),'No aparecen las ventanas fixture'
 handles=json.loads(ids.read_text())
 desktop=folder/'brisafixture.desktop';desktop.write_text('[Desktop Entry]\nType=Application\nName=BrisaFixture\nExec='+sys.executable+'\nStartupWMClass=BrisaFixture\nIcon=utilities-terminal\n')
 backend=X11Backend();backend.desktop_index=DesktopIndex([dict(name='BrisaFixture',path=str(desktop))])
 def own():return [w for w in backend.snapshot() if w['id'] in handles]
 windows=own();assert len(windows)==2,windows
 items=merge_items([dict(name='BrisaFixture',path=str(desktop))],windows)
 assert len(items)==1 and len(items[0]['windows'])==2
 report['two_windows_one_pinned_icon']=True
 dock=Dock();QTest.qWait(600)
 panel=WindowPanel(dock,items[0]);panel.show();QTest.qWait(2500)
 if panel.preview_results!=[True,True]:
  direct=subprocess.run([sys.executable,str(ROOT/'src/x11_previews.py')],input=json.dumps(dict(generation=1,windows=windows))+'\n',text=True,capture_output=True,timeout=4)
  report['preview_diagnostic']=direct.stderr
 assert panel.preview_results==[True,True],panel.preview_results
 app.primaryScreen().grabWindow(int(panel.winId())).save(str(ROOT/'pruebas/ventanas-x11.png'))
 report['composite_previews']=True
 def capture():
  request=json.dumps(dict(generation=1,windows=[windows[0]]))+'\n'
  result=subprocess.run([sys.executable,str(ROOT/'src/x11_previews.py')],input=request,text=True,capture_output=True,timeout=3)
  encoded=json.loads(result.stdout)['images'][0]['png'];assert encoded
  image=QImage.fromData(base64.b64decode(encoded));return image.pixelColor(50,80).name()
 first=capture();fixture.stdin.write('green\n');fixture.stdin.flush();QTest.qWait(250);second=capture()
 assert first!=second,(first,second)
 report['preview_changed_while_occluded']=[first,second]
 panel.close();panel.deleteLater();panel=None;QTest.qWait(200)
 backend.minimize(windows[0]);QTest.qWait(600)
 assert next(w for w in own() if w['id']==windows[0]['id'])['minimized']
 dock.set_preference('minimize_into_app',False);QTest.qWait(1800)
 tiles=[item for item in dock.items if item.get('minimized_tile') and item['windows'][0]['id']==windows[0]['id']]
 assert len(tiles)==1 and len(tiles[0]['windows'])==1
 dock.set_preference('minimize_into_app',True);QTest.qWait(100)
 assert not any(item.get('minimized_tile') for item in dock.items)
 report['minimized_group_or_separate']=True
 backend.activate(windows[0]);QTest.qWait(600)
 assert not next(w for w in own() if w['id']==windows[0]['id'])['minimized']
 report['individual_minimize_restore']=True
 backend.close_window(windows[0]);QTest.qWait(600)
 remaining=own();assert len(remaining)==1 and remaining[0]['id']==windows[1]['id']
 report['closing_one_preserves_other']=True
 report['result']='PASS'
except Exception as error:
 report['error']=repr(error);report['result']='FAIL'
finally:
 if panel:panel.close();panel.deleteLater()
 if dock:dock.close()
 if backend:backend.close()
 if fixture.poll() is None:
  fixture.stdin.write('quit\n');fixture.stdin.flush()
  try:fixture.wait(timeout=3)
  except subprocess.TimeoutExpired:fixture.terminate();fixture.wait(timeout=3)
 QTest.qWait(200)
(ROOT/'pruebas/bloque-ventanas.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));sys.exit(report['result']!='PASS')
