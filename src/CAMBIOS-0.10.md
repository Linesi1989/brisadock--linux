# Versión 0.10

- Arrastrar un acceso personalizado fuera del dock permite quitarlo, con un umbral de 64 píxeles y aviso Quitar del dock.
- Arrastrar sobre otro acceso sigue permitiendo reordenar. El acceso arrastrado se atenúa y la barra permanece quieta durante el gesto.
- Clic derecho durante el arrastre cancela. Soltar cerca de la barra sin otro destino conserva el acceso.
- Deshacer quitar acceso recupera la última eliminación del gesto o del menú y su posición durante esta ejecución. Evita duplicados y respeta el límite de 18 accesos.
- Quitar un acceso no borra el archivo ni cierra la aplicación. Las aplicaciones abiertas se mantienen como iconos de ejecución.

Pruebas de eventos Qt en los tres bordes y una prueba con entrada real del ratón en Windows, incluida la liberación fuera de la ventana. Preparado para Linux; aún sin prueba en Mint/KDE.
