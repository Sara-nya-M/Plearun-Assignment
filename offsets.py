import math
import statistics


def estimate_offset(anchors):
    """Estimate one clock offset from at least three consistent anchors."""
    values = [float(value) for value in anchors if isinstance(value, (int, float))
              and not isinstance(value, bool) and math.isfinite(float(value))]

    if len(values) < 3:
        return None, "too few anchors"

    offset = float(statistics.median(values))
    deviations = [abs(value - offset) for value in values]
    mad = float(statistics.median(deviations))

    if mad > 2.0 or max(deviations) > 5.0:
        return None, "disagreeing anchors"

    return offset, "ok"
