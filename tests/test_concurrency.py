"""
Test race condition dan konkurensi.
Membuktikan multi-worker tidak menghasilkan double-processing.
"""
import pytest
import httpx
import uuid
import threading
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"


def make_event(event_id: str, topic: str = "test.concurrent") -> dict:
    return {
        "topic": topic,
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "concurrent-test",
        "payload": {"concurrent": True},
    }


def test_concurrent_same_event_no_duplicate():
    """
    10 thread mengirim event yang SAMA secara bersamaan.
    Hanya boleh ada 1 yang diterima, sisanya duplikat.
    """
    shared_event_id = f"concurrent-{uuid.uuid4()}"
    event = make_event(shared_event_id)
    
    accepted_list = []
    lock = threading.Lock()

    def send():
        resp = httpx.post(f"{BASE_URL}/publish", json=event)
        data = resp.json()
        with lock:
            accepted_list.append(data.get("accepted", 0))

    threads = [threading.Thread(target=send) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_accepted = sum(accepted_list)
    assert total_accepted == 1, (
        f"Seharusnya hanya 1 event diterima, tapi ada {total_accepted}. "
        f"Race condition terdeteksi!"
    )


def test_concurrent_different_events_all_accepted():
    """
    10 thread mengirim event BERBEDA secara bersamaan.
    Semuanya harus diterima.
    """
    events = [make_event(f"unique-concurrent-{uuid.uuid4()}") for _ in range(10)]
    accepted_list = []
    lock = threading.Lock()

    def send(event):
        resp = httpx.post(f"{BASE_URL}/publish", json=event)
        data = resp.json()
        with lock:
            accepted_list.append(data.get("accepted", 0))

    threads = [threading.Thread(target=send, args=(e,)) for e in events]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(accepted_list) == 10


def test_stats_consistent_under_concurrency():
    """
    Stats harus konsisten meski ditulis banyak worker paralel.
    received = unique_processed + duplicate_dropped harus selalu benar.
    """
    # Kirim beberapa event termasuk duplikat
    base_id = f"stats-concurrent-{uuid.uuid4()}"
    events = [make_event(base_id) for _ in range(5)]  # 5 duplikat dari event sama

    threads = [
        threading.Thread(
            target=lambda e=e: httpx.post(f"{BASE_URL}/publish", json=e)
        )
        for e in events
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = httpx.get(f"{BASE_URL}/stats").json()
    total = stats["unique_processed"] + stats["duplicate_dropped"]
    assert stats["received"] == total, (
        f"received={stats['received']} != "
        f"unique_processed={stats['unique_processed']} + "
        f"duplicate_dropped={stats['duplicate_dropped']}"
    )