"""KDE Plasma / KWin Wayland backend using KWin D-Bus Scripting + XWayland hybrid bridge."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from PySide6.QtCore import QCoreApplication, QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface
from desktop_backend import canonical
from hidden_windows import HiddenWindows
from linux_desktop import DesktopIndex


class _KWinDBusReceiver(QObject):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.ready_event = threading.Event()
        self.payload = '[]'

    @Slot(str)
    def report(self, data):
        with self.lock:
            self.payload = data or '[]'
            self.ready_event.set()


class KWinWaylandBackend:
    status = 'KDE/Wayland: puente KWin D-Bus Scripting + XWayland activo'
    capabilities = dict(
        list_windows=True,
        activate_window=True,
        minimize_window=True,
        live_previews=True,
        reserve_space=True,
        native_minimize_animation=False,
    )

    def __init__(self):
        self.lock = threading.RLock()
        self.desktop_index = DesktopIndex()
        self.desktop_index_time = time.monotonic()
        self.hidden = HiddenWindows(self)
        self.service_name = f'org.brisadock.KWinBridge.p{os.getpid()}'
        self.receiver = _KWinDBusReceiver()
        app = QCoreApplication.instance()
        if app is not None and self.receiver.thread() is not app.thread():
            self.receiver.moveToThread(app.thread())
        self.bus = QDBusConnection.sessionBus()
        if not self.bus.isConnected():
            raise RuntimeError('Session D-Bus no disponible')
        self.bus.registerService(self.service_name)
        self.bus.registerObject('/Bridge', self.receiver, QDBusConnection.ExportAllSlots)
        self.uuid_by_id = {}
        self._next_synthetic_id = 900_000_000
        self._id_by_uuid = {}
        self._script_dir = Path(tempfile.mkdtemp(prefix='brisadock-kwin-'))
        self._enum_script = self._script_dir / 'enumerate.js'
        self._enum_script.write_text(self._build_enum_js(), encoding='utf-8')
        # Verify KWin Scripting interface is reachable
        scripting = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', self.bus)
        if not scripting.isValid():
            raise RuntimeError('Interfaz org.kde.kwin.Scripting no disponible')

    def _build_enum_js(self):
        return f"""
var listFn = workspace.clientList ? function() {{ return workspace.clientList(); }}
           : (workspace.windowList ? function() {{ return workspace.windowList(); }} : null);
