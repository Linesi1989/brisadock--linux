"""Only the explicit BrisaDock/Craft validation scripts are executable here."""
import os,subprocess,sys,json,datetime,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TESTS={
 'inicio':(ROOT/'pruebas/diagnostico_inicio.py',[]),
 'dolphin':(ROOT/'pruebas/dolphin_arrastre.py',[]),
 'superficie':(ROOT/'pruebas/bloque_superficie.py',[]),
 'entorno':(ROOT/'pruebas/entorno_nativo.py',[]),
 'ventanas':(ROOT/'pruebas/bloque_ventanas.py',[]),
 'escritorio':(ROOT/'pruebas/bloque_escritorio.py',[]),
 'arrastre':(ROOT/'pruebas/bloque_arrastre.py',[]),
 'instancia':(ROOT/'pruebas/validar-nativo.py',[]),
 'limpiar-gio':(ROOT.parent/'CraftSuite-Linux/pruebas-documentos/inspeccionar_deck_gio.py',['--close']),
}
name=sys.argv[1] if len(sys.argv)==2 else None
if name not in TESTS:raise SystemExit('Pruebas permitidas: '+', '.join(TESTS))
script,args=TESTS[name];env=dict(os.environ,QT_QPA_PLATFORM='xcb')
outputs={'inicio':'diagnostico-inicio.json','ventanas':'bloque-ventanas.json','escritorio':'bloque-escritorio.json','arrastre':'bloque-arrastre.json','instancia':'validacion-nativa.json','superficie':'bloque-superficie.json','dolphin':'dolphin-arrastre.json'}
output=ROOT/'pruebas'/outputs[name] if name in outputs else None
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
if output and output.exists():
 history=ROOT/'pruebas/historial';history.mkdir(exist_ok=True)
 shutil.copy2(output,history/(stamp+'-'+output.name))
code=subprocess.call([sys.executable,str(script),*args],cwd=ROOT,env=env)
if output and output.exists():
 result=json.loads(output.read_text())
 digest=hashlib.sha256()
 for source in sorted((ROOT/'src').glob('*.py')):digest.update(source.name.encode());digest.update(source.read_bytes())
 result['verification_metadata']=dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=digest.hexdigest(),script=script.name,exit_code=code)
 output.write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(code)
