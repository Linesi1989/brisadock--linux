# Brisa Dock — prototipo 0.11

Dock independiente gratuito para Windows 11 y, como objetivo de compatibilidad,
Linux Mint con KDE Plasma. Código propio bajo licencia MIT. No contiene código,
iconos ni recursos extraídos de XWindows Dock o macOS.

## Windows 11

Cierra la versión anterior y abre `Windows-0.11/BrisaDock/BrisaDock.exe` si
recibiste el paquete compilado.
Mantén la carpeta `_internal` junto al ejecutable. Es una aplicación portable;
no cambia la barra de tareas ni se configura para iniciarse con Windows.
Desde 0.8 se permite una copia por perfil. Abrir otra copia hace visible la que
ya está en marcha. Cerrar Brisa Dock termina el proceso y libera el perfil. Esto
no detecta versiones anteriores a 0.8, que deben cerrarse antes de actualizar.

Para compilar desde el código, instala Python 3.12 para Windows y ejecuta
`powershell -ExecutionPolicy Bypass -File construir-windows.ps1` dentro de esta carpeta.
La primera compilación descarga dependencias de PyPI.

## Linux Mint + KDE Plasma

Extrae el paquete en una carpeta permanente. Requiere Python 3.10 o posterior.
Si no tienes las dependencias del sistema, instala:

```bash
sudo apt install python3 python3-venv libglib2.0-bin libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0
bash iniciar-linux.sh
```

El script crea `.venv` en su carpeta y descarga PySide6 desde PyPI la primera vez.
Las siguientes ejecuciones utilizan ese entorno. No instala un panel de Plasma
ni cambia la configuración del escritorio. No necesita sudo para ejecutarse.
En una sesión Wayland necesita XWayland. La posición y la ocultación deben
comprobarse en tu sesión; para este prototipo se recomienda probar en Plasma X11.
Si el panel existente ocupa el borde inferior, el dock se sitúa encima del área
reservada por ese panel. No oculta el panel existente automáticamente.

## Uso

- Pulsa Archivos, Navegador o Descargas para abrirlos.
- Hasta tres aplicaciones recientes aparecen en una sección separada cuando
  deja de detectarse su última ventana. Se excluyen las ancladas y las abiertas.
  Clic derecho permite anclarlas o quitarlas; Borrar aplicaciones recientes limpia
  el historial. Desactivar Mostrar aplicaciones recientes borra y detiene su
  recopilación. Se guardan nombres y rutas de ejecutables, no títulos de documentos.
- Un punto ámbar y un rebote breve indican una petición de atención. En Windows
  se reciben avisos del Shell mientras el dock está abierto; al activar la app
  se retira la marca. No representa un número de mensajes ni lee notificaciones.
  Se puede desactivar en Preferencias. La API de Shell puede no estar disponible
  en algunos entornos; su ausencia no impide utilizar el resto del dock.
- Pulsa el icono morado Aplicaciones para abrir el lanzador. Busca por nombre
  o palabras clave; la búsqueda ignora tildes. Enter abre el primer resultado,
  las flechas permiten seleccionar y Escape cierra el panel. Clic derecho sobre
  una aplicación ofrece Mantener en el dock. Los resultados se paginan de 24 en 24.
- Windows: se leen las carpetas conocidas del menú Inicio y Get-StartApps. Se
  combinan por nombre, dando prioridad a los accesos del menú Inicio. Puede haber
  aplicaciones sin un icono específico o accesos que dependan del lanzador original.
- Linux: se leen entradas `.desktop` de XDG y ubicaciones habituales de Flatpak,
  respetando Hidden, NoDisplay, OnlyShowIn, NotShowIn y TryExec. Se usa gio para
  abrirlas. Esta lectura se comprobó con archivos de ensayo en Windows; el
  lanzamiento real en Linux Mint/KDE sigue pendiente de validación.
- El catálogo se lee en segundo plano y se conserva durante un minuto. Usa
  Actualizar para releerlo después de instalar aplicaciones.
- Si una aplicación ya tiene ventanas, el clic normal la activa/restaura.
- Windows: el menú de una aplicación abierta ofrece Ocultar aplicación y Ocultar
  otras aplicaciones. Se ocultan las ventanas detectadas sin cerrarlas; el icono
  permanece y se atenúa cuando todas sus ventanas están ocultas. Un clic vuelve
  a mostrarlas y activa una; las demás conservan su estado minimizado o maximizado.
  Mostrar aplicaciones ocultas, en el menú general, las recupera sin activarlas.
- Al cerrar Brisa normalmente se solicita mostrar todas las ventanas que ocultó.
  Antes de ocultarlas se escribe hidden-windows.json en el perfil. Tras terminar
  Brisa de forma forzada, vuelve a abrirlo con el mismo perfil para recuperarlas.
  La recuperación comprueba ventana, proceso y fecha de creación del proceso.
  Si no puede guardar el registro, no oculta la ventana. No registra títulos ni
  contenido de documentos. No es un servicio que recupere ventanas mientras Brisa
  esté cerrado. Windows o la aplicación pueden rechazar estas peticiones; las
  pruebas se hicieron con ventanas de ensayo, no con todas las aplicaciones.
  Esta función aún no está disponible en Linux.
