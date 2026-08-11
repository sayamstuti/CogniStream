"""
CogniStream - Mock Data Generator

We don't have access to real GitHub/Slack/Jira/VSCode accounts, so this
script fakes a realistic day of developer activity instead. Later scripts
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

# Pretend the workday starts at 9 AM on Aug 10, 2026.
DAY = datetime(2026, 8, 10, 9, 0)


def random_time():
    """Pick a random moment sometime during an 8-hour workday."""
    return DAY + timedelta(minutes=random.randint(0, 8 * 60))


def make_events(source, event_types, extra_field, n):
    """
    Slack messages, GitHub commits, and Jira ticket updates all follow the
    same basic shape: someone (a dev) did something (event_type) at some
    time. So instead of writing three almost-identical functions, we write
    this ONE generic function and just plug in what's different each time
    (the source name, the possible event types, and one extra field that's
    unique to that source, like "channel" for Slack or "repo" for GitHub).
    """
    events = [{
        "source": source,
        "dev": random.choice(DEVS),
        "event_type": random.choice(event_types),
        "timestamp": random_time().isoformat(),
        **extra_field(),  # bolt on the one extra field specific to this source
    } for _ in range(n)]

    # Sort by time so the JSON file reads top-to-bottom like a real timeline.
    return sorted(events, key=lambda e: e["timestamp"])


def make_vscode_sessions(n=40):
    """
    VSCode activity is different from the others — it's not a single
    moment, it's a BLOCK of time (start coding -> stop coding). This is
    the data we'll later use to detect "flow state," so it needs a
    start and end timestamp, not just one timestamp like the others.
    """
    events, t = [], DAY

    for _ in range(n):
        # How long was this coding burst? Somewhere between 5 and 45 mins.
        duration = random.randint(5, 45)

        events.append({
            "source": "vscode",
            "dev": random.choice(DEVS),
            "event_type": "coding_active",
            "start": t.isoformat(),
            "end": (t := t + timedelta(minutes=duration)).isoformat(),
        })

        # After a coding burst, the dev takes a short break (grabbing coffee,
        # checking phone, etc.) before the next session starts.
        t += timedelta(minutes=random.randint(1, 20))

        # Stop generating sessions once we've gone past 5 PM (end of an
        # 8-hour day starting at 9 AM).
        if t.hour >= 17:
            break

    return events


def main():
    """Generate all four fake datasets and save each one as its own JSON file."""
    datasets = {
        "vscode_events.json": make_vscode_sessions(),

        # Slack messages include some noisy CI/CD bot alerts on purpose —
        # these are the "interruptions" we'll be measuring in later weeks.
        "slack_events.json": make_events(
            "slack",
            ["message", "message", "ci_cd_alert", "ci_cd_alert", "mention"],
            lambda: {"channel": random.choice(["#deploys", "#team-eng", "#alerts"])},
            n=25,
        ),

        "github_events.json": make_events(
            "github",
            ["commit", "pr_opened", "pr_review"],
            lambda: {"repo": "cognistream-app"},
            n=8,
        ),

        "jira_events.json": make_events(
            "jira",
            ["ticket_moved", "ticket_commented"],
            lambda: {"ticket_id": f"COG-{random.randint(100, 199)}"},
            n=5,
        ),
    }

    # Write each dataset to its own JSON file, just like a real API response
    # would be saved before further processing.
    for filename, data in datasets.items():
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Generated {filename}: {len(data)} events")


if __name__ == "__main__":
    main()