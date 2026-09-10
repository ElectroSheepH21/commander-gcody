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
        painter.setPen(QPen(QColor(200, 40, 40), 2))
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
