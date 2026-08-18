

from __future__ import annotations

import json
import os
from typing import Optional

import polars as pl
import pymysql

FLOW_BLOCK_MIN_MINUTES = 90
IDE_GAP_TOLERANCE_MINUTES = 20        # breaks up to 20 min don't end a flow attempt
INTERRUPTION_WINDOW_MINUTES = 15      # look 15 min after a block ends for the cause

SLACK_HUMAN_TYPES = {"message", "mention"}

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "neel1405")
MYSQL_DB = os.getenv("MYSQL_DB", "cognistream")


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


# --------------------------------------------------------------------------------
# Step 1 + 2: merge session intervals, keep only >= 90 min merged blocks
# --------------------------------------------------------------------------------
def detect_flow_blocks(vscode_events: pl.DataFrame) -> pl.DataFrame:
    """
    vscode_events: DataFrame with columns [user_id, timestamp, metadata] where
    `timestamp` is a session's start and `metadata` is the JSON string
    {"end": ..., "duration_minutes": ...} (as written by load_data.clean_vscode).

    Returns one row per Flow Block: [user_id, block_start, block_end, duration_minutes]
    """
    if vscode_events.height == 0:
        return pl.DataFrame(
            schema={"user_id": pl.Utf8, "block_start": pl.Datetime, "block_end": pl.Datetime, "duration_minutes": pl.Float64}
        )

    df = vscode_events.with_columns(
        pl.col("metadata")
        .map_elements(lambda m: json.loads(m)["end"], return_dtype=pl.Utf8)
        .str.to_datetime()
        .alias("session_end")
    ).rename({"timestamp": "session_start"})

    df = df.sort(["user_id", "session_start"])

    # Running max of session_end seen so far within the same user, shifted by
    # one row - i.e. "the furthest this flow attempt has reached before this
    # session started". A new block starts when this session's start is more
    # than IDE_GAP_TOLERANCE_MINUTES past that running end.
    df = df.with_columns(
        pl.col("session_end").cum_max().shift(1).over("user_id").alias("running_end")
    )

    df = df.with_columns(
        (
            pl.col("running_end").is_null()
            | (
                (pl.col("session_start") - pl.col("running_end")).dt.total_minutes()
                > IDE_GAP_TOLERANCE_MINUTES
            )
        )
        .cum_sum()
        .over("user_id")
        .alias("block_id")
    )

    blocks = (
        df.group_by(["user_id", "block_id"])
        .agg(
            pl.col("session_start").min().alias("block_start"),
            pl.col("session_end").max().alias("block_end"),
        )
        .with_columns(
            ((pl.col("block_end") - pl.col("block_start")).dt.total_seconds() / 60.0)
            .alias("duration_minutes")
        )
        .filter(pl.col("duration_minutes") >= FLOW_BLOCK_MIN_MINUTES)
        .drop("block_id")
        .sort(["user_id", "block_start"])
    )

    return blocks


# --------------------------------------------------------------------------------
# Step 3: tag each block with what interrupted it, via an asof join
# --------------------------------------------------------------------------------
def tag_interruptions(flow_blocks: pl.DataFrame, other_events: pl.DataFrame) -> pl.DataFrame:
    """
    other_events: DataFrame of non-vscode events with columns
        [user_id, timestamp, source, event_type]

    For each flow block, finds the earliest qualifying event within
    INTERRUPTION_WINDOW_MINUTES after block_end, per user, via a forward
    asof join.
    """
    if flow_blocks.height == 0 or other_events.height == 0:
        return flow_blocks.with_columns(
            pl.lit(None).cast(pl.Utf8).alias("interrupted_by_source"),
            pl.lit(None).cast(pl.Utf8).alias("interrupted_by_detail"),
        )

    def classify(row) -> Optional[str]:
        if row["source"] == "slack":
            return "ci_cd_alert" if row["event_type"] == "ci_cd_alert" else (
                "human_message" if row["event_type"] in SLACK_HUMAN_TYPES else None
            )
        if row["source"] == "jira":
            return "jira_activity"
        return None  # github activity doesn't count as an "interruption" source

    events = other_events.with_columns(
        pl.struct(["source", "event_type"])
        .map_elements(classify, return_dtype=pl.Utf8)
        .alias("interrupted_by_detail")
    ).with_columns(pl.col("source").alias("interrupted_by_source"))

    events = events.filter(pl.col("interrupted_by_detail").is_not_null())
    events = events.sort(["user_id", "timestamp"])

    blocks = flow_blocks.sort(["user_id", "block_end"])

    tagged = blocks.join_asof(
        events.select(["user_id", "timestamp", "interrupted_by_source", "interrupted_by_detail"]),
        left_on="block_end",
        right_on="timestamp",
        by="user_id",
        strategy="forward",
    )

    within_window = (
        (pl.col("timestamp") - pl.col("block_end")).dt.total_minutes() <= INTERRUPTION_WINDOW_MINUTES
    )
    tagged = tagged.with_columns(
        pl.when(within_window).then(pl.col("interrupted_by_source")).otherwise(None).alias("interrupted_by_source"),
        pl.when(within_window).then(pl.col("interrupted_by_detail")).otherwise(None).alias("interrupted_by_detail"),
    ).drop("timestamp")

    return tagged


