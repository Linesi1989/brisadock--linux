"""EWMH hints for Brisa's own surface; restore icon hints we temporarily own."""
import math
from Xlib import display, X, Xatom


def rounded_blur_region(rectangle, radius=21):
    x, y, width, height = [int(v) for v in rectangle]
    if width <= 0 or height <= 0:
        return []
    r = max(0, min(int(radius), width // 2, height // 2))
    if r <= 2:
        return [x, y, width, height]
    values = []
    for row in range(r):
        dy = r - row - 0.5
        dx = max(0, round(r - math.sqrt(max(0.0, r * r - dy * dy))))
        w = max(1, width - 2 * dx)
        values.extend([x + dx, y + row, w, 1])
    middle = height - 2 * r
    if middle > 0:
        values.extend([x, y + r, width, middle])
    for row in range(r):
        dy = row + 0.5
        dx = max(0, round(r - math.sqrt(max(0.0, r * r - dy * dy))))
        w = max(1, width - 2 * dx)
        values.extend([x + dx, y + height - r + row, w, 1])
    return values


class X11Surface:
    def __init__(self, widget):
        self.widget = widget
        self.display = display.Display()
        self.display.set_error_handler(lambda *_: None)
        self.root = self.display.screen().root
        self.window = self.display.create_resource_object('window', int(widget.winId()))
        self.original = {}
        self.last_icons = {}
        self.last_reservation = None
        self.last_blur = None
        self.window.change_property(self.atom('_NET_WM_WINDOW_TYPE'), Xatom.ATOM, 32,
                                    [self.atom('_NET_WM_WINDOW_TYPE_DOCK')])
        self.display.sync()

    def atom(self, name):
        return self.display.intern_atom(name)

    def configure(self, edge, screen, thickness, enabled):
        root = self.root.get_geometry()
        # EWMH struts are distances from root edges. Never reserve unrelated
        # screens when the requested edge is internal to a monitor layout.
        outer = {'bottom': screen.bottom()+1 == root.height,
                 'left': screen.left() == 0,
                 'right': screen.right()+1 == root.width}[edge]
        values = [0]*12
        if enabled and outer:
            if edge == 'bottom':
                values[3], values[10], values[11] = int(thickness), screen.left(), screen.right()
            elif edge == 'left':
                values[0], values[4], values[5] = int(thickness), screen.top(), screen.bottom()
            else:
                values[1], values[6], values[7] = int(thickness), screen.top(), screen.bottom()
        if values != self.last_reservation:
            self.window.change_property(self.atom('_NET_WM_STRUT_PARTIAL'), Xatom.CARDINAL, 32, values)
            self.window.change_property(self.atom('_NET_WM_STRUT'), Xatom.CARDINAL, 32, values[:4])
            self.display.flush()
            self.last_reservation = values
        return not enabled or outer

    def blur(self, rectangle, enabled=True):
        values = rounded_blur_region(rectangle, 21) if enabled else None
        if values == self.last_blur:
            return
        atom = self.atom('_KDE_NET_WM_BLUR_BEHIND_REGION')
        if not values:
            self.window.delete_property(atom)
        else:
            self.window.change_property(atom, Xatom.CARDINAL, 32, values)
        self.display.flush()
        self.last_blur = values

    def input_rectangle(self, rectangle=None):
        if not self.display.has_extension('SHAPE'):
            return
        from Xlib.ext import shape
        rectangles = [] if rectangle is None else [tuple(int(v) for v in rectangle)]
        self.window.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, rectangles)
        self.display.flush()

    def publish_icons(self, records):
        live = set()
        for item, rectangle in records:
            identity = (item['id'], item['pid'])
            live.add(identity)
            try:
                resource = self.display.create_resource_object('window', item['id'])
                pid = resource.get_full_property(self.atom('_NET_WM_PID'), X.AnyPropertyType)
                if pid is None or not len(pid.value) or int(pid.value[0]) != item['pid']:
                    continue
                values = [max(0, int(v)) for v in rectangle]
                if identity not in self.original:
                    previous = resource.get_full_property(self.atom('_NET_WM_ICON_GEOMETRY'), X.AnyPropertyType)
                    self.original[identity] = list(previous.value) if previous else None
                if self.last_icons.get(identity) != values:
                    resource.change_property(self.atom('_NET_WM_ICON_GEOMETRY'), Xatom.CARDINAL, 32, values)
                    self.last_icons[identity] = values
            except Exception:
                continue
        for identity in set(self.original)-live:
            self.restore(identity)
        self.display.flush()

    def restore(self, identity):
        try:
            resource = self.display.create_resource_object('window', identity[0])
            pid = resource.get_full_property(self.atom('_NET_WM_PID'), X.AnyPropertyType)
            current = resource.get_full_property(self.atom('_NET_WM_ICON_GEOMETRY'), X.AnyPropertyType)
            if pid is not None and int(pid.value[0]) == identity[1] and current is not None and list(current.value) == self.last_icons.get(identity):
                previous = self.original[identity]
                if previous is None:
                    resource.delete_property(self.atom('_NET_WM_ICON_GEOMETRY'))
                else:
                    resource.change_property(self.atom('_NET_WM_ICON_GEOMETRY'), Xatom.CARDINAL, 32, previous)
        except Exception:
            pass
        self.original.pop(identity, None)
        self.last_icons.pop(identity, None)

    def close(self):
        for identity in list(self.original):
            self.restore(identity)
        self.window.delete_property(self.atom('_NET_WM_STRUT_PARTIAL'))
        self.window.delete_property(self.atom('_NET_WM_STRUT'))
        self.display.flush()
        self.display.close()
