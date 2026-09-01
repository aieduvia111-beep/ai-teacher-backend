"""Minimalny, tylko-do-odczytu endpoint administracyjny do sprawdzania
telemetrii generowania (GenerationRequestLog) bez logowania sie
bezposrednio do bazy produkcyjnej. Chroniony osobnym kluczem (ADMIN_STATS_KEY),
tak samo jak istniejacy wzorzec w api/affiliates.py (AFFILIATE_ADMIN_KEY)."""
import os

from fastapi import APIRouter
from sqlalchemy import func

from ..database import SessionLocal
from ..models import GenerationRequestLog

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/generation-stats")
def generation_stats(admin_key: str, feature: str = None, limit: int = 20):
    expected = os.environ.get("ADMIN_STATS_KEY", "")
    if not expected or admin_key != expected:
        # TYMCZASOWA DIAGNOSTYKA (do usuniecia po ustaleniu przyczyny
        # niezgodnosci klucza) - dlugosc/reprezentacja obu wartosci,
        # NIGDY sama wartosc sekretu.
        return {
            "success": False,
            "error": "Brak uprawnien - wymagany poprawny admin_key",
            "debug_expected_len": len(expected),
            "debug_received_len": len(admin_key),
            "debug_expected_repr": repr(expected),
            "debug_received_repr": repr(admin_key),
        }

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
