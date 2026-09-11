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
    """Yield (code, nx, ny, nz, feed, pass_index, total_passes) per motion line.

    pass_index/total_passes come from "; Pass i/N" marker comments emitted
    by generate_gcode ahead of each multi-pass cut; they stay at (1, 1) for
    everything before the first marker or when the G-code has none.
    """
    x = y = z = 0.0
    feed = 0.0
    pass_index, total_passes = 1, 1
    token = re.compile(r"([XYZF])(-?\d+\.?\d*)", re.I)
    pass_marker = re.compile(r"^;\s*Pass\s+(\d+)\s*/\s*(\d+)", re.I)

    for raw in gcode.splitlines():
        marker = pass_marker.match(raw.strip())
        if marker:
            pass_index, total_passes = int(marker.group(1)), int(marker.group(2))
            continue

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

        yield code, nx, ny, nz, feed, pass_index, total_passes
        x, y, z = nx, ny, nz


class Toolpath:
    """Simulated G-code toolpath with trapezoidal motion.

    Given raw G-code plus machine parameters, computes a timed list of
    XY segments that can be queried for total duration and for the tool
    position at any given time. Each segment is
    (t0, t1, x0, y0, x1, y1, is_rapid, pass_index, total_passes) — the
    trailing pair identifies which stepdown pass (1-based) a cut belongs
    to, so a viewer can tell an already-cut-once line from a finished one.
    """

    def __init__(self, gcode, rapid_feed_mm_min, accel_mm_s2):
        self.rapid_feed = rapid_feed_mm_min
        self.accel = accel_mm_s2
        self._x = self._y = self._z = 0.0
        self._t = 0.0
        self._batch = []
        self._batch_feed = 0.0
        self._batch_pass = (1, 1)
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
        for s in self.segments:
            t0, t1 = s[0], s[1]
            if t0 <= t <= t1:
                frac = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return (s[2] + frac * (s[4] - s[2]), s[3] + frac * (s[5] - s[3]), s[6])
        s = self.segments[-1]
        return (s[4], s[5], s[6])

    def _process(self, code, nx, ny, nz, feed, pass_index, total_passes):
        xy_moved = abs(nx - self._x) > 1e-9 or abs(ny - self._y) > 1e-9
        is_cut = code in ("G1", "G01") and xy_moved

        if is_cut:
            self._add_to_batch(nx, ny, feed, pass_index, total_passes)
        else:
            self._flush()
            self._emit_rapid(code, nx, ny, nz, feed, pass_index, total_passes)

        self._x, self._y, self._z = nx, ny, nz

    def _add_to_batch(self, nx, ny, feed, pass_index, total_passes):
        # feed or pass change breaks the batch — each trapezoid runs at one feed
        pass_key = (pass_index, total_passes)
        if self._batch and (self._batch_feed != feed or self._batch_pass != pass_key):
            self._flush()
        self._batch_feed = feed
        self._batch_pass = pass_key
        d = math.sqrt((nx - self._x) ** 2 + (ny - self._y) ** 2)
        self._batch.append((self._x, self._y, nx, ny, d))

    def _emit_rapid(self, code, nx, ny, nz, feed, pass_index, total_passes):
        dist = math.sqrt((nx - self._x) ** 2 + (ny - self._y) ** 2 + (nz - self._z) ** 2)
        v = self.rapid_feed if code in ("G0", "G00") else feed
        dt = _move_time(dist, v, self.accel)
        if dt > 0.0 or dist > 0.0:
            self.segments.append(
                (self._t, self._t + dt, self._x, self._y, nx, ny, True,
                 pass_index, total_passes))
        self._t += dt

    def _flush(self):
        # collapse the batched cut moves into one trapezoid, then split
        # the resulting time proportionally back onto the sub-segments
        if not self._batch:
            return
        total_dist = sum(s[4] for s in self._batch)
        total_time = _move_time(total_dist, self._batch_feed, self.accel)
        pass_index, total_passes = self._batch_pass
        elapsed = 0.0
        for x0, y0, x1, y1, d in self._batch:
            seg_t = total_time * (d / total_dist) if total_dist > 0 else 0.0
            self.segments.append(
                (self._t + elapsed, self._t + elapsed + seg_t,
                 x0, y0, x1, y1, False, pass_index, total_passes))
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


def compute_pass_depths(surface_z, target_z, max_stepdown):
    """Split the cut from surface_z down to target_z into even passes.

    Each pass removes at most max_stepdown mm. Returns the list of Z
    heights to plunge to, shallowest first, deepest (== target_z) last.
    A max_stepdown of 0 (or a cut that already fits in one bite) yields
    a single-element list, i.e. a single pass.
    """
    total_depth = surface_z - target_z
    if total_depth <= 0:
        return [target_z]
    if max_stepdown and max_stepdown > 0 and total_depth > max_stepdown:
        num_passes = math.ceil(total_depth / max_stepdown)
    else:
        num_passes = 1
    return [surface_z - total_depth * i / num_passes for i in range(1, num_passes + 1)]


def generate_gcode(
    toolpaths,
    offset_x,
    offset_y,
    surface_z,
    z_down,
    z_up,
    feed_xy,
    feed_z,
    comments,
    max_stepdown=0.0,
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

    pass_depths = compute_pass_depths(surface_z, z_down, max_stepdown)
    num_passes = len(pass_depths)

    # One plunge-cut-lift cycle per pass, per polyline — every pass rapids
    # back to the start point and safe height before plunging deeper
    for poly in toolpaths:
        first = poly[0]
        x0 = offset_x + first.x()
        y0 = offset_y + first.y()

        for i, pass_z in enumerate(pass_depths, start=1):
            # Marks which stepdown pass this is, so the simulator/preview
            # can tell a partially-cut line from a fully finished one
            if num_passes > 1:
                lines.append(f"; Pass {i}/{num_passes}")

            # Rapid move to the start point of the polyline
            lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")

            # Controlled plunge into the material at feed_z rate
            lines.append(f"G1 Z{pass_z:.3f} F{feed_z}")

            # Controlled cutting along the polyline at feed_xy rate
            for point in poly[1:]:
                x = offset_x + point.x()
                y = offset_y + point.y()
                lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_xy}")

            # Controlled lift back to safe height
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