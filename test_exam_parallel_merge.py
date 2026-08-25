# -*- coding: utf-8 -*-
"""PORT z Quizu: Sprawdzian (ExamGenerator) tez dzieli wieksze partie na
rownolegle wywolania AI, zeby czas oczekiwania nie rosl liniowo z
liczba zadan (patrz test_parallel_batching.py - identyczny problem/
naprawa dla Quizu). Roznica mechanizmu: ExamGenerator.client jest
SYNCHRONICZNY (OpenAI, nie AsyncOpenAI), wiec rownoleglosc idzie przez
concurrent.futures.ThreadPoolExecutor (_get_exam_data_raw_parallel)
zamiast asyncio.gather - ta sama _parallel_batch_sizes z openai_exam.py
jest wspoldzielona.

Ten test sprawdza WYLACZNIE _merge_exam_data_chunks (czysta, deterministyczna
funkcja laczaca) - ZERO wywolan AI. Samo _get_exam_data_raw_parallel
(ktore faktycznie odpala watki/wywoluje AI) jest pokryte posrednio przez
realny test end-to-end (n=13, rownania kwadratowe, srednia)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.exam_pdf_generator import _merge_exam_data_chunks, ExamGenerator
from app.openai_exam import _parallel_batch_sizes

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("_get_exam_data_raw_parallel istnieje i jest wpiete (2 call sites)")
print("=" * 70)
check("metoda istnieje na ExamGenerator", hasattr(ExamGenerator, "_get_exam_data_raw_parallel"), None)

print()
print("=" * 70)
print("Bufor dla n=13 medium quadratic (20) -> _parallel_batch_sizes dzieli na 2")
print("=" * 70)
sizes = _parallel_batch_sizes(20)
check("n=20 (bufor dla n=13 medium quadratic) -> 2 rownolegle czesci", len(sizes) == 2, sizes)
check("suma czesci = 20", sum(sizes) == 20, sizes)

print()
print("=" * 70)
print("_merge_exam_data_chunks: pusta lista / brak wynikow")
print("=" * 70)
check("pusta lista chunkow -> {}", _merge_exam_data_chunks([]) == {}, None)
check("lista samych pustych/None -> {}", _merge_exam_data_chunks([{}, None, {"sekcje": []}]) == {}, None)

print()
print("=" * 70)
print("_merge_exam_data_chunks: pojedynczy chunk -> zwracany bez zmian")
print("=" * 70)
single = {"tytul": "Test", "sekcje": [{"typ": "zamkniete", "pytania": [{"tresc": "A"}]}]}
check("1 chunk -> identyczny obiekt zwrocony (identity/shape zachowane)",
      _merge_exam_data_chunks([single]) is single, None)

print()
print("=" * 70)
print("_merge_exam_data_chunks: 2 chunki, ten sam typ sekcji -> pytania POLACZONE")
print("=" * 70)
chunk1 = {"tytul": "Sprawdzian", "przedmiot": "Matematyka", "sekcje": [
    {"typ": "zamkniete", "nazwa": "Czesc A", "pytania": [{"tresc": "Q1"}, {"tresc": "Q2"}]},
]}
chunk2 = {"tytul": "Sprawdzian", "przedmiot": "Matematyka", "sekcje": [
    {"typ": "zamkniete", "nazwa": "Czesc A", "pytania": [{"tresc": "Q3"}, {"tresc": "Q4"}, {"tresc": "Q5"}]},
]}
merged = _merge_exam_data_chunks([chunk1, chunk2])
check("2 chunki -> 1 sekcja 'zamkniete' (nie zdublowana)", len(merged["sekcje"]) == 1, merged["sekcje"])
texts = [p["tresc"] for p in merged["sekcje"][0]["pytania"]]
check("wszystkie 5 pytan obecne, w kolejnosci chunk1 potem chunk2 (nic nie zgubione)",
      texts == ["Q1", "Q2", "Q3", "Q4", "Q5"], texts)
check("metadane (tytul/przedmiot) z pierwszego niepustego chunka", merged["tytul"] == "Sprawdzian" and merged["przedmiot"] == "Matematyka", merged)

print()
print("=" * 70)
print("_merge_exam_data_chunks: rozne typy sekcji (zamkniete/otwarte) -> NIE mieszane")
print("=" * 70)
chunk_closed = {"sekcje": [{"typ": "zamkniete", "pytania": [{"tresc": "Z1"}]}]}
chunk_open = {"sekcje": [{"typ": "otwarte", "pytania": [{"tresc": "O1"}]}]}
merged2 = _merge_exam_data_chunks([chunk_closed, chunk_open])
typy = [s["typ"] for s in merged2["sekcje"]]
check("2 osobne sekcje zachowane (zamkniete + otwarte, NIE polaczone w jedna)",
      sorted(typy) == ["otwarte", "zamkniete"], typy)
closed_section = next(s for s in merged2["sekcje"] if s["typ"] == "zamkniete")
open_section = next(s for s in merged2["sekcje"] if s["typ"] == "otwarte")
check("sekcja 'zamkniete' zawiera TYLKO zamkniete pytania", [p["tresc"] for p in closed_section["pytania"]] == ["Z1"], None)
check("sekcja 'otwarte' zawiera TYLKO otwarte pytania", [p["tresc"] for p in open_section["pytania"]] == ["O1"], None)

print()
print("=" * 70)
print("_merge_exam_data_chunks: chunk z pustymi sekcjami (nieudane wywolanie) -> pomijany bezpiecznie")
print("=" * 70)
chunk_fail = {"sekcje": []}
merged3 = _merge_exam_data_chunks([chunk1, chunk_fail])
texts3 = [p["tresc"] for p in merged3["sekcje"][0]["pytania"]]
check("pusty chunk (nieudane rownolegle wywolanie) nie psuje wyniku - pozostale zadania zachowane",
      texts3 == ["Q1", "Q2"], texts3)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
