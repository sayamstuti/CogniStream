"""
test_flow_detection.py
Sanity-checks detect_flow_blocks / tag_interruptions / compute_interruption_tax
against small synthetic tables shaped exactly like Sayam's generate_mock_data.py
output (after passing through the updated load_data.py normalization) - no
ClickHouse needed.

Run: python test_flow_detection.py
"""

import json
from datetime import datetime, timedelta

import polars as pl

from flow_detection import detect_flow_blocks, tag_interruptions, compute_interruption_tax

BASE = datetime(2026, 8, 10, 9, 0, 0)


def vscode_row(user, start, minutes, day_offset=0):
    s = BASE + timedelta(days=day_offset, minutes=start)
    e = s + timedelta(minutes=minutes)
    return {
        "user_id": user,
        "timestamp": s,
        "metadata": json.dumps({"end": e.isoformat(), "duration_minutes": minutes}),
    }


def build_synthetic_data():
    # dev_amit: three sessions with small gaps (<=20 min) that should MERGE into
    # one long flow block: 0-40, 45-90 (gap 5), 95-140 (gap 5) => 0 to 140 = 140 min.
    amit_sessions = [
        vscode_row("dev_amit", 0, 40),
        vscode_row("dev_amit", 45, 45),   # starts at 45, prev ended at 40 -> gap 5
        vscode_row("dev_amit", 95, 45),   # starts at 95, prev ended at 90 -> gap 5
    ]

    # dev_riya: one session then a LONG gap (30 min, over tolerance) then another
    # session -> should NOT merge, and neither piece alone hits 90 min.
    riya_sessions = [
        vscode_row("dev_riya", 0, 60),
        vscode_row("dev_riya", 90, 60),  # gap = 90-60 = 30 min > tolerance
    ]

    vscode_events = pl.DataFrame(amit_sessions + riya_sessions)

    # dev_amit's merged block ends at BASE+140min. Put a ci_cd_alert 5 min later.
    block_end = BASE + timedelta(minutes=140)
    other_events = pl.DataFrame(
        [
            {
                "user_id": "dev_amit",
                "timestamp": block_end + timedelta(minutes=5),
                "source": "slack",
                "event_type": "ci_cd_alert",
            },
            {
                "user_id": "dev_amit",
                "timestamp": block_end + timedelta(hours=5),  # way outside window, ignored
                "source": "slack",
                "event_type": "message",
            },
        ]
    )
    return vscode_events, other_events


def main():
    vscode_events, other_events = build_synthetic_data()

    blocks = detect_flow_blocks(vscode_events)
    print("=== Detected Flow Blocks (>=90 min, sessions merged) ===")
    print(blocks)

    assert blocks.height == 1, "expected exactly 1 flow block (dev_amit's merged 140min); dev_riya's two 60min sessions must NOT qualify"
    assert blocks["user_id"][0] == "dev_amit"
    assert abs(blocks["duration_minutes"][0] - 140) < 0.01, "dev_amit's 3 sessions should merge into a single 140-minute block"

    tagged = tag_interruptions(blocks, other_events)
    print("\n=== Tagged Interruptions ===")
    print(tagged)
    assert tagged["interrupted_by_detail"][0] == "ci_cd_alert"

    tax = compute_interruption_tax(tagged)
    print("\n=== Interruption Tax Breakdown (% of flow minutes) ===")
    print(tax)
    assert tax.get("ci_cd_alert") == 100.0, "the only block we have should be 100% attributed to the ci_cd alert"

    print("\nAll assertions passed - session-merging + interrupt tagging both work correctly.")


if __name__ == "__main__":
    main()
