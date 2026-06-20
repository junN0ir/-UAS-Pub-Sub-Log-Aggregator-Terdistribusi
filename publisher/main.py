import asyncio
import httpx
import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("publisher")

AGGREGATOR_URL = os.getenv("AGGREGATOR_URL", "http://aggregator:8080")
EVENTS_TO_SEND = int(os.getenv("EVENTS_TO_SEND", "500"))
DUPLICATE_RATIO = float(os.getenv("DUPLICATE_RATIO", "0.3"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))

TOPICS = [
    "system.auth",
    "system.payment",
    "system.order",
    "system.notification",
    "system.audit",
]


def generate_event(topic: str | None = None) -> dict:
    """Buat satu event dengan format yang valid."""
    return {
        "topic": topic or random.choice(TOPICS),
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": f"publisher-{random.randint(1, 5)}",
        "payload": {
            "user_id": random.randint(1000, 9999),
            "action": random.choice(["login", "logout", "purchase", "view"]),
            "value": round(random.uniform(1.0, 1000.0), 2),
        },
    }


async def send_event(client: httpx.AsyncClient, event: dict,
                     max_retries: int = 3) -> bool:
    """
    Kirim satu event dengan retry dan exponential backoff.
    
    Pola at-least-once: jika gagal, kirim ulang sampai max_retries.
    Backoff: 1s, 2s, 4s — mencegah thundering herd saat aggregator
    sedang overload atau restart.
    """
    for attempt in range(max_retries):
        try:
            resp = await client.post(
                f"{AGGREGATOR_URL}/publish",
                json=event,
                timeout=10.0,
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                # 4xx = error klien, tidak perlu retry
                logger.error(f"Client error {e.response.status_code} untuk event {event.get('event_id')}")
                return False
            # 5xx = error server, retry dengan backoff
            wait = 2 ** attempt
            logger.warning(f"Server error, retry {attempt+1}/{max_retries} setelah {wait}s")
            await asyncio.sleep(wait)
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Koneksi gagal, retry {attempt+1}/{max_retries} setelah {wait}s: {e}")
            await asyncio.sleep(wait)

    logger.error(f"Gagal kirim setelah {max_retries} percobaan: {event.get('event_id')}")
    return False


async def run_publisher():
    """
    Publisher utama:
    1. Generate N event unik
    2. Tambahkan duplikat sesuai DUPLICATE_RATIO
    3. Kirim semua secara concurrent
    """
    logger.info(f"Publisher start: {EVENTS_TO_SEND} events, {DUPLICATE_RATIO*100:.0f}% duplikat")

    # Buat event unik
    unique_events = [generate_event() for _ in range(EVENTS_TO_SEND)]

    # Tambah duplikat
    n_duplicates = int(EVENTS_TO_SEND * DUPLICATE_RATIO)
    duplicate_events = random.choices(unique_events, k=n_duplicates)

    # Gabungkan dan acak urutan
    all_events = unique_events + duplicate_events
    random.shuffle(all_events)

    logger.info(f"Total event yang akan dikirim: {len(all_events)} ({n_duplicates} duplikat)")

    # Kirim dengan batasan concurrency
    semaphore = asyncio.Semaphore(CONCURRENCY)
    success = 0
    fail = 0

    async def send_with_semaphore(client, event):
        async with semaphore:
            return await send_event(client, event)

    async with httpx.AsyncClient() as client:
        tasks = [send_with_semaphore(client, e) for e in all_events]
        results = await asyncio.gather(*tasks)
        success = sum(1 for r in results if r)
        fail = sum(1 for r in results if not r)

    logger.info(f"Publisher selesai: {success} berhasil, {fail} gagal")

    # Tampilkan stats akhir
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{AGGREGATOR_URL}/stats", timeout=5.0)
            stats = resp.json()
            logger.info(f"Stats akhir: {json.dumps(stats, indent=2)}")
    except Exception as e:
        logger.warning(f"Tidak bisa ambil stats: {e}")


async def wait_for_aggregator():
    """Tunggu sampai aggregator siap menerima request."""
    logger.info("Menunggu aggregator siap...")
    async with httpx.AsyncClient() as client:
        for attempt in range(30):
            try:
                resp = await client.get(f"{AGGREGATOR_URL}/health", timeout=3.0)
                if resp.status_code == 200:
                    logger.info("Aggregator siap!")
                    return
            except Exception:
                pass
            logger.info(f"Percobaan {attempt + 1}/30, tunggu 2 detik...")
            await asyncio.sleep(2)
    raise RuntimeError("Aggregator tidak siap setelah 60 detik")


if __name__ == "__main__":
    async def main():
        await wait_for_aggregator()
        await asyncio.sleep(2)  # Jeda kecil sebelum mulai
        await run_publisher()

    asyncio.run(main())