from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("instance/provenance_guard.sqlite3")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuditStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS contents (
                    content_id TEXT PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    attribution TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    ai_probability REAL NOT NULL,
                    label_variant TEXT NOT NULL,
                    label_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    creator_id TEXT,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def save_submission(self, record: dict[str, Any]) -> None:
        now = record.get("timestamp", utc_now())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO contents (
                    content_id, creator_id, text, attribution, confidence,
                    ai_probability, label_variant, label_text, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["content_id"],
                    record["creator_id"],
                    record["text"],
                    record["attribution"],
                    record["confidence"],
                    record["ai_probability"],
                    record["label_variant"],
                    record["label_text"],
                    "classified",
                    now,
                    now,
                ),
            )
            self._insert_audit_event(connection, "classification", record["content_id"], record["creator_id"], record)

    def get_content(self, content_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM contents WHERE content_id = ?", (content_id,)).fetchone()
        return dict(row) if row else None

    def save_appeal(self, content_id: str, creator_reasoning: str) -> dict[str, Any]:
        content = self.get_content(content_id)
        if content is None:
            raise KeyError(content_id)

        now = utc_now()
        appeal_record = {
            "content_id": content_id,
            "creator_id": content["creator_id"],
            "timestamp": now,
            "status": "under_review",
            "appeal_reasoning": creator_reasoning,
            "original_attribution": content["attribution"],
            "original_confidence": content["confidence"],
            "original_ai_probability": content["ai_probability"],
        }
        with self.connect() as connection:
            connection.execute(
                "UPDATE contents SET status = ?, updated_at = ? WHERE content_id = ?",
                ("under_review", now, content_id),
            )
            self._insert_audit_event(connection, "appeal", content_id, content["creator_id"], appeal_record)
        return appeal_record

    def recent_events(self, limit: int = 25) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        events = []
        for row in rows:
            payload = json.loads(row["payload"])
            payload["event_type"] = row["event_type"]
            events.append(payload)
        return events

    def _insert_audit_event(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        content_id: str,
        creator_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        timestamp = payload.get("timestamp", utc_now())
        connection.execute(
            """
            INSERT INTO audit_events (event_type, content_id, creator_id, timestamp, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, content_id, creator_id, timestamp, json.dumps(payload, sort_keys=True)),
        )

