"""Trash state and operations via GIO and XDG directories."""
import os
from pathlib import Path
import re
import shutil
import subprocess


def read_state():
    try:
        result = subprocess.run(['gio', 'info', '-a', 'trash::item-count', 'trash:///'],
                                capture_output=True, text=True, timeout=1.0)
        match = re.search(r'trash::item-count:\s*(\d+)', result.stdout) if result.returncode == 0 else None
        if match:
            count = int(match.group(1))
            return dict(available=True, count=count, full=count > 0, source='gio')
    except (OSError, subprocess.TimeoutExpired):
        pass
    paths = [Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'Trash/files']
    try:
        local_types = {'ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'f2fs', 'ntfs3', 'fuseblk', 'vfat', 'exfat', 'fuse.exfat', 'zfs', 'ecryptfs', 'overlay'}
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            fields = line.split()
            separator = fields.index('-')
            if fields[separator+1] not in local_types:
                continue
            mount = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
            root = Path(mount)
            paths.extend([root/f'.Trash-{os.getuid()}/files', root/'.Trash'/str(os.getuid())/'files'])
    except (OSError, ValueError):
        pass
    unknown = False
    seen = set()
    for path in paths:
        try:
            if path.is_symlink():
                continue
            info = path.stat()
            identity = (info.st_dev, info.st_ino)
            if identity in seen:
                continue
            seen.add(identity)
            with os.scandir(path) as entries:
                if next(entries, None) is not None:
                    return dict(available=True, count=None, full=True, source='xdg-directories')
        except FileNotFoundError:
            continue
        except OSError:
            unknown = True
    return dict(available=not unknown, count=None, full=None if unknown else False, source='xdg-directories')


def item_count():
    """Compatibility for the shelf's empty/full indicator; fallback is zero/nonzero."""
    state = read_state()
    if not state['available']:
        return None
    return state['count'] if state['count'] is not None else int(state['full'])


def move_to_trash(paths):
    """Move local files or directories to the user's Trash via gio trash."""
    valid = [str(Path(p).resolve()) for p in paths if p and Path(p).exists()]
    if not valid:
        return False
    try:
        result = subprocess.run(['gio', 'trash', *valid], capture_output=True, text=True, timeout=6.0)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def empty_trash():
    """Empty the user's Trash via gio trash --empty with XDG fallback."""
    try:
        result = subprocess.run(['gio', 'trash', '--empty'], capture_output=True, text=True, timeout=8.0)
        if result.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    trash_root = Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'Trash'
    ok = False
    for sub in ('files', 'info'):
        folder = trash_root / sub
        if not folder.is_dir():
            continue
        try:
            for child in folder.iterdir():
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            ok = True
        except OSError:
            pass
    return ok
