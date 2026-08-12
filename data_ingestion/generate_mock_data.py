"""
CogniStream - Mock Data Generator

We don't have access to real GitHub/Slack/Jira/VSCode accounts, so this
script fakes a realistic WEEK of developer activity instead. Later scripts
(Airflow, ClickHouse, Polars) will treat this fake data exactly like it
came from a real API pull.
"""

import json
import random
from datetime import datetime, timedelta

# Fixing the random seed means every time we run this script, we get the
# SAME fake data. Useful while building/debugging, so results don't change
# on every run and confuse us.
random.seed(42)

DEVS = ["dev_amit", "dev_riya", "dev_sam"]

# Generate data for a work week instead of just one day, so later on we can
# spot patterns across multiple days (e.g. "flow state is worst on Mondays").
NUM_DAYS = 5
START_DATE = datetime(2026, 8, 10, 9, 0)  # first workday, 9 AM


def random_time(day_start):
    """Pick a random moment sometime during an 8-hour workday."""
    return day_start + timedelta(minutes=random.randint(0, 8 * 60))


def make_events(source, event_types, extra_field, day_start, n):
    """
    Slack messages, GitHub commits, and Jira ticket updates all follow the
    same basic shape: someone (a dev) did something (event_type) at some
    time. So instead of writing three almost-identical functions, we write
    this ONE generic function and just plug in what's different each time
    (the source name, the possible event types, and one extra field that's
    unique to that source, like "channel" for Slack or "repo" for GitHub).
    """
    return [{
        "source": source,
        "dev": random.choice(DEVS),
        "event_type": random.choice(event_types),
        "timestamp": random_time(day_start).isoformat(),
        **extra_field(),  # bolt on the one extra field specific to this source
    } for _ in range(n)]


def make_vscode_sessions(day_start, n=40):
    """
    VSCode activity is different from the others — it's not a single
    moment, it's a BLOCK of time (start coding -> stop coding). This is
    the data we'll later use to detect "flow state," so it needs a
    start and end timestamp, not just one timestamp like the others.
    """
    events, t = [], day_start

    for _ in range(n):
        duration = random.randint(5, 45)  # length of this coding burst

        events.append({
            "source": "vscode",
            "dev": random.choice(DEVS),
            "event_type": "coding_active",
            "start": t.isoformat(),
            "end": (t := t + timedelta(minutes=duration)).isoformat(),
        })

        # Short break before the next coding session starts.
        t += timedelta(minutes=random.randint(1, 20))

        # Stop once we've gone past 5 PM (end of an 8-hour day).
        if t.hour >= 17:
            break

    return events


def generate_one_day(day_start):
    """Generate one full day's worth of events across all four sources."""
    return {
        "vscode": make_vscode_sessions(day_start),
        "slack": make_events(
            "slack",
            ["message", "message", "ci_cd_alert", "ci_cd_alert", "mention"],
            lambda: {"channel": random.choice(["#deploys", "#team-eng", "#alerts"])},
            day_start, n=25,
        ),
        "github": make_events(
            "github", ["commit", "pr_opened", "pr_review"],
            lambda: {"repo": "cognistream-app"}, day_start, n=8,
        ),
        "jira": make_events(
            "jira", ["ticket_moved", "ticket_commented"],
            lambda: {"ticket_id": f"COG-{random.randint(100, 199)}"}, day_start, n=5,
        ),
    }


def main():
    """
    Loop over NUM_DAYS workdays, generate each day's events, and merge
    everything from the same source together into one file. So instead of
    one vscode file per day, we get ONE vscode_events.json that spans the
    whole week — same as how a real week-long API pull would look.
    """
    combined = {"vscode": [], "slack": [], "github": [], "jira": []}

    for day_offset in range(NUM_DAYS):
        day_start = START_DATE + timedelta(days=day_offset)
        one_day = generate_one_day(day_start)
        for source in combined:
            combined[source].extend(one_day[source])

    for source, events in combined.items():
        filename = f"{source}_events.json"
        with open(filename, "w") as f:
            json.dump(events, f, indent=2)
        print(f"Generated {filename}: {len(events)} events across {NUM_DAYS} days")


if __name__ == "__main__":
    main()