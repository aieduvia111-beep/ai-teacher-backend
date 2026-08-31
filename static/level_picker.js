/* ============================================================
   Eduvia — wspólny komponent wyboru poziomu nauki (Etap -> Klasa)
   Emituje klucze DOKŁADNIE zgodne z app/level_config.py:
     podstawowka_1..8, liceum_1..4, technikum_1..5,
     matura_podstawowa / matura_rozszerzona, studia_1..5
   (koszyki ogólne bez numeru - "liceum", "matura" itd. - są nadal
   poprawnymi wartościami wejściowymi dla `value`, ale komponent
   zawsze zapisuje wybór jako konkretną klasę po kliknięciu).

   Użycie:
     EduviaLevelPicker.render('containerId', {
       value: 'liceum_2',              // opcjonalne, wstępny wybór
       onChange: function(value, label) { ... }
     });
   ============================================================ */
(function () {
  'use strict';

  var STAGES = [
    {
      key: 'podstawowka',
      label: 'Podstawówka',
      icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
      classes: [1, 2, 3, 4, 5, 6, 7, 8].map(function (n) {
        return { key: String(n), label: 'Klasa ' + n };
      })
    },
    {
      key: 'liceum',
      label: 'Liceum',
      icon: '<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
      classes: [1, 2, 3, 4].map(function (n) {
        return { key: String(n), label: 'Klasa ' + n };
      })
    },
    {
      key: 'technikum',
      label: 'Technikum',
      icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82A1.65 1.65 0 0 0 3 13.09H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
      classes: [1, 2, 3, 4, 5].map(function (n) {
        return { key: String(n), label: 'Klasa ' + n };
      })
    },
    {
      key: 'matura',
      label: 'Matura',
      icon: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
      classes: [
        { key: 'podstawowa', label: 'Podstawowa' },
        { key: 'rozszerzona', label: 'Rozszerzona' }
      ]
    },
    {
      key: 'studia',
      label: 'Studia',
      icon: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
      classes: [1, 2, 3, 4, 5].map(function (n) {
        return { key: String(n), label: 'Rok ' + n };
      })
    }
  ];

  // Haptyka NIE jest obsługiwana tutaj - strony ładujące animations.js
  // już mają globalny listener (window._haptic + wibracja na każdy klik
  // przycisku, patrz static/animations.js), więc dublowałby wibrację na
  // klik. Strony bez animations.js (jak dawniej voice_conversation.html)
  // powinny je dołączyć, zamiast każdy komponent wynajdywał to na nowo.

  function findStage(stageKey) {
    for (var i = 0; i < STAGES.length; i++) {
      if (STAGES[i].key === stageKey) return STAGES[i];
    }
    return null;
  }

  function encodeKey(stageKey, classKey) {
    return stageKey + '_' + classKey;
  }

  function decodeKey(value) {
    if (!value) return { stageKey: null, classKey: null };
    for (var i = 0; i < STAGES.length; i++) {
      var st = STAGES[i];
      if (value === st.key) return { stageKey: st.key, classKey: null };
      var prefix = st.key + '_';
      if (value.indexOf(prefix) === 0) {
        return { stageKey: st.key, classKey: value.slice(prefix.length) };
      }
    }
    return { stageKey: null, classKey: null };
  }

  function describeLevelLabel(value) {
    var d = decodeKey(value);
    var st = findStage(d.stageKey);
    if (!st) return value || '';
    if (!d.classKey) return st.label;
    switch (d.stageKey) {
      case 'podstawowka': return 'Klasa ' + d.classKey + ' podstawówki';
      case 'liceum': return 'Klasa ' + d.classKey + ' liceum';
      case 'technikum': return 'Klasa ' + d.classKey + ' technikum';
      case 'studia': return 'Rok ' + d.classKey + ' studiów';
      case 'matura':
        var cls = null;
        for (var i = 0; i < st.classes.length; i++) {
          if (st.classes[i].key === d.classKey) cls = st.classes[i];
        }
        return 'Matura ' + (cls ? cls.label.toLowerCase() : d.classKey);
      default: return st.label;
    }
  }

  function render(container, opts) {
    opts = opts || {};
    var el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return;

    var current = decodeKey(opts.value);

    el.classList.add('lvl-picker');
    el.innerHTML = '';

    var stageGrid = document.createElement('div');
    stageGrid.className = 'lvl-stage-grid';

    var classWrap = document.createElement('div');
    classWrap.className = 'lvl-class-wrap';
    var classLabel = document.createElement('div');
    classLabel.className = 'lvl-class-label';
    classLabel.textContent = 'Wybierz klasę';
    var classRow = document.createElement('div');
    classRow.className = 'lvl-class-row';
    classWrap.appendChild(classLabel);
    classWrap.appendChild(classRow);

    function renderClasses(stageKey) {
      var st = findStage(stageKey);
      classRow.innerHTML = '';
      st.classes.forEach(function (cls) {
        var chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'lvl-class-chip';
        chip.textContent = cls.label;
        chip.dataset.class = cls.key;
        if (current.stageKey === stageKey && current.classKey === cls.key) {
          chip.classList.add('active');
        }
        chip.addEventListener('click', function () {
          Array.prototype.forEach.call(classRow.children, function (c) {
            c.classList.remove('active');
          });
          chip.classList.add('active');
          current.classKey = cls.key;
          var value = encodeKey(stageKey, cls.key);
          if (typeof opts.onChange === 'function') {
            opts.onChange(value, describeLevelLabel(value));
          }
        });
        classRow.appendChild(chip);
      });
    }

    function selectStage(stageKey) {
      // Zmiana etapu unieważnia poprzednio wybraną klasę - "Klasa 2" w
      // liceum to nie to samo co "Klasa 2" w podstawówce, więc stary
      // wybór nie może zostać wizualnie aktywny po przełączeniu etapu.
      if (current.stageKey !== stageKey) current.classKey = null;
      current.stageKey = stageKey;
      Array.prototype.forEach.call(stageGrid.children, function (b) {
        b.classList.toggle('active', b.dataset.stage === stageKey);
      });
      renderClasses(stageKey);
      classWrap.classList.add('open');
    }

    STAGES.forEach(function (st) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'lvl-stage-btn';
      btn.dataset.stage = st.key;
      btn.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        st.icon + '</svg><span>' + st.label + '</span>';
      if (current.stageKey === st.key) btn.classList.add('active');
      btn.addEventListener('click', function () {
        selectStage(st.key);
      });
      stageGrid.appendChild(btn);
    });

    el.appendChild(stageGrid);
    el.appendChild(classWrap);

    if (current.stageKey) {
      renderClasses(current.stageKey);
      classWrap.classList.add('open');
    }
  }

  // Kompaktowy tryb: jeden przycisk (ikona + etykieta + strzalka) +
  // rozwijany panel z etapem i klasa w jednym widoku (bez ekranu
  // posredniego jak w pelnym .lvl-picker). Uzywany na stronach
  // narzedzi, gdzie poziom zwykle jest juz auto-wypelniony z ankiety
  // i user tylko sporadycznie chce go zmienic.
  var PLACEHOLDER_ICON = '<path d="M22 10 12 5 2 10l10 5 10-5Z"/><path d="M6 12v5c0 1 3 2 6 2s6-1 6-2v-5"/>';

  function renderCompact(container, opts) {
    opts = opts || {};
    var el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return;

    // Niektore strony (np. voice_conversation.html: applyAutoLevel wywoluje
    // ponownie initLevelPicker() po doczytaniu profilu ucznia) wolaja
    // renderCompact DWA RAZY na tym samym kontenerze. Poniewaz panel jest
    // teraz portalowany do document.body (patrz nizej), sam el.innerHTML=''
    // juz go NIE usunie - trzeba jawnie posprzatac poprzednia instancje
    // (usunac stary panel z body + zdjac jego globalne listenery), zeby
    // nie zostawic osieroconego wezla i wyciekajacych listenerow.
    if (el._lvlCompactCleanup) el._lvlCompactCleanup();

    var current = decodeKey(opts.value);
    el.classList.add('lvl-compact');
    el.innerHTML = '';

    var wrap = document.createElement('div');
    wrap.className = 'lvl-compact-wrap';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lvl-compact-btn';

    // NAPRAWIONE (audyt Voice AI, sierpien 2026 - user zglosil: rozwijana
    // lista poziomu pojawia sie na dole ekranu, niemozliwa do przewiniecia/
    // klikniecia): panel byl `position:absolute` WEWNATRZ `wrap`, wiec byl
    // przycinany przez overflow:hidden KTOREGOKOLWIEK przodka (np.
    // .form-panel w voice_conversation.html mial DWIE konfliktujace
    // definicje - jedna z overflow-y:auto, druga, pozniejsza, z
    // overflow:hidden, ktora wygrywala w kaskadzie) - a nawet bez
    // overflow:hidden, panel (position:absolute) nie powieksza wysokosci
    // rodzica (jest wyjety z flow), wiec przy przycisku blisko dolu
    // widocznego obszaru panel renderowal sie POZA widoczna/przewijalna
    // czescia strony. Ten sam komponent (renderCompact) jest uzywany
    // IDENTYCZNIE na 7 stronach (quiz/sprawdziany/notatki/plan nauki/
    // voice/tablica/onboarding) - blad nie byl specyficzny dla Voice AI,
    // dotyczyl KAZDEJ strony, gdzie przycisk wypada blisko dolu ekranu.
    //
    // Naprawa: panel jest teraz "portalowany" do document.body z
    // position:fixed - wspolrzedne liczone w JS wzgledem VIEWPORTU
    // (getBoundingClientRect przycisku), wiec ZADEN przodek (overflow,
    // position, wysokosc) nie moze go juz przycinac ani ograniczac. Przed
    // kazdym otwarciem liczymy dostepne miejsce nad/pod przyciskiem i
    // otwieramy w GORE, jesli na dole nie ma miejsca (dokladnie zadanie
    // usera) - user NIGDY nie musi juz reczne przewijac, zeby zobaczyc
    // liste.
    var panel = document.createElement('div');
    panel.style.display = 'none';
    panel.style.position = 'fixed';

    function updateBtn() {
      var st = findStage(current.stageKey);
      var hasValue = !!(current.stageKey && current.classKey);
      var iconSvg = st ? st.icon : PLACEHOLDER_ICON;
      var label = hasValue
        ? describeLevelLabel(encodeKey(current.stageKey, current.classKey))
        : (opts.placeholder || 'Wybierz poziom');
      btn.innerHTML =
        '<svg class="lvl-compact-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' + iconSvg + '</svg>' +
        '<span class="lvl-compact-txt' + (hasValue ? '' : ' placeholder') + '">' + label + '</span>' +
        '<svg class="lvl-compact-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>';
    }

    function renderPanel() {
      panel.className = 'lvl-compact-panel';
      panel.innerHTML = '';

      var stageRow = document.createElement('div');
      stageRow.className = 'lvl-stage-row';
      STAGES.forEach(function (st) {
        var chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'lvl-stage-chip';
        if (current.stageKey === st.key) chip.classList.add('active');
        chip.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' + st.icon + '</svg><span>' + st.label + '</span>';
        chip.addEventListener('click', function () {
          if (current.stageKey !== st.key) current.classKey = null;
          current.stageKey = st.key;
          renderPanel();
          // NAPRAWIONE (31.08.2026, user zglosil realny bug: panel "wskakuje
          // na sama gore ekranu" po wybraniu etapu): renderPanel() dorenderowuje
          // siatke klas i panel realnie rosnie w wysokosc, ale pozycja (top)
          // byla policzona TYLKO RAZ przy otwarciu (gdy panel byl jeszcze
          // krotki - sam rzad etapow, bez klas) i nigdy nie byla przeliczana
          // ponownie po zmianie wysokosci tresci - na malych ekranach telefonu
          // (gdzie miejsca ponizej przycisku i tak jest malo) to bez korekty
          // pozycji moglo wypychac panel poza widoczny obszar/wymuszac dziwne
          // zachowanie przegladarki probujacej "doscrollowac" do niego.
          positionPanel();
        });
        stageRow.appendChild(chip);
      });
      panel.appendChild(stageRow);

      if (current.stageKey) {
        var st2 = findStage(current.stageKey);
        var classRow = document.createElement('div');
        classRow.className = 'lvl-class-row-compact';
        st2.classes.forEach(function (cls) {
          var c = document.createElement('button');
          c.type = 'button';
          c.className = 'lvl-class-chip-compact';
          c.textContent = cls.label;
          if (current.classKey === cls.key) c.classList.add('active');
          c.addEventListener('click', function () {
            current.classKey = cls.key;
            var value = encodeKey(current.stageKey, cls.key);
            updateBtn();
            closePanel();
            if (typeof opts.onChange === 'function') opts.onChange(value, describeLevelLabel(value));
          });
          classRow.appendChild(c);
        });
        panel.appendChild(classRow);
      }
    }

    var VIEWPORT_MARGIN = 10; // odstep od krawedzi ekranu, zeby panel nigdy nie dotykal brzegu

    function positionPanel() {
      var r = btn.getBoundingClientRect();
      var vw = document.documentElement.clientWidth;
      var vh = document.documentElement.clientHeight;
      // NAPRAWIONE (znalezione realnym testem na viewport 375px): szerokosc
      // MUSI byc ustawiona PRZED zmierzeniem offsetHeight/uzyciem do
      // pozycjonowania - bez width, panel (position:fixed, bez ograniczen)
      // mierzy sie na podstawie WLASNEJ, niczym nieograniczonej szerokosci
      // tresci (5 kafelkow etapu z white-space:nowrap na etykietach daje
      // ~457px), co na telefonie WYCHODZI POZA EKRAN w bok - dokladnie
      // ten sam rodzaj bledu co ten zglaszany przez usera, tylko w poziomie
      // zamiast w pionie. Panel MA byc szerokosci przycisku (tak jak w
      // oryginalnym CSS left:0;right:0 wzgledem .lvl-compact-wrap o
      // szerokosci 100% - to odtwarza dokladnie ten sam efekt), a wewnetrzne
      // flex/grid (majace juz min-width:0 i text-overflow:ellipsis) same
      // zawijaja/skracaja tresc do tej szerokosci.
      var panelW = Math.min(r.width, vw - 2 * VIEWPORT_MARGIN);
      panel.style.width = panelW + 'px';
      var panelH = panel.offsetHeight;

      // NAPRAWIONE x2 (31.08.2026). Pierwsza proba: user zglosil "belka
      // fruwa" (raz pod przyciskiem, raz nad, zalezne od tresci nad
      // przyciskiem) - usunalem wtedy przelaczanie gora/dol na rzecz
      // ZAWSZE w dol. To okazalo sie GORSZE: gdy user przewinie strone tak,
      // ze przycisk jest blisko dolu widocznego ekranu (typowe po
      // przewinieciu formularza na telefonie), panel (zwlaszcza po wybraniu
      // etapu, wiec z dorenderowana siatka klas - patrz fix przy
      // renderPanel() w chip.addEventListener) nie miescil sie ponizej, a
      // klamra bezpieczenstwa ponizej przypinala go do SAMEJ GORY CALEGO
      // EKRANU - daleko od przycisku, wygladalo jeszcze gorzej niz
      // pierwotny "fruwajacy" bug. Poprawne rozwiazanie: panel MA
      // przelaczac sie gora/dol (zeby zawsze zostac BLISKO/"przyklejony"
      // do przycisku, nie skakac na drugi koniec ekranu) - pierwotny bug
      // NIE byl w samym przelaczaniu, byl w tym ze pozycja nie byla
      // przeliczana ponownie po zmianie wysokosci tresci (osobny fix
      // wyzej). Z tamtym fixem juz na miejscu, przywrocenie przelaczania
      // jest bezpieczne i daje faktycznie stabilne, przewidywalne
      // zachowanie (zawsze blisko przycisku, nigdy nie "leci" przez cala
      // strone).
      var spaceBelow = vh - r.bottom - VIEWPORT_MARGIN;
      var spaceAbove = r.top - VIEWPORT_MARGIN;
      var openUp = panelH > spaceBelow && spaceAbove > spaceBelow;
      var top = openUp ? (r.top - panelH - 8) : (r.bottom + 8);
      // Zabezpieczenie na bardzo niskich ekranach (panel wiekszy niz cala
      // dostepna przestrzen w OBU kierunkach) - przypnij do krawedzi
      // viewportu zamiast wyjechac poza ekran w druga strone.
      top = Math.max(VIEWPORT_MARGIN, Math.min(top, vh - panelH - VIEWPORT_MARGIN));

      var left = r.left;
      left = Math.max(VIEWPORT_MARGIN, Math.min(left, vw - panelW - VIEWPORT_MARGIN));

      panel.style.top = top + 'px';
      panel.style.left = left + 'px';
      panel.classList.toggle('lvl-compact-panel-up', openUp);
    }

    function onDocClick(e) {
      if (!wrap.contains(e.target) && !panel.contains(e.target)) closePanel();
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') closePanel();
    }
    function onReposition() {
      if (panel.style.display !== 'none') positionPanel();
    }
    function openPanel() {
      // Defensywnie: jesli przycisk jest czesciowo poza widocznym
      // obszarem (np. na dole dlugiego formularza na telefonie),
      // doscrolluj do niego NAJPIERW - per prosba usera ("auto-scroll do
      // niej") - potem i tak liczymy dokladna pozycje ponizej.
      // UWAGA: celowo 'instant', NIE 'smooth' - ponizej dopiero co
      // otwarty panel zamyka sie na KAZDY scroll (patrz 'scroll' listener
      // nizej, potrzebny zeby panel nie zostawal "przyklejony" w starym
      // miejscu przy przewijaniu strony) - 'smooth' generowaloby wlasne
      // zdarzenia scroll W TRAKCIE animacji, ktore ten sam listener
      // wylapalby jako "user przewinal" i natychmiast zamykal dopiero co
      // otwarty panel (znaleziono i naprawiono realnym testem w
      // przegladarce - 'smooth' na stronach z html{scroll-behavior:smooth}
      // powodowalo, ze panel migal i znikal ulamek sekundy po otwarciu).
      // 'instant' konczy sie synchronicznie PRZED podpieciem listenera,
      // wiec ten wyscig jest niemozliwy.
      btn.scrollIntoView({ block: 'nearest', behavior: 'instant' });
      renderPanel();
      panel.style.visibility = 'hidden';
      panel.style.display = '';
      if (panel.parentNode !== document.body) document.body.appendChild(panel);
      positionPanel();
      panel.style.visibility = '';
      btn.classList.add('open');
      document.addEventListener('mousedown', onDocClick, true);
      document.addEventListener('keydown', onKeyDown, true);
      window.addEventListener('resize', onReposition);
      // 'scroll' nie bąbelkuje, ale w fazie capture jest widoczny dla
      // kazdego przewijanego przodka (np. .main{overflow-y:auto}) - stad
      // capture:true zamiast (nieskutecznego tu) listenera na window.
      document.addEventListener('scroll', closePanel, true);
    }
    function closePanel() {
      panel.style.display = 'none';
      btn.classList.remove('open');
      document.removeEventListener('mousedown', onDocClick, true);
      document.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('resize', onReposition);
      document.removeEventListener('scroll', closePanel, true);
    }
    el._lvlCompactCleanup = function () {
      closePanel();
      if (panel.parentNode) panel.parentNode.removeChild(panel);
    };

    btn.addEventListener('click', function () {
      if (panel.style.display === 'none') openPanel(); else closePanel();
    });

    updateBtn();
    wrap.appendChild(btn);
    el.appendChild(wrap);

    // Pozwala odswiezyc etykiete przycisku po auto-wypelnieniu z ankiety
    // bez pelnego re-renderu calego widgetu (patrz applyAutoLevel na
    // stronach narzedzi).
    el._lvlCompactSetValue = function (value) {
      current = decodeKey(value);
      updateBtn();
      if (panel.style.display !== 'none') renderPanel();
    };
  }

  // Backend eduvia - localhost wykrywany automatycznie, zeby testy
  // lokalne nigdy nie trafialy na produkcyjny serwer.
  // NAPRAWIONE: sam string "localhost"/"127.0.0.1" nie lapal testow z
  // telefonu w tej samej sieci WiFi (192.168.x.x) - lecialo do produkcji,
  // wiec auto-wypelnianie poziomu z ankiety cicho nie dzialalo na telefonie.
  var _isPrivateLAN = /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(location.hostname);
  var PROFILE_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : _isPrivateLAN ? location.origin
    : 'https://eduvia-backend-2.onrender.com';

  // Pobiera zapisany w ankiecie onboardingowej poziom ucznia i - jesli
  // istnieje - stosuje go (przez callback onLevel). Uzywane na kazdej
  // z 6 stron narzedzi (quiz/sprawdziany/notatki/plan nauki/voice/
  // tablica), zeby user NIE musial za kazdym razem recznie wybierac
  // poziomu, jesli juz go raz podal w ankiecie. Nie robi nic (cicho),
  // jesli user nie jest zalogowany, ankiety nie wypelnil, albo backend
  // jest niedostepny - picker zostaje wtedy na swojej domyslnej wartosci.
  function applyUserProfileLevel(opts) {
    opts = opts || {};
    if (!opts.user) return Promise.resolve(null);
    return opts.user.getIdToken().then(function (token) {
      return fetch(PROFILE_BASE + '/users/me', { headers: { 'Authorization': 'Bearer ' + token } });
    }).then(function (res) {
      return res.json();
    }).then(function (data) {
      if (data && data.success && data.profile && data.profile.education_level) {
        if (typeof opts.onLevel === 'function') opts.onLevel(data.profile.education_level, data.profile);
        return data.profile;
      }
      return null;
    }).catch(function (e) {
      console.warn('[EduviaLevelPicker] nie udalo sie pobrac zapisanego profilu ucznia:', e);
      return null;
    });
  }

  window.EduviaLevelPicker = {
    render: render,
    renderCompact: renderCompact,
    describeLevelLabel: describeLevelLabel,
    encodeKey: encodeKey,
    decodeKey: decodeKey,
    applyUserProfileLevel: applyUserProfileLevel,
    STAGES: STAGES
  };
})();
