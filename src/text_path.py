from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath, QTransform


def font_path_mm(text, family, font_size_mm):
    """Render text as a QPainterPath in millimeter coordinates.

    Uses 10x oversampling for the font rasterisation, then scales back
    down to millimeters. This avoids Qt integer-pixel size rounding.
    """
    font = QFont(family)
    font.setPixelSize(max(1, int(round(font_size_mm * 10.0))))
    line_height = QFontMetricsF(font).lineSpacing()

    path = QPainterPath()
    y = 0.0
    for line in text.split("\n"):
        path.addText(0.0, y, font, line)
        y += line_height

    transform = QTransform()
    transform.scale(0.1, 0.1)
    return transform.map(path)


def normalized_text_path(text, family, font_size_mm):
    """Return the text as a QPainterPath aligned to (0, 0) with Y up.

    Qt draws text with the baseline as origin and Y growing downward.
    This flips Y and translates so the bounding box starts at (0, 0),
    which matches the machine coordinate convention used elsewhere.
    """
    raw = font_path_mm(text, family, font_size_mm)
    if raw.isEmpty():
        return QPainterPath(), QRectF()

    bounds = raw.boundingRect()
    transform = QTransform()
    transform.translate(-bounds.left(), bounds.bottom())
    transform.scale(1.0, -1.0)
    result = transform.map(raw)
    return result, result.boundingRect()