import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from dock import Dock
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
folder=ROOT/'perfiles/estabilidad-sesion';folder.mkdir(parents=True,exist_ok=True)
(folder/'settings.json').write_text(json.dumps(dict(pins=[],auto_hide=True,edge='left',show_recent=False,screen_mode='primary')))
app.setProperty('brisaProfileDir',str(folder));dock=Dock();samples=[];start=time.monotonic()
def sample():
 status=Path('/proc/self/status').read_text();fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.splitlines() if ':' in line}
 samples.append(dict(seconds=round(time.monotonic()-start,1),rss_kib=int(fields['VmRSS'].split()[0]),threads=int(fields['Threads']),windows=len(dock.windows),hidden=dock.hidden_amount))
 print(json.dumps(samples[-1]),flush=True)
 (ROOT/'pruebas/estabilidad-sesion.json').write_text(json.dumps(dict(status='RUNNING',samples=samples),indent=2))
def finish():
 sample();dock.close();app.quit()
timer=QTimer();timer.timeout.connect(sample);timer.start(30000)
QTimer.singleShot(10000,sample);QTimer.singleShot(180000,finish);app.exec()
report=dict(result='PASS',duration_seconds=round(time.monotonic()-start,1),samples=samples,note='Ensayo de 3 minutos en sesión real; no sustituye una jornada de uso ni suspensión/cable físicos.')
(ROOT/'pruebas/estabilidad-sesion.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS cierre',flush=True)
