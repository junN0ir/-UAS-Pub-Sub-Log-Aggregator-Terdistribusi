import asyncpg
import os
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://loguser:logpass@storage:5432/logdb"
        )

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            dsn=self.database_url,
            min_size=2,
            max_size=20,
            command_timeout=30,
        )
        logger.info("Database connection pool berhasil dibuat")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def insert_event(self, topic: str, event_id: str, source: str,
                           timestamp: str, payload: dict) -> bool:
        """
        Insert event dengan transaksi atomik.

        Isolation level: READ COMMITTED (default PostgreSQL).
        Alasan: Unique constraint di level database sudah cukup mencegah
        race condition tanpa perlu SERIALIZABLE yang lebih mahal.
        Phantom reads tidak relevan karena kita hanya INSERT, bukan
        range scan. Write skew dimitigasi oleh unique constraint.

        Pola transaksi:
        1. BEGIN (isolation READ COMMITTED)
        2. INSERT events ON CONFLICT DO NOTHING → tahu apakah baru/duplikat
        3. INSERT audit_log → rekam setiap kejadian
        4. INSERT outbox → untuk outbox pattern (processed=false)
        5. UPDATE stats → counter transaksional anti lost-update
        6. COMMIT
        """
        async with self.pool.acquire() as conn:
            # Set isolation level secara eksplisit
            async with conn.transaction(isolation="read_committed"):

                # Langkah 1: Insert event utama
                result = await conn.fetchrow(
                    """
                    INSERT INTO events (topic, event_id, source, timestamp, payload)
                    VALUES ($1, $2, $3, $4::timestamptz, $5::jsonb)
                    ON CONFLICT ON CONSTRAINT uq_topic_event_id DO NOTHING
                    RETURNING id
                    """,
                    topic, event_id, source, timestamp, json.dumps(payload),
                )

                is_new = result is not None
                action = "accepted" if is_new else "duplicate"

                # Langkah 2: Tulis ke audit log (selalu, baru maupun duplikat)
                await conn.execute(
                    """
                    INSERT INTO audit_log (topic, event_id, source, action)
                    VALUES ($1, $2, $3, $4)
                    """,
                    topic, event_id, source, action,
                )

                # Langkah 3: Outbox pattern — hanya untuk event baru
                if is_new:
                    await conn.execute(
                        """
                        INSERT INTO outbox (topic, event_id, payload, processed)
                        VALUES ($1, $2, $3::jsonb, false)
                        """,
                        topic, event_id, json.dumps(payload),
                    )

                # Langkah 4: Update stats secara atomik
                # Menggunakan UPDATE SET col = col + 1 bukan SELECT + UPDATE
                # untuk mencegah lost-update saat multi-worker
                if is_new:
                    await conn.execute(
                        """
                        UPDATE stats
                        SET received = received + 1,
                            unique_processed = unique_processed + 1
                        WHERE id = 1
                        """
                    )
                    logger.info(f"[ACCEPTED] {topic}/{event_id} dari {source}")
                else:
                    await conn.execute(
                        """
                        UPDATE stats
                        SET received = received + 1,
                            duplicate_dropped = duplicate_dropped + 1
                        WHERE id = 1
                        """
                    )
                    logger.warning(f"[DUPLICATE] {topic}/{event_id} diabaikan")

                return is_new

    async def get_events(self, topic: Optional[str] = None,
                         limit: int = 100, offset: int = 0) -> list[dict]:
        async with self.pool.acquire() as conn:
            if topic:
                rows = await conn.fetch(
                    """
                    SELECT id, topic, event_id, source,
                           timestamp::text, payload::text, received_at::text
                    FROM events
                    WHERE topic = $1
                    ORDER BY received_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    topic, limit, offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, topic, event_id, source,
                           timestamp::text, payload::text, received_at::text
                    FROM events
                    ORDER BY received_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset,
                )
            return [dict(r) for r in rows]

    async def get_stats(self) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM stats WHERE id = 1")
            topics = await conn.fetch("SELECT DISTINCT topic FROM events ORDER BY topic")
            latest = await conn.fetchrow(
                """
                SELECT EXTRACT(EPOCH FROM (NOW() - timestamp))::float AS lag_seconds
                FROM events ORDER BY received_at DESC LIMIT 1
                """
            )
            return {
                "received": row["received"],
                "unique_processed": row["unique_processed"],
                "duplicate_dropped": row["duplicate_dropped"],
                "error_count": row["error_count"],
                "started_at": row["started_at"].isoformat(),
                "topics": [r["topic"] for r in topics],
                "lag_seconds": round(latest["lag_seconds"], 2) if latest else 0.0,
            }

    async def get_audit_log(self, limit: int = 50) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, topic, event_id, source, action, logged_at::text
                FROM audit_log
                ORDER BY logged_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    async def is_healthy(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False


db = Database()