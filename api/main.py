"""
CogniStream - FastAPI Backend

Serves the pre-computed developer metrics (from aggregate_metrics.py) as
JSON over HTTP. This is what the React dashboard will call to get data --
instead of the frontend needing to know anything about ClickHouse.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import clickhouse_connect

app = FastAPI(title="CogniStream API")

# Allow the React frontend (running on a different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client():
    return clickhouse_connect.get_client(
        host="localhost", port=8123,
        username="cognistream", password="cognistream",
        database="cognistream",
    )


@app.get("/")
def root():
    return {"message": "CogniStream API is running"}


@app.get("/metrics")
def get_all_metrics():
    """Returns the full per-developer summary table -- the main data the
    dashboard's overview page will show."""
    client = get_client()
    result = client.query("SELECT * FROM dev_metrics_summary ORDER BY dev")
    columns = result.column_names
    return [dict(zip(columns, row)) for row in result.result_rows]


@app.get("/metrics/{dev}")
def get_dev_metrics(dev: str):
    """Returns metrics for just one developer -- used for a detail/drill-down
    view in the dashboard."""
    client = get_client()
    result = client.query(
        "SELECT * FROM dev_metrics_summary WHERE dev = {dev:String}",
        parameters={"dev": dev},
    )
    if not result.result_rows:
        raise HTTPException(status_code=404, detail=f"No data for dev '{dev}'")
    columns = result.column_names
    return dict(zip(columns, result.result_rows[0]))