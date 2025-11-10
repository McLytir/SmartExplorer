import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from .logging_setup import configure_logging
from .ui.main_window import MainWindow

log = logging.getLogger(__name__)


def main():
    configure_logging()
    # Enable high DPI scaling on Windows
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    log.info("Launching SmartExplorer UI.")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
