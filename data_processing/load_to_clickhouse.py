"""
CogniStream - ClickHouse Loader

Reads the JSON files our generator created and loads them into ClickHouse's
`dev_events` table. Each source (Slack/GitHub/Jira/VSCode) has slightly
different fields, so this script's main job is reshaping each one into the
SAME 6-column format the table expects, before inserting.
"""

import json
from datetime import datetime
import polars as pl
import clickhouse_connect

# Every source has one "extra" field that's unique to it -- this map tells
# us which field to grab for each source, so we can stuff it into the
# generic `extra_field` column.
EXTRA_FIELD_MAP = {
    "slack": "channel",
    "github": "repo",
    "jira": "ticket_id",
}

COLUMNS = ["source", "dev", "event_type", "timestamp", "end_timestamp", "extra_field"]


def load_json(filename):
    with open(f"../data_ingestion/{filename}") as f:
        return json.load(f)


def reshape_source(source, events):
    """
    Turn a list of raw event dicts (different shape per source) into rows
    matching our ClickHouse table: source, dev, event_type, timestamp,
    end_timestamp, extra_field.
    """
    rows = []
    for e in events:
        rows.append({
            "source": source,
            "dev": e["dev"],
            "event_type": e["event_type"],
            # VSCode events use "start" instead of "timestamp" -- treat
            # start-of-session as the main timestamp.
            "timestamp": e.get("timestamp") or e.get("start"),
            "end_timestamp": e.get("end"),  # only VSCode events have this
            "extra_field": str(e.get(EXTRA_FIELD_MAP.get(source, ""), "")),
        })
    return rows


def main():
    sources = {
        "vscode": "vscode_events.json",
        "slack": "slack_events.json",
        "github": "github_events.json",
        "jira": "jira_events.json",
    }

    all_rows = []
    for source, filename in sources.items():
        events = load_json(filename)
        all_rows.extend(reshape_source(source, events))
        print(f"Reshaped {len(events)} events from {filename}")

    # Polars DataFrame is just used here to preview/sanity-check the shape --
    # the actual insert below uses plain rows, since ClickHouse's insert_df
    # expects a pandas DataFrame, not a Polars one.
    df = pl.DataFrame(all_rows)
    print(df.head())

    # Convert each row-dict into a plain list matching COLUMNS order, and
    # turn timestamp strings into real datetime objects (ClickHouse's
    # DateTime column needs actual datetimes, not raw strings).
    data = []
    for row in all_rows:
        data.append([
            row["source"],
            row["dev"],
            row["event_type"],
            datetime.fromisoformat(row["timestamp"]),
            datetime.fromisoformat(row["end_timestamp"]) if row["end_timestamp"] else None,
            row["extra_field"],
        ])

    # Connect to ClickHouse (matches the credentials in docker-compose.yaml)
    client = clickhouse_connect.get_client(
        host="localhost", port=8123,
        username="cognistream", password="cognistream",
        database="cognistream",
    )

    client.insert("dev_events", data, column_names=COLUMNS)
    print(f"Loaded {len(data)} total rows into ClickHouse.")


if __name__ == "__main__":
    main()