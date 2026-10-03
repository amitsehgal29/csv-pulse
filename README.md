# csv-pulse

Small command-line profiler for a CSV file. It uses only the Python standard library.

Given a path or stdin, it prints one JSON document with:

- row count and column names
- null/empty count and rate for each column
- distinct count for each column, capped so a wide column cannot grow without bound
- a freshness check for timestamp-like columns: the latest parsed value compared with the current UTC time

A column is treated as a timestamp when its name looks like a date or time field and at least half of its non-empty values parse, or when at least 80% of non-empty values parse as ISO-8601 timestamps. Naive timestamps are read as UTC.

## Usage

```bash
python3 csv_pulse.py sample.csv
```

```bash
python3 csv_pulse.py --distinct-cap 1000 sample.csv
```

```bash
cat sample.csv | python3 csv_pulse.py -
```

Example output for `sample.csv` (the `age_seconds` and `reference_time` fields move with the clock):

```json
{
  "column_names": ["order_id", "region", "amount", "updated_at"],
  "columns": {
    "amount": {
      "distinct_capped": false,
      "distinct_count": 2,
      "null_empty_count": 1,
      "null_empty_rate": 0.25
    },
    "order_id": {
      "distinct_capped": false,
      "distinct_count": 3,
      "null_empty_count": 0,
      "null_empty_rate": 0.0
    },
    "region": {
      "distinct_capped": false,
      "distinct_count": 2,
      "null_empty_count": 1,
      "null_empty_rate": 0.25
    },
    "updated_at": {
      "distinct_capped": false,
      "distinct_count": 2,
      "null_empty_count": 1,
      "null_empty_rate": 0.25
    }
  },
  "freshness": [
    {
      "age_seconds": 1107000.0,
      "column": "updated_at",
      "max_value": "2026-09-20T08:30:00+00:00",
      "parsed_count": 3,
      "reference_time": "2026-10-03T04:00:00+00:00"
    }
  ],
  "row_count": 4
}
```

The numbers above are what the unit test locks in for a fixed reference time of `2026-10-03T04:00:00Z`. A live run uses the current time, so `age_seconds` and `reference_time` will differ.

## Check

```bash
python3 -m unittest test_csv_pulse.py
```
