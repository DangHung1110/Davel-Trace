"""Append-only SQLite evidence store for accepted plans and shadow runs."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4


SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


class AcceptanceStore:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS acceptance_records (
                    acceptance_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    itinerary_id TEXT NOT NULL,
                    trip_id TEXT NOT NULL,
                    parent_acceptance_id TEXT,
                    selected_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    data_version TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    gate_json TEXT NOT NULL,
                    deterministic_rank INTEGER,
                    deterministic_score REAL,
                    shadow_observation_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_acceptance_trip_time
                  ON acceptance_records(trip_id, selected_at DESC);
                CREATE TABLE IF NOT EXISTS shadow_observations (
                    observation_id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data_version TEXT NOT NULL,
                    candidate_ids_json TEXT NOT NULL,
                    forward_json TEXT NOT NULL,
                    reverse_json TEXT NOT NULL,
                    consensus_json TEXT NOT NULL,
                    deterministic_top_id TEXT,
                    shadow_top_id TEXT,
                    swap_consistent INTEGER NOT NULL,
                    length_correlation REAL,
                    veto_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    latency_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_shadow_trip_time
                  ON shadow_observations(trip_id, created_at DESC);
                """
            )

    @staticmethod
    def _decode_acceptance(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)
        for source, target in (
            ("request_json", "request"),
            ("plan_json", "plan"),
            ("gate_json", "gate"),
        ):
            out[target] = json.loads(out.pop(source))
        return out

    @staticmethod
    def _decode_shadow(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)
        for source, target in (
            ("candidate_ids_json", "candidate_ids"),
            ("forward_json", "forward"),
            ("reverse_json", "reverse"),
            ("consensus_json", "consensus"),
        ):
            out[target] = json.loads(out.pop(source))
        out["swap_consistent"] = bool(out["swap_consistent"])
        return out

    def save_acceptance(self, *, idempotency_key: str,
                        itinerary_id: str, trip_id: str,
                        data_version: str, request: dict, plan: dict,
                        gate: dict, deterministic_rank: int | None = None,
                        deterministic_score: float | None = None,
                        parent_acceptance_id: str | None = None,
                        shadow_observation_id: str | None = None) -> dict:
        key = str(idempotency_key or "").strip()
        if not 8 <= len(key) <= 128:
            raise ValueError("idempotency_key phai dai 8-128 ky tu")
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT * FROM acceptance_records WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                return self._decode_acceptance(existing)
            acceptance_id = str(uuid4())
            conn.execute(
                """INSERT INTO acceptance_records (
                  acceptance_id,idempotency_key,itinerary_id,trip_id,
                  parent_acceptance_id,selected_at,schema_version,data_version,
                  request_json,plan_json,gate_json,deterministic_rank,
                  deterministic_score,shadow_observation_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    acceptance_id, key, itinerary_id, trip_id,
                    parent_acceptance_id, _utc_now(), SCHEMA_VERSION,
                    data_version, _json(request), _json(plan), _json(gate),
                    deterministic_rank, deterministic_score,
                    shadow_observation_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM acceptance_records WHERE acceptance_id = ?",
                (acceptance_id,),
            ).fetchone()
        return self._decode_acceptance(row)

    def get_acceptance(self, acceptance_id: str) -> dict | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM acceptance_records WHERE acceptance_id = ?",
                (acceptance_id,),
            ).fetchone()
        return self._decode_acceptance(row)

    def list_acceptances(self, trip_id: str | None = None,
                         limit: int = 50) -> list[dict]:
        limit = max(1, min(200, int(limit)))
        with self._connection() as conn:
            if trip_id:
                rows = conn.execute(
                    """SELECT * FROM acceptance_records WHERE trip_id = ?
                    ORDER BY selected_at DESC, rowid DESC LIMIT ?""",
                    (trip_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM acceptance_records
                    ORDER BY selected_at DESC, rowid DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [self._decode_acceptance(row) for row in rows]

    def count_acceptances(self) -> int:
        with self._connection() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM acceptance_records"
            ).fetchone()[0])

    def save_shadow(self, observation: dict) -> dict:
        observation_id = observation.get("observation_id") or str(uuid4())
        created_at = observation.get("created_at") or _utc_now()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO shadow_observations (
                  observation_id,trip_id,created_at,data_version,
                  candidate_ids_json,forward_json,reverse_json,consensus_json,
                  deterministic_top_id,shadow_top_id,swap_consistent,
                  length_correlation,veto_count,status,latency_ms
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    observation_id, observation.get("trip_id", ""), created_at,
                    observation.get("data_version", ""),
                    _json(observation.get("candidate_ids", [])),
                    _json(observation.get("forward", {})),
                    _json(observation.get("reverse", {})),
                    _json(observation.get("consensus", {})),
                    observation.get("deterministic_top_id"),
                    observation.get("shadow_top_id"),
                    int(bool(observation.get("swap_consistent"))),
                    observation.get("length_correlation"),
                    int(observation.get("veto_count") or 0),
                    observation.get("status", "skipped"),
                    observation.get("latency_ms"),
                ),
            )
            row = conn.execute(
                "SELECT * FROM shadow_observations WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
        return self._decode_shadow(row)

    def list_shadows(self, limit: int = 1000) -> list[dict]:
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT * FROM shadow_observations
                ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (max(1, min(5000, int(limit))),),
            ).fetchall()
        return [self._decode_shadow(row) for row in rows]
