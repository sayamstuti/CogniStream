import polars as pl

# ==========================================
# 1. LOAD RAW DATA
# ==========================================

github = pl.read_json("data/raw/github.json")
slack = pl.read_json("data/raw/slack.json")
jira = pl.read_json("data/raw/jira.json")
vscode = pl.read_json("data/raw/vscode.json")

print("Raw data loaded successfully!")


# ==========================================
# 2. COMBINE ALL DATASETS
# ==========================================

combined = pl.concat(
    [github, slack, jira, vscode],
    how="vertical"
)

print("All datasets combined successfully!")


# ==========================================
# 3. CONVERT TIMESTAMP
# ==========================================

combined = combined.with_columns(
    pl.col("timestamp").str.to_datetime()
)


# ==========================================
# 4. SORT EVENTS CHRONOLOGICALLY
# ==========================================

combined = combined.sort("timestamp")


# ==========================================
# 5. SELECT REQUIRED COLUMNS
# ==========================================

combined = combined.select([
    "event_id",
    "developer_id",
    "event_type",
    "source",
    "timestamp",
    "project"
])


# ==========================================
# 6. SAVE PROCESSED DATA
# ==========================================

combined.write_parquet(
    "data/processed/events.parquet"
)

print("Data cleaning and transformation completed!")


# ==========================================
# 7. DISPLAY TOTAL EVENTS
# ==========================================

print(f"Total events: {combined.height}")


# ==========================================
# 8. DISPLAY EVENTS BY SOURCE
# ==========================================

print("\nEvents by source:")

source_summary = (
    combined
    .group_by("source")
    .agg(
        pl.len().alias("event_count")
    )
    .sort("source")
)

print(source_summary)


# ==========================================
# 9. DISPLAY PROCESSED DATA PREVIEW
# ==========================================

print("\nProcessed data preview:")

print(combined.head(10))