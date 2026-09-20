# -*- coding: utf-8 -*-
"""Offline: endpointy ankiety po anulowaniu (zapis, walidacja, dedup, raport pod kluczem)."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import Subscription, CancellationFeedback
import app.api.payments as pay
from app.config import settings

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

U = {"uid": "uid_f1"}
db.add(Subscription(user_id="uid_f1", stripe_subscription_id="sub_f1", status="trialing")); db.commit()

r = pay.cancellation_feedback(pay.CancellationFeedbackRequest(reason="price", details="  za drogo dla mnie  "), db, U)
row = db.query(CancellationFeedback).one()
check("zapis poprawnej odpowiedzi", r["success"] and row.reason == "price" and row.details == "za drogo dla mnie", (r, row.details))
check("zapisany status subskrypcji (trialing)", row.sub_status == "trialing", row.sub_status)

r = pay.cancellation_feedback(pay.CancellationFeedbackRequest(reason="hack; drop table"), db, U)
check("nieznany powod odrzucony, nic nie zapisano", r["success"] is False and db.query(CancellationFeedback).count() == 1, r)

r = pay.cancellation_feedback(pay.CancellationFeedbackRequest(reason="quality", details="x" * 900), db, U)
row = db.query(CancellationFeedback).one()
check("ponowne wyslanie w 30 min aktualizuje ten sam wiersz", r["success"] and db.query(CancellationFeedback).count() == 1 and row.reason == "quality", row.reason)
check("komentarz przyciety do 500 znakow", len(row.details) == 500, len(row.details))

row.created_at = datetime.utcnow() - timedelta(hours=2); db.commit()
r = pay.cancellation_feedback(pay.CancellationFeedbackRequest(reason="bugs"), db, U)
check("po 30 min powstaje nowy wiersz (bez komentarza = None)", db.query(CancellationFeedback).count() == 2 and db.query(CancellationFeedback).order_by(CancellationFeedback.id.desc()).first().details is None)

settings.ANALYTICS_ADMIN_KEY = "sekret"
r = pay.cancellation_feedback_summary(key="zly", days=90, db=db)
check("raport bez poprawnego klucza: odmowa", r["success"] is False, r)
r = pay.cancellation_feedback_summary(key="sekret", days=90, db=db)
check("raport z kluczem: liczby wg powodu", r["success"] and r["counts"] == {"quality": 1, "bugs": 1}, r)
check("raport: komentarze tylko z niepustymi detalami", len(r["comments"]) == 1 and r["comments"][0]["reason"] == "quality", r["comments"])

# kody z JS musza byc zgodne z whitelista backendu
import re
js = open(os.path.join(HERE, "static", "cancel_survey.js"), encoding="utf-8").read()
codes = set(re.findall(r"code: '([a-z_]+)'", js))
check("kody powodow w JS == whitelista backendu", codes == pay._CANCEL_REASONS, (codes ^ pay._CANCEL_REASONS))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