- Alt + clic minimiza las ventanas de la aplicación. Shift + clic solicita abrirla
  de nuevo (cada aplicación decide si permite otra instancia).
- Las aplicaciones con ventanas aparecen agrupadas y con un punto inferior;
  el punto azul indica que una de sus ventanas está activa.
- Clic derecho sobre una aplicación: elegir una ventana, minimizar, solicitar
  el cierre normal de sus ventanas o mantenerla en el dock.
- El cierre envía la petición normal a cada ventana; la aplicación puede pedir
  guardar o cancelar. No mata procesos ni equivale siempre a salir de la aplicación.
- Descargas y carpetas ancladas abren un panel con rejilla/lista, miniaturas de
  imágenes, subcarpetas y orden por fecha o nombre. Se muestran hasta 96 entradas;
  Abrir carpeta permite ver el contenido completo en el gestor del sistema.
- Ctrl + clic sobre una aplicación abierta muestra el panel de ventanas. También
  está disponible en su menú como Mostrar todas las ventanas. En Windows usa
  miniaturas nativas DWM. Puedes activar una ventana o solicitar su cierre normal.
- Las miniaturas de DWM pueden mostrar el último contenido de una ventana
  minimizada. Las ventanas protegidas o incompatibles pueden carecer de vista;
  sus títulos y botones siguen disponibles. No se graban ni guardan esas vistas.
- Escape o un clic fuera cierran los paneles.
- Carpetas: elige Automático, Abanico, Rejilla o Lista. Automático usa abanico
  cuando los elementos caben y rejilla cuando no. El abanico muestra hasta siete
  entradas, según el espacio disponible; la rejilla permite ver más. Las flechas
  arriba/abajo recorren el abanico y Enter o Espacio abren el elemento enfocado.
- Preferencias permite ajustar tamaño (36–72 px), ampliación (1,1–1,7×), espera
  antes de ocultarse (0,2–5 s), ocultación, ampliación y apariencia.
- Windows: Animar minimización y restauración añade una reducción hacia el icono
  mediante una miniatura DWM, y su movimiento inverso al restaurar. Está apagada
  por defecto. Para probarla, actívala en Preferencias, minimiza con Alt + clic
  y restaura con un clic normal. También se aplica al menú Minimizar ventanas.
- La restauración animada requiere que esa ventana se haya minimizado con el
  dock durante esta ejecución. Los efectos duran unos 340 ms; se permiten hasta
  tres a la vez. Las ventanas de otra pantalla y los casos incompatibles usan
  la acción normal del sistema. No sustituye las animaciones globales de Windows.
- En Preferencias, Animación de ventanas permite elegir Reducir o Deformar hacia
  el icono. Deformar curva la ventana hacia el borde inferior, izquierdo o derecho
  durante unos 550 ms. Es una aproximación propia, no el efecto Genie exacto de Apple.
  Requiere activar Animar minimización y restauración; Reducir sigue siendo la opción inicial.
- Deformar captura únicamente la ventana solicitada en memoria mediante PrintWindow;
  no guarda la imagen en disco. Espera como máximo 350 ms y usa Reducir si falla,
  se mueve la ventana o devuelve una imagen negra. Las aplicaciones protegidas o
  aceleradas por GPU pueden no funcionar; el marco capturado puede verse diferente.
  Se admiten capturas de hasta cuatro millones de píxeles y hasta 32 MiB de imágenes
  para restauración. Si la imagen ya no está disponible, se usa la reducción normal.
  La reducción DWM no toma capturas. Ningún modo sustituye las animaciones globales.
- Posición: Abajo, Izquierda o Derecha, con iconos derechos y separación
  configurable de 0 a 32 px. Los paneles se abren hacia el interior de la pantalla.
- Windows: Reservar espacio reduce el área de trabajo para que las ventanas
  maximizadas respeten el dock. Está desactivado por defecto y solo se aplica
  cuando Ocultar automáticamente está desactivado. La reserva se retira al cerrar
  el dock o activar su ocultación. Se conserva la barra de tareas de Windows.
- Ocultar en pantalla completa está activado por defecto en Windows. Se detecta
  la ventana activa sin marco que cubre el monitor del dock; este se oculta y
  reaparece desde el borde. Al salir de pantalla completa recupera su comportamiento
  anterior. Se libera la reserva mientras se aplica esta ocultación. No se han
  probado todos los juegos ni todos los modos de pantalla completa exclusivos.
- La reserva usa la API de barras de Windows y puede ser rechazada por un
  entorno aislado. Se verificó fuera del aislamiento, con permisos normales de
  usuario, y sin instalar servicios. Si el sistema la rechaza, el dock sigue
  funcionando como barra superpuesta. En Linux esta función está desactivada.
