"""Run the test suite and destroy Qt while Python callbacks are still alive."""
import gc
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=1).run(suite)
success = result.wasSuccessful()
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if app is not None:
    for timer in app.findChildren(QTimer):
        timer.stop()
    app.aboutToQuit.emit()
    app.closeAllWindows()
    for window in app.topLevelWidgets():
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    del suite, result
    gc.collect()
    app.shutdown()
sys.exit(0 if success else 1)
