"""Check report claims against the local record files."""
import argparse
import json
import os
import sys

from claims import extract_claims
from decide import decide_claims
from loaders import load_camera, load_dispatch, load_notes, load_vtt


def load_records(records_dir):
    return (
        load_camera(os.path.join(records_dir, "camera_log.csv"))
        + load_dispatch(os.path.join(records_dir, "dispatch.json"))
        + load_notes(os.path.join(records_dir, "notes_cp1252.csv"))
        + load_vtt(os.path.join(records_dir, "bodycam_transcript.vtt"))
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="path to the incident report")
    parser.add_argument("records_dir", help="directory containing the record files")
    args = parser.parse_args(argv)

    try:
        with open(args.report, "rb") as report_file:
            report = report_file.read().decode("utf-8-sig", errors="replace")
        rows = load_records(args.records_dir)
    except (OSError, ValueError, UnicodeError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2

    output = {"findings": decide_claims(extract_claims(report), rows)}
    json.dump(output, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
