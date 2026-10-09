
from datetime import timedelta

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import model
from .database import get_db
from .feature_engineering import build_features

app = FastAPI(
    title="Urban Traffic Intelligence API",
    description="Backend API for traffic forecasting and route intelligence",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "urban-traffic-intelligence-api",
    }


@app.get("/db-test")
def database_test(db: Session = Depends(get_db)):
    road_count = db.execute(
        text("SELECT COUNT(*) FROM roads")
    ).scalar()

    return {
        "database": "connected",
        "road_count": road_count,
    }


@app.get("/roads")
def get_roads(db: Session = Depends(get_db)):
    roads = db.execute(
        text("""
            SELECT
                segment_id,
                new_segment_id,
                street_name,
                speed_limit,
                frc,
                distance
            FROM roads
            ORDER BY segment_id
            LIMIT 100
        """)
    ).mappings().all()

    return {
        "count": len(roads),
        "roads": [dict(road) for road in roads],
    }


@app.get("/roads/{segment_id}")
def get_road(
    segment_id: int,
    db: Session = Depends(get_db),
):
    road = db.execute(
        text("""
            SELECT
                segment_id,
                new_segment_id,
                street_name,
                speed_limit,
                frc,
                distance
            FROM roads
            WHERE segment_id = :segment_id
        """),
        {"segment_id": segment_id},
    ).mappings().first()

    if road is None:
        raise HTTPException(
            status_code=404,
            detail="Road not found",
        )

    return dict(road)


@app.get("/traffic/history/{segment_id}")
def get_traffic_history(
    segment_id: int,
    db: Session = Depends(get_db),
):
    readings = db.execute(
        text("""
            SELECT
                tr.timestamp,
                tr.probe_count
            FROM traffic_readings AS tr
            JOIN roads AS r ON r.id = tr.road_id
            WHERE r.segment_id = :segment_id
            ORDER BY tr.timestamp
        """),
        {"segment_id": segment_id},
    ).mappings().all()

    if not readings:
        raise HTTPException(
            status_code=404,
            detail="No traffic history found for this road",
        )

    return {
        "segment_id": segment_id,
        "count": len(readings),
        "readings": [
            {
                "timestamp": reading["timestamp"],
                "probe_count": reading["probe_count"],
            }
            for reading in readings
        ],
    }


@app.post("/predict/{segment_id}")
def predict_traffic(
    segment_id: int,
    db: Session = Depends(get_db),
):
    # 1. Retrieve road metadata.
    road = db.execute(
        text("""
            SELECT
                id,
                speed_limit,
                frc,
                distance
            FROM roads
            WHERE segment_id = :segment_id
        """),
        {"segment_id": segment_id},
    ).mappings().first()

    if road is None:
        raise HTTPException(
            status_code=404,
            detail="Road not found",
        )

    # 2. Retrieve the latest 25 hourly observations.
    readings = db.execute(
        text("""
            SELECT
                tr.timestamp,
                tr.probe_count
            FROM traffic_readings AS tr
            JOIN roads AS r ON r.id = tr.road_id
            WHERE r.segment_id = :segment_id
            ORDER BY tr.timestamp DESC
            LIMIT 25
        """),
        {"segment_id": segment_id},
    ).mappings().all()

    # The query returns newest first; feature engineering needs oldest first.
    readings = list(reversed([dict(row) for row in readings]))

    if len(readings) < 25:
        raise HTTPException(
            status_code=422,
            detail="At least 25 hourly readings are required",
        )

    # 3. Generate the model features.
    try:
        features = build_features(readings, dict(road))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # 4. Predict the next-hour probe count.
    X = features[model.feature_columns].astype(float).to_frame().T
    prediction = max(float(model.model.predict(X)[0]), 0.0)

    # 5. Calculate the observation and target times in India-local time.
    latest_clock = (
        pd.to_datetime(readings[-1]["timestamp"], utc=True)
        .tz_convert("Asia/Kolkata")
    )
    target_clock = latest_clock + timedelta(hours=1)

    # Store timezone-aware instants in PostgreSQL.
    prediction_time_utc = latest_clock.tz_convert("UTC").to_pydatetime()
    target_time_utc = target_clock.tz_convert("UTC").to_pydatetime()

    # 6. Persist the forecast.
    try:
        saved_prediction = db.execute(
            text("""
                INSERT INTO predictions (
                    road_id,
                    prediction_time,
                    target_time,
                    predicted_probe_count,
                    model_version
                )
                VALUES (
                    :road_id,
                    :prediction_time,
                    :target_time,
                    :predicted_probe_count,
                    :model_version
                )
                RETURNING id
            """),
            {
                "road_id": road["id"],
                "prediction_time": prediction_time_utc,
                "target_time": target_time_utc,
                "predicted_probe_count": prediction,
                "model_version": "xgboost-v1",
            },
        )

        prediction_id = saved_prediction.scalar_one()
        db.commit()

    except Exception:
        db.rollback()
        raise

    # 7. Return the forecast.
    return {
        "prediction_id": prediction_id,
        "segment_id": segment_id,
        "predicted_next_hour_probe_count": round(prediction, 2),
        "latest_observation_time": latest_clock.isoformat(),
        "prediction_target_time": target_clock.isoformat(),
        "timezone": "Asia/Kolkata",
        "model_version": "xgboost-v1",
        "note": "Predicted probe count, not total vehicle count.",
    }


@app.get("/predictions/{segment_id}")
def get_prediction_history(
    segment_id: int,
    db: Session = Depends(get_db),
):
    # Confirm that the requested road exists.
    road_exists = db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM roads
                WHERE segment_id = :segment_id
            )
        """),
        {"segment_id": segment_id},
    ).scalar()

    if not road_exists:
        raise HTTPException(
            status_code=404,
            detail="Road not found",
        )

    predictions = db.execute(
        text("""
            SELECT
                p.id AS prediction_id,
                p.prediction_time,
                p.target_time,
                p.predicted_probe_count,
                p.model_version
            FROM predictions AS p
            JOIN roads AS r ON r.id = p.road_id
            WHERE r.segment_id = :segment_id
            ORDER BY p.target_time DESC, p.created_at DESC
            LIMIT 100
        """),
        {"segment_id": segment_id},
    ).mappings().all()

    return {
        "segment_id": segment_id,
        "count": len(predictions),
        "predictions": [
            {
                "prediction_id": p["prediction_id"],
                "prediction_time": p["prediction_time"],
                "target_time": p["target_time"],
                "predicted_probe_count": p["predicted_probe_count"],
                "model_version": p["model_version"],
            }
            for p in predictions
        ],
    }
