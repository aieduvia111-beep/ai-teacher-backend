"""Lokalne testy (zero kosztu) - naprawa deduplikacji:
1. _question_fingerprint teraz lapie duplikaty z TYM SAMYM wzorem
   matematycznym ($...$), nawet gdy otaczajaca proza (czasownik) sie
   rozni ("Oblicz calke..." vs "Znajdz calke...").
2. Sprawdzian: deduplikacja dziala TERAZ TAKZE na sekcji otwarte,
   WSPOLDZIELAC seen_fingerprints z sekcja zamkniete - wczesniej
   dzialala WYLACZNIE na zamknietych.

Live-test (30.08.2026, temat ze studiow "Calki nieoznaczone", poziom
trudny) ujawnil real duplikat: Zadanie 2 (Czesc A, zamkniete) "Oblicz
calke nieoznaczona $\\int e^{2x}\\,dx$." i Zadanie 13 (Czesc B, otwarte)
"Znajdz calke nieoznaczona $\\int e^{2x}\\,dx$." - identyczna calka,
inny czasownik, inna sekcja - stary mechanizm (szkielet slowny, TYLKO
zamkniete) nie mial szans tego zlapac z DWOCH niezaleznych powodow."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.exam_pdf_generator import _question_fingerprint as exam_fp, _verify_open_section
from app.openai_exam import _question_fingerprint as quiz_fp

print("=" * 70)
print("_question_fingerprint: dokladny przypadek z live-testu")
print("=" * 70)
t1 = "Oblicz całkę nieoznaczoną $\\int e^{2x} \\, dx$."
t2 = "Znajdź całkę nieoznaczoną $\\int e^{2x} \\, dx$."
fp1 = exam_fp(t1)
fp2 = exam_fp(t2)
check("Exam: rozne szkielety slowne (inny czasownik)", fp1[0] != fp2[0], (fp1[0], fp2[0]))
check("Exam: ALE wspolny klucz 'math' (ten sam wzor) - fingerprinty maja przeciecie",
      any(k in fp2 for k in fp1), (fp1, fp2))

fp1q = quiz_fp(t1)
fp2q = quiz_fp(t2)
check("Quiz: identyczna naprawa - wspolny klucz 'math'",
      any(k in fp2q for k in fp1q), (fp1q, fp2q))

print()
print("=" * 70)
print("_question_fingerprint: regresja - rozne wzory NIE sa duplikatem")
print("=" * 70)
t3 = "Oblicz całkę nieoznaczoną $\\int \\sin(3x) \\, dx$."
fp3 = exam_fp(t3)
check("Rozne calki (e^2x vs sin(3x)) -> BRAK wspolnego klucza",
      not any(k in fp3 for k in fp1), (fp1, fp3))

print()
print("=" * 70)
print("_question_fingerprint: regresja - krotkie/trywialne wzory NIE dają falszywych trafien")
print("=" * 70)
ta = "Dla jakich wartości parametru $x$ zachodzi warunek A?"
tb = "Dla jakich wartości parametru $x$ zachodzi warunek B?"
fpa = exam_fp(ta)
fpb = exam_fp(tb)
check("Pojedyncza zmienna '$x$' (za krotka, <5 znakow) -> brak klucza 'math'",
      not any(k[0] == "math" for k in fpa), fpa)

print()
print("=" * 70)
print("_question_fingerprint: regresja - identyczny tekst nadal wykrywany jako duplikat")
print("=" * 70)
t4 = "Ile kosztuje bilet, jeśli cena wynosi 50 zł, a rabat to 18 zł?"
t4b = "Ile kosztuje bilet, jeśli cena wynosi 50 zł, a rabat to 18 zł?"
t5 = "Ile kosztuje bilet, jeśli cena wynosi 80 zł, a rabat to 20 zł?"
fp4 = exam_fp(t4)
fp4b = exam_fp(t4b)
fp5 = exam_fp(t5)
check("Identyczny tekst (te same liczby) -> identyczny caly fingerprint (duplikat)",
      fp4 == fp4b, (fp4, fp4b))
check("Ten sam szkielet slowny, ALE INNE liczby -> NIE duplikat (rozne klucze skel, bo numbers rozne)",
      fp4[0] != fp5[0], (fp4[0], fp5[0]))

print()
print("=" * 70)
print("Sprawdzian: cross-section dedup - duplikat Czesc A <-> Czesc B wykryty")
print("=" * 70)
seen = set()
# Symuluj: Czesc A (zamkniete) juz przetworzona, dodala swoj fingerprint
seen.update(exam_fp(t1))
otwarte_pytania = [
    {"tresc": t2, "final_answer": "1/2 e^(2x) + C"},  # DUPLIKAT (ten sam wzor, inny czasownik)
    {"tresc": t3, "final_answer": "-1/3 cos(3x) + C"},  # NIE duplikat (inna calka)
]
result = _verify_open_section(otwarte_pytania, metrics=None, client=None, tytul="Test", seen_fingerprints=seen)
check("Duplikat (t2, ten sam wzor co t1 z Czesci A) USUNIETY z sekcji otwartej",
      len(result) == 1 and result[0]["tresc"] == t3, [r["tresc"] for r in result])

print()
print("=" * 70)
print("Regresja: _verify_open_section bez seen_fingerprints (None) - stare zachowanie")
print("=" * 70)
result2 = _verify_open_section(
    [{"tresc": t1, "final_answer": "1/2 e^(2x) + C"}, {"tresc": t2, "final_answer": "1/2 e^(2x) + C"}],
    metrics=None, client=None, tytul="Test", seen_fingerprints=None,
)
check("Bez seen_fingerprints, duplikat NIE jest usuwany (zachowanie bez zmian dla callerow bez tego param.)",
      len(result2) == 2, [r["tresc"] for r in result2])

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
