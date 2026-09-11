"""ANALITYKA LEJKA "Kup Pro" (11.09.2026) - patrz FunnelEvent w models.py
dla pelnego uzasadnienia. Minimalny, wlasny tracking (bez Google
Analytics/Mixpanel/Plausible - zero konta zewnetrznego do zakladania),
zeby "gdzie userzy odpadaja przy platnosci" bylo pytaniem z odpowiedzia
z bazy, nie zgadywaniem z czytania kodu."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import FunnelEvent
from ..config import settings

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Whitelist celowo WASKA - to NIE jest ogolny "wyslij cokolwiek" endpoint
# (bylby otwartym zaproszeniem do zapychania bazy smieciowymi wierszami
# przez kogokolwiek, kto zajrzy do zrodla pricing.html). Rozszerzac TYLKO
# gdy faktycznie dodaje sie nowy, konkretny punkt pomiaru we froncie.
_ALLOWED_EVENTS = {
    "view_pricing", "click_upgrade", "payment_success",
    "payment_cancelled", "blik_setup_cancelled",
}


class TrackEventRequest(BaseModel):
    event: str
    # user_id NIEWERYFIKOWANY (brak wymogu Firebase tokenu) - celowo, zeby
    # dzialalo tez na pricing.html PRZED zalogowaniem. To czysto
    # obserwacyjne dane, nigdy nie uzywane do egzekwowania dostepu/platnosci,
    # wiec zaufanie klientowi co do samego user_id jest tu akceptowalne.
    user_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@router.post("/track")
def track_event(request: TrackEventRequest, db: Session = Depends(get_db)):
    """Fire-and-forget - front wywoluje to bez czekania na wynik (patrz
    trackEvent() w pricing.html). Nieznany event -> cichy no-op (fail
    quiet, nie chcemy zeby literowka w kodzie frontu kiedykolwiek
    wywalila UI usera)."""
    if request.event not in _ALLOWED_EVENTS:
        return {"success": False, "ignored": True}
    try:
        db.add(FunnelEvent(event=request.event, user_id=request.user_id, meta=request.meta or {}))
        db.commit()
    except Exception as e:
        print(f"[analytics] blad zapisu eventu '{request.event}': {e}")
        return {"success": False}
    return {"success": True}


@router.get("/funnel-summary")
def funnel_summary(key: str = "", days: int = 30, db: Session = Depends(get_db)):
    """Agregaty (liczba eventow danego typu w ostatnich N dniach) - zero
    PII w odpowiedzi, ale i tak fail-closed za sekretem
    (ANALYTICS_ADMIN_KEY w .env) - to sa surowe liczby biznesowe
    ('ile osob kliknelo Kup Pro'), nie powinny wisiec publicznie bez klucza."""
    if not settings.ANALYTICS_ADMIN_KEY or key != settings.ANALYTICS_ADMIN_KEY:
        return {"success": False, "error": "Brak lub bledny klucz dostepu"}

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(FunnelEvent.event, func.count(FunnelEvent.id))
        .filter(FunnelEvent.created_at >= cutoff)
        .group_by(FunnelEvent.event)
        .all()
    )
    counts = {event: count for event, count in rows}
    return {"success": True, "days": days, "counts": counts}
