"""Asynchronous folder-stack icons with directory/file watches and stale-result rejection."""
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, QFileSystemWatcher, QTimer, Qt, QRectF
from PySide6.QtGui import QIcon, QImageReader, QPixmap, QPainter, QColor, QPen
from folder_content import scan_directory
from file_icons import stack_icon


class StackSignals(QObject):
    ready = Signal(str, int, object)


class StackTask(QRunnable):
    def __init__(self, path, generation, order, signals):
        super().__init__()
        self.path = path
        self.generation = generation
        self.order = order
        self.signals = signals

    def run(self):
        entries, _, error = scan_directory(self.path, self.order, 3)
        result = []
        for _, _, value, directory in entries:
            image = None
            if not directory:
                reader = QImageReader(value)
                reader.setAutoTransform(True)
                size = reader.size()
                if size.isValid():
                    reader.setScaledSize(size.scaled(96, 96, Qt.KeepAspectRatio))
                    image = reader.read()
                    if image.isNull():
                        image = None
            result.append((value, directory, image))
        try:
            self.signals.ready.emit(self.path, self.generation, result)
        except RuntimeError:
            pass


class FolderStacks(QObject):
    changed = Signal(str)

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.icons = {}
        self.generations = {}
        self.watched = set()
        self.closed = False
        self.files_by_folder = {}
        self.signals = StackSignals(self)
        self.signals.ready.connect(self.receive)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.queue)
        self.watcher.fileChanged.connect(self.queue)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh_all)
        QImageReader.setAllocationLimit(64)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(2)

    def queue(self, *_):
        if not self.closed:
            self.timer.start()

    def sync(self, paths):
        selected = {str(Path(p).resolve()) for p in paths if Path(p).is_dir()}
        added = selected-self.watched
        removed = self.watched-selected
        for path in removed:
            self.generations[path] = self.generations.get(path, 0)+1
            self.icons.pop(path, None)
            self.files_by_folder.pop(path, None)
        self.watched = selected
        required = set().union(*self.files_by_folder.values()) if self.files_by_folder else set()
        obsolete = set(self.watcher.files())-required
        if obsolete:
            self.watcher.removePaths(list(obsolete))
        current = set(self.watcher.directories())
        if current-selected:
            self.watcher.removePaths(list(current-selected))
        if selected-current:
            self.watcher.addPaths(list(selected-current))
        for path in selected:
            if path in added or path not in self.generations:
                self.request(path)

    def refresh_all(self):
        for path in self.watched:
            self.request(path)

    def request(self, path):
        if self.closed:
            return
        self.generations[path] = self.generations.get(path, 0)+1
        preferences = self.dock.config.get('folder_preferences', {}).get(path, {})
        order = preferences.get('order') or preferences.get('folder_order') or self.dock.config.get('folder_order', 'date')
        self.pool.start(StackTask(path, self.generations[path], order, self.signals))

    def receive(self, path, generation, entries):
        if self.closed or path not in self.watched or generation != self.generations.get(path):
            return
        if not entries:
            self.files_by_folder[path] = set()
            self.icons.pop(path, None)
            self.changed.emit(path)
            return
        image = QPixmap(128, 128)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # Draw back-to-front like a real macOS Dock stack of tilted cards.
        for index, (value, directory, thumbnail) in reversed(list(enumerate(entries[:3]))):
            painter.save()
            painter.translate(64 + index*3, 64 - index*5)
            painter.rotate(-index * 6)
            target = QRectF(-44, -44, 88, 88)
            is_desktop = not directory and str(value).endswith('.desktop')
            if index > 0 and not is_desktop:
                painter.setPen(QPen(QColor(0, 0, 0, 45), 1))
                painter.setBrush(QColor(250, 252, 255, 225))
                painter.drawRoundedRect(target.adjusted(4, 4, -4, -4), 10, 10)
            if thumbnail is not None:
                icon = QIcon(QPixmap.fromImage(thumbnail))
            elif is_desktop:
                icon = self.dock.icon_for(dict(path=value))
            else:
                icon = stack_icon(value, directory=directory)
            icon.paint(painter, target.toRect())
            painter.restore()
        painter.end()
        self.icons[path] = QIcon(image)
        files = [value for value, directory, _ in entries if not directory and Path(value).is_file()]
        self.files_by_folder[path] = set(files)
        current = set(self.watcher.files())
        required = set().union(*self.files_by_folder.values())
        # Directory watches cover membership; the few visible files cover edits.
        if current-required:
            self.watcher.removePaths(list(current-required))
        if required-current:
            self.watcher.addPaths(list(required-current))
        self.changed.emit(path)

    def close(self):
        self.closed = True
        self.timer.stop()
        paths = self.watcher.files()+self.watcher.directories()
        if paths:
            self.watcher.removePaths(paths)
        self.icons.clear()
        self.watched.clear()
