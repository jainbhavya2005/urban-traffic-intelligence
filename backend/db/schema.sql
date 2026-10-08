CREATE EXTENSION IF NOT EXISTS postgis;


-- ============================================
-- ROADS
-- ============================================

CREATE TABLE roads (
    id BIGSERIAL PRIMARY KEY,

    segment_id BIGINT NOT NULL UNIQUE,
    new_segment_id TEXT,

    street_name TEXT,

    speed_limit DOUBLE PRECISION,
    frc INTEGER,

    distance DOUBLE PRECISION,

    geometry GEOMETRY(LineString, 4326),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================
-- TRAFFIC READINGS
-- ============================================

CREATE TABLE traffic_readings (
    id BIGSERIAL PRIMARY KEY,

    road_id BIGINT NOT NULL
        REFERENCES roads(id)
        ON DELETE CASCADE,

    timestamp TIMESTAMPTZ NOT NULL,

    probe_count INTEGER NOT NULL
        CHECK (probe_count >= 0),

    UNIQUE (road_id, timestamp)
);


-- ============================================
-- PREDICTIONS
-- ============================================

CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,

    road_id BIGINT NOT NULL
        REFERENCES roads(id)
        ON DELETE CASCADE,

    prediction_time TIMESTAMPTZ NOT NULL,

    target_time TIMESTAMPTZ NOT NULL,

    predicted_probe_count DOUBLE PRECISION NOT NULL
        CHECK (predicted_probe_count >= 0),

    model_version TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================
-- INCIDENTS
-- ============================================

CREATE TABLE incidents (
    id BIGSERIAL PRIMARY KEY,

    road_id BIGINT
        REFERENCES roads(id)
        ON DELETE SET NULL,

    incident_type TEXT NOT NULL,

    severity INTEGER
        CHECK (severity BETWEEN 1 AND 5),

    description TEXT,

    start_time TIMESTAMPTZ NOT NULL,

    end_time TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_traffic_readings_road_timestamp
ON traffic_readings (road_id, timestamp);

CREATE INDEX idx_predictions_road_target
ON predictions (road_id, target_time);

CREATE INDEX idx_incidents_road_start
ON incidents (road_id, start_time);

CREATE INDEX idx_incidents_status
ON incidents (status);

CREATE INDEX idx_roads_geometry
ON roads
USING GIST (geometry);