"""SQL DB del sistema (Polyglot Persistence, Sección 4.4).

Guarda conversaciones y tickets (RF04, RF05-RF07), calificaciones de respuestas (RF09),
estadísticas (RF08), reseñas del lugar (RF11), errores del sistema y la base de
conocimiento, que es la fuente de verdad del catálogo (RF03).

La ruta de la base se toma de DATABASE_URL (por defecto ./data/chatbot_audit.db).
"""
import json
import logging
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

import config
from patterns import (
    ROUTED_BOT,
    ROUTED_HUMAN,
    ROUTED_HUMAN_RESOLVED,
    STATUS_ANSWERED,
    STATUS_PENDING_HUMAN,
    STATUS_RESOLVED_BY_HUMAN,
)

logger = logging.getLogger("Database")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _prepare_sqlite_path(url: str) -> None:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        directory = os.path.dirname(url[len("sqlite:///"):])
        if directory:
            os.makedirs(directory, exist_ok=True)


DATABASE_URL = config.DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")
if IS_SQLITE:
    _prepare_sqlite_path(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
)

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record):
        # WAL permite lecturas mientras se escribe (Sección 19.4)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False)
    user_type = Column(String(50), nullable=False, default="estudiante")
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    routed_to = Column(String(20), nullable=False, index=True)
    method = Column(String(20), nullable=True)
    kb_id = Column(String(50), nullable=True)
    response_time_ms = Column(Float, nullable=True)
    feedback = Column(Integer, nullable=True)  # 1 = útil, -1 = no útil (RF09)
    timestamp = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)


class SystemErrorLog(Base):
    __tablename__ = "system_errors"
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utcnow)


class PlaceReview(Base):
    __tablename__ = "place_reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(50), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(String(50), primary_key=True)
    category = Column(String(100), nullable=False)
    answer = Column(Text, nullable=False)
    questions = Column(Text, nullable=False)  # lista JSON
    keywords = Column(Text, nullable=False, default="[]")  # lista JSON
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AppMetadata(Base):
    __tablename__ = "app_metadata"
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


# Columnas agregadas después de la versión anterior. create_all() no modifica tablas que ya
# existen, así que se agregan aquí para que una base vieja siga funcionando.
_MIGRATIONS = {
    "conversation_logs": {
        "user_type": "VARCHAR(50) NOT NULL DEFAULT 'estudiante'",
        "method": "VARCHAR(20)",
        "kb_id": "VARCHAR(50)",
        "response_time_ms": "FLOAT",
        "feedback": "INTEGER",
        "resolved_at": "DATETIME",
    },
}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in _MIGRATIONS.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    logger.info("Migración: columna %s.%s agregada.", table, name)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _status_for(routed_to: str) -> str:
    return {
        ROUTED_BOT: STATUS_ANSWERED,
        ROUTED_HUMAN: STATUS_PENDING_HUMAN,
        ROUTED_HUMAN_RESOLVED: STATUS_RESOLVED_BY_HUMAN,
    }.get(routed_to, routed_to)


# ------------------------------------------------------------------ conversaciones y tickets
def save_log(user_id: str, user_type: str, query: str, response: str, score: float, routed_to: str,
             method: Optional[str] = None, kb_id: Optional[str] = None,
             response_time_ms: Optional[float] = None) -> int:
    with session_scope() as session:
        entry = ConversationLog(
            user_id=user_id,
            user_type=user_type,
            query=query,
            response=response,
            confidence_score=score,
            routed_to=routed_to,
            method=method,
            kb_id=kb_id,
            response_time_ms=response_time_ms,
        )
        session.add(entry)
        session.flush()
        return entry.id


def update_ticket(ticket_id: int, manual_response: str) -> str:
    """Devuelve 'resolved', 'not_found' o 'not_pending'."""
    with session_scope() as session:
        ticket = session.get(ConversationLog, ticket_id)
        if ticket is None:
            return "not_found"
        if ticket.routed_to != ROUTED_HUMAN:
            return "not_pending"
        ticket.response = manual_response
        ticket.routed_to = ROUTED_HUMAN_RESOLVED
        ticket.resolved_at = utcnow()
        return "resolved"


def get_ticket(ticket_id: int) -> Optional[dict]:
    with session_scope() as session:
        ticket = session.get(ConversationLog, ticket_id)
        if ticket is None:
            return None
        return {
            "ticket_id": ticket.id,
            "response": ticket.response,
            "routed_to": ticket.routed_to,
            "status": _status_for(ticket.routed_to),
        }


