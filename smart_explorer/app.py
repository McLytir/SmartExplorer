import os
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main():
    # Enable high DPI scaling on Windows
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

