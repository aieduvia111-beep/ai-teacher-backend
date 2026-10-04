"""Minimalny, tylko-do-odczytu endpoint administracyjny do sprawdzania
telemetrii generowania (GenerationRequestLog) bez logowania sie
bezposrednio do bazy produkcyjnej. Chroniony osobnym kluczem (ADMIN_STATS_KEY),
tak samo jak istniejacy wzorzec w api/affiliates.py (AFFILIATE_ADMIN_KEY)."""
import hmac
import os

from fastapi import APIRouter
from sqlalchemy import func

from ..database import SessionLocal
from ..models import GenerationRequestLog, NotesCache, NotesReport

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/generation-stats")
def generation_stats(admin_key: str, feature: str = None, limit: int = 20):
    expected = os.environ.get("ADMIN_STATS_KEY", "")
    if not expected or admin_key != expected:
        return {"success": False, "error": "Brak uprawnien - wymagany poprawny admin_key"}

    db = SessionLocal()
    try:
        q = db.query(GenerationRequestLog)
        if feature:
            q = q.filter(GenerationRequestLog.feature == feature)

        total = q.count()
        agg = q.with_entities(
            func.sum(GenerationRequestLog.requested_count),
            func.sum(GenerationRequestLog.accepted_count),
            func.sum(GenerationRequestLog.rejected_count),
            func.sum(GenerationRequestLog.retry_count),
            func.avg(GenerationRequestLog.total_time),
        ).first()

        recent = (
            q.order_by(GenerationRequestLog.created_at.desc())
            .limit(min(limit, 100))
            .all()
        )

        return {
            "success": True,
            "total_rows": total,
            "totals": {
                "requested": int(agg[0] or 0),
                "accepted": int(agg[1] or 0),
                "rejected": int(agg[2] or 0),
                "retries": int(agg[3] or 0),
                "avg_time_seconds": round(agg[4], 2) if agg[4] else 0,
            },
            "recent": [
                {
                    "id": r.id,
                    "feature": r.feature,
                    "temat": r.temat,
                    "trudnosc": r.trudnosc,
                    "poziom": r.poziom,
                    "requested": r.requested_count,
                    "accepted": r.accepted_count,
                    "rejected": r.rejected_count,
                    "retries": r.retry_count,
                    "time_s": round(r.total_time, 1) if r.total_time else None,
                    "rejection_reasons": r.rejection_reasons,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recent
            ],
        }
    finally:
        db.close()


@router.get("/notes-reports")
def notes_reports(admin_key: str, limit: int = 50):
    """Zgloszenia bledow w notatkach + statystyki pamieci notatek (03.10.2026). Ten sam klucz
    (ADMIN_STATS_KEY) co /admin/generation-stats. Tylko odczyt."""
    expected = os.environ.get("ADMIN_STATS_KEY", "")
    if not expected or not hmac.compare_digest(str(admin_key), expected):
        return {"success": False, "error": "Brak uprawnien - wymagany poprawny admin_key"}
    db = SessionLocal()
    try:
        total_reports = db.query(NotesReport).count()
        by_topic = (
            db.query(NotesReport.temat, func.count(NotesReport.id).label("c"), func.max(NotesReport.created_at))
            .group_by(NotesReport.temat)
            .order_by(func.count(NotesReport.id).desc())
            .limit(30)
            .all()
        )
        recent = (
            db.query(NotesReport).order_by(NotesReport.created_at.desc()).limit(max(1, min(limit, 200))).all()
        )
        cache_entries = db.query(NotesCache).count()
        cache_hits = db.query(func.coalesce(func.sum(NotesCache.hits), 0)).scalar() or 0
        top_cached = db.query(NotesCache).order_by(NotesCache.hits.desc()).limit(10).all()
        return {
            "success": True,
            "zgloszen_lacznie": total_reports,
            "pamiec_notatek": {
                "notatek_w_pamieci": cache_entries,
                "trafien_lacznie": int(cache_hits),
                "najczesciej_uzywane": [{"temat": r.temat, "klasa": r.klasa, "trafien": r.hits} for r in top_cached],
            },
            "tematy_z_najwieksza_liczba_zgloszen": [
                {"temat": t, "zgloszen": int(c), "ostatnie": str(last)} for t, c, last in by_topic
            ],
            "ostatnie_zgloszenia": [
                {"temat": r.temat, "komentarz": r.comment, "kiedy": str(r.created_at)} for r in recent
            ],
        }
    finally:
        db.close()
