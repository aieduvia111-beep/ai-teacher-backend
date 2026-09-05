/* ============================================================
   Eduvia — informacyjny popup zachecajacy do 7-dniowego triala Pro,
   pokazywany przy otwarciu Dashboardu (nie przy wyczerpaniu limitu -
   patrz limit_modal.js dla tamtego, "twardego" paywalla).

   Cel: user (04.09.2026, po potwierdzeniu ze cala petla trial+cancel
   dziala end-to-end) chcial dodatkowy, "miekki" komunikat marketingowy
   dla darmowych userow, niezalezny od trafienia w limit - zeby
   przyciagnac do zakupu tych, ktorzy nigdy nie uzywaja apki na tyle,
   zeby zobaczyc paywall.

   Design (05.09.2026, po kilku iteracjach - user probowal "lepszy niz
   limit", potem "identyczny jak limit"): user ostatecznie zdecydowal
   1:1 = TA SAMA struktura/CSS co showLimitPopup() w limit_modal.js
   (ten sam rozmiar karty, min-height:398px, ten sam ksztalt
   feature-boxa, te same przyciski) - zmieniona TYLKO ikona (tarcza+
   checkmark zamiast samej tarczy, zeby jednak odroznic od limitu) i
   tekst (naglowek/opis/lista, pod katem "rodzice to kupuja" - patrz
   nizej). Celowo NIE ma dodatkowych elementow (badge pill, stopka
   zaufania) ktorych nie ma limit_modal.js - to byla wczesniejsza
   iteracja, zdjeta na prosbe usera o scisle 1:1.

   Copy pod katem "bardziej rodzice to kupuja" (user 05.09.2026): glowna
   obiekcja rodzica przy platnej subskrypcji dla dziecka to strach przed
   "pulapka" (zapomni anulowac, zaplaci bez wiedzy), nie brak wiedzy o
   funkcjach - stad pierwszy punkt listy to "anulujesz jednym kliknieciem",
   nie funkcja produktu.

   Pokazywany max raz na 24h na uzytkownika (localStorage, jak reszta
   dobowych licznikow w apce - patrz limit_modal.js/voice_usage_date) i
   TYLKO gdy plan === 'free' (jesli user jest w trialu lub ma Pro,
   Firestore 'plan' juz jest 'pro' - patrz dashboard_FINAL.html
   payment=success handler). Pelnoekranowe tlo jak w limit_modal.js, ale
   NIE blokuje scrolla (to nie paywall, user moze to zignorowac).
   ============================================================ */
(function () {
  'use strict';

  function shouldShow() {
    var uid = localStorage.getItem('eduvia_uid') || 'anon';
    var today = new Date().toISOString().split('T')[0];
    var key = 'eduvia_trial_promo_' + uid;
    var last = localStorage.getItem(key);
    if (last === today) return false;
    localStorage.setItem(key, today);
    return true;
  }

  function closeTrialPromo() {
    var el = document.getElementById('trialPromoPopup');
    if (el) el.remove();
    document.body.style.overflow = '';
  }

  function showTrialPromo() {
    var old = document.getElementById('trialPromoPopup');
    if (old) old.remove();

    var popup = document.createElement('div');
    popup.id = 'trialPromoPopup';
    popup.style.cssText =
      'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;' +
      'background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);padding:20px;';

    popup.innerHTML =
      '<div style="' +
      'background:#0f0f18;border:1px solid rgba(124,106,255,0.3);border-radius:22px;' +
      'padding:32px 28px;max-width:380px;width:100%;min-height:398px;box-sizing:border-box;text-align:center;' +
      'box-shadow:0 0 60px rgba(124,106,255,0.15);position:relative;' +
      'animation:trialPopIn .3s cubic-bezier(.34,1.56,.64,1);' +
      '">' +
      '<style>@keyframes trialPopIn{from{opacity:0;transform:scale(.85)}to{opacity:1;transform:scale(1)}}</style>' +
      '<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,rgba(124,106,255,.2),rgba(124,106,255,.05));border:1px solid rgba(124,106,255,.3);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">' +
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>' +
      '</div>' +
      '<div style="font-family:\'Syne\',sans-serif;font-size:1.2em;font-weight:800;color:#eeeef5;margin-bottom:8px;">' +
      'Wypróbuj Eduvia Pro' +
      '</div>' +
      '<p style="color:#8888a0;font-size:.85em;line-height:1.6;margin-bottom:20px;">' +
      '7 dni pełnego dostępu <strong style="color:#a78bfa">za darmo</strong>, bez zobowiązań.<br>Anulujesz jednym kliknięciem — jeśli zrobisz to przed końcem triala, nie zapłacisz ani grosza.' +
      '</p>' +
      '<div style="background:rgba(124,106,255,.06);border:1px solid rgba(124,106,255,.15);border-radius:12px;padding:12px 16px;margin-bottom:20px;text-align:left;">' +
      '<div style="font-size:.75em;color:#55556a;margin-bottom:6px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;">Plan Pro — 29 zł/mies (po triale)</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Anulujesz jednym kliknięciem — zero zobowiązań' +
      '</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Nieograniczony Czat AI, Quizy i Sprawdziany' +
      '</div>' +
      '<div style="font-size:.8em;color:#a78bfa;display:flex;align-items:center;gap:6px;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' +
      'Notatki, Voice AI i Plan nauki bez limitu' +
      '</div>' +
      '</div>' +
      '<button onclick="window.location.href=\'pricing.html\'" style="' +
      'width:100%;padding:13px;background:linear-gradient(135deg,#7c6aff,#5b4fcf);' +
      'border:none;border-radius:12px;color:white;font-family:\'Syne\',sans-serif;' +
      'font-size:.88em;font-weight:700;cursor:pointer;margin-bottom:10px;' +
      'box-shadow:0 0 20px rgba(124,106,255,.3);transition:all .2s;letter-spacing:.03em;' +
      '" onmouseover="this.style.transform=\'translateY(-1px)\'" onmouseout="this.style.transform=\'none\'">' +
      'Wypróbuj 7 dni za darmo →' +
      '</button>' +
      '<button onclick="window.EduviaTrialPromo.close()" style="' +
      'width:100%;padding:10px;background:transparent;border:1px solid rgba(255,255,255,.08);' +
      'border-radius:12px;color:#55556a;font-family:\'DM Sans\',sans-serif;' +
      'font-size:.82em;cursor:pointer;transition:all .2s;' +
      '" onmouseover="this.style.borderColor=\'rgba(255,255,255,.15)\';this.style.color=\'#8888a0\'" onmouseout="this.style.borderColor=\'rgba(255,255,255,.08)\';this.style.color=\'#55556a\'">' +
      'Nie teraz' +
      '</button>' +
      '</div>';

    // Ta sama poprawka mobilna co limit_modal.js (patrz project_limit_modal_mobile_scroll_fix_sep2026)
    window.scrollTo(0, 0);
    document.body.appendChild(popup);
    popup.addEventListener('click', function (e) {
      if (e.target === popup) closeTrialPromo();
    });
  }

  function maybeShow(plan) {
    if (plan !== 'free') return;
    if (!shouldShow()) return;
    showTrialPromo();
  }

  window.EduviaTrialPromo = {
    maybeShow: maybeShow,
    close: closeTrialPromo
  };
})();
