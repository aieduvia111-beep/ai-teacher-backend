/* ============================================================
   Eduvia — anulowanie subskrypcji + ankieta "dlaczego odchodzisz".
   (20.09.2026, user: "6 z 10 zrezygnowalo, nie wiemy dlaczego")

   Wyglad 1:1 jak ankieta poczatkowa (static/onboarding.html): pelnoekranowa
   strona z naglowkiem "E Eduvia", karta z fioletowa poswiata, zielona linijka,
   duzy naglowek, wiersze z ikonami w kwadratach, kropki postepu, przycisk
   "Dalej ->". Trzy ekrany:
     1. potwierdzenie  -> POST /api/v1/payments/cancel-subscription
     2. ankieta        -> POST /api/v1/payments/cancellation-feedback
     3. podziekowanie

   Uzycie:  EduviaCancelFlow.open({ apiBase: '...', getToken: async () => idToken });
   Kody powodow musza byc zgodne z _CANCEL_REASONS w app/api/payments.py.
   ============================================================ */
(function () {
  'use strict';

  function svg(paths) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + paths + '</svg>';
  }
  var ICONS = {
    price: svg('<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>'),
    low_use: svg('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'),
    trial_only: svg('<polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/>'),
    free_enough: svg('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'),
    missing_features: svg('<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>'),
    quality: svg('<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>'),
    bugs: svg('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
    other: svg('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>')
  };
  var REASONS = [
    { code: 'price', label: 'Za drogo' },
    { code: 'low_use', label: 'Za rzadko z niej korzystam' },
    { code: 'trial_only', label: 'Chciałem(am) tylko wypróbować' },
    { code: 'free_enough', label: 'Wystarczy mi plan darmowy' },
    { code: 'missing_features', label: 'Brakuje mi funkcji' },
    { code: 'quality', label: 'Jakość pytań lub odpowiedzi' },
    { code: 'bugs', label: 'Działa wolno lub ma błędy' },
    { code: 'other', label: 'Inny powód' }
  ];
  var MAX_DETAILS = 500;
  var ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

  var CSS =
    '@keyframes edsFadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}' +
    '@keyframes edsCardIn{from{opacity:0;transform:translateY(24px) scale(.97)}to{opacity:1;transform:none}}' +
    '.eds-ov{position:fixed;inset:0;z-index:99999;background:#07070d;overflow-y:auto;-webkit-overflow-scrolling:touch;' +
    'font-family:"Inter",-apple-system,"Segoe UI",sans-serif;color:#eeeef5;display:flex;flex-direction:column;}' +
    '.eds-hdr{position:sticky;top:0;z-index:2;padding:16px 24px;padding-top:calc(16px + env(safe-area-inset-top));display:flex;align-items:center;gap:10px;' +
    'background:rgba(7,7,13,.72);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-bottom:1px solid rgba(255,255,255,.06);flex-shrink:0;}' +
    '.eds-brand{width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#7c6aff,#4f3fcf);display:flex;align-items:center;justify-content:center;' +
    'font-weight:800;font-size:.95em;color:#fff;box-shadow:0 0 24px rgba(124,106,255,.45),inset 0 1px 0 rgba(255,255,255,.18);flex-shrink:0;}' +
    '.eds-brand-name{font-weight:800;font-size:.95em;color:#fff;letter-spacing:-.01em;}' +
    '.eds-main{flex:1;display:flex;align-items:center;justify-content:center;padding:24px 20px 40px;}' +
    '.eds-wrap{width:100%;max-width:420px;margin:auto;}' +
    '.eds-card{background:#0f0f18;border:1px solid rgba(255,255,255,.11);border-radius:22px;padding:26px 22px;display:flex;flex-direction:column;position:relative;overflow:hidden;' +
    'box-shadow:0 0 0 1px rgba(0,0,0,.3),0 24px 60px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.03);animation:edsCardIn .5s cubic-bezier(.16,1,.3,1) both;}' +
    '.eds-card::before{content:"";position:absolute;top:-60%;right:-30%;width:280px;height:280px;background:radial-gradient(circle,rgba(124,106,255,.12),transparent 70%);pointer-events:none;}' +
    '.eds-screen{position:relative;z-index:1;display:flex;flex-direction:column;animation:edsFadeUp .45s cubic-bezier(.22,1,.36,1) both;}' +
    '.eds-greet{font-size:.95em;color:#22d3a0;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:7px;}' +
    '.eds-greet svg{width:16px;height:16px;}' +
    '.eds-title{font-size:1.7em;font-weight:800;line-height:1.22;margin:0 0 8px;color:#eeeef5;}' +
    '.eds-sub{color:#8888a0;font-size:.9em;margin:0 0 22px;line-height:1.5;}' +
    '.eds-sub b{color:#eeeef5;font-weight:600;}' +
    '.eds-list{display:flex;flex-direction:column;gap:9px;}' +
    '.eds-opt{display:flex;align-items:center;gap:14px;padding:11px 14px;background:#161622;border:1.5px solid rgba(255,255,255,.06);border-radius:16px;cursor:pointer;' +
    'transition:all .25s cubic-bezier(.22,1,.36,1);text-align:left;width:100%;color:#8888a0;font-family:inherit;}' +
    '.eds-opt:hover{border-color:rgba(255,255,255,.11);transform:translateY(-1px);background:#1c1c2e;}' +
    '.eds-opt:focus-visible{outline:2px solid #a78bfa;outline-offset:2px;}' +
    '.eds-opt[aria-checked="true"]{background:linear-gradient(135deg,rgba(124,106,255,.28),rgba(124,106,255,.1));border-color:#7c6aff;' +
    'box-shadow:0 0 0 1px rgba(124,106,255,.35),0 10px 32px rgba(124,106,255,.35),inset 0 1px 0 rgba(255,255,255,.1);}' +
    '.eds-ico{width:40px;height:40px;border-radius:12px;background:#1c1c2e;border:1px solid rgba(255,255,255,.11);display:flex;align-items:center;justify-content:center;' +
    'flex-shrink:0;color:#8888a0;transition:all .25s;}' +
    '.eds-ico svg{width:20px;height:20px;}' +
    '.eds-opt[aria-checked="true"] .eds-ico{background:rgba(124,106,255,.28);border-color:rgba(124,106,255,.55);color:#a78bfa;box-shadow:0 0 20px rgba(124,106,255,.55);}' +
    '.eds-lbl{font-weight:700;font-size:.95em;color:#8888a0;transition:color .25s;line-height:1.3;}' +
    '.eds-opt[aria-checked="true"] .eds-lbl{color:#eeeef5;}' +
    '.eds-ta{width:100%;box-sizing:border-box;min-height:78px;resize:vertical;margin:12px 0 2px;padding:13px 15px;background:#161622;border:1.5px solid rgba(255,255,255,.06);' +
    'border-radius:16px;color:#eeeef5;font-family:inherit;font-size:.9em;line-height:1.5;outline:none;transition:border-color .2s;}' +
    '.eds-ta:focus{border-color:#7c6aff;}' +
    '.eds-ta::placeholder{color:#55556a;}' +
    '.eds-cnt{text-align:right;font-size:.7em;color:#55556a;}' +
    '.eds-dots{display:flex;justify-content:center;gap:8px;margin:18px 0 16px;}' +
    '.eds-dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.11);transition:all .3s cubic-bezier(.22,1,.36,1);}' +
    '.eds-dot.active{background:#a78bfa;width:24px;border-radius:5px;box-shadow:0 0 10px rgba(124,106,255,.65);}' +
    '.eds-dot.done{background:#22d3a0;box-shadow:0 0 6px rgba(34,211,160,.5);}' +
    '.eds-next{width:100%;padding:16px;background:linear-gradient(135deg,#7c6aff,#8b5cf6);border:none;border-radius:14px;color:#fff;font-family:inherit;font-size:.92em;font-weight:700;' +
    'cursor:pointer;transition:all .25s cubic-bezier(.22,1,.36,1);box-shadow:0 8px 28px rgba(124,106,255,.4),inset 0 1px 0 rgba(255,255,255,.15);' +
    'display:flex;align-items:center;justify-content:center;gap:8px;}' +
    '.eds-next svg{width:16px;height:16px;}' +
    '.eds-next:disabled{opacity:.35;cursor:not-allowed;box-shadow:none;}' +
    '.eds-next:not(:disabled):hover{transform:translateY(-2px);box-shadow:0 12px 34px rgba(124,106,255,.55),inset 0 1px 0 rgba(255,255,255,.2);}' +
    '.eds-next:not(:disabled):active{transform:scale(.98);}' +
    '.eds-next:focus-visible,.eds-skip:focus-visible{outline:2px solid #a78bfa;outline-offset:2px;}' +
    '.eds-skip{background:rgba(34,211,160,.07);border:1.5px solid rgba(34,211,160,.3);color:#22d3a0;font-family:inherit;font-size:.85em;font-weight:600;cursor:pointer;' +
    'text-align:center;padding:12px;width:100%;border-radius:13px;transition:all .2s;margin-top:10px;}' +
    '.eds-skip:hover:not(:disabled){background:rgba(34,211,160,.13);border-color:rgba(34,211,160,.5);}' +
    '.eds-skip.danger{background:rgba(248,113,113,.06);border-color:rgba(248,113,113,.3);color:#f87171;}' +
    '.eds-skip.danger:hover:not(:disabled){background:rgba(248,113,113,.12);border-color:rgba(248,113,113,.5);}' +
    '.eds-skip:disabled{opacity:.5;cursor:not-allowed;}' +
    '.eds-err{color:#f87171;font-size:.82em;line-height:1.5;margin:0 0 12px;}' +
    '.eds-big{width:64px;height:64px;border-radius:18px;margin:2px 0 16px;display:flex;align-items:center;justify-content:center;' +
    'background:rgba(34,211,160,.16);border:1px solid rgba(34,211,160,.5);color:#22d3a0;box-shadow:0 0 24px rgba(34,211,160,.4);}' +
    '.eds-big svg{width:30px;height:30px;}' +
    '@media(max-width:420px){.eds-title{font-size:1.4em;}.eds-main{padding:16px 16px 28px;}.eds-card{padding:22px 18px;}}';

  var state = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function formatDate(iso) {
    if (!iso) return null;
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return null;
      return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch (e) { return null; }
  }

  function close() {
    if (!state) return;
    if (state.overlay && state.overlay.parentNode) state.overlay.parentNode.removeChild(state.overlay);
    document.body.style.overflow = state.prevOverflow || '';
    document.removeEventListener('keydown', state.onKey);
    var onClose = state.onClose;
    state = null;
    if (typeof onClose === 'function') { try { onClose(); } catch (e) {} }
  }

  function dots(active) {
    var d = el('div', 'eds-dots');
    for (var i = 0; i < 3; i++) d.appendChild(el('div', 'eds-dot' + (i < active ? ' done' : (i === active ? ' active' : ''))));
    return d;
  }

  function greet(text, withCheck) {
    var g = el('div', 'eds-greet');
    if (withCheck) { var s = el('span'); s.innerHTML = CHECK; g.appendChild(s.firstChild); }
    g.appendChild(document.createTextNode(text));
    return g;
  }

  function render(node) {
    state.wrap.innerHTML = '';
    var card = el('div', 'eds-card');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.appendChild(node);
    state.wrap.appendChild(card);
    state.overlay.scrollTop = 0;
    var first = card.querySelector('button');
    if (first) { try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); } }
  }

  /* ---------- EKRAN 1: potwierdzenie ---------- */
  function stepConfirm() {
    var w = el('div', 'eds-screen');
    w.appendChild(greet('Zanim odejdziesz'));
    w.appendChild(el('h2', 'eds-title', 'Anulować subskrypcję Pro?'));
    var p = el('p', 'eds-sub');
    p.innerHTML = 'Zachowasz dostęp do <b>końca opłaconego okresu</b> (albo do końca darmowego triala). Nic więcej Cię nie obciąży.';
    w.appendChild(p);
    var err = el('p', 'eds-err');
    err.style.display = 'none';
    w.appendChild(err);
    w.appendChild(dots(0));
    var keep = el('button', 'eds-next');
    keep.type = 'button';
    keep.innerHTML = 'Zostaję z Pro ' + ARROW;
    keep.onclick = close;
    var cancel = el('button', 'eds-skip danger', 'Anuluj subskrypcję');
    cancel.type = 'button';
    cancel.onclick = function () {
      cancel.disabled = true; keep.disabled = true;
      cancel.textContent = 'Anuluję…';
      err.style.display = 'none';
      doCancel().then(function (res) {
        if (res.ok) { state.endsAt = res.endsAt; state.cancelled = true; render(stepSurvey()); }
        else {
          err.textContent = res.message;
          err.style.display = 'block';
          cancel.disabled = false; keep.disabled = false;
          cancel.textContent = 'Spróbuj ponownie';
        }
      });
    };
    w.appendChild(keep);
    w.appendChild(cancel);
    return w;
  }

  function doCancel() {
    return Promise.resolve(state.opts.getToken()).then(function (token) {
      if (!token) return { ok: false, message: 'Nie jesteś zalogowany. Zaloguj się ponownie.' };
      return fetch(state.opts.apiBase + '/api/v1/payments/cancel-subscription', {
        method: 'POST', headers: { 'Authorization': 'Bearer ' + token }
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d && d.success) return { ok: true, endsAt: d.ends_at || null };
        var msg = (d && (d.message || d.error)) || 'Nie udało się anulować subskrypcji.';
        if (d && d.error === 'apple_managed') msg = d.message;
        return { ok: false, message: msg };
      });
    }).catch(function () {
      return { ok: false, message: 'Brak połączenia. Spróbuj ponownie za chwilę.' };
    });
  }

  /* ---------- EKRAN 2: ankieta ---------- */
  function stepSurvey() {
    var w = el('div', 'eds-screen');
    w.appendChild(greet('Subskrypcja anulowana', true));
    w.appendChild(el('h2', 'eds-title', 'Dlaczego odchodzisz?'));
    var when = formatDate(state.endsAt);
    var p = el('p', 'eds-sub');
    p.innerHTML = (when ? 'Pro zostaje aktywne do <b>' + when + '</b>. ' : '') + 'Jedno kliknięcie pomoże nam ulepszyć Eduvię.';
    w.appendChild(p);

    var selected = null;
    var list = el('div', 'eds-list');
    list.setAttribute('role', 'radiogroup');
    list.setAttribute('aria-label', 'Powód rezygnacji');
    var ta = el('textarea', 'eds-ta');
    ta.placeholder = 'Chcesz coś dodać? (opcjonalnie)';
    ta.maxLength = MAX_DETAILS;
    ta.style.display = 'none';
    var cnt = el('div', 'eds-cnt', '0/' + MAX_DETAILS);
    cnt.style.display = 'none';
    var send = el('button', 'eds-next');
    send.type = 'button';
    send.disabled = true;
    send.innerHTML = 'Wyślij ' + ARROW;

    REASONS.forEach(function (r) {
      var b = el('button', 'eds-opt');
      b.type = 'button';
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', 'false');
      var ic = el('span', 'eds-ico'); ic.innerHTML = ICONS[r.code] || '';
      b.appendChild(ic);
      b.appendChild(el('span', 'eds-lbl', r.label));
      b.onclick = function () {
        selected = r.code;
        Array.prototype.forEach.call(list.children, function (c) { c.setAttribute('aria-checked', 'false'); });
        b.setAttribute('aria-checked', 'true');
        ta.style.display = 'block'; cnt.style.display = 'block';
        send.disabled = false;
      };
      list.appendChild(b);
    });
    ta.oninput = function () { cnt.textContent = ta.value.length + '/' + MAX_DETAILS; };

    send.onclick = function () {
      if (!selected) return;
      send.disabled = true; send.innerHTML = 'Wysyłam…';
      submitFeedback(selected, ta.value).then(function () { render(stepThanks()); });
    };
    var skip = el('button', 'eds-skip', 'Pomiń');
    skip.type = 'button';
    skip.onclick = close;

    w.appendChild(list); w.appendChild(ta); w.appendChild(cnt);
    w.appendChild(dots(1));
    w.appendChild(send); w.appendChild(skip);
    return w;
  }

  function submitFeedback(reason, details) {
    return Promise.resolve(state.opts.getToken()).then(function (token) {
      if (!token) return;
      return fetch(state.opts.apiBase + '/api/v1/payments/cancellation-feedback', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason, details: (details || '').trim().slice(0, MAX_DETAILS) })
      });
    }).catch(function () { /* cicho: brak ankiety nie moze psuc anulowania */ });
  }

  /* ---------- EKRAN 3: podziekowanie ---------- */
  function stepThanks() {
    var w = el('div', 'eds-screen');
    w.appendChild(greet('Gotowe'));
    w.appendChild(el('h2', 'eds-title', 'Dziękujemy!'));
    w.appendChild(el('p', 'eds-sub', 'Twoja opinia pomoże nam ulepszyć Eduvię. Jeśli zmienisz zdanie, wrócisz do Pro w każdej chwili.'));
    w.appendChild(dots(2));
    var ok = el('button', 'eds-next');
    ok.type = 'button';
    ok.innerHTML = 'Zamknij ' + ARROW;
    ok.onclick = close;
    w.appendChild(ok);
    return w;
  }

  function open(opts) {
    if (state) return;
    if (!opts || !opts.apiBase || typeof opts.getToken !== 'function') return;
    if (!document.getElementById('edsStyle')) {
      var st = document.createElement('style');
      st.id = 'edsStyle';
      st.textContent = CSS;
      document.head.appendChild(st);
    }
    var overlay = el('div', 'eds-ov');
    var hdr = el('div', 'eds-hdr');
    hdr.appendChild(el('div', 'eds-brand', 'E'));
    hdr.appendChild(el('div', 'eds-brand-name', 'Eduvia'));
    var main = el('div', 'eds-main');
    var wrap = el('div', 'eds-wrap');
    main.appendChild(wrap);
    overlay.appendChild(hdr);
    overlay.appendChild(main);
    document.body.appendChild(overlay);
    state = {
      opts: opts, overlay: overlay, wrap: wrap, endsAt: null, cancelled: false,
      prevOverflow: document.body.style.overflow, onClose: opts.onClose,
      onKey: function (e) { if (e.key === 'Escape') close(); }
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', state.onKey);
    render(stepConfirm());
  }

  window.EduviaCancelFlow = { open: open, close: close, REASONS: REASONS };
})();
