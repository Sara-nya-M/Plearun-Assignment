# Verified Findings

Offline CLI that extracts time, speed, and interval claims from a report, loads
the supplied CSV, JSON, and WebVTT records, and emits JSON findings:

```powershell
python plearun_cli.py reports\report_fictional_02.txt records > findings.json
python -m unittest discover -s tests -v
```

Findings with `match` or `conflict` pass through `make_finding`, which checks
that the cited row exists and the quote is an exact substring of its raw text.
Clock offsets are estimated only from at least three unique, exact, unhedged
event-time claims other than the claim being evaluated. The corresponding
record events must be unambiguous and their offsets consistent. Otherwise the
clock is not aligned. Record text is parsed as data and never treated as
instructions.

## Three hardest decisions

1. Avoiding clock alignment based only on timestamps: a timezone does not prove
   that independent devices are synchronized.
2. Requiring event-specific evidence, not merely a matching number or time.
3. Preferring `not_settled` over a potentially false conflict when evidence is
   ambiguous or incomplete.

## Limitations

The claim extraction is pattern-based and will miss varied phrasing. The
decision logic is deliberately conservative, so some true claims remain
unsettled; the sample does not provide enough consistent independent anchors
to align its speed, dispatch, and transcript clocks. On real records, schema
drift and missing or misleading clock anchors would likely break reliable
decisions first.

## Tools

Used Python's standard library and tests, plus Copilot SDK in VS Code for
implementation assistance. Claude was not used.
