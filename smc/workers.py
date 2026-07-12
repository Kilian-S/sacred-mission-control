"""Background execution: every read of a heavy artefact (torch, tfevents, LP
solves, ALNS) runs here, never on the UI thread (brief §2)."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class WorkerSignals(QObject):
    finished = Signal(object)   # result
    failed = Signal(str)        # traceback text
    progress = Signal(str)      # status line


class Worker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        # Lifetime is managed by run_in_background's registry, NOT the pool:
        # with autoDelete the pool destroys the runnable (and its signals
        # QObject) the moment run() returns, so a QUEUED finished/failed
        # emission is dropped whenever the UI thread has not yet processed it.
        # That was a real, intermittent lost-result race (stuck "loading…"
        # states, the flaky smoke).
        self.setAutoDelete(False)

    def run(self) -> None:  # noqa: D102
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            try:
                self.signals.failed.emit(traceback.format_exc())
            except RuntimeError:
                pass  # app shutting down
        else:
            try:
                self.signals.finished.emit(result)
            except RuntimeError:
                pass


_ACTIVE: set[Worker] = set()


def run_in_background(
    fn: Callable[..., Any],
    *args,
    on_done: Callable[[Any], None] | None = None,
    on_fail: Callable[[str], None] | None = None,
    **kwargs,
) -> Worker:
    """Convenience: schedule fn on the global pool, wire callbacks, return the worker.

    The worker is held in a module registry until its finished/failed signal
    has actually been DELIVERED on the UI thread, so a queued emission can
    never be dropped because the pool deleted the sender first. The caller
    must keep the connection targets alive (normal Qt ownership).
    """
    w = Worker(fn, *args, **kwargs)
    _ACTIVE.add(w)

    def _done(result):
        _ACTIVE.discard(w)
        if on_done is not None:
            on_done(result)

    def _fail(tb):
        _ACTIVE.discard(w)
        if on_fail is not None:
            on_fail(tb)

    w.signals.finished.connect(_done)
    w.signals.failed.connect(_fail)
    QThreadPool.globalInstance().start(w)
    return w
