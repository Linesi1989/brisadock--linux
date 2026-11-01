import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from dock import Dock
from instance import InstanceGuard
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
profile=ROOT/'perfiles/validacion';profile.mkdir(parents=True,exist_ok=True)
settings={'size':16,'edge':'left','gap':20,'auto_hide':False,'pins':[], 'clave_futura':{'conservar':True}}
(profile/'settings.json').write_text(json.dumps(settings))
app.setProperty('brisaProfileDir',str(profile))
guard=InstanceGuard(profile,app);assert guard.owner and not guard.error
dock=Dock();report={}
def validate():
 try:
  dock.save()
  saved=json.loads((profile/'settings.json').read_text())
  assert saved['clave_futura']==settings['clave_futura'] and saved['size']==16
  second=subprocess.run([sys.executable,str(ROOT/'src/dock.py'),'--profile-dir',str(profile),'--smoke-test'],capture_output=True,text=True,timeout=5)
  assert second.returncode==0,second.stderr
  assert dock.watcher.backend and 'X11' in dock.watcher.backend.status
  shot=app.primaryScreen().grabWindow(int(dock.winId()));assert not shot.isNull()
  shot.save(str(ROOT/'pruebas/brisa-x11.png'))
  report.update(settings_preserved=True,second_instance_exit=second.returncode,backend=dock.watcher.backend.status,windows=len(dock.watcher.backend.snapshot()),screenshot='brisa-x11.png')
 except Exception as e:report['error']=repr(e)
 finally:
  dock.close();guard.close();app.quit()
QTimer.singleShot(1500,validate)
app.exec()
(ROOT/'pruebas/validacion-nativa.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report));sys.exit(1 if 'error' in report else 0)
