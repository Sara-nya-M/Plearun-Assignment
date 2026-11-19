import re

from claims import INTERVAL_RE
from findings import build_index, make_finding
from offsets import (
    clock_domain,
    clock_reading,
    estimate_report_offsets,
    event_of,
    speed_zone,
)


_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_HEDGE_RE = re.compile(r"\b(?:about|around|roughly|approximately|approx|nearly)\b|~", re.I)
_NEGATION_RE = re.compile(r"\b(?:not|never|isn't|wasn't|didn't|incorrectly)\b", re.I)
_STOP_RE = re.compile(r"\bstop(?:ped|ping)?\b|\bpulling in\b|\bpulled (?:in|over|into)\b", re.I)
_SCENE_RE = re.compile(r"\bon scene\b|\barriv(?:ed|al)\b", re.I)


def _minute_of_day(match):
    return int(match.group(1)) * 60 + int(match.group(2))


def _minute_distance(left, right):
    difference = abs(left - right)
    return min(difference, 24 * 60 - difference)


def _event_note_times(claim, rows):
    event = claim.get("event")
    candidates = []
    for row in rows:
        note = row.get("note")
        if not isinstance(note, str) or event_of(row) != event:
            continue
        times = list(_TIME_RE.finditer(note))
        candidates.append((row, times[0] if len(times) == 1 else None, note))
    return candidates


def _decide_time(claim, note_rows, rows, index, claims, claim_index):
    candidates = _event_note_times(claim, note_rows)
    if len(candidates) == 1 and candidates[0][1] is not None:
        row, time_match, quote = candidates[0]
        target = int(claim["hour"]) * 60 + int(claim["minute"])
        observed = _minute_of_day(time_match)
        distance = _minute_distance(target, observed)
        tolerance = 1 if claim.get("approx") else 0

        if distance <= tolerance:
            return make_finding(claim["claim"], "match", index, row["file"], row["row"], quote)

        if not claim.get("approx") and not _HEDGE_RE.search(quote):
            return make_finding(claim["claim"], "conflict", index, row["file"], row["row"], quote)

        return make_finding(claim["claim"], "not_settled", index)

    offsets = estimate_report_offsets(claims, rows, claim_index)
    target = int(claim["hour"]) * 3600 + int(claim["minute"]) * 60
    aligned = []
    for row in rows:
        if event_of(row) != claim.get("event"):
            continue
        estimate = offsets.get(clock_domain(row))
        reading = clock_reading(row)
        if estimate is None or estimate[1] != "ok" or reading is None:
            continue
        offset, _, offset_uncertainty = estimate
        if offset is None:
            continue
        observed = (reading[0] - offset) % (24 * 60 * 60)
        distance_seconds = min(
            abs(target - observed),
            24 * 60 * 60 - abs(target - observed),
        )
        aligned.append((row, distance_seconds, reading[1] + offset_uncertainty))

    if not aligned:
        return make_finding(claim["claim"], "not_settled", index)

    within_tolerance = [
        distance <= (60 if claim.get("approx") else 0) + uncertainty
        for _, distance, uncertainty in aligned
    ]
    if all(within_tolerance):
        row = aligned[0][0]
        return make_finding(
            claim["claim"], "match", index, row["file"], row["row"], row.get("raw")
        )
    if (len(aligned) == 1 and not within_tolerance[0]
            and not claim.get("approx")):
        row = aligned[0][0]
        return make_finding(
            claim["claim"], "conflict", index, row["file"], row["row"], row.get("raw")
        )
    return make_finding(claim["claim"], "not_settled", index)


def _decide_speed(claim, rows, index, claims, claim_index):
    context = claim.get("context_time")
    if not isinstance(context, dict) or claim.get("zone") is None:
        return make_finding(claim["claim"], "not_settled", index)

    offsets = estimate_report_offsets(claims, rows, claim_index)
    target = int(context["hour"]) * 3600 + int(context["minute"]) * 60
    aligned = []
    for row in rows:
        text = row.get("text")
        if (not isinstance(text, str)
                or not re.search(r"^\s*(?:\[SYNTHETIC\]\s*)?Officer Lee\s*:", text, re.I)
                or _NEGATION_RE.search(text)
                or speed_zone(row) != (claim["speed"], claim["zone"])):
            continue
        estimate = offsets.get(clock_domain(row))
        reading = clock_reading(row)
        if estimate is None or estimate[1] != "ok" or reading is None:
            continue
        offset, _, offset_uncertainty = estimate
        if offset is None:
            continue
        observed = (reading[0] - offset) % (24 * 60 * 60)
        distance = min(abs(target - observed), 24 * 60 * 60 - abs(target - observed))
        aligned.append((row, distance, reading[1] + offset_uncertainty))

    if len(aligned) != 1:
        return make_finding(claim["claim"], "not_settled", index)

    row, distance, uncertainty = aligned[0]
    tolerance = 60 if context.get("approx") else 0
    if distance <= tolerance + uncertainty:
        return make_finding(
            claim["claim"], "match", index, row["file"], row["row"], row.get("raw")
        )
    return make_finding(claim["claim"], "not_settled", index)


def _decide_interval(claim, rows, index):
    candidates = []
    for row in rows:
        text = row.get("note")
        if not isinstance(text, str):
            text = row.get("text")
        if (not isinstance(text, str) or not _STOP_RE.search(text)
                or not _SCENE_RE.search(text)):
            continue
        interval_matches = list(INTERVAL_RE.finditer(text))
        if len(interval_matches) != 1:
            continue
        match = interval_matches[0]
        unit = match.group(2).lower()
        try:
            observed_seconds = int(match.group(1)) * (
                60 if unit.startswith("min") else 1
            )
        except ValueError:
            continue
        candidates.append((row, match, observed_seconds, text))

    if len(candidates) != 1:
        return make_finding(claim["claim"], "not_settled", index)

    row, match, observed_seconds, source_text = candidates[0]
    same_direction = match.group(3).lower() == claim.get("direction")
    tolerance = 60 if claim.get("approx") else 0
    agrees = same_direction and abs(observed_seconds - claim["seconds"]) <= tolerance
    quote = row.get("raw")
    if agrees:
        return make_finding(claim["claim"], "match", index, row["file"], row["row"], quote)
    if not claim.get("approx") and not _HEDGE_RE.search(source_text):
        return make_finding(claim["claim"], "conflict", index, row["file"], row["row"], quote)
    return make_finding(claim["claim"], "not_settled", index)


def decide_claims(claims, rows):
    """Make conservative findings with leave-one-claim-out clock calibration."""
    index = build_index(rows)
    notes = [row for row in rows if isinstance(row.get("note"), str)]
    findings = []

    for claim_index, claim in enumerate(claims):
        if claim.get("kind") == "uncheckable":
            result = make_finding(claim["claim"], "not_checkable", index)
        elif claim.get("kind") == "time":
            result = _decide_time(claim, notes, rows, index, claims, claim_index)
        elif claim.get("kind") == "speed":
            result = _decide_speed(claim, rows, index, claims, claim_index)
        elif claim.get("kind") == "interval":
            result = _decide_interval(claim, rows, index)
        else:
            result = make_finding(claim["claim"], "not_settled", index)
        findings.append(result)

    return findings
