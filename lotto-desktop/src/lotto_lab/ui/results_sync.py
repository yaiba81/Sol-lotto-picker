"""Qt worker orchestration for non-blocking results synchronization."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from lotto_lab.draw_history.remote import ResultsSyncService, SyncResult


class ResultsSyncWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, service: ResultsSyncService, per_game: int) -> None:
        super().__init__()
        self.service = service
        self.per_game = per_game

    @Slot()
    def run(self) -> None:
        try:
            thread = QThread.currentThread()
            self.completed.emit(
                self.service.synchronize(
                    per_game=self.per_game,
                    should_cancel=thread.isInterruptionRequested,
                )
            )
        except Exception as exc:  # final worker boundary keeps the GUI alive
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ResultsSyncController(QObject):
    status_changed = Signal(str)
    synchronized = Signal(object)

    def __init__(self, service: ResultsSyncService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._thread: QThread | None = None
        self._worker: ResultsSyncWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @Slot()
    def start(self) -> None:
        if self.is_running:
            self.status_changed.emit("Results synchronization is already running.")
            return
        self.status_changed.emit("Checking recent lotto results...")
        thread = QThread(self)
        worker = ResultsSyncWorker(self.service, per_game=50)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._complete)
        worker.failed.connect(self._failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _complete(self, result: SyncResult) -> None:
        if result.errors and not result.fetched:
            message = "Could not reach results feeds. Existing local history was kept."
        else:
            message = (
                f"Results checked: {result.inserted} new, "
                f"{result.fetched - result.inserted} already stored."
            )
            if result.errors:
                message += f" {len(result.errors)} result(s) could not be used."
            if result.outdated:
                message += f" Older than expected: {', '.join(result.outdated)}."
            if result.failovers:
                message += f" Backup feed used for {len(result.failovers)} game(s)."
        self.status_changed.emit(message)
        self.synchronized.emit(result)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.status_changed.emit(
            f"Results update failed: {message}. Existing local history was kept."
        )

    @Slot()
    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None

    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(8_000)
