import math
import re
import statistics
from datetime import datetime, time, timedelta, timezone


REPORT_TZ = timezone(timedelta(hours=-5))
DAY_SECONDS = 24 * 60 * 60
_EVENT_PATTERNS = (
    ("911_call", re.compile(r"\b911\b|\bcaller\b|\bcall\b", re.I)),
    ("unit_on_scene", re.compile(r"\bon scene\b|\barriv(?:ed|al)\b", re.I)),
    ("unit_dispatched", re.compile(r"\bdispatched\b", re.I)),
    ("stop", re.compile(r"\bstopp?ed\b|\bpulling in\b|\bpulled (?:in|over|into)\b", re.I)),
    ("observation", re.compile(r"\bobserv(?:ed|ation)\b|\bfirst saw\b|\bspotted\b", re.I)),
)


def estimate_offset(anchors):
    """Estimate an offset from numeric anchors or (offset, uncertainty) pairs."""
    values, uncertainties = [], []
    for anchor in anchors:
        if isinstance(anchor, (tuple, list)) and len(anchor) == 2:
            value, uncertainty = anchor
        else:
            value, uncertainty = anchor, 0.0
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or isinstance(uncertainty, bool)
                or not isinstance(uncertainty, (int, float))
                or not math.isfinite(float(value))
                or not math.isfinite(float(uncertainty))
                or uncertainty < 0):
            continue
        values.append(float(value))
        uncertainties.append(float(uncertainty))

    if len(values) < 3:
        return None, "too few anchors"

    offset = float(statistics.median(values))
    deviations = [abs(value - offset) for value in values]
    mad = float(statistics.median(deviations))
    tolerance = float(statistics.median(uncertainties))

    if mad > max(2.0, tolerance) or any(
        deviation > 5.0 + uncertainty
        for deviation, uncertainty in zip(deviations, uncertainties)
    ):
        return None, "disagreeing anchors"

    return offset, "ok"


def event_of(row):
    """Return a narrow event label from structured fields or record text."""
    event_type = row.get("type")
    if isinstance(event_type, str) and event_type in {name for name, _ in _EVENT_PATTERNS}:
        return event_type

    text = " ".join(
        value for value in (row.get("note"), row.get("text"))
        if isinstance(value, str)
    )
    matches = [name for name, pattern in _EVENT_PATTERNS if pattern.search(text)]
    return matches[0] if len(matches) == 1 else None


def clock_domain(row):
    if isinstance(row.get("clock_id"), str) and row["clock_id"]:
        return row["clock_id"]
    device = row.get("device")
    if device:
        return "%s:%s" % (row.get("file", "camera"), device)
    return row.get("file", "unknown")


def clock_reading(row):
    """Return local seconds since midnight and its precision in seconds."""
    value = row.get("time")
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(REPORT_TZ)
        return _seconds_of_day(value.time()), 0.5

    value = row.get("naive_time")
    if isinstance(value, datetime):
        return _seconds_of_day(value.time()), 0.5

    value = row.get("clock")
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        if value.tzinfo is not None:
            value = datetime.combine(datetime(2000, 1, 1), value).astimezone(REPORT_TZ).time()
        return _seconds_of_day(value), 30.0

    start, end = row.get("start"), row.get("end")
    if (isinstance(start, (int, float)) and isinstance(end, (int, float))
            and math.isfinite(start) and math.isfinite(end) and end >= start):
        return ((start + end) / 2) % DAY_SECONDS, (end - start) / 2
    return None


def _seconds_of_day(value):
    return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1000000


def _signed_day_difference(left, right):
    return (left - right + DAY_SECONDS / 2) % DAY_SECONDS - DAY_SECONDS / 2


def estimate_report_offsets(claims, rows, excluded_claim):
    """Calibrate each record clock against three other exact report event times."""
    event_counts = {}
    for claim in claims:
        if claim.get("kind") == "time" and claim.get("event"):
            event_counts[claim["event"]] = event_counts.get(claim["event"], 0) + 1

    rows_by_domain = {}
    for row in rows:
        reading = clock_reading(row)
        event = event_of(row)
        if reading is None or event is None:
            continue
        rows_by_domain.setdefault(clock_domain(row), []).append((event, row, reading))

    anchors = {}
    for claim_index, claim in enumerate(claims):
        if (claim_index == excluded_claim or claim.get("kind") != "time"
                or claim.get("approx") or not claim.get("event")
                or event_counts.get(claim["event"]) != 1):
            continue
        report_time = int(claim["hour"]) * 3600 + int(claim["minute"]) * 60
        for domain, entries in rows_by_domain.items():
            candidates = [entry for entry in entries if entry[0] == claim["event"]]
            if len(candidates) != 1:
                continue
            _, row, (record_time, precision) = candidates[0]
            delta = _signed_day_difference(record_time, report_time)
            anchors.setdefault(domain, []).append((delta, precision))

    results = {}
    for domain, samples in anchors.items():
        offset, reason = estimate_offset(samples)
        uncertainty = float(statistics.median(sample[1] for sample in samples))
        results[domain] = (offset, reason, uncertainty)
    return results
