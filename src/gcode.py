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