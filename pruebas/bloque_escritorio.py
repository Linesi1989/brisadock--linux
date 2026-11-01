import json,sys,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from dock import Dock
from panels import FolderPanel,PreferencesPanel
from Xlib import display,X,protocol
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
profile=ROOT/'perfiles/bloque-escritorio';profile.mkdir(parents=True,exist_ok=True)
(profile/'settings.json').write_text(json.dumps(dict(pins=[],auto_hide=True,hide_delay=.2,edge='bottom',show_recent=False)))
app.setProperty('brisaProfileDir',str(profile))
original=QCursor.pos();dock=None;panel=None;fixture=None;report={};d=display.Display();r=d.screen().root
atom=d.intern_atom
def wait_until(fn,seconds=5):
 for _ in range(int(seconds*10)):
  QTest.qWait(100)
  if fn():return True
 return False
try:
 ids=profile/'fixture.json';ids.unlink(missing_ok=True)
 fixture=subprocess.Popen([sys.executable,str(ROOT/'pruebas/fixture_ventanas.py'),str(ids)],stdin=subprocess.PIPE,text=True)
 assert wait_until(ids.exists)
 handle=json.loads(ids.read_text())[0]
 ev=protocol.event.ClientMessage(window=handle,client_type=atom('_NET_WM_STATE'),data=(32,[1,atom('_NET_WM_STATE_MAXIMIZED_VERT'),atom('_NET_WM_STATE_MAXIMIZED_HORZ'),2,0]))
 r.send_event(ev,event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.flush();QTest.qWait(400)
 resource=d.create_resource_object('window',handle)
 states=resource.get_full_property(atom('_NET_WM_STATE'),X.AnyPropertyType).value
 assert atom('_NET_WM_STATE_MAXIMIZED_VERT') in states and atom('_NET_WM_STATE_MAXIMIZED_HORZ') in states,'Fixture no maximizada'
 dock=Dock();QTest.qWait(300)
 tested=[]
 for screen in app.screens():
  dock.set_preference('screen_id',__import__('display_policy').screen_identity(screen));dock.set_preference('screen_mode','selected');QTest.qWait(300)
  for edge in ['bottom','left','right']:
   dock.set_preference('edge',edge)
   area=screen.geometry();QCursor.setPos(area.center())
   assert wait_until(lambda:dock.hidden_amount>.98),(screen.name(),edge,'no se oculta',dock.hidden_amount)
   point=QPoint(area.center().x(),area.bottom()) if edge=='bottom' else QPoint(area.left() if edge=='left' else area.right(),area.center().y())
   QCursor.setPos(point)
   assert wait_until(lambda:dock.hidden_amount<.02),(screen.name(),edge,'no reaparece',dock.hidden_amount)
   tested.append([screen.name(),edge])
   if len(tested)==1:app.primaryScreen().grabWindow(int(dock.winId())).save(str(ROOT/'pruebas/autoocultamiento-x11.png'))
 report['auto_hide_reveal_real_pointer']=tested
 report['maximized_fixture_present']=True
 dock.set_preference('auto_hide',False);dock.set_preference('screen_mode','primary');dock.set_preference('edge','left');QTest.qWait(400)
 # Directory watcher, natural sort, per-folder persistence and old-result rejection.
 folder=profile/'carpeta';folder.mkdir(exist_ok=True)
 for p in folder.iterdir():
  if p.is_file():p.unlink()
 for name in ['archivo10.txt','archivo2.txt','Árbol1.txt']:(folder/name).write_text('prueba')
 panel=FolderPanel(dock,dict(name='Carpeta de ensayo',path=str(folder)));panel.show()
 assert wait_until(lambda:panel.list.count()==3)
 panel.order.setCurrentIndex(panel.orders.index('name'));assert wait_until(lambda:panel.list.count()==3)
 names=[panel.list.item(i).text() for i in range(panel.list.count())]
 assert names.index('archivo2.txt')<names.index('archivo10.txt'),names
 panel.mode.setCurrentIndex(2);QTest.qWait(200)
 dock.add_path(str(folder));panel.display.setCurrentIndex(1)
 assert wait_until(lambda:str(folder.resolve()) in dock.folder_stacks.icons),'Pila no generada'
 assert not dock.icon_for(dict(path=str(folder))).isNull()
 report['folder_stack_icon_live']=True
 app.primaryScreen().grabWindow(int(panel.winId())).save(str(ROOT/'pruebas/carpeta-abanico-x11.png'))
 (folder/'nuevo.txt').write_text('nuevo')
 assert wait_until(lambda:panel.list.count()==4),'Watcher no actualiza carpeta'
 assert panel.folder_preferences()['display']=='stack'
 stale=panel.generation-1;panel.directory_ready(stale,[],0,'error antiguo');assert panel.list.count()==4
 panel.close();panel.deleteLater();panel=None;QTest.qWait(200)
 panel=FolderPanel(dock,dict(name='Carpeta de ensayo',path=str(folder)));panel.show();QTest.qWait(300)
 assert panel.mode.currentIndex()==2 and panel.orders[panel.order.currentIndex()]=='name'
 report['folder_natural_order_watcher_preferences']=True
 panel.close();panel.deleteLater();panel=None;QTest.qWait(100)
 panel=PreferencesPanel(dock);panel.show();QTest.qWait(200)
 dock.set_appearance('dock_color','#365070');dock.set_appearance('dock_alpha',180)
 dock.set_appearance('folder_color','#f1e9db');dock.set_appearance('folder_alpha',240)
 assert dock.appearance['dock_color']=='#365070'
 panel.close();panel.deleteLater();panel=None;QTest.qWait(100)
 # 240 open/close cycles; drain workers to detect disposal mistakes.
 for i in range(240):
  panel=FolderPanel(dock,dict(name='Ciclos',path=str(folder)));panel.show();QTest.qWait(12)
  panel.close();panel.deleteLater();panel=None;QTest.qWait(12)
  if (i+1)%40==0:print('CICLOS',i+1,flush=True)
 report['folder_panel_open_close_cycles']=240
 saved=json.loads((profile/'settings.json').read_text());assert saved['appearance']['dock_alpha']==180
 dock.close();dock=None;QTest.qWait(200)
 report['result']='PASS'
except Exception as error:
 if dock:report['diagnostic']=dict(cursor=[QCursor.pos().x(),QCursor.pos().y()],dock=[dock.x(),dock.y(),dock.width(),dock.height()],hidden=dock.hidden_amount,auto_hide=dock.auto_hide,menu=dock.menu_open,pressed=str(dock.press_pos),last_inside_age=time.monotonic()-dock.last_inside,screen=dock.dock_screen.name(),screen_mode=dock.screen_mode,external_drag=dock.external_drag)
 report['error']=repr(error);report['result']='FAIL'
finally:
 if panel:panel.close();panel.deleteLater()
 if dock:dock.close()
 if fixture and fixture.poll() is None:
  fixture.stdin.write('quit\n');fixture.stdin.flush()
  try:fixture.wait(timeout=3)
  except subprocess.TimeoutExpired:fixture.terminate();fixture.wait()
 QCursor.setPos(original);d.close();QTest.qWait(300)
(ROOT/'pruebas/bloque-escritorio.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));sys.exit(report['result']!='PASS')
