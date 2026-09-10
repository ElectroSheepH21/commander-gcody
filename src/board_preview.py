from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class BoardPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(650, 500)
        self.board_width = 200.0
        self.board_height = 100.0
        self.board_thickness = 10.0

    def set_board(self, width_mm, height_mm, thickness_mm):
        self.board_width = width_mm
        self.board_height = height_mm
        self.board_thickness = thickness_mm
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
