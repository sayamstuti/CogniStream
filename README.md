# CogniStream — Developer Flow-State & Cognitive Load Analytics
Measures developer flow-state and "Context-Switching Tax" using activity logs (GitHub, Slack, Jira, VSCode) instead of shallow metrics like lines-of-code or tickets closed.


## My Contributions-


## Tech Stack
Apache Airflow · ClickHouse · Python (Polars) · Docker · FastAPI (planned) · React + Tremor.js (planned)

## Architecture
Mock APIs → Airflow (daily schedule) → ClickHouse (storage) → Polars (flow-state logic) → FastAPI → React Dashboard

## Project Structure
CogniStream/
├── dags/mock_data_pipeline.py           # Airflow DAG
├── data_ingestion/generate_mock_data.py # Mock event generator
├── data_processing/
│   ├── load_to_clickhouse.py            # ETL: JSON → ClickHouse
│   └── validate_pipeline.py             # Data quality checks
├── docs/screenshots/
├── docker-compose.yaml                  # Airflow + Postgres + ClickHouse
└── requirements.txt

## How to Run
docker-compose up airflow-init      # one-time setup
docker-compose up -d                # start all services
docker ps                           # confirm containers running

Airflow dashboard: http://localhost:8080 (admin/admin)

cd data_processing
python load_to_clickhouse.py        # load data into ClickHouse
python validate_pipeline.py         # run data quality checks

## Progress Log
- Day 1-2: Mock data generators for GitHub/Slack/Jira/VSCode, extended to a 5-day work week
- Day 3-4: Airflow DAG built and deployed via Docker; verified successful scheduled runs
- Day 5-6: ClickHouse deployed; dev_events schema created; 261 events loaded via Polars ETL
- Day 7-8: Automated pipeline validation (6 data quality checks, all passing); mid-review docs

## Mid-Review Proof

Airflow DAG running successfully:
![Airflow success](docs/screenshots/airflow_success.jpg)

Pipeline validation — all checks passing:
![Validation checks](docs/screenshots/validate_pipeline.png)

Full stack running (Airflow + Postgres + ClickHouse):
![Docker containers](docs/screenshots/docker_containers.png)

## Next Steps
Flow-state detection algorithm → Context-Switching Tax metric → FastAPI → React dashboard

## Author

**Sayam Stuti Shuvadarsini**

- LinkedIn: [www.linkedin.com/in/sayam-stuti-shuvadarsini](https://www.linkedin.com/in/sayam-stuti-shuvadarsini)
- GitHub: [github.com/sayamstuti](https://github.com/sayamstuti)
- Email: sayamstuti594@gmail.com