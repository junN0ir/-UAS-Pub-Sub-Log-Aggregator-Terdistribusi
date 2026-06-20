"""
Test deduplication dan idempotency.
Membuktikan event yang sama tidak diproses dua kali.
"""
import pytest
import httpx
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def make_event(topic: str = "test.dedup", event_id: str = None) -> dict:
    return {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {"test": True},
    }


def test_single_event_accepted():
    """Event baru harus diterima dan disimpan."""
    event = make_event()
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["duplicates"] == 0


def test_duplicate_event_rejected():
    """Event yang sama dikirim dua kali, duplikat harus ditolak."""
    event = make_event(event_id="dedup-test-001")

    # Kirim pertama
    resp1 = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp1.status_code == 200
    assert resp1.json()["accepted"] == 1

    # Kirim kedua (sama persis)
    resp2 = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["accepted"] == 0
    assert data2["duplicates"] == 1


def test_duplicate_10_times():
    """Kirim event yang sama 10 kali, hanya 1 yang diterima."""
    event = make_event(event_id=f"dedup-10x-{uuid.uuid4()}")
    accepted_total = 0
    duplicate_total = 0

    for _ in range(10):
        resp = httpx.post(f"{BASE_URL}/publish", json=event)
        assert resp.status_code == 200
        data = resp.json()
        accepted_total += data["accepted"]
        duplicate_total += data["duplicates"]

    assert accepted_total == 1
    assert duplicate_total == 9


def test_different_topic_same_event_id():
    """
    Event_id yang sama tapi topic berbeda = event berbeda.
    Keduanya harus diterima.
    """
    shared_id = f"shared-{uuid.uuid4()}"
    event_a = make_event(topic="test.topica", event_id=shared_id)
    event_b = make_event(topic="test.topicb", event_id=shared_id)

    resp_a = httpx.post(f"{BASE_URL}/publish", json=event_a)
    resp_b = httpx.post(f"{BASE_URL}/publish", json=event_b)

    assert resp_a.json()["accepted"] == 1
    assert resp_b.json()["accepted"] == 1


def test_dedup_survives_payload_change():
    """
    Payload berbeda tapi (topic, event_id) sama = tetap duplikat.
    Idempotency tidak bergantung pada isi payload.
    """
    event_id = f"payload-change-{uuid.uuid4()}"
    topic = "test.payload"

    event1 = make_event(topic=topic, event_id=event_id)
    event1["payload"] = {"version": 1}

    event2 = make_event(topic=topic, event_id=event_id)
    event2["payload"] = {"version": 2, "extra": "data"}

    resp1 = httpx.post(f"{BASE_URL}/publish", json=event1)
    resp2 = httpx.post(f"{BASE_URL}/publish", json=event2)

    assert resp1.json()["accepted"] == 1
    assert resp2.json()["duplicates"] == 1