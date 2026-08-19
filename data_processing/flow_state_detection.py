"""
CogniStream - Flow-State Detection

Reads VSCode coding sessions from ClickHouse and merges consecutive
sessions (with small gaps) into continuous "flow blocks." A block counts
as genuine flow state if the total merged duration is 90+ minutes -- this
is the core metric the whole project is built around.
"""

import polars as pl
import clickhouse_connect

MAX_GAP_MINUTES = 15     # gaps this small or smaller get merged together
FLOW_THRESHOLD_MINUTES = 60 # merged blocks this long count as "flow state"


def get_client():
    return clickhouse_connect.get_client(
        host="localhost", port=8123,
        username="cognistream", password="cognistream",
        database="cognistream",
    )


def fetch_vscode_sessions(client):
    """Pull all VSCode sessions, ordered so each dev's sessions are in
    time order -- required before we can merge consecutive ones."""
    result = client.query(
        "SELECT dev, timestamp, end_timestamp FROM dev_events "
        "WHERE source = 'vscode' ORDER BY dev, timestamp"
    )
    return pl.DataFrame(
        result.result_rows,
        schema=["dev", "start", "end"],
        orient="row",
    )


def merge_into_flow_blocks(sessions_df):
    """
    Walk through each dev's sessions in order. Keep extending the current
    block as long as the gap to the next session is small. Once the gap
    is too big, close out the current block and start a new one.
    """
    blocks = []

    for dev in sessions_df["dev"].unique():
        dev_sessions = sessions_df.filter(pl.col("dev") == dev).sort("start")

        block_start = None
        block_end = None

        for row in dev_sessions.iter_rows(named=True):
            if block_start is None:
                # first session of a new block
                block_start, block_end = row["start"], row["end"]
                continue

            gap_minutes = (row["start"] - block_end).total_seconds() / 60

            if gap_minutes <= MAX_GAP_MINUTES:
                # small gap -- extend the current block
                block_end = row["end"]
            else:
                # gap too big -- close the current block, start a new one
                blocks.append(_make_block(dev, block_start, block_end))
                block_start, block_end = row["start"], row["end"]

        if block_start is not None:
            blocks.append(_make_block(dev, block_start, block_end))

    return pl.DataFrame(blocks)


def _make_block(dev, start, end):
    duration = (end - start).total_seconds() / 60
    return {
        "dev": dev,
        "block_start": start,
        "block_end": end,
        "duration_minutes": round(duration, 1),
        "is_flow_state": duration >= FLOW_THRESHOLD_MINUTES,
    }


def main():
    client = get_client()
    sessions_df = fetch_vscode_sessions(client)
    print(f"Loaded {len(sessions_df)} VSCode sessions")

    blocks_df = merge_into_flow_blocks(sessions_df)
    print(f"Merged into {len(blocks_df)} continuous blocks")

    flow_blocks = blocks_df.filter(pl.col("is_flow_state"))
    print(f"\n{len(flow_blocks)} blocks qualify as flow state (90+ min):\n")
    print(flow_blocks)

    # Per-dev summary -- total flow-state minutes each dev achieved.
    summary = (
        flow_blocks.group_by("dev")
        .agg(pl.col("duration_minutes").sum().alias("total_flow_minutes"))
        .sort("total_flow_minutes", descending=True)
    )
    print("\nFlow-state totals per developer:")
    print(summary)


if __name__ == "__main__":
    main()