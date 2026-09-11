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


def _parse_moves(gcode):
    """Yield (code, nx, ny, nz, feed) for each motion line in the G-code."""
    x = y = z = 0.0
    feed = 0.0
    token = re.compile(r"([XYZF])(-?\d+\.?\d*)", re.I)

    for raw in gcode.splitlines():
        line = raw.split(";")[0].strip().upper()
        if not line:
            continue
        code = line.split()[0]
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

        yield code, nx, ny, nz, feed
        x, y, z = nx, ny, nz


class Toolpath:
    """Simulated G-code toolpath with trapezoidal motion.

    Given raw G-code plus machine parameters, computes a timed list of
    XY segments that can be queried for total duration and for the tool
    position at any given time.
    """

    def __init__(self, gcode, rapid_feed_mm_min, accel_mm_s2):
        self.rapid_feed = rapid_feed_mm_min
        self.accel = accel_mm_s2
        self._x = self._y = self._z = 0.0
        self._t = 0.0
        self._batch = []
        self._batch_feed = 0.0
        self.segments = []

        for move in _parse_moves(gcode):
            self._process(*move)
        self._flush()

    def duration(self):
        return self.segments[-1][1] if self.segments else 0.0

    def position_at(self, t):
        """Return (x, y, is_rapid) at time t along the toolpath."""
        if not self.segments:
            return (0.0, 0.0, True)
        if t <= self.segments[0][0]:
            s = self.segments[0]
            return (s[2], s[3], s[6])
        if t >= self.segments[-1][1]:
            s = self.segments[-1]
            return (s[4], s[5], s[6])
        for t0, t1, x0, y0, x1, y1, is_rapid in self.segments:
            if t0 <= t <= t1:
                frac = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return (x0 + frac * (x1 - x0), y0 + frac * (y1 - y0), is_rapid)
        s = self.segments[-1]
        return (s[4], s[5], s[6])

    def _process(self, code, nx, ny, nz, feed):
        xy_moved = abs(nx - self._x) > 1e-9 or abs(ny - self._y) > 1e-9
        is_cut = code in ("G1", "G01") and xy_moved

        if is_cut:
            self._add_to_batch(nx, ny, feed)
        else:
            self._flush()
            self._emit_rapid(code, nx, ny, nz, feed)

        self._x, self._y, self._z = nx, ny, nz

    def _add_to_batch(self, nx, ny, feed):
        # feed rate change breaks the batch — each trapezoid runs at one feed
        if self._batch and self._batch_feed != feed:
            self._flush()
        self._batch_feed = feed
        d = math.sqrt((nx - self._x) ** 2 + (ny - self._y) ** 2)
        self._batch.append((self._x, self._y, nx, ny, d))

    def _emit_rapid(self, code, nx, ny, nz, feed):
        dist = math.sqrt((nx - self._x) ** 2 + (ny - self._y) ** 2 + (nz - self._z) ** 2)
        v = self.rapid_feed if code in ("G0", "G00") else feed
        dt = _move_time(dist, v, self.accel)
        if dt > 0.0 or dist > 0.0:
            self.segments.append(
                (self._t, self._t + dt, self._x, self._y, nx, ny, True))
        self._t += dt

    def _flush(self):
        # collapse the batched cut moves into one trapezoid, then split
        # the resulting time proportionally back onto the sub-segments
        if not self._batch:
            return
        total_dist = sum(s[4] for s in self._batch)
        total_time = _move_time(total_dist, self._batch_feed, self.accel)
        elapsed = 0.0
        for x0, y0, x1, y1, d in self._batch:
            seg_t = total_time * (d / total_dist) if total_dist > 0 else 0.0
            self.segments.append(
                (self._t + elapsed, self._t + elapsed + seg_t,
                 x0, y0, x1, y1, False))
            elapsed += seg_t
        self._t += total_time
        self._batch.clear()


def format_duration(seconds):
    total = int(round(seconds))
    if total < 3600:
        m, s = divmod(total, 60)
        return f"{m}:{s:02d}"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


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

    # Setup commands (millimeters, absolute positioning, lift to safe height)
    lines.extend(
        [
            "G21 ; millimeters",
            "G90 ; absolute positioning",
            f"G0 Z{z_up:.3f}",
            "",
        ]
    )

    # One plunge-cut-lift cycle per polyline
    for poly in toolpaths:
        # Rapid move to the start point of the polyline
        first = poly[0]
        x0 = offset_x + first.x()
        y0 = offset_y + first.y()
        lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")

        # Controlled plunge into the material at feed_z rate
        lines.append(f"G1 Z{z_down:.3f} F{feed_z}")

        # Controlled cutting along the polyline at feed_xy rate
        for point in poly[1:]:
            x = offset_x + point.x()
            y = offset_y + point.y()
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_xy}")

        # Controlled lift back to safe height at feed_z rate
        lines.append(f"G0 Z{z_up:.3f}")
        lines.append("")

    # Ensure the tool is lifted and return to origin, then end the program
    lines.extend(
        [
            f"G0 Z{z_up:.3f}",
            "G0 X0 Y0 ; return to origin",
            "M2",
            "",
        ]
    )
    return "\n".join(lines)