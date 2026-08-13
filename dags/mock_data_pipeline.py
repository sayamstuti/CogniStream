"""
CogniStream - Airflow DAG

This tells Airflow: "every day, run our mock data generator script."
Right now we're using fake data, but later this same DAG structure is what
would call REAL GitHub/Slack/Jira APIs instead — the orchestration logic
doesn't change, only what's inside the task does.
"""

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys

# Make sure Airflow can find our generator script.
sys.path.append("/opt/airflow/data_ingestion")
from generate_mock_data import main as generate_data


# Basic settings every DAG needs: who owns it, and what happens if it fails.
default_args = {
    "owner": "sayam",
    "retries": 1,
}

with DAG(
    dag_id="cognistream_data_ingestion",
    default_args=default_args,
    description="Pulls (mock) developer activity data daily",
    schedule="@daily",          # run once every day
    start_date=datetime(2026, 8, 10),
    catchup=False,               # don't backfill old runs, only run going forward
    tags=["cognistream"],
) as dag:

    # A single task: run our data generator function.
    generate_task = PythonOperator(
        task_id="generate_mock_events",
        python_callable=generate_data,
    )

    generate_task