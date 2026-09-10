import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "res" / "app.ico"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
