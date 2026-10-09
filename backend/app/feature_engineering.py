import numpy as np
import pandas as pd


def build_features(readings, road):
    """
    Build the same 23 features used by the trained model.

    readings must be in chronological order and contain at least
    25 consecutive hourly observations.
    """

    if len(readings) < 25:
        raise ValueError(
            "At least 25 hourly observations are required."
        )

    df = pd.DataFrame(readings)

   # Database timestamps contain the original India-local clock
# values, but PostgreSQL interpreted them as UTC.
# Remove the timezone without shifting the clock values.
    # Convert real UTC instants to India-local time.
    df["timestamp"] = (
    pd.to_datetime(df["timestamp"], utc=True)
      .dt.tz_convert("Asia/Kolkata")
    )
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Ensure observations are hourly and consecutive.
    differences = df["timestamp"].diff().dropna()

    if not (differences == pd.Timedelta(hours=1)).all():
        raise ValueError(
            "Traffic history contains missing or irregular hourly observations."
        )

    df["probe_lag_1"] = df["probe_count"].shift(1)
    df["probe_lag_2"] = df["probe_count"].shift(2)
    df["probe_lag_3"] = df["probe_count"].shift(3)
    df["probe_lag_6"] = df["probe_count"].shift(6)
    df["probe_lag_24"] = df["probe_count"].shift(24)

    df["rolling_mean_3h"] = (
        df["probe_count"].shift(1).rolling(3).mean()
    )

    df["rolling_std_3h"] = (
        df["probe_count"].shift(1).rolling(3).std()
    )

    df["rolling_mean_6h"] = (
        df["probe_count"].shift(1).rolling(6).mean()
    )

    df["traffic_change_1h"] = (
        df["probe_count"] - df["probe_lag_1"]
    )

    df["traffic_change_3h"] = (
        df["probe_count"] - df["probe_lag_3"]
    )

    df["traffic_change_6h"] = (
        df["probe_count"] - df["probe_lag_6"]
    )

    df["traffic_acceleration"] = (
        (df["probe_count"] - df["probe_lag_1"])
        - (df["probe_lag_1"] - df["probe_lag_2"])
    )

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    df["hour_sin"] = np.sin(
        2 * np.pi * df["hour"] / 24
    )

    df["hour_cos"] = np.cos(
        2 * np.pi * df["hour"] / 24
    )

    df["day_sin"] = np.sin(
        2 * np.pi * df["day_of_week"] / 7
    )

    df["day_cos"] = np.cos(
        2 * np.pi * df["day_of_week"] / 7
    )

    # Road attributes are static.
    df["speed_limit"] = road["speed_limit"]
    df["frc"] = road["frc"]
    df["distance"] = road["distance"]

    from app.model import feature_columns
    return df.iloc[-1][feature_columns]