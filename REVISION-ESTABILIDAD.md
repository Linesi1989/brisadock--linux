# Revisión de estabilidad de BrisaDock Linux

Resultado: **APTO para sustituir Cairo-Dock y activar autoarranque** (pendiente únicamente de confirmación explícita del usuario para ejecutar la retirada APT o copiar el archivo de autoarranque).

- **Huella SHA-256 de `src/*.py` verificada**: `f74b976e3482db8678e9fd43db61353952b74c40bf3f156a0d09091db5023e1e` (35 módulos Python con sintaxis AST validada).
- **Resolución del bloqueo anterior (`bloque_superficie.py`)**: el fallo previo (`backend: NoneType`) se debía al uso de `QTest.qWait` sin bucle de eventos durante el arranque del hilo `WindowWatcher`. Con `QEventLoop` + `QTimer`, `diagnostico_inicio.py` certifica arranque completo de `X11Backend` y lectura de papelera en `0.593 s` (`PASS`), y `bloque_superficie.py` certifica reserva/restauración de espacio EWMH (`_NET_WM_STRUT_PARTIAL`), traspaso entre pantallas (`follow_edge`) bloqueado durante menús, navegación por teclado, lectura de papelera (`gio`) y aparición de `FullscreenShelf` sobre ventana en pantalla completa sin robar foco (`PASS`).
- **Paridad estética y funcional macOS / Windows 0.37 certificada sobre el mismo SHA-256**:
  - `diagnostico-inicio.json`: `PASS` (`0.593 s`, `X11Backend`, parada limpia de hilos).
  - `validacion-nativa.json`: `PASS` (preservación de claves futuras en `settings.json`, tamaño mínimo `16 px`, segunda instancia retorna `0`, captura `pruebas/brisa-x11.png`).
  - `bloque-iconos.json`: `PASS` (160 extracciones iniciales, 0 extracciones y 160 aciertos en disco tras reinicio, invalidación selectiva ante cambio o corrupción, modo solo lectura y respaldo squircle macOS).
  - `bloque-arrastre.json`: `PASS` (vista previa en vivo, cancelación con `Escape` y guardado al soltar en los 3 bordes `bottom`/`left`/`right`; anclado de archivos sin mover ni ejecutar el original).
  - `bloque-ventanas.json`: `PASS` (agrupación determinista, miniaturas XComposite en vivo bajo oclusión en `WindowPanel` con fondo translúcido pintado, ventanas minimizadas agrupadas o en azulejos separados `MinimizedTiles`, minimizar/restaurar/cerrar individual, captura `pruebas/ventanas-x11.png`).
  - `bloque-escritorio.json`: `PASS` (6 combinaciones reales de autoocultamiento en `HDMI-1` y `eDP-1` con puntero real sobre fixture maximizada, abanico curvo macOS `FanView`, pilas de carpetas inclinadas `FolderStacks`, orden natural, observador de archivos en vivo y **240 ciclos consecutivos de apertura/cierre de paneles** sin bloqueos; capturas `pruebas/autoocultamiento-x11.png` y `pruebas/carpeta-abanico-x11.png`).
  - `bloque-superficie.json`: `PASS` (captura `pruebas/pantalla-completa-estante.png`).
- **CraftSuite Linux**: WordCraft DOCX, GridCraft XLSX con fórmula, DeckCraft PPTX y PDFCraft PDF editados, guardados y reabiertos; 8 aperturas por asociaciones MIME verificadas; se conservan XLS/PPT en LibreOffice si se desea o hasta confirmar su desinstalación.
- **Respaldo previo a la actualización macOS/0.37**: `/media/leonardo/Documentos/Documentos/Respaldos-BrisaDock-Linux/antes-macos-paridad-20261101-180733`.
