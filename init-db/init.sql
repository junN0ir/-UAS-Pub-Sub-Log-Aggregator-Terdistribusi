CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    topic       VARCHAR(255)    NOT NULL,
    event_id    VARCHAR(255)    NOT NULL,
    source      VARCHAR(255)    NOT NULL DEFAULT '',
    timestamp   TIMESTAMPTZ     NOT NULL,
    payload     JSONB           NOT NULL DEFAULT '{}',
    received_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_topic_event_id UNIQUE (topic, event_id)
);

-- Tabel audit log: rekam setiap event yang masuk termasuk duplikat
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    topic       VARCHAR(255)    NOT NULL,
    event_id    VARCHAR(255)    NOT NULL,
    source      VARCHAR(255)    NOT NULL DEFAULT '',
    action      VARCHAR(50)     NOT NULL,  -- 'accepted' atau 'duplicate'
    logged_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Tabel outbox: untuk outbox pattern (opsional tapi bernilai)
CREATE TABLE IF NOT EXISTS outbox (
    id              BIGSERIAL PRIMARY KEY,
    topic           VARCHAR(255)    NOT NULL,
    event_id        VARCHAR(255)    NOT NULL,
    payload         JSONB           NOT NULL DEFAULT '{}',
    processed       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stats (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    received            BIGINT NOT NULL DEFAULT 0,
    unique_processed    BIGINT NOT NULL DEFAULT 0,
    duplicate_dropped   BIGINT NOT NULL DEFAULT 0,
    error_count         BIGINT NOT NULL DEFAULT 0,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO stats (id, received, unique_processed, duplicate_dropped, error_count)
VALUES (1, 0, 0, 0, 0)
ON CONFLICT (id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_events_topic ON events (topic);
CREATE INDEX IF NOT EXISTS idx_events_received_at ON events (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_topic_event_id ON events (topic, event_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_logged_at ON audit_log (logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_processed ON outbox (processed) WHERE processed = FALSE;