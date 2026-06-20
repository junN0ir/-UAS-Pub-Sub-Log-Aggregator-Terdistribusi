"""
Test endpoint API aggregator.
"""
import pytest
import httpx
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def make_event(**kwargs) -> dict:
    base = {
        "topic": "test.api",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {},
    }
    base.update(kwargs)
    return base


def test_health_endpoint():
    """Health check harus return 200."""
    resp = httpx.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_publish_single_event():
    """POST /publish menerima event valid."""
    event = make_event()
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 200


def test_publish_invalid_missing_topic():
    """Event tanpa topic harus ditolak (422)."""
    event = make_event()
    del event["topic"]
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_publish_invalid_timestamp():
    """Timestamp yang tidak valid harus ditolak."""
    event = make_event(timestamp="bukan-tanggal")
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_publish_batch():
    """POST /publish/batch menerima banyak event sekaligus."""
    events = [make_event() for _ in range(5)]
    resp = httpx.post(f"{BASE_URL}/publish/batch", json={"events": events})
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 5
    assert data["duplicates"] == 0


def test_get_events_returns_list():
    """GET /events harus return list."""
    resp = httpx.get(f"{BASE_URL}/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_events_filter_by_topic():
    """GET /events?topic=X hanya return event dari topic X."""
    unique_topic = f"filter.test.{uuid.uuid4().hex[:8]}"
    event = make_event(topic=unique_topic)
    httpx.post(f"{BASE_URL}/publish", json=event)

    resp = httpx.get(f"{BASE_URL}/events", params={"topic": unique_topic})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(e["topic"] == unique_topic for e in data)


def test_get_stats_structure():
    """GET /stats harus punya semua field yang diperlukan."""
    resp = httpx.get(f"{BASE_URL}/stats")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = ["received", "unique_processed", "duplicate_dropped",
                       "topics", "uptime_seconds", "duplicate_rate_percent"]
    for field in required_fields:
        assert field in data, f"Field '{field}' tidak ada di response stats"


def test_stats_increase_after_publish():
    """Stats received harus bertambah setelah publish."""
    stats_before = httpx.get(f"{BASE_URL}/stats").json()
    received_before = stats_before["received"]

    httpx.post(f"{BASE_URL}/publish", json=make_event())

    stats_after = httpx.get(f"{BASE_URL}/stats").json()
    assert stats_after["received"] >= received_before + 1