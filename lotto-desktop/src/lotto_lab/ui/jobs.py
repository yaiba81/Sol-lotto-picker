"""Queued worker delivery and cooperative cancellation for expensive use cases."""
from threading import Event
from PySide6.QtCore import QObject, QThread, Signal, Slot


class Worker(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, operation, cancel):
        super().__init__()
        self.operation = operation
        self.cancel = cancel

    @Slot()
    def run(self):
        try:
            self.result.emit(self.operation(self.cancel, self.progress.emit))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class JobController(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
        self.cancel_event = Event()

    @property
    def running(self):
        return self.thread is not None

    def start(self, operation):
        if self.running:
            return False
        self.cancel_event = Event()
        self.thread = QThread(self)
        self.worker = Worker(operation, self.cancel_event)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.result.connect(self.result)
        self.worker.error.connect(self.error)
        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.start()
        return True

    @Slot()
    def _finished(self):
        self.thread.wait()
        self.thread.deleteLater()
        self.thread = None
        self.worker = None
        self.finished.emit()

    def cancel(self):
        self.cancel_event.set()
