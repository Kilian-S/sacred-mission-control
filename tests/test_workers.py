"""The worker registry must guarantee delivery: a queued finished/failed
signal is never dropped because the pool deleted the sender first, even when
the caller discards the returned worker (which every call site does)."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _drain(app, cond, timeout=6.0):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.01)
    return cond()


def test_discarded_workers_still_deliver_results():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from smc.workers import run_in_background

    res = {}
    for key, delay in (("a", 0.25), ("b", 0.02), ("c", 0.4)):
        run_in_background(lambda d=delay: (time.sleep(d), d)[1],
                          on_done=lambda v, k=key: res.setdefault(k, v))
    assert _drain(app, lambda: len(res) == 3), f"lost results: got {res}"


def test_discarded_workers_still_deliver_failures():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from smc.workers import run_in_background

    seen = {}

    def boom():
        time.sleep(0.15)
        raise RuntimeError("expected test failure")

    run_in_background(boom, on_fail=lambda tb: seen.setdefault("tb", tb))
    assert _drain(app, lambda: "tb" in seen), "failure signal was dropped"
    assert "expected test failure" in seen["tb"]
