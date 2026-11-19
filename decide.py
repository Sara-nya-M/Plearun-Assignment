import re

from findings import build_index, make_finding


_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_EVENT_PATTERNS = {
    "911_call": re.compile(r"\b911\b|\bcall\b", re.I),
    "observation": re.compile(r"\bobserv(?:ed|ation)\b|\bfirst saw\b|\bspotted\b", re.I),
    "stop": re.compile(r"\bstopp?ed\b|\bpulled (?:in|over|into)\b", re.I),
    "unit_on_scene": re.compile(r"\bon scene\b|\barriv(?:ed|al)\b", re.I),
    "unit_dispatched": re.compile(r"\bdispatched\b", re.I),
}
_HEDGE_RE = re.compile(r"\b(?:about|around|roughly|approximately|approx|nearly)\b|~", re.I)


def _event_matches(event, text):
    pattern = _EVENT_PATTERNS.get(event)
    return bool(pattern and pattern.search(text or ""))


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
        if not isinstance(note, str) or not _event_matches(event, note):
            continue
        times = list(_TIME_RE.finditer(note))
        candidates.append((row, times[0] if len(times) == 1 else None, note))
    return candidates


def _decide_time(claim, rows, index):
    candidates = _event_note_times(claim, rows)
    if len(candidates) != 1 or candidates[0][1] is None:
        return make_finding(claim["claim"], "not_settled", index)

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


def decide_claims(claims, rows):
    """Make conservative findings; only explicit, event-matched note times are aligned."""
    index = build_index(rows)
    notes = [row for row in rows if isinstance(row.get("note"), str)]
    findings = []

    for claim in claims:
        if claim.get("kind") == "uncheckable":
            result = make_finding(claim["claim"], "not_checkable", index)
        elif claim.get("kind") == "time":
            result = _decide_time(claim, notes, index)
        else:
            # The available speed/dispatch/transcript records lack a reliable
            # shared event anchor, so they cannot support a safe alignment.
            result = make_finding(claim["claim"], "not_settled", index)
        findings.append(result)

    return findings
