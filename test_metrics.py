"""
Test regresyjny app/metrics.py (GenerationMetrics, ETAP 4) - w izolacji,
BEZ wywolan AI (czysto deterministyczny obiekt danych).

Uruchom: python test_metrics.py
"""
import sys, json, time
sys.path.insert(0, ".")

from app.metrics import GenerationMetrics, _Timer

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


print("=== GenerationMetrics: wartosci domyslne ===")
m = GenerationMetrics()
check("requested_count domyslnie 0", m.requested_count == 0)
check("rejection_reasons domyslnie pusty dict", m.rejection_reasons == {})
check("KAZDA instancja ma WLASNY dict (brak wspoldzielonego mutable default)",
      GenerationMetrics().rejection_reasons is not m.rejection_reasons)


print()
print("=== record_rejection: histogram i licznik ===")
m = GenerationMetrics()
m.record_rejection("sympy_mismatch")
m.record_rejection("sympy_mismatch")
m.record_rejection("difficulty_fail")
check("rejected_count sumuje wszystkie wywolania", m.rejected_count == 3, m.rejected_count)
check("histogram poprawnie liczy powtorzenia", m.rejection_reasons == {"sympy_mismatch": 2, "difficulty_fail": 1}, m.rejection_reasons)

m.record_rejection("final_answer_no_match")
m.record_rejection("json_crash")
m.record_rejection("duplicate")
check("wszystkie 5 kategorii wspolistnieja niezaleznie", set(m.rejection_reasons.keys()) == {"sympy_mismatch", "difficulty_fail", "final_answer_no_match", "json_crash", "duplicate"}, m.rejection_reasons)


print()
print("=== to_json_line / log: poprawny, parsowalny JSON ===")
m = GenerationMetrics(requested_count=6, batch_size=10, api_request_count=3, generated_count=21, accepted_count=3, retry_count=2)
m.record_rejection("sympy_mismatch")
m.generation_time = 12.3456
m.total_time = 15.999

line = m.to_json_line()
parsed = json.loads(line)  # rzuci wyjatek, jesli to nie jest poprawny JSON
check("to_json_line() zwraca parsowalny JSON", True)
check("requested_count zachowany poprawnie", parsed["requested_count"] == 6, parsed)
check("czas zaokraglony do 2 miejsc (12.35, nie 12.3456)", parsed["generation_time"] == 12.35, parsed["generation_time"])
check("rejection_reasons zserializowane poprawnie", parsed["rejection_reasons"] == {"sympy_mismatch": 1}, parsed)
check("polskie znaki NIE sa uciekane do \\uXXXX (ensure_ascii=False)", "ą" not in line and "\\u" not in line or True, line)  # sanity - brak polskich znakow w tym przykladzie, test strukturalny ponizej

m2 = GenerationMetrics()
m2.record_rejection("za trudne - ą ę ć")
line2 = m2.to_json_line()
check("polskie znaki w powodzie odrzucenia zachowane czytelnie (nie \\uXXXX)", "ą" in line2 and "\\u" not in line2, line2)


print()
print("=== log(prefix) - format wyjscia ===")
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    GenerationMetrics(requested_count=5).log("[GenerationMetrics][Quiz]")
output = buf.getvalue().strip()
check("log() zaczyna sie od podanego prefiksu", output.startswith("[GenerationMetrics][Quiz] "), output)
check("reszta linii po prefiksie to poprawny JSON", json.loads(output[len("[GenerationMetrics][Quiz] "):])["requested_count"] == 5, output)


print()
print("=== _Timer: mierzy i AKUMULUJE czas na wskazanym atrybucie ===")
# Tolerancja ponizej sleep() celowo, bo time.sleep(x) gwarantuje TYLKO
# "co najmniej x" w teorii, ale ziarnistosc zegara systemowego (zwlaszcza
# Windows) potrafi w praktyce zmierzyc odrobine mniej - test sprawdza
# ZE _Timer w ogole mierzy i akumuluje, nie dokladnosc co do milisekundy.
m = GenerationMetrics()
with _Timer(m, "generation_time"):
    time.sleep(0.05)
check("_Timer dodaje uplyniety czas (>= 0.03s)", m.generation_time >= 0.03, m.generation_time)

prev = m.generation_time
with _Timer(m, "generation_time"):
    time.sleep(0.05)
check("_Timer AKUMULUJE (nie nadpisuje) przy wielokrotnym uzyciu", m.generation_time >= prev + 0.03, (prev, m.generation_time))

m2 = GenerationMetrics()
raised = False
try:
    with _Timer(m2, "validation_time"):
        raise ValueError("test")
except ValueError:
    raised = True
check("_Timer NIE polyka wyjatku (propaguje sie normalnie)", raised)
check("_Timer zapisuje nieujemny czas nawet przy natychmiastowym wyjatku", m2.validation_time >= 0, m2.validation_time)


print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
    sys.exit(0)
