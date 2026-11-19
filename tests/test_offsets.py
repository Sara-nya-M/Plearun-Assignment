import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from offsets import estimate_offset


class OffsetTests(unittest.TestCase):
    def test_too_few_anchors(self):
        offset, _ = estimate_offset([41.0, 43.0])
        self.assertIsNone(offset)

    def test_consistent_anchors_give_median(self):
        offset, reason = estimate_offset([41.0, 43.0, 40.0])
        self.assertEqual((offset, reason), (41.0, "ok"))

    def test_disagreeing_anchors_rejected(self):
        offset, _ = estimate_offset([41.0, 200.0, 40.0])
        self.assertIsNone(offset)


if __name__ == "__main__":
    unittest.main()