# -*- coding: utf-8 -*-
"""Raport zuzycia tokenow OpenAI na funkcje/model (tabela api_usage_daily,
patrz app/usage_tracker.py). TYLKO ODCZYT.

Uzycie:  PROD_DB_URL=postgresql://... python raport_zuzycia_api.py [dni=7]
(bez PROD_DB_URL uzywa DATABASE_URL z .env / lokalnej bazy)

UWAGA: ceny ponizej sa PRZYBLIZONE (USD za 1M tokenow, stan wiedzy autora) i
moga byc nieaktualne - to szacunek do porownan "co kosztuje najwiecej", NIE
faktura. Prawdziwy koszt: platform.openai.com -> Usage.
Tokeny cached liczone po polowie ceny wejscia (przyblizenie)."""
import os, sys, io, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRICES = {  # (wejscie, wyjscie) USD / 1M tokenow - PRZYBLIZONE
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # glos (19.09.2026): realtime liczone z response.done; ceny gpt-4o-realtime-preview
    "realtime-text": (5.00, 20.00),
    "realtime-audio": (40.00, 80.00),
    # tts-1: rozliczane za ZNAKI (15 USD / 1M znakow) - kolumna "we" to znaki, nie tokeny
    "tts-1": (15.00, 0.0),
}
USD_PLN = 4.0   # przyblizony kurs


def price_for(model: str):
    for name in sorted(PRICES, key=len, reverse=True):   # dluzsze nazwy pierwsze (mini przed 4o)
        if model.startswith(name):
            return PRICES[name]
    return None


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    url = os.environ.get("PROD_DB_URL")
    if url:
        import psycopg2
        conn = psycopg2.connect(url)
        conn.set_session(readonly=True, autocommit=True)
        ph = "%s"
    else:
        import sqlite3
        conn = sqlite3.connect("ai_teacher.db")
        ph = "?"
    cur = conn.cursor()
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    cur.execute(f"SELECT day, label, model, calls, prompt_tokens, completion_tokens, cached_tokens, stream_calls "
                f"FROM api_usage_daily WHERE day >= {ph}", (since,))
    rows = cur.fetchall()
    if not rows:
        print(f"Brak danych od {since} (pomiar dziala od wdrozenia; poczekaj na ruch).")
        return
    by_label = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0])
    by_model = collections.defaultdict(lambda: [0, 0, 0, 0.0])
    unknown_models = set()
    for day, label, model, calls, pt, ct, cached, streams in rows:
        p = price_for(model)
        cost = 0.0
        if p:
            cost = ((pt - cached) * p[0] + cached * p[0] * 0.5 + ct * p[1]) / 1_000_000
        else:
            unknown_models.add(model)
        a = by_label[(label, model)]
        a[0] += calls; a[1] += pt; a[2] += ct; a[3] += cost; a[4] += streams
        b = by_model[model]
        b[0] += calls; b[1] += pt; b[2] += ct; b[3] += cost
    total = sum(v[3] for v in by_model.values())
    print(f"=== zuzycie OpenAI (chat.completions) od {since}, {days} dni ===")
    print(f"RAZEM szacunkowo: ${total:.2f} (~{total*USD_PLN:.0f} zl), ~${total/days:.2f}/dzien\n")
    print("wg modelu:")
    for m, (c, pt, ct, cost) in sorted(by_model.items(), key=lambda kv: -kv[1][3]):
        print(f"  {m:32s} {c:7d} wywolan  {pt/1e6:6.2f}M we / {ct/1e6:5.2f}M wy   ${cost:7.2f}")
    print("\nTOP 20 pozycji (funkcja, model):")
    for (label, m), (c, pt, ct, cost, st) in sorted(by_label.items(), key=lambda kv: -kv[1][3])[:20]:
        extra = f"  (+{st} strumieniowych bez tokenow)" if st else ""
        print(f"  ${cost:6.2f}  {c:6d}x  {label[:58]:58s} {m[:18]}{extra}")
    if unknown_models:
        print("\nmodele bez ceny w tabeli (koszt=0 w raporcie):", sorted(unknown_models))
    print("\nNie mierzone: Whisper/TTS/realtime (glos) - patrz panel OpenAI.")


main()
