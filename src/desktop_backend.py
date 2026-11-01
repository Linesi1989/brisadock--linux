"""Desktop integration and deterministic grouping, independent of Qt rendering."""
import configparser
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import threading
import time


def canonical(path):
    return os.path.normcase(os.path.realpath(path)) if path else ''


def application_target(path):
    """Resolve launcher identity without executing the launcher."""
    if path.startswith(('https://', 'http://')):
        if os.name == 'nt':
            import winreg
            try:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice') as key:
                        progid = winreg.QueryValueEx(key, 'ProgId')[0]
                except OSError:
                    progid = 'https'
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r'\shell\open\command') as key:
                    command = winreg.QueryValue(key, None)
                tokens = shlex.split(command, posix=False)
                if tokens:
                    return os.path.expandvars(tokens[0].strip('"'))
            except (OSError, ValueError):
                pass
        else:
            try:
                name = subprocess.run(['xdg-settings', 'get', 'default-web-browser'], capture_output=True,
                                      text=True, timeout=2).stdout.strip()
                if name and '/' not in name:
                    folders = [Path.home()/'.local/share/applications', Path('/usr/local/share/applications'), Path('/usr/share/applications')]
                    for folder in folders:
                        if (folder/name).is_file():
                            return application_target(str(folder/name))
            except (OSError, subprocess.TimeoutExpired):
                pass
        return path
    if path.lower().endswith('.lnk') and os.name == 'nt':
        command = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:BRISA_SHORTCUT); $s.TargetPath"
        env = dict(os.environ, BRISA_SHORTCUT=path)
        try:
            target = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=env, capture_output=True, timeout=4,
                                    creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode('utf-8', 'replace').strip()
            return target or path
        except (OSError, subprocess.TimeoutExpired):
            return path
    if path.endswith('.desktop'):
        return str(Path(path).resolve())
    return path


def merge_items(pins, windows, targets=None, pin_indices=None):
    """Keep pin order and group visible windows by executable identity."""
    targets = targets or {}
    pin_indices = range(len(pins)) if pin_indices is None else pin_indices
    groups = {}
    for window in windows:
        groups.setdefault(window['key'], []).append(window)
    items = []
    claimed = set()
    for index, pin in zip(pin_indices, pins):
        target = targets.get(pin['path'], pin.get('target', pin['path']))
        key = canonical(target)
        items.append(dict(pin, pin_index=index, key=key, windows=groups.get(key, [])))
        claimed.add(key)
    # Stable alphabetical ordering avoids jumps when foreground order changes.
    for key in sorted(groups):
        if key not in claimed:
            window = groups[key][0]
            items.append(dict(name=window['name'], path=window['path'], key=key,
                              windows=groups[key], temporary=True))
    return items


class NullBackend:
    capabilities = dict(list_windows=False, activate_window=False, minimize_window=False,
                        live_previews=False, reserve_space=False, native_minimize_animation=False)
    def __init__(self, status):
        self.status = status

    def snapshot(self):
        return []

    def close(self):
        pass


