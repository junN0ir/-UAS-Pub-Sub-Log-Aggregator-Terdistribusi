import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from schemas import (
    AuditEntry,
    BatchEventIn,
    EventIn,
    EventOut,
    PublishResult,
    StatsOut,
)

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from database import db
from schemas import (
    BatchEventIn,
    EventIn,
    EventOut,
    PublishResult,
    StatsOut,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aggregator")

START_TIME = time.time()
def parse_timestamp(value):
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    raise ValueError(f"Format timestamp tidak valid: {value}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan handler: jalankan setup saat startup,
    cleanup saat shutdown.
    """
    logger.info("Aggregator starting up...")
    await db.connect()
    logger.info("Aggregator ready!")
    yield
    logger.info("Aggregator shutting down...")
    await db.disconnect()


app = FastAPI(
    title="Pub-Sub Log Aggregator",
    description="Sistem aggregasi log terdistribusi dengan idempotent consumer dan deduplication",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint untuk Docker Compose healthcheck.
    Digunakan agar service lain tahu aggregator sudah siap.
    """
    db_ok = await db.is_healthy()
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database tidak dapat dijangkau")
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/publish", response_model=PublishResult)
async def publish_event(event: EventIn):
    """
    Publish satu event.
    
    Idempotent: mengirim event yang sama berkali-kali
    hanya menghasilkan satu penyimpanan.
    """
    try:
        is_new = await db.insert_event(
            topic=event.topic,
            event_id=event.event_id,
            source=event.source,
            timestamp=parse_timestamp(event.timestamp),
            payload=event.payload,
        )
        return PublishResult(
            status="ok",
            accepted=1 if is_new else 0,
            duplicates=0 if is_new else 1,
            errors=0,
        )
    except Exception as e:
        logger.error(f"Error saat publish: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/publish/batch", response_model=PublishResult)
async def publish_batch(batch: BatchEventIn):
    """
    Publish banyak event sekaligus secara paralel.
    
    Setiap event diproses independen secara idempotent.
    Jika satu event gagal, event lain tetap diproses.
    """
    accepted = 0
    duplicates = 0
    errors = 0

    # Proses semua event secara concurrent dengan asyncio.gather
    tasks = [
        db.insert_event(
            topic=e.topic,
            event_id=e.event_id,
            source=e.source,
            timestamp=parse_timestamp(e.timestamp),
            payload=e.payload,
        )
        for e in batch.events
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            errors += 1
            logger.error(f"Error batch processing: {result}")
        elif result:
            accepted += 1
        else:
            duplicates += 1

    return PublishResult(
        status="ok",
        accepted=accepted,
        duplicates=duplicates,
        errors=errors,
    )


@app.get("/events", response_model=list[EventOut])
async def get_events(
    topic: str | None = Query(default=None, description="Filter berdasarkan topic"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    Ambil daftar event yang sudah diproses.
    Opsional filter berdasarkan topic.
    """
    import json

    rows = await db.get_events(topic=topic, limit=limit, offset=offset)
    return [
        EventOut(
            id=r["id"],
            topic=r["topic"],
            event_id=r["event_id"],
            source=r["source"],
            timestamp=r["timestamp"],
            payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            received_at=r["received_at"],
        )
        for r in rows
    ]


@app.get("/stats", response_model=StatsOut)
async def get_stats():
    """
    Ambil statistik agregat sistem.
    """
    stats = await db.get_stats()
    uptime = time.time() - START_TIME
    received = stats["received"]
    dup_rate = (stats["duplicate_dropped"] / received * 100) if received > 0 else 0.0

    return StatsOut(
        received=received,
        unique_processed=stats["unique_processed"],
        duplicate_dropped=stats["duplicate_dropped"],
        error_count=stats.get("error_count", 0),
        topics=stats["topics"],
        uptime_seconds=round(uptime, 2),
        duplicate_rate_percent=round(dup_rate, 2),
        lag_seconds=stats.get("lag_seconds", 0),
    )

@app.get("/audit", response_model=list[AuditEntry])
async def get_audit_log(limit: int = Query(default=50, ge=1, le=500)):
    """
    Audit log: rekam semua event masuk termasuk duplikat.
    Berguna untuk debugging dan verifikasi idempotency.
    """
    rows = await db.get_audit_log(limit=limit)
    return [AuditEntry(**r) for r in rows]


@app.get("/stats", response_model=StatsOut)
async def get_stats():
    stats = await db.get_stats()
    uptime = time.time() - START_TIME
    received = stats["received"]
    dup_rate = (stats["duplicate_dropped"] / received * 100) if received > 0 else 0.0

    return StatsOut(
        received=received,
        unique_processed=stats["unique_processed"],
        duplicate_dropped=stats["duplicate_dropped"],
        error_count=stats["error_count"],
        topics=stats["topics"],
        uptime_seconds=round(uptime, 2),
        duplicate_rate_percent=round(dup_rate, 2),
        lag_seconds=stats["lag_seconds"],
    )

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8080"))
    workers = int(os.getenv("WORKER_COUNT", "4"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
    )