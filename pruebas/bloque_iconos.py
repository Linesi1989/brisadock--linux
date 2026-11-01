import json,sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication,QFileIconProvider
from linux_icons import PersistentIcons
app=QApplication([]);provider=QFileIconProvider()
folder=ROOT/'perfiles/bloque-iconos';folder.mkdir(parents=True,exist_ok=True)
cache_dir=folder/'cache';cache_dir.mkdir(exist_ok=True)
for p in cache_dir.iterdir():p.unlink()
paths=[]
for i in range(160):
 icon=folder/f'icon-{i}.svg';icon.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" fill="#{i*7919%0xffffff:06x}"/></svg>')
 desktop=folder/f'app-{i}.desktop';desktop.write_text(f'[Desktop Entry]\nType=Application\nName=App {i}\nExec=/bin/true\nIcon={icon}\n');paths.append(str(desktop))
first=PersistentIcons(cache_dir)
assert all(not first.get(path,provider).isNull() for path in paths)
assert first.extractions==160
second=PersistentIcons(cache_dir)
assert all(not second.get(path,provider).isNull() for path in paths)
assert second.extractions==0 and second.disk_hits==160
icon=folder/'icon-50.svg';icon.write_text(icon.read_text().replace('width="128" height="128" fill','width="127" height="128" fill'))
third=PersistentIcons(cache_dir)
for path in paths:third.get(path,provider)
assert third.extractions==1 and third.disk_hits==159
import hashlib
key=hashlib.sha256(paths[30].encode()).hexdigest();(cache_dir/(key+'.png')).write_bytes(b'corrupt')
fourth=PersistentIcons(cache_dir)
for path in paths:assert not fourth.get(path,provider).isNull()
assert fourth.extractions==1
with tempfile.TemporaryDirectory(prefix='brisa-cache-') as temp:
 readonly=Path(temp)/'readonly';readonly.mkdir();readonly.chmod(0o555)
 try:
  fallback=PersistentIcons(readonly)
  assert not fallback.get(paths[0],provider).isNull()
  assert not list(readonly.iterdir()),'La carpeta de ensayo no era solo lectura'
 finally:readonly.chmod(0o755)
report=dict(result='PASS',entries=160,first_extractions=160,restart_extractions=0,restart_disk_hits=160,changed_resource_extractions=1,corrupt_entry_regenerated=1,read_only_fallback=True,no_empty_icons=True)
(ROOT/'pruebas/bloque-iconos.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
