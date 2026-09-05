/* ============================================================
   Eduvia — informacyjny popup zachecajacy do 7-dniowego triala Pro,
   pokazywany przy otwarciu Dashboardu (nie przy wyczerpaniu limitu -
   patrz limit_modal.js dla tamtego, "twardego" paywalla).

   Cel: user (04.09.2026, po potwierdzeniu ze cala petla trial+cancel
   dziala end-to-end) chcial dodatkowy, "miekki" komunikat marketingowy
   dla darmowych userow, niezalezny od trafienia w limit - zeby
   przyciagnac do zakupu tych, ktorzy nigdy nie uzywaja apki na tyle,
   zeby zobaczyc paywall. Design CELOWO odrozniony od limit_modal.js
   (user 05.09.2026: "ma byc lepszy design niz komunikat jak konczy sie
   limit") - to ma czuc sie jak prezent/zaproszenie, nie jak restrykcja:
   badge "oferta powitalna", ikona prezentu zamiast tarczy, duzy naglowek
   z "7 dni", lista korzysci z checkmarkami zamiast samego akapitu.

   Pokazywany max raz na 24h na uzytkownika (localStorage, jak reszta
   dobowych liczników w apce - patrz limit_modal.js/voice_usage_date) i
   TYLKO gdy plan === 'free' (jesli user jest w trialu lub ma Pro,
   Firestore 'plan' juz jest 'pro' - patrz dashboard_FINAL.html
   payment=success handler). Pelnoekranowe tlo jak w limit_modal.js, ale
   NIE blokuje scrolla (to nie paywall, user moze to zignorowac).

   Copy zmieniony 05.09.2026 (user: "bardziej rodzice to kupuja") - z
   "prezentowego" tonu na tonu ZAUFANIA: glowna obiekcja rodzica przy
   platnej subskrypcji dla dziecka to strach przed "pulapka" (zapomni
   anulowac, zaplaci bez wiedzy) - stad najwazniejszy punkt listy to
   teraz "anuluj jednym kliknieciem", nie funkcje produktu. Ikona
   zmieniona z prezentu na tarcze+checkmark (ten sam ksztalt tarczy co
   w limit_modal.js, dla spojnosci wizualnej, ale z checkiem = bezpieczne/
   zweryfikowane) zamiast "nagrody/upominku".
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
  }

  function showTrialPromo() {
    var old = document.getElementById('trialPromoPopup');
    if (old) old.remove();

    var popup = document.createElement('div');
    popup.id = 'trialPromoPopup';
    popup.style.cssText =
      'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;' +
      'background:rgba(0,0,0,0.75);backdrop-filter:blur(10px);padding:20px;';

    var feats = [
      'Anulujesz jednym kliknięciem — zero zobowiązań',
      'Nieograniczony Czat AI, Quizy i Sprawdziany',
      'Notatki, Voice AI i Plan nauki bez limitu'
    ];
    var featsHTML = feats.map(function (f) {
      return '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;">' +
        '<div style="flex-shrink:0;width:20px;height:20px;border-radius:50%;background:rgba(124,106,255,.15);display:flex;align-items:center;justify-content:center;">' +
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' +
        '</div>' +
        '<span style="font-size:.85em;color:#c8c8d8;text-align:left;">' + f + '</span>' +
        '</div>';
    }).join('');

    popup.innerHTML =
      '<div style="' +
      'background:radial-gradient(circle at 50% 0%,rgba(124,106,255,.1),transparent 60%),#0f0f18;' +
      'border:1px solid rgba(124,106,255,0.35);border-radius:26px;' +
      'padding:40px 32px 32px;max-width:420px;width:100%;box-sizing:border-box;text-align:center;' +
      'box-shadow:0 0 80px rgba(124,106,255,0.2);position:relative;overflow:hidden;' +
      'animation:trialPopIn .35s cubic-bezier(.34,1.56,.64,1);' +
      '">' +
      '<style>@keyframes trialPopIn{from{opacity:0;transform:scale(.88)}to{opacity:1;transform:scale(1)}}</style>' +
      '<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(124,106,255,.12);border:1px solid rgba(124,106,255,.3);border-radius:100px;padding:5px 14px;font-size:.7em;font-weight:700;color:#a78bfa;letter-spacing:.06em;text-transform:uppercase;margin-bottom:20px;font-family:\'Syne\',sans-serif;">' +
      '✅ Próba bez ryzyka' +
      '</div>' +
      '<div style="width:64px;height:64px;border-radius:18px;background:linear-gradient(135deg,rgba(124,106,255,.25),rgba(124,106,255,.05));border:1px solid rgba(124,106,255,.35);display:flex;align-items:center;justify-content:center;margin:0 auto 18px;box-shadow:0 0 30px rgba(124,106,255,.2);">' +
      '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>' +
      '</div>' +
      '<div style="font-family:\'Syne\',sans-serif;font-size:1.4em;font-weight:800;color:#eeeef5;margin-bottom:6px;line-height:1.25;">' +
      '7 dni Pro <span style="white-space:nowrap;background:linear-gradient(135deg,#a78bfa,#7c6aff);-webkit-background-clip:text;background-clip:text;color:transparent;">za darmo</span>' +
      '</div>' +
      '<p style="color:#8888a0;font-size:.85em;line-height:1.6;margin-bottom:18px;">' +
      'Pełny dostęp na tydzień, bez zobowiązań. Anulujesz w każdej chwili jednym kliknięciem — jeśli zrobisz to przed końcem triala, nie zapłacisz ani grosza.' +
      '</p>' +
      '<div style="background:rgba(124,106,255,.06);border:1px solid rgba(124,106,255,.15);border-radius:14px;padding:6px 18px;margin-bottom:24px;">' +
      featsHTML +
      '</div>' +
      '<button onclick="window.location.href=\'pricing.html\'" style="' +
      'width:100%;padding:15px;background:linear-gradient(135deg,#7c6aff,#5b4fcf);' +
      'border:none;border-radius:13px;color:white;font-family:\'Syne\',sans-serif;' +
      'font-size:.92em;font-weight:700;cursor:pointer;margin-bottom:10px;' +
      'box-shadow:0 4px 24px rgba(124,106,255,.35);transition:all .2s;letter-spacing:.03em;' +
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
      '<div style="margin-top:14px;font-size:.72em;color:#4a4a5e;">' +
      '🔒 Bezpieczne płatności obsługiwane przez Stripe' +
      '</div>' +
      '</div>';

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
