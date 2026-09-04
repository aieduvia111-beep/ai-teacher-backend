/* ============================================================
   Eduvia — wspolny modal limitu darmowych uzyc (paywall).
   Uzywany identycznie w: exam_generator.html, quiz_app.html,
   notes_generator.html, lesson_planner.html, voice_conversation.html.

   Byl wczesniej zduplikowany (kopiuj-wklej) osobno w kazdym z tych
   5 plikow - user zglosil kilka bledow (brak blokady scrolla tla,
   zla odmiana liczebnika "uzyc") ktore trzeba by bylo poprawiac w
   kazdej kopii osobno. Wydzielone tutaj raz, tak jak level_picker.js.

   Kazda strona zachowuje wlasna funkcje checkLimit(feature) (bo
   kazda ma swoj wlasny obiekt LIMITS_FREE), ktora woa stad
   showLimitPopup()/useLimit().
   ============================================================ */
(function () {
  'use strict';

  var NAMES = {
    chat: 'Chatu AI', quiz: 'Quizu AI',
    notes: 'Notatek AI', exam: 'Sprawdzianów AI', voice: 'Voice AI', lesson: 'Planu nauki',
    lessonDay: 'odznaczania dni planu', flashcards: 'Fiszek AI'
  };

  // Poprawna polska odmiana liczebnika przy "darmowych uzyc" - user zglosil
  // ze "Wykorzystales 1 darmowych uzyc" brzmi zle (bylo na sztywno "uzyc"
  // niezaleznie od liczby). Przymiotnik "darmowe/darmowych" musi sie
  // odmieniac RAZEM z rzeczownikiem (nie tylko sam rzeczownik) - stad cala
  // fraza, nie pojedyncze slowo. Standardowa polska regula liczby mnogiej:
  // 1 -> "darmowe uzycie"; koncowka 2/3/4 ale NIE 12/13/14 -> "darmowe
  // uzycia"; reszta -> "darmowych uzyc".
  function freeUsesPhrase(n) {
    if (n === 1) return 'darmowe użycie';
    var lastDigit = n % 10;
    var lastTwo = n % 100;
    if (lastDigit >= 2 && lastDigit <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return 'darmowe użycia';
    return 'darmowych użyć';
  }

  function useLimit(feature) {
    var today = new Date().toISOString().split('T')[0];
    var uid = localStorage.getItem('eduvia_uid') || 'anon';
    var key = 'eduvia_limit_' + feature + '_' + uid + '_' + today;
    var used = parseInt(localStorage.getItem(key) || '0');
    localStorage.setItem(key, used + 1);
  }

  function closeLimitPopup() {
    var el = document.getElementById('limitPopup');
    if (el) el.remove();
    // Blokada scrolla tla (patrz showLimitPopup) - zdejmowana przy kazdym
    // zamknieciu, zeby strona pod spodem znow dala sie przewijac.
    document.body.style.overflow = '';
  }

  function showLimitPopup(feature, limit) {
    var old = document.getElementById('limitPopup');
    if (old) old.remove();

    var name = NAMES[feature] || feature;

    var popup = document.createElement('div');
    popup.id = 'limitPopup';
    popup.style.cssText =
      'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;' +
      'background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);padding:20px;';

    var bodyText = feature === 'voice'
      ? 'Wykorzystałeś dzisiejszy darmowy limit rozmów (5 minut).'
      : 'Wykorzystałeś ' + limit + ' ' + freeUsesPhrase(limit) + ' dzisiaj.';

    popup.innerHTML =
      '<div style="' +
      'background:#0f0f18;border:1px solid rgba(124,106,255,0.3);border-radius:22px;' +
      'padding:32px 28px;max-width:380px;width:100%;min-height:398px;box-sizing:border-box;text-align:center;' +
      'box-shadow:0 0 60px rgba(124,106,255,0.15);position:relative;' +
      'animation:popIn .3s cubic-bezier(.34,1.56,.64,1);' +
      '">' +
      '<style>@keyframes popIn{from{opacity:0;transform:scale(.85)}to{opacity:1;transform:scale(1)}}</style>' +
      '<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,rgba(124,106,255,.2),rgba(124,106,255,.05));border:1px solid rgba(124,106,255,.3);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">' +
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' +
      '</div>' +
      '<div style="font-family:\'Syne\',sans-serif;font-size:1.2em;font-weight:800;color:#eeeef5;margin-bottom:8px;">' +
      'Limit ' + name + ' wyczerpany' +
      '</div>' +
      '<p style="color:#8888a0;font-size:.85em;line-height:1.6;margin-bottom:20px;">' +
      bodyText + '<br>Kup <strong style="color:#a78bfa">Pro</strong> i ucz się bez limitów!' +
      '</p>' +
      '<div style="background:rgba(124,106,255,.06);border:1px solid rgba(124,106,255,.15);border-radius:12px;padding:12px 16px;margin-bottom:20px;text-align:left;">' +
      '<div style="font-size:.75em;color:#55556a;margin-bottom:6px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;">Plan Pro — 29 zł/mies</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Nieograniczony Chat, Fiszki, Quiz' +
      '</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Nieograniczone Notatki i Sprawdziany' +
      '</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Voice AI i Plan nauki bez limitów' +
      '</div>' +
      '</div>' +
      '<button onclick="window.location.href=\'pricing.html\'" style="' +
      'width:100%;padding:13px;background:linear-gradient(135deg,#7c6aff,#5b4fcf);' +
      'border:none;border-radius:12px;color:white;font-family:\'Syne\',sans-serif;' +
      'font-size:.88em;font-weight:700;cursor:pointer;margin-bottom:10px;' +
      'box-shadow:0 0 20px rgba(124,106,255,.3);transition:all .2s;letter-spacing:.03em;' +
      '" onmouseover="this.style.transform=\'translateY(-1px)\'" onmouseout="this.style.transform=\'none\'">' +
      'Kup Pro — bez limitów →' +
      '</button>' +
      '<button onclick="window.EduviaLimitModal.close()" style="' +
      'width:100%;padding:10px;background:transparent;border:1px solid rgba(255,255,255,.08);' +
      'border-radius:12px;color:#55556a;font-family:\'DM Sans\',sans-serif;' +
      'font-size:.82em;cursor:pointer;transition:all .2s;' +
      '" onmouseover="this.style.borderColor=\'rgba(255,255,255,.15)\';this.style.color=\'#8888a0\'" onmouseout="this.style.borderColor=\'rgba(255,255,255,.08)\';this.style.color=\'#55556a\'">' +
      'Może później' +
      '</button>' +
      '</div>';

    // NAPRAWIONE (user 04.09.2026, mobile: "w innych funkcjach trzeba
    // przewinac na srodek, zeby zobaczyc komunikat, w czacie tak nie ma"):
    // roznica miedzy stronami - chat.html ma na <body> overflow:hidden
    // (strona nigdy sie nie przewija), pozostale strony (Quiz, Sprawdzian,
    // Voice, Notatki, Plan nauki) przewijaja sie normalnie. Na mobile
    // (Safari/Chrome z chowajacym sie paskiem adresu) position:fixed;inset:0
    // bywa liczone wzgledem WIEKSZEGO viewportu (bez paska adresu) niz to,
    // co faktycznie widac, gdy strona jest przewinieta - wiec popup
    // renderuje sie "ponizej" aktualnie widocznego fragmentu ekranu i
    // trzeba przewinac, zeby go zobaczyc. Wymuszenie scrollTo(0,0) PRZED
    // pokazaniem popupu naprawia to niezaleznie od tego, gdzie user byl
    // przewiniety.
    window.scrollTo(0, 0);
    document.body.appendChild(popup);
    // Blokada scrolla tla, dopoki modal jest otwarty - to jest BLOKADA
    // uniemozliwiajaca dalsze dzialanie (paywall), wiec strona pod spodem
    // nie powinna dawac sie przewijac, dopoki user nie podejmie decyzji.
    document.body.style.overflow = 'hidden';
    popup.addEventListener('click', function (e) {
      if (e.target === popup) closeLimitPopup();
    });
  }

  window.EduviaLimitModal = {
    show: showLimitPopup,
    close: closeLimitPopup,
    useLimit: useLimit
  };
  // Nazwy globalne zachowane dla wstecznej zgodnosci - kazda strona
  // wywoluje je dzis jako showLimitPopup(...)/useLimit(...) bez prefiksu.
  window.showLimitPopup = showLimitPopup;
  window.useLimit = useLimit;
})();
