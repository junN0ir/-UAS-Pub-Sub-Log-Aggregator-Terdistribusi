"""
Test validasi schema event.
"""
import pytest
import httpx
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def valid_event() -> dict:
    return {
        "topic": "test.schema",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {"key": "value"},
    }


def test_valid_event_accepted():
    resp = httpx.post(f"{BASE_URL}/publish", json=valid_event())
    assert resp.status_code == 200


def test_missing_event_id_rejected():
    event = valid_event()
    del event["event_id"]
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_empty_topic_rejected():
    event = valid_event()
    event["topic"] = ""
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_topic_with_space_rejected():
    event = valid_event()
    event["topic"] = "topic dengan spasi"
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_invalid_timestamp_format_rejected():
    event = valid_event()
    event["timestamp"] = "31-12-2024"
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 422


def test_payload_optional():
    """Payload boleh dikosongkan (default dict kosong)."""
    event = valid_event()
    del event["payload"]
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 200


def test_batch_empty_rejected():
    """Batch kosong harus ditolak."""
    resp = httpx.post(f"{BASE_URL}/publish/batch", json={"events": []})
    assert resp.status_code == 422