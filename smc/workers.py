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
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D102
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            self.signals.failed.emit(traceback.format_exc())
        else:
            self.signals.finished.emit(result)


def run_in_background(
    fn: Callable[..., Any],
    *args,
    on_done: Callable[[Any], None] | None = None,
    on_fail: Callable[[str], None] | None = None,
    **kwargs,
) -> Worker:
    """Convenience: schedule fn on the global pool, wire callbacks, return the worker.

    The caller must keep the connection targets alive (normal Qt ownership).
    """
    w = Worker(fn, *args, **kwargs)
    if on_done is not None:
        w.signals.finished.connect(on_done)
    if on_fail is not None:
        w.signals.failed.connect(on_fail)
    QThreadPool.globalInstance().start(w)
    return w
