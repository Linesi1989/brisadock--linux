# Validación de Brisa Dock 0.8

Entorno comprobado: Windows 11 x64, Python 3.12.14, PySide6 6.8.3.

Resultados:

- Sintaxis Python: correcta.
- Accesos: alta, prevención de duplicados, reordenación y eliminación comprobadas.
- Configuración: lectura/escritura y recuperación ante JSON inválido comprobadas.
- Límites de tamaño y número de accesos: comprobados.
- Cálculo de ocultación y recuperación: comprobado con Qt offscreen.
- Renderizado: imagen generada y revisada visualmente.
- Arranque con backend nativo Windows: salida 0 en modo de prueba breve.
- Compilación PyInstaller: terminada correctamente.
- Ejecutable portable: salida 0 en prueba breve y renderizado correcto con backend Windows.

Pruebas conservadas de 0.2:

- Dos ventanas Qt reales en un proceso de ensayo independiente: enumeración
  Win32, identidad del ejecutable, agrupación, minimización, restauración y cierre
  normal comprobados. SetForegroundWindow aceptó la activación en ese ensayo.
- Resolución de un acceso `.lnk` de ensayo con nombre Unicode: correcta.
- Identificación del navegador predeterminado del entorno: resuelta a un archivo existente.
- Pruebas Qt offscreen con clics: activación, Alt + clic para minimizar ambas
  ventanas, conversión de temporal a anclada sin duplicar y permanencia del acceso
  después del cierre de sus ventanas.
- Menús Qt: nombres de las dos ventanas y opción
  Mantener en el dock comprobados sin abrir archivos del usuario.
- Agrupación por ejecutable: distingue dos aplicaciones distintas y asocia un
  destino de acceso directo con la aplicación ya abierta.

Pruebas añadidas para 0.3:

- Panel de carpetas nativo: rejilla, tres miniaturas de imágenes de ensayo
  cargadas en segundo plano, cambio a lista persistente, navegación a subcarpeta,
  carpeta vacía y carpeta inexistente comprobados.
- Panel de ventanas en Windows: las dos ventanas de ensayo coloreadas se
  registran, actualizan y muestran mediante DWM. Se revisó la captura de la región
  del panel ya compuesta por Windows; la captura directa de QWidget no contiene
  las superficies DWM y no se usó como prueba visual de sus miniaturas.
- Los dos recursos DWM se liberan al cerrar el panel.
- rejilla-ejemplo.png contiene archivos sintéticos, no documentos del usuario.
- ventanas-ensayo.png muestra exclusivamente ventanas creadas para la prueba.

Pruebas añadidas para 0.4:

- Abanico revisado visualmente con archivos de ensayo, selección por flecha
  arriba y persistencia de su elección comprobadas.
- Selección automática de abanico/rejilla según capacidad disponible comprobada.
- Preferencias: tamaño, ampliación y espera de ocultación guardados y leídos
  correctamente, con comprobación visual del panel.
- Se conservan las pruebas de carpetas, ventanas nativas DWM y control Win32.

Pruebas añadidas para 0.5:

- Abajo/Izquierda/Derecha: revisión visual de capturas y clics Qt para activar
  la misma aplicación desde las tres posiciones. Los iconos conservan su orientación.
- Persistencia de borde y separación comprobadas.
- Reserva AppBar: dentro del aislamiento SHAppBarMessage(ABM_NEW) devolvió 0.
  Fuera de él, el registro y la asignación de posición devolvieron 1 y el área
  de trabajo de Windows cambió en cada borde.
- Una ventana Qt de ensayo maximizada respetó los límites reservados en los
  tres bordes, comprobados con DwmGetWindowAttribute y el área real del monitor.
- La reserva se retiró al desactivarla, activar ocultación y cerrar el dock.
  El área de trabajo original se recuperó en todos esos casos.
- La lógica de reaparición desde los bordes laterales se comprobó con Qt offscreen.
- El código contempla cambios de área disponible, retirada de monitor y aviso
  TaskbarCreated, pero no se ha probado reiniciar Explorer ni desconectar pantallas.

Pruebas añadidas para 0.6:

- Ventana de ensayo en proceso independiente: animación de reducción con DWM,
  estado minimizado real, animación inversa y estado restaurado comprobados.
- Recursos DWM y superposiciones liberados al terminar cada efecto.
- Ruta real Dock.window_action para minimizar y activar: caché de posición,
  limpieza al restaurar y preferencia persistente comprobadas.
- Cierre del dock durante la restauración: libera el efecto y completa la acción
  normal de restauración de la ventana.
- Se conservan pruebas de clics, carpetas, abanico y vistas de ventanas.
- El material Acrylic devolvió éxito, pero la prueba visual con fondo de colores
  no confirmó un desenfoque visible fiable. El experimento no se distribuye.
  No se modificaron las preferencias globales de transparencia del usuario.
- minimizar-ensayo.png y restaurar-ensayo.png muestran únicamente ventanas
  sintéticas creadas para las pruebas, durante los efectos.

Pruebas añadidas para 0.7:

- Catálogo Windows real: dos carpetas conocidas, 108 accesos y 157 entradas
  Get-StartApps leídas; el trabajador entregó 193 aplicaciones combinadas.
- Prueba de interfaz con catálogo sintético: búsqueda por nombre sin tildes,
  búsqueda por palabra clave, anclaje con nombre original, prevención de
  duplicados y apertura con Enter exactamente una vez.
- El temporizador de interfaz siguió funcionando durante la lectura del catálogo.
  Esto no equivale a una medición completa de latencia ni rendimiento.
