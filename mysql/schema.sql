-- schema.sql
-- CogniStream MySQL schema (Person 2 - Database & Core Logic Track).
--
-- NOTE: the original design called for ClickHouse (a columnar OLAP store)
-- specifically because this workload is "scan millions of timestamped
-- events, filtered by user + time range." MySQL/InnoDB is a row-store built
-- for OLTP, so it won't scale the same way - but for a class-project volume
-- of mock data it's fine, and the indexing choices below are the best you
-- can do to keep the two query patterns this project needs (per-user time
-- range scans, and daily aggregation) fast on InnoDB:
--   1. `idx_user_time` (user_id, timestamp) - a composite B-tree index so
--      "give me all events for user X between t1 and t2" (what every
--      downstream step needs) is an index range scan, not a full table scan.
--   2. `idx_source` - a secondary index so filtering to e.g. 'slack' events
--      doesn't have to scan every row.
--   3. `metadata` uses MySQL's native JSON column type (5.7+/8.0), which
--      stores a validated binary form and supports JSON_EXTRACT()/->>
--      operators for querying into source-specific fields without an
--      upfront schema migration per source (GitHub/Slack/Jira/VSCode all
--      have different metadata shapes).

CREATE DATABASE IF NOT EXISTS cognistream
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE cognistream;

CREATE TABLE IF NOT EXISTS events (
    event_id        CHAR(36)      NOT NULL,
    source          VARCHAR(20)   NOT NULL,   -- 'github' | 'slack' | 'jira' | 'vscode'
    event_type      VARCHAR(30)   NOT NULL,   -- 'commit' | 'ci_cd_alert' | 'coding_active' | ...
    user_id         VARCHAR(50)   NOT NULL,
    `timestamp`     DATETIME(3)   NOT NULL,   -- for vscode rows: session START
    repo            VARCHAR(100)  NULL,
    metadata        JSON          NULL,       -- source-specific extra fields
                                               -- (vscode: {"end": ..., "duration_minutes": ...})
    ingested_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id),
    KEY idx_user_time (user_id, `timestamp`),
    KEY idx_source (source)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS flow_blocks (
    block_id                VARCHAR(80)  NOT NULL,
    user_id                 VARCHAR(50)  NOT NULL,
    block_start             DATETIME(3)  NOT NULL,
    block_end               DATETIME(3)  NOT NULL,
    duration_minutes        FLOAT        NOT NULL,
    interrupted_by_source   VARCHAR(20)  NULL,   -- e.g. 'slack'
    interrupted_by_detail   VARCHAR(30)  NULL,   -- e.g. 'ci_cd_alert' | 'human_message' | 'jira_activity' | NULL
    repo                    VARCHAR(100) NULL,
    computed_at              TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (block_id),
    KEY idx_user_start (user_id, block_start)
) ENGINE = InnoDB;

-- Example "prove it's fast" query for the mid-review demo:
-- EXPLAIN
-- SELECT COUNT(*) FROM events
-- WHERE user_id = 'dev_amit' AND `timestamp` >= NOW() - INTERVAL 7 DAY;
-- -> should show `key: idx_user_time` (index range scan), not a full table scan.

-- Example query into JSON metadata (equivalent of ClickHouse's JSONExtract):
-- SELECT event_id, metadata->>'$.channel' AS channel
-- FROM events
-- WHERE source = 'slack' AND event_type = 'ci_cd_alert';
