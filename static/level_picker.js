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

  window.EduviaLevelPicker = {
    render: render,
    describeLevelLabel: describeLevelLabel,
    encodeKey: encodeKey,
    decodeKey: decodeKey,
    STAGES: STAGES
  };
})();