# --------------------------------------------------------------------------------
# Headline metric: the "Context-Switching Tax"
# --------------------------------------------------------------------------------
def compute_interruption_tax(tagged_blocks: pl.DataFrame) -> dict:
    """
    % of total flow-block minutes cut short by each interrupt category, e.g.
        {"ci_cd_alert": 40.2, "human_message": 12.1, "jira_activity": 3.4, "none": 44.3}
    """
    if tagged_blocks.height == 0:
        return {}

    total_minutes = tagged_blocks["duration_minutes"].sum()

    breakdown = (
        tagged_blocks.with_columns(
            pl.col("interrupted_by_detail").fill_null("none").alias("bucket")
        )
        .group_by("bucket")
        .agg(pl.col("duration_minutes").sum().alias("minutes"))
        .with_columns((pl.col("minutes") / total_minutes * 100).round(1).alias("pct"))
    )

    return dict(zip(breakdown["bucket"].to_list(), breakdown["pct"].to_list()))


# --------------------------------------------------------------------------------
# MySQL I/O: pull raw events, run the algorithm, write flow_blocks back
# --------------------------------------------------------------------------------
def _fetch_df(conn, sql: str, columns: list[str]) -> pl.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    if not rows:
        return pl.DataFrame(schema={c: pl.Utf8 for c in columns})
    return pl.DataFrame(rows, schema=columns, orient="row")


def run_flow_detection():
    conn = _get_connection()
    try:
        vscode_events = _fetch_df(
            conn,
            "SELECT user_id, `timestamp`, metadata FROM events WHERE source = 'vscode'",
            ["user_id", "timestamp", "metadata"],
        )
        other_events = _fetch_df(
            conn,
            "SELECT user_id, `timestamp`, source, event_type FROM events WHERE source != 'vscode'",
            ["user_id", "timestamp", "source", "event_type"],
        )

        blocks = detect_flow_blocks(vscode_events)
        tagged = tag_interruptions(blocks, other_events)
        tax = compute_interruption_tax(tagged)
        print(f"[flow_detection] interruption tax breakdown: {tax}")

        if tagged.height > 0:
            insert_df = tagged.with_columns(
                (pl.col("user_id") + "_" + pl.col("block_start").dt.strftime("%Y%m%dT%H%M%S")).alias("block_id")
            )
            rows = insert_df.select(
                ["block_id", "user_id", "block_start", "block_end", "duration_minutes",
                 "interrupted_by_source", "interrupted_by_detail"]
            ).rows()

            sql = """
                INSERT INTO flow_blocks
                    (block_id, user_id, block_start, block_end, duration_minutes,
                     interrupted_by_source, interrupted_by_detail)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    duration_minutes = VALUES(duration_minutes),
                    interrupted_by_source = VALUES(interrupted_by_source),
                    interrupted_by_detail = VALUES(interrupted_by_detail)
            """
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()
            print(f"[flow_detection] wrote {len(rows)} flow blocks to cognistream.flow_blocks")

        return tagged, tax
    finally:
        conn.close()


if __name__ == "__main__":
    run_flow_detection()
