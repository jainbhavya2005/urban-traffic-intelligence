
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_roads_endpoint():
    response = client.get("/roads")

    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert "roads" in data
    assert data["count"] <= 100


def test_existing_road_endpoint():
    segment_id = -13560345653148

    response = client.get(f"/roads/{segment_id}")

    assert response.status_code == 200
    assert response.json()["segment_id"] == segment_id


def test_nonexistent_road_endpoint():
    response = client.get("/roads/999999999999999999")

    assert response.status_code == 404


def test_prediction_history_endpoint():
    segment_id = -13560345653148

    response = client.get(f"/predictions/{segment_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["segment_id"] == segment_id
    assert data["count"] >= 1
    assert isinstance(data["predictions"], list)


def test_prediction_endpoint():
    segment_id = -13560345653148

    road = {
        "id": 30289,
        "speed_limit": 40,
        "frc": 2,
        "distance": 1.5,
    }

    # Provide 25 hourly readings, newest first, as returned by SQL.
    
    from datetime import datetime, timedelta, timezone

    latest = datetime(2024, 8, 30, 17, 0, tzinfo=timezone.utc)

    # SQL returns newest first, so generate the readings in reverse order.
    readings = [
        {
            "timestamp": latest - timedelta(hours=i),
            "probe_count": (24 - i) * 10,
        }
        for i in range(25)
    ]


    mock_db = MagicMock()

    road_result = MagicMock()
    road_result.mappings.return_value.first.return_value = road

    readings_result = MagicMock()
    readings_result.mappings.return_value.all.return_value = readings

    insert_result = MagicMock()
    insert_result.scalar_one.return_value = 999

    mock_db.execute.side_effect = [
        road_result,
        readings_result,
        insert_result,
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.main.model.model.predict",
            return_value=[12.5],
        ):
            response = client.post(f"/predict/{segment_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    data = response.json()
    assert data["prediction_id"] == 999
    assert data["segment_id"] == segment_id
    assert data["predicted_next_hour_probe_count"] == 12.5
    assert data["model_version"] == "xgboost-v1"
    assert data["timezone"] == "Asia/Kolkata"

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()
