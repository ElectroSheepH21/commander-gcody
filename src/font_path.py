from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath, QTransform, QBrush, QImage, QPainter
import numpy as np
import math


def font_path_mm(text, family, font_size_mm):
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
    raw = font_path_mm(text, family, font_size_mm)
    if raw.isEmpty():
        return QPainterPath(), QRectF()

    bounds = raw.boundingRect()
    transform = QTransform()
    transform.translate(-bounds.left(), bounds.bottom())
    transform.scale(1.0, -1.0)
    result = transform.map(raw)
    return result, result.boundingRect()

def centerline_text_path(text, font_family, font_size_mm):
    outline_path, bounds = normalized_text_path(text, font_family, font_size_mm)
    if outline_path.isEmpty() or bounds.width() <= 0 or bounds.height() <= 0:
        return QPainterPath(), bounds

    dpi = min(30.0, 3000.0 / max(bounds.width(), bounds.height()))
    dpi = max(dpi, 15.0)
    pad = 4
    W = int(bounds.width() * dpi) + 2 * pad
    H = int(bounds.height() * dpi) + 2 * pad

    image = QImage(W, H, QImage.Format_Grayscale8)
    image.fill(0)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QBrush(Qt.white))
    p.setPen(Qt.NoPen)
    p.translate(pad, H - pad)
    p.scale(dpi, -dpi)
    p.drawPath(outline_path)
    p.end()

    ptr = image.constBits()
    bpl = image.bytesPerLine()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=bpl * H).reshape(H, bpl)[:, :W]
    binary = arr > 128
    skel = _skeletonize_zs(binary)
    polylines = _trace_skeleton(skel)
    polylines = _chain_polylines(polylines)

    min_len_px = 2.0 * dpi
    polylines = [pl for pl in polylines
                 if len(pl) >= 3 and _polyline_length_px(pl) >= min_len_px]

    eps_px = 0.15 * dpi
    polylines = [_rdp(pl, eps_px) for pl in polylines]

    result = QPainterPath()
    for poly in polylines:
        if len(poly) < 2:
            continue
        px, py = poly[0]
        result.moveTo((px - pad) / dpi, (H - pad - py) / dpi)
        for px, py in poly[1:]:
            result.lineTo((px - pad) / dpi, (H - pad - py) / dpi)
    return result, bounds


def _skeletonize_zs(binary):
    img = binary.astype(np.uint8)
    while True:
        m1 = _zs_iter(img, 0)
        img[m1] = 0
        m2 = _zs_iter(img, 1)
        img[m2] = 0
        if not m1.any() and not m2.any():
            break
    return img.astype(bool)


def _zs_iter(img, step):
    def shift(dy, dx):
        out = np.zeros_like(img)
        y0, y1 = max(dy, 0), img.shape[0] + min(dy, 0)
        x0, x1 = max(dx, 0), img.shape[1] + min(dx, 0)
        out[y0:y1, x0:x1] = img[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        return out
    p2, p3, p4 = shift(1, 0),  shift(1, -1),  shift(0, -1)
    p5, p6, p7 = shift(-1, -1), shift(-1, 0), shift(-1, 1)
    p8, p9 = shift(0, 1), shift(1, 1)
    B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
    seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
    A = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
    if step == 0:
        c45 = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
    else:
        c45 = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
    return (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c45


def _trace_skeleton(skel):
    """Trace skeleton with direction-preserving junction traversal."""
    ys, xs = np.where(skel)
    pixels = set(zip(xs.tolist(), ys.tolist()))

    def neigh(p):
        x, y = p
        return [(x + dx, y + dy)
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (x + dx, y + dy) in pixels]

    visited = set()

    def edge(a, b):
        return (a, b) if a < b else (b, a)

    def walk(start, nxt):
        path = [start, nxt]
        visited.add(edge(start, nxt))
        prev, cur = start, nxt
        while True:
            cands = [n for n in neigh(cur) if edge(cur, n) not in visited]
            if not cands:
                break
            if len(cands) == 1:
                nxt = cands[0]
            else:
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                def align(c):
                    cdx, cdy = c[0] - cur[0], c[1] - cur[1]
                    return dx * cdx + dy * cdy
                nxt = max(cands, key=align)
            path.append(nxt)
            visited.add(edge(cur, nxt))
            prev, cur = cur, nxt
        return path

    degree = {p: len(neigh(p)) for p in pixels}
    endpoints = [p for p, d in degree.items() if d == 1]
    junctions = [p for p, d in degree.items() if d >= 3]

    polylines = []
    for ep in endpoints:
        for n in neigh(ep):
            if edge(ep, n) not in visited:
                polylines.append(walk(ep, n))
    for j in junctions:
        for n in neigh(j):
            if edge(j, n) not in visited:
                polylines.append(walk(j, n))

    used = {p for pl in polylines for p in pl}
    remaining = pixels - used
    while remaining:
        start = min(remaining)
        first = next((n for n in neigh(start)
                      if edge(start, n) not in visited), None)
        if first is None:
            remaining.discard(start)
            continue
        pl = walk(start, first)
        polylines.append(pl)
        remaining -= set(pl)
    return polylines

def _chain_polylines(polylines):
    pls = [list(pl) for pl in polylines if len(pl) >= 2]
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(pls):
            j = i + 1
            merged = False
            while j < len(pls):
                a0, a1 = pls[i][0], pls[i][-1]
                b0, b1 = pls[j][0], pls[j][-1]
                if a1 == b0:
                    pls[i] = pls[i] + pls[j][1:]
                elif a1 == b1:
                    pls[i] = pls[i] + list(reversed(pls[j]))[1:]
                elif a0 == b1:
                    pls[i] = pls[j] + pls[i][1:]
                elif a0 == b0:
                    pls[i] = list(reversed(pls[j])) + pls[i][1:]
                else:
                    j += 1
                    continue
                pls.pop(j)
                merged = True
                changed = True
            if not merged:
                i += 1
    return pls

def _polyline_length_px(pl):
    return sum(math.hypot(pl[i + 1][0] - pl[i][0], pl[i + 1][1] - pl[i][1])
               for i in range(len(pl) - 1))


def _rdp(pts, eps):
    if len(pts) < 3:
        return list(pts)
    dmax, idx = 0.0, 0
    x0, y0 = pts[0]
    xn, yn = pts[-1]
    dx, dy = xn - x0, yn - y0
    norm = math.hypot(dx, dy) or 1.0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dy * px - dx * py + xn * y0 - yn * x0) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = _rdp(pts[:idx + 1], eps)
        right = _rdp(pts[idx:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]