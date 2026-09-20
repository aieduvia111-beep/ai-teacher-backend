/* ============================================================
   Eduvia — anulowanie subskrypcji + ankieta "dlaczego odchodzisz".
   (20.09.2026, user: "6 z 10 zrezygnowalo, nie wiemy dlaczego")

   Trzy kroki w jednym oknie, w tym samym designie co limit_modal.js
   i trial_promo_modal.js (ciemna karta #0f0f18, fioletowy akcent, Inter):
     1. potwierdzenie  -> POST /api/v1/payments/cancel-subscription
     2. ankieta        -> POST /api/v1/payments/cancellation-feedback
     3. podziekowanie

   Uzycie:  EduviaCancelFlow.open({ apiBase: '...', getToken: async () => idToken });
   Kody powodow musza byc zgodne z _CANCEL_REASONS w app/api/payments.py.
   ============================================================ */
(function () {
  'use strict';

  var REASONS = [
    { code: 'price', label: 'Za drogo' },
    { code: 'low_use', label: 'Za rzadko z niej korzystam' },
    { code: 'trial_only', label: 'Chciałem(am) tylko wypróbować' },
    { code: 'free_enough', label: 'Wystarczy mi plan darmowy' },
    { code: 'missing_features', label: 'Brakuje mi funkcji' },
    { code: 'quality', label: 'Jakość pytań lub odpowiedzi mnie nie przekonuje' },
    { code: 'bugs', label: 'Aplikacja działa wolno lub ma błędy' },
    { code: 'other', label: 'Inny powód' }
  ];
  var MAX_DETAILS = 500;

  var CSS =
    '@keyframes edsPop{from{opacity:0;transform:scale(.9) translateY(8px)}to{opacity:1;transform:none}}' +
    '@keyframes edsFade{from{opacity:0}to{opacity:1}}' +
    '.eds-ov{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;' +
    'background:rgba(0,0,0,.72);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);padding:20px;animation:edsFade .2s ease;}' +
    '.eds-card{background:#0f0f18;border:1px solid rgba(124,106,255,.3);border-radius:22px;padding:30px 26px 24px;' +
    'max-width:400px;width:100%;max-height:calc(100vh - 40px);overflow-y:auto;box-sizing:border-box;position:relative;' +
    'box-shadow:0 0 60px rgba(124,106,255,.15);animation:edsPop .3s cubic-bezier(.34,1.56,.64,1);' +
    'font-family:"Inter",-apple-system,"Segoe UI",sans-serif;color:#eeeef5;text-align:center;}' +
    '.eds-ico{width:60px;height:60px;border-radius:16px;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;}' +
    '.eds-ico.purple{background:linear-gradient(135deg,rgba(124,106,255,.28),rgba(124,106,255,.08));border:1px solid rgba(124,106,255,.4);}' +
    '.eds-ico.green{background:linear-gradient(135deg,rgba(34,211,160,.26),rgba(34,211,160,.07));border:1px solid rgba(34,211,160,.4);}' +
    '.eds-h{font-size:1.2em;font-weight:800;margin:0 0 8px;color:#eeeef5;}' +
    '.eds-p{color:#8888a0;font-size:.86em;line-height:1.6;margin:0 0 18px;}' +
    '.eds-p b{color:#eeeef5;font-weight:600;}' +
    '.eds-sub{font-size:.7em;color:#55556a;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin:0 0 10px;text-align:left;}' +
    '.eds-list{display:flex;flex-direction:column;gap:7px;margin-bottom:12px;text-align:left;}' +
    '.eds-opt{display:flex;align-items:center;gap:12px;width:100%;padding:10px 14px;background:rgba(255,255,255,.03);' +
    'border:1px solid rgba(255,255,255,.08);border-radius:14px;color:#eeeef5;font-family:inherit;font-size:.86em;font-weight:500;' +
    'cursor:pointer;text-align:left;transition:border-color .18s,background .18s;}' +
    '.eds-opt:hover{border-color:rgba(124,106,255,.4);}' +
    '.eds-opt:focus-visible{outline:2px solid #a78bfa;outline-offset:2px;}' +
    '.eds-opt[aria-checked="true"]{border-color:#7c6aff;background:rgba(124,106,255,.12);}' +
    '.eds-radio{width:18px;height:18px;border-radius:50%;border:2px solid #55556a;flex-shrink:0;position:relative;transition:border-color .18s;}' +
    '.eds-opt[aria-checked="true"] .eds-radio{border-color:#a78bfa;}' +
    '.eds-opt[aria-checked="true"] .eds-radio::after{content:"";position:absolute;inset:3px;border-radius:50%;background:#a78bfa;}' +
    '.eds-ta{width:100%;box-sizing:border-box;min-height:74px;resize:vertical;margin:0 0 4px;padding:12px 14px;background:rgba(255,255,255,.03);' +
    'border:1px solid rgba(255,255,255,.08);border-radius:14px;color:#eeeef5;font-family:inherit;font-size:.85em;line-height:1.5;outline:none;}' +
    '.eds-ta:focus{border-color:#7c6aff;}' +
    '.eds-ta::placeholder{color:#55556a;}' +
    '.eds-cnt{text-align:right;font-size:.68em;color:#55556a;margin-bottom:14px;}' +
    '.eds-btn{width:100%;padding:13px;border:none;border-radius:12px;font-family:inherit;font-size:.88em;font-weight:700;cursor:pointer;' +
    'margin-bottom:10px;transition:transform .15s,opacity .15s;letter-spacing:.02em;}' +
    '.eds-btn:focus-visible{outline:2px solid #a78bfa;outline-offset:2px;}' +
    '.eds-btn.primary{background:linear-gradient(135deg,#7c6aff,#5b4fcf);color:#fff;box-shadow:0 0 20px rgba(124,106,255,.3);}' +
    '.eds-btn.primary:hover:not(:disabled){transform:translateY(-1px);}' +
    '.eds-btn.primary:disabled{opacity:.4;cursor:not-allowed;box-shadow:none;}' +
    '.eds-btn.ghost{background:transparent;border:1px solid rgba(255,255,255,.08);color:#8888a0;font-weight:600;}' +
    '.eds-btn.ghost:hover:not(:disabled){border-color:rgba(255,255,255,.2);color:#eeeef5;}' +
    '.eds-btn.danger{background:transparent;border:1px solid rgba(248,113,113,.3);color:#f87171;font-weight:600;}' +
    '.eds-btn.danger:hover:not(:disabled){background:rgba(248,113,113,.08);}' +
    '.eds-btn:last-child{margin-bottom:0;}' +
    '.eds-err{color:#f87171;font-size:.8em;line-height:1.5;margin:0 0 12px;}' +
    '.eds-sep{height:1px;background:rgba(255,255,255,.07);margin:2px 0 18px;}' +
    '@media(max-width:400px){.eds-card{padding:26px 18px 20px;}}';

  var ICON_STOP = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
  var ICON_CHECK = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#22d3a0" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
  var ICON_HEART = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

  var state = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function icon(kind, svg) {
    var d = el('div', 'eds-ico ' + kind);
    d.innerHTML = svg;
    return d;
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

  function render(node) {
    state.card.innerHTML = '';
    state.card.appendChild(node);
    var focusable = state.card.querySelector('button');
    if (focusable) focusable.focus();
  }

  /* ---------- KROK 1: potwierdzenie ---------- */
  function stepConfirm() {
    var w = el('div');
    w.appendChild(icon('purple', ICON_STOP));
    w.appendChild(el('h2', 'eds-h', 'Anulować subskrypcję Pro?'));
    var p = el('p', 'eds-p');
    p.innerHTML = 'Zachowasz dostęp do <b>końca opłaconego okresu</b> (albo do końca darmowego triala). Nic więcej Cię nie obciąży.';
    w.appendChild(p);
    var err = el('p', 'eds-err');
    err.style.display = 'none';
    w.appendChild(err);
    var keep = el('button', 'eds-btn primary', 'Zostaję z Pro');
    keep.type = 'button';
    keep.onclick = close;
    var cancel = el('button', 'eds-btn danger', 'Anuluj subskrypcję');
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

  /* ---------- KROK 2: ankieta ---------- */
  function stepSurvey() {
    var w = el('div');
    w.appendChild(icon('green', ICON_CHECK));
    w.appendChild(el('h2', 'eds-h', 'Subskrypcja anulowana'));
    var when = formatDate(state.endsAt);
    var p = el('p', 'eds-p');
    p.innerHTML = when ? 'Pro zostaje aktywne do <b>' + when + '</b>.' : 'Pro zostaje aktywne do końca opłaconego okresu.';
    w.appendChild(p);
    w.appendChild(el('div', 'eds-sep'));
    w.appendChild(el('div', 'eds-sub', 'Dlaczego odchodzisz?'));

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
    var send = el('button', 'eds-btn primary', 'Wyślij');
    send.type = 'button';
    send.disabled = true;

    REASONS.forEach(function (r) {
      var b = el('button', 'eds-opt');
      b.type = 'button';
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', 'false');
      b.appendChild(el('span', 'eds-radio'));
      b.appendChild(el('span', '', r.label));
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
      send.disabled = true; send.textContent = 'Wysyłam…';
      submitFeedback(selected, ta.value).then(function () { render(stepThanks()); });
    };
    var skip = el('button', 'eds-btn ghost', 'Pomiń');
    skip.type = 'button';
    skip.onclick = close;

    w.appendChild(list); w.appendChild(ta); w.appendChild(cnt); w.appendChild(send); w.appendChild(skip);
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

  /* ---------- KROK 3: podziekowanie ---------- */
  function stepThanks() {
    var w = el('div');
    w.appendChild(icon('purple', ICON_HEART));
    w.appendChild(el('h2', 'eds-h', 'Dziękujemy!'));
    w.appendChild(el('p', 'eds-p', 'Twoja opinia pomoże nam ulepszyć Eduvię. Jeśli zmienisz zdanie, wrócisz do Pro w każdej chwili.'));
    var ok = el('button', 'eds-btn primary', 'Gotowe');
    ok.type = 'button';
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
    var card = el('div', 'eds-card');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    state = {
      opts: opts, overlay: overlay, card: card, endsAt: null, cancelled: false,
      prevOverflow: document.body.style.overflow, onClose: opts.onClose,
      onKey: function (e) { if (e.key === 'Escape') close(); }
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', state.onKey);
    render(stepConfirm());
  }

  window.EduviaCancelFlow = { open: open, close: close, REASONS: REASONS };
})();
