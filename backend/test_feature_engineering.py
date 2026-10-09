
from app.feature_engineering import build_features


def make_readings():
    """Create 30 consecutive hourly readings, oldest to newest."""
    readings = []

    for i in range(30):
        day = 11 + i // 24
        hour = i % 24

        readings.append({
            "timestamp": f"2024-08-{day:02d} {hour:02d}:00:00+00",
            "probe_count": i * 10,
        })

    return readings


def make_road():
    return {
        "speed_limit": 40,
        "frc": 2,
        "distance": 1.5,
    }


def test_build_features_returns_expected_columns():
    features = build_features(make_readings(), make_road())

    expected_columns = [
        "probe_count",
        "probe_lag_1",
        "probe_lag_2",
        "probe_lag_3",
        "probe_lag_6",
        "probe_lag_24",
        "rolling_mean_3h",
        "rolling_std_3h",
        "rolling_mean_6h",
        "traffic_change_1h",
        "traffic_change_3h",
        "traffic_change_6h",
        "traffic_acceleration",
        "hour",
        "day_of_week",
        "is_weekend",
        "hour_sin",
        "hour_cos",
        "day_sin",
        "day_cos",
        "speed_limit",
        "frc",
        "distance",
    ]

    assert list(features.keys()) == expected_columns


def test_build_features_calculates_lags():
    features = build_features(make_readings(), make_road())

    assert features["probe_count"] == 290
    assert features["probe_lag_1"] == 280
    assert features["probe_lag_2"] == 270
    assert features["probe_lag_3"] == 260
    assert features["probe_lag_6"] == 230
    assert features["probe_lag_24"] == 50


def test_build_features_includes_road_attributes():
    features = build_features(make_readings(), make_road())

    assert features["speed_limit"] == 40
    assert features["frc"] == 2
    assert features["distance"] == 1.5
