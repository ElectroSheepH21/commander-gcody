from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPlainTextEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel
)

from board_preview import BoardPreview


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Commander GCody")
        icon = Path(__file__).resolve().parents[1] / "res" / "app.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
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
        self.text_edit = QPlainTextEdit("Hello")
        self.text_edit.setFixedHeight(90)
        self.text_edit.setTabChangesFocus(True)
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase.families())
        index = self.font_combo.findText(QFont().family())
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        self.font_size_spin = self._spin(1.0, 500.0, 20.0)
        text_form.addRow("Text:", self.text_edit)
        text_form.addRow("Font:", self.font_combo)
        text_form.addRow("Font size:", self.font_size_spin)

        machine = QGroupBox("Machine / Z axis")
        machine_form = QFormLayout(machine)
        self.plunge_spin = self._spin(0.0, 100.0, 0.5)
        self.lift_spin = self._spin(0.1, 100.0, 5.0)
        self.xy_feed_spin = QSpinBox()
        self.xy_feed_spin.setRange(1, 50000)
        self.xy_feed_spin.setValue(1200)
        self.xy_feed_spin.setSuffix(" mm/min")
        self.z_feed_spin = QSpinBox()
        self.z_feed_spin.setRange(1, 50000)
        self.z_feed_spin.setValue(300)
        self.z_feed_spin.setSuffix(" mm/min")
        machine_form.addRow("Plunge depth:", self.plunge_spin)
        machine_form.addRow("Lift above surface:", self.lift_spin)
        machine_form.addRow("XY feed rate:", self.xy_feed_spin)
        machine_form.addRow("Z feed rate:", self.z_feed_spin)

        info = QGroupBox("Calculated values")
        info_form = QFormLayout(info)
        self.text_width_label = QLabel("-")
        self.text_height_label = QLabel("-")
        self.range_label = QLabel("-")
        self.z_label = QLabel("-")
        self.fit_label = QLabel("-")
        info_form.addRow("Text width:", self.text_width_label)
        info_form.addRow("Text height:", self.text_height_label)
        info_form.addRow("G-code range:", self.range_label)
        info_form.addRow("Z down / up:", self.z_label)
        info_form.addRow("Fits on board:", self.fit_label)

        col.addWidget(board)
        col.addWidget(text)
        col.addWidget(machine)
        col.addWidget(info)
        col.addStretch()

        layout.addWidget(controls)
        self.preview = BoardPreview()
        layout.addWidget(controls)
        layout.addWidget(self.preview, 1)

        for spin in (self.width_spin, self.height_spin, self.thickness_spin):
            spin.valueChanged.connect(self.update_preview)

        self.text_edit.textChanged.connect(self.update_preview)
        self.font_combo.currentTextChanged.connect(self.update_preview)
        self.font_size_spin.valueChanged.connect(self.update_preview)

        self.plunge_spin.valueChanged.connect(self.update_preview)
        self.lift_spin.valueChanged.connect(self.update_preview)

        self.update_preview()

    def update_preview(self):
        self.preview.set_data(
            self.width_spin.value(),
            self.height_spin.value(),
            self.thickness_spin.value(),
            self.text_edit.toPlainText(),
            self.font_combo.currentText(),
            self.font_size_spin.value(),
        )
        bounds = self.preview.text_bounds
        self.text_width_label.setText(f"{bounds.width():.2f} mm")
        self.text_height_label.setText(f"{bounds.height():.2f} mm")

        half_w = bounds.width() / 2.0
        half_h = bounds.height() / 2.0
        self.range_label.setText(
            f"X={-half_w:.2f}..{half_w:.2f}, Y={-half_h:.2f}..{half_h:.2f} mm"
        )

        thickness = self.thickness_spin.value()
        plunge = self.plunge_spin.value()
        z_down = thickness - plunge
        z_up = thickness + self.lift_spin.value()
        self.z_label.setText(f"{z_down:.2f} / {z_up:.2f} mm")

        fits = (
            bounds.width() <= self.width_spin.value()
            and bounds.height() <= self.height_spin.value()
        )

        if plunge > thickness:
            self.fit_label.setText("Plunge deeper than board")
            self.fit_label.setStyleSheet("color: red; font-weight: bold;")
        elif not self.text_edit.toPlainText().strip():
            self.fit_label.setText("No text")
            self.fit_label.setStyleSheet("color: red; font-weight: bold;")
        elif fits:
            self.fit_label.setText("Yes")
            self.fit_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.fit_label.setText("No – text is too large")
            self.fit_label.setStyleSheet("color: red; font-weight: bold;")

    @staticmethod
    def _spin(minimum, maximum, value):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" mm")
        return spin
