"""Lokalne testy (zero kosztu) dla problem_class=="factual" w Warstwie 2.5:
1. build_blind_verify_prompt_closed/open uzywaja innej, faktograficznej
   ramy (nie "rozwiaz zadanie krok po kroku") gdy problem_class=="factual".
2. NAPRAWIONE: _blind_verify_one_open mial guard oparty o sympy
   (_extract_single_value), ktory BEZWARUNKOWO odrzucal (cichy abstain,
   ZERO blind-verify) kazda tekstowa odpowiedz faktograficzna ("Adam
   Mickiewicz" nie parsuje sie jako wyrazenie sympy) - naprawione tak,
   by dla problem_class=="factual" wystarczylo niepuste `claimed`."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.blind_verify import (
    build_blind_verify_prompt_closed, build_blind_verify_prompt_open,
    BLIND_VERIFY_SYSTEM_PROMPT, BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL,
)
import app.exam_pdf_generator as epg

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=== build_blind_verify_prompt_* : rama faktograficzna vs matematyczna ===")
p_math = build_blind_verify_prompt_closed("2+2=?", ["a) 3", "b) 4"])
p_fact = build_blind_verify_prompt_closed("Kto napisal Pana Tadeusza?", ["a) Slowacki", "b) Mickiewicz"], problem_class="factual")
check("domyslnie (brak problem_class) -> 'rozwiaz zadanie krok po kroku'", "krok po kroku" in p_math)
check("factual -> BEZ 'rozwiaz zadanie krok po kroku'", "krok po kroku" not in p_fact)
check("factual -> wspomina fakt/wiedze", "faktu/wiedzy" in p_fact)

po_math = build_blind_verify_prompt_open("Oblicz pole kola o promieniu 3.")
po_fact = build_blind_verify_prompt_open("W ktorym roku wybuchla II wojna swiatowa?", problem_class="factual")
check("open domyslnie -> 'rozwiaz zadanie krok po kroku'", "krok po kroku" in po_math)
check("open factual -> BEZ 'rozwiaz zadanie krok po kroku'", "krok po kroku" not in po_fact)

print("=== system prompt: inna persona dla factual ===")
check("BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL istnieje i rozni sie od domyslnego",
      BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL != BLIND_VERIFY_SYSTEM_PROMPT)
check("wersja factual NIE wspomina 'matematyki'", "matematyki" not in BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL)

print("=== _blind_verify_one_open: naprawiony guard dla tekstowych odpowiedzi factual ===")


class _SentinelClient:
    """Zwraca ustalona odpowiedz JSON - dowod, ze funkcja NAPRAWDE dotarla
    do wywolania AI-2 (a nie cicho zabstainowala jak przed naprawa)."""
    class chat:
        class completions:
            @staticmethod
            def create(*a, **kw):
                class _Msg:
                    content = '{"final_answer": "Adam Mickiewicz"}'
                class _Choice:
                    message = _Msg()
                class _Resp:
                    choices = [_Choice()]
                return _Resp()


pyt_factual_text = {
    "tresc": "Kto napisal 'Pana Tadeusza'?",
    "final_answer": "Adam Mickiewicz",
    "problem_class": "factual",
}
result = epg._blind_verify_one_open(_SentinelClient, pyt_factual_text)
check("PRZED naprawa to zawsze bylo True/abstain BEZ wywolania AI-2 - teraz NAPRAWDE woła AI-2 i porownuje (zgadza sie)",
      result is True, result)

pyt_factual_wrong = {
    "tresc": "Kto napisal 'Pana Tadeusza'?",
    "final_answer": "Juliusz Slowacki",
    "problem_class": "factual",
}
result2 = epg._blind_verify_one_open(_SentinelClient, pyt_factual_wrong)
check("Faktograficzna BLEDNA odpowiedz (AI-2 mowi Mickiewicz, AI-1 twierdzil Slowacki) -> False",
      result2 is False, result2)

print("=== Regresja: matematyczne otwarte zadania bez zmian (nadal wymagaja sympy-parsowalnej wartosci) ===")
pyt_math_unparseable = {
    "tresc": "Opisz slowami jak rozwiazac rownanie kwadratowe.",
    "final_answer": "najpierw oblicz delte a potem...",
    # BRAK problem_class (domyslne zachowanie matematyczne, jak dotychczas)
}
result3 = epg._blind_verify_one_open(_SentinelClient, pyt_math_unparseable)
check("Nieparsowalna matematyczna odpowiedz (brak problem_class) -> nadal cichy abstain (True, bez wywolania AI-2)",
      result3 is True, result3)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
