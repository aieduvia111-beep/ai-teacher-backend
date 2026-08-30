"""Lokalne testy (zero kosztu) dla _select_blind_verify_model - waski
wyjatek: ciagi wracaja do gpt-4o w Warstwie 2.5, reszta zostaje na
gpt-4o-mini. Patrz real-test porownawczy 30.08.2026 (11 znanych
przypadkow z real PDF): gpt-4o 9/11, gpt-4o-mini 7/11 - w
przeciwienstwie do rownan kwadratowych z parametrem, gdzie mini byl
rowny lub lepszy niz gpt-4o."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.openai_exam import _select_blind_verify_model as select_quiz
from app.exam_pdf_generator import _select_blind_verify_model as select_exam

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=== Quiz (openai_exam.py) ===")
check("ciagi arytmetyczne -> gpt-4o", select_quiz("Matematyka: ciągi arytmetyczne - Quiz") == "gpt-4o")
check("ciagi geometryczne -> gpt-4o", select_quiz("Matematyka: ciągi geometryczne - Quiz") == "gpt-4o")
check("ciag bez slowa arytm/geom -> gpt-4o-mini (nie pasuje)", select_quiz("Matematyka: ciąg Fibonacciego - Quiz") == "gpt-4o-mini")
check("rownania kwadratowe -> gpt-4o-mini (bez zmian)", select_quiz("Matematyka: równania kwadratowe - Quiz") == "gpt-4o-mini")
check("brak tematu (None) -> gpt-4o-mini (domyslnie)", select_quiz(None) == "gpt-4o-mini")
check("pusty string -> gpt-4o-mini (domyslnie)", select_quiz("") == "gpt-4o-mini")
check("wielkosc liter nie ma znaczenia", select_quiz("CIĄGI ARYTMETYCZNE") == "gpt-4o")

print("=== Sprawdzian (exam_pdf_generator.py) ===")
check("ciagi arytmetyczne -> gpt-4o", select_exam("Sprawdzian: Ciągi arytmetyczne (liceum)") == "gpt-4o")
check("ciagi geometryczne -> gpt-4o", select_exam("Sprawdzian: Ciągi geometryczne") == "gpt-4o")
check("trygonometria -> gpt-4o-mini (bez zmian)", select_exam("Sprawdzian: Trygonometria") == "gpt-4o-mini")
check("brak tematu (None) -> gpt-4o-mini (domyslnie)", select_exam(None) == "gpt-4o-mini")
check("tytul testowy 'Test' -> gpt-4o-mini (nie pasuje, regresja dla mockow)", select_exam("Test") == "gpt-4o-mini")

print(f"\n=== WYNIK: {'WSZYSTKIE OK' if not FAILED else str(len(FAILED)) + ' FAIL'} ===")
sys.exit(1 if FAILED else 0)
