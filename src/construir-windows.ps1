$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .build-env
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python.' }
& .\.build-env\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.12.0
if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de dependencias.' }
& .\.build-env\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --name BrisaDock --distpath Windows-0.11 --workpath .build --specpath .build dock.py
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
