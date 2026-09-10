import json
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
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from board_preview import BoardPreview
from gcode import flatten_path, generate_gcode, format_duration, estimate_seconds_from_gcode


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
        self.rapid_feed_spin = QSpinBox()
        self.rapid_feed_spin.setRange(1, 50000)
        self.rapid_feed_spin.setValue(3000)
        self.rapid_feed_spin.setSuffix(" mm/min")
        self.accel_spin = QSpinBox()
        self.accel_spin.setRange(1, 20000)
        self.accel_spin.setValue(500)
        self.accel_spin.setSuffix(" mm/s²")
        machine_form.addRow("Plunge depth:", self.plunge_spin)
        machine_form.addRow("Lift above surface:", self.lift_spin)
        machine_form.addRow("XY feed rate:", self.xy_feed_spin)
        machine_form.addRow("Z feed rate:", self.z_feed_spin)
        machine_form.addRow("Rapid feed rate:", self.rapid_feed_spin)
        machine_form.addRow("Acceleration:", self.accel_spin)

        info = QGroupBox("Calculated values")
        info_form = QFormLayout(info)
        self.text_width_label = QLabel("-")
        self.text_height_label = QLabel("-")
        self.range_label = QLabel("-")
        self.z_label = QLabel("-")
        self.fit_label = QLabel("-")
        self.time_label = QLabel("-")
        info_form.addRow("Text width:", self.text_width_label)
        info_form.addRow("Text height:", self.text_height_label)
        info_form.addRow("G-code range:", self.range_label)
        info_form.addRow("Z down / up:", self.z_label)
        info_form.addRow("Fits on board:", self.fit_label)
        info_form.addRow("Est. cut time:", self.time_label)

        self.save_config_button = QPushButton("Save configuration...")
        self.save_config_button.clicked.connect(self.save_config)
        self.load_config_button = QPushButton("Load configuration...")
        self.load_config_button.clicked.connect(self.load_config)
        self.export_button = QPushButton("Save G-code...")
        self.export_button.clicked.connect(self.export_gcode)

        col.addWidget(board)
        col.addWidget(text)
        col.addWidget(machine)
        col.addWidget(info)
        col.addWidget(self.save_config_button)
        col.addWidget(self.load_config_button)
        col.addWidget(self.export_button)
        col.addStretch()

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
        self.xy_feed_spin.valueChanged.connect(self.update_preview)
        self.z_feed_spin.valueChanged.connect(self.update_preview)
        self.rapid_feed_spin.valueChanged.connect(self.update_preview)
        self.accel_spin.valueChanged.connect(self.update_preview)

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
        try:
            gcode = self.build_gcode()
            seconds = estimate_seconds_from_gcode(
                gcode, self.rapid_feed_spin.value(), self.accel_spin.value())
        except ValueError:
            seconds = 0.0
        self.time_label.setText(format_duration(seconds))

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

        can_export = (
            plunge <= thickness
            and bool(self.text_edit.toPlainText().strip())
            and fits
            and not self.preview.text_path.isEmpty()
        )
        self.export_button.setEnabled(can_export)

    def get_config(self):
        return {
            "format": "commander_gcody_config",
            "version": 1,
            "board": {
                "width_mm": self.width_spin.value(),
                "height_mm": self.height_spin.value(),
                "thickness_mm": self.thickness_spin.value(),
            },
            "text": {
                "content": self.text_edit.toPlainText(),
                "font_family": self.font_combo.currentText(),
                "font_size_mm": self.font_size_spin.value(),
            },
            "machine": {
                "plunge_depth_mm": self.plunge_spin.value(),
                "lift_above_surface_mm": self.lift_spin.value(),
                "xy_feed_mm_min": self.xy_feed_spin.value(),
                "z_feed_mm_min": self.z_feed_spin.value(),
                "rapid_feed_mm_min": self.rapid_feed_spin.value(),
                "accel_mm_s2": self.accel_spin.value(),
            },
            "window": {
                "width": self.width(),
                "height": self.height(),
            },
        }

    def apply_config(self, config):
        if config.get("format") != "commander_gcody_config":
            raise ValueError(
                "This file is not a Commander GCody configuration.")

        board = config.get("board", {})
        text = config.get("text", {})
        machine = config.get("machine", config.get("plotter", {}))
        window = config.get("window", {})

        widgets = [
            self.width_spin,
            self.height_spin,
            self.thickness_spin,
            self.text_edit,
            self.font_combo,
            self.font_size_spin,
            self.plunge_spin,
            self.lift_spin,
            self.xy_feed_spin,
            self.z_feed_spin,
            self.rapid_feed_spin,
            self.accel_spin,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        try:
            self.width_spin.setValue(
                float(board.get("width_mm", self.width_spin.value())))
            self.height_spin.setValue(
                float(board.get("height_mm", self.height_spin.value())))
            self.thickness_spin.setValue(
                float(board.get("thickness_mm", self.thickness_spin.value()))
            )

            self.text_edit.setPlainText(
                str(text.get("content", self.text_edit.toPlainText()))
            )

            saved_font = str(
                text.get("font_family", self.font_combo.currentText()))
            font_index = self.font_combo.findText(saved_font)
            if font_index >= 0:
                self.font_combo.setCurrentIndex(font_index)

            self.font_size_spin.setValue(
                float(text.get("font_size_mm", self.font_size_spin.value()))
            )
            self.plunge_spin.setValue(
                float(machine.get("plunge_depth_mm", self.plunge_spin.value()))
            )
            self.lift_spin.setValue(
                float(machine.get("lift_above_surface_mm", self.lift_spin.value()))
            )
            self.xy_feed_spin.setValue(
                int(machine.get("xy_feed_mm_min", self.xy_feed_spin.value()))
            )
            self.z_feed_spin.setValue(
                int(machine.get("z_feed_mm_min", self.z_feed_spin.value()))
            )
            self.rapid_feed_spin.setValue(
                int(machine.get("rapid_feed_mm_min", self.rapid_feed_spin.value()))
            )
            self.accel_spin.setValue(
                int(machine.get("accel_mm_s2", self.accel_spin.value()))
            )

            self.resize(
                max(500, int(window.get("width", self.width()))),
                max(400, int(window.get("height", self.height()))),
            )
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self.update_preview()

    def save_config(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save configuration",
            "commander_gcody.json",
            "JSON configuration (*.json);;All files (*.*)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"

        try:
            Path(filename).write_text(
                json.dumps(self.get_config(), indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Could not save configuration:\n{exc}")
            return

        QMessageBox.information(
            self, "Saved", f"Configuration saved:\n{filename}")

    def load_config(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load configuration",
            "",
            "JSON configuration (*.json);;All files (*.*)",
        )
        if not filename:
            return

        try:
            config = json.loads(Path(filename).read_text(encoding="utf-8"))
            self.apply_config(config)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            QMessageBox.critical(
                self, "Error", f"Could not load configuration:\n{exc}")
            return

        QMessageBox.information(
            self, "Loaded", f"Configuration loaded:\n{filename}")

    def build_gcode(self):
        if self.preview.text_path.isEmpty():
            raise ValueError("No valid text.")

        bounds = self.preview.text_bounds
        fits = (
            bounds.width() <= self.width_spin.value()
            and bounds.height() <= self.height_spin.value()
        )
        if not fits:
            raise ValueError("Text does not fit on the board.")

        thickness = self.thickness_spin.value()
        plunge = self.plunge_spin.value()
        if plunge > thickness:
            raise ValueError("Plunge depth is larger than board thickness.")

        z_down = thickness - plunge
        z_up = thickness + self.lift_spin.value()
        offset_x = -bounds.width() / 2.0
        offset_y = -bounds.height() / 2.0

        comments = [
            "; Generated by Commander GCody",
            f"; Board: {self.width_spin.value():.3f} x "
            f"{self.height_spin.value():.3f} x {thickness:.3f} mm",
            f"; Text: {self.text_edit.toPlainText().replace(chr(10), ' / ')}",
            f"; Font: {self.font_combo.currentText()}",
            f"; Text bounding box: {bounds.width():.3f} x {bounds.height():.3f} mm",
            f"; Board surface Z: {thickness:.3f} mm",
            f"; Plunge depth: {plunge:.3f} mm",
            f"; Z down: {z_down:.3f} mm",
            f"; Z up: {z_up:.3f} mm",
            "; XY origin: center of board/text",
            "",
        ]

        return generate_gcode(
            toolpaths=flatten_path(self.preview.text_path),
            offset_x=offset_x,
            offset_y=offset_y,
            z_down=z_down,
            z_up=z_up,
            feed_xy=self.xy_feed_spin.value(),
            feed_z=self.z_feed_spin.value(),
            comments=comments,
        )

    def export_gcode(self):
        try:
            gcode = self.build_gcode()
        except ValueError as exc:
            QMessageBox.warning(self, "G-code", str(exc))
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save G-code",
            "text_plot.gcode",
            "G-code (*.gcode *.nc);;All files (*.*)",
        )
        if not filename:
            return

        Path(filename).write_text(gcode, encoding="utf-8")
        QMessageBox.information(self, "Saved", f"G-code saved:\n{filename}")

    @staticmethod
    def _spin(minimum, maximum, value):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" mm")
        return spin
