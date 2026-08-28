# TODO

## Niski priorytet

- **Dogenerowanie zadan OTWARTYCH przy odrzuceniu (Sprawdzian).**
  Kiedy Warstwa 2.5 (blind-check AI-2, patrz `app/blind_verify.py`)
  odrzuci zadanie z Czesci B (otwarte), `_fill_missing_exam_questions`
  dogenerowuje ZAMKNIETE zamienniki (jedyny typ, jaki dzis potrafi
  generowac `_get_exam_data_raw_parallel` w rundach uzupelniajacych -
  patrz komentarz "STRUKTURA: TYLKO sekcja A (zamkniete). ZAKAZ sekcji
  B." w `app/exam_pdf_generator.py`). Calkowita liczba zadan w
  sprawdzianie ZAWSZE sie zgadza - jedyny efekt to, ze proporcja
  Czesc A / Czesc B moze sie nieznacznie przesunac w strone wiecej
  zamknietych, jesli akurat otwarte zostalo odrzucone.
  Pelna naprawa wymaga osobnego generatora "tylko zadania otwarte" +
  osobnego liczenia brakujacych zamknietych/otwartych w petli
  dogenerowania. User (28.08.2026): "to NIEPILNE, drobna kosmetyczna
  sprawa... zapisz jako TODO niskiego priorytetu, NIE naprawiaj teraz."
