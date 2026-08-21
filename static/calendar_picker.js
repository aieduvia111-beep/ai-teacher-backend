/* ============================================================
   Eduvia — wspólny komponent wyboru daty (kalendarz)
   Ta sama logika/wygląd używane w pełnej wersji (ankieta
   onboardingowa, ekran 3) i w wersji kompaktowej (karta
   sprawdzianu w Dashboardzie) - patrz calendar_picker.css.

   Użycie:
     EduviaCalendar.render('containerId', {
       value: '2026-08-28',        // opcjonalna wstępnie wybrana data (ISO)
       disablePast: true,          // domyślnie true - dni przed dzisiaj nieklikalne
       showSelectedLabel: true,    // domyślnie true dla render(), false dla renderCompact()
       onSelect: function(isoDate, dateObj) { ... }
     });
     EduviaCalendar.renderCompact('containerId', { ...te same opcje... });
     EduviaCalendar.setValue('containerId', '2026-09-05'); // programowa zmiana (np. przy "Zmień termin")
     EduviaCalendar.getValue('containerId'); // -> ISO string albo null

   Kazdy kontener trzyma WLASNY stan (miesiac, wybrana data) - w
   przeciwienstwie do oryginalnej wersji z onboarding.html, ktora
   uzywala pojedynczych globalnych zmiennych (dzialalo tylko dla
   jednej instancji na strone).
   ============================================================ */
(function () {
  'use strict';

  var MONTHS_GEN = ['stycznia','lutego','marca','kwietnia','maja','czerwca','lipca','sierpnia','września','października','listopada','grudnia'];
  var MONTHS_NOM = ['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'];
  var WEEKDAYS = ['Niedziela','Poniedziałek','Wtorek','Środa','Czwartek','Piątek','Sobota'];

  var instances = {}; // containerId -> {viewDate, selectedDate, opts, els}

  function isoFromDate(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function dateFromIso(iso) {
    var parts = iso.split('-').map(Number);
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function renderGrid(state) {
    var y = state.viewDate.getFullYear(), m = state.viewDate.getMonth();
    state.els.monthLabel.textContent = MONTHS_NOM[m] + ' ' + y;

    var firstOfMonth = new Date(y, m, 1);
    var startOffset = firstOfMonth.getDay() - 1;
    if (startOffset < 0) startOffset = 6;
    var daysInMonth = new Date(y, m + 1, 0).getDate();
    var daysInPrevMonth = new Date(y, m, 0).getDate();

    var grid = state.els.grid;
    grid.innerHTML = '';
    var today = new Date(); today.setHours(0, 0, 0, 0);

    for (var i = startOffset - 1; i >= 0; i--) {
      var pd = document.createElement('div');
      pd.className = 'cal-day muted';
      pd.textContent = daysInPrevMonth - i;
      grid.appendChild(pd);
    }
    var _loop = function (day) {
      var cellDate = new Date(y, m, day);
      var d = document.createElement('div');
      d.className = 'cal-day';
      d.textContent = day;
      var isPast = state.opts.disablePast && cellDate.getTime() < today.getTime();
      if (isPast) {
        d.classList.add('past');
      } else {
        if (cellDate.getTime() === today.getTime()) d.classList.add('today');
        if (state.selectedDate && cellDate.getTime() === state.selectedDate.getTime()) d.classList.add('selected');
        d.addEventListener('click', function () {
          state.selectedDate = cellDate;
          renderGrid(state);
          updateSelectedLabel(state);
          if (typeof state.opts.onSelect === 'function') state.opts.onSelect(isoFromDate(cellDate), cellDate);
        });
      }
      grid.appendChild(d);
    };
    for (var day = 1; day <= daysInMonth; day++) _loop(day);

    var totalCells = startOffset + daysInMonth;
    var remaining = (7 - (totalCells % 7)) % 7;
    for (var j = 1; j <= remaining; j++) {
      var nd = document.createElement('div');
      nd.className = 'cal-day muted';
      nd.textContent = j;
      grid.appendChild(nd);
    }
  }

  function updateSelectedLabel(state) {
    if (!state.els.selectedLabel) return;
    var el = state.els.selectedLabel;
    if (!state.selectedDate) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    var wd = WEEKDAYS[state.selectedDate.getDay()];
    el.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
      + '<span><strong>' + wd + ', ' + state.selectedDate.getDate() + ' ' + MONTHS_GEN[state.selectedDate.getMonth()] + ' ' + state.selectedDate.getFullYear() + '</strong></span>';
  }

  function build(containerId, opts, compact) {
    var container = document.getElementById(containerId);
    if (!container) return;
    opts = opts || {};
    var showLabel = opts.showSelectedLabel != null ? opts.showSelectedLabel : !compact;

    var initialDate = opts.value ? dateFromIso(opts.value) : null;
    var state = {
      viewDate: initialDate ? new Date(initialDate.getFullYear(), initialDate.getMonth(), 1) : new Date(),
      selectedDate: initialDate,
      opts: { disablePast: opts.disablePast !== false, onSelect: opts.onSelect },
      els: {}
    };

    container.innerHTML =
      '<div class="cal-widget' + (compact ? ' cal-compact' : '') + '">'
      + '<div class="cal-nav">'
      + '<button type="button" class="cal-nav-btn" data-dir="-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M15 18l-6-6 6-6"/></svg></button>'
      + '<div class="cal-month-label"></div>'
      + '<button type="button" class="cal-nav-btn" data-dir="1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6"/></svg></button>'
      + '</div>'
      + '<div class="cal-weekdays"><span>PN</span><span>WT</span><span>ŚR</span><span>CZ</span><span>PT</span><span>SO</span><span>ND</span></div>'
      + '<div class="cal-grid"></div>'
      + '</div>'
      + (showLabel ? '<div class="cal-selected"></div>' : '');

    state.els.monthLabel = container.querySelector('.cal-month-label');
    state.els.grid = container.querySelector('.cal-grid');
    state.els.selectedLabel = showLabel ? container.querySelector('.cal-selected') : null;

    container.querySelectorAll('.cal-nav-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var delta = parseInt(btn.getAttribute('data-dir'), 10);
        state.viewDate = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth() + delta, 1);
        renderGrid(state);
      });
    });

    instances[containerId] = state;
    renderGrid(state);
    updateSelectedLabel(state);
  }

  window.EduviaCalendar = {
    render: function (containerId, opts) { build(containerId, opts, false); },
    renderCompact: function (containerId, opts) { build(containerId, opts, true); },
    setValue: function (containerId, isoDate) {
      var state = instances[containerId];
      if (!state) return;
      state.selectedDate = isoDate ? dateFromIso(isoDate) : null;
      state.viewDate = state.selectedDate ? new Date(state.selectedDate.getFullYear(), state.selectedDate.getMonth(), 1) : new Date();
      renderGrid(state);
      updateSelectedLabel(state);
    },
    getValue: function (containerId) {
      var state = instances[containerId];
      return (state && state.selectedDate) ? isoFromDate(state.selectedDate) : null;
    }
  };
})();
