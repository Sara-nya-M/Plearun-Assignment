import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from findings import build_index, make_finding

ROWS = [{"file": "notes.csv", "row": 4, "raw": 'N-3,Officer Lee,Stopped at lot ~21:16,21:16'}]
INDEX = build_index(ROWS)


class GateTests(unittest.TestCase):
    def test_good_quote_is_kept(self):
        f = make_finding("c", "match", INDEX, "notes.csv", 4, "Stopped at lot ~21:16")
        self.assertEqual(f["finding"], "match")
        self.assertEqual(f["cite"], {"file": "notes.csv", "row": 4})

    def test_quote_not_in_row_is_downgraded(self):
        f = make_finding("c", "conflict", INDEX, "notes.csv", 4, "Stopped at lot 21:20")
        self.assertEqual(f, {"claim": "c", "finding": "not_settled"})

    def test_missing_row_is_downgraded(self):
        f = make_finding("c", "match", INDEX, "notes.csv", 99, "Stopped")
        self.assertEqual(f["finding"], "not_settled")

    def test_empty_or_none_quote_is_downgraded(self):
        for q in ("", None):
            f = make_finding("c", "match", INDEX, "notes.csv", 4, q)
            self.assertEqual(f["finding"], "not_settled")

    def test_not_settled_has_no_cite_or_quote(self):
        f = make_finding("c", "not_checkable", INDEX, "notes.csv", 4, "Stopped")
        self.assertEqual(f, {"claim": "c", "finding": "not_checkable"})


if __name__ == "__main__":
    unittest.main()