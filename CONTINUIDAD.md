# BrisaDock Linux — continuidad

## Estado actual: Paridad estética y funcional macOS / Windows 0.37 completada y validada (`PASS`)

1. **Estabilidad y validación completa en X11 (`SHA-256: f74b976e3482db8678e9fd43db61353952b74c40bf3f156a0d09091db5023e1e`)**:
   - Se aisló y resolvió el bloqueo previo en `bloque_superficie.py` (`backend: NoneType` causado por `QTest.qWait` sin bucle de eventos durante la inicialización del hilo `WindowWatcher`).
   - Se completó la integración de los 35 módulos de `src/` con estética y comportamiento idénticos al Dock de macOS y paridad funcional con la referencia `0.37`:
     - `dock_icons.py`: iconos vectoriales estilo macOS (Finder bicolor sonriente, brújula Safari, Launchpad multicolor, carpeta azul de Descargas, Papelera de rejilla metálica vacía/llena).
     - `file_icons.py` + `folder_stacks_linux.py` + `fan_view.py`: iconos uniformes de documentos/carpetas, pilas de carpetas inclinadas (`-index * 6°`) en el Dock y abanico curvo macOS con etiquetas en pastilla oscura.
     - `dock_zones.py`: separación de zonas estilo macOS (aplicaciones a la izquierda/arriba del separador; carpetas, archivos, Descargas, ventanas minimizadas y Papelera después del separador; eliminado el botón `+` del estante).
     - `minimized_tiles.py`: azulejos individuales de ventanas minimizadas con miniatura capturada en RAM e insignia del icono de la app en la esquina.
     - `sheet_effect.py` y `minimize_effect.py`: efectos de deformación tipo Genie (`sheet`) y reducción (`scale`) habilitados en Linux X11 mediante capturas XComposite en memoria, junto con `_NET_WM_ICON_GEOMETRY` para KWin.
     - `x11_surface.py`: región de desenfoque redondeada (`rounded_blur_region`) para `_KDE_NET_WM_BLUR_BEHIND_REGION` ajustada al radio de 21 px del estante.
     - `panels.py` + `apps_panel.py` + `catalog_drag.py` + `running_apps_panel.py` + `keyboard_dock.py`: corrección del fondo transparente sin pintar en popups sobre X11 (`Popup.paintEvent`), popover con flecha en `FolderPanel`, catálogo estilo Launchpad con categorías en español y arrastre directo al Dock, e indexación de aplicaciones Snap (`/var/lib/snapd/desktop/applications`, `X-SnapInstanceName`).
   - Todos los bloques de prueba (`diagnostico-inicio.json`, `validacion-nativa.json`, `bloque-iconos.json`, `bloque-arrastre.json`, `bloque-ventanas.json`, `bloque-escritorio.json` con 240 ciclos y `bloque-superficie.json`) han pasado con `PASS` (`exit_code: 0`) sobre el código actual.

2. **Respaldos verificados en `/media/leonardo/Documentos/Documentos/Respaldos-BrisaDock-Linux`**:
   - Respaldo inicial: `20261030-230802-228232`
   - Respaldo previo a la actualización de paridad macOS/0.37: `antes-macos-paridad-20261101-180733`

3. **Lanzador, perfil principal y autoarranque preparado**:
   - Comando: `/home/leonardo/.local/bin/brisadock` (`/media/leonardo/Documentos/Documentos/BrisaDock-Linux/iniciar-brisadock.sh`).
   - Entrada de menú actualizada: `/home/leonardo/.local/share/applications/brisadock-linux.desktop`.
   - Plantilla de autoarranque lista para activar cuando el usuario lo indique: `/media/leonardo/Documentos/Documentos/BrisaDock-Linux/brisadock-autostart.desktop`.
   - Perfil principal (`/media/leonardo/Documentos/Documentos/BrisaDock-Linux/perfiles/principal/settings.json`) configurado con efecto Genie (`animation_style: "sheet"`, `animate_minimize: true`), desenfoque KWin (`blur_enabled: true`) y pilas de carpetas (`folder_display: "stack"`).

4. **Retirada pendiente de confirmación del usuario (Cairo-Dock y LibreOffice)**:
   - Simulación verificada en `pruebas/simulacion-retirada-final.json` y `pruebas/simulacion-retirada-final.txt`: 84 paquetes en total (44 de Cairo-Dock, 39 de LibreOffice y `python3-uno`), 0 paquetes de KDE/KWin/Cinnamon afectados.
   - No se ha ejecutado `apt-get remove` ni modificado `~/.config/autostart` a la espera de la confirmación explícita del usuario.
