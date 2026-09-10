from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Commander GCody")
        self.resize(1050, 650)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        controls = QWidget()
        controls.setMaximumWidth(350)
        col = QVBoxLayout(controls)

        board = QGroupBox("Board")
        board_form = QFormLayout(board)
        self.width_spin = self._spin(1.0, 5000.0, 200.0)
        self.height_spin = self._spin(1.0, 5000.0, 100.0)
        self.thickness_spin = self._spin(0.1, 500.0, 10.0)
        board_form.addRow("Width:", self.width_spin)
        board_form.addRow("Height:", self.height_spin)
        board_form.addRow("Thickness:", self.thickness_spin)

        text = QGroupBox("Text")
        text_form = QFormLayout(text)
        self.text_edit = QLineEdit("Hello")
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase.families())
        index = self.font_combo.findText(QFont().family())
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        self.font_size_spin = self._spin(1.0, 500.0, 20.0)
        text_form.addRow("Text:", self.text_edit)
        text_form.addRow("Font:", self.font_combo)
        text_form.addRow("Font size:", self.font_size_spin)

        col.addWidget(board)
        col.addWidget(text)
        col.addStretch()

        layout.addWidget(controls)
        layout.addWidget(QWidget(), 1)

    @staticmethod
    def _spin(minimum, maximum, value):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" mm")
        return spin
