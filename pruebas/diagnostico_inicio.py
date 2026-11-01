"""Bounded native startup diagnosis; touches only its isolated profile."""
import faulthandler,json,os,sys,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
log=(ROOT/'pruebas/diagnostico-inicio-pilas.txt').open('w')
faulthandler.enable(file=log);faulthandler.dump_traceback_later(7,file=log)
def deadline():
 time.sleep(22)
 faulthandler.dump_traceback(file=log);log.flush();os._exit(124)
threading.Thread(target=deadline,daemon=True).start()
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from dock import Dock
app=QApplication([]);app.setApplicationName('BrisaDock');app.setOrganizationName('Brisa')
folder=ROOT/'perfiles/diagnostico-inicio';folder.mkdir(exist_ok=True)
(folder/'settings.json').write_text(json.dumps(dict(pins=[],edge='left',auto_hide=True,show_recent=False)))
app.setProperty('brisaProfileDir',str(folder))
start=time.monotonic();dock=Dock()
from PySide6.QtCore import QTimer
loop_timer=QTimer()
loop_timer.timeout.connect(lambda: app.quit() if (dock.watcher.backend is not None and dock.trash_count is not None) or time.monotonic()-start>10 else None)
loop_timer.start(100)
app.exec()
report=dict(phase=dock.watcher.phase,backend=type(dock.watcher.backend).__name__,trash_count=dock.trash_count,startup_seconds=round(time.monotonic()-start,3))
(ROOT/'pruebas/diagnostico-inicio.json').write_text(json.dumps(report,indent=2))
dock.close();report['thread_stopped']=not dock.watcher.isRunning();report['result']='PASS' if report['thread_stopped'] and report['backend']!='NoneType' else 'FAIL'
(ROOT/'pruebas/diagnostico-inicio.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
faulthandler.cancel_dump_traceback_later();log.flush();os._exit(0 if report['result']=='PASS' else 1)
