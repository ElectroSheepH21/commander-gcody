import math
import re


def _move_time(dist, feed_mm_min, accel):
    if dist <= 0 or feed_mm_min <= 0:
        return 0.0
    v = feed_mm_min / 60.0
    d_accel = v * v / (2.0 * accel)
    if dist >= 2.0 * d_accel:
        # trapezoid — reaches target velocity
        return 2.0 * (v / accel) + (dist - 2.0 * d_accel) / v
    # triangle — segment too short to reach target
    return 2.0 * math.sqrt(dist / accel)


def estimate_seconds_from_gcode(gcode, rapid_feed_mm_min, accel_mm_s2):
    x = y = z = 0.0
    feed = 0.0
    seconds = 0.0
    token = re.compile(r"([XYZF])(-?\d+\.?\d*)", re.I)

    for raw in gcode.splitlines():
        line = raw.split(";")[0].strip().upper()
        if not line:
            continue
        words = line.split()
        code = words[0]
        if code not in ("G0", "G00", "G1", "G01"):
            continue

        nx, ny, nz = x, y, z
        new_feed = None
        for key, value in token.findall(line):
            value = float(value)
            if key == "X":
                nx = value
            elif key == "Y":
                ny = value
            elif key == "Z":
                nz = value
            elif key == "F":
                new_feed = value
        if new_feed is not None:
            feed = new_feed

        dist = math.sqrt((nx - x) ** 2 + (ny - y) ** 2 + (nz - z) ** 2)

        if code in ("G0", "G00"):
            seconds += _move_time(dist, rapid_feed_mm_min, accel_mm_s2)
        elif feed > 0:
            seconds += _move_time(dist, feed, accel_mm_s2)

        x, y, z = nx, ny, nz

    return seconds


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.2f} s"
    if seconds < 3600:
        minutes = seconds / 60.0
        return f"{minutes:.2f} min"
    return f"{seconds / 3600.0:.2f} h"


def flatten_path(path):
    return [list(poly) for poly in path.toSubpathPolygons() if len(poly) >= 2]


def generate_gcode(
    toolpaths,
    offset_x,
    offset_y,
    z_down,
    z_up,
    feed_xy,
    feed_z,
    comments,
):
    lines = list(comments)
    if lines and lines[-1] != "":
        lines.append("")

    lines.extend(
        [
            "G21 ; millimeters",
            "G90 ; absolute positioning",
            f"G0 Z{z_up:.3f}",
            "",
        ]
    )

    for poly in toolpaths:
        first = poly[0]
        x0 = offset_x + first.x()
        y0 = offset_y + first.y()
        lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")
        lines.append(f"G1 Z{z_down:.3f} F{feed_z}")
        for point in poly[1:]:
            x = offset_x + point.x()
            y = offset_y + point.y()
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_xy}")
        lines.append(f"G0 Z{z_up:.3f}")
        lines.append("")

    lines.extend(
        [
            f"G0 Z{z_up:.3f}",
            "G0 X0 Y0 ; return to origin",
            "M2",
            "",
        ]
    )
    return "\n".join(lines)
