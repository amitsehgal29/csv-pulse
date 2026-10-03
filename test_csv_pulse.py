#!/usr/bin/env python3
"""Runnable checks for csv-pulse. Standard library only."""

import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import csv_pulse

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample.csv"
FIXED_NOW = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)


class ProfileTests(unittest.TestCase):
    def test_sample_profile(self) -> None:
        with SAMPLE.open(newline="") as handle:
            document = csv_pulse.profile_source(
                handle, distinct_cap=10, now=FIXED_NOW
            )

        self.assertEqual(document["row_count"], 4)
        self.assertEqual(
            document["column_names"],
            ["order_id", "region", "amount", "updated_at"],
        )
        self.assertEqual(document["columns"]["region"]["null_empty_count"], 1)
        self.assertEqual(document["columns"]["region"]["null_empty_rate"], 0.25)
        self.assertEqual(document["columns"]["amount"]["null_empty_count"], 1)
        self.assertEqual(document["columns"]["order_id"]["distinct_count"], 3)
        self.assertFalse(document["columns"]["order_id"]["distinct_capped"])
        self.assertEqual(len(document["freshness"]), 1)
        freshness = document["freshness"][0]
        self.assertEqual(freshness["column"], "updated_at")
        self.assertEqual(freshness["parsed_count"], 3)
        self.assertEqual(freshness["max_value"], "2026-09-20T08:30:00+00:00")
        self.assertEqual(freshness["age_seconds"], 1107000.0)

    def test_distinct_cap(self) -> None:
        rows = [{"color": name} for name in ("red", "blue", "red", "green")]
        document = csv_pulse.profile_rows(
            ["color"], rows, distinct_cap=2, now=FIXED_NOW
        )
        self.assertEqual(document["columns"]["color"]["distinct_count"], 2)
        self.assertTrue(document["columns"]["color"]["distinct_capped"])
        self.assertEqual(document["freshness"], [])

    def test_cli_on_sample(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "csv_pulse.py"), str(SAMPLE)],
            check=True,
            capture_output=True,
            text=True,
        )
        document = json.loads(completed.stdout)
        self.assertEqual(document["row_count"], 4)
        self.assertIn("updated_at", document["columns"])
        self.assertEqual(document["freshness"][0]["column"], "updated_at")


if __name__ == "__main__":
    unittest.main()
