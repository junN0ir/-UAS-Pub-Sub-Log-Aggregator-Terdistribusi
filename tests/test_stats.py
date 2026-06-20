"""
Test statistik sistem.
"""
import pytest
import httpx
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def make_event(**kwargs) -> dict:
    base = {
        "topic": "test.stats",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {},
    }
    base.update(kwargs)
    return base


def test_stats_format():
    """Stats response harus punya format yang benar."""
    resp = httpx.get(f"{BASE_URL}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["received"], int)
    assert isinstance(data["unique_processed"], int)
    assert isinstance(data["duplicate_dropped"], int)
    assert isinstance(data["topics"], list)
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["duplicate_rate_percent"], (int, float))


def test_stats_accounting():
    """received harus sama dengan unique + duplicate."""
    stats = httpx.get(f"{BASE_URL}/stats").json()
    assert stats["received"] == stats["unique_processed"] + stats["duplicate_dropped"]


def test_duplicate_rate_increases():
    """duplicate_rate_percent harus naik setelah kirim duplikat."""
    event = make_event(event_id=f"rate-test-{uuid.uuid4()}")
    httpx.post(f"{BASE_URL}/publish", json=event)

    # Kirim duplikat banyak kali
    for _ in range(5):
        httpx.post(f"{BASE_URL}/publish", json=event)

    stats = httpx.get(f"{BASE_URL}/stats").json()
    assert stats["duplicate_rate_percent"] > 0


def test_topic_appears_in_stats():
    """Topic yang digunakan harus muncul di daftar topics stats."""
    unique_topic = f"stats.topic.{uuid.uuid4().hex[:8]}"
    event = make_event(topic=unique_topic)
    httpx.post(f"{BASE_URL}/publish", json=event)

    stats = httpx.get(f"{BASE_URL}/stats").json()
    assert unique_topic in stats["topics"]