# -*- coding: utf-8 -*-
"""User: Sprawdzian z trygonometrii, real-test odtworzyl (potwierdzajac
identyczny wzorzec juz raz zgloszony dla ciagow - Zadanie 4/5 "prawie
duplikat"): Pytanie 1 i Pytanie 6 to TEN SAM problem (kat 30°,
przyprostokatna naprzeciw = 5, znajdz przeciwprostokatna), tylko
zwerbalizowany innymi slowami przez AI - Diversity Engine (Jaccard na
AI-authored diversity_tag) tego NIE zlapal, bo "reasoning"/"task_type"
byly opisane wystarczajaco roznie.

Naprawiono: diversity_tag_tokens/is_too_similar_diversity_tag dostaly
DRUGI, NIEZALEZNY sygnal - identyczny zestaw liczb (>=2) z TRESCI
pytania. Wszystkie testy sa JEDNOSTKOWE (zero AI), na DOKLADNYCH
tekstach z real-testu tego samego dnia (8 pytan zamknietych z
wygenerowanego Sprawdzianu: Trygonometria)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import is_too_similar_diversity_tag

# DOKLADNE teksty z real-testu (Sprawdzian: Trygonometria w trojkatach)
Q1 = "W trójkącie prostokątnym jeden z kątów ostrych ma miarę 30°. Oblicz długość przeciwprostokątnej, jeśli jedna z przyprostokątnych ma długość 5."
Q6 = "W trójkącie prostokątnym jeden z kątów ostrych ma miarę 30°. Jaką długość ma przeciwprostokątna, jeśli przyprostokątna naprzeciw tego kąta ma długość 5?"
Q2 = "Oblicz wartość kąta w radianach, jeśli jego miara w stopniach wynosi 150°."
Q3 = "W trójkącie prostokątnym przeciwprostokątna ma długość 13, a jedna z przyprostokątnych ma długość 5. Oblicz długość drugiej przyprostokątnej."
Q4 = "Zamień kąt o mierze π/4 radianów na stopnie."
Q5 = "W trójkącie dowolnym boki mają długości 7, 24 i 25. Sprawdź, czy trójkąt jest prostokątny."
Q7 = "W trójkącie ABC, kąt ACB ma miarę 90°, a długości boków wynoszą odpowiednio: AC = 6, BC = 8. Oblicz długość boku AB."
Q8 = "Oblicz miarę kąta w stopniach, jeśli jego miara w radianach wynosi π/3."

# Tagi jakie AI PRAWDOPODOBNIE przypisalo - CELOWO rozne slowa dla Q1/Q6
# (to jest dokladnie to, co zawiodlo w real-tescie - Jaccard NIE lapie
# tego, bo tag jest opisany innymi slowami mimo tej samej matematyki).
TAG_Q1 = {"skill": "trygonometria w trojkacie prostokatnym", "concept": "kat 30 stopni",
          "task_type": "oblicz przeciwprostokatna", "reasoning": "zastosuj sin 30 rowne 0.5"}
TAG_Q6 = {"skill": "zwiazki miarowe w trojkacie", "concept": "kat ostry i przyprostokatna",
          "task_type": "wyznacz dlugosc boku", "reasoning": "uzyj stosunku przeciwprostokatnej do przyprostokatnej"}
TAG_Q2 = {"skill": "zamiana jednostek kata", "concept": "stopnie na radiany",
          "task_type": "przelicz miare kata", "reasoning": "pomnoz przez pi przez 180"}

print("=" * 70)
print("Real przypadek: Pytanie 1 vs Pytanie 6 (ten sam problem, inne slowa)")
print("=" * 70)
seen = []
too_similar_1, tokens_1 = is_too_similar_diversity_tag(TAG_Q1, seen, question_text=Q1)
check("Pytanie 1 (pierwsze w partii) -> nie za podobne do niczego (pusta lista)",
      too_similar_1 is False)
seen.append(tokens_1)

too_similar_6, tokens_6 = is_too_similar_diversity_tag(TAG_Q6, seen, question_text=Q6)
check("Pytanie 6 (te same liczby {30,5}, ROZNE slowa w tagu) -> ZLAPANE jako za podobne",
      too_similar_6 is True, (TAG_Q1, TAG_Q6))

print()
print("=" * 70)
print("Regresja: pozostale 6 pytan (rozne liczby) NIE sa falszywie odrzucane")
print("=" * 70)
# NAPRAWIONE (blad WLASNEJ konstrukcji testu, nie kodu - pierwsza wersja
# dala Q2/Q4/Q8 przypadkowo nachodzace na siebie slownictwo "zamiana
# jednostek kata" x2/x3, co samo w sobie juz mialo Jaccard>=0.85,
# CALKOWICIE niezaleznie od liczb - falszywy alarm byl w danych
# testowych, nie w is_too_similar_diversity_tag). Ponizsze 6 tagow ma
# CELOWO nienachodzace sie slownictwo, zeby test faktycznie izolowal
# TYLKO sygnal liczbowy, nie przypadkowe powielenie slow tagu.
others = [(Q2, TAG_Q2),
          (Q3, {"skill": "twierdzenie pitagorasa", "concept": "przeciwprostokatna i przyprostokatna", "task_type": "oblicz brakujacy bok", "reasoning": "podstaw do c kwadrat rowne a kwadrat plus b kwadrat"}),
          (Q4, {"skill": "luk i kat srodkowy", "concept": "miara lukowa", "task_type": "konwersja jednostki katowej", "reasoning": "skorzystaj z proporcji pelnego kata"}),
          (Q5, {"skill": "twierdzenie odwrotne do pitagorasa", "concept": "sprawdzenie prostokatnosci", "task_type": "zweryfikuj typ trojkata", "reasoning": "porownaj sume kwadratow krotszych bokow z kwadratem najdluzszego"}),
          (Q7, {"skill": "dlugosc przeciwprostokatnej", "concept": "trojkat prostokatny z danymi przyprostokatnymi", "task_type": "znajdz brakujacy bok figury", "reasoning": "dodaj kwadraty i wyciagnij pierwiastek kwadratowy"}),
          (Q8, {"skill": "funkcje trygonometryczne katow", "concept": "notacja lukowa wzgledem kata pelnego", "task_type": "wyraz miare w innym systemie", "reasoning": "zastosuj wspolczynnik przeliczeniowy"})]

seen2 = [tokens_1, tokens_6]
false_positive = False
for q_text, q_tag in others:
    ts, toks = is_too_similar_diversity_tag(q_tag, seen2, question_text=q_text)
    if ts:
        false_positive = True
        print(f"  FALSZYWY ALARM dla: {q_text[:50]}...")
    seen2.append(toks)
check("Zadne z pozostalych 6 pytan (rozne liczby: 150; 13,5; 4; 7,24,25; 6,8; 3) nie zostalo falszywie odrzucone",
      not false_positive)

print()
print("=" * 70)
print("Regresja: bez question_text (stare wywolanie) - zachowanie niezmienione")
print("=" * 70)
seen3 = [is_too_similar_diversity_tag(TAG_Q1, [])[1]]
too_similar_no_text, _ = is_too_similar_diversity_tag(TAG_Q6, seen3)  # BEZ question_text
check("Bez question_text, rozne tagi -> NIE zlapane (identyczne jak przed naprawa)",
      too_similar_no_text is False)

print()
print("=" * 70)
print("Regresja: identyczny tag + BEZ question_text (dawny mechanizm Jaccard) nadal dziala")
print("=" * 70)
same_tag = {"skill": "x", "concept": "y", "task_type": "z", "reasoning": "w"}
seen4 = [is_too_similar_diversity_tag(same_tag, [])[1]]
too_similar_same, _ = is_too_similar_diversity_tag(dict(same_tag), seen4)
check("Identyczny tag (Jaccard=1.0) nadal poprawnie zlapany, z lub bez liczb",
      too_similar_same is True)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
