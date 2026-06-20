"""
Stress test: kirim 20.000 event dengan 30% duplikasi.
Membuktikan sistem tetap responsif di bawah beban tinggi.
"""

import pytest
import httpx
import uuid
import time
import random
from datetime import datetime, timezone


BASE_URL = "http://localhost:8080"
TOTAL_EVENTS = 20000
DUPLICATE_RATIO = 0.30
BATCH_SIZE = 100
MAX_ACCEPTABLE_LATENCY_MS = 5000


def make_event(topic: str = "stress.test", event_id: str = None) -> dict:
    return {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "stress-test",
        "payload": {"stress": True, "batch": True},
    }


def test_stress_20k_events():
    """
    Kirim 20.000 event dengan sekitar 30% duplikat via batch.
    Ukur throughput dan pastikan sistem tetap responsif.
    """

    # Buat jumlah duplikat sebagai 30% dari TOTAL_EVENTS
    n_dup = int(TOTAL_EVENTS * DUPLICATE_RATIO)
    n_unique = TOTAL_EVENTS - n_dup

    # Buat event unik
    unique_events = [make_event() for _ in range(n_unique)]

    # Tambahkan duplikat dari event unik yang sudah dibuat
    duplicate_events = random.choices(unique_events, k=n_dup)

    # Gabungkan event unik dan duplikat
    all_events = unique_events + duplicate_events
    random.shuffle(all_events)

    # Kirim dalam batch
    start_time = time.time()
    total_accepted = 0
    total_duplicates = 0
    total_errors = 0

    with httpx.Client(timeout=60.0) as client:
        for i in range(0, len(all_events), BATCH_SIZE):
            batch = all_events[i:i + BATCH_SIZE]

            try:
                resp = client.post(
                    f"{BASE_URL}/publish/batch",
                    json={"events": batch},
                )
                resp.raise_for_status()

                data = resp.json()
                total_accepted += data.get("accepted", 0)
                total_duplicates += data.get("duplicates", 0)
                total_errors += data.get("errors", 0)

            except Exception as e:
                print(f"Batch gagal pada index {i}: {e}")
                total_errors += len(batch)

    elapsed = time.time() - start_time
    throughput = TOTAL_EVENTS / elapsed
    duplicate_rate = total_duplicates / TOTAL_EVENTS

    print(f"\n--- Hasil Stress Test ---")
    print(f"Total event: {TOTAL_EVENTS}")
    print(f"Accepted: {total_accepted}")
    print(f"Duplicates: {total_duplicates}")
    print(f"Errors: {total_errors}")
    print(f"Waktu: {elapsed:.2f}s")
    print(f"Throughput: {throughput:.0f} event/detik")
    print(f"Duplicate rate: {duplicate_rate * 100:.1f}%")

    # Assertions
    assert total_errors == 0, f"Ada {total_errors} error selama stress test"
    assert total_accepted + total_duplicates == TOTAL_EVENTS, "Accounting tidak balance"
    assert duplicate_rate >= 0.25, "Duplicate rate terlalu rendah (ekspektasi ~30%)"
    assert elapsed < 300, f"Stress test terlalu lama: {elapsed:.0f}s (maks 5 menit)"

    print(f"\n✓ Throughput: {throughput:.0f} event/s")


def test_latency_single_event():
    """Latency satu event harus di bawah threshold."""
    event = make_event(event_id=f"latency-{uuid.uuid4()}")

    start = time.time()
    resp = httpx.post(f"{BASE_URL}/publish", json=event)
    latency_ms = (time.time() - start) * 1000

    assert resp.status_code == 200
    assert latency_ms < MAX_ACCEPTABLE_LATENCY_MS, (
        f"Latency {latency_ms:.0f}ms melebihi batas {MAX_ACCEPTABLE_LATENCY_MS}ms"
    )

    print(f"\nLatency single event: {latency_ms:.1f}ms")


def test_stats_consistency_after_stress():
    """Setelah stress test, stats harus konsisten."""
    stats = httpx.get(f"{BASE_URL}/stats").json()

    total = stats["unique_processed"] + stats["duplicate_dropped"]

    assert stats["received"] == total, (
        f"Stats tidak konsisten: received={stats['received']}, "
        f"unique+dup={total}"
    )