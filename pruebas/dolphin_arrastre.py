"""Real Dolphin -> Brisa XDND drag, gated by actual source/target ownership."""
import base64,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from Xlib import display,X,protocol
from Xlib.ext import xtest
from dock import Dock
from x11_previews import capture
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
profile=ROOT/'perfiles/dolphin-arrastre';profile.mkdir(parents=True,exist_ok=True)
origin=profile/'BRISA-ORIGEN-ARRASTRE';origin.mkdir(exist_ok=True);file=origin/'BRISA prueba.txt';file.write_text('Original de ensayo de arrastre. No mover ni ejecutar.\n')
expected=hashlib.sha256(file.read_bytes()).hexdigest()
(profile/'settings.json').write_text(json.dumps(dict(pins=[],edge='left',auto_hide=False,show_recent=False,screen_mode='primary')))
app.setProperty('brisaProfileDir',str(profile));d=display.Display();r=d.screen().root;atom=d.intern_atom
original_cursor=QCursor.pos();value=r.get_full_property(atom('_NET_ACTIVE_WINDOW'),X.AnyPropertyType);original_active=int(value.value[0]) if value else None
initial=set(int(h) for h in r.get_full_property(atom('_NET_CLIENT_LIST'),X.AnyPropertyType).value)
command=profile/'accion.json';command.unlink(missing_ok=True)
dock=Dock();source=None;source_frame=None;report={};finished=False
log=(profile/'dolphin.log').open('w');subprocess.Popen(['dolphin','--new-window',str(origin)],stdout=log,stderr=subprocess.STDOUT)
def message(w,name,values):
 event=protocol.event.ClientMessage(window=w.id,client_type=atom(name),data=(32,values));r.send_event(event,event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);d.flush()
def frame_of(w):
 current=w
 for _ in range(8):
  parent=current.query_tree().parent
  if parent.id==r.id:return current
  current=parent
 raise RuntimeError('Marco de ventana no encontrado')
def title(w):
 value=w.get_full_property(atom('_NET_WM_NAME'),X.AnyPropertyType)
 return bytes(value.value).decode('utf-8','replace') if value else (w.get_wm_name() or '')
def finish():
 global finished
 if finished:return
 finished=True
 if source:
  try:message(source,'_NET_CLOSE_WINDOW',[0,2,0,0,0])
  except Exception:pass
 dock.close();log.close();QCursor.setPos(original_cursor)
 if original_active:
  try:message(d.create_resource_object('window',original_active),'_NET_ACTIVE_WINDOW',[2,0,0,0,0])
  except Exception:pass
 d.close();app.quit()
 (ROOT/'pruebas/dolphin-arrastre.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
def prepare():
 global source,source_frame
 try:
  for _ in range(60):
   handles=r.get_full_property(atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
   for h in handles.value:
    w=d.create_resource_object('window',int(h))
    if int(h) not in initial and 'dolphin' in (w.get_wm_class() or ()) and origin.name in title(w):source=w;break
   if source:break
   QTest.qWait(150)
  assert source,'No hay una ventana Dolphin nueva del origen de ensayo'
  area=app.primaryScreen().availableGeometry();flags=(15<<8)|(2<<12)
  message(source,'_NET_MOVERESIZE_WINDOW',[flags,area.left()+230,area.top()+70,min(900,area.width()-260),min(580,area.height()-150)])
  message(source,'_NET_WM_STATE',[1,atom('_NET_WM_STATE_ABOVE'),0,2,0]);message(source,'_NET_ACTIVE_WINDOW',[2,0,0,0,0]);QTest.qWait(700)
  source_frame=frame_of(source);source_frame.configure(stack_mode=X.Above);d.sync()
  g=source.get_geometry();point=r.translate_coords(source,round(g.width*.5),round(g.height*.5));xtest.fake_input(d,X.MotionNotify,x=point.x,y=point.y);source.set_input_focus(X.RevertToParent,X.CurrentTime);d.sync()
  # Ctrl+1 chooses Dolphin's icon view. No text is typed or file opened.
  from Xlib import XK
  ctrl=d.keysym_to_keycode(XK.string_to_keysym('Control_L'));key=d.keysym_to_keycode(XK.string_to_keysym('1'))
  for code in [ctrl,key]:xtest.fake_input(d,X.KeyPress,code)
  for code in [key,ctrl]:xtest.fake_input(d,X.KeyRelease,code)
  d.sync();QTest.qWait(700)
  pid=int(source.get_full_property(atom('_NET_WM_PID'),X.AnyPropertyType).value[0]);fg=source_frame.get_geometry();image=capture(d,source.id,pid,(fg.width,fg.height));assert image
  (ROOT/'pruebas/dolphin-origen.png').write_bytes(base64.b64decode(image))
  metadata=dict(source_id=source.id,frame_id=source_frame.id,frame_width=fg.width,frame_height=fg.height,origin=str(origin),command=str(command))
  (profile/'escena.json').write_text(json.dumps(metadata,indent=2)+'\n');print('READY',json.dumps(metadata),flush=True)
 except Exception as error:report.update(result='FAIL',error=repr(error));finish()
def poll():
 if finished or not command.exists():return
 try:
  action=json.loads(command.read_text());command.unlink()
  if action['action']=='close':report.update(result='CANCELLED');finish();return
  assert action['action']=='drag' and source is not None
  x,y=map(int,action['point']);g=source_frame.get_geometry();assert 0<=x<g.width and 0<=y<g.height
  source_frame.configure(stack_mode=X.Above);d.sync();message(source,'_NET_ACTIVE_WINDOW',[2,0,0,0,0]);QTest.qWait(250)
  point=r.translate_coords(source_frame,x,y);xtest.fake_input(d,X.MotionNotify,x=point.x,y=point.y);d.sync();QTest.qWait(100)
  assert r.query_pointer().child.id==source_frame.id,'El origen está cubierto; no se inició el arrastre'
  target=next((rect.center() for item,rect in zip(dock.items,dock.rects) if item.get('symbol') in ('add','apps','download')),dock.rects[0].center());end=dock.mapToGlobal(target.toPoint())
  xtest.fake_input(d,X.ButtonPress,1);d.sync();QTest.qWait(150)
  try:
   for i in range(1,31):
    xtest.fake_input(d,X.MotionNotify,x=round(point.x+(end.x()-point.x)*i/30),y=round(point.y+(end.y()-point.y)*i/30));d.sync();QTest.qWait(25)
   QTest.qWait(300)
  finally:xtest.fake_input(d,X.ButtonRelease,1);d.sync()
  for _ in range(40):
   QTest.qWait(100)
   if any(pin['path']==str(file) for pin in dock.pins):break
  assert any(pin['path']==str(file) for pin in dock.pins),'Dolphin no entregó el archivo al Dock'
  assert file.exists() and hashlib.sha256(file.read_bytes()).hexdigest()==expected,'El original cambió'
  assert json.loads((profile/'settings.json').read_text())['pins']==dock.pins
  report.update(result='PASS',real_dolphin_drag=True,original_unchanged=True,pin_saved=True,source=str(file))
 except Exception as error:report.update(result='FAIL',error=repr(error))
 finish()
timer=QTimer();timer.timeout.connect(poll);timer.start(150)
QTimer.singleShot(200,prepare)
def timeout():
 if not finished:report.update(result='TIMEOUT',error='No se recibió un gesto de ensayo');finish()
QTimer.singleShot(180000,timeout);app.exec()
