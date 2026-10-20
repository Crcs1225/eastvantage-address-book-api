import json
import math

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    from app.main import create_app

    with TestClient(create_app(tmp_path / "addresses.db")) as test_client:
        yield test_client


def address(**changes):
    return {"address": "123 Main Street, Manila", "label": "Home",
            "latitude": 14.5995, "longitude": 120.9842, **changes}


def test_crud_and_pagination(client):
    payload = address(address="  123 Main Street, Manila  ")
    response = client.post("/addresses", json=payload)
    assert response.status_code == 201
    saved = response.json()
    assert saved == {**address(), "id": saved["id"]}
    path = f"/addresses/{saved['id']}"
    assert client.get(path).json() == saved
    other = client.post("/addresses", json=address(address="Second address")).json()
    assert client.get("/addresses", params={"limit": 1, "offset": 1}).json() == [other]
    assert client.get("/addresses", params={"offset": 2}).json() == []
    replacement = address(address="456 New Street", latitude=0, longitude=0)
    replacement.pop("label")
    response = client.put(path, json=replacement)
    assert response.status_code == 200
    assert response.json() == {**replacement, "label": None, "id": saved["id"]}
    assert client.get(path).json() == response.json()
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get("/addresses").json() == [other]


def test_persists_across_restarts(tmp_path, monkeypatch):
    from app.main import create_app

    path = tmp_path / "nested" / "persistent.db"
    monkeypatch.setenv("ADDRESS_BOOK_DB", str(path))
    with TestClient(create_app()) as first:
        saved = first.post("/addresses", json=address()).json()
    with TestClient(create_app()) as second:
        assert second.get(f"/addresses/{saved['id']}").json() == saved


@pytest.mark.parametrize("changes", [
    {"address": ""}, {"address": " \t\n "}, {"address": None},
    {"address": "\x00Main Street"}, {"address": "Main\x00Street"},
    {"latitude": 90.01}, {"latitude": -90.01},
    {"longitude": 180.01}, {"longitude": -180.01},
    {"latitude": "NaN"}, {"longitude": "Infinity"},
    {"latitude": None}, {"unexpected": "field"},
])
def test_invalid_create_and_update_leave_data_unchanged(client, changes):
    saved = client.post("/addresses", json=address()).json()
    assert client.post("/addresses", json=address(**changes)).status_code == 422
    assert client.put(f"/addresses/{saved['id']}", json=address(**changes)).status_code == 422
    assert client.get("/addresses").json() == [saved]


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_returns_validation_error(client, number):
    # Raw JSON also exercises invalid numbers that standard clients refuse to encode.
    response = client.post("/addresses", content=json.dumps(address(latitude=number)),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]


def test_required_fields_and_full_replacement(client):
    assert client.post("/addresses", json={"address": "Incomplete"}).status_code == 422
    saved = client.post("/addresses", json=address()).json()
    assert client.put(f"/addresses/{saved['id']}", json={"address": "Partial"}).status_code == 422
    assert client.get(f"/addresses/{saved['id']}").json() == saved


def test_missing_records(client):
    assert client.get("/addresses/999").status_code == 404
    assert client.put("/addresses/999", json=address()).status_code == 404
    assert client.delete("/addresses/999").status_code == 404


@pytest.mark.parametrize("params", [
    {"latitude": 91}, {"longitude": -181}, {"radius_km": -1},
    {"latitude": "NaN"}, {"longitude": "inf"}, {"radius_km": "NaN"},
    {"radius_km": "inf"},
])
def test_invalid_nearby_search(client, params):
    response = client.get("/addresses/nearby", params={
        "latitude": 0, "longitude": 0, "radius_km": 10, **params})
    assert response.status_code == 422


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"offset": -1}])
def test_invalid_pagination(client, params):
    assert client.get("/addresses", params=params).status_code == 422


def test_nearby_sorted_and_filtered(client):
    for name, lon in [("Far", 2), ("Near", 0.5), ("Origin", 0)]:
        client.post("/addresses", json=address(address=name, latitude=0, longitude=lon))
    response = client.get("/addresses/nearby", params={
        "latitude": 0, "longitude": 0, "radius_km": 100})
    assert response.status_code == 200
    results = response.json()
    assert [row["address"] for row in results] == ["Origin", "Near"]
    assert results[0]["distance_km"] == 0
    assert results[1]["distance_km"] == pytest.approx(55.59754, abs=0.001)
    assert client.get("/addresses/nearby", params={
        "latitude": 50, "longitude": 50, "radius_km": 1}).json() == []


def test_zero_radius_and_inclusive_boundary(client):
    client.post("/addresses", json=address(address="Origin", latitude=0, longitude=0))
    client.post("/addresses", json=address(address="Boundary", latitude=0, longitude=1))
    params = {"latitude": 0, "longitude": 0, "radius_km": 0}
    assert [r["address"] for r in client.get("/addresses/nearby", params=params).json()] == ["Origin"]
    # One equatorial degree on a sphere with the IUGG mean Earth radius.
    params["radius_km"] = 6371.0088 * math.pi / 180
    assert [r["address"] for r in client.get("/addresses/nearby", params=params).json()] == ["Origin", "Boundary"]


def test_international_date_line(client):
    client.post("/addresses", json=address(latitude=0, longitude=-179.9))
    results = client.get("/addresses/nearby", params={
        "latitude": 0, "longitude": 179.9, "radius_km": 23}).json()
    assert len(results) == 1
    assert results[0]["distance_km"] == pytest.approx(22.239, abs=0.001)


def test_empty_search_and_required_parameters(client):
    assert client.get("/addresses/nearby", params={
        "latitude": 0, "longitude": 0, "radius_km": 1}).json() == []
    assert client.get("/addresses/nearby").status_code == 422


def test_sql_text_is_stored_as_data(client):
    payload = address(address="Robert'); DROP TABLE addresses; --")
    assert client.post("/addresses", json=payload).status_code == 201
    assert client.get("/addresses").json()[0]["address"] == payload["address"]


def test_docs_and_schema(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/addresses/nearby" in schema["paths"]
    assert "post" in schema["paths"]["/addresses"]
