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

  // NOWE (wrzesien 2026, App Store IAP): 39,99 zl na natywnej iOS (DOKLADNA
  // cena produktu "com.eduvia.ios.pro.monthly" w App Store Connect - StoreKit,
  // prowizja Apple), 30 zl wszedzie indziej (Android/Web, Stripe -
  // NAPRAWIONE 11.09.2026: wyrownano do realnej ceny Stripe Price, patrz
  // pricing.html).
  // NAPRAWIONE: samo "PWAShell" w UA bylo zawodne na realnym urzadzeniu
  // (patrz pelne uzasadnienie w login.html) - dodano niepodrabialny sygnal
  // (obecnosc mostka window.webkit.messageHandlers), niezalezny od UA.
  var isIosApp = navigator.userAgent.includes('PWAShell') || !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.print);
  var PRO_PRICE = isIosApp ? '39,99' : '30';

  // NOWE (07.09.2026, promocja ograniczona czasowo - patrz PROMO_DEADLINE w
  // app/services/stripe_service.py): identyczny mechanizm co
  // trial_promo_modal.js - domyslnie 7 (TYLKO Android/Web), odpalane od
  // razu przy zaladowaniu skryptu.
  var TRIAL_DAYS = 7;
  var _isPrivateLAN = /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(location.hostname);
  var BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1') ? 'http://localhost:8000' : _isPrivateLAN ? location.origin : 'https://eduvia-backend-2.onrender.com';
  if (!isIosApp) {
    fetch(BASE + '/api/v1/payments/trial-info').then(function (r) { return r.json(); }).then(function (info) {
      TRIAL_DAYS = info.trial_days || 7;
    }).catch(function () {});
  }

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

  // NOWE (wrzesien 2026, user: "musza poczuc wartosc ze Pro jest o wiele
  // lepsze zeby podali karte") - popup pokazywal SUCHA liste funkcji Pro,
  // identyczna dla kazdego, niezaleznie co user realnie dzis osiagnal.
  // Ponizej: prawdziwe (nie zmyslone) dane z localStorage - XP i seria dni
  // sa NAPRAWDE zapisywane (patrz dashboard_FINAL.html), a liczba dzisiaj
  // wykorzystanych uzyc danej funkcji to dokladnie parametr "limit" (skoro
  // popup pokazuje sie WLASNIE dlatego, ze user dobil do tego limitu).
  //
  // Stylistycznie: NIE nowy "AI-dashboard" wyglad (pigulki/ikony/glow) -
  // user to odrzucil ("wyglada jakby AI zrobil"). Uzyty ponizej box to
  // DOKLADNIE ten sam wzorzec co juz istnieje w tym kodzie (patrz
  // .stat-box/.stat-val/.stat-lbl w quiz_app.html, ekran wynikow quizu) -
  // plaski box #161622, cienki border, duza liczba (Inter 800), maly szary
  // podpis pod spodem. Zero ikon/gradientow/swiecenia - to nie jest
  // spojne z reszta apki.
  function statBoxHtml(value, label, color) {
    return '<div style="flex:1;background:#161622;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:12px 8px;text-align:center;">' +
      '<div style="font-family:\'Inter\',sans-serif;font-size:1.3em;font-weight:800;color:' + color + ';">' + value + '</div>' +
      '<div style="font-size:.66em;color:#8888a0;margin-top:3px;text-transform:uppercase;letter-spacing:.05em;">' + label + '</div>' +
      '</div>';
  }

  function valueRecapHtml() {
    var xp = parseInt(localStorage.getItem('eduvia_xp') || '0', 10) || 0;
    var streak = parseInt(localStorage.getItem('eduvia_streak') || '0', 10) || 0;
    var boxes = '';
    if (streak > 1) boxes += statBoxHtml(streak, 'dni serii', '#f5a623');
    if (xp > 0) boxes += statBoxHtml(xp, 'XP zdobyte', '#f5a623');
    var boxesHtml = boxes ? '<div style="display:flex;gap:8px;margin-bottom:14px;">' + boxes + '</div>' : '';

    // Reszta ("wykorzystales X dzisiaj") jest juz w bodyText ponizej - tu
    // tylko dokonczenie mysli, zeby nie powtarzac tej samej liczby dwa razy.
    // NAPRAWIONE: user "komunikat malo namawia" - plaskie "bez limitu,
    // zawsze" nie odwolywalo sie do niczego konkretnego. Gdy user ma serie
    // dni, awersja do jej utraty jest silniejszym argumentem niz sama
    // lista funkcji - odwoluje sie WPROST do liczby pokazanej wyzej.
    var line = streak > 1
      ? 'Nie przerywaj <strong style="color:#a78bfa">' + streak + '-dniowej serii</strong> — z Pro uczysz się bez limitu, kiedy chcesz.'
      : 'Z <strong style="color:#a78bfa">Pro</strong> — bez limitu, kiedy tylko chcesz się uczyć.';
    var contrastHtml =
      '<p style="color:#8888a0;font-size:.82em;line-height:1.6;margin-bottom:16px;">' +
      line +
      '</p>';
    return boxesHtml + contrastHtml;
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

    // NAPRAWIONE (12.09.2026, audyt "dlaczego ludzie nie chca placic"):
    // popup NIGDY nie mowil userowi KIEDY limit sie odnowi - wygladalo
    // to jak calkowita, bezterminowa sciana zamiast "wroc jutro", co
    // pasuje do powtarzajacego sie w tym kodzie wzorca skarg o
    // niejasnosci limitow (patrz "logowalem sie na rozne konta i limit
    // byl ten sam" w 6 innych plikach). Dodano jawna informacje o
    // resecie o polnocy - uczciwiej pokazuje, ze to NIE jest "nigdy
    // wiecej", tylko "poczekaj albo zaplac za dostep od razu".
    //
    // NOWE (user: "ten komunikat jak sie skonczy limit tez ma malo
    // namawiac") - sam fakt "wykorzystales limit" to zawsze zla wiadomosc
    // podana na plasko. Jesli user ma realna serie dni (wiec limit trafil
    // kogos kto NAPRAWDE uzywa apki, nie kogos kto raz kliknal), zdanie
    // zaczyna sie od uznania tego, zanim poda fakt o limicie - kolejnosc
    // "pochwala -> fakt" zamiast "fakt -> pochwala nizej w boxach".
    var _streakForPraise = parseInt(localStorage.getItem('eduvia_streak') || '0', 10) || 0;
    var praise = _streakForPraise > 1 ? 'Świetna robota — jesteś na fali! ' : '';
    var bodyText = praise + (feature === 'voice'
      ? 'Wykorzystałeś dzisiejszy darmowy limit rozmów (5 minut). Odnawia się o północy.'
      : 'Wykorzystałeś ' + limit + ' ' + freeUsesPhrase(limit) + ' dzisiaj. Odnawia się o północy.');

    popup.innerHTML =
      '<div style="' +
      'background:#0f0f18;border:1px solid rgba(124,106,255,0.3);border-radius:22px;' +
      'padding:32px 28px;max-width:380px;width:100%;min-height:398px;max-height:calc(100vh - 40px);overflow-y:auto;box-sizing:border-box;text-align:center;' +
      'box-shadow:0 0 60px rgba(124,106,255,0.15);position:relative;' +
      'animation:popIn .3s cubic-bezier(.34,1.56,.64,1);' +
      '">' +
      '<style>@keyframes popIn{from{opacity:0;transform:scale(.85)}to{opacity:1;transform:scale(1)}}</style>' +
      '<div style="width:60px;height:60px;border-radius:16px;background:linear-gradient(135deg,rgba(124,106,255,.28),rgba(124,106,255,.08));border:1px solid rgba(124,106,255,.4);display:flex;align-items:center;justify-content:center;margin:0 auto 18px;box-shadow:0 0 26px rgba(124,106,255,.3);">' +
      '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' +
      '</div>' +
      '<div style="font-family:\'Inter\',sans-serif;font-size:1.2em;font-weight:800;color:#eeeef5;margin-bottom:8px;">' +
      'Limit ' + name + ' wyczerpany' +
      '</div>' +
      '<p style="color:#8888a0;font-size:.85em;line-height:1.6;margin-bottom:16px;">' +
      bodyText +
      '</p>' +
      valueRecapHtml() +
      '<div style="background:rgba(124,106,255,.06);border:1px solid rgba(124,106,255,.15);border-radius:14px;padding:16px 18px;margin-bottom:20px;text-align:left;">' +
      '<div style="font-size:.72em;color:#55556a;margin-bottom:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Plan Pro — ' + PRO_PRICE + ' zł/mies</div>' +
      '<div style="font-size:.83em;color:#eeeef5;display:flex;align-items:center;gap:10px;margin-bottom:9px;">' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3a0" stroke-width="2.5" style="flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Nieograniczony Chat, Fiszki, Quiz' +
      '</div>' +
      '<div style="font-size:.83em;color:#eeeef5;display:flex;align-items:center;gap:10px;margin-bottom:9px;">' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3a0" stroke-width="2.5" style="flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Nieograniczone Notatki i Sprawdziany' +
      '</div>' +
      '<div style="font-size:.83em;color:#eeeef5;display:flex;align-items:center;gap:10px;">' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3a0" stroke-width="2.5" style="flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Voice AI i Plan nauki bez limitów' +
      '</div>' +
      '</div>' +
      '<button onclick="window.location.href=\'pricing.html\'" style="' +
      'width:100%;padding:13px;background:linear-gradient(135deg,#7c6aff,#5b4fcf);' +
      'border:none;border-radius:12px;color:white;font-family:\'Inter\',sans-serif;' +
      'font-size:.88em;font-weight:700;cursor:pointer;margin-bottom:10px;' +
      'box-shadow:0 0 20px rgba(124,106,255,.3);transition:all .2s;letter-spacing:.03em;' +
      '" onmouseover="this.style.transform=\'translateY(-1px)\'" onmouseout="this.style.transform=\'none\'">' +
      'Wypróbuj ' + TRIAL_DAYS + ' dni za darmo →' +
      '</button>' +
      // NOWE (wrzesien 2026, user: "musza namowic rodzica, zeby podal
      // karte") - dziecko czesto nie ma wlasnej karty platniczej. Przycisk
      // generuje bezpieczny, wygasajacy (48h) link do publicznej strony
      // rodzic.html (bez logowania) z prawdziwymi statystykami dziecka i
      // przyciskiem zakupu Pro - patrz app/api/parent_share.py.
      '<button id="askParentBtn" style="' +
      'display:flex;align-items:center;justify-content:center;gap:7px;width:100%;padding:11px;' +
      'background:rgba(167,139,250,.08);border:1px solid rgba(167,139,250,.35);border-radius:12px;' +
      'color:#a78bfa;font-family:\'Inter\',sans-serif;font-size:.82em;font-weight:700;cursor:pointer;margin-bottom:10px;transition:all .2s;' +
      '">' +
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>' +
      'Poproś rodzica o Pro' +
      '</button>' +
      '<button onclick="window.EduviaLimitModal.close()" style="' +
      'width:100%;padding:10px;background:transparent;border:1px solid rgba(255,255,255,.08);' +
      'border-radius:12px;color:#55556a;font-family:\'Inter\',sans-serif;' +
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

    var askBtn = document.getElementById('askParentBtn');
    if (askBtn) askBtn.addEventListener('click', function () { askParent(askBtn, name); });
  }

  // NOWE: generuje link (POST /api/v1/parent-share/create, autoryzowany
  // tokenem dziecka), potem probuje natywny system share (WhatsApp/SMS/
  // Messenger - dziecko samo wybiera odbiorce, apka NIGDZIE nie zapisuje
  // numeru/maila rodzica). Bez navigator.share (desktop/stare przegladarki)
  // - link trafia do schowka, zeby dziecko mogl wkleic go recznie.
  function askParent(btn, featureName) {
    if (typeof window._getAuthToken !== 'function') {
      btn.textContent = 'Zaloguj się ponownie, aby wysłać';
      return;
    }
    var originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = 'Tworzę link…';

    window._getAuthToken().then(function (token) {
      if (!token) throw new Error('brak sesji');
      return fetch(BASE + '/api/v1/parent-share/create', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token }
      });
    }).then(function (r) {
      if (!r.ok) throw new Error('blad serwera');
      return r.json();
    }).then(function (data) {
      if (!data.success || !data.url) throw new Error('brak linku');
      var text = 'Cześć! Uczę się w Eduvia AI i właśnie wykorzystałem dzisiejszy darmowy limit ' + featureName + '. Włączysz mi Pro? ' + data.url;
      if (navigator.share) {
        navigator.share({ title: 'Eduvia AI', text: text }).catch(function () {});
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      } else {
        window.open('https://wa.me/?text=' + encodeURIComponent(text), '_blank');
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = 'Nie udało się — spróbuj ponownie';
      setTimeout(function () { btn.innerHTML = originalHtml; }, 2500);
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
