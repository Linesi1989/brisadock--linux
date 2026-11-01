"""Brisa Dock: an independent, free desktop launcher. MIT license."""
import base64
from collections import OrderedDict
import configparser
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QFileInfo, QStandardPaths, QUrl, QThread, Signal
from PySide6.QtGui import (QColor, QCursor, QDesktopServices, QFont, QPainter, QPainterPath,
                           QPen, QIcon, QPolygonF, QImage, QLinearGradient)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QFileDialog, QFileIconProvider, QMessageBox, QToolTip, QLabel
from desktop_backend import create_backend, merge_items, application_target, canonical
from dock_state import RecentApplications
from dock_icons import draw_builtin
from file_icons import stack_icon
from instance import VERSION
from icon_visuals import visible_icon, application_fallback
from minimized_tiles import MinimizedTiles, identity as tile_identity
from folder_content import ORDERS
from dock_zones import pin_zone, zoned_items, neighbor
from appearance import normalize as normalize_appearance, background as appearance_background
from display_policy import MODES, EdgeHandoff, screen_identity, select_screen
from linux_desktop import is_program, local_drop_paths

APP = 'BrisaDock'
FILE_MANAGER_NAMES = {'explorer', 'dolphin', 'archivos (dolphin)', 'archivos', 'files', 'nemo', 'nautilus', 'thunar'}
FILE_MANAGER_DESKTOPS = {'org.kde.dolphin.desktop', 'dolphin.desktop', 'org.gnome.nautilus.desktop', 'nemo.desktop', 'thunar.desktop'}