- Entradas `.desktop` de ensayo: prioridad de usuario, Hidden, NoDisplay,
  OnlyShowIn=KDE, TryExec y nombre localizado comprobados sobre Windows.
  No se ejecutaron esas entradas ni se validó GIO en una máquina Linux.
- Ventana de ensayo externa: entrada/salida real de pantalla completa detectada;
  ocultación del dock en el mismo monitor, reaparición desde el borde y vuelta
  al comportamiento normal comprobadas.
- Posición de animación descartada al detectar restauración externa.
- Regresión de minimización/restauración animada y liberación de recursos correcta.
- aplicaciones-ejemplo.png usa exclusivamente entradas y archivos sintéticos.

Pruebas añadidas para 0.8:

- Recientes: límite de tres visibles, orden, exclusiones, persistencia, anclaje
  sin duplicar y borrado al desactivar comprobados con archivos de ensayo.
- Atención Windows: FlashWindowEx de una ventana de ensayo produjo un mensaje
  Shell real y una marca en el dock. La activación aceptada por Windows retiró
  la marca. La comprobación completa se hizo fuera del aislamiento.
- Bloqueo: dos procesos con un mismo perfil, aviso de la segunda copia, recuperación
  del bloqueo tras terminar abruptamente el proceso de ensayo y liberación normal
  comprobados. El servidor local fue rechazado dentro del aislamiento y funcionó
  fuera de él con la sesión normal del usuario.
- Punto de entrada real del dock: segunda apertura sin duplicar y cierre normal
  con salida 0 y retirada de instance.lock comprobados. Se corrigió el proceso
  que antes podía quedar activo después de cerrar la ventana de herramienta.
- Regresión de animación y paneles correcta. Las ventanas de ensayo se sitúan
  explícitamente en la pantalla primaria para no depender de la ubicación del cursor.
- La lectura X11 de DEMANDS_ATTENTION y diagnostico-linux.sh no se han ejecutado
  en Linux. Se documentan como preparados, pendientes de prueba en Mint.

## Versión 0.9

- Captura asíncrona de ventanas de ensayo mediante PrintWindow, comprobando el contenido esperado.
- Contracción curva y restauración nativa en borde inferior, izquierdo y derecho. Capturas visuales sobre un fondo de ensayo controlado; se corrigieron las uniones visibles entre franjas.
- Ruta real del Dock: minimizar, conservar imagen en memoria, restaurar y retirar caché comprobados.
- Captura simulada de 800 ms: el temporizador de interfaz respondió antes de 300 ms, se activó la reducción de respaldo y el resultado tardío se ignoró.
- Regresión del efecto DWM anterior, restauración y cierre durante la animación correctos.
- La imagen de PrintWindow puede incluir un marco clásico diferente del marco DWM real. No se afirma equivalencia exacta con Genie ni compatibilidad con todas las aplicaciones GPU.

## Versión 0.10

- Eventos Qt en bordes inferior, izquierdo y derecho: reordenar, quitar a distancia, deshacer, cancelar con clic derecho, persistencia y conservación del contenido de los archivos.
- Windows, fuera del aislamiento: entrada real del ratón sobre un acceso de ensayo, captura implícita del ratón y liberación fuera de la ventana del dock; el acceso se quitó y se recuperó con Deshacer.
- Una ventana de ensayo permanece en el modelo como aplicación abierta tras desanclar. Deshacer no duplica accesos que se hayan vuelto a añadir.
- Linux: los gestos usan Qt, pero no se han comprobado en una sesión Mint/KDE.

## Versión 0.11

- Ventanas nativas de un proceso de ensayo: ocultación sin terminar el proceso, permanencia en el modelo agrupado y clic del Dock para mostrar la aplicación.
- Se conserva una segunda ventana minimizada y se comprueba también el caso maximizado tras ocultar/mostrar.
- Ocultar otras: prueba de selección sobre dos ventanas reales con claves de grupo de ensayo; solo la ajena al grupo seleccionado se ocultó. No se han ocultado las aplicaciones personales del escritorio durante las pruebas.
- Recuperación: un proceso auxiliar oculta ventanas y sale mediante os._exit, sin ejecutar limpieza. Un nuevo backend con el mismo registro las muestra. Un registro con fecha de creación incorrecta se rechaza.
- Si no puede escribirse el registro, la ventana permanece visible. Cerrar normalmente el Dock vuelve a mostrar sus ventanas ocultas.
- Ejecutable 0.11: apertura con un perfil que contiene un registro de recuperación real, ventanas mostradas y cierre con salida 0. Segunda apertura sin duplicar y liberación del bloqueo correctas.
- Regresión de clics, grupos, gestos de accesos y animaciones con captura lenta correcta.
- Linux: no se añade ocultación de aplicaciones; continúa pendiente la prueba real en Mint/KDE.

Límites de esta validación:

No se ha probado en Linux Mint ni KDE, ni en una sesión Wayland. No se han
medido fluidez, consumo sostenido, suspensión, cambio de resolución o monitores.
No se ha comprobado manualmente la apertura de todos los tipos de accesos,
la papelera, el arrastre entre aplicaciones ni el reordenamiento por arrastre
en un escritorio real, ni un uso prolongado con aplicaciones reales.
Las pruebas de estado no sustituyen una prueba interactiva de escritorio.

La inspección del ejecutable de referencia no fue una descompilación. El
resultado es un prototipo independiente y aún no cumple todas las funciones
de un dock como el de macOS. Consulta los pendientes en LEEME.md.
