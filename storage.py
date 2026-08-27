from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "data" / "decision_records.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DecisionRecordSummary:
    id: int
    scene_name: str
    decision_mode: str
    best_agent: str
    best_strategy: str
    created_at: str


@dataclass(frozen=True)
class DecisionRecordDetail:
    id: int
    scene: Dict[str, Any]
    result: Dict[str, Any]
    scene_name: str
    decision_mode: str
    best_agent: str
    best_strategy: str
    created_at: str


@dataclass(frozen=True)
class MemoryEntryRecord:
    id: int
    record_id: int
    scene: Dict[str, Any]
    scene_name: str
    best_agent: str
    best_strategy: str
    risk_level: str
    summary: str
    lessons: List[str]
    tags: List[str]
    importance_score: float
    write_policy: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "scene": self.scene,
            "scene_name": self.scene_name,
            "best_agent": self.best_agent,
            "best_strategy": self.best_strategy,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "lessons": self.lessons,
            "tags": self.tags,
            "importance_score": round(self.importance_score, 2),
            "write_policy": self.write_policy,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class EvaluationReportSummaryRecord:
    id: int
    report_type: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_type": self.report_type,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class EvaluationReportDetailRecord(EvaluationReportSummaryRecord):
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["summary"] = self.summary
        return data


class DecisionRecordStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scene_name TEXT NOT NULL,
                    decision_mode TEXT NOT NULL,
                    best_agent TEXT NOT NULL,
                    best_strategy TEXT NOT NULL,
                    scene_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_decision_records_created_at
                ON decision_records(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL UNIQUE,
                    scene_name TEXT NOT NULL,
                    best_agent TEXT NOT NULL,
                    best_strategy TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    lessons_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    importance_score REAL NOT NULL,
                    write_policy TEXT NOT NULL,
                    scene_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_memory_entries_created_at
                ON agent_memory_entries(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_memory_entries_record_id
                ON agent_memory_entries(record_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_type TEXT NOT NULL,
                    total_cases INTEGER NOT NULL,
                    passed_cases INTEGER NOT NULL,
                    pass_rate REAL NOT NULL,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evaluation_reports_type_created_at
                ON evaluation_reports(report_type, created_at DESC)
                """
            )

    def save_decision(self, scene: Dict[str, Any], result: Dict[str, Any]) -> int:
        best = result["best"]["proposal"]
        created_at = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO decision_records (
                    scene_name,
                    decision_mode,
                    best_agent,
                    best_strategy,
                    scene_json,
                    result_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(scene["name"]),
                    str(result["decision_mode"]),
                    str(best["agent_name"]),
                    str(best["strategy_name"]),
                    json.dumps(scene, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def list_records(self, limit: int = 20) -> List[DecisionRecordSummary]:
        bounded_limit = max(1, min(limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, scene_name, decision_mode, best_agent, best_strategy, created_at
                FROM decision_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [
            DecisionRecordSummary(
                id=int(row["id"]),
                scene_name=str(row["scene_name"]),
                decision_mode=str(row["decision_mode"]),
                best_agent=str(row["best_agent"]),
                best_strategy=str(row["best_strategy"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def get_record(self, record_id: int) -> DecisionRecordDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, scene_name, decision_mode, best_agent, best_strategy, scene_json, result_json, created_at
                FROM decision_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return DecisionRecordDetail(
            id=int(row["id"]),
            scene=json.loads(str(row["scene_json"])),
            result=json.loads(str(row["result_json"])),
            scene_name=str(row["scene_name"]),
            decision_mode=str(row["decision_mode"]),
            best_agent=str(row["best_agent"]),
            best_strategy=str(row["best_strategy"]),
            created_at=str(row["created_at"]),
        )

    def save_memory_entry(
        self,
        *,
        record_id: int,
        scene: Dict[str, Any],
        summary: str,
        lessons: List[str],
        tags: List[str],
        risk_level: str,
        best_agent: str,
        best_strategy: str,
        importance_score: float,
        write_policy: str,
    ) -> int:
        created_at = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO agent_memory_entries (
                    id,
                    record_id,
                    scene_name,
                    best_agent,
                    best_strategy,
                    risk_level,
                    summary,
                    lessons_json,
                    tags_json,
                    importance_score,
                    write_policy,
                    scene_json,
                    created_at
                )
                VALUES (
                    (SELECT id FROM agent_memory_entries WHERE record_id = ?),
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    record_id,
                    record_id,
                    str(scene.get("name", "")),
                    best_agent,
                    best_strategy,
                    risk_level,
                    summary,
                    json.dumps(lessons, ensure_ascii=False),
                    json.dumps(tags, ensure_ascii=False),
                    float(importance_score),
                    write_policy,
                    json.dumps(scene, ensure_ascii=False),
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def list_memory_entries(self, limit: int = 20) -> List[MemoryEntryRecord]:
        bounded_limit = max(1, min(limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    record_id,
                    scene_name,
                    best_agent,
                    best_strategy,
                    risk_level,
                    summary,
                    lessons_json,
                    tags_json,
                    importance_score,
                    write_policy,
                    scene_json,
                    created_at
                FROM agent_memory_entries
                ORDER BY id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [
            MemoryEntryRecord(
                id=int(row["id"]),
                record_id=int(row["record_id"]),
                scene=json.loads(str(row["scene_json"])),
                scene_name=str(row["scene_name"]),
                best_agent=str(row["best_agent"]),
                best_strategy=str(row["best_strategy"]),
                risk_level=str(row["risk_level"]),
                summary=str(row["summary"]),
                lessons=_loads_list(row["lessons_json"]),
                tags=_loads_list(row["tags_json"]),
                importance_score=float(row["importance_score"]),
                write_policy=str(row["write_policy"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def save_evaluation_report(self, *, report_type: str, summary: Dict[str, Any]) -> int:
        total_cases = int(summary.get("total_cases", 0))
        passed_cases = int(summary.get("passed_cases", 0))
        pass_rate = float(summary.get("pass_rate", _pass_rate(passed_cases, total_cases)))
        created_at = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluation_reports (
                    report_type,
                    total_cases,
                    passed_cases,
                    pass_rate,
                    summary_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(report_type),
                    total_cases,
                    passed_cases,
                    pass_rate,
                    json.dumps(summary, ensure_ascii=False),
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def list_evaluation_reports(
        self,
        *,
        report_type: str | None = None,
        limit: int = 20,
    ) -> List[EvaluationReportSummaryRecord]:
        bounded_limit = max(1, min(limit, 100))
        query = """
            SELECT id, report_type, total_cases, passed_cases, pass_rate, created_at
            FROM evaluation_reports
        """
        params: tuple[Any, ...]
        if report_type:
            query += " WHERE report_type = ?"
            params = (report_type, bounded_limit)
        else:
            params = (bounded_limit,)
        query += " ORDER BY id DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            EvaluationReportSummaryRecord(
                id=int(row["id"]),
                report_type=str(row["report_type"]),
                total_cases=int(row["total_cases"]),
                passed_cases=int(row["passed_cases"]),
                pass_rate=float(row["pass_rate"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def get_evaluation_report(self, report_id: int) -> EvaluationReportDetailRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, report_type, total_cases, passed_cases, pass_rate, summary_json, created_at
                FROM evaluation_reports
                WHERE id = ?
                """,
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        return EvaluationReportDetailRecord(
            id=int(row["id"]),
            report_type=str(row["report_type"]),
            total_cases=int(row["total_cases"]),
            passed_cases=int(row["passed_cases"]),
            pass_rate=float(row["pass_rate"]),
            summary=json.loads(str(row["summary_json"])),
            created_at=str(row["created_at"]),
        )


def _loads_list(value: Any) -> List[str]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _pass_rate(passed_cases: int, total_cases: int) -> float:
    if total_cases <= 0:
        return 0.0
    return passed_cases / total_cases
