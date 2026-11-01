#!/usr/bin/env bash
set -u
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
printf '%s\n' 'Brisa Dock — diagnóstico del entorno Linux (sin cambios en el sistema)'
printf 'Escritorio: %s\n' "${XDG_CURRENT_DESKTOP:-no indicado}"
printf 'Tipo de sesión: %s\n' "${XDG_SESSION_TYPE:-no indicado}"
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
  printf '%s\n' 'Wayland detectado: lanzador disponible; control nativo de ventanas pendiente.'
elif [ -n "${DISPLAY:-}" ]; then
  printf '%s\n' 'Pantalla X11/XWayland detectada. El control de ventanas requiere una sesión X11 real.'
else
  printf '%s\n' 'No se detectó una pantalla de escritorio.'
fi
if [ -x .venv/bin/python ]; then
  task_python=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  task_python=python3
else
  printf '%s\n' 'Python 3: no encontrado.'
  exit 1
fi
"$task_python" -c 'import sys, importlib.util; print("Python:", sys.version.split()[0]); print("PySide6:", "disponible" if importlib.util.find_spec("PySide6") else "no instalado"); print("python-xlib:", "disponible" if importlib.util.find_spec("Xlib") else "no instalado")'
if command -v gio >/dev/null 2>&1; then
  printf '%s\n' 'GIO: disponible.'
else
  printf '%s\n' 'GIO: no encontrado. El lanzador .desktop lo necesita.'
fi
printf '%s\n' 'Este informe no demuestra que la interfaz ni el control de ventanas funcionen en este equipo.'
