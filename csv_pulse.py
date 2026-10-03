#!/usr/bin/env python3
"""Profile a CSV: shape, nulls, capped distinct counts, and timestamp freshness."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from typing import Iterable, Mapping, TextIO

DEFAULT_DISTINCT_CAP = 10_000
NAME_HINTS = ("date", "time", "timestamp", "updated", "created", "_at")


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_timestamp(value: str) -> datetime | None:
    """Parse a few common ISO-like timestamps. Naive values are treated as UTC."""
    text = value.strip()
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_timestamp_column(name: str, values: Iterable[str]) -> bool:
    nonempty = [v for v in values if v]
    if not nonempty:
        return False
    parsed = sum(1 for v in nonempty if parse_timestamp(v) is not None)
    ratio = parsed / len(nonempty)
    lowered = name.lower()
    hinted = any(hint in lowered for hint in NAME_HINTS)
    if hinted:
        return ratio >= 0.5 and parsed >= 1
    return ratio >= 0.8 and parsed >= 2


def profile_rows(
    fieldnames: list[str],
    rows: list[Mapping[str, str]],
    *,
    distinct_cap: int = DEFAULT_DISTINCT_CAP,
    now: datetime | None = None,
) -> dict:
    """Build a JSON-serializable profile of already-read CSV rows."""
    if distinct_cap < 1:
        raise ValueError("distinct_cap must be at least 1")
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)

    columns = list(fieldnames)
    null_empty = {name: 0 for name in columns}
    distinct: dict[str, set[str]] = {name: set() for name in columns}
    capped = {name: False for name in columns}
    stored: dict[str, list[str]] = {name: [] for name in columns}

    for row in rows:
        for name in columns:
            value = _clean(row.get(name))
            stored[name].append(value)
            if value == "":
                null_empty[name] += 1
                continue
            seen = distinct[name]
            if value in seen:
                continue
            if len(seen) >= distinct_cap:
                capped[name] = True
                continue
            seen.add(value)

    row_count = len(rows)
    column_stats = {}
    for name in columns:
        count = null_empty[name]
        column_stats[name] = {
            "null_empty_count": count,
            "null_empty_rate": round(count / row_count, 6) if row_count else 0.0,
            "distinct_count": len(distinct[name]),
            "distinct_capped": capped[name],
        }

    freshness = []
    for name in columns:
        values = stored[name]
        if not _is_timestamp_column(name, values):
            continue
        parsed = [ts for value in values if (ts := parse_timestamp(value))]
        if not parsed:
            continue
        latest = max(parsed)
        freshness.append(
            {
                "column": name,
                "parsed_count": len(parsed),
                "max_value": latest.isoformat(),
                "reference_time": reference.isoformat(),
                "age_seconds": round((reference - latest).total_seconds(), 3),
            }
        )

    return {
        "row_count": row_count,
        "column_names": columns,
        "columns": column_stats,
        "freshness": freshness,
    }


def read_csv(source: TextIO) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(source)
    fieldnames = list(reader.fieldnames or [])
    rows = []
    for raw in reader:
        rows.append({name: _clean(raw.get(name)) for name in fieldnames})
    return fieldnames, rows


def profile_source(
    source: TextIO,
    *,
    distinct_cap: int = DEFAULT_DISTINCT_CAP,
    now: datetime | None = None,
) -> dict:
    fieldnames, rows = read_csv(source)
    return profile_rows(fieldnames, rows, distinct_cap=distinct_cap, now=now)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a JSON profile of a CSV (shape, nulls, distincts, freshness)."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="CSV file path. Use '-' or omit the path to read stdin.",
    )
    parser.add_argument(
        "--distinct-cap",
        type=int,
        default=DEFAULT_DISTINCT_CAP,
        help=f"Stop counting new distinct values per column after this many (default {DEFAULT_DISTINCT_CAP}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.distinct_cap < 1:
        parser.error("--distinct-cap must be at least 1")

    path = args.path
    if path in (None, "-"):
        if path is None and sys.stdin.isatty():
            parser.print_help(sys.stderr)
            return 2
        document = profile_source(sys.stdin, distinct_cap=args.distinct_cap)
    else:
        with open(path, newline="") as handle:
            document = profile_source(handle, distinct_cap=args.distinct_cap)

    json.dump(document, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
