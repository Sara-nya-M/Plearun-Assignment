import csv
import io
import json
import logging
import math
import re
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


def parse_time(value):
    """Turn a timestamp (string or number) into a UTC datetime, or None if unclear."""
    value = str(value).strip()
    if value.isdigit():                       # e.g. 1772504078000 (milliseconds)
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        t = datetime.fromisoformat(value)     # e.g. 2026-03-02T21:15:18-05:00
    except ValueError:
        return None
    if t.tzinfo is None:                      # no timezone given: don't guess
        return None
    return t.astimezone(timezone.utc)


def parse_naive(value):
    """For timestamps WITHOUT a timezone: keep the clock reading as-is."""
    try:
        t = datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    return t if t.tzinfo is None else None


def load_camera(path):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number == 1 and line.startswith("#"):
            continue
        if number == 2:
            continue
        try:
            fields = next(csv.reader(io.StringIO(line), strict=True))
            if len(fields) != 4:
                raise ValueError("expected four fields")
            speed, zone = int(fields[2]), int(fields[3])
        except (csv.Error, StopIteration, ValueError):
            logger.warning("Skipping malformed camera row %d", number)
            continue
        rows.append({
            "file": "camera_log.csv", "row": number, "raw": line,
            "clock_id": "camera:%s" % fields[1],
            "time": parse_time(fields[0]), "device": fields[1],
            "speed": speed, "zone": zone,
        })
    return rows


def find_event_list(node, key=None):
    """Search nested JSON for the first list of objects. Returns (key, list)."""
    if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
        return key, node
    if isinstance(node, dict):
        for k, v in node.items():
            found = find_event_list(v, k)
            if found:
                return found
    return None


def raw_event_texts(text, key):
    """Cut out the exact original text of each event object."""
    start = text.find('"%s"' % key)
    start = text.find("[", start) + 1
    decoder = json.JSONDecoder()
    pieces, pos = [], start
    while True:
        while pos < len(text) and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            break
        _, end = decoder.raw_decode(text, pos)
        pieces.append(text[pos:end])
        pos = end
    return pieces


def load_dispatch(path):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    found = find_event_list(json.loads(text))
    if not found:
        return []
    key, events = found
    raws = raw_event_texts(text, key)
    rows = []
    for number, event in enumerate(events, start=1):
        raw = raws[number - 1] if len(raws) == len(events) else None
        logged = event.get("logged")
        rows.append({
            "file": "dispatch.json", "row": number, "raw": raw,
            "clock_id": "dispatch",
            "time": parse_time(logged) if logged is not None else None,
            "naive_time": parse_naive(logged) if logged is not None else None,
            "type": event.get("type"), "id": event.get("id"),
            "unit": event.get("unit"),
        })
    return rows


def split_lines(text):
    """Split into lines KEEPING the line endings, on \r\n, \n or \r only."""
    return re.findall(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+", text)


def decode_bytes(data):
    """Try UTF-8 first; if that fails, treat as Windows-1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def load_notes(path):
    with open(path, "rb") as f:
        text = decode_bytes(f.read())
    lines = split_lines(text)
    reader = csv.reader(lines)
    rows, previous_end, header = [], 0, None
    for fields in reader:
        start, end = previous_end + 1, reader.line_num
        previous_end = end
        raw = "".join(lines[start - 1:end]).rstrip("\r\n")
        if header is None:                    # first record is the header
            header = fields
            continue
        if len(fields) != len(header):
            logger.warning("Skipping malformed notes record at line %d", start)
            continue
        record = dict(zip(header, fields))
        try:
            clock = datetime.strptime(record.get("Time", "").strip(), "%H:%M").time()
        except ValueError:
            clock = None
        rows.append({
            "file": path.replace("\\", "/").split("/")[-1], "row": start, "raw": raw,
            "clock_id": "notes:%s" % path.replace("\\", "/").split("/")[-1],
            "id": record.get("ID"), "author": record.get("Author"),
            "note": record.get("Note"), "clock": clock,
        })
    return rows


def parse_vtt_seconds(value):
    """'00:00:03.500' or '03.500' style -> seconds as a number."""
    parts = value.strip().replace(",", ".").split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def load_vtt(path):
    with open(path, "rb") as f:
        text = decode_bytes(f.read())
    blocks, current = [], []
    for line in split_lines(text):
        if line.strip(" \t\r\n"):
            current.append(line)
        elif current:
            blocks.append("".join(current).rstrip("\r\n"))
            current = []
    if current:
        blocks.append("".join(current).rstrip("\r\n"))

    rows, counter = [], 0
    for block in blocks:
        lines = re.split(r"\r\n|\n|\r", block)
        timing = [i for i, ln in enumerate(lines) if "-->" in ln]
        if not timing:                        # WEBVTT header, NOTE, STYLE...
            continue
        i = timing[0]
        left, right = lines[i].split("-->", 1)
        try:
            start = parse_vtt_seconds(left)
            end = parse_vtt_seconds(right.split()[0])
        except (ValueError, IndexError):
            logger.warning("Skipping malformed WebVTT cue")
            continue
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            logger.warning("Skipping malformed WebVTT cue")
            continue
        counter += 1
        label = lines[0].strip() if i > 0 else ""
        try:
            number = int(label) if label.isdigit() else counter
        except ValueError:
            number = counter
        rows.append({
            "file": path.replace("\\", "/").split("/")[-1], "row": number, "raw": block,
            "clock_id": "vtt:%s" % path.replace("\\", "/").split("/")[-1],
            "start": start, "end": end, "text": "\n".join(lines[i + 1:]),
        })
    return rows