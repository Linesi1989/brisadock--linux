"""Bounded XComposite snapshots, isolated from the GUI and compositor state.

Never redirect/unredirect user windows. Only read an existing compositor pixmap.
A minimized window returns no image; old images are never labelled live.
"""
import base64
import json
import os
import sys


def capture(connection, handle, pid, max_size=(456,256)):
    from Xlib import X
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage
    window = connection.create_resource_object('window', handle)
    def values(name):
        value = window.get_full_property(connection.intern_atom(name), X.AnyPropertyType)
        return value.value if value else []
    actual_pid = values('_NET_WM_PID')
    if not len(actual_pid) or int(actual_pid[0]) != pid:
        return None
    if connection.intern_atom('_NET_WM_STATE_HIDDEN') in values('_NET_WM_STATE'):
        return None
    if window.get_attributes().map_state != X.IsViewable:
        return None
    # KWin redirects the reparenting frame, not necessarily its client child.
    drawable = window
    root = connection.screen().root
    for _ in range(8):
        parent = drawable.query_tree().parent
        if parent.id == root.id:
            break
        drawable = parent
    else:
        return None
    pixmap = drawable.composite_name_window_pixmap()
    try:
        geometry = pixmap.get_geometry()
        width, height = geometry.width, geometry.height
        if not 0 < width*height <= 4_000_000 or geometry.depth not in (24, 32):
            return None
        raw = pixmap.get_image(0, 0, width, height, X.ZPixmap, 0xffffffff)
        # The supported local Xorg server is little-endian with 32-bit pixels.
        if len(raw.data) != width*height*4 or sys.byteorder != 'little':
            return None
        image = QImage(raw.data, width, height, width*4, QImage.Format_RGB32).copy()
        image = image.scaled(*max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG'); buffer.close()
        return base64.b64encode(bytes(data)).decode('ascii')
    finally:
        pixmap.free()
        connection.flush()


def main():
    from Xlib import display
    connection = display.Display()
    connection.set_error_handler(lambda *_: None)
    for line in sys.stdin:
        if len(line) > 8192:
            break
        try:
            request = json.loads(line)
            windows = request['windows'][:6]
            results = []
            for window in windows:
                try:
                    png = capture(connection, int(window['id']), int(window['pid']))
                except Exception as error:
                    print(type(error).__name__+': '+str(error), file=sys.stderr, flush=True)
                    png = None
                results.append({'id':window['id'], 'png':png})
            print(json.dumps({'generation':request['generation'], 'images':results}), flush=True)
        except (KeyError, ValueError, TypeError):
            break
    connection.close()


if __name__ == '__main__':
    main()
