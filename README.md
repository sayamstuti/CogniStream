# CogniStream — Ingestion & Orchestration

### My Contributions  — Ingestion & Orchestration Track

My contribution focuses on **mock data generation and Airflow-based orchestration**.

## 📌 Responsibilities

- Generate mock **GitHub, Slack, Jira & VSCode** activity data using Python
- Generate data for a **5-day work week**
- Set up **Apache Airflow**
- Create DAGs for scheduled data generation
- Verify successful manual and scheduled DAG runs

## 🛠️ Tech Stack

- Python
- Apache Airflow
- PostgreSQL
- Docker Compose
- JSON

## 📁 Project Structure

```text
CogniStream/
│
├── dags/
│   └── mock_data_pipeline.py
│
├── data_ingestion/
│   └── generate_mock_data.py
│
├── docs/
│   └── screenshots/
│       └── airflow_success.jpg
│
├── docker-compose.yaml
├── requirements.txt
└── README.md

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

![Airflow DAG success](docs/screenshots/airflow-success.jpg)

## Mid-Review Deliverable

Orchestration Audit -- Airflow DAG runs successfully, confirmed via the
Airflow UI (Grid view shows successful runs for `generate_mock_events`).