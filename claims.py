import re

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
SPEED_RE = re.compile(r"\b(\d{1,3})\s*mph\b", re.I)
ZONE_RE = re.compile(r"\b(?:posted|in a|in the)\s+(\d{1,3})\b", re.I)
INTERVAL_RE = re.compile(r"\b(\d+)\s*(minutes?|mins?|seconds?|secs?)\s+(after|before)\b", re.I)
HEDGE_RE = re.compile(r"\b(about|around|roughly|approximately|approx|nearly)\b|~", re.I)

# Words that tell us which kind of event a sentence is about.
EVENTS = [
    ("911_call", re.compile(r"\b911\b", re.I)),
    ("unit_on_scene", re.compile(r"\bon scene\b|\barrived\b", re.I)),
    ("unit_dispatched", re.compile(r"\bdispatched\b", re.I)),
    ("stop", re.compile(r"\bstopped\b|\bpulled (?:in|over|into)\b", re.I)),
    ("observation", re.compile(r"\bobserved\b|\bfirst saw\b|\bspotted\b", re.I)),
]


def report_date(text):
    """Find the incident date (YYYY-MM-DD) mentioned in the report."""
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    return m.group(1) if m else None


def split_sentences(text):
    """Split into sentences. Each piece is an exact piece of the original text."""
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", text)
    return [p.strip() for p in pieces if p.strip()]


def has_claim_pattern(s):
    return bool(TIME_RE.search(s) or SPEED_RE.search(s) or INTERVAL_RE.search(s))


def split_clauses(sentence):
    """Split at commas only when BOTH sides contain a checkable pattern."""
    parts = [p.strip() for p in sentence.split(",")]
    clauses, current = [], parts[0]
    for part in parts[1:]:
        if has_claim_pattern(current) and has_claim_pattern(part):
            clauses.append(current)
            current = part
        else:
            current = current + ", " + part
    clauses.append(current)
    return clauses


def event_of(s):
    for name, rx in EVENTS:
        if rx.search(s):
            return name
    return None


def classify(clause):
    """Return a dict describing what kind of claim this clause is."""
    text = clause.rstrip(". ").strip()
    approx = bool(HEDGE_RE.search(clause))
    m = INTERVAL_RE.search(clause)
    if m:
        unit = m.group(2).lower()
        seconds = int(m.group(1)) * (60 if unit.startswith("min") else 1)
        return {"claim": text, "kind": "interval", "seconds": seconds,
                "direction": m.group(3).lower(), "event": event_of(clause),
                "approx": approx}
    m = SPEED_RE.search(clause)
    if m:
        z = ZONE_RE.search(clause)
        return {"claim": text, "kind": "speed", "speed": int(m.group(1)),
                "zone": int(z.group(1)) if z else None, "approx": approx}
    m = TIME_RE.search(clause)
    if m:
        return {"claim": text, "kind": "time",
                "hour": int(m.group(1)), "minute": int(m.group(2)),
                "event": event_of(clause), "approx": approx}
    return {"claim": text, "kind": "uncheckable"}


def is_header(sentence):
    """Banner / case-label lines are not claims."""
    return bool(re.match(r"^(SYNTHETIC\b|Incident\s+\d{4}-\d{2}-\d{2})", sentence))


def extract_claims(report_text):
    claims = []
    for sentence in split_sentences(report_text):
        if is_header(sentence):
            continue
        for clause in split_clauses(sentence):
            claims.append(classify(clause))
    return claims


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/report_fictional_02.txt"
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="replace")
    print("date:", report_date(text))
    for c in extract_claims(text):
        print(c)