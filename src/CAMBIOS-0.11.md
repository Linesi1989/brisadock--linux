# Versión 0.11

- Windows: Ocultar aplicación y Ocultar otras aplicaciones, desde el menú de una aplicación abierta.
- Las ventanas ocultadas por Brisa siguen agrupadas en el dock. El icono se atenúa cuando todas están ocultas.
- Clic para mostrar la aplicación, conservando el estado de sus demás ventanas. Mostrar aplicaciones ocultas recupera todas sin solicitar activación.
- El cierre normal de Brisa solicita mostrar sus ventanas ocultas. Un registro previo permite recuperarlas al abrir de nuevo el mismo perfil tras terminar el dock de forma forzada.
- El registro contiene identificadores de ventana, proceso y creación del proceso, sin títulos ni imágenes. No se oculta si falla su escritura. Se excluyen clases de escritorio y barras del sistema.
- Las animaciones pendientes de las ventanas afectadas se retiran antes de ocultar.

Implementado con peticiones asíncronas de Windows. No equivale a integración completa de aplicaciones de macOS. Aún no está disponible en Linux; las pruebas reales de Mint/KDE siguen pendientes.

Referencia de API: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync
