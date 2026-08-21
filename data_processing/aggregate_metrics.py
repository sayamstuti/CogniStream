"""
CogniStream - Aggregate Metrics

Runs the flow-state + context-switching-tax logic (Day 9-10) and saves the
final per-developer summary into a new ClickHouse table. This way, the
FastAPI backend (Day 12) can just read pre-computed numbers instantly,
instead of re-running the whole algorithm on every request.
"""

import polars as pl
from flow_state_detection import get_client, fetch_vscode_sessions, merge_into_flow_blocks
from context_switching_tax import fetch_slack_events, count_interruptions


def create_summary_table(client):
    """Fresh table each time we aggregate -- drop and recreate so old
    numbers never linger if the underlying data changes."""
    client.command("DROP TABLE IF EXISTS dev_metrics_summary")
    client.command("""
        CREATE TABLE dev_metrics_summary (
            dev String,
            flow_block_count UInt32,
            total_flow_minutes Float64,
            total_interruptions UInt32,
            ci_cd_interruptions UInt32,
            ci_cd_tax_pct Float64
        ) ENGINE = MergeTree()
        ORDER BY dev
    """)


def build_summary(flow_blocks, tax_df):
    """
    One row per developer with the numbers that matter for the dashboard:
    how much flow time they got, how many interruptions hit it, and what
    percentage of their flow blocks were broken by a CI/CD alert
    specifically (the "tax" the problem statement is about).
    """
    block_counts = (
        flow_blocks.group_by("dev")
        .agg(pl.len().alias("flow_block_count"))
    )

    tax_summary = (
        tax_df.group_by("dev")
        .agg([
            pl.col("duration_minutes").sum().alias("total_flow_minutes"),
            pl.col("total_interruptions").sum().alias("total_interruptions"),
            pl.col("ci_cd_interruptions").sum().alias("ci_cd_interruptions"),
        ])
    )

    summary = block_counts.join(tax_summary, on="dev")

    # What % of this dev's flow blocks were hit by at least one CI/CD alert
    ci_cd_hit_blocks = (
        tax_df.filter(pl.col("ci_cd_interruptions") > 0)
        .group_by("dev")
        .agg(pl.len().alias("blocks_hit"))
    )
    summary = summary.join(ci_cd_hit_blocks, on="dev", how="left").fill_null(0)
    summary = summary.with_columns(
        (pl.col("blocks_hit") / pl.col("flow_block_count") * 100)
        .round(1)
        .alias("ci_cd_tax_pct")
    ).drop("blocks_hit")

    return summary


def main():
    client = get_client()

    sessions_df = fetch_vscode_sessions(client)
    blocks_df = merge_into_flow_blocks(sessions_df)
    flow_blocks = blocks_df.filter(pl.col("is_flow_state"))

    slack_events = fetch_slack_events(client)
    tax_df = count_interruptions(flow_blocks, slack_events)

    summary = build_summary(flow_blocks, tax_df)
    print("Final aggregated summary:\n")
    print(summary)

    create_summary_table(client)

    rows = [
        [r["dev"], r["flow_block_count"], r["total_flow_minutes"],
         r["total_interruptions"], r["ci_cd_interruptions"], r["ci_cd_tax_pct"]]
        for r in summary.iter_rows(named=True)
    ]
    client.insert(
        "dev_metrics_summary", rows,
        column_names=["dev", "flow_block_count", "total_flow_minutes",
                      "total_interruptions", "ci_cd_interruptions", "ci_cd_tax_pct"],
    )
    print(f"\nSaved {len(rows)} rows into dev_metrics_summary table.")


if __name__ == "__main__":
    main()