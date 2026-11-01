#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.37.0"
PKG_NAME="brisadock"
ARCH="all"
OUT_DIR="$ROOT/dist"
STAGE="$(mktemp -d -t brisadock-deb-XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/lib/brisadock/src" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/metainfo" \
  "$STAGE/etc/xdg/autostart" \
  "$OUT_DIR"

cp "$ROOT/src/"*.py "$STAGE/usr/lib/brisadock/src/"
chmod 0644 "$STAGE/usr/lib/brisadock/src/"*.py

cat > "$STAGE/usr/bin/brisadock" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n ${DISPLAY:-} ]]; then
    export QT_QPA_PLATFORM=xcb
fi
if [[ -x "/media/leonardo/Documentos/Documentos/BrisaDock-Linux/.venv/bin/python" && -d "/media/leonardo/Documentos/Documentos/BrisaDock-Linux/src" ]]; then
    exec "/media/leonardo/Documentos/Documentos/BrisaDock-Linux/.venv/bin/python" "/media/leonardo/Documentos/Documentos/BrisaDock-Linux/src/dock.py" "$@"
fi
if [[ -x "$HOME/.local/share/brisadock/venv/bin/python" ]]; then
    exec "$HOME/.local/share/brisadock/venv/bin/python" "/usr/lib/brisadock/src/dock.py" "$@"
fi
exec python3 "/usr/lib/brisadock/src/dock.py" "$@"
EOF
chmod 0755 "$STAGE/usr/bin/brisadock"

install -m 0644 "$ROOT/empaquetado/org.brisadock.BrisaDock.desktop" "$STAGE/usr/share/applications/org.brisadock.BrisaDock.desktop"
install -m 0644 "$ROOT/empaquetado/org.brisadock.BrisaDock.desktop" "$STAGE/etc/xdg/autostart/org.brisadock.BrisaDock.desktop"
install -m 0644 "$ROOT/empaquetado/org.brisadock.BrisaDock.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/org.brisadock.BrisaDock.svg"
install -m 0644 "$ROOT/empaquetado/org.brisadock.BrisaDock.metainfo.xml" "$STAGE/usr/share/metainfo/org.brisadock.BrisaDock.metainfo.xml"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-xlib, libglib2.0-bin
Recommends: python3-pyside6.qtwidgets | python3-venv, dolphin
Maintainer: Leonardo <brisadock@localhost>
Homepage: https://github.com/brisadock/brisadock-linux
Description: Dock estilo macOS para escritorios Linux (X11 y KWin Wayland)
 BrisaDock es un lanzador y barra de tareas independiente con estetica de
 cristal (Glassmorphism), carpetas en Abanico/Rejilla/Lista, pilas (Stacks),
 efecto lamina (Genie/Sheet), vistas previas en vivo y soporte hibrido para
 sesiones X11 y KDE Wayland.
EOF
chmod 0644 "$STAGE/DEBIAN/control"
find "$STAGE" -type d -exec chmod 0755 {} +

DEB_PATH="$OUT_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB_PATH" >/dev/null
printf 'Paquete generado correctamente: %s\n' "$DEB_PATH"
