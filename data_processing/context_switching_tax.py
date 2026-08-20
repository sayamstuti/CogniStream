"""
CogniStream - Context-Switching Tax

Cross-references flow-state blocks (from flow_state_detection.py) against
Slack events to measure how many interruptions -- especially CI/CD alerts
-- land inside a developer's flow state. This is the project's headline
metric: how much focused time is being "taxed" by notifications.
"""

import polars as pl
import clickhouse_connect
from flow_state_detection import (
    get_client, fetch_vscode_sessions, merge_into_flow_blocks,
)


def fetch_slack_events(client):
    """Pull all Slack events -- we care about WHEN they happened and
    what type, so we can check if they land inside a flow block."""
    result = client.query(
        "SELECT dev, event_type, timestamp FROM dev_events "
        "WHERE source = 'slack' ORDER BY dev, timestamp"
    )
    return pl.DataFrame(
        result.result_rows, schema=["dev", "event_type", "timestamp"], orient="row"
    )


def count_interruptions(flow_blocks, slack_events):
    """
    For each flow block, count how many Slack messages landed inside it
    (between block_start and block_end), split into total interruptions
    vs. specifically CI/CD alerts (the noisiest, most avoidable kind).
    """
    results = []

    for block in flow_blocks.iter_rows(named=True):
        dev_slack = slack_events.filter(pl.col("dev") == block["dev"])

        inside_block = dev_slack.filter(
            (pl.col("timestamp") >= block["block_start"])
            & (pl.col("timestamp") <= block["block_end"])
        )

        ci_cd_count = inside_block.filter(
            pl.col("event_type") == "ci_cd_alert"
        ).height

        results.append({
            "dev": block["dev"],
            "block_start": block["block_start"],
            "duration_minutes": block["duration_minutes"],
            "total_interruptions": inside_block.height,
            "ci_cd_interruptions": ci_cd_count,
        })

    return pl.DataFrame(results)


def main():
    client = get_client()

    sessions_df = fetch_vscode_sessions(client)
    blocks_df = merge_into_flow_blocks(sessions_df)
    flow_blocks = blocks_df.filter(pl.col("is_flow_state"))
    print(f"Analyzing {len(flow_blocks)} flow-state blocks...")

    slack_events = fetch_slack_events(client)

    tax_df = count_interruptions(flow_blocks, slack_events)
    print("\nInterruptions per flow block:\n")
    print(tax_df)

    # Per-dev summary -- the actual "Context-Switching Tax" headline numbers.
    summary = (
        tax_df.group_by("dev")
        .agg([
            pl.col("duration_minutes").sum().alias("total_flow_minutes"),
            pl.col("total_interruptions").sum().alias("total_interruptions"),
            pl.col("ci_cd_interruptions").sum().alias("ci_cd_interruptions"),
        ])
        .sort("ci_cd_interruptions", descending=True)
    )
    print("\nContext-Switching Tax summary per developer:")
    print(summary)


if __name__ == "__main__":
    main()