class WindowWatcher(QThread):
    changed = Signal(object, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_event = threading.Event()
        self.paths_lock = threading.Lock()
        self.paths = []
        self.backend = None
        self.phase = 'not-started'

    def set_paths(self, paths):
        with self.paths_lock:
            self.paths = list(paths)

    def run(self):
        try:
            self.phase = 'backend-start'
            self.backend = create_backend()
            self.phase = 'backend-ready'
            if hasattr(self.backend, 'hidden'):
                self.backend.hidden.configure(self.parent().config_path.with_name('hidden-windows.json'))
            cache = {}
            refreshed = {}
            last_windows = []
            trash_time = 0.
            trash_count = None
            while not self.stop_event.is_set():
                with self.paths_lock:
                    paths = list(self.paths)
                self.phase = 'resolve-launchers'
                for path in paths:
                    if self.stop_event.is_set():
                        break
                    if path not in cache or (path.startswith('shell:AppsFolder\\') and time.monotonic()-refreshed.get(path, 0) > 5):
                        cache[path] = application_target(path)
                        refreshed[path] = time.monotonic()
                try:
                    self.phase = 'window-snapshot'
                    windows = self.backend.snapshot()
                    if os.name != 'nt' and time.monotonic()-trash_time >= 5:
                        self.phase = 'trash-read'
                        from trash_linux import item_count
                        trash_count = item_count()
                        trash_time = time.monotonic()
                    cache['__trash_count__'] = trash_count
                    last_windows = windows
                    self.phase = 'notify'
                    self.changed.emit(windows, dict(cache), self.backend.status)
                    self.phase = 'idle'
                except Exception as error:
                    self.changed.emit(last_windows, dict(cache), f'Integración temporalmente no disponible: {type(error).__name__}')
                self.stop_event.wait(1.0)
        except Exception as error:
            self.changed.emit([], {}, f'Integración no disponible: {type(error).__name__}')
        finally:
            if self.backend:
                self.backend.close()


def read_settings(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('El perfil debe contener un objeto JSON.')
        data['pins'] = [p for p in data.get('pins', []) if isinstance(p, dict)
                        and isinstance(p.get('path'), str) and isinstance(p.get('name'), str)][:18]
        data['size'] = max(16, min(72, int(data.get('size', 48))))
        data['magnification'] = max(1.1, min(1.7, float(data.get('magnification', 1.48))))
        data['hide_delay'] = max(.2, min(5., float(data.get('hide_delay', 1.))))
        data['edge'] = data.get('edge') if data.get('edge') in ('bottom', 'left', 'right') else 'bottom'
        data['gap'] = max(0, min(32, int(data.get('gap', 0))))
        data['screen_mode'] = data.get('screen_mode') if data.get('screen_mode') in ('follow_edge', 'primary', 'selected') else 'follow_edge'
        preferences = data.get('folder_preferences', {})
        data['folder_preferences'] = {
            k: dict(pref) for k, pref in preferences.items() if isinstance(k, str) and isinstance(pref, dict)
        } if isinstance(preferences, dict) else {}
        data['animation_style'] = data.get('animation_style') if data.get('animation_style') in ('scale', 'sheet') else 'scale'
        return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f'No se puede leer el perfil {path}; se conserva sin cambios: {error}') from error


class Dock(QWidget):
    closed = Signal()
    appearance_changed = Signal()
    display_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Brisa Dock '+VERSION+' — integración X11')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.blur_shelf = None
        self.application_icons = None
        profile = QApplication.instance().property('brisaProfileDir') or QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        self.config_path = Path(profile) / 'settings.json'
        self.config = read_settings(self.config_path)
        self.appearance = normalize_appearance(self.config.get('appearance', {}))
        self.size = self.config.get('size', 48)
        self.auto_hide = bool(self.config.get('auto_hide', False))
        self.magnify = bool(self.config.get('magnify', True))
        self.light = bool(self.config.get('light', False))
        self.magnification = self.config.get('magnification', 1.48)
        self.hide_delay = self.config.get('hide_delay', 1.)
        self.edge = self.config.get('edge', 'bottom')
        self.gap = self.config.get('gap', 0)
        self.reserve_space = bool(self.config.get('reserve_space', False))
        self.appbar = None
        self.surface = None
        self.screen_mode = self.config.get('screen_mode', 'follow_edge')
        if self.screen_mode not in MODES:
            self.screen_mode = 'follow_edge'
        self.screen_id = self.config.get('screen_id', '')
        if not isinstance(self.screen_id, str):
            self.screen_id = ''
        self.handoff = EdgeHandoff()
        self.screen_handoff = self.handoff
        self.blur_enabled = bool(self.config.get('blur_enabled', True))
        self.external_drag = False
        self.drop_index = -1
        self.drop_label = ''
        self.drop_kind = ''
        self.spring_index = -1
        self.spring_timer = QTimer(self)
        self.spring_timer.setSingleShot(True)
        self.spring_timer.setInterval(650)
        self.spring_timer.timeout.connect(self.trigger_spring_folder)
        self.last_folder_close_path = ''
        self.last_folder_close_time = 0.
        self.resizing_separator = False
        self.resize_start_pos = None
        self.resize_start_size = self.size
        self.icon_hint_time = 0.
        self.active_capture_time = 0.
        self.minimize_into_app = bool(self.config.get('minimize_into_app', True))
        self.click_previews = bool(self.config.get('click_previews', False))
        self.animate_minimize = bool(self.config.get('animate_minimize', False))
        self.animate_window_buttons = bool(self.config.get('animate_window_buttons', False))
        self.keyboard_hotkey = bool(self.config.get('keyboard_hotkey', True))
        self.dock_hotkey = None
        self.keyboard_controller = None
        self.keyboard_panel = None
        self.keyboard_index = -1
        self.keyboard_launch = False
        self.last_context_action = None
        self.effects = []
        self.minimized_bounds = {}
        self.animation_style = self.config.get('animation_style', 'scale')
        self.sheet_frames = OrderedDict()
        self.sheet_pending = {}
        self.tile_pending = {}
        self.capture_broker = None
        self.tile_capture_broker = None
        self.minimized_tiles = MinimizedTiles()
        self.catalog = []
        self.catalog_time = 0
        self.catalog_worker = None
        self.hide_fullscreen = bool(self.config.get('hide_fullscreen', True))
        self.fullscreen_active = False
        self.fullscreen_shelf = None
        self.fullscreen_edge_active = False
        self.show_recent = bool(self.config.get('show_recent', True))
        self.recent = RecentApplications(self.config.get('recent_apps', []))
        self.show_attention = bool(self.config.get('show_attention', True))
        self.attention_requests = {}
        self.shell_attention = None
        self.pins = [p for p in self.config.get('pins', []) if not self.is_file_manager_launcher(p.get('path', ''))]
        self.provider = QFileIconProvider()
        self.icon_cache = {}
        from linux_icons import PersistentIcons
        self.persistent_icons = PersistentIcons(self.config_path.parent/'cache/icons')
        from folder_stacks_linux import FolderStacks
        self.folder_stacks = FolderStacks(self)
        self.folder_stacks.changed.connect(lambda *_: self.update())
        self.rects = []
        self.hover = -1
        self.hidden_amount = 0.0
        self.zoom = []
        self.bounce_index = -1
        self.bounce_until = 0
        self.menu_open = False
        self.last_inside = time.monotonic()
        self.windows = []
        self.targets = {}
        self.trash_count = None
        self.integration_status = 'Detectando ventanas…'
        self.press_pos = None
        self.press_pin = None
        self.press_item = None
        self.drag_target = None
        self.drag_snapshot = None
        self.drag_position = None
        self.drag_offsets = {}
        self.reorder_timer = QTimer(self)
        self.reorder_timer.setInterval(16)
        self.reorder_timer.timeout.connect(self.animate_reorder)
        self.dragged = False
        self.drag_cancelled = False
        self.removed_pin = None
        self.drag_original = None
        self.drag_path = None
        self.drag_ghost = None
        self.refresh_items()
        self.watcher = WindowWatcher(self)
        self.watcher.set_paths([p['path'] for p in self.pins] + ['https://www.google.com'])
        self.watcher.changed.connect(self.receive_windows)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        if os.name != 'nt' and os.environ.get('DISPLAY'):
            try:
                from x11_surface import X11Surface
                self.surface = X11Surface(self)
            except Exception:
                self.surface = None
        self.position_dock()
        self.show()
        self.sync_reservation()
        if os.name == 'nt':
            from appbar import AppBarHost
            self.appbar = AppBarHost(self)
            self.sync_reservation()
            try:
                from attention import ShellAttention
                self.shell_attention = ShellAttention(int(self.winId()))
            except (OSError, AttributeError):
                pass
        self.geometry_pending = False
        for screen in QApplication.screens():
            screen.availableGeometryChanged.connect(self.schedule_geometry)
        QApplication.instance().screenRemoved.connect(self.screen_removed)
        QApplication.instance().screenAdded.connect(self.screen_added)
        QApplication.instance().primaryScreenChanged.connect(self.schedule_geometry)
        self.watcher.start()
        QTimer.singleShot(150, self.warm_catalog)

    def warm_catalog(self):
        if getattr(self, 'closing', False) or self.catalog:
            return
        from apps_panel import CatalogWorker
        if self.catalog_worker is None or not self.catalog_worker.isRunning():
            worker = CatalogWorker(self)
            self.catalog_worker = worker
            worker.ready.connect(self.receive_catalog)
            worker.start()

    def receive_catalog(self, entries, complete=True):
        self.catalog = list(entries)
        if complete:
            self.catalog_time = time.monotonic()

    def trash_label(self):
        if self.trash_count is None:
            return 'Papelera'
        return 'Papelera vacía' if self.trash_count == 0 else f'Papelera · {self.trash_count} '+('elemento' if self.trash_count == 1 else 'elementos')

    @staticmethod
    def running_name(window):
        name = window['name']
        return {'chrome': 'Google Chrome', 'msedge': 'Microsoft Edge',
                'firefox': 'Firefox', 'explorer': 'Explorador de archivos',
                'dolphin': 'Archivos (Dolphin)', 'whatsapp.root': 'WhatsApp'}.get(name.lower(), name)

    @staticmethod
    def is_file_manager_launcher(path):
        if not path:
            return False
        name = Path(path).name.lower()
        return name in FILE_MANAGER_DESKTOPS or name in ('explorer.exe', 'dolphin')

    @classmethod
    def is_file_manager_window(cls, window):
        if os.name == 'nt':
            return window.get('name', '').lower() == 'explorer' or Path(window.get('path', '')).name.lower() == 'explorer.exe'
        if window.get('name', '').lower() in FILE_MANAGER_NAMES:
            return True
        if cls.is_file_manager_launcher(window.get('path', '')):
            return True
        wm_class = window.get('wm_class') or ()
        return any(str(part).lower() in ('dolphin', 'org.kde.dolphin', 'nemo', 'nautilus', 'thunar') for part in wm_class)

    def refresh_items(self):
        home = str(Path.home())
        downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or home
        grouped_windows = self.windows if self.minimize_into_app else [w for w in self.windows if not w.get('minimized')]
        file_windows = [w for w in grouped_windows if self.is_file_manager_window(w)]
        browser_target = self.targets.get('https://www.google.com', '')
        browser_windows = [w for w in grouped_windows if browser_target and w['key'] == canonical(browser_target)]
        self.items = [dict(name='Archivos', path=home, symbol='folder', windows=file_windows),
                      dict(name='Navegador', path='https://www.google.com', symbol='web', windows=browser_windows)]
        if browser_windows:
            browser = browser_windows[0]
            self.items[1] = dict(name=self.running_name(browser), path=browser['path'],
                                 symbol='web', windows=browser_windows, temporary=True)
        pinned_keys = {canonical(self.targets.get(p['path'], p['path'])) for p in self.pins if pin_zone(p, self.targets) == 'apps'}
        if browser_target and canonical(browser_target) in pinned_keys:
            self.items = self.items[:1]
        # File manager windows always combine into the built-in macOS Finder ('Archivos') icon.
        builtin_ids = {w['id'] for w in file_windows} | {w['id'] for w in browser_windows if w['key'] not in pinned_keys}
        applications, resources = zoned_items(self.pins, [w for w in grouped_windows if w['id'] not in builtin_ids], self.targets)
        applications = [app for app in applications if not self.is_file_manager_launcher(app.get('path', ''))]
        self.items += applications
        self.items.append(dict(name='Aplicaciones', path='', symbol='apps'))
        self.recent_start = len(self.items)
        excluded = pinned_keys | {window['key'] for window in self.windows}
        excluded |= {w['key'] for w in file_windows}
        excluded |= {canonical(browser_target)} if browser_target else set()
        if os.name == 'nt':
            excluded.add(canonical(str(Path(os.environ.get('WINDIR', 'C:\\Windows'))/'explorer.exe')))
        if self.show_recent:
            visible_recent = [r for r in self.recent.visible(excluded) if not self.is_file_manager_launcher(r.get('path', ''))]
            self.items += visible_recent
        self.utility_start = len(self.items)
        self.items += resources
        self.items.append(dict(name='Descargas', path=downloads, symbol='download'))
        self.minimized_tiles.update([w for w in self.windows if not w.get('hidden')])
        if not self.minimize_into_app:
            self.items += self.minimized_tiles.items()
        self.items.append(dict(name=self.trash_label(), path='shell:RecycleBinFolder' if os.name == 'nt' else 'trash:/',
                               symbol='trash', full=bool(self.trash_count)))
        self.zoom = [1.0] * len(self.items)
        if hasattr(self, 'watcher'):
            self.watcher.set_paths([p['path'] for p in self.pins] + ['https://www.google.com'])
        preferences = self.config.get('folder_preferences', {})
        stack_paths = []
        for candidate in [p['path'] for p in self.pins] + [downloads]:
            try:
                resolved = str(Path(candidate).resolve())
            except OSError:
                continue
            pref = preferences.get(resolved, {}) if isinstance(preferences, dict) else {}
            if pref.get('display') == 'stack' or pref.get('folder_display') == 'stack':
                stack_paths.append(candidate)
        self.folder_stacks.sync(stack_paths)
        self.resize_to_fit()
        if self.keyboard_controller:
            self.keyboard_controller.reconcile()

    def receive_windows(self, windows, targets, status):
        if self.menu_open or self.dragged or self.external_drag or self.resizing_separator:
            return
        previous_by_id = {(w['pid'], w['id']): w for w in self.windows}
        if self.show_recent and self.recent.observe(self.windows, windows):
            self.save()
        self.windows, self.targets, self.integration_status = windows, targets, status
        self.trash_count = targets.get('__trash_count__')
        alive = {(window['pid'], window['id']) for window in windows}
        active_apps = {window['key'] for window in windows if window.get('active')}
        self.attention_requests = {identity: stamp for identity, stamp in self.attention_requests.items()
                                   if identity in alive and not any((w['pid'], w['id']) == identity and w['key'] in active_apps for w in windows)}
        if self.show_attention:
            for window in windows:
                if window.get('urgent') and window['key'] not in active_apps:
                    self.request_attention((window['pid'], window['id']))

        # On X11, keep a fresh lightweight capture of the active normal window so native titlebar minimize can animate.
        if os.name != 'nt' and self.animate_minimize and self.animate_window_buttons:
            now = time.monotonic()
            active_win = next((w for w in windows if w.get('active') and not w.get('minimized') and not w.get('fullscreen')), None)
            if active_win is not None and now - self.active_capture_time >= 2.2:
                self.active_capture_time = now
                ident = (active_win['pid'], active_win['id'])
                geom = active_win.get('geometry')
                if geom and len(geom) == 4 and geom[2] > 40 and geom[3] > 40:
                    captured = self.capture_x11_window(active_win, max_size=(560, 360))
                    if captured is not None:
                        self.minimized_tiles.remember(active_win, captured, detailed=self.minimize_into_app)
                        self.sheet_frames.pop(ident, None)
                        self.sheet_frames[ident] = captured
                        self.minimized_bounds[ident] = QRect(*[int(v) for v in geom])
                        while sum(frame.sizeInBytes() for frame in self.sheet_frames.values()) > 32*1024*1024:
                            self.sheet_frames.popitem(last=False)

            for window in windows:
                ident = (window['pid'], window['id'])
                prev = previous_by_id.get(ident)
                if (prev and not prev.get('minimized') and window.get('minimized') and not window.get('hidden')
                        and not any(tile_identity(effect.window) == tile_identity(window) for effect in self.effects)):
                    origin = self.minimized_bounds.get(ident)
                    if origin is None and prev.get('geometry') and len(prev['geometry']) == 4:
                        origin = QRect(*[int(v) for v in prev['geometry']])
                        self.minimized_bounds[ident] = origin
                    image = self.sheet_frames.get(ident)
                    if self.animation_style == 'sheet' and image is not None and origin is not None:
                        self.start_sheet_effect(window, image, origin, False)
                    elif origin is not None:
                        self.start_minimize_effect(window, False)

        live_keep = {(window['pid'], window['id']) for window in windows
                     if window.get('minimized') or (self.animate_window_buttons and window.get('active'))}
        self.minimized_bounds = {key: bounds for key, bounds in self.minimized_bounds.items() if key in live_keep}
        self.sheet_frames = OrderedDict((key, image) for key, image in self.sheet_frames.items() if key in live_keep)
        fullscreen = False
        if os.name != 'nt':
            area = self.dock_screen.geometry()
            fullscreen = any(w.get('active') and w.get('fullscreen') and
                QRectF(*w.get('geometry', (0, 0, 0, 0))).intersects(QRectF(area)) for w in windows)
        if os.name == 'nt' and self.watcher.backend and hasattr(self.watcher.backend, 'u'):
            from ctypes import wintypes as W
            api = self.watcher.backend.u
            api.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]
            api.MonitorFromWindow.restype = W.HMONITOR
            monitor = api.MonitorFromWindow(int(self.winId()), 2)
            fullscreen = any(window.get('active') and window.get('fullscreen') and window.get('monitor') == monitor for window in windows)
        if fullscreen != self.fullscreen_active:
            self.fullscreen_active = fullscreen
            self.fullscreen_edge_active = False
            if self.fullscreen_shelf:
                self.fullscreen_shelf.hide()
            self.sync_reservation()
            self.position_dock()
        old_zoom = self.zoom[:]
        old_identity = [(i['path'], i.get('pin_index'), i.get('window_id')) for i in self.items]
        self.refresh_items()
        if old_identity == [(i['path'], i.get('pin_index'), i.get('window_id')) for i in self.items]:
            self.zoom = old_zoom
        self.update()

    def resize_to_fit(self):
        if not QApplication.screens():
            return
        screen = QApplication.screenAt(QCursor.pos()) if not hasattr(self, 'dock_screen') else self.dock_screen
        self.dock_screen = select_screen(self.screen_mode, self.screen_id, screen,
                                         QApplication.screens(), QApplication.primaryScreen())
        area = self.anchor_area()
        width = area.width() if self.edge == 'bottom' else area.height()
        spacing = min(18, max(6, self.size * .375))
        self.step = min(self.size + spacing, max(12, (width - 56 - 2*self.size) / max(1, len(self.items))))
        self.base_size = min(self.size, self.step - 6)
        length = int(self.step * len(self.items) + 44 + 2*self.size)
        self.resize(length, 186) if self.edge == 'bottom' else self.resize(186, length)
        self.position_dock()

    def anchor_area(self):
        if self.dock_screen not in QApplication.screens():
            self.dock_screen = QApplication.primaryScreen()
        area = self.dock_screen.geometry() if self.auto_hide else self.dock_screen.availableGeometry()
        if self.surface and self.reserve_space and not self.auto_hide:
            area = self.dock_screen.geometry()
        if self.fullscreen_active and self.hide_fullscreen:
            return self.dock_screen.geometry()
        if self.appbar and self.appbar.rect is not None:
            if self.edge == 'bottom':
                area.setBottom(self.appbar.rect.bottom())
            elif self.edge == 'left':
                area.setLeft(self.appbar.rect.left())
            else:
                area.setRight(self.appbar.rect.right())
        return area

    def schedule_geometry(self, *args):
        if getattr(self, 'closing', False) or getattr(self, 'geometry_pending', False):
            return
        self.geometry_pending = True
        def update():
            self.geometry_pending = False
            if getattr(self, 'closing', False):
                return
            self.sync_reservation()
            self.resize_to_fit()
            self.display_changed.emit()
        QTimer.singleShot(80, update)

    def screen_removed(self, screen):
        if self.dock_screen == screen or self.dock_screen not in QApplication.screens():
            self.dock_screen = QApplication.primaryScreen()
            self.schedule_geometry()

    def screen_added(self, screen):
        screen.availableGeometryChanged.connect(self.schedule_geometry)
        self.schedule_geometry()

    def update_screen(self):
        screens = QApplication.screens()
        if not screens:
            return
        chosen = select_screen(self.screen_mode, self.screen_id, self.dock_screen, screens, QApplication.primaryScreen())
        blocked = (self.dragged or self.press_pos is not None or self.menu_open or self.external_drag or self.resizing_separator
                   or bool(self.effects or self.sheet_pending) or self.keyboard_controller is not None)
        if self.screen_mode == 'follow_edge':
            target = self.handoff.poll(QCursor.pos(), self.edge, screens, chosen, time.monotonic(), blocked)
            chosen = target or chosen
        if chosen is not self.dock_screen and not blocked:
            self.dock_screen = chosen
            self.hidden_amount = 0
            self.last_inside = time.monotonic()
            self.sync_reservation()
            self.resize_to_fit()
            self.display_changed.emit()

    def sync_reservation(self):
        thickness = round((self.shelf_rect().height() if self.edge == 'bottom' else self.shelf_rect().width()) + 9 + self.gap)
        if self.surface:
            enabled = self.reserve_space and not self.auto_hide and not (self.fullscreen_active and self.hide_fullscreen)
            if not self.surface.configure(self.edge, self.dock_screen.geometry(), thickness, enabled):
                self.integration_status = 'Reserva no disponible en un borde interior entre monitores.'
        if self.appbar:
            if self.reserve_space and not self.auto_hide and not (self.fullscreen_active and self.hide_fullscreen):
                if not self.appbar.reserve(self.edge, thickness):
                    self.integration_status = 'Windows no pudo reservar el espacio del dock.'
            else:
                self.appbar.release()

    def layout_centers(self):
        widths = [self.step + self.base_size*(zoom-1) for zoom in self.zoom]
        length = self.width() if self.edge == 'bottom' else self.height()
        cursor = (length - sum(widths))/2
        centers = []
        for width in widths:
            centers.append(cursor + width/2)
            cursor += width
        return centers, sum(widths) + 26

    def shelf_rect(self):
        _, shelf_width = self.layout_centers()
        compact = max(0, 48 - self.base_size)
        if self.edge == 'bottom':
            return QRectF((self.width()-shelf_width)/2, 108+compact, shelf_width, 69-compact)
        return QRectF(9 if self.edge == 'left' else 108+compact,
                      (self.height()-shelf_width)/2, 69-compact, shelf_width)

    def separator_positions(self):
        centers, _ = self.layout_centers()
        boundaries = [self.utility_start]
        if self.recent_start < self.utility_start:
            boundaries.append(self.recent_start)
        return [(centers[b-1] + centers[b])/2 for b in boundaries if 0 < b < len(centers)]

    def separator_hit(self, point):
        shelf = self.shelf_rect()
        if not shelf.contains(point):
            return False
        coord = point.x() if self.edge == 'bottom' else point.y()
        return any(abs(coord - sx) <= 6 for sx in self.separator_positions())

    def position_dock(self):
        if not QApplication.screens():
            return
        if self.dock_screen not in QApplication.screens():
            self.dock_screen = QApplication.primaryScreen()
        area = self.anchor_area()
        offset = round(self.hidden_amount * (112+self.gap))
        if self.edge == 'bottom':
            self.move(area.center().x() - self.width() // 2, area.bottom()-self.height()+1-self.gap+offset)
        elif self.edge == 'left':
            self.move(area.left()+self.gap-offset, area.center().y()-self.height()//2)
        else:
            self.move(area.right()-self.width()+1-self.gap+offset, area.center().y()-self.height()//2)
        controller = getattr(self, 'keyboard_controller', None)
        if controller and controller.isVisible():
            controller.setGeometry(self.geometry())

    def item_rect(self, center, size, lift=0):
        if self.edge == 'bottom':
            return QRectF(center-size/2, 165-size-lift, size, size)
        if self.edge == 'left':
            return QRectF(21+lift, center-size/2, size, size)
        return QRectF(165-size-lift, center-size/2, size, size)

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(self.config)
        pins_to_save = self.drag_snapshot if self.drag_snapshot is not None else self.pins
        data.update(dict(
            size=self.size,
            auto_hide=self.auto_hide,
            magnify=self.magnify,
            light=self.light,
            magnification=self.magnification,
            hide_delay=self.hide_delay,
            edge=self.edge,
            gap=self.gap,
            reserve_space=self.reserve_space,
            screen_mode=self.screen_mode,
            screen_id=self.screen_id,
            appearance=self.appearance,
            blur_enabled=self.blur_enabled,
            animate_minimize=self.animate_minimize,
            animate_window_buttons=self.animate_window_buttons,
            minimize_into_app=self.minimize_into_app,
            click_previews=self.click_previews,
            keyboard_hotkey=self.keyboard_hotkey,
            animation_style=self.animation_style,
            hide_fullscreen=self.hide_fullscreen,
            show_recent=self.show_recent,
            recent_apps=self.recent.serialize(),
            show_attention=self.show_attention,
            folder_mode=self.config.get('folder_mode', 'auto'),
            folder_order=self.config.get('folder_order', 'date'),
            folder_display=self.config.get('folder_display', 'folder'),
            pins=pins_to_save,
        ))
        for key in ('folder_preferences', 'app_categories', 'apps_view', 'apps_layout'):
            if key in self.config:
                data[key] = self.config[key]
        temporary = self.config_path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(self.config_path)
        except OSError as error:
            QMessageBox.warning(self, APP, f'No se pudo guardar la configuración:\n{error}')

    def tick(self):
        self.update_screen()
        if self.surface:
            if self.hidden_amount > .8:
                self.surface.input_rectangle()
            else:
                if self.edge == 'bottom':
                    region = (0, 48, self.width(), 136)
                elif self.edge == 'left':
                    region = (0, 0, 126, self.height())
                else:
                    region = (60, 0, 126, self.height())
                self.surface.input_rectangle(region)
            shelf = self.shelf_rect()
            blur = (round(shelf.x()), round(shelf.y()), round(shelf.width()), round(shelf.height()))
            self.surface.blur(blur, self.blur_enabled and self.hidden_amount < .95)
            if self.hidden_amount < .1 and time.monotonic()-self.icon_hint_time > .7:
                self.icon_hint_time = time.monotonic()
                centers, _ = self.layout_centers()
                records = []
                for item, center in zip(self.items, centers):
                    rect = self.item_rect(center, self.base_size).toRect()
                    point = self.mapToGlobal(rect.topLeft())
                    records.extend((w, (point.x(), point.y(), rect.width(), rect.height())) for w in item.get('windows', []))
                self.surface.publish_icons(records)
        if self.keyboard_controller and self.keyboard_controller.isVisible():
            self.last_inside = time.monotonic()
            self.hover = self.keyboard_index
            return
        if self.press_pos is not None or self.resizing_separator:
            if self.drag_ghost:
                self.drag_ghost.move(QCursor.pos().x()-self.drag_ghost.width()//2, QCursor.pos().y()-self.drag_ghost.height()//2)
            self.last_inside = time.monotonic()
            self.update()
            return
        point = self.mapFromGlobal(QCursor.pos())
        inside = self.rect().contains(point)
        if self.hidden_amount > .8:
            area = self.anchor_area()
            cursor = QCursor.pos()
            if self.edge == 'bottom':
                inside = area.bottom()-3 <= cursor.y() <= area.bottom() and self.x() <= cursor.x() <= self.x()+self.width()
            elif self.edge == 'left':
                inside = area.left() <= cursor.x() <= area.left()+3 and self.y() <= cursor.y() <= self.y()+self.height()
            else:
                inside = area.right()-3 <= cursor.x() <= area.right() and self.y() <= cursor.y() <= self.y()+self.height()
        if inside and self.fullscreen_active and self.hidden_amount > .8:
            self.fullscreen_edge_active = True
        now = time.monotonic()
        if inside or self.menu_open or self.effects or self.sheet_pending or self.press_pos is not None or self.external_drag:
            self.last_inside = now
        timed_hide = self.auto_hide and now-self.last_inside > self.hide_delay
        full_hide = self.hide_fullscreen and self.fullscreen_active and now-self.last_inside > min(self.hide_delay, .35)
        target = 1.0 if timed_hide or full_hide else 0.0
        old = self.hidden_amount
        self.hidden_amount += (target - old) * 0.22
        if abs(target - self.hidden_amount) < 0.01:
            self.hidden_amount = target
        changed = abs(self.hidden_amount - old) > 0.001
        if self.hidden_amount > .99:
            self.fullscreen_edge_active = False
        old_hover = self.hover
        self.hover = -1
        axis = point.x() if self.edge == 'bottom' else point.y()
        centers, _ = self.layout_centers()
        on_separator = inside and self.hidden_amount < 0.3 and self.separator_hit(QPointF(point))
        if inside and self.hidden_amount < 0.3:
            self.setCursor(
                (Qt.SizeVerCursor if self.edge == 'bottom' else Qt.SizeHorCursor)
                if on_separator else Qt.ArrowCursor
            )
            if not on_separator:
                for i in range(len(self.items)):
                    center = centers[i]
                    if abs(axis - center) < self.step / 2:
                        self.hover = i
        for i in range(len(self.items)):
            distance = abs(axis - centers[i])
            goal = 1 + (self.magnification-1) * math.exp(-((distance / (self.step * 1.15)) ** 2)) if self.magnify and inside and target == 0 and not on_separator else 1
            previous = self.zoom[i]
            self.zoom[i] += (goal - previous) * 0.25
            changed |= abs(previous - self.zoom[i]) > 0.001
        if changed:
            self.position_dock()
        attention_animation = any(now-stamp < 1.2 for stamp in self.attention_requests.values())
        if changed or inside or self.hover != old_hover or now < self.bounce_until or attention_animation:
            self.update()
        if os.name != 'nt' and self.fullscreen_active and self.hidden_amount < .99 and (self.fullscreen_edge_active or (not self.hide_fullscreen and not self.auto_hide)):
            if self.fullscreen_shelf is None:
                from fullscreen_shelf import FullscreenShelf
                self.fullscreen_shelf = FullscreenShelf(self)
            self.fullscreen_shelf.refresh()
        elif self.fullscreen_shelf:
            self.fullscreen_shelf.hide()
        self.timer.setInterval(16 if changed or inside or now < self.bounce_until or attention_animation else 80)

    def icon_for(self, item, high_resolution=True):
        raw_path = item.get('path', '')
        path = ''
        if raw_path and not raw_path.startswith(('https://', 'http://', 'shell:', 'trash:')):
            try:
                path = str(Path(raw_path).resolve())
            except OSError:
                path = raw_path
        if path and path in self.folder_stacks.icons:
            return self.folder_stacks.icons[path]
        if item.get('directory') or item.get('kind') == 'folder' or (path and Path(path).is_dir() and item.get('symbol') != 'folder'):
            return stack_icon(path or raw_path, directory=True)
        return self.persistent_icons.get(raw_path, self.provider)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        centers, _ = self.layout_centers()
        shelf = self.shelf_rect()
        painter.setPen(Qt.NoPen)
        for pad in range(7, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 5))
            painter.drawRoundedRect(shelf.adjusted(-pad, -pad / 2, pad, pad), 23, 23)
        # Outer dark hairline + inner translucent glass surface + specular highlight rim
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 55 if self.light else 95), 1))
        painter.drawRoundedRect(shelf.adjusted(-.5, -.5, .5, .5), 21.5, 21.5)
        painter.setBrush(appearance_background(self.appearance, 'dock', self.light))
        painter.setPen(QPen(QColor(255, 255, 255, 130 if self.light else 82), 1))
        painter.drawRoundedRect(shelf, 21, 21)
        # Subtle top glass sheen like macOS Sonoma/Sequoia Dock
        sheen = QLinearGradient(shelf.topLeft(), shelf.bottomLeft())
        sheen.setColorAt(0.0, QColor(255, 255, 255, 42 if self.light else 24))
        sheen.setColorAt(0.45, QColor(255, 255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(sheen)
        painter.drawRoundedRect(shelf.adjusted(1, 1, -1, -1), 20, 20)

        for sx in self.separator_positions():
            painter.setPen(QPen(QColor(40, 40, 48, 55) if self.light else QColor(255, 255, 255, 68), 1))
            if self.edge == 'bottom':
                inset = min(15, shelf.height()*.22)
                painter.drawLine(QPointF(sx, shelf.top()+inset), QPointF(sx, shelf.bottom()-inset))
            else:
                inset = min(15, shelf.width()*.22)
                painter.drawLine(QPointF(shelf.left()+inset, sx), QPointF(shelf.right()-inset, sx))

        self.rects = []
        hovered_rect = None
        for i, item in enumerate(self.items):
            painter.save()
            if item.get('windows') and all(window.get('hidden') for window in item['windows']):
                painter.setOpacity(.5)
            if self.dragged and not self.drag_cancelled and self.press_pin is not None and item.get('pin_index') == self.press_pin:
                painter.setOpacity(.18)
            size = self.base_size * self.zoom[i]
            bounce = max(0, self.bounce_until - time.monotonic())
            lift = abs(math.sin(bounce * 15)) * 13 if i == self.bounce_index and bounce else 0
            stamps = [self.attention_requests[(w['pid'], w['id'])] for w in item.get('windows', [])
                      if (w['pid'], w['id']) in self.attention_requests]
            if stamps and self.show_attention:
                age = time.monotonic()-max(stamps)
                if age < 1.2:
                    lift = max(lift, abs(math.sin(age*10))*12*(1-age/1.2))
            visual_center = centers[i] + self.drag_offsets.get(item['path'], 0)
            rect = self.item_rect(visual_center, size, lift)
            self.rects.append(rect)
            if i == self.hover:
                hovered_rect = rect
            if self.dragged and not self.drag_cancelled and self.drag_target is not None and item.get('pin_index') == self.drag_target:
                painter.setPen(QPen(QColor('#8dd5ff'), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-5, -5, 5, 5), 12, 12)
            if i == self.drop_index:
                painter.setPen(QPen(QColor('#8dd5ff'), 2))
                painter.setBrush(QColor(65, 155, 225, 90))
                painter.drawRoundedRect(rect.adjusted(-4, -4, 4, 4), 12, 12)
            symbol = item.get('symbol')
            resolved_path = ''
            if item.get('path') and not item['path'].startswith(('https://', 'http://', 'shell:', 'trash:')):
                try:
                    resolved_path = str(Path(item['path']).resolve())
                except OSError:
                    resolved_path = ''
            if item.get('minimized_window') or item.get('minimized_tile'):
                self.minimized_tiles.draw(painter, rect, item, self.icon_for(item), self.light)
            elif resolved_path and resolved_path in self.folder_stacks.icons and symbol != 'folder':
                self.folder_stacks.icons[resolved_path].paint(painter, rect.toRect())
            elif symbol:
                if symbol == 'web' and item.get('temporary') and item.get('path') and not item['path'].startswith(('https://', 'http://')):
                    self.icon_for(item).paint(painter, rect.toRect())
                else:
                    draw_builtin(painter, rect, 'trash_full' if symbol == 'trash' and (item.get('full') or self.trash_count) else symbol)
            else:
                self.icon_for(item).paint(painter, rect.toRect())
            # D20: macOS question-mark overlay when a pinned item's target path is missing on disk
            if ('pin_index' in item and item.get('path')
                    and not item['path'].startswith(('https://', 'http://', 'shell:', 'trash:'))
                    and not Path(item['path']).exists()):
                q_size = max(14, rect.width() * 0.42)
                q_rect = QRectF(rect.center().x() - q_size/2, rect.center().y() - q_size/2, q_size, q_size)
                painter.setPen(QPen(QColor(255, 255, 255, 210), 1.2))
                painter.setBrush(QColor(40, 44, 52, 215))
                painter.drawEllipse(q_rect)
                painter.setFont(QFont('Sans Serif', max(8, int(q_size * 0.58)), QFont.Bold))
                painter.setPen(QColor('#ffffff'))
                painter.drawText(q_rect, Qt.AlignCenter, '?')
            if i == self.keyboard_index:
                painter.setPen(QPen(QColor('#79bcff'), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-5, -5, 5, 5), 12, 12)
            # macOS red notification/attention badge on top-right corner (Refs C & D)
            if stamps and self.show_attention:
                badge_r = max(7.0, min(11.0, rect.width() * 0.19))
                center_pt = QPointF(rect.right() - badge_r * 0.55, rect.top() + badge_r * 0.65)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, 55))
                painter.drawEllipse(center_pt + QPointF(0, 1.2), badge_r, badge_r)
                painter.setBrush(QColor('#ff3b30'))
                painter.setPen(QPen(QColor(255, 255, 255, 195), 1.0))
                painter.drawEllipse(center_pt, badge_r, badge_r)
                painter.setFont(QFont('Sans Serif', max(7, int(badge_r * 0.95)), QFont.Bold))
                painter.setPen(QColor('#ffffff'))
                badge_rect = QRectF(center_pt.x() - badge_r, center_pt.y() - badge_r, badge_r * 2, badge_r * 2)
                painter.drawText(badge_rect, Qt.AlignCenter, str(len(stamps)) if len(stamps) > 1 else '1')
            if item.get('windows') and not item.get('minimized_window') and not item.get('minimized_tile'):
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor('#525256' if self.light else '#e9e9ec'))
                point = (QPointF(rect.center().x(), 171) if self.edge == 'bottom'
                         else QPointF(15 if self.edge == 'left' else 171, rect.center().y()))
                painter.drawEllipse(point, 2.4, 2.4)
            painter.restore()

        # Draw unified macOS callout bubble for hovered item on all edges (Ref C)
        if (0 <= self.hover < len(self.items) and hovered_rect is not None
                and not self.external_drag and not self.menu_open and not self.dragged and not self.resizing_separator):
            painter.save()
            text = self.items[self.hover]['name'][:45]
            painter.setFont(QFont('Segoe UI' if os.name == 'nt' else 'Sans Serif', 10))
            metrics = painter.fontMetrics()
            bubble_fill = QColor(246, 248, 252, 244) if self.light else QColor(36, 37, 42, 244)
            bubble_text = QColor('#1d1d1f' if self.light else '#f5f5f7')
            bubble_border = QColor(0, 0, 0, 32) if self.light else QColor(255, 255, 255, 58)
            if self.edge == 'bottom':
                tw = metrics.horizontalAdvance(text) + 24
                tx = max(2, min(self.width() - tw - 2, hovered_rect.center().x() - tw / 2))
                label = QRectF(tx, max(2, hovered_rect.top()-38), tw, 27)
                pointer = max(label.left()+10, min(label.right()-10, hovered_rect.center().x()))
                arrow = QPolygonF([QPointF(pointer-5.5, label.bottom()-1),
                                   QPointF(pointer+5.5, label.bottom()-1),
                                   QPointF(pointer, label.bottom()+6)])
            elif self.edge == 'left':
                avail = max(60, self.width() - hovered_rect.right() - 14)
                text = metrics.elidedText(text, Qt.ElideRight, int(avail - 16))
                tw = min(avail, metrics.horizontalAdvance(text) + 20)
                tx = hovered_rect.right() + 10
                ty = max(2, min(self.height() - 29, hovered_rect.center().y() - 13.5))
                label = QRectF(tx, ty, tw, 27)
                pointer = max(label.top()+7, min(label.bottom()-7, hovered_rect.center().y()))
                arrow = QPolygonF([QPointF(label.left()+1, pointer-5.5),
                                   QPointF(label.left()+1, pointer+5.5),
                                   QPointF(label.left()-6, pointer)])
            else:
                avail = max(60, hovered_rect.left() - 14)
                text = metrics.elidedText(text, Qt.ElideRight, int(avail - 16))
                tw = min(avail, metrics.horizontalAdvance(text) + 20)
                tx = hovered_rect.left() - 10 - tw
                ty = max(2, min(self.height() - 29, hovered_rect.center().y() - 13.5))
                label = QRectF(tx, ty, tw, 27)
                pointer = max(label.top()+7, min(label.bottom()-7, hovered_rect.center().y()))
                arrow = QPolygonF([QPointF(label.right()-1, pointer-5.5),
                                   QPointF(label.right()-1, pointer+5.5),
                                   QPointF(label.right()+6, pointer)])
            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(label, 8.5, 8.5)
            arrow_path = QPainterPath()
            arrow_path.addPolygon(arrow)
            unified = bubble_path.united(arrow_path)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 28 if self.light else 55))
            painter.drawPath(unified.translated(0, 1.5))
            painter.setPen(QPen(bubble_border, 1))
            painter.setBrush(bubble_fill)
            painter.drawPath(unified)
            painter.setPen(bubble_text)
            painter.drawText(label, Qt.AlignCenter, text)
            painter.restore()

        if self.dragged and not self.drag_cancelled and self.drag_position is not None and self.press_item and not self.drag_ghost:
            size = self.base_size * 1.08
            rect = QRectF(self.drag_position.x()-size/2, self.drag_position.y()-size/2, size, size)
            item = self.press_item
            painter.save()
            painter.setOpacity(.95)
            if item.get('symbol'):
                draw_builtin(painter, rect, item['symbol'])
            else:
                self.icon_for(item).paint(painter, rect.toRect())
            painter.restore()

        if self.external_drag and self.drop_label:
            painter.setFont(QFont('Segoe UI' if os.name == 'nt' else 'Sans Serif', 10))
            text = self.drop_label[:48]
            tw = painter.fontMetrics().horizontalAdvance(text) + 22
            center_x = self.rects[self.drop_index].center().x() if 0 <= self.drop_index < len(self.rects) else self.width()/2
            tx = max(4, min(self.width()-tw-4, center_x-tw/2))
            label = QRectF(tx, 62, tw, 26)
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            painter.setBrush(QColor(246, 248, 252, 244) if self.light else QColor(28, 28, 32, 240))
            painter.drawRoundedRect(label, 8, 8)
            painter.setPen(QColor('#1d1d1f' if self.light else 'white'))
            painter.drawText(label, Qt.AlignCenter, text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.dragged:
            self.drag_cancelled = True
            self.clear_drag_ghost()
            self.restore_drag_order()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            self.clearFocus()
            event.accept()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            direction = -1 if event.key() in (Qt.Key_Left, Qt.Key_Up) else 1
            self.hover = (self.hover+direction) % len(self.items)
            self.update()
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Space) and self.hover >= 0:
            self.launch(self.hover)
            event.accept()
        else:
            super().keyPressEvent(event)

    def launch(self, index, force_new=False):
        item = self.items[index]
        if item.get('minimized_window') or item.get('minimized_tile'):
            if item.get('window_overflow'):
                self.window_overview(item)
            elif item.get('windows'):
                self.window_action('activate', item['windows'][0])
            return
        if item.get('symbol') == 'apps':
            self.applications_panel()
            return
        windows = item.get('windows', [])
        if windows and not force_new:
            if len(windows) > 1 and self.click_previews:
                self.window_overview(item)
                return
            self.show_application(item)
            chosen = next((w for w in windows if w['active']), next((w for w in windows if not w['minimized']), windows[0]))
            self.window_action('activate', chosen)
            return
        if not force_new and item.get('path') and Path(item['path']).is_dir() and item.get('symbol') != 'folder':
            resolved = str(Path(item['path']).resolve())
            if resolved == self.last_folder_close_path and time.monotonic() - self.last_folder_close_time < 0.22:
                self.last_folder_close_path = ''
                return
            self.folder_stack(item)
            return
        self.bounce_index = index
        self.bounce_until = time.monotonic() + 0.65
        if force_new and item.get('symbol') == 'folder' and os.name != 'nt' and shutil.which('dolphin'):
            try:
                subprocess.Popen(['dolphin', '--new-window', item['path']])
                return
            except OSError:
                pass
        self.open_path(item['path'])

    def open_path(self, target):
        try:
            if os.name == 'nt' and target.startswith('shell:AppsFolder\\'):
                os.startfile(target)
            elif os.name != 'nt' and target.endswith('.desktop'):
                subprocess.Popen(['gio', 'launch', target])
            elif os.name != 'nt' and is_program(target):
                subprocess.Popen([target])
            else:
                QDesktopServices.openUrl(QUrl(target) if target.startswith(('https://', 'http://', 'trash:')) else QUrl.fromLocalFile(target))
            return True
        except OSError as error:
            QMessageBox.warning(self, APP, f'No se pudo abrir {target}:\n{error}')
            return False

    def reveal_in_file_manager(self, path):
        if not path or path.startswith(('https://', 'http://', 'shell:', 'trash:')):
            return
        resolved = Path(path).resolve()
        target = resolved if resolved.exists() else resolved.parent
        if not target.exists():
            return
        if os.name != 'nt' and resolved.exists() and shutil.which('dolphin'):
            try:
                subprocess.Popen(['dolphin', '--select', str(resolved)])
                return
            except OSError:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target if target.is_dir() else target.parent)))

    def force_quit_application(self, item):
        windows = item.get('windows', [])
        pids = sorted({int(w['pid']) for w in windows if w.get('pid') and int(w['pid']) != os.getpid()})
        if not pids:
            return
        previous = self.menu_open
        self.menu_open = True
        try:
            answer = QMessageBox.question(
                self,
                APP,
                f"¿Forzar la salida de «{item['name']}»?\nSe perderán los cambios no guardados en sus ventanas abiertas.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
        finally:
            self.menu_open = previous
            self.last_inside = time.monotonic()

    def empty_trash_prompt(self):
        from trash_linux import empty_trash, item_count
        previous = self.menu_open
        self.menu_open = True
        try:
            answer = QMessageBox.question(
                self,
                APP,
                '¿Seguro que quieres vaciar la Papelera de forma permanente?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes and empty_trash():
                self.trash_count = item_count()
                self.refresh_items()
                self.update()
        finally:
            self.menu_open = previous
            self.last_inside = time.monotonic()

    def show_application(self, item):
        hidden = getattr(self.watcher.backend, 'hidden', None)
        if hidden:
            for window in item.get('windows', []):
                hidden.show(window)
                window['hidden'] = False

    def hide_application(self, item, others=False):
        hidden = getattr(self.watcher.backend, 'hidden', None)
        if not hidden:
            return
        targets = ([window for window in self.windows if not window.get('hidden')
                    and window['key'] not in {entry['key'] for entry in item.get('windows', [])}]
                   if others else item.get('windows', []))
        target_ids = {window['id'] for window in targets}
        for token, request in list(self.sheet_pending.items()):
            if request[0]['id'] in target_ids:
                self.sheet_pending.pop(token, None)
        for effect in self.effects[:]:
            if effect.window['id'] in target_ids:
                effect.suppress_restore = True
                effect.close()
        failures = sum(not hidden.hide(window) for window in targets if hidden.can_hide(window))
        for window in targets:
            if hidden.tracked(window):
                window['hidden'] = True
                window['minimized'] = False
        self.refresh_items()
        self.update()
        if failures:
            self.integration_status = 'El sistema no permitió ocultar alguna ventana; puedes seguir usando el dock.'

    def show_hidden_applications(self):
        hidden = getattr(self.watcher.backend, 'hidden', None)
        if hidden:
            hidden.restore_all()
            for window in self.windows:
                window['hidden'] = False
            self.refresh_items()
            self.update()

    def nativeEvent(self, event_type, message):
        hook = getattr(self, 'shell_attention', None)
        if hook and hook.available:
            hwnd = hook.event_window(event_type, message)
            if hwnd and self.show_attention:
                for window in self.windows:
                    if window['id'] == hwnd and not window.get('active'):
                        self.request_attention((window['pid'], window['id']))
        return super().nativeEvent(event_type, message)

    def request_attention(self, identity):
        now = time.monotonic()
        if now - self.attention_requests.get(identity, 0) > 1.0:
            self.attention_requests[identity] = now
            self.timer.setInterval(16)
            self.update()

    def begin_keyboard_navigation(self, preferred=None):
        if getattr(self, 'closing', False) or not self.items:
            return
        from keyboard_dock import KeyboardDock
        if self.keyboard_controller:
            self.keyboard_controller.raise_()
            self.keyboard_controller.activateWindow()
            return
        self.hidden_amount = 0.0
        self.last_inside = time.monotonic()
        self.position_dock()
        controller = KeyboardDock(self, preferred)
        self.keyboard_controller = controller
        controller.show()
        controller.raise_()
        controller.activateWindow()
        controller.setFocus()
        self.update()

    def keyboard_focus(self):
        from panels import KeyboardPanel
        current = getattr(self, 'keyboard_panel', None)
        if current is not None and current.isVisible():
            current.raise_()
            current.activateWindow()
            return
        self.reveal_instance()
        self.menu_open = True
        panel = KeyboardPanel(self)
        self.keyboard_panel = panel
        def finished(*_):
            self.menu_open = False
            self.last_inside = time.monotonic()
            self.keyboard_panel = None
            panel.deleteLater()
        panel.finished.connect(finished)
        panel.show()
        panel.activateWindow()

    def reveal_instance(self):
        self.show()
        self.hidden_amount = 0
        self.last_inside = time.monotonic()+1.5
        self.position_dock()
        self.raise_()

    def clear_recent(self):
        self.recent.clear()
        self.save()
        self.refresh_items()

    def remove_recent(self, key):
        self.recent.remove(key)
        self.save()
        self.refresh_items()

    def applications_panel(self):
        from apps_panel import ApplicationsPanel
        self.menu_open = True
        panel = ApplicationsPanel(self)
        try:
            panel.exec()
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()
            panel.deleteLater()

    def running_applications(self):
        groups = {}
        for window in self.windows:
            entry = groups.setdefault(window['key'], dict(name=self.running_name(window),
                                        path=window['path'], windows=[], key=window['key']))
            entry['windows'].append(window)
        return sorted(groups.values(), key=lambda entry: entry['name'].casefold())

    def running_applications_panel(self):
        from running_apps_panel import RunningAppsPanel
        self.menu_open = True
        panel = RunningAppsPanel(self)
        try:
            panel.exec()
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()
            panel.deleteLater()

    def pin_application(self, entry, persist=True):
        path = entry['path']
        if self.is_file_manager_launcher(path):
            return
        key = canonical(self.targets.get(path, path))
        if any(canonical(self.targets.get(pin['path'], pin['path'])) == key for pin in self.pins):
            return
        if len(self.pins) >= 18:
            QMessageBox.information(self, APP, 'Se admiten hasta 18 accesos personalizados.')
            return
        if Path(path).exists() or (os.name == 'nt' and path.startswith('shell:AppsFolder\\')):
            self.pins.append(dict(name=entry['name'], path=path, kind='app'))
            if persist:
                self.save()
            self.refresh_items()

    def pin_catalog_entry(self, entry, global_position):
        if self.is_file_manager_launcher(entry.get('path', '')):
            return True
        key = canonical(self.targets.get(entry['path'], entry['path']))
        if any(canonical(self.targets.get(pin['path'], pin['path'])) == key for pin in self.pins):
            return True
        if len(self.pins) >= 18:
            self.integration_status = 'No se añadió la app: ya hay 18 accesos personalizados.'
            return False
        previous = len(self.pins)
        self.pin_application(entry)
        if len(self.pins) == previous:
            self.integration_status = 'No se añadió la app: su acceso ya no está disponible.'
            return False
        source = len(self.pins)-1
        destination = self.pin_drag_destination(self.mapFromGlobal(global_position), source)
        if destination is not None and source != destination:
            self.pins.insert(destination, self.pins.pop(source))
            self.save()
            self.refresh_items()
        return True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.resizing_separator:
            self.resizing_separator = False
            self.resize_start_pos = None
            self.save()
            self.sync_reservation()
            QToolTip.hideText()
            self.update()
            return
        if event.button() == Qt.LeftButton and self.dragged:
            source = self.press_pin
            if self.drag_cancelled:
                self.restore_drag_order()
            elif source is not None and 0 <= source < len(self.pins):
                if self.pin_removal_zone(event.position()):
                    self.drag_snapshot = None
                    self.change_pin(source, 0)
                elif self.pin_drag_destination(event.position(), source) is not None:
                    self.drag_snapshot = None
                    self.save()
                else:
                    self.restore_drag_order()
            else:
                self.restore_drag_order()
            self.clear_drag_ghost()
            self.drag_original = None
            self.drag_path = None
            QToolTip.hideText()
        if event.button() == Qt.LeftButton and not self.dragged and self.press_pos is not None:
            for i, rect in enumerate(self.rects):
                if rect.contains(event.position()):
                    if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.AltModifier):
                        self.reveal_in_file_manager(self.items[i].get('path', ''))
                    elif event.modifiers() & Qt.ControlModifier and self.items[i].get('windows'):
                        self.window_overview(self.items[i])
                    elif event.modifiers() & Qt.AltModifier:
                        for window in self.items[i].get('windows', []):
                            self.window_action('minimize', window)
                    else:
                        self.launch(i, bool(event.modifiers() & Qt.ShiftModifier))
                    break
        if event.button() == Qt.LeftButton:
            self.press_pos, self.press_pin, self.dragged = None, None, False
            self.press_item, self.drag_target = None, None
            self.drag_snapshot, self.drag_position = None, None
            self.drag_cancelled = False
            self.last_inside = time.monotonic()
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton and self.resizing_separator:
            self.resizing_separator = False
            self.size = self.resize_start_size
            self.refresh_items()
            self.sync_reservation()
            QToolTip.hideText()
            self.update()
            return
        if event.button() == Qt.RightButton and self.press_pos is not None:
            self.drag_cancelled = True
            self.clear_drag_ghost()
            self.restore_drag_order()
            QToolTip.hideText()
            return
        if event.button() == Qt.LeftButton:
            if self.separator_hit(event.position()):
                self.resizing_separator = True
                self.resize_start_pos = event.globalPosition()
                self.resize_start_size = self.size
                return
            self.press_pos = event.position().toPoint()
            self.dragged = False
            self.drag_snapshot = None
            self.drag_position = None
            self.drag_cancelled = False
            self.press_item = next((dict(item) for item, rect in zip(self.items, self.rects)
                                    if rect.contains(event.position())), None)
            self.press_pin = next((item.get('pin_index') for item, rect in zip(self.items, self.rects)
                                   if rect.contains(event.position())), None)

    def mouseMoveEvent(self, event):
        if self.resizing_separator and event.buttons() & Qt.LeftButton and self.resize_start_pos is not None:
            if self.edge == 'bottom':
                delta = self.resize_start_pos.y() - event.globalPosition().y()
            elif self.edge == 'left':
                delta = event.globalPosition().x() - self.resize_start_pos.x()
            else:
                delta = self.resize_start_pos.x() - event.globalPosition().x()
            new_size = max(16, min(72, round(self.resize_start_size + delta * 0.45)))
            if new_size != self.size:
                self.size = new_size
                self.refresh_items()
            QToolTip.showText(event.globalPosition().toPoint(), f'Tamaño del Dock: {self.size} px', self)
            return
        if self.press_pos is None or self.drag_cancelled or not event.buttons() & Qt.LeftButton:
            return
        if not self.dragged and (event.position().toPoint() - self.press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        if self.press_pin is None:
            item = self.press_item or {}
            if not item.get('temporary') or item.get('minimized_window') or item.get('minimized_tile'):
                return
            self.dragged = True
            if len(self.pins) >= 18:
                return
            if self.drag_snapshot is None:
                self.drag_snapshot = [dict(pin) for pin in self.pins]
            self.pin_application(item, persist=False)
            key = canonical(item['path'])
            self.press_pin = next((i for i, pin in enumerate(self.pins)
                                   if canonical(self.targets.get(pin['path'], pin['path'])) == key), None)
            if self.press_pin is None:
                return
        if not self.dragged:
            self.drag_original = [dict(pin) for pin in self.pins]
            self.drag_path = self.pins[self.press_pin]['path']
            ghost = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
            ghost.setAttribute(Qt.WA_TranslucentBackground)
            ghost.setAttribute(Qt.WA_TransparentForMouseEvents)
            size = max(24, self.base_size)
            ghost.setPixmap(self.icon_for(dict(path=self.drag_path)).pixmap(round(size), round(size)))
            ghost.setWindowOpacity(.88)
            ghost.adjustSize()
            ghost.show()
            self.drag_ghost = ghost
        self.dragged = True
        if self.drag_snapshot is None:
            self.drag_snapshot = [dict(pin) for pin in self.pins]
        if self.drag_ghost:
            self.drag_ghost.move(round(event.globalPosition().x()-self.drag_ghost.width()/2),
                                 round(event.globalPosition().y()-self.drag_ghost.height()/2))
        self.drag_position = QPointF(event.position())
        self.drag_target = self.pin_drag_destination(event.position(), self.press_pin)
        if self.drag_target is not None and self.drag_target != self.press_pin and not self.pin_removal_zone(event.position()):
            centers, _ = self.layout_centers()
            before = {item['path']: centers[i]+self.drag_offsets.get(item['path'], 0)
                      for i, item in enumerate(self.items) if 'pin_index' in item}
            self.pins.insert(self.drag_target, self.pins.pop(self.press_pin))
            self.press_pin = self.drag_target
            self.refresh_items()
            centers, _ = self.layout_centers()
            self.drag_offsets = {item['path']: before.get(item['path'], centers[i])-centers[i]
                                 for i, item in enumerate(self.items) if 'pin_index' in item}
            self.reorder_timer.start()
        self.update()
        if not self.drag_cancelled:
            label = 'Quitar del dock' if self.pin_removal_zone(event.position()) else 'Mover acceso · clic derecho para cancelar'
            QToolTip.showText(event.globalPosition().toPoint(), label, self)

    def clear_drag_ghost(self):
        if self.drag_ghost:
            self.drag_ghost.close()
            self.drag_ghost.deleteLater()
            self.drag_ghost = None

    def restore_drag_order(self):
        if self.drag_snapshot is not None:
            self.pins = [dict(pin) for pin in self.drag_snapshot]
            self.drag_snapshot = None
            self.drag_offsets.clear()
            self.reorder_timer.stop()
            self.refresh_items()
            self.update()

    def animate_reorder(self):
        self.drag_offsets = {path: offset*.68 for path, offset in self.drag_offsets.items() if abs(offset) > .3}
        if not self.drag_offsets:
            self.reorder_timer.stop()
        self.update()

    def pin_drag_destination(self, position, source):
        if not 0 <= source < len(self.pins):
            return None
        zone = pin_zone(self.pins[source], self.targets)
        centers, _ = self.layout_centers()
        choices = [(centers[i], item['pin_index']) for i, item in enumerate(self.items)
                   if 'pin_index' in item and pin_zone(self.pins[item['pin_index']], self.targets) == zone]
        if not choices:
            return None
        coordinate = position.x() if self.edge == 'bottom' else position.y()
        if not choices[0][0]-self.step/2 <= coordinate <= choices[-1][0]+self.step/2:
            return None
        return min(choices, key=lambda pair: abs(pair[0]-coordinate))[1]

    def pin_removal_zone(self, position):
        shelf = self.shelf_rect()
        return not shelf.adjusted(-64, -64, 64, 64).contains(position)

    def capture_x11_window(self, window, max_size=(520, 340)):
        if os.name == 'nt' or not self.watcher.backend or not hasattr(self.watcher.backend, 'display'):
            return None
        try:
            from x11_previews import capture
            with self.watcher.backend.lock:
                encoded = capture(self.watcher.backend.display, int(window['id']), int(window['pid']), max_size=max_size)
            if not encoded:
                return None
            image = QImage()
            if image.loadFromData(base64.b64decode(encoded)) and not image.isNull():
                return image
        except Exception:
            pass
        return None

    def window_action(self, action, window, skip_tile_capture=False):
        if self.watcher.backend:
            try:
                if action == 'activate':
                    self.show_application(dict(windows=[entry for entry in self.windows if entry['key'] == window['key']]))
                if action in ('activate', 'close_window'):
                    for token, request in list(self.sheet_pending.items()):
                        if request[0]['id'] == window['id']:
                            self.sheet_pending.pop(token, None)
                active = next((effect for effect in self.effects if tile_identity(effect.window) == tile_identity(window)), None)
                if active:
                    if action in ('minimize', 'activate') and hasattr(active, 'redirect') and active.redirect(action == 'activate'):
                        return
                    active.suppress_restore = action == 'close_window'
                    active.close()
                minimized = (bool(self.watcher.backend.u.IsIconic(window['id']))
                             if hasattr(self.watcher.backend, 'u')
                             else bool(window.get('minimized')))
                identity = (window['pid'], window['id'])
                if action == 'minimize' and not minimized and os.name != 'nt':
                    captured = self.capture_x11_window(window, max_size=(640, 420))
                    if captured is not None:
                        self.minimized_tiles.remember(window, captured, detailed=self.minimize_into_app)
                        self.sheet_frames.pop(identity, None)
                        self.sheet_frames[identity] = captured
                        while sum(frame.sizeInBytes() for frame in self.sheet_frames.values()) > 32*1024*1024:
                            self.sheet_frames.popitem(last=False)
                    if not self.minimize_into_app:
                        self.minimized_tiles.reserve(window)
                        self.refresh_items()
                if self.animate_minimize:
                    if self.animation_style == 'sheet':
                        if action == 'minimize' and not minimized:
                            if os.name != 'nt':
                                image = self.sheet_frames.get(identity)
                                geometry = window.get('geometry')
                                if image is not None and geometry and len(geometry) == 4:
                                    origin = QRect(*[int(v) for v in geometry])
                                    if self.start_sheet_effect(window, image, origin, False):
                                        return
                            elif self.request_sheet_capture(window):
                                return
                        if action == 'activate' and minimized and identity in self.sheet_frames and identity in self.minimized_bounds:
                            if self.start_sheet_effect(window, self.sheet_frames[identity], self.minimized_bounds[identity], True):
                                return
                    if action == 'minimize' and not minimized and self.start_minimize_effect(window):
                        return
                    if action == 'activate' and minimized and identity in self.minimized_bounds and self.start_minimize_effect(window, True):
                        return
                success = getattr(self.watcher.backend, action)(window)
                if action in ('activate', 'close_window'):
                    self.minimized_tiles.forget(window)
                    self.minimized_bounds.pop(identity, None)
                    self.sheet_frames.pop(identity, None)
                    self.refresh_items()
                if action == 'activate' and not success:
                    self.integration_status = 'El sistema limitó la activación de esta ventana.'
            except Exception as error:
                self.integration_status = f'No se pudo completar la acción: {type(error).__name__}'

    def transition_target(self, window):
        matching = [(index, item) for index, item in enumerate(self.items)
                    if any(tile_identity(candidate) == tile_identity(window) for candidate in item.get('windows', []))]
        if not matching:
            return None
        preferred = next(((index, item) for index, item in matching
                          if bool(item.get('minimized_window')) == (not self.minimize_into_app)), matching[0])
        index, _ = preferred
        centers, _ = self.layout_centers()
        rect = self.item_rect(centers[index], self.base_size*self.zoom[index])
        return QRect(self.mapToGlobal(rect.topLeft().toPoint()), rect.size().toSize())

    def start_minimize_effect(self, window, reverse=False):
        if any(effect.window['id'] == window['id'] for effect in self.effects):
            return True
        bounds = self.transition_target(window)
        if bounds is None or len(self.effects) >= 3:
            return False
        from minimize_effect import MinimizeEffect
        identity = (window['pid'], window['id'])
        image = self.sheet_frames.get(identity)
        effect = MinimizeEffect(self.watcher.backend, window, bounds, self.dock_screen, int(self.winId()),
                                reverse=reverse, origin=self.minimized_bounds.get(identity), image=image)
        effect.target_provider = lambda: self.transition_target(window)
        return self.track_effect(effect, identity)

    def track_effect(self, effect, identity):
        self.effects.append(effect)
        def finished():
            if effect.started and not effect.reverse and not getattr(self, 'closing', False):
                if not self.minimize_into_app:
                    self.minimized_tiles.reserve(effect.window)
                self.minimized_bounds[identity] = effect.origin
                image = getattr(effect, 'image', None)
                if image is not None:
                    self.minimized_tiles.remember(effect.window, image, detailed=self.minimize_into_app)
                    self.sheet_frames.pop(identity, None)
                    self.sheet_frames[identity] = image
                    while sum(frame.sizeInBytes() for frame in self.sheet_frames.values()) > 32*1024*1024:
                        self.sheet_frames.popitem(last=False)
            elif effect.reverse:
                self.minimized_bounds.pop(identity, None)
                self.sheet_frames.pop(identity, None)
                self.minimized_tiles.forget(effect.window)
            if effect in self.effects:
                self.effects.remove(effect)
            effect.deleteLater()
            if not getattr(self, 'closing', False):
                self.refresh_items()
                self.update()
        effect.finished.connect(finished)
        if effect.begin():
            return True
        if effect in self.effects:
            effect.close()
        return False

    def request_sheet_capture(self, window):
        if any(request[0]['id'] == window['id'] for request in self.sheet_pending.values()):
            return True
        if any(effect.window['id'] == window['id'] for effect in self.effects):
            return True
        if len(self.effects)+len(self.sheet_pending) >= 3:
            return False
        from window_capture import CaptureBroker, logical_bounds
        origin = logical_bounds(self.watcher.backend, window, self.dock_screen, int(self.winId()))
        if origin is None:
            return False
        if self.capture_broker is None:
            self.capture_broker = CaptureBroker(self)
            self.capture_broker.ready.connect(self.sheet_capture_ready)
        token = self.capture_broker.request(window)
        if token is None:
            return False
        self.sheet_pending[token] = (dict(window), origin)
        def expire():
            pending = self.sheet_pending.pop(token, None)
            if pending and not getattr(self, 'closing', False):
                self.sheet_fallback(pending[0])
        QTimer.singleShot(350, expire)
        return True

    def sheet_capture_ready(self, token, image):
        pending = self.sheet_pending.pop(token, None)
        if pending is None or getattr(self, 'closing', False):
            return
        window, origin = pending
        from window_capture import logical_bounds
        current = logical_bounds(self.watcher.backend, window, self.dock_screen, int(self.winId()))
        valid_image = image is not None and not image.isNull()
        if valid_image:
            ratio = self.dock_screen.devicePixelRatio()
            valid_image = abs(image.width()-origin.width()*ratio) <= 3 and abs(image.height()-origin.height()*ratio) <= 3
            if valid_image:
                sample = image.scaled(12, 12)
                valid_image = any(sample.pixelColor(x, y).lightness() > 2 for x in range(sample.width()) for y in range(sample.height()))
        if current != origin or not valid_image or not self.start_sheet_effect(window, image, origin):
            self.sheet_fallback(window)

    def start_sheet_effect(self, window, image, origin, reverse=False):
        if len(self.effects) >= 3 or any(effect.window['id'] == window['id'] for effect in self.effects):
            return False
        bounds = self.transition_target(window)
        if bounds is None:
            return False
        from sheet_effect import SheetEffect
        effect = SheetEffect(self.watcher.backend, window, bounds, self.dock_screen, origin, image,
                             edge=self.edge, reverse=reverse)
        effect.target_provider = lambda: self.transition_target(window)
        return self.track_effect(effect, (window['pid'], window['id']))

    def sheet_fallback(self, window):
        if self.watcher.backend and self.watcher.backend.valid(window):
            if not self.start_minimize_effect(window):
                self.watcher.backend.minimize(window)

    def folder_stack(self, item):
        from panels import FolderPanel
        resolved = ''
        if item.get('path'):
            try:
                resolved = str(Path(item['path']).resolve())
            except OSError:
                resolved = item['path']
        self.menu_open = True
        panel = FolderPanel(self, item)
        try:
            panel.exec()
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()
            self.last_folder_close_path = resolved
            self.last_folder_close_time = time.monotonic()
            panel.deleteLater()

    def window_overview(self, item):
        from panels import WindowPanel
        self.menu_open = True
        panel = WindowPanel(self, item)
        try:
            panel.exec()
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()
            panel.deleteLater()

    def add_path(self, path):
        if self.is_file_manager_launcher(path):
            return
        if len(self.pins) >= 18:
            QMessageBox.information(self, APP, 'Este prototipo admite hasta 18 accesos personalizados.')
            return
        if Path(path).exists() and not any(p['path'] == path for p in self.pins):
            pin = dict(name=Path(path).stem, path=path)
            if Path(path).is_dir():
                pin['kind'] = 'folder'
            self.pins.append(pin)
            self.save()
            self.refresh_items()

    def add_pin(self, folder=False):
        self.menu_open = True
        try:
            path = QFileDialog.getExistingDirectory(self, 'Añadir carpeta') if folder else QFileDialog.getOpenFileName(self, 'Selecciona aplicación, acceso directo o archivo')[0]
            if path:
                self.add_path(path)
        finally:
            self.menu_open = False

    def accepts_documents(self, item):
        if not item or item.get('minimized_window') or item.get('minimized_tile'):
            return False
        symbol = item.get('symbol')
        if symbol in ('apps', 'download', 'trash', 'folder'):
            return False
        if symbol == 'web':
            return True
        path = item.get('path', '')
        if not path:
            return False
        if path.endswith('.desktop') or is_program(path):
            return True
        if os.name == 'nt' and Path(path).suffix.lower() in ('.exe', '.lnk'):
            return True
        return pin_zone(item, self.targets) == 'apps'

    def classify_drop_target(self, position, paths, modifiers=Qt.NoModifier):
        index = next((i for i, rect in enumerate(self.rects) if rect.contains(position)), -1)
        if 0 <= index < len(self.items):
            item = self.items[index]
            if item.get('symbol') == 'trash':
                return index, 'trash', 'Mover a la Papelera'
            if (item.get('symbol') != 'folder' and item.get('path')
                    and not item['path'].startswith(('https://', 'http://', 'shell:', 'trash:'))
                    and Path(item['path']).is_dir()):
                folder_resolved = Path(item['path']).resolve()
                if not any(Path(p).resolve() == folder_resolved for p in paths):
                    verb = 'Copiar a' if modifiers & Qt.ControlModifier else 'Mover a'
                    return index, 'folder', f"{verb} {item['name']}"
            ordinary_files = [p for p in paths if Path(p).is_file() and not p.endswith('.desktop')
                              and Path(p).suffix.lower() not in ('.exe', '.lnk', '.appimage')]
            if ordinary_files and len(ordinary_files) == len(paths) and self.accepts_documents(item):
                return index, 'app', f"Abrir con {item['name']}"
        return -1, 'pin', 'Anclar en el dock'

    def trigger_spring_folder(self):
        if not self.external_drag or not 0 <= self.spring_index < len(self.items):
            return
        item = self.items[self.spring_index]
        if item.get('path') and Path(item['path']).is_dir() and item.get('symbol') != 'folder':
            self.reset_document_drag()
            QTimer.singleShot(0, lambda target=dict(item): self.folder_stack(target))

    def reset_document_drag(self):
        self.external_drag = False
        self.drop_index = -1
        self.drop_label = ''
        self.drop_kind = ''
        self.spring_index = -1
        self.spring_timer.stop()
        self.last_inside = time.monotonic()
        QToolTip.hideText()
        self.update()

    def dragEnterEvent(self, event):
        paths = local_drop_paths(event.mimeData().urls(), self.catalog) if event.mimeData().hasUrls() else []
        if paths:
            self.external_drag = True
            self.dragMoveEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        paths = local_drop_paths(event.mimeData().urls(), self.catalog) if event.mimeData().hasUrls() else []
        if not paths:
            event.ignore()
            return
        self.drop_index, self.drop_kind, self.drop_label = self.classify_drop_target(
            event.position(), paths, event.modifiers()
        )
        if self.drop_kind == 'folder' and self.drop_index >= 0:
            if self.spring_index != self.drop_index:
                self.spring_index = self.drop_index
                self.spring_timer.start()
        else:
            self.spring_index = -1
            self.spring_timer.stop()
        self.last_inside = time.monotonic()
        event.setDropAction(Qt.LinkAction if event.possibleActions() & Qt.LinkAction else Qt.CopyAction)
        event.accept()
        self.update()

    def dragLeaveEvent(self, event):
        self.reset_document_drag()
        event.accept()

    def dropEvent(self, event):
        paths = local_drop_paths(event.mimeData().urls(), self.catalog) if event.mimeData().hasUrls() else []
        index, kind, _ = self.classify_drop_target(event.position(), paths, event.modifiers())
        target = self.items[index] if 0 <= index < len(self.items) else None
        self.reset_document_drag()
        if not paths:
            event.ignore()
            return
        if kind == 'trash':
            from trash_linux import move_to_trash, item_count
            if move_to_trash(paths):
                self.trash_count = item_count()
                self.refresh_items()
                self.update()
        elif kind == 'folder' and target is not None:
            self.drop_into_folder(target['path'], paths, copy=bool(event.modifiers() & Qt.ControlModifier))
        elif kind == 'app' and target is not None:
            files = [str(Path(path).resolve()) for path in paths if Path(path).is_file()]
            if files:
                self.open_documents_with(target, files)
        else:
            for path in paths:
                self.add_path(path)
        event.setDropAction(Qt.LinkAction if event.possibleActions() & Qt.LinkAction else Qt.CopyAction)
        event.accept()

    def drop_into_folder(self, folder_path, paths, copy=False):
        dest_dir = Path(folder_path).resolve()
        if not dest_dir.is_dir():
            return False
        changed = False
        for raw in paths:
            src = Path(raw).resolve()
            if not src.exists() or src == dest_dir or src.parent == dest_dir:
                continue
            candidate = dest_dir / src.name
            counter = 2
            while candidate.exists():
                candidate = dest_dir / f'{src.stem} ({counter}){src.suffix}'
                counter += 1
            try:
                if copy:
                    if src.is_dir():
                        shutil.copytree(src, candidate)
                    else:
                        shutil.copy2(src, candidate)
                else:
                    shutil.move(str(src), str(candidate))
                changed = True
            except OSError as error:
                self.integration_status = f'No se pudo trasladar {src.name}: {error}'
        if changed:
            self.folder_stacks.request(str(dest_dir))
            self.update()
        return changed

    def open_documents_with(self, item, paths):
        files = [str(Path(p).resolve()) for p in paths if Path(p).is_file()][:64]
        if not files:
            return False
        target = item.get('path', '')
        if item.get('symbol') == 'web' and target.startswith(('https://', 'http://')):
            target = self.targets.get(target, target)
        try:
            if target.endswith('.desktop'):
                subprocess.Popen(['gio', 'launch', str(Path(target).resolve()), *files])
                return True
            if is_program(target) or Path(target).is_file():
                subprocess.Popen([str(Path(target).resolve()), *files])
                return True
            for f in files:
                QDesktopServices.openUrl(QUrl.fromLocalFile(f))
            return True
        except OSError as error:
            self.integration_status = f'No se pudo entregar el documento: {error}'
            return False

    def choose_documents(self, item):
        previous = self.menu_open
        self.menu_open = True
        try:
            files = QFileDialog.getOpenFileNames(self, f"Abrir archivos con {item['name']}")[0]
            if files:
                self.open_documents_with(item, files)
        finally:
            self.menu_open = previous
            self.last_inside = time.monotonic()

    def launch_documents(self, desktop, paths):
        return self.open_documents_with({'path': desktop, 'name': Path(desktop).stem}, paths)

    def folder_preferences(self, path):
        preferences = {key: self.config.get(key, default) for key, default in
                       (('folder_mode', 'auto'), ('folder_order', 'date'), ('folder_display', 'folder'))}
        stored = self.config.get('folder_preferences', {})
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            resolved = canonical(path)
        for candidate in (resolved, canonical(path)):
            if isinstance(stored, dict) and isinstance(stored.get(candidate), dict):
                entry = stored[candidate]
                preferences.update(entry)
                if 'mode' in entry and 'folder_mode' not in entry:
                    preferences['folder_mode'] = entry['mode']
                if 'order' in entry and 'folder_order' not in entry:
                    preferences['folder_order'] = entry['order']
                if 'display' in entry and 'folder_display' not in entry:
                    preferences['folder_display'] = entry['display']
        return preferences

    def set_folder_option(self, key, value, path=None):
        if path:
            try:
                resolved = str(Path(path).resolve())
            except OSError:
                resolved = canonical(path)
            if not isinstance(self.config.get('folder_preferences'), dict):
                self.config['folder_preferences'] = {}
            entry = self.config['folder_preferences'].setdefault(resolved, {})
            entry[key] = value
            short = key.replace('folder_', '')
            entry[short] = value
        else:
            self.config[key] = value
        self.save()
        self.refresh_items()
        if path:
            self.folder_stacks.request(str(Path(path).resolve()))
        self.update()

    def contextMenuEvent(self, event):
        self.last_context_action = None
        if self.press_pos is not None:
            self.drag_cancelled = True
            event.accept()
            return
        self.menu_open = True
        menu = QMenu(self)
        menu.addAction('Brisa Dock '+VERSION).setEnabled(False)
        menu.addSeparator()
        selected = next((item for item, rect in zip(self.items, self.rects) if rect.contains(event.pos())), {})
        if selected.get('symbol') == 'trash':
            menu.addAction('Abrir Papelera', lambda: self.open_path(selected['path']))
            empty_action = menu.addAction('Vaciar Papelera…', self.empty_trash_prompt)
            empty_action.setEnabled(bool(self.trash_count))
            menu.addSeparator()
        if selected.get('path') and selected.get('symbol') != 'folder' and not selected['path'].startswith(('https://', 'http://', 'shell:', 'trash:')) and Path(selected['path']).is_dir():
            views = menu.addMenu('Ver contenido como')
            for key, label in (('fan', 'Abanico'), ('grid', 'Rejilla'), ('list', 'Lista'), ('auto', 'Automático')):
                action = views.addAction(label, lambda checked=False, value=key: self.set_folder_option('folder_mode', value, selected['path']))
                action.setCheckable(True)
                action.setChecked(self.folder_preferences(selected['path']).get('folder_mode', 'auto') == key)
            order = menu.addMenu('Ordenar por')
            for key, label in ORDERS:
                action = order.addAction(label, lambda checked=False, value=key: self.set_folder_option('folder_order', value, selected['path']))
                action.setCheckable(True)
                action.setChecked(self.folder_preferences(selected['path']).get('folder_order') == key)
            representation = menu.addMenu('Mostrar como')
            for key, label in (('folder', 'Carpeta'), ('stack', 'Pila')):
                action = representation.addAction(label, lambda checked=False, value=key: self.set_folder_option('folder_display', value, selected['path']))
                action.setCheckable(True)
                action.setChecked(self.folder_preferences(selected['path']).get('folder_display') == key)
            menu.addSeparator()
        if self.accepts_documents(selected):
            menu.addAction('Abrir archivos con esta aplicación…', lambda: self.choose_documents(selected))
            menu.addSeparator()
        if (selected.get('path') and not selected['path'].startswith(('https://', 'http://', 'shell:', 'trash:'))
                and selected.get('symbol') not in ('apps', 'trash')):
            menu.addAction('Mostrar en Archivos', lambda: self.reveal_in_file_manager(selected['path']))
            menu.addSeparator()
        windows = selected.get('windows', [])
        if windows:
            menu.addAction('Mostrar todas las ventanas', lambda: self.window_overview(selected))
            if not selected.get('minimized_window') and hasattr(self.watcher.backend, 'hidden'):
                if any(window.get('hidden') for window in windows):
                    menu.addAction('Mostrar aplicación', lambda: self.launch(self.items.index(selected)))
                else:
                    menu.addAction('Ocultar aplicación', lambda: self.hide_application(selected))
                menu.addAction('Ocultar otras aplicaciones', lambda: self.hide_application(selected, True))
            menu.addSeparator()
            for window in windows:
                label = ('✓ ' if window['active'] else '') + window['title'][:75]
                menu.addAction(label, lambda checked=False, w=window: self.window_action('activate', w))
            menu.addSeparator()
            if not selected.get('minimized_window'):
                menu.addAction('Abrir de nuevo', lambda: self.launch(self.items.index(selected), True))
                menu.addAction('Minimizar ventanas', lambda: [self.window_action('minimize', w) for w in windows])
            menu.addAction('Cerrar ventanas…', lambda: [self.window_action('close_window', w) for w in windows])
            if not selected.get('minimized_window'):
                menu.addAction('Forzar salida…', lambda: self.force_quit_application(selected))
            if selected.get('temporary'):
                menu.addAction('Mantener en el dock', lambda: self.pin_application(selected))
            menu.addSeparator()
        if selected.get('recent'):
            menu.addAction('Mantener en el dock', lambda: self.pin_application(selected))
            menu.addAction('Quitar de recientes', lambda: self.remove_recent(selected['key']))
            menu.addSeparator()
        menu.addAction('Añadir app abierta…', self.running_applications_panel)
        menu.addAction('Añadir aplicación o archivo…', lambda: self.add_pin())
        menu.addAction('Añadir carpeta…', lambda: self.add_pin(True))
        if self.removed_pin is not None:
            menu.addAction('Deshacer quitar acceso', self.undo_remove_pin).setEnabled(len(self.pins) < 18)
        index = selected.get('pin_index', -1)
        if 0 <= index < len(self.pins):
            menu.addSeparator()
            menu.addAction('Quitar acceso', lambda: self.change_pin(index, 0))
            if neighbor(self.pins, index, -1, self.targets) is not None:
                menu.addAction('Mover antes', lambda: self.change_pin(index, -1))
            if neighbor(self.pins, index, 1, self.targets) is not None:
                menu.addAction('Mover después', lambda: self.change_pin(index, 1))
            placement = menu.addMenu('Zona del acceso')
            for key, label in (('auto', 'Automática'), ('apps', 'Aplicaciones'), ('files', 'Carpetas y documentos')):
                action = placement.addAction(label, lambda checked=False, value=key: self.set_pin_zone(index, value))
                action.setCheckable(True)
                action.setChecked(self.pins[index].get('zone', 'auto') == key)
        menu.addSeparator()
        menu.addAction('Navegar con teclado…', lambda: QTimer.singleShot(0, self.begin_keyboard_navigation))
        menu.addAction('Preferencias…', self.preferences)
        menu.addAction('Borrar aplicaciones recientes', self.clear_recent)
        if hasattr(self.watcher.backend, 'hidden'):
            menu.addAction('Mostrar aplicaciones ocultas', self.show_hidden_applications)
        hide = menu.addAction('Ocultar automáticamente')
        hide.setCheckable(True)
        hide.setChecked(self.auto_hide)
        hide.triggered.connect(self.toggle_hide)
        magnify = menu.addAction('Ampliar iconos al pasar el cursor')
        magnify.setCheckable(True)
        magnify.setChecked(self.magnify)
        magnify.triggered.connect(lambda checked: self.set_preference('magnify', checked))
        light = menu.addAction('Apariencia clara')
        light.setCheckable(True)
        light.setChecked(self.light)
        light.triggered.connect(lambda checked: self.set_preference('light', checked))
        sizes = menu.addMenu('Tamaño de iconos')
        for size in (16, 24, 32, 36, 48, 60, 72):
            sizes.addAction(f'{size} px', lambda checked=False, s=size: self.set_size(s))
        status = menu.addAction(self.integration_status)
        status.setEnabled(False)
        menu.addAction('Cerrar Brisa Dock', self.close)
        try:
            self.last_context_action = menu.exec(event.globalPos())
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()

    def change_pin(self, index, direction):
        if direction:
            other = neighbor(self.pins, index, direction, self.targets)
            if other is None:
                return
            self.pins[index], self.pins[other] = self.pins[other], self.pins[index]
        else:
            self.removed_pin = (index, dict(self.pins.pop(index)))
        self.save()
        self.refresh_items()

    def set_pin_zone(self, index, zone):
        if not 0 <= index < len(self.pins):
            return
        if zone in ('apps', 'files'):
            self.pins[index]['zone'] = zone
        else:
            self.pins[index].pop('zone', None)
        self.save()
        self.refresh_items()

    def undo_remove_pin(self):
        if self.removed_pin is None or len(self.pins) >= 18:
            return
        index, pin = self.removed_pin
        if not any(existing['path'] == pin['path'] for existing in self.pins):
            self.pins.insert(min(index, len(self.pins)), pin)
            self.save()
            self.refresh_items()
        self.removed_pin = None

    def preferences(self):
        from panels import PreferencesPanel
        self.menu_open = True
        panel = PreferencesPanel(self)
        try:
            panel.exec()
        finally:
            self.menu_open = False
            self.last_inside = time.monotonic()
            panel.deleteLater()

    def toggle_hide(self, checked):
        self.auto_hide = checked
        self.sync_reservation()
        self.resize_to_fit()
        self.save()

    def set_preference(self, name, value):
        if name == 'screen_mode' and value not in MODES:
            return
        if name == 'screen_id' and not isinstance(value, str):
            return
        setattr(self, name, value)
        if name == 'minimize_into_app':
            if value:
                self.minimized_tiles.reserved.clear()
            self.refresh_items()
        if name == 'show_recent':
            if not value:
                self.recent.clear()
            self.refresh_items()
        if name == 'show_attention' and not value:
            self.attention_requests.clear()
        if name == 'animate_minimize' and not value:
            for effect in self.effects[:]:
                effect.close()
            self.sheet_frames.clear()
        if name in ('edge', 'gap', 'reserve_space', 'auto_hide', 'hide_fullscreen', 'screen_mode', 'screen_id'):
            self.hidden_amount = 0
            self.last_inside = time.monotonic()
            self.sync_reservation()
            self.resize_to_fit()
            self.display_changed.emit()
        self.save()
        if name == 'light':
            self.appearance_changed.emit()
        self.update()

    def set_appearance(self, name=None, value=None):
        self.appearance = normalize_appearance(dict(self.appearance, **{name: value}) if name else {})
        self.save()
        self.appearance_changed.emit()
        self.update()

    def set_size(self, size):
        self.size = size
        self.save()
        self.refresh_items()
        self.sync_reservation()

    def closeEvent(self, event):
        self.clear_drag_ghost()
        self.spring_timer.stop()
        self.reorder_timer.stop()
        self.restore_drag_order()
        if self.keyboard_controller:
            self.keyboard_controller.reject()
        if self.fullscreen_shelf:
            self.fullscreen_shelf.close()
            self.fullscreen_shelf.deleteLater()
            self.fullscreen_shelf = None
        self.closing = True
        for window, _ in list(self.sheet_pending.values()):
            if self.watcher.backend and self.watcher.backend.valid(window):
                self.watcher.backend.minimize(window)
        self.sheet_pending.clear()
        self.minimized_tiles.frames.clear()
        if self.shell_attention:
            self.shell_attention.close()
        if self.catalog_worker:
            self.catalog_worker.stop.set()
            self.catalog_worker.wait(2500)
        for effect in self.effects[:]:
            effect.close()
        self.sheet_frames.clear()
        self.show_hidden_applications()
        if self.appbar:
            self.appbar.release()
            self.appbar.close()
        if self.surface:
            self.surface.close()
            self.surface = None
        self.timer.stop()
        self.folder_stacks.close()
        self.watcher.stop_event.set()
        self.watcher.wait(6000)
        super().closeEvent(event)
        self.closed.emit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName('Brisa')
    profile = Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation))
    diagnostic = '--smoke-test' in sys.argv or '--render' in sys.argv
    def startup_error(message):
        if diagnostic:
            if sys.stderr:
                print(message, file=sys.stderr)
        else:
            QMessageBox.critical(None, APP, 'No se pudo iniciar Brisa Dock.\n'+str(message))
    if '--profile-dir' in sys.argv:
        if sys.argv.index('--profile-dir')+1 >= len(sys.argv):
            startup_error('Falta la carpeta de perfil.')
            return 2
        profile = Path(sys.argv[sys.argv.index('--profile-dir')+1]).resolve()
    app.setProperty('brisaProfileDir', str(profile))
    from instance import InstanceGuard
    try:
        guard = InstanceGuard(profile, app)
    except OSError as error:
        startup_error(f'No se puede abrir el perfil: {error}')
        return 2
    if guard.error:
        startup_error(guard.error)
        return 2
    if not guard.owner:
        guard.notify('keyboard' if '--keyboard' in sys.argv else 'show')
        return 0
    try:
        dock = Dock()
    except ValueError as error:
        guard.close()
        startup_error(str(error))
        return 2
    dock.closed.connect(app.quit)
    guard.reveal.connect(dock.reveal_instance)
    guard.keyboard.connect(dock.keyboard_focus)
    if '--keyboard' in sys.argv:
        QTimer.singleShot(150, dock.keyboard_focus)
    app.aboutToQuit.connect(guard.close)
    app.aboutToQuit.connect(lambda: dock.shell_attention.close() if dock.shell_attention else None)
    app.aboutToQuit.connect(lambda: dock.appbar.release() if dock.appbar else None)
    app.aboutToQuit.connect(lambda: [effect.close() for effect in dock.effects[:]])
    app.aboutToQuit.connect(lambda: (dock.catalog_worker.stop.set(), dock.catalog_worker.wait(2500)) if dock.catalog_worker else None)
    app.aboutToQuit.connect(lambda: (dock.watcher.stop_event.set(), dock.watcher.wait(6000)))
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(800, app.quit)
    if '--render' in sys.argv:
        def render():
            dock.grab().save(sys.argv[sys.argv.index('--render') + 1])
            app.quit()
        QTimer.singleShot(500, render)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