var clients = listFn ? listFn() : [];
var out = [];
for (var i = 0; i < clients.length; i++) {{
    var c = clients[i];
    if (c.skipTaskbar || !c.normalWindow) continue;
    var g = c.frameGeometry || {{x: 0, y: 0, width: 0, height: 0}};
    out.push({{
        uuid: String(c.internalId || ''),
        windowId: Number(c.windowId || 0),
        pid: Number(c.pid || 0),
        title: String(c.caption || ''),
        resourceName: String(c.resourceName || ''),
        resourceClass: String(c.resourceClass || ''),
        desktopFile: String(c.desktopFileName || ''),
        minimized: Boolean(c.minimized),
        active: Boolean(c.active),
        fullscreen: Boolean(c.fullScreen),
        urgent: Boolean(c.demandsAttention),
        geom: [Math.round(g.x), Math.round(g.y), Math.round(g.width), Math.round(g.height)]
    }});
}}
callDBus('{self.service_name}', '/Bridge', '', 'report', JSON.stringify(out));
"""

    def _run_kwin_script(self, script_path, plugin_name):
        conn = QDBusConnection.sessionBus()
        scripting = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', conn)
        if not scripting.isValid():
            return False
        scripting.call('unloadScript', plugin_name)
        reply = scripting.call('loadScript', str(script_path), plugin_name)
        if not reply.arguments():
            return False
        script_id = reply.arguments()[0]
        for obj_path in (f'/{script_id}', f'/Scripting/Script{script_id}'):
            script_iface = QDBusInterface('org.kde.KWin', obj_path, 'org.kde.kwin.Script', conn)
            if script_iface.isValid():
                script_iface.call('run')
                break
        return True

    def _unload_kwin_script(self, plugin_name):
        conn = QDBusConnection.sessionBus()
        scripting = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', conn)
        if scripting.isValid():
            scripting.call('unloadScript', plugin_name)

    def _window_id_for(self, uuid_str, raw_win_id):
        if raw_win_id and int(raw_win_id) > 0:
            wid = int(raw_win_id)
            self.uuid_by_id[wid] = uuid_str
            return wid
        wid = self._id_by_uuid.get(uuid_str)
        if wid is None:
            self._next_synthetic_id += 1
            wid = self._next_synthetic_id
            self._id_by_uuid[uuid_str] = wid
        self.uuid_by_id[wid] = uuid_str
        return wid

    def snapshot(self):
        self.hidden.prune()
        if time.monotonic() - self.desktop_index_time > 30:
            self.desktop_index = DesktopIndex()
            self.desktop_index_time = time.monotonic()
        with self.lock:
            self.receiver.ready_event.clear()
            plugin = f'brisadock_enum_{os.getpid()}'
            if not self._run_kwin_script(self._enum_script, plugin):
                return []
            self.receiver.ready_event.wait(0.75)
            self._unload_kwin_script(plugin)
            with self.receiver.lock:
                raw_json = self.receiver.payload
        try:
            rows = json.loads(raw_json)
        except ValueError:
            return []
        result = []
        own_pid = os.getpid()
        for row in rows:
            raw_pid = int(row.get('pid') or 0)
            if raw_pid == own_pid:
                continue
            path = ''
            if raw_pid > 2:
                try:
                    path = os.readlink(f'/proc/{raw_pid}/exe')
                except OSError:
                    path = ''
            wm_class = tuple(
                v for v in (row.get('resourceName', ''), row.get('resourceClass', ''), row.get('desktopFile', '')) if v
            )
            launcher = self.desktop_index.resolve(wm_class, path)
            if not launcher and path and (
                '/libexec/' in path or Path(path).name.startswith(('xdg-desktop-portal', 'kwin_killer'))
            ):
                continue
            if not launcher and 'BrisaDock-Linux/.venv' in path and not any('fixture' in str(c).lower() for c in wm_class):
                continue
            if not launcher and not path and not wm_class:
                continue
            target = launcher['path'] if launcher else (path or (wm_class[-1] if wm_class else ''))
            identity = canonical(target) if (launcher or (path and not wm_class)) else 'wmclass:' + wm_class[-1].casefold()
            raw_id = self._window_id_for(row.get('uuid', ''), row.get('windowId', 0))
            is_minimized = bool(row.get('minimized'))
            is_active = bool(row.get('active'))
            tracked_hidden = self.hidden.tracked({'id': raw_id, 'pid': raw_pid})
            if tracked_hidden and not is_minimized and is_active:
                self.hidden.show({'id': raw_id, 'pid': raw_pid})
                tracked_hidden = False
            geom = row.get('geom') or [0, 0, 0, 0]
            fallback_name = (Path(path).stem if path else (wm_class[-1] if wm_class else 'Ventana'))
            result.append(dict(
                id=raw_id,
                uuid=row.get('uuid', ''),
                pid=raw_pid,
                path=target,
                key=identity,
                title=row.get('title') or fallback_name,
                name=launcher['name'] if launcher else fallback_name,
                minimized=is_minimized and not tracked_hidden,
                hidden=tracked_hidden,
                urgent=bool(row.get('urgent')),
                active=is_active,
                fullscreen=bool(row.get('fullscreen')),
                geometry=tuple(int(v) for v in geom[:4]),
                wm_class=wm_class,
            ))
        return result

    def _mutate_window(self, window_or_id, js_body):
        raw_id = window_or_id['id'] if isinstance(window_or_id, dict) else int(window_or_id or 0)
        uuid_str = (window_or_id.get('uuid') if isinstance(window_or_id, dict) else None) or self.uuid_by_id.get(raw_id, '')
        if not raw_id and not uuid_str:
            return False
        script_file = self._script_dir / 'action.js'
        js = f"""
var listFn = workspace.clientList ? function() {{ return workspace.clientList(); }}
           : (workspace.windowList ? function() {{ return workspace.windowList(); }} : null);
var clients = listFn ? listFn() : [];
for (var i = 0; i < clients.length; i++) {{
    var c = clients[i];
    if ((String(c.internalId) === {json.dumps(uuid_str)}) || (Number(c.windowId || 0) === {int(raw_id)})) {{
        {js_body}
        break;
    }}
}}
"""
        with self.lock:
            try:
                script_file.write_text(js, encoding='utf-8')
                plugin = f'brisadock_act_{os.getpid()}'
                ok = self._run_kwin_script(script_file, plugin)
                self._unload_kwin_script(plugin)
                return ok
            except OSError:
                return False

    def active_window_id(self):
        rows = self.snapshot()
        active = next((w['id'] for w in rows if w.get('active')), 0)
        return int(active)

    def activate_id(self, window_id):
        if not window_id:
            return False
        return self._mutate_window(
            int(window_id),
            'c.minimized = false; if ("activeClient" in workspace) { workspace.activeClient = c; } else if ("activeWindow" in workspace) { workspace.activeWindow = c; }',
        )

    def valid(self, window):
        wid = window.get('id', 0) if isinstance(window, dict) else int(window or 0)
        return bool(wid in self.uuid_by_id or wid > 0)

    def icon_geometry(self, window, rectangle):
        return True

    def activate(self, window):
        return self._mutate_window(
            window,
            'c.minimized = false; if ("activeClient" in workspace) { workspace.activeClient = c; } else if ("activeWindow" in workspace) { workspace.activeWindow = c; }',
        )

    def minimize(self, window):
        return self._mutate_window(window, 'c.minimized = true;')

    def close_window(self, window):
        return self._mutate_window(window, 'c.closeWindow();')

    def close(self):
        with self.lock:
            try:
                self.bus.unregisterObject('/Bridge')
                self.bus.unregisterService(self.service_name)
            except Exception:
                pass
            try:
                for p in self._script_dir.glob('*'):
                    p.unlink(missing_ok=True)
                self._script_dir.rmdir()
            except OSError:
                pass
