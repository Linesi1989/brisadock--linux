import json,sys,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,Qt,QEventLoop,QTimer
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from Xlib import display,X,protocol
from dock import Dock
from display_policy import screen_identity
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
folder=ROOT/'perfiles/superficie';folder.mkdir(parents=True,exist_ok=True)
(folder/'settings.json').write_text(json.dumps(dict(pins=[],edge='left',auto_hide=False,show_recent=False,screen_mode='primary',hide_delay=.2)))
app.setProperty('brisaProfileDir',str(folder));d=display.Display();root=d.screen().root;atom=d.intern_atom;original=QCursor.pos()
active=root.get_full_property(atom('_NET_ACTIVE_WINDOW'),X.AnyPropertyType);original_active=int(active.value[0]) if active else None
report={};dock=None;fixture=None

def pause(milliseconds):
 loop=QEventLoop();QTimer.singleShot(milliseconds,loop.quit);loop.exec()

def prop(window,name):
 value=window.get_full_property(atom(name),X.AnyPropertyType);return list(value.value) if value else []
def wait(fn,seconds=6):
 for _ in range(round(seconds*10)):
  pause(100)
  if fn():return True
 return False
def message(handle,name,values):
 event=protocol.event.ClientMessage(window=handle,client_type=atom(name),data=(32,values));root.send_event(event,event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.flush()
try:
 initial=prop(root,'_NET_WORKAREA');dock=Dock();pause(1000)
 dock.set_preference('reserve_space',True);pause(500)
 resource=d.create_resource_object('window',int(dock.winId()))
 hints=prop(resource,'_NET_WM_STRUT_PARTIAL');assert len(hints)==12 and hints[0]>0,hints
 assert wait(lambda:prop(root,'_NET_WORKAREA')!=initial),(initial,prop(root,'_NET_WORKAREA'))
 dock.set_preference('reserve_space',False);assert wait(lambda:prop(root,'_NET_WORKAREA')==initial)
 report['reservation_and_restore']=True
 screens=app.screens()
 if len(screens)>1:
  primary=app.primaryScreen();other=next(s for s in screens if s is not primary)
  dock.set_preference('screen_mode','follow_edge');pause(100)
  area=other.geometry();QCursor.setPos(QPoint(area.left(),area.center().y()))
  assert wait(lambda:dock.dock_screen is other),'No sigue el borde'
  dock.menu_open=True;area=primary.geometry();QCursor.setPos(QPoint(area.left(),area.center().y()));pause(700)
  assert dock.dock_screen is other,'Se traslada durante un menú'
  dock.menu_open=False;assert wait(lambda:dock.dock_screen is primary)
  report['one_dock_handoff_and_menu_lock']=True
 # Test keyboard navigation without opening user applications.
 selected=[];dock.launch=lambda index,*_:selected.append(index)
 dock.keyboard_focus();pause(250);panel=dock.keyboard_panel;assert panel is not None
 QTest.keyClick(panel.list,Qt.Key_Down);QTest.keyClick(panel.list,Qt.Key_Return);pause(150)
 assert selected==[1] and dock.keyboard_panel is None and not dock.menu_open,selected
 report['keyboard_navigation_and_clean_close']=True
 from trash_linux import read_state
 trash=read_state();assert trash['available'],trash
 assert wait(lambda:dock.trash_count is not None),dict(provider=trash,integration=dock.integration_status,menu_open=dock.menu_open,watcher_running=dock.watcher.isRunning(),phase=dock.watcher.phase,backend=type(dock.watcher.backend).__name__)
 report['trash_state_read_only']=dict(trash,no_deletions=True)
 # Fullscreen only the fixture; no real user window is minimized or closed.
 ids=folder/'fixture.json';ids.unlink(missing_ok=True)
 fixture=subprocess.Popen([sys.executable,str(ROOT/'pruebas/fixture_ventanas.py'),str(ids)],stdin=subprocess.PIPE,text=True)
 assert wait(ids.exists);handle=json.loads(ids.read_text())[0]
 dock.set_preference('screen_mode','primary');dock.set_preference('auto_hide',False)
 QCursor.setPos(app.primaryScreen().geometry().center())
 message(handle,'_NET_WM_STATE',[1,atom('_NET_WM_STATE_FULLSCREEN'),0,2,0]);message(handle,'_NET_ACTIVE_WINDOW',[2,0,0,0,0])
 assert wait(lambda:dock.fullscreen_active),'KWin no comunica pantalla completa activa'
 assert wait(lambda:dock.hidden_amount>.98),'No se oculta en pantalla completa'
 report['fullscreen_hide_own_fixture']=True
 area=app.primaryScreen().geometry();QCursor.setPos(QPoint(area.left(),area.center().y()))
 assert wait(lambda:dock.hidden_amount<.02),'No reaparece desde el borde'
 stacking=prop(root,'_NET_CLIENT_LIST_STACKING')
 mirror=dock.fullscreen_shelf
 assert mirror is not None and mirror.isVisible(),'No hay superficie propia visible'
 frame=d.create_resource_object('window',handle)
 for _ in range(8):
  parent=frame.query_tree().parent
  if parent.id==root.id:break
  frame=parent
 children=[w.id for w in root.query_tree().children]
 above=children.index(int(mirror.winId()))>children.index(frame.id)
 preserved=(prop(root,'_NET_ACTIVE_WINDOW')==[handle])
 assert above and preserved,dict(above=above,preserved=preserved)
 report['fullscreen_edge_reveal_without_focus']=dict(own_shelf_visible=True,above_fixture=above,active_window_preserved=preserved)
 assert not mirror.mask().isEmpty()
 hover=dock.mapToGlobal(dock.rects[0].center().toPoint());QCursor.setPos(hover);pause(150)
 assert root.query_pointer().child.id==int(mirror.winId()),'El estante no recibe el puntero'
 assert prop(root,'_NET_ACTIVE_WINDOW')==[handle],'Se perdió el foco de la ventana fullscreen'
 QTest.mouseClick(mirror,Qt.LeftButton,Qt.NoModifier,dock.rects[0].center().toPoint());pause(100)
 assert selected[-1]==0,'No se activó el elemento del estante propio'
 report['fullscreen_edge_reveal_without_focus']['input_forwarding_tested']=True
 mirror.grab().save(str(ROOT/'pruebas/pantalla-completa-estante.png'))
 message(handle,'_NET_WM_STATE',[0,atom('_NET_WM_STATE_FULLSCREEN'),0,2,0]);pause(200)
 report['result']='PASS'
except Exception as error:report.update(result='FAIL',error=repr(error))
finally:
 if dock:dock.close()
 if fixture and fixture.poll() is None:
  fixture.stdin.write('quit\n');fixture.stdin.flush()
  try:fixture.wait(timeout=3)
  except subprocess.TimeoutExpired:fixture.terminate();fixture.wait()
 QCursor.setPos(original)
 if original_active:
  try:message(original_active,'_NET_ACTIVE_WINDOW',[2,0,0,0,0])
  except Exception:pass
 d.close();pause(200)
(ROOT/'pruebas/bloque-superficie.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));sys.exit(report['result']!='PASS')
