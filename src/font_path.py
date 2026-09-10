from PySide6.QtGui import QFont, QPainterPath, QTransform
from PySide6.QtCore import QRectF


def font_path_mm(text, family, font_size_mm):
    font = QFont(family)
    font.setPixelSize(max(1, int(round(font_size_mm * 10.0))))
    path = QPainterPath()
    path.addText(0.0, 0.0, font, text)
    transform = QTransform()
    transform.scale(0.1, 0.1)
    return transform.map(path)


def normalized_text_path(text, family, font_size_mm):
    raw = font_path_mm(text, family, font_size_mm)
    if raw.isEmpty():
        return QPainterPath(), QRectF()

    bounds = raw.boundingRect()
    transform = QTransform()
    transform.translate(-bounds.left(), bounds.bottom())
    transform.scale(1.0, -1.0)
    result = transform.map(raw)
    return result, result.boundingRect()