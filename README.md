# CogniStream — Developer Flow-State & Cognitive Load Analytics

Engineering productivity is usually measured with shallow metrics like
"lines of code" or "tickets closed" — these measure *output*, not the
*friction* that blocks deep, focused work. CogniStream analyzes developer
activity logs (GitHub, Slack, Jira, IDE) to surface a "Context-Switching
Tax": how much flow-state time is lost to interruptions like poorly-timed
CI/CD Slack alerts — giving engineering managers something actionable
instead of vanity metrics.

## Tech Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow |
| OLAP Database | ClickHouse |
| Data Processing | Python + Polars |
| Backend API | FastAPI |
| Frontend | React + Tremor.js |
| Infra | Docker Compose |

## Architecture
Mock APIs (GitHub/Slack/Jira/VSCode)
↓
Airflow (daily schedule)
↓
ClickHouse (event storage)
↓
Polars (flow-state detection logic)
↓
FastAPI (serves aggregated metrics)
↓
React + Tremor.js (dashboard)

## Project Structure

CogniStream/
├── dags/
│ └── mock_data_pipeline.py # Airflow DAG -- schedules daily data generation
├── data_ingestion/
│ └── generate_mock_data.py # Generates fake GitHub/Slack/Jira/VSCode events
├── docker-compose.yaml # Spins up Airflow + Postgres (+ ClickHouse)
├── requirements.txt
└── README.md

## How to Run This Project

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Start the one-time Airflow database/user setup
docker-compose up airflow-init

# 2. Start all services in the background
docker-compose up -d

# 3. Confirm containers are running
docker ps
```

Open the Airflow dashboard at **http://localhost:8080**
(Username: `admin` / Password: `admin`)

You'll see the `cognistream_data_ingestion` DAG. Toggle it on and trigger a
run manually, or let it run automatically on its daily schedule.

## Progress Log

- **Day 1:** Built mock data generators simulating GitHub commits, Slack
  messages (including CI/CD bot alerts), Jira ticket updates, and VSCode
  coding sessions.
- **Day 2:** Extended data generation from a single day to a full 5-day
  work week, enabling pattern detection across days.
- **Day 3:** Wrote the Airflow DAG (`mock_data_pipeline.py`) to schedule
  the data generator to run daily.
- **Day 4:** Set up Airflow via Docker Compose (Postgres + webserver +
  scheduler). Verified the DAG runs successfully -- confirmed both a
  manual trigger and an automatic scheduled run completed with
  `Total success: 2`.
  ![Airflow DAG success](docs/screenshots/airflow_success.jpg)

## Mid-Review Deliverable

Orchestration Audit -- Airflow DAG runs successfully, confirmed via the
Airflow UI (Grid view shows successful runs for `generate_mock_events`).

## Next Steps

- Deploy ClickHouse and design the event-table schema
- Load generated JSON data into ClickHouse using Polars
- Build the core "Flow-State Detection" algorithm