class X11Backend:
    status = 'KDE/X11: EWMH; identidad .desktop/WM_CLASS; paridad macOS/0.37'
    capabilities = dict(list_windows=True, activate_window=True, minimize_window=True,
                        live_previews=True, reserve_space=True, native_minimize_animation=True)

    def __init__(self):
        from Xlib import display, X, Xatom, protocol
        self.X, self.Xatom, self.protocol = X, Xatom, protocol
        self.display = display.Display()
        self.root = self.display.screen().root
        self.lock = threading.RLock()
        from linux_desktop import DesktopIndex
        self.desktop_index = DesktopIndex()
        self.desktop_index_time = time.monotonic()
        from hidden_windows import HiddenWindows
        self.hidden = HiddenWindows(self)

    def atom(self, name):
        return self.display.intern_atom(name)

    def prop(self, window, name):
        value = window.get_full_property(self.atom(name), self.X.AnyPropertyType)
        return value.value if value else []

    def active_window_id(self):
        with self.lock:
            try:
                active = self.prop(self.root, '_NET_ACTIVE_WINDOW')
                return int(active[0]) if len(active) else 0
            except Exception:
                return 0

    def activate_id(self, window_id):
        if not window_id:
            return False
        from Xlib.error import BadWindow
        with self.lock:
            try:
                event = self.protocol.event.ClientMessage(
                    window=int(window_id),
                    client_type=self.atom('_NET_ACTIVE_WINDOW'),
                    data=(32, [2, self.X.CurrentTime, 0, 0, 0]),
                )
                self.root.send_event(event, event_mask=self.X.SubstructureRedirectMask | self.X.SubstructureNotifyMask)
                self.display.flush()
                return True
            except BadWindow:
                return False

    def snapshot(self):
        from Xlib.error import BadWindow
        result = []
        self.hidden.prune()
        if time.monotonic()-self.desktop_index_time > 30:
            from linux_desktop import DesktopIndex
            self.desktop_index = DesktopIndex()
            self.desktop_index_time = time.monotonic()
        with self.lock:
            active = self.prop(self.root, '_NET_ACTIVE_WINDOW')
            active = int(active[0]) if len(active) else 0
            for handle in self.prop(self.root, '_NET_CLIENT_LIST'):
                try:
                    window = self.display.create_resource_object('window', int(handle))
                    state = self.prop(window, '_NET_WM_STATE')
                    if self.atom('_NET_WM_STATE_SKIP_TASKBAR') in state:
                        continue
                    types = self.prop(window, '_NET_WM_WINDOW_TYPE')
                    if any(self.atom(kind) in types for kind in ('_NET_WM_WINDOW_TYPE_DOCK', '_NET_WM_WINDOW_TYPE_DESKTOP')):
                        continue
                    pid = self.prop(window, '_NET_WM_PID')
                    raw_pid = int(pid[0]) if len(pid) else 0
                    if raw_pid == os.getpid():
                        continue
                    path = ''
                    if raw_pid > 2:
                        try:
                            path = os.readlink(f'/proc/{raw_pid}/exe')
                        except OSError:
                            path = ''
                    wm_class = tuple(window.get_wm_class() or ())
                    for desk_prop in ('_KDE_NET_WM_DESKTOP_FILE', '_GTK_APPLICATION_ID'):
                        raw_desk = self.prop(window, desk_prop)
                        if isinstance(raw_desk, bytes) and raw_desk:
                            desk_val = raw_desk.decode('utf-8', 'replace').strip('\x00')
                            if desk_val and desk_val not in wm_class:
                                wm_class = wm_class + (desk_val,)
                    if not path and not wm_class:
                        continue
                    fallback_stem = Path(path).stem if path else (wm_class[-1] if wm_class else 'Ventana')
                    title = self.prop(window, '_NET_WM_NAME')
                    title = title.decode('utf-8', 'replace') if isinstance(title, bytes) else (window.get_wm_name() or fallback_stem)
                    launcher = self.desktop_index.resolve(wm_class, path)
                    if not launcher and path and ('/libexec/' in path or Path(path).name.startswith(('xdg-desktop-portal', 'kwin_killer'))):
                        continue
                    if not launcher and 'BrisaDock-Linux/.venv' in path and not any('fixture' in str(c).lower() for c in wm_class):
                        continue
                    target = launcher['path'] if launcher else (path or wm_class[-1])
                    identity = canonical(target) if (launcher or (path and not wm_class)) else 'wmclass:'+wm_class[-1].casefold()
                    geometry = window.get_geometry()
                    position = self.root.translate_coords(window, 0, 0)
                    raw_id = int(handle)
                    is_hidden_state = self.atom('_NET_WM_STATE_HIDDEN') in state
                    tracked_hidden = self.hidden.tracked({'id': raw_id, 'pid': raw_pid})
                    if tracked_hidden and not is_hidden_state and raw_id == active:
                        self.hidden.show({'id': raw_id, 'pid': raw_pid})
                        tracked_hidden = False
                    result.append(dict(id=raw_id, pid=raw_pid, path=target, key=identity,
                                       title=title, name=launcher['name'] if launcher else fallback_stem,
                                       minimized=is_hidden_state and not tracked_hidden,
                                       hidden=tracked_hidden,
                                       urgent=self.atom('_NET_WM_STATE_DEMANDS_ATTENTION') in state,
                                       active=raw_id == active,
                                       fullscreen=self.atom('_NET_WM_STATE_FULLSCREEN') in state,
                                       geometry=(position.x, position.y, geometry.width, geometry.height),
                                       wm_class=wm_class))
                except (BadWindow, OSError):
                    continue
            self.display.flush()
        return result

    def valid(self, window):
        from Xlib.error import XError
        with self.lock:
            try:
                resource = self.display.create_resource_object('window', window['id'])
                pid = self.prop(resource, '_NET_WM_PID')
                if not window.get('pid'):
                    return True
                return bool(len(pid) and int(pid[0]) == window['pid'])
            except XError:
                return False

    def icon_geometry(self, window, rectangle):
        with self.lock:
            if not self.valid(window):
                return False
            resource = self.display.create_resource_object('window', window['id'])
            resource.change_property(self.atom('_NET_WM_ICON_GEOMETRY'), self.Xatom.CARDINAL, 32,
                                     [max(0, int(v)) for v in rectangle])
            self.display.flush()
            return True

    def send(self, window, message, data):
        from Xlib.error import BadWindow
        with self.lock:
            try:
                resource = self.display.create_resource_object('window', window['id'])
                pid = self.prop(resource, '_NET_WM_PID')
                if window.get('pid') and (not len(pid) or int(pid[0]) != window['pid']):
                    return False
                event = self.protocol.event.ClientMessage(window=window['id'],
                            client_type=self.atom(message), data=(32, data))
                self.root.send_event(event, event_mask=self.X.SubstructureRedirectMask | self.X.SubstructureNotifyMask)
                self.display.flush()
                return True
            except BadWindow:
                return False

    def activate(self, window):
        return self.send(window, '_NET_ACTIVE_WINDOW', [2, self.X.CurrentTime, 0, 0, 0])

    def minimize(self, window):
        return self.send(window, 'WM_CHANGE_STATE', [3, 0, 0, 0, 0])

    def close_window(self, window):
        return self.send(window, '_NET_CLOSE_WINDOW', [self.X.CurrentTime, 2, 0, 0, 0])

    def close(self):
        with self.lock:
            self.display.close()


def create_backend():
    if os.name == 'nt':
        from windows_backend import WindowsBackend
        return WindowsBackend()
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland' or os.environ.get('WAYLAND_DISPLAY'):
        try:
            from wayland_backend import KWinWaylandBackend
            return KWinWaylandBackend()
        except Exception:
            if os.environ.get('DISPLAY'):
                try:
                    return X11Backend()
                except Exception:
                    pass
            return NullBackend('Wayland: solo lanzador; puente KWin D-Bus no disponible')
    try:
        return X11Backend()
    except Exception as error:
        try:
            from wayland_backend import KWinWaylandBackend
            return KWinWaylandBackend()
        except Exception:
            return NullBackend(f'Integración X11 no disponible: {type(error).__name__}')
