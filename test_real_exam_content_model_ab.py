# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "Sprawdzian - przetestuj
gpt-4o-mini") - porownuje gpt-4o vs gpt-4o-mini dla GLOWNEGO generatora
tresci Sprawdzianu (_get_exam_data_raw, freeform - AI samo odpowiada za
poprawnosc matematyczna, w odroznieniu od "safe archetype" batch funkcji
gdzie matematyke liczy kod). To jest wiekszy koszt niz archetypy, wiec
ten test jest najwazniejszy do decyzji o swapie.

Male N (5), 2 rozne tematy (jeden latwy, jeden trudniejszy), zeby bylo
tanio ale reprezentatywnie."""
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from openai import OpenAI
from app.config import settings
from app.exam_pdf_generator import ExamGenerator

REAL_CLIENT = OpenAI(api_key=settings.OPENAI_API_KEY)


class _ForcedModelCompletions:
    def __init__(self, real_completions, forced_model):
        self._real = real_completions
        self._forced_model = forced_model

    def create(self, *a, **kw):
        kw["model"] = self._forced_model
        return self._real.create(*a, **kw)


class _ForcedModelClientWrapper:
    def __init__(self, real_client, forced_model):
        self.chat = type("C", (), {"completions": _ForcedModelCompletions(real_client.chat.completions, forced_model)})()


def run(model_name, temat, klasa, trudnosc, n):
    gen = ExamGenerator(settings.OPENAI_API_KEY)
    gen.client = _ForcedModelClientWrapper(REAL_CLIENT, model_name)
    t0 = time.time()
    data = gen._get_exam_data(temat, klasa, trudnosc, n)
    elapsed = time.time() - t0
    total = sum(len(s.get('pytania', [])) for s in data.get('sekcje', []))
    print(f"\n{'='*70}\n{model_name} | '{temat}' ({klasa}, {trudnosc}, n={n}) -> {total}/{n} w {elapsed:.1f}s\n{'='*70}")
    for s in data.get('sekcje', []):
        for p in s.get('pytania', []):
            print(f"[{s.get('typ')}] {p.get('tresc')}")
            if s.get('typ') == 'zamkniete':
                print(f"    opcje: {p.get('opcje')}  odp: {p.get('odpowiedz')}  final_answer: {p.get('final_answer')}")
            else:
                print(f"    odpowiedz_modelowa: {p.get('odpowiedz_modelowa')}")
    return data


if __name__ == "__main__":
    # Temat 1: latwy, sprawdzony (geometria)
    run("gpt-4o", "Pole i obwod figur plaskich", "podstawowka_6", "srednia", 5)
    run("gpt-4o-mini", "Pole i obwod figur plaskich", "podstawowka_6", "srednia", 5)
    # Temat 2: trudniejszy (funkcje trygonometryczne)
    run("gpt-4o", "Funkcje trygonometryczne", "liceum_2", "srednia", 5)
    run("gpt-4o-mini", "Funkcje trygonometryczne", "liceum_2", "srednia", 5)
