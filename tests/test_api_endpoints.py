import pytest
import requests

BASE = "http://127.0.0.1:8000"


@pytest.fixture(scope="module", autouse=True)
def ensure_server():
    """Skip tests if the FastAPI server is not reachable at BASE."""
    try:
        r = requests.get(f"{BASE}/forecasts", timeout=2)
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - network-dependent
        pytest.skip(f"FastAPI server not reachable at {BASE}: {exc}")


def test_cod_decision_required_params():
    params = {"sku_id": "SKU0002", "warehouse_id": "west"}
    r = requests.get(f"{BASE}/cod/decision", params=params, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert data.get("sku_id") == params["sku_id"]
    assert data.get("warehouse_id") == params["warehouse_id"]


def test_reorder_filters_by_warehouse():
    params = {"sku_id": "SKU0002", "warehouse_id": "WH_west"}
    r = requests.get(f"{BASE}/reorder", params=params, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for row in data:
        assert row.get("warehouse_id") == "WH_west"


def test_reorder_returns_multiple_warehouses_for_sku():
    params = {"sku_id": "SKU0002"}
    r = requests.get(f"{BASE}/reorder", params=params, timeout=5)
    assert r.status_code == 200
    data = r.json()
    warehouses = {row.get("warehouse_id") for row in data}
    assert isinstance(warehouses, set)
    assert len(warehouses) >= 2


def test_forecasts_returns_list_for_sku():
    params = {"sku_id": "SKU0002", "limit": 5}
    r = requests.get(f"{BASE}/forecasts", params=params, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
