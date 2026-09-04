import json
import random
from datetime import datetime, timedelta

developers = ["D001", "D002", "D003"]

events = []

start_time = datetime(2026, 8, 25, 9, 0, 0)

for i in range(50):

    event = {
        "event_id": f"S{i+1:03}",
        "developer_id": random.choice(developers),
        "event_type": random.choice([
            "message",
            "mention",
            "notification"
        ]),
        "source": "slack",
        "timestamp": (
            start_time + timedelta(minutes=random.randint(0, 480))
        ).isoformat(),
        "project": "Cognistream"
    }

    events.append(event)

with open("../data/raw/slack.json", "w") as file:
    json.dump(events, file, indent=4)

print("Slack mock data generated successfully!")