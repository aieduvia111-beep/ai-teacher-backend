# -*- coding: utf-8 -*-
"""User zapytal "czy poziom jest odpowiedni?" po realnym real-teście
Quizu (ciagi, klasa 3 liceum, trudny) i poprosil o naprawe 3 luk
zgloszonych po poprzedniej naprawie (prosze o oszczednosc kosztow -
zero dodatkowych wywolan AI przy budowie, TYLKO real logi/kod):

LUKA 1 (NAJWIEKSZA): pytania napisane CZYSTA PROZA, bez ZADNEGO LaTeX/
symbolu ("pierwszy wyraz wynosi 7, ostatni wyraz wynosi 47, a różnica
wynosi 4" zamiast "$a_1=7$"/"$d=4$") byly calkowicie niewidoczne dla
Warstwy 2 - wszystkie regexy wymagaly formy "litera[_indeks]=liczba".
Dodano UZUPELNIAJACE (fallback, tylko gdy forma symboliczna nic nie
znalazla) wzorce prozy: pierwszy wyraz, roznica/iloraz, ostatni wyraz,
oraz tolerancje na wypelniacze ("suma JEGO pierwszych..."). Dodatkowo
_sequence_a1_given zaktualizowane, zeby TEZ rozpoznawalo proze - inaczej
"pierwszy wyraz wynosi 7" (OPIS danej) falszywie sygnalizowaloby
"a1 jest szukane".

LUKA 2: geometryczne/dwumianowe uklady rownan (np. a4/a2=q^2=9) maja
CZESTO DWA matematycznie poprawne rozwiazania (q=+-3), ale weryfikator
ZAWSZE abstainowal, nawet gdy TYLKO JEDNO z tych rozwiazan faktycznie
wystepowalo wsrod podanych opcji (drugie po prostu nie bylo wyborem).
Dodano _disambiguate_multi_solution - bezpiecznie wybiera JEDYNE
rozwiazanie obecne wsrod opcji, ale NADAL abstainuje, jesli OBA (lub
ZADNE) sa obecne - patrz testy bezpieczenstwa ponizej.

LUKA 3 (mniejsza, znaleziona PRZY BUDOWIE luki 2): opcje dla
two_term_to_a1_ratio czasem podaja TYLKO a1 ("$a_1=3$"), nie pare
a1+iloraz razem - _option_a1_ratio wymagal OBU wartosci w kazdej
opcji, wiec zawsze zwracal None dla tego formatu. Dodano fallback:
gdy ZADNA opcja nie zawiera wartosci ilorazu/roznicy, porownuj TYLKO
po a1 (jedyne bezpiecznie sprawdzalne z danych opcji).

PRZY OKAZJI zlapano i naprawiono TEZ falszywy pozytyw we WCZESNIEJSZYM
dzisiejszym intencie "two_term_to_ratio_only" - pierwsza wersja
sprawdzala czasownik i "różnic"/"iloraz" NIEZALEZNIE gdziekolwiek w
tekscie, wiec falszywie lapala "Znajdź sumę..., a różnica wynosi 5"
(pytanie o SUME, "różnica" tam tylko OPISUJE dana). Wymagane teraz:
czasownik BEZPOSREDNIO przed "różnicę"/"iloraz".

Wszystkie testy sa JEDNOSTKOWE (zero AI), na DOKLADNYCH tekstach z
realnego logu drugiej real-testowej generacji."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import verify_and_fix_math_question, analyze_sequence_question, detect_sequence_intent

print("=" * 70)
print("LUKA 1: rozpoznawanie CZYSTEJ PROZY (bez LaTeX/symboli)")
print("=" * 70)

a = analyze_sequence_question("Ciąg arytmetyczny, którego pierwszy wyraz wynosi 7, ostatni wyraz wynosi 47, a różnica wynosi 4.")
check("proza: 'pierwszy wyraz wynosi 7' -> terms[1]=7", a["terms"].get(1) == 7, a)
check("proza: 'różnica wynosi 4' -> ratio=4", a["ratio"] == 4, a)
check("proza: 'ostatni wyraz wynosi 47' -> last_term=47", a["last_term"] == 47, a)

q_prose = "Ile wyrazów ma ciąg arytmetyczny, którego pierwszy wyraz wynosi 7, ostatni wyraz wynosi 47, a różnica wynosi 4?"
r_prose = verify_and_fix_math_question(q_prose, ["13", "10", "11", "12"])
check("Real przypadek (dokladny tekst z logu): n=11 poprawnie wykryte (byloby 'unverifiable' PRZED naprawa)",
      r_prose["status"] == "match_index" and r_prose["true_index"] == 2, r_prose)

# Wariant BEZ czasownika "wynosi" (obserwowany w tej samej partii:
# "pierwszy wyraz 2 i różnicę 3" - bez "wynosi")
a_no_verb = analyze_sequence_question("Ciąg arytmetyczny ma pierwszy wyraz 2 i różnicę 3.")
check("proza BEZ 'wynosi' ('pierwszy wyraz 2') nadal dziala", a_no_verb["terms"].get(1) == 2 and a_no_verb["ratio"] == 3, a_no_verb)

print()
print("=" * 70)
print("Uczciwosc: genuinie zle sformulowane pytanie AI (brak calkowitego "
      "rozwiazania) NIE crashuje, poprawnie odrzucone")
print("=" * 70)
q_broken = "Jeśli ciąg arytmetyczny ma pierwszy wyraz 2 i różnicę 3, a suma jego pierwszych n wyrazów wynosi 65, to ile wynosi n?"
r_broken = verify_and_fix_math_question(q_broken, ["5", "6", "7", "8"])
# S_n=65 dla a1=2,d=3 nie ma rozwiazania calkowitego (sprawdzone: n=(-1+sqrt(1561))/6)
check("Real przypadek: matematycznie NIEROZWIAZYWALNE calkowitoliczbowo pytanie -> odrzucone (no_option_matches), nie crash",
      r_broken["status"] in ("no_option_matches", "unverifiable"), r_broken)

print()
print("=" * 70)
print("Precyzja: 'Znajdź sumę...' z 'różnica' gdzies indziej w tekscie "
      "NIE jest falszywie lapane jako two_term_to_ratio_only")
print("=" * 70)
q_sum_not_ratio = "Znajdź sumę wszystkich wyrazów ciągu arytmetycznego, którego pierwszy wyraz wynosi 5, ostatni wyraz 50, a różnica wynosi 5."
intent_sum = detect_sequence_intent(q_sum_not_ratio)
check("intent NIE jest 'two_term_to_ratio_only' (poprzednia, zbyt luzna wersja by tak zrobila)",
      intent_sum is None or intent_sum.get("intent") != "two_term_to_ratio_only", intent_sum)

print()
print("=" * 70)
print("LUKA 2+3: dwuznaczne +-rozwiazanie (q^2=N) - bezpieczna "
      "dezambiguacja przez sprawdzenie OPCJI")
print("=" * 70)
q_amb = "Dany jest ciąg geometryczny, w którym drugi wyraz $a_2 = 6$ i czwarty wyraz $a_4 = 54$. Oblicz pierwszy wyraz tego ciągu."

r_one_present = verify_and_fix_math_question(q_amb, ["$a_1 = 3$", "$a_1 = 4$", "$a_1 = 5$", "$a_1 = 2$"])
check("Real przypadek: q=+-3 -> a1=+-2, TYLKO a1=2 wsrod opcji -> bezpiecznie wybrane (index 3)",
      r_one_present["status"] == "match_index" and r_one_present["true_index"] == 3, r_one_present)

print()
print("BEZPIECZENSTWO (KRYTYCZNE): gdy OBA matematycznie poprawne "
      "rozwiazania sa wsrod opcji, NADAL abstain - nie zgadywanie")
r_both_present = verify_and_fix_math_question(q_amb, ["$a_1 = 2$", "$a_1 = -2$", "$a_1 = 5$", "$a_1 = 7$"])
check("BEZPIECZENSTWO: oba +-2 wsrod opcji -> unverifiable (NIE arbitralny wybor)",
      r_both_present["status"] == "unverifiable", r_both_present)

r_neither_present = verify_and_fix_math_question(q_amb, ["$a_1 = 5$", "$a_1 = 7$", "$a_1 = 9$", "$a_1 = 11$"])
check("BEZPIECZENSTWO: zadne z +-2 nie jest wsrod opcji -> unverifiable (NIE zgadywanie czegos innego)",
      r_neither_present["status"] == "unverifiable", r_neither_present)

print()
print("=" * 70)
print("Regresja: pojedyncze (jednoznaczne) rozwiazanie two_term_to_a1_ratio "
      "nadal dziala normalnie (bez dezambiguacji)")
print("=" * 70)
r_unambiguous = verify_and_fix_math_question(
    "Ciąg arytmetyczny ma a3=11 i a7=27. Znajdź pierwszy wyraz.",
    ["a1=3, r=4", "a1=5, r=3", "a1=7, r=2", "a1=9, r=1"]
)
check("Regresja: jednoznaczny (liniowy uklad) przypadek nadal dziala jak wczesniej",
      r_unambiguous["status"] == "match_index" and r_unambiguous["true_index"] == 0, r_unambiguous)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
