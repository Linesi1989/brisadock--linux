"""Persistent, selectively invalidated Linux icon cache; no entry-count eviction."""
import configparser
import hashlib
import json
import os
from pathlib import Path
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from icon_visuals import application_fallback


def stamp(path):
    try:
        p = Path(path)
        s = p.stat()
        return [str(p.resolve()), s.st_mtime_ns, s.st_size]
    except OSError:
        return [str(path), None, None]


class PersistentIcons:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.memory = {}
        self.descriptors = {}
        self.extractions = 0
        self.disk_hits = 0
        self._desktop_index = None

    def resource(self, name):
        if not name:
            return None
        if os.path.isabs(name):
            p = Path(name)
            return p if p.is_file() else None
        themes = [QIcon.themeName(), QIcon.fallbackThemeName(), 'WhiteSur', 'breeze', 'hicolor']
        roots = [Path(p) for p in QIcon.themeSearchPaths() if not p.startswith(':')]
        for extra in (
            Path.home()/'.local/share/icons',
            Path.home()/'.icons',
            Path('/var/lib/flatpak/exports/share/icons'),
            Path.home()/'.local/share/flatpak/exports/share/icons',
            Path('/var/lib/snapd/desktop/icons'),
            Path('/usr/local/share/icons'),
            Path('/usr/share/icons'),
        ):
            if extra not in roots:
                roots.append(extra)
        fallback_subdirs = (
            'apps/scalable', 'scalable/apps', '256x256/apps', '128x128/apps',
            '64x64/apps', '48x48/apps', 'apps/128', 'apps/64', 'apps/48',
        )
        visited = set()
        while themes:
            theme = themes.pop(0)
            if not theme or theme in visited:
                continue
            visited.add(theme)
            for root in roots:
                folder = root/theme
                if not folder.is_dir():
                    continue
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                directories = []
                try:
                    if (folder/'index.theme').is_file():
                        parser.read(folder/'index.theme', encoding='utf-8')
                        directories = [d for d in parser.get('Icon Theme', 'Directories', fallback='').split(',') if d]
                        directories.sort(key=lambda v: (not ('scalable' in v or '/128' in v or '/256' in v), v))
                        themes.extend(parser.get('Icon Theme', 'Inherits', fallback='').split(','))
                except (OSError, configparser.Error):
                    pass
                for sub in fallback_subdirs:
                    if sub not in directories:
                        directories.append(sub)
                for directory in directories:
                    for suffix in ('.svg', '.png', '.xpm'):
                        p = folder/directory/(name+suffix)
                        if p.is_file():
                            return p
        for root in (
            Path('/usr/share/pixmaps'),
            Path.home()/'.local/share/icons',
            Path('/var/lib/snapd/desktop/icons'),
        ):
            for suffix in ('.svg', '.png', '.xpm'):
                p = root/(name+suffix)
                if p.is_file():
                    return p
        return None

    def describe(self, path):
        signature = stamp(path)+[QIcon.themeName(), QIcon.fallbackThemeName()]
        cached = self.descriptors.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        icon = ''
        desktop_path = path if path.endswith('.desktop') else ''
        if not desktop_path and path and not Path(path).is_dir():
            if self._desktop_index is None:
                try:
                    from linux_desktop import DesktopIndex
                    self._desktop_index = DesktopIndex()
                except Exception:
                    self._desktop_index = False
            if self._desktop_index:
                matched = self._desktop_index.resolve((Path(path).stem,), path)
                if matched:
                    desktop_path = matched['path']
        if desktop_path:
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(desktop_path, encoding='utf-8')
                icon = parser.get('Desktop Entry', 'Icon', fallback='')
            except (OSError, configparser.Error):
                pass
        if not icon and path and not path.endswith('.desktop') and not Path(path).is_dir():
            stem = Path(path).stem.lower()
            if stem and stem not in ('python', 'python3', 'bash', 'sh'):
                icon = stem
        source = self.resource(icon) if icon else None
        if not source and desktop_path:
            stem = Path(desktop_path).stem
            for candidate in (stem, stem.rsplit('.', 1)[-1] if '.' in stem else ''):
                if candidate:
                    source = self.resource(candidate)
                    if source:
                        icon = candidate
                        break
        result = (source, icon)
        self.descriptors[path] = (signature, result)
        return result

    def get(self, path, provider):
        source, name = self.describe(path)
        fingerprint = [stamp(path), stamp(source) if source else None, QIcon.themeName(), QIcon.fallbackThemeName()]
        cached = self.memory.get(path)
        if cached and cached[0] == fingerprint:
            return cached[1]
        key = hashlib.sha256(path.encode()).hexdigest()
        image_path = self.directory/(key+'.png')
        meta_path = self.directory/(key+'.json')
        try:
            meta = json.loads(meta_path.read_text())
            data = image_path.read_bytes()
            if meta['fingerprint'] == fingerprint and hashlib.sha256(data).hexdigest() == meta['sha256']:
                icon = QIcon(str(image_path))
                if not icon.isNull():
                    self.disk_hits += 1
                    self.memory[path] = (fingerprint, icon)
                    return icon
        except (OSError, ValueError, KeyError):
            pass
        icon = QIcon(str(source)) if source else QIcon.fromTheme(name) if name else provider.icon(QFileInfo(path))
        if icon.isNull():
            icon = QIcon.fromTheme('application-x-executable')
        pixmap = icon.pixmap(128, 128)
        if pixmap.isNull():
            pixmap = application_fallback(Path(path).stem or '?', path).pixmap(128, 128)
        icon = QIcon(pixmap)
        self.extractions += 1
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = image_path.with_suffix('.png.tmp')
            if pixmap.save(str(temporary), 'PNG'):
                digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
                temporary.replace(image_path)
                temporary = meta_path.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(dict(fingerprint=fingerprint, sha256=digest)))
                temporary.replace(meta_path)
        except OSError:
            pass
        self.memory[path] = (fingerprint, icon)
        return icon
