# -*- coding: utf-8 -*-
"""User (koniec dnia, po dyskusji o priorytetyzacji kolejnych archetypow
Safe Parameter Generation - "A teraz (krotkie), B rownolegle dalej bez
czekania"): dane o KAZDYM wywolaniu generowania Quizu/Sprawdzianu leciaty
dotad WYLACZNIE do konsoli (print, GenerationMetrics.log) - znikaly przy
kazdym restarcie serwera (a restartowalismy go dzis kilkanascie razy).
Bez tego nie da sie za tydzien/dwa ustalic, ktore tematy/trudnosci
FAKTYCZNIE sa najczesciej zamawiane (do potwierdzenia albo korekty
dzisiejszej priorytetyzacji "na wyczucie" - trygonometria, ciagi).

Dodano: GenerationRequestLog (nowa tabela, models.py) +
persist_generation_metrics (metrics.py) - jeden wiersz na kazde
wywolanie generowania, wpiete w KAZDE z 4 miejsc, gdzie
GenerationMetrics.log() jest juz wolane (2x Quiz, 2x Sprawdzian).
CELOWO odporne na kazdy blad zapisu (nigdy nie przerywa generowania).

Ten plik testuje SAMA logike zapisu/odczytu (real SQLite - dev baza
tego projektu, NIE mock) - tworzy tabele jesli nie istnieje (identyczny
mechanizm co main.py przy starcie), zapisuje testowy wiersz, odczytuje
go z powrotem, PO CZYM GO USUWA (zeby nie zanieczyszczac przyszlej
analizy Pareto danymi testowymi)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.database import Base, engine, SessionLocal
from app.models import GenerationRequestLog
from app.metrics import GenerationMetrics, persist_generation_metrics

# Identyczny mechanizm co main.py przy starcie - tworzy TYLKO brakujace
# tabele, nie rusza istniejacych danych.
Base.metadata.create_all(bind=engine)

print("=" * 70)
print("persist_generation_metrics - zapisuje real wiersz do bazy")
print("=" * 70)
m = GenerationMetrics(
    requested_count=15, batch_size=21, accepted_count=15, rejected_count=9,
    retry_count=1, total_time=68.2,
)
m.rejection_reasons = {"blind_ai_mismatch": 3, "duplicate": 1, "diversity_too_similar": 5}
_MARKER = "__TEST_MARKER_DO_USUNIECIA__"
persist_generation_metrics(m, feature="exam", temat=_MARKER, trudnosc="trudna", poziom="liceum_3")

db = SessionLocal()
try:
    row = db.query(GenerationRequestLog).filter(GenerationRequestLog.temat == _MARKER).order_by(GenerationRequestLog.id.desc()).first()
    check("Wiersz zostal faktycznie zapisany i jest odczytywalny", row is not None, row)
    if row is not None:
        check("feature == 'exam'", row.feature == "exam", row.feature)
        check("trudnosc == 'trudna'", row.trudnosc == "trudna", row.trudnosc)
        check("poziom == 'liceum_3'", row.poziom == "liceum_3", row.poziom)
        check("requested_count == 15", row.requested_count == 15, row.requested_count)
        check("accepted_count == 15", row.accepted_count == 15, row.accepted_count)
        check("rejected_count == 9", row.rejected_count == 9, row.rejected_count)
        check("retry_count == 1", row.retry_count == 1, row.retry_count)
        check("total_time == 68.2", row.total_time == 68.2, row.total_time)
        check("rejection_reasons zapisane jako JSON ze wszystkimi kluczami",
              row.rejection_reasons == {"blind_ai_mismatch": 3, "duplicate": 1, "diversity_too_similar": 5},
              row.rejection_reasons)
finally:
    # Sprzatanie - usuwa TYLKO wiersze z tym markerem, zeby nie
    # zanieczyszczac przyszlej analizy Pareto danymi testowymi.
    db.query(GenerationRequestLog).filter(GenerationRequestLog.temat == _MARKER).delete()
    db.commit()
    db.close()

print()
print("=" * 70)
print("Odpornosc na bledy - NIGDY nie rzuca wyjatku (nawet przy zlych danych)")
print("=" * 70)
try:
    persist_generation_metrics(None, feature="exam", temat="x")
    check("None jako metrics -> nie rzuca wyjatku (blad polkniety, zalogowany)", True)
except Exception as e:
    check("None jako metrics -> nie rzuca wyjatku", False, str(e))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
