import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from loaders import load_camera, load_vtt


class MalformedRecordTests(unittest.TestCase):
    def test_bad_camera_row_is_skipped(self):
        contents = (
            "#PLEARUN synthetic\n"
            "timestamp,device,speed_mph,zone_mph\n"
            "2026-03-02T21:15:00-05:00,CAM-1,not-a-speed,45\n"
            "2026-03-02T21:16:00-05:00,CAM-1,40,45\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            f.write(contents)
            path = f.name
        try:
            rows = load_camera(path)
        finally:
            os.unlink(path)
        self.assertEqual([row["speed"] for row in rows], [40])

    def test_malformed_vtt_cue_is_skipped(self):
        contents = (
            "WEBVTT\n\n"
            "00:00:xx --> 00:00:02.000\nBad timestamp\n\n"
            "00:00:02.000 --> 00:00:03.000\nGood cue\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            f.write(contents)
            path = f.name
        try:
            rows = load_vtt(path)
        finally:
            os.unlink(path)
        self.assertEqual([row["text"] for row in rows], ["Good cue"])


if __name__ == "__main__":
    unittest.main()
