# -*- coding: utf-8 -*-
"""ETAP 4 (Performance/observability): GenerationMetrics - jeden obiekt
zbierajacy statystyki CALEGO procesu generowania (Quiz albo Sprawdzian),
od pierwszego (buforowanego) wywolania AI do finalnej, zwroconej listy
pytan/zadan. Watany przez openai_exam.py i exam_pdf_generator.py w te
same miejsca, ktore juz dzis threaduja `t_start`/`difficulty`/
`seen_fingerprints` przez cala petle retry (patrz Etap 2/3).

Cel (audyt Etapu wstepnego): odpowiedziec na "Dlaczego user dostal
mniej pytan?", "Dlaczego pytania byly odrzucane?", "Co zajelo 20 sekund?"
- bez potrzeby grzebania w logach print() linia po linii."""
import json
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GenerationMetrics:
    """UWAGA (potwierdzone realnymi danymi w tej sesji): `rejected_count`
    liczy TYLKO jakosciowe odrzucenia (record_rejection - zly final_answer,
    sympy, zla trudnosc, duplikat, crash JSON). Bufor (patrz Etap 3
    _buffered_count) celowo prosi o WIECEJ kandydatow niz requested_count,
    wiec czasem po wszystkich warstwach zostaje ich WIECEJ niz trzeba -
    nadmiar jest wtedy po prostu PRZYCINANY (nie odrzucany za jakosc).
    Dlatego `generated_count - accepted_count` MOZE byc WIEKSZE niz
    `rejected_count` - roznica to zdrowy, oczekiwany nadmiar bufora, NIE
    niespojnosc w liczeniu."""
    requested_count: int = 0
    batch_size: int = 0
    api_request_count: int = 0
    generated_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    retry_count: int = 0
    generation_time: float = 0.0
    validation_time: float = 0.0
    difficulty_time: float = 0.0
    total_time: float = 0.0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)

    def record_rejection(self, reason: str) -> None:
        """Wywolywane w KAZDYM miejscu, gdzie pytanie/zadanie zostaje
        odrzucone (Warstwa 1/2/3, dedup, crash JSON) - jeden spojny
        histogram zamiast rozproszonych print()."""
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
        self.rejected_count += 1

    def to_json_line(self) -> str:
        return json.dumps({
            "requested_count": self.requested_count,
            "batch_size": self.batch_size,
            "api_request_count": self.api_request_count,
            "generated_count": self.generated_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "retry_count": self.retry_count,
            "generation_time": round(self.generation_time, 2),
            "validation_time": round(self.validation_time, 2),
            "difficulty_time": round(self.difficulty_time, 2),
            "total_time": round(self.total_time, 2),
            "rejection_reasons": self.rejection_reasons,
        }, ensure_ascii=False)

    def log(self, prefix: str) -> None:
        print(f"{prefix} {self.to_json_line()}")


def persist_generation_metrics(metrics: "GenerationMetrics", feature: str, temat: str = None, trudnosc: str = None, poziom: str = None) -> None:
    """Zapisuje jeden wiersz surowych danych generowania do bazy
    (GenerationRequestLog w models.py) - patrz pelne uzasadnienie tam.
    User (29.08.2026): "zrob to teraz, jest tanie... koszt odlozenia
    tego rosnie z kazdym dniem". CELOWO odporne na KAZDY blad (brak
    polaczenia z baza, brakujaca tabela przed pierwszym restartem po
    migracji, itp.) - to jest CZYSTO obserwacyjna instrumentacja i
    NIGDY nie moze przerwac faktycznego generowania dla usera (stad
    zaimportowane wewnatrz funkcji, nie na gorze modulu - zero ryzyka
    circular importu miedzy metrics.py a models.py/database.py, ktore
    dzis nic z tego modulu nie importuja)."""
    try:
        from .database import SessionLocal
        from .models import GenerationRequestLog
        db = SessionLocal()
        try:
            db.add(GenerationRequestLog(
                feature=feature, temat=temat, trudnosc=trudnosc, poziom=poziom,
                requested_count=metrics.requested_count,
                accepted_count=metrics.accepted_count,
                rejected_count=metrics.rejected_count,
                retry_count=metrics.retry_count,
                total_time=round(metrics.total_time, 2),
                rejection_reasons=metrics.rejection_reasons,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[GenerationMetrics] blad zapisu instrumentacji do bazy (nieblokujacy): {e}")


class _Timer:
    """Context manager pomocniczy - dodaje uplyniety czas do wskazanego
    atrybutu GenerationMetrics. `with _Timer(metrics, 'generation_time'):`
    zamiast recznego time.monotonic() przed/po w kazdym miejscu uzycia."""

    def __init__(self, metrics: GenerationMetrics, attr: str):
        self.metrics = metrics
        self.attr = attr
        self._start = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.monotonic() - self._start
        setattr(self.metrics, self.attr, getattr(self.metrics, self.attr) + elapsed)
        return False
