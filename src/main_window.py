import json
from pathlib import Path
import time
from PySide6.QtCore import Qt, QTimer
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
    QSlider,
)

from board_preview import BoardPreview
from gcode import (
    flatten_path, generate_gcode, format_duration,
    estimate_seconds_from_gcode, simulate_toolpath, position_at,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_window()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        layout.addWidget(self._build_controls_column())
        self._init_playback_state()
        layout.addWidget(self._build_preview_area(), 1)

        self._connect_signals()
        self.update_preview()

    def _setup_window(self):
        self.setWindowTitle("Commander GCody")
        icon = Path(__file__).resolve().parents[1] / "res" / "app.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1050, 650)

    def _build_controls_column(self):
        controls = QWidget()
        controls.setMaximumWidth(350)
        col = QVBoxLayout(controls)
        col.addWidget(self._build_board_group())
        col.addWidget(self._build_text_group())
        col.addWidget(self._build_machine_group())
        col.addWidget(self._build_info_group())

        self.save_config_button = QPushButton("Save configuration...")
        self.save_config_button.clicked.connect(self.save_config)
        self.load_config_button = QPushButton("Load configuration...")
        self.load_config_button.clicked.connect(self.load_config)
        self.export_button = QPushButton("Save G-code...")
        self.export_button.clicked.connect(self.export_gcode)
        col.addWidget(self.save_config_button)
        col.addWidget(self.load_config_button)
        col.addWidget(self.export_button)
        col.addStretch()
        return controls

    def _build_board_group(self):
        group = QGroupBox("Board")
        form = QFormLayout(group)
        self.width_spin = self._spin(1.0, 5000.0, 200.0)
        self.height_spin = self._spin(1.0, 5000.0, 100.0)
        self.thickness_spin = self._spin(0.1, 500.0, 10.0)
        form.addRow("Width:", self.width_spin)
        form.addRow("Height:", self.height_spin)
        form.addRow("Thickness:", self.thickness_spin)
        return group

    def _build_text_group(self):
        group = QGroupBox("Text")
        form = QFormLayout(group)
        self.text_edit = QPlainTextEdit("Hello")
        self.text_edit.setFixedHeight(90)
        self.text_edit.setTabChangesFocus(True)
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase.families())
        index = self.font_combo.findText(QFont().family())
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        self.font_size_spin = self._spin(1.0, 500.0, 20.0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Outline", "Centerline"])
        form.addRow("Text:", self.text_edit)
        form.addRow("Font:", self.font_combo)
        form.addRow("Font size:", self.font_size_spin)
        form.addRow("Toolpath:", self.mode_combo)
        return group

    def _build_machine_group(self):
        group = QGroupBox("Machine / Z axis")
        form = QFormLayout(group)
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
        form.addRow("Plunge depth:", self.plunge_spin)
        form.addRow("Lift above surface:", self.lift_spin)
        form.addRow("XY feed rate:", self.xy_feed_spin)
        form.addRow("Z feed rate:", self.z_feed_spin)
        form.addRow("Rapid feed rate:", self.rapid_feed_spin)
        form.addRow("Acceleration:", self.accel_spin)
        return group

    def _build_info_group(self):
        group = QGroupBox("Calculated values")
        form = QFormLayout(group)
        self.text_width_label = QLabel("-")
        self.text_height_label = QLabel("-")
        self.range_label = QLabel("-")
        self.z_label = QLabel("-")
        self.fit_label = QLabel("-")
        self.time_label = QLabel("-")
        form.addRow("Text width:", self.text_width_label)
        form.addRow("Text height:", self.text_height_label)
        form.addRow("G-code range:", self.range_label)
        form.addRow("Z down / up:", self.z_label)
        form.addRow("Fits on board:", self.fit_label)
        form.addRow("Est. cut time:", self.time_label)
        return group

    def _init_playback_state(self):
        self.segments = []
        self.speed_multiplier = 1.0
        self.play_start_wall = 0.0
        self.play_start_t = 0.0
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(30)
        self.play_timer.timeout.connect(self.on_play_tick)

    def _build_preview_area(self):
        self.preview = BoardPreview()
        self.play_button = QPushButton("▶")
        self.play_button.setFixedWidth(36)
        self.play_button.clicked.connect(self.toggle_playback)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(
            ["0.5x", "1x", "2x", "5x", "10x", "25x", "50x", "100x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self.on_speed_change)
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_label = QLabel("0.00 s / 0.00 s")
        self.timeline_label.setMinimumWidth(160)

        timeline_row = QHBoxLayout()
        timeline_row.addWidget(self.play_button)
        timeline_row.addWidget(self.speed_combo)
        timeline_row.addWidget(self.timeline_slider, 1)
        timeline_row.addWidget(self.timeline_label)

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.preview, 1)
        col.addLayout(timeline_row)
        return container

    def _connect_signals(self):
        self.timeline_slider.valueChanged.connect(self.on_timeline_change)
        self.timeline_slider.sliderMoved.connect(self.on_slider_scrub)

        for spin in (self.width_spin, self.height_spin, self.thickness_spin):
            spin.valueChanged.connect(self.update_preview)

        self.text_edit.textChanged.connect(self.update_preview)
        self.font_combo.currentTextChanged.connect(self.update_preview)
        self.font_size_spin.valueChanged.connect(self.update_preview)
        self.mode_combo.currentTextChanged.connect(self.update_preview)

        self.plunge_spin.valueChanged.connect(self.update_preview)
        self.lift_spin.valueChanged.connect(self.update_preview)
        self.xy_feed_spin.valueChanged.connect(self.update_preview)
        self.z_feed_spin.valueChanged.connect(self.update_preview)
        self.rapid_feed_spin.valueChanged.connect(self.update_preview)
        self.accel_spin.valueChanged.connect(self.update_preview)

    def on_timeline_change(self, value):
        if not self.segments:
            self.preview.set_marker(None)
            self.timeline_label.setText(
                f"{format_duration(0)} / {format_duration(0)}")
            return
        total = self.segments[-1][1]
        t = (value / 1000.0) * total
        x, y, is_rapid = position_at(self.segments, t)
        self.preview.set_marker((x, y, is_rapid))
        self.preview.set_playback(self.segments, t)
        self.timeline_label.setText(
            f"{format_duration(t)} / {format_duration(total)}")

    def _current_t(self):
        if not self.segments:
            return 0.0
        total = self.segments[-1][1]
        return (self.timeline_slider.value() / 1000.0) * total

    def toggle_playback(self):
        if self.play_timer.isActive():
            self.pause_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if not self.segments:
            return
        total = self.segments[-1][1]
        if self._current_t() >= total - 1e-6:
            self.timeline_slider.setValue(0)
        self.play_start_wall = time.monotonic()
        self.play_start_t = self._current_t()
        self.play_timer.start()
        self.play_button.setText("⏸")

    def pause_playback(self):
        self.play_timer.stop()
        self.play_button.setText("▶")

    def on_play_tick(self):
        if not self.segments:
            self.pause_playback()
            return
        total = self.segments[-1][1]
        elapsed = time.monotonic() - self.play_start_wall
        new_t = self.play_start_t + elapsed * self.speed_multiplier
        if new_t >= total:
            self.timeline_slider.setValue(1000)
            self.pause_playback()
            return
        self.timeline_slider.setValue(int((new_t / total) * 1000))

    def on_slider_scrub(self, value):
        if self.play_timer.isActive():
            self.play_start_wall = time.monotonic()
            self.play_start_t = self._current_t()

    def on_speed_change(self, text):
        self.speed_multiplier = float(text.rstrip("x"))
        if self.play_timer.isActive():
            self.play_start_wall = time.monotonic()
            self.play_start_t = self._current_t()

    def update_preview(self):
        self.preview.set_data(
            self.width_spin.value(),
            self.height_spin.value(),
            self.thickness_spin.value(),
            self.text_edit.toPlainText(),
            self.font_combo.currentText(),
            self.font_size_spin.value(),
            self.mode_combo.currentText(),
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
            self.segments = simulate_toolpath(
                gcode, self.rapid_feed_spin.value(), self.accel_spin.value())
            seconds = self.segments[-1][1] if self.segments else 0.0
        except ValueError:
            self.segments = []
            seconds = 0.0
        self.time_label.setText(format_duration(seconds))
        if not self.segments and self.play_timer.isActive():
            self.pause_playback()
        elif self.play_timer.isActive():
            self.play_start_wall = time.monotonic()
            self.play_start_t = self._current_t()
        self.on_timeline_change(self.timeline_slider.value())

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
                "mode": self.mode_combo.currentText(),
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
            saved_mode = str(text.get("mode", self.mode_combo.currentText()))
            mode_index = self.mode_combo.findText(saved_mode)
            if mode_index >= 0:
                self.mode_combo.setCurrentIndex(mode_index)

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
