# TODO

## Zrobione

- ~~**Dogenerowanie zadan OTWARTYCH przy odrzuceniu (Sprawdzian).**~~
  ZROBIONE 30.08.2026 (commit "Dogenerowanie zadan OTWARTYCH w B1/B2",
  staging). Real-test (n=13, rownania kwadratowe, srednia) trafil w ten
  dokladny przypadek: 12/13 z myllacym komunikatem "wyczerpano 10 prob
  dogenerowania" (realnie 1 runda) - user: "user ma zawsze dostawac tyle
  zamowien ile zamawial, ma byc szybki i bez bledow". `_get_exam_data_raw(_parallel)`
  ma teraz `only_open=True`, uzywane przez `_fill_missing_exam_questions`
  (B1) i `_apply_b2_difficulty_downgrade` (B2), gdy cel proporcji
  zamknietych jest juz osiagniety, a otwartych wciaz brakuje. Patrz
  `test_exam_open_backfill.py`.
