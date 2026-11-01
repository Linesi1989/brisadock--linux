# Versión 0.9

- Opción Windows Deformar hacia el icono, con contracción curva y restauración inversa en los tres bordes.
- Captura de la ventana solicitada en un hilo de trabajo, con espera limitada a 350 ms y reducción de respaldo.
- Imágenes solo en memoria, hasta cuatro millones de píxeles por captura y 32 MiB de caché para restauración.
- La reducción DWM anterior se conserva como opción inicial. Las animaciones siguen apagadas por defecto.

Es una aproximación visual propia. PrintWindow puede producir marcos distintos o no representar aplicaciones protegidas/GPU. No es una implementación exacta de Genie. Linux mantiene las funciones anteriores y sigue pendiente de pruebas en Linux Mint/KDE real.
