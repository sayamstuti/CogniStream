

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import polars as pl
import pymysql

# Where generate_mock_data.py writes its {source}_events.json files.
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "."))
SOURCES = ["vscode", "slack", "github", "jira"]

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "neel1405")
MYSQL_DB = os.getenv("MYSQL_DB", "cognistream")

BATCH_SIZE = 1000  # rows per executemany() batch


def _get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        autocommit=False,
    )


def _load_json_array(path: Path) -> list[dict]:
    if not path.exists():
        print(f"[load_data] WARNING: {path} not found, skipping")
        return []
    with open(path) as f:
        return json.load(f)


def _empty_events_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "event_id": pl.Utf8, "source": pl.Utf8, "event_type": pl.Utf8,
            "user_id": pl.Utf8, "timestamp": pl.Datetime("us"),
            "repo": pl.Utf8, "metadata": pl.Utf8,
        }
    )


def clean_vscode(records: list[dict]) -> pl.DataFrame:
    """
    vscode records: {"source": "vscode", "dev": "dev_amit",
    "event_type": "coding_active", "start": ..., "end": ...}
    """
    if not records:
        return _empty_events_df()

    rows = []
    for r in records:
        start_dt = datetime.fromisoformat(r["start"])
        end_dt = datetime.fromisoformat(r["end"])
        duration_min = round((end_dt - start_dt).total_seconds() / 60.0, 2)
        rows.append(
            {
                "event_id": str(uuid.uuid4()),
                "source": "vscode",
                "event_type": r["event_type"],
                "user_id": r["dev"],
                "timestamp": r["start"],
                "repo": None,
                "metadata": json.dumps({"end": r["end"], "duration_minutes": duration_min}),
            }
        )
    return pl.DataFrame(rows).with_columns(
        pl.col("timestamp").str.to_datetime(),
        pl.col("repo").cast(pl.Utf8),  # all-None column would otherwise infer as Null dtype
    )


def clean_flat_source(records: list[dict], source: str, repo_key: str | None) -> pl.DataFrame:
    """
    Handles slack / github / jira, which share the shape:
        {"source": ..., "dev": ..., "event_type": ..., "timestamp": ..., <extra field>}
    """
    if not records:
        return _empty_events_df()

    rows = []
    for r in records:
        extra = {k: v for k, v in r.items() if k not in {"source", "dev", "event_type", "timestamp"}}
        rows.append(
            {
                "event_id": str(uuid.uuid4()),
                "source": source,
                "event_type": r["event_type"],
                "user_id": r["dev"],
                "timestamp": r["timestamp"],
                "repo": r.get(repo_key) if repo_key else None,
                "metadata": json.dumps(extra),
            }
        )
    return pl.DataFrame(rows).with_columns(
        pl.col("timestamp").str.to_datetime(),
        pl.col("repo").cast(pl.Utf8),  # jira has no repo_key -> all-None column, same fix as above
    )


def _insert_batch(conn, df: pl.DataFrame) -> int:
    if df.height == 0:
        return 0

    sql = """
        INSERT INTO events (event_id, source, event_type, user_id, `timestamp`, repo, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    rows = df.select(
        ["event_id", "source", "event_type", "user_id", "timestamp", "repo", "metadata"]
    ).rows()

    inserted = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            cur.executemany(sql, batch)
            inserted += len(batch)
    conn.commit()
    return inserted


def load_all_sources() -> int:
    """
    Reads the four {source}_events.json files, normalizes each into the
    shared events schema, and batch-inserts into MySQL. Returns total rows
    inserted.

    Note: generate_mock_data.py regenerates the SAME deterministic week every
    run (random.seed(42)). Since a fresh UUID is generated per row on every
    load, re-running this against the same files WILL create duplicate rows
    in MySQL - truncate `events` before re-loading during testing, or hash
    the row's real content into a deterministic id if you want re-runs to be
    naturally idempotent.
    """
    frames = [
        clean_vscode(_load_json_array(RAW_DATA_DIR / "vscode_events.json")),
        clean_flat_source(_load_json_array(RAW_DATA_DIR / "slack_events.json"), "slack", "channel"),
        clean_flat_source(_load_json_array(RAW_DATA_DIR / "github_events.json"), "github", "repo"),
        clean_flat_source(_load_json_array(RAW_DATA_DIR / "jira_events.json"), "jira", None),
    ]

    for source, df in zip(SOURCES, frames):
        print(f"[load_data] {source}: {df.height} cleaned rows")

    combined = pl.concat(frames, how="vertical")
    if combined.height == 0:
        print("[load_data] nothing to load")
        return 0

    conn = _get_connection()
    try:
        inserted = _insert_batch(conn, combined)
        print(f"[load_data] inserted {inserted} rows into cognistream.events")
        return inserted
    finally:
        conn.close()


if __name__ == "__main__":
    load_all_sources()
