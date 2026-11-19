from datetime import timezone, timedelta
from loaders import load_camera, load_dispatch, load_notes, load_vtt

LOCAL = timezone(timedelta(hours=-5))   # display only: the report is in -05:00
DATE = "2026-03-02"                     # the report date

lines = []

for r in load_camera("records/camera_log.csv"):
    when = r["time"].astimezone(LOCAL).strftime("%Y-%m-%d %H:%M:%S") if r["time"] else "UNKNOWN"
    lines.append((when, "camera  ", "row %d" % r["row"], "%s %d mph (zone %d)" % (r["device"], r["speed"], r["zone"])))

for r in load_dispatch("records/dispatch.json"):
    if r["time"]:
        when = r["time"].astimezone(LOCAL).strftime("%Y-%m-%d %H:%M:%S")
        tag = ""
    elif r["naive_time"]:
        when = r["naive_time"].strftime("%Y-%m-%d %H:%M:%S")
        tag = "  <- NO TIMEZONE"
    else:
        when, tag = "UNKNOWN", ""
    lines.append((when, "dispatch", "row %d" % r["row"], r["type"] + tag))

for r in load_notes("records/notes_cp1252.csv"):
    when = "%s %s" % (DATE, r["clock"]) if r["clock"] else "UNKNOWN"
    lines.append((when, "notes   ", "row %d" % r["row"], r["note"] + "  <- minute only"))

for when, src, row, what in sorted(lines):
    print(when, "|", src, "|", row, "|", what)

print()
print("Transcript (no real clock, seconds from video start):")
for r in load_vtt("records/bodycam_transcript.vtt"):
    print("  cue %d  %.1f-%.1f s  %s" % (r["row"], r["start"], r["end"], r["text"]))