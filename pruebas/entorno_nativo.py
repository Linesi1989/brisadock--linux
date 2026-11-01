import json,os,sys
from pathlib import Path
from Xlib import display,X
from PySide6.QtWidgets import QApplication
app=QApplication([]);d=display.Display();r=d.screen().root
value=r.get_full_property(d.intern_atom('_NET_SUPPORTING_WM_CHECK'),X.AnyPropertyType)
name='unknown'
if value and len(value.value):
 w=d.create_resource_object('window',int(value.value[0]));p=w.get_full_property(d.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
 name=bytes(p.value).decode('utf-8','replace') if p else w.get_wm_name()
report=dict(wm=name,session=os.environ.get('XDG_SESSION_TYPE'),desktop=os.environ.get('XDG_CURRENT_DESKTOP'),wayland=os.environ.get('WAYLAND_DISPLAY'),screens=[dict(name=s.name(),geometry=[s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()],dpi=s.devicePixelRatio()) for s in app.screens()])
Path(__file__).with_name('entorno-nativo.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));d.close()
