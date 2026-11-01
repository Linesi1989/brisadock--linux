#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null; then
  echo 'Instala Python 3: sudo apt install python3 python3-venv'
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo 'Se necesita Python 3.10 o posterior. No se modificó el sistema.'
  exit 1
}
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv || { echo 'Instala python3-venv: sudo apt install python3-venv'; exit 1; }
fi
if ! .venv/bin/python -c 'import PySide6, Xlib' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
# X11 permite posicionar una ventana independiente en KDE. En una sesión
# Wayland se usa XWayland; el compositor todavía puede limitar la posición.
export QT_QPA_PLATFORM=xcb
exec .venv/bin/python dock.py "$@"
