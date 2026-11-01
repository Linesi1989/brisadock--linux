# Brisa Dock 0.8

- Hasta tres aplicaciones recientes en una sección separada, con opción de anclar,
  quitar, borrar el historial o desactivar su recopilación.
- Marca de atención ámbar y rebote breve ante avisos Shell de Windows.
- Lectura de DEMANDS_ATTENTION en el backend X11, pendiente de prueba en Mint.
- Una copia por perfil; las siguientes aperturas hacen visible la copia existente.
- Recuperación de bloqueo tras un cierre inesperado y perfil alternativo opcional.
- Cerrar el dock termina el proceso y libera sus recursos y bloqueo.
- Un fallo temporal de lectura de ventanas conserva la última lista conocida,
  evitando generar recientes falsos por un error de transporte.
- Diagnóstico Linux sin modificaciones del sistema y tabla de capacidades.

No se leen mensajes ni contadores de correo. Los avisos reflejan peticiones de
atención de ventanas. Linux Mint/KDE sigue pendiente de ejecución real.

Referencias:
https://doc.qt.io/qt-6/qlockfile.html
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registershellhookwindow
https://specifications.freedesktop.org/wm/latest-single/
