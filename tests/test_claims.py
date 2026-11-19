import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claims import extract_claims, report_date

REPORT = (
    "SYNTHETIC - FICTIONAL CASE. Incident 2026-03-02, Route 21 corridor.  \n"
    "Officer Lee first observed the blue sedan at about 21:14 near mile marker 4, "
    "travelling 58 mph in a posted 45 zone.  \n"
    "The driver pulled into the Harbor Gas lot and stopped around 21:16. "
    "A 911 call reporting the incident was logged at 21:11.  \n"
    "Dispatch records show a unit on scene roughly 2 minutes after the stop. "
    "Officer Lee states the vehicle was the only car in the lane.  \n"
)


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.claims = extract_claims(REPORT)

    def test_six_claims_found(self):
        self.assertEqual(len(self.claims), 6)

    def test_date(self):
        self.assertEqual(report_date(REPORT), "2026-03-02")

    def test_speed_claim(self):
        c = self.claims[1]
        self.assertEqual((c["kind"], c["speed"], c["zone"]), ("speed", 58, 45))

    def test_time_claims(self):
        times = [(c["event"], c["hour"], c["minute"], c["approx"])
                 for c in self.claims if c["kind"] == "time"]
        self.assertEqual(times, [("observation", 21, 14, True),
                                 ("stop", 21, 16, True),
                                 ("911_call", 21, 11, False)])

    def test_interval_claim(self):
        c = self.claims[4]
        self.assertEqual((c["kind"], c["seconds"], c["event"]),
                         ("interval", 120, "unit_on_scene"))

    def test_uncheckable(self):
        self.assertEqual(self.claims[5]["kind"], "uncheckable")

    def test_claim_text_is_from_report(self):
        for c in self.claims:
            self.assertIn(c["claim"], REPORT)


if __name__ == "__main__":
    unittest.main()