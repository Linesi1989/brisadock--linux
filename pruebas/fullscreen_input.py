"""Real KDE/X11 regression: every dock edge passes clicks to fullscreen clients."""
import sys,json,time,subprocess,os
from pathlib import Path
R=Path(os.environ.get('BRISADOCK_SOURCE_ROOT',Path(__file__).resolve().parents[1]));sys.path.insert(0,str(R/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QEventLoop,QPoint
from PySide6.QtGui import QCursor
from Xlib import display,X,protocol
from Xlib.ext import xtest
from dock import Dock
app=QApplication(['BrisaDockTest']);folder=Path(os.environ.get('BRISADOCK_TEST_OUTPUT',R/'pruebas/fullscreen-input'));folder.mkdir(exist_ok=True);profile=folder/'profile';profile.mkdir(exist_ok=True);(profile/'settings.json').write_text(json.dumps({'pins':[],'auto_hide':True,'hide_fullscreen':True,'reserve_space':False,'show_recent':False,'screen_mode':'primary'}));app.setProperty('brisaProfileDir',str(profile))
d=display.Display();root=d.screen().root;atom=d.intern_atom;original=QCursor.pos();active=root.get_full_property(atom('_NET_ACTIVE_WINDOW'),X.AnyPropertyType);oldactive=int(active.value[0]) if active else None;fixture=None;dock=None;rows=[];result={'result':'FAIL'}
def pause(ms):
 loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
def wait(fn,seconds=8):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  pause(80)
  if fn():return
 raise AssertionError('Timed out')
def prop(name):
 p=root.get_full_property(atom(name),X.AnyPropertyType);return list(p.value) if p else []
def msg(name,values):root.send_event(protocol.event.ClientMessage(window=handle,client_type=atom(name),data=(32,values)),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.flush()
try:
 (folder/'window.json').unlink(missing_ok=True);dock=Dock();fixture=subprocess.Popen([sys.executable,str(Path(os.environ.get('BRISADOCK_FIXTURE',R/'pruebas/fullscreen_game_fixture.py'))),str(folder)],stdin=subprocess.PIPE,text=True);wait((folder/'window.json').exists);handle=json.loads((folder/'window.json').read_text())['id'];area=app.primaryScreen().geometry()
 for auto in [False,True]:
  dock.set_preference('auto_hide',auto)
  for edge in ['bottom','left','right']:
   dock.set_preference('edge',edge);msg('_NET_WM_STATE',[1,atom('_NET_WM_STATE_FULLSCREEN'),0,2,0]);msg('_NET_ACTIVE_WINDOW',[2,0,0,0,0]);wait(lambda:dock.fullscreen_active and not dock.isVisible());selected=[];dock.launch=lambda *a:selected.append(a)
   point=QPoint(area.center().x(),area.bottom()-1) if edge=='bottom' else QPoint(area.left()+1 if edge=='left' else area.right()-1,area.center().y());QCursor.setPos(point);pause(900)
   assert dock.hidden_amount==1 and not dock.isVisible();assert dock.fullscreen_shelf is None or not dock.fullscreen_shelf.isVisible();assert prop('_NET_ACTIVE_WINDOW')==[handle]
   before=json.loads((folder/'clicks.json').read_text())['count'];xtest.fake_input(d,X.MotionNotify,x=point.x(),y=point.y());xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1);d.sync();wait(lambda:json.loads((folder/'clicks.json').read_text())['count']>before)
   assert not selected and prop('_NET_ACTIVE_WINDOW')==[handle]
   rows.append({'auto_hide':auto,'edge':edge,'dock_unmapped':True,'game_received_real_edge_click':True,'game_focus_preserved':True})
   msg('_NET_WM_STATE',[0,atom('_NET_WM_STATE_FULLSCREEN'),0,2,0]);wait(lambda:not dock.fullscreen_active);QCursor.setPos(point);wait(lambda:dock.isVisible() and dock.hidden_amount<.1)
   rows[-1]['normal_edge_reveal_restored']=True
 # Maximized windows must retain normal dock behavior.
 msg('_NET_WM_STATE',[1,atom('_NET_WM_STATE_MAXIMIZED_HORZ'),atom('_NET_WM_STATE_MAXIMIZED_VERT'),2,0]);pause(500);assert not dock.fullscreen_active;dock.reveal_instance();wait(lambda:dock.isVisible() and dock.hidden_amount<.1)
 result={'result':'PASS','scope':'Real KDE/X11 synthetic client, six edge/auto-hide combinations, physical XTest clicks and restore; no claim of actual game engine gameplay','cases':rows,'maximized_window_not_blocked':True}
except Exception as e:
 import traceback;result.update(error=repr(e),traceback=traceback.format_exc(),cases=rows)
finally:
 if dock:dock.close()
 if fixture and fixture.poll() is None:fixture.stdin.write('quit\n');fixture.stdin.flush();fixture.wait(timeout=8)
 QCursor.setPos(original)
 if oldactive:
  root.send_event(protocol.event.ClientMessage(window=oldactive,client_type=atom('_NET_ACTIVE_WINDOW'),data=(32,[2,0,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.flush()
 d.close();pause(200)
(folder/'RESULT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));sys.exit(result['result']!='PASS')
