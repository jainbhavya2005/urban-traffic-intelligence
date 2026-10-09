
from fastapi.testclient import TestClient

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
    # This segment ID was verified in our local database.
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
