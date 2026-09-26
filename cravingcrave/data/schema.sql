-- CETUS canonical schema (schema_version = 1).
-- All timestamps are ISO-8601 UTC text. Foreign keys are enforced at runtime
-- via PRAGMA foreign_keys = ON.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clinician (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient (
    id                INTEGER PRIMARY KEY,
    code              TEXT UNIQUE NOT NULL,   -- pseudonymous; used in exports
    display_name      TEXT,                   -- never leaves the DB into filenames
    birth_year        INTEGER,
    primary_substance TEXT,
    notes             TEXT,
    created_by        INTEGER REFERENCES clinician(id),
    created_at        TEXT NOT NULL,
    archived          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cue_config (
    id                 INTEGER PRIMARY KEY,
    patient_id         INTEGER NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    substance          TEXT NOT NULL,
    media_path         TEXT NOT NULL,         -- relative to media root
    media_type         TEXT NOT NULL,         -- image|video|audio
    appetitive_rank    INTEGER NOT NULL DEFAULT 0,
    enabled            INTEGER NOT NULL DEFAULT 1,
    is_personal_reason INTEGER NOT NULL DEFAULT 0,
    is_neutral         INTEGER NOT NULL DEFAULT 0,
    craving_weight     REAL,
    research_weight    REAL,
    exposure_count     INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cue_patient ON cue_config(patient_id);

CREATE TABLE IF NOT EXISTS session (
    id                INTEGER PRIMARY KEY,
    patient_id        INTEGER NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    clinician_id      INTEGER NOT NULL REFERENCES clinician(id),
    substance         TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    end_reason        TEXT,                    -- habituated|time_cap|panic|clinician_stop
    consent_given     INTEGER NOT NULL DEFAULT 0,
    baseline_vas      INTEGER,
    peak_vas          INTEGER,
    endpoint_vas      INTEGER,
    habituation_slope REAL,
    app_version       TEXT NOT NULL,
    clinician_notes   TEXT,
    mode              TEXT NOT NULL DEFAULT 'intense'
);
CREATE INDEX IF NOT EXISTS idx_session_patient ON session(patient_id);

CREATE TABLE IF NOT EXISTS craving_rating (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    ts            TEXT NOT NULL,
    elapsed_sec   INTEGER NOT NULL,
    value         INTEGER NOT NULL,           -- 0..10 VAS
    kind          TEXT NOT NULL,              -- baseline|periodic|peak|endpoint
    cue_config_id INTEGER REFERENCES cue_config(id)
);
CREATE INDEX IF NOT EXISTS idx_rating_session ON craving_rating(session_id);

CREATE TABLE IF NOT EXISTS coping_event (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    ts          TEXT NOT NULL,
    elapsed_sec INTEGER NOT NULL,
    skill       TEXT NOT NULL,                -- name_feeling|recall_negative|recall_benefit|alternative_action
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_coping_session ON coping_event(session_id);

CREATE TABLE IF NOT EXISTS intensity_event (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    ts          TEXT NOT NULL,
    elapsed_sec INTEGER NOT NULL,
    action      TEXT NOT NULL,                -- shrink|blur|dim|mute|gallery_open|gallery_close
    scale_pct   INTEGER,
    blur_pct    INTEGER,
    dim_pct     INTEGER,
    muted       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_intensity_session ON intensity_event(session_id);

CREATE TABLE IF NOT EXISTS cue_dwell (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    cue_config_id INTEGER REFERENCES cue_config(id),
    start_sec     INTEGER NOT NULL,
    end_sec       INTEGER NOT NULL,
    dwell_sec     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cue_dwell_session ON cue_dwell(session_id);

CREATE TABLE IF NOT EXISTS app_setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