- Papelera abre la papelera del sistema; no vacía ni borra archivos.
- Pulsa + para anclar un ejecutable, acceso directo, archivo o un `.desktop` de Linux.
- Arrastra archivos o carpetas al dock para añadirlos. Añade solo accesos de confianza.
- Clic derecho: añadir carpeta, cambiar tamaño, ocultar automáticamente o cerrar.
- Clic derecho sobre un acceso personalizado: quitarlo o moverlo de posición.
- También puedes arrastrar un acceso personalizado sobre otro para reordenarlo.
- Para quitar un acceso personalizado, arrástralo fuera de la barra hasta ver
  Quitar del dock y suéltalo. Se exige una separación de 64 píxeles. Durante el
  arrastre, clic derecho cancela; soltar sobre la barra sin otro acceso conserva
  su posición. La barra permanece quieta mientras mantienes pulsado el ratón.
- Deshacer quitar acceso, en el menú contextual, recupera el último acceso quitado
  en esta ejecución y su posición. También sirve tras usar Quitar acceso en el menú.
  No borra archivos, no desinstala aplicaciones ni cierra ventanas. Una aplicación
  abierta que se desancla sigue visible como aplicación en ejecución. Deshacer
  no duplica un acceso vuelto a añadir y se desactiva al alcanzar el límite de 18.
- El menú permite cambiar entre apariencia clara y oscura y desactivar la ampliación.
- La configuración se guarda en la carpeta de configuración del usuario que indica Qt.
- Para volver a mostrarlo con ocultación activa, lleva el cursor al borde elegido,
  a la altura de la barra. Se usa el borde del área de trabajo disponible, que
  puede quedar junto al panel de KDE o la barra de tareas si están visibles.

## Qué incluye esta versión

Fondo oscuro translúcido, esquinas redondeadas, sombra, ampliación animada,
nombres emergentes, animación al abrir, accesos persistentes, tamaños de iconos,
ocultación opcional y selección del monitor donde esté el cursor al arrancar.
La ampliación desplaza los iconos vecinos; la bandeja se ensancha durante la animación.
La detección de ventanas se hace en segundo plano cada segundo. Los indicadores
reflejan ventanas detectadas, no todos los procesos que viven sin ventana.

Windows usa las API nativas de ventanas. Resuelve accesos `.lnk` normales para
asociarlos al ejecutable. Algunas aplicaciones empaquetadas/UWP, procesos con
permisos superiores y lanzadores que abren otro ejecutable pueden agruparse mal
o quedar sin identificar. Windows también puede rechazar traer una ventana al frente.
Las aplicaciones ancladas por identificador de AppsFolder pueden quedar sin
asociación con sus ventanas en esta primera integración del catálogo.

En KDE/X11 se preparó una integración EWMH con python-xlib, todavía sin prueba
en Linux Mint. En Wayland la aplicación funciona solo como lanzador: la lista
y control de ventanas nativas quedan desactivados explícitamente. No se instala
ninguna extensión de KWin. Los `.desktop` que usan wrappers o `env` pueden no
coincidir con el ejecutable real para la agrupación.

Para revisar el entorno de Mint sin instalar ni modificar nada:

```bash
bash diagnostico-linux.sh
```

El informe muestra tipo de sesión y dependencias detectadas. No demuestra que
la interfaz ni el control de ventanas funcionen. Estado por plataforma:

| Función | Windows 11 | KDE/X11 | KDE/Wayland |
| --- | --- | --- | --- |
| Lanzador y carpetas | Probados | Preparados, sin prueba en Mint | Preparados, sin prueba en Mint |
| Lista/control de ventanas | Probados con ventanas de ensayo | EWMH experimental | No disponible |
| Atención | Aviso Shell probado | Lee DEMANDS_ATTENTION, sin prueba real | No disponible |
| Ocultar y recuperar aplicaciones | Probado con ventanas de ensayo | No implementado | No implementado |
| Reserva y animaciones de ventanas | Probadas con ventanas de ensayo | No implementadas | No implementadas |

Uso avanzado: `--profile-dir CARPETA` utiliza configuración y bloqueo separados.
El bloqueo usa un archivo local y un canal local restringido al usuario; no abre
un puerto TCP ni requiere conexión a Internet.

## Pendiente antes de considerarlo un dock completo

No incluye el efecto Genie exacto, desenfoque real, animación propia de ventanas en Linux,
reserva de borde en Linux,
vistas gráficas de ventanas en KDE, integración nativa con KWin/Wayland,
instalador Linux ni inicio automático. No sustituye todavía al panel del sistema.
No se ha medido todavía el consumo en tu equipo.
Un lanzamiento correcto no demuestra compatibilidad completa ni fluidez.
Consulta VALIDACION.md para distinguir las pruebas reales de las pendientes.

## Licencias

`LICENSE` cubre únicamente el código propio. PySide6/Qt y Shiboken son componentes
de terceros con sus propias licencias. En el paquete portable Windows se
distribuyen como bibliotecas dinámicas, junto con sus avisos de licencia.
Documentación: https://doc.qt.io/qtforpython-6/licenses.html
Código fuente de Qt for Python: https://code.qt.io/pyside/pyside-setup.git/
El ejecutable es un lanzador congelado con PyInstaller; el código editable está
incluido en este paquete. Las bibliotecas Qt no se enlazan estáticamente.
