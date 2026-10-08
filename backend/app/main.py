from fastapi import FastAPI, Depends
from sqlalchemy import text

from . import model
from .database import get_db
from .schemas import (
    TrafficPredictionRequest,
    TrafficPredictionResponse
)
app = FastAPI(
    title="Urban Traffic Intelligence API",
    description="Backend API for traffic forecasting and route intelligence",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "urban-traffic-intelligence-api"
    }

@app.get("/db-test")
def database_test(db=Depends(get_db)):

    result = db.execute(
        text("SELECT COUNT(*) FROM roads")
    )

    road_count = result.scalar()

    return {
        "database": "connected",
        "road_count": road_count
    }
@app.post(
    "/predict",
    response_model=TrafficPredictionResponse
)
def predict_traffic(request: TrafficPredictionRequest):

    input_data = request.model_dump()

    features = [
        input_data[column]
        for column in model.feature_columns
    ]

    prediction = model.model.predict([features])[0]

    prediction = max(float(prediction), 0.0)

    return {
        "predicted_next_hour_probe_count": prediction
    }