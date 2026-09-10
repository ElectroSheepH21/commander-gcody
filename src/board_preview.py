from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTransform
from font_path import normalized_text_path


class BoardPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(650, 500)
        self.board_width = 200.0
        self.board_height = 100.0
        self.board_thickness = 10.0
        self.text = ""
        self.font_family = ""
        self.font_size_mm = 20.0
        self.text_path = QPainterPath()
        self.text_bounds = QRectF()
        self.text_x = 0.0
        self.text_y = 0.0
        self.marker_pos = None
        self.playback_segments = []
        self.current_t = 0.0

    def set_marker(self, pos):
        self.marker_pos = pos
        self.update()
        
    def set_playback(self, segments, current_t):
        self.playback_segments = segments
        self.current_t = current_t
        self.update()

    def set_data(self, width_mm, height_mm, thickness_mm, text, font_family, font_size_mm):
        self.board_width = width_mm
        self.board_height = height_mm
        self.board_thickness = thickness_mm
        self.text = text
        self.font_family = font_family
        self.font_size_mm = font_size_mm

        self.text_path, self.text_bounds = normalized_text_path(
            text, font_family, font_size_mm
        )
        self.text_x = (self.board_width - self.text_bounds.width()) / 2.0
        self.text_y = (self.board_height - self.text_bounds.height()) / 2.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window().color())

        if self.board_width <= 0 or self.board_height <= 0:
            return

        margin = 45.0
        scale = min(
            (self.width() - 2 * margin) / self.board_width,
            (self.height() - 2 * margin) / self.board_height,
        )
        w = self.board_width * scale
        h = self.board_height * scale
        x = (self.width() - w) / 2.0
        y = (self.height() - h) / 2.0

        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        painter.setPen(QPen(QColor(60, 60, 60), 2))
        painter.setBrush(QBrush(QColor(222, 196, 147)))
        painter.drawRect(QRectF(x, y, w, h))

        machine = QTransform()
        machine.translate(x, y + h)
        machine.scale(scale, -scale)
        machine.translate(self.text_x, self.text_y)

        fits = (
            self.text_bounds.width() <= self.board_width
            and self.text_bounds.height() <= self.board_height
        )
        color = QColor(20, 20, 20) if fits else QColor(190, 30, 30)
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(machine.map(self.text_path))
        
        ox = x + w / 2.0
        oy = y + h / 2.0

        color = QColor(20, 20, 20) if fits else QColor(190, 30, 30)
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(machine.map(self.text_path))

        if self.playback_segments and self.current_t > 0:
            painter.setPen(QPen(QColor(220, 40, 40), 1.8))
            painter.setBrush(Qt.NoBrush)
            for t0, t1, x0, y0, x1, y1, is_rapid in self.playback_segments:
                if is_rapid or t0 >= self.current_t:
                    continue
                px0 = ox + x0 * scale
                py0 = oy - y0 * scale
                if t1 <= self.current_t:
                    px1 = ox + x1 * scale
                    py1 = oy - y1 * scale
                else:
                    frac = (self.current_t - t0) / (t1 - t0) if t1 > t0 else 1.0
                    ix = x0 + frac * (x1 - x0)
                    iy = y0 + frac * (y1 - y0)
                    px1 = ox + ix * scale
                    py1 = oy - iy * scale
                painter.drawLine(QPointF(px0, py0), QPointF(px1, py1))

        painter.setPen(QPen(QColor(60, 60, 60), 2))
        painter.drawLine(QPointF(ox - 9, oy), QPointF(ox + 9, oy))
        painter.drawLine(QPointF(ox, oy - 9), QPointF(ox, oy + 9))
        painter.drawText(QPointF(ox + 12, oy - 8), "X0 / Y0")

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRectF(x, y - 28, w, 22),
            Qt.AlignCenter,
            f"{self.board_width:.1f} x {self.board_height:.1f} x "
            f"{self.board_thickness:.1f} mm",
        )

        if not self.text_path.isEmpty():
            bb = QRectF(
                self.text_x,
                self.text_y,
                self.text_bounds.width(),
                self.text_bounds.height(),
            )
            bb_on_widget = QTransform()
            bb_on_widget.translate(x, y + h)
            bb_on_widget.scale(scale, -scale)
            painter.setPen(QPen(QColor(70, 160, 255), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(bb_on_widget.mapRect(bb))
            if self.marker_pos is not None:
                gx, gy, is_rapid = self.marker_pos
                mx = ox + gx * scale
                my = oy - gy * scale
                size = 10.0 * 0.7071
                gap = 4.0 * 0.7071
                dot_r = 1.8
                color = QColor(220, 40, 40, 128) if is_rapid else QColor(220, 40, 40)
                painter.setPen(QPen(color, 2.0))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(QPointF(mx - size, my - size), QPointF(mx - gap, my - gap))
                painter.drawLine(QPointF(mx + gap, my + gap), QPointF(mx + size, my + size))
                painter.drawLine(QPointF(mx - size, my + size), QPointF(mx - gap, my + gap))
                painter.drawLine(QPointF(mx + gap, my - gap), QPointF(mx + size, my - size))
                if not is_rapid:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(QPointF(mx, my), dot_r, dot_r)
                    painter.setPen(QPen(color, 1.5))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(mx, my), size, size)
