def build_index(rows):
    """Map (file, row) -> raw text, using only rows our loaders produced."""
    index = {}
    for r in rows:
        if r.get("raw") is not None:
            index[(r["file"], r["row"])] = r["raw"]
    return index


def make_finding(claim, verdict, index, file=None, row=None, quote=None):
    """The ONLY place findings are created. Enforces the quote rule."""
    if verdict in ("match", "conflict"):
        raw = index.get((file, row))
        ok = (
            isinstance(quote, str) and quote != ""
            and isinstance(raw, str) and quote in raw
        )
        if ok:
            return {
                "claim": claim,
                "finding": verdict,
                "cite": {"file": file, "row": row},
                "quote": quote,
            }
        verdict = "not_settled"               # downgrade: evidence not verified
    if verdict not in ("not_settled", "not_checkable"):
        verdict = "not_settled"               # unknown verdict word: be safe
    return {"claim": claim, "finding": verdict}   # no cite, no quote