"""Small state models independent of desktop APIs."""
import os
from pathlib import Path
from desktop_backend import canonical

IGNORED_RECENT_NAMES = {
    'python', 'python3', 'bash', 'sh', 'env', 'kwin_killer_helper',
    'xdg-desktop-portal-kde', 'xdg-desktop-portal', 'xdg-desktop-portal-gtk',
}


def normalize_recent_entry(name, path, desktop_index=None):
    if not isinstance(path, str) or not isinstance(name, str) or not path:
        return None
    if '/libexec/' in path or 'BrisaDock-Linux/.venv' in path:
        return None
    stem = Path(path).stem.lower()
    if not path.endswith('.desktop') and (stem in IGNORED_RECENT_NAMES or stem.startswith('python3.')):
        return None
    if os.name != 'nt' and not path.endswith('.desktop'):
        if desktop_index is None:
            try:
                from linux_desktop import DesktopIndex
                desktop_index = DesktopIndex()
            except Exception:
                desktop_index = None
        if desktop_index is not None:
            resolved = desktop_index.resolve((name, Path(path).stem), path)
            if resolved:
                path = resolved['path']
                name = resolved['name']
    return dict(name=name, path=path, key=canonical(path))


class RecentApplications:
    def __init__(self, entries=()):
        self.entries = []
        self._desktop_index = None
        seen = set()
        for entry in entries or ():
            if isinstance(entry, dict):
                norm = normalize_recent_entry(entry.get('name', ''), entry.get('path', ''), self._get_index())
                if norm and norm['key'] not in seen:
                    seen.add(norm['key'])
                    self.entries.append(norm)
        self.entries = self.entries[:6]

    def _get_index(self):
        if os.name == 'nt':
            return None
        if self._desktop_index is None:
            try:
                from linux_desktop import DesktopIndex
                self._desktop_index = DesktopIndex()
            except Exception:
                self._desktop_index = None
        return self._desktop_index

    def observe(self, previous, current):
        before = {window['key']: window for window in previous}
        after = {window['key'] for window in current}
        changed = False
        for key in reversed(list(before)):
            window = before[key]
            if key not in after and Path(window['path']).is_file():
                norm = normalize_recent_entry(window['name'], window['path'], self._get_index())
                if not norm:
                    continue
                self.entries = [entry for entry in self.entries if entry['key'] != norm['key']]
                self.entries.insert(0, norm)
                self.entries = self.entries[:6]
                changed = True
        return changed

    def visible(self, excluded):
        return [dict(entry, recent=True, windows=[]) for entry in self.entries
                if entry['key'] not in excluded and Path(entry['path']).is_file()][:3]

    def remove(self, key):
        self.entries = [entry for entry in self.entries if entry['key'] != key]

    def clear(self):
        self.entries.clear()

    def serialize(self):
        return [dict(name=entry['name'], path=entry['path']) for entry in self.entries]