def get_escalated_tickets() -> List[dict]:
    """Tickets pendientes, del más antiguo al más reciente (orden de atención)."""
    with session_scope() as session:
        tickets = (
            session.query(ConversationLog)
            .filter(ConversationLog.routed_to == ROUTED_HUMAN)
            .order_by(ConversationLog.timestamp.asc())
            .all()
        )
        return [
            {
                "id": t.id,
                "user_id": t.user_id,
                "user_type": t.user_type,
                "query": t.query,
                "confidence_score": t.confidence_score,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in tickets
        ]


def save_feedback(ticket_id: int, helpful: bool) -> bool:
    with session_scope() as session:
        ticket = session.get(ConversationLog, ticket_id)
        if ticket is None:
            return False
        ticket.feedback = 1 if helpful else -1
        return True


# ------------------------------------------------------------------ estadísticas (RF08)
def _percentile(sorted_values: List[float], quantile: float) -> Optional[float]:
    if not sorted_values:
        return None
    index = max(0, math.ceil(quantile * len(sorted_values)) - 1)
    return round(sorted_values[index], 2)


def _summarize(rows: List[tuple]) -> dict:
    total = len(rows)
    answered = sum(1 for r in rows if r[1] == ROUTED_BOT)
    resolved = sum(1 for r in rows if r[1] == ROUTED_HUMAN_RESOLVED)
    pending = sum(1 for r in rows if r[1] == ROUTED_HUMAN)
    escalated = resolved + pending
    confidences = [r[2] for r in rows if r[2] is not None]
    times = sorted(r[3] for r in rows if r[3] is not None)
    return {
        "total": total,
        "answered_by_bot": answered,
        "escalated": escalated,
        "resolved_by_human": resolved,
        "pending": pending,
        "escalation_rate": round(escalated / total, 4) if total else 0.0,
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "avg_response_ms": round(sum(times) / len(times), 2) if times else None,
        "p95_response_ms": _percentile(times, 0.95),
        "positive_feedback": sum(1 for r in rows if r[4] == 1),
        "negative_feedback": sum(1 for r in rows if r[4] == -1),
    }


def get_user_stats() -> dict:
    with session_scope() as session:
        rows = [
            tuple(row)
            for row in session.query(
                ConversationLog.user_type,
                ConversationLog.routed_to,
                ConversationLog.confidence_score,
                ConversationLog.response_time_ms,
                ConversationLog.feedback,
            ).all()
        ]
    groups: Dict[str, List[tuple]] = {}
    for row in rows:
        groups.setdefault(row[0] or "desconocido", []).append(row)
    return {
        "overall": _summarize(rows),
        "by_user_type": [{"user_type": user_type, **_summarize(items)}
                         for user_type, items in sorted(groups.items())],
    }


# ------------------------------------------------------------------ errores del sistema
def log_system_error(endpoint: str, error_message: str) -> None:
    with session_scope() as session:
        session.add(SystemErrorLog(endpoint=endpoint[:100], error_message=error_message))


def get_system_errors(limit: int = 50) -> List[dict]:
    with session_scope() as session:
        errors = session.query(SystemErrorLog).order_by(SystemErrorLog.timestamp.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "endpoint": e.endpoint,
                "error_message": e.error_message,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in errors
        ]


# ------------------------------------------------------------------ reseñas del lugar (RF11)
def save_review(user_type: str, rating: int, comment: str) -> int:
    with session_scope() as session:
        review = PlaceReview(user_type=user_type, rating=rating, comment=comment or None)
        session.add(review)
        session.flush()
        return review.id


def get_reviews() -> List[dict]:
    with session_scope() as session:
        reviews = session.query(PlaceReview).order_by(PlaceReview.timestamp.desc()).all()
        return [
            {
                "id": r.id,
                "user_type": r.user_type,
                "rating": r.rating,
                "comment": r.comment,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in reviews
        ]


# ------------------------------------------------------------------ base de conocimiento (RF03)
def _clean_list(values: Iterable[str]) -> List[str]:
    cleaned, seen = [], set()
    for value in values or []:
        value = str(value).strip()
        if value and value.lower() not in seen:
            cleaned.append(value)
            seen.add(value.lower())
    return cleaned


def _kb_to_dict(row: KnowledgeEntry) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "answer": row.answer,
        "questions": json.loads(row.questions or "[]"),
        "keywords": json.loads(row.keywords or "[]"),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_kb_entries() -> List[dict]:
    with session_scope() as session:
        return [_kb_to_dict(row) for row in session.query(KnowledgeEntry).order_by(KnowledgeEntry.id).all()]


def get_kb_entry(kb_id: str) -> Optional[dict]:
    with session_scope() as session:
        row = session.get(KnowledgeEntry, kb_id)
        return _kb_to_dict(row) if row else None


def create_kb_entry(data: dict) -> dict:
    """Crea una entrada; lanza ValueError si el id ya existe."""
    with session_scope() as session:
        if session.get(KnowledgeEntry, data["id"]) is not None:
            raise ValueError(f"Ya existe una entrada con id '{data['id']}'.")
        row = KnowledgeEntry(
            id=data["id"],
            category=data["category"].strip(),
            answer=data["answer"].strip(),
            questions=json.dumps(_clean_list(data["questions"]), ensure_ascii=False),
            keywords=json.dumps(_clean_list(data.get("keywords", [])), ensure_ascii=False),
        )
        session.add(row)
        session.flush()
        return _kb_to_dict(row)


def update_kb_entry(kb_id: str, data: dict) -> Optional[dict]:
    with session_scope() as session:
        row = session.get(KnowledgeEntry, kb_id)
        if row is None:
            return None
        row.category = data["category"].strip()
        row.answer = data["answer"].strip()
        row.questions = json.dumps(_clean_list(data["questions"]), ensure_ascii=False)
        row.keywords = json.dumps(_clean_list(data.get("keywords", [])), ensure_ascii=False)
        row.updated_at = utcnow()
        session.flush()
        return _kb_to_dict(row)


def delete_kb_entry(kb_id: str) -> bool:
    with session_scope() as session:
        row = session.get(KnowledgeEntry, kb_id)
        if row is None:
            return False
        session.delete(row)
        return True


def get_metadata(key: str) -> Optional[str]:
    with session_scope() as session:
        row = session.get(AppMetadata, key)
        return row.value if row else None


def set_metadata(key: str, value: str) -> None:
    with session_scope() as session:
        row = session.get(AppMetadata, key)
        if row is None:
            session.add(AppMetadata(key=key, value=value))
        else:
            row.value = value


def _row_from_entry(entry: dict) -> dict:
    return {
        "category": entry["category"],
        "answer": entry["answer"],
        "questions": json.dumps(_clean_list(entry["questions"]), ensure_ascii=False),
        "keywords": json.dumps(_clean_list(entry.get("keywords", [])), ensure_ascii=False),
    }


def sync_default_kb(entries: List[dict], version: str) -> dict:
    """Carga o actualiza las entradas predeterminadas cuando cambia KB_SEED_VERSION.

    - Base vacía: inserta todas las entradas.
    - Versión distinta: reemplaza las entradas predeterminadas con su nuevo contenido y borra las
      que eran predeterminadas en la versión anterior y ya no existen. Las entradas creadas por el
      Administrador (ids que nunca fueron predeterminados) no se tocan.
    - Misma versión: no hace nada, para respetar las ediciones hechas desde el panel.
    """
    new_ids = [entry["id"] for entry in entries]
    stored_version = get_metadata("kb_seed_version")
    previous_ids = json.loads(get_metadata("kb_seed_ids") or "[]")
    summary = {"version": version, "previous_version": stored_version, "inserted": [], "updated": [], "removed": []}

    if stored_version == version:
        return summary

    with session_scope() as session:
        for entry in entries:
            row = session.get(KnowledgeEntry, entry["id"])
            if row is None:
                session.add(KnowledgeEntry(id=entry["id"], **_row_from_entry(entry)))
                summary["inserted"].append(entry["id"])
            else:
                for field, value in _row_from_entry(entry).items():
                    setattr(row, field, value)
                row.updated_at = utcnow()
                summary["updated"].append(entry["id"])
        for old_id in set(previous_ids) - set(new_ids):
            row = session.get(KnowledgeEntry, old_id)
            if row is not None:
                session.delete(row)
                summary["removed"].append(old_id)

    set_metadata("kb_seed_version", version)
    set_metadata("kb_seed_ids", json.dumps(new_ids))
    return summary


def seed_kb_if_empty(entries: Iterable[dict]) -> int:
    """Llena la base de conocimiento con los datos iniciales solo si está vacía."""
    with session_scope() as session:
        if session.query(KnowledgeEntry).count() > 0:
            return 0
        added = 0
        for entry in entries:
            session.add(KnowledgeEntry(
                id=entry["id"],
                category=entry["category"],
                answer=entry["answer"],
                questions=json.dumps(_clean_list(entry["questions"]), ensure_ascii=False),
                keywords=json.dumps(_clean_list(entry.get("keywords", [])), ensure_ascii=False),
            ))
            added += 1
        return added


init_db()
