"""
Test persistensi data.
Catatan: test ini perlu dijalankan dengan kondisi khusus
(restart container) untuk full verification.
Versi ini test yang bisa dijalankan tanpa restart.
"""
import pytest
import httpx
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def make_event(event_id: str = None, topic: str = "test.persist") -> dict:
    return {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "persist-test",
        "payload": {"persistent": True},
    }


def test_event_retrievable_after_insert():
    """Event yang disimpan harus bisa diambil kembali via GET /events."""
    unique_topic = f"persist.{uuid.uuid4().hex[:8]}"
    event = make_event(topic=unique_topic)

    # Simpan
    resp_post = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp_post.json()["accepted"] == 1

    # Ambil kembali
    resp_get = httpx.get(f"{BASE_URL}/events", params={"topic": unique_topic})
    data = resp_get.json()
    assert len(data) >= 1
    assert data[0]["event_id"] == event["event_id"]


def test_data_not_lost_after_multiple_requests():
    """
    Data lama tidak hilang setelah request baru masuk.
    Simulasi bahwa data persisten antar sesi.
    """
    topic = f"persist.multi.{uuid.uuid4().hex[:8]}"
    event_ids = [str(uuid.uuid4()) for _ in range(3)]

    # Simpan 3 event
    for eid in event_ids:
        httpx.post(f"{BASE_URL}/publish", json=make_event(event_id=eid, topic=topic))

    # Pastikan semua masih ada
    resp = httpx.get(f"{BASE_URL}/events", params={"topic": topic})
    retrieved_ids = {e["event_id"] for e in resp.json()}

    for eid in event_ids:
        assert eid in retrieved_ids, f"Event {eid} tidak ditemukan setelah multiple requests"


def test_dedup_persists_across_calls():
    """
    Dedup harus bekerja meski ada jeda waktu antar pengiriman.
    Simulasi bahwa dedup store persisten (bukan in-memory saja).
    """
    event_id = f"persist-dedup-{uuid.uuid4()}"
    event = make_event(event_id=event_id)

    resp1 = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp1.json()["accepted"] == 1

    # Tunggu sebentar (simulasi jeda)
    import time
    time.sleep(1)

    resp2 = httpx.post(f"{BASE_URL}/publish", json=event)
    assert resp2.json()["duplicates"] == 1