"""Resolve X11 windows to desktop launchers without executing Exec strings."""
import configparser
from pathlib import Path
import shlex
import shutil

from applications import scan_desktop_entries


class DesktopIndex:
    def __init__(self, entries=None):
        self.classes = {}
        self.fallback_classes = {}
        self.executables = {}
        for item in scan_desktop_entries() if entries is None else entries:
            path = Path(item['path'])
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding='utf-8')
                entry = parser['Desktop Entry']
                for value in (
                    entry.get('StartupWMClass', ''),
                    entry.get('X-SnapInstanceName', ''),
                    entry.get('X-SnapAppName', ''),
                    path.stem,
                ):
                    if value:
                        self.classes.setdefault(value.casefold(), []).append(item)
                stem_tail = path.stem.rsplit('.', 1)[-1] if '.' in path.stem else ''
                if len(stem_tail) >= 3:
                    self.fallback_classes.setdefault(stem_tail.casefold(), []).append(item)
                tokens = shlex.split(entry.get('Exec', ''))
                while tokens and (tokens[0] == 'env' or ('=' in tokens[0] and not tokens[0].startswith('/'))):
                    tokens.pop(0)
                if tokens:
                    cmd_stem = Path(tokens[0]).stem
                    if len(cmd_stem) >= 3 and cmd_stem.casefold() not in ('python', 'python3', 'bash', 'sh', 'env', 'flatpak', 'snap'):
                        self.fallback_classes.setdefault(cmd_stem.casefold(), []).append(item)
                    executable = shutil.which(tokens[0]) or tokens[0]
                    if Path(executable).is_absolute():
                        self.executables.setdefault(str(Path(executable).resolve()), []).append(item)
            except (OSError, ValueError, KeyError, configparser.Error):
                continue

    @staticmethod
    def unique(items):
        by_path = {item['path']: item for item in items}
        return next(iter(by_path.values())) if len(by_path) == 1 else None

    def resolve(self, wm_class, executable):
        # An interpreter shared by several applications is never sufficient
        # to pick an arbitrary launcher. WM_CLASS is stronger evidence.
        for value in reversed(wm_class or ()):
            item = self.unique(self.classes.get(value.casefold(), []))
            if item:
                return item
        if executable:
            parts = Path(executable).parts
            if len(parts) >= 3 and parts[1] == 'snap':
                item = self.unique(self.classes.get(parts[2].casefold(), []))
                if item:
                    return item
            item = self.unique(self.executables.get(str(Path(executable).resolve()), []))
            if item:
                return item
        for value in reversed(wm_class or ()):
            item = self.unique(self.fallback_classes.get(value.casefold(), []))
            if item:
                return item
        return None


def is_program(path):
    """NTFS may mark every document executable; inspect a native program header."""
    import os
    try:
        source = Path(path)
        if not source.is_file() or not os.access(source, os.X_OK):
            return False
        with source.open('rb') as stream:
            header = stream.read(4)
        return header == b'\x7fELF' or header.startswith(b'#!')
    except OSError:
        return False


def local_drop_paths(urls, catalog=()):
    """Resolve local file URLs and known Plasma application IDs, without launching."""
    from applications import linux_application_dirs
    results = []
    known = {entry.get('desktop_id'): entry['path'] for entry in catalog if entry.get('desktop_id')}
    for url in urls:
        value = None
        if url.isLocalFile():
            path = Path(url.toLocalFile())
            if path.is_absolute() and path.exists():
                value = str(path)
        elif url.scheme() == 'applications':
            identifier = url.path().lstrip('/')
            if not identifier:
                identifier = url.toString().split(':', 1)[-1].lstrip('/')
            if identifier.endswith('.desktop') and '/' not in identifier and '..' not in identifier:
                value = known.get(identifier)
                if not value:
                    value = next((str(root/identifier) for root in linux_application_dirs() if (root/identifier).is_file()), None)
        if value and value not in results:
            results.append(value)
    return results
