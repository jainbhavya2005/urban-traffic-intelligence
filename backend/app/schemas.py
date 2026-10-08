from pydantic import BaseModel


class TrafficPredictionRequest(BaseModel):
    probe_count: float
    probe_lag_1: float
    probe_lag_2: float
    probe_lag_3: float
    probe_lag_6: float
    probe_lag_24: float

    rolling_mean_3h: float
    rolling_std_3h: float
    rolling_mean_6h: float

    traffic_change_1h: float
    traffic_change_3h: float
    traffic_change_6h: float
    traffic_acceleration: float

    hour: int
    day_of_week: int
    is_weekend: int

    hour_sin: float
    hour_cos: float
    day_sin: float
    day_cos: float

    speed_limit: float
    frc: float
    distance: float


class TrafficPredictionResponse(BaseModel):
    predicted_next_hour_probe_count: float