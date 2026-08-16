"""
CogniStream - Pipeline Validation

Runs a handful of sanity checks against the ClickHouse `dev_events` table
to confirm the ingestion pipeline actually worked correctly -- not just
that it ran without crashing. Each check prints PASS or FAIL, so this can
be re-run any time to confirm the pipeline's health.
"""

import clickhouse_connect

EXPECTED_SOURCES = {"vscode", "slack", "github", "jira"}
EXPECTED_DEVS = {"dev_amit", "dev_riya", "dev_sam"}


def get_client():
    return clickhouse_connect.get_client(
        host="localhost", port=8123,
        username="cognistream", password="cognistream",
        database="cognistream",
    )


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    return condition


def main():
    client = get_client()
    all_passed = True

    # Check 1: table isn't empty
    total = client.query("SELECT count() FROM dev_events").result_rows[0][0]
    all_passed &= check(f"Table has data (found {total} rows)", total > 0)

    # Check 2: every expected source is present, none missing
    sources = {row[0] for row in client.query(
        "SELECT DISTINCT source FROM dev_events"
    ).result_rows}
    all_passed &= check(
        f"All 4 sources present (found: {sources})",
        sources == EXPECTED_SOURCES,
    )

    # Check 3: every expected dev shows up in the data
    devs = {row[0] for row in client.query(
        "SELECT DISTINCT dev FROM dev_events"
    ).result_rows}
    all_passed &= check(
        f"All 3 devs present (found: {devs})",
        devs == EXPECTED_DEVS,
    )

    # Check 4: no source has suspiciously few rows (e.g. failed to load)
    counts = dict(client.query(
        "SELECT source, count() FROM dev_events GROUP BY source"
    ).result_rows)
    all_passed &= check(
        f"No source has 0 rows (counts: {counts})",
        all(c > 0 for c in counts.values()),
    )

    # Check 5: no null/missing timestamps (critical -- flow-state logic
    # depends entirely on accurate timestamps)
    null_timestamps = client.query(
        "SELECT count() FROM dev_events WHERE timestamp IS NULL"
    ).result_rows[0][0]
    all_passed &= check(
        "No missing timestamps",
        null_timestamps == 0,
    )

    # Check 6: vscode sessions have a valid end_timestamp AFTER their start
    bad_sessions = client.query(
        "SELECT count() FROM dev_events "
        "WHERE source = 'vscode' AND end_timestamp <= timestamp"
    ).result_rows[0][0]
    all_passed &= check(
        "All vscode sessions end after they start",
        bad_sessions == 0,
    )

    print("\n" + ("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"))


if __name__ == "__main__":
    main()