CREATE TABLE IF NOT EXISTS channel (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    niche TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_run (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_json TEXT,
    FOREIGN KEY(channel_id) REFERENCES channel(id)
);

CREATE TABLE IF NOT EXISTS research_item (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    data_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    FOREIGN KEY(channel_id) REFERENCES channel(id)
);

CREATE TABLE IF NOT EXISTS opportunity (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    score REAL NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(channel_id) REFERENCES channel(id)
);

CREATE TABLE IF NOT EXISTS content_asset (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    status TEXT NOT NULL,
    storage_url TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(channel_id) REFERENCES channel(id)
);

CREATE TABLE IF NOT EXISTS video_performance (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    FOREIGN KEY(channel_id) REFERENCES channel(id)
);
