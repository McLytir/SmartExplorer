import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from .logging_setup import configure_logging
from .ui.main_window import MainWindow

log = logging.getLogger(__name__)

GPU_FLAG_VALUE = "--disable-gpu --disable-software-rasterizer"


def _apply_qt_safety_defaults() -> None:
    # Avoid Qt WebEngine GPU crashes on some Linux/Mesa setups by forcing Chromium into CPU mode.
    if sys.platform.startswith("linux"):
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", GPU_FLAG_VALUE)


def main():
    configure_logging()
    _apply_qt_safety_defaults()
    # Enable high DPI scaling on Windows
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    log.info("Launching SmartExplorer UI.")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